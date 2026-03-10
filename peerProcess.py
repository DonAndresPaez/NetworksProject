"""
peerProcess.py - P2P BitTorrent-like file sharing peer process.
Usage:  python peerProcess.py <peer_id>

Simplified design: no pending-piece tracking. The watchdog re-triggers
requests on all unchoked connections every few seconds, making stalls
impossible. Duplicate piece deliveries are discarded safely.
"""

import sys
import socket
import threading
import time
import random
import struct
import os

from config import read_common_config, read_peer_info, num_pieces
from messages import (
    make_handshake, recv_handshake, recv_message,
    make_choke, make_unchoke, make_interested, make_not_interested,
    make_have, make_bitfield, make_request, make_piece,
    make_bitfield_bytes, bitfield_has, bitfield_set, bitfield_count,
    MSG_CHOKE, MSG_UNCHOKE, MSG_INTERESTED, MSG_NOT_INTERESTED,
    MSG_HAVE, MSG_BITFIELD, MSG_REQUEST, MSG_PIECE,
)
from file_manager import FileManager
from peer_connection import PeerConnection
from logger import (
    setup_logger, log_tcp_connect, log_tcp_connected_from,
    log_preferred_neighbors, log_optimistic_unchoke,
    log_unchoked, log_choked, log_have, log_interested, log_not_interested,
    log_downloaded_piece, log_download_complete,
)


class Peer:
    def __init__(self, peer_id: int, cfg_dir: str = "."):
        self.peer_id = peer_id
        self.cfg_dir = cfg_dir

        self.cfg = read_common_config(os.path.join(cfg_dir, "Common.cfg"))
        self.peer_list = read_peer_info(os.path.join(cfg_dir, "PeerInfo.cfg"))
        self.info = next(p for p in self.peer_list if p["id"] == peer_id)
        self.total_pieces = num_pieces(self.cfg)

        self.logger = setup_logger(peer_id, cfg_dir)
        self.fm = FileManager(peer_id, self.cfg, cfg_dir)

        has_file = self.info["has_file"]
        self.bitfield = make_bitfield_bytes(self.total_pieces, have_all=has_file)
        self.bitfield_lock = threading.Lock()

        self.connections: dict = {}
        self.connections_lock = threading.Lock()

        self.preferred: set = set()
        self.optimistic = None
        self.neighbor_lock = threading.Lock()

        # Send lock per connection is handled via sock itself; use a write lock
        self._shutdown = threading.Event()

    # ------------------------------------------------------------------
    # Start
    # ------------------------------------------------------------------

    def start(self):
        threading.Thread(target=self._listen, daemon=True).start()
        time.sleep(0.3)

        my_index = next(i for i, p in enumerate(self.peer_list) if p["id"] == self.peer_id)
        for p in self.peer_list[:my_index]:
            threading.Thread(target=self._connect_to, args=(p,), daemon=True).start()

        time.sleep(1.0)

        threading.Thread(target=self._preferred_neighbors_loop, daemon=True).start()
        threading.Thread(target=self._optimistic_unchoke_loop, daemon=True).start()
        threading.Thread(target=self._watchdog_loop, daemon=True).start()

        self._wait_for_completion()

    # ------------------------------------------------------------------
    # Networking
    # ------------------------------------------------------------------

    def _listen(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("", self.info["port"]))
        s.listen(20)
        while not self._shutdown.is_set():
            try:
                s.settimeout(1.0)
                conn, _ = s.accept()
                threading.Thread(target=self._handle_incoming, args=(conn,), daemon=True).start()
            except socket.timeout:
                continue
            except Exception:
                break

    def _handle_incoming(self, sock):
        try:
            remote_id = recv_handshake(sock)
            sock.sendall(make_handshake(self.peer_id))
        except Exception as e:
            self.logger.debug(f"Handshake error (incoming): {e}")
            sock.close()
            return
        log_tcp_connected_from(self.logger, self.peer_id, remote_id)
        conn = PeerConnection(remote_id, sock, self.peer_id)
        with self.connections_lock:
            self.connections[remote_id] = conn
        self._post_handshake(conn)
        self._message_loop(conn)

    def _connect_to(self, peer_info: dict):
        remote_id = peer_info["id"]
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((peer_info["host"], peer_info["port"]))
            sock.sendall(make_handshake(self.peer_id))
            got_id = recv_handshake(sock)
            if got_id != remote_id:
                sock.close()
                return
        except Exception as e:
            self.logger.debug(f"Connect to {remote_id} failed: {e}")
            return
        log_tcp_connect(self.logger, self.peer_id, remote_id)
        conn = PeerConnection(remote_id, sock, self.peer_id)
        with self.connections_lock:
            self.connections[remote_id] = conn
        self._post_handshake(conn)
        self._message_loop(conn)

    # ------------------------------------------------------------------
    # Post-handshake: always send bitfield
    # ------------------------------------------------------------------

    def _post_handshake(self, conn: PeerConnection):
        with self.bitfield_lock:
            bf_copy = bytearray(self.bitfield)
        try:
            conn.send(make_bitfield(bf_copy))
        except Exception as e:
            self.logger.debug(f"Error sending bitfield to {conn.remote_id}: {e}")

    # ------------------------------------------------------------------
    # Message loop
    # ------------------------------------------------------------------

    def _message_loop(self, conn: PeerConnection):
        while not self._shutdown.is_set():
            try:
                msg_type, payload = recv_message(conn.sock)
            except Exception as e:
                self.logger.debug(f"Connection closed with {conn.remote_id}: {e}")
                break
            self._handle_message(conn, msg_type, payload)

    def _handle_message(self, conn: PeerConnection, msg_type: int, payload: bytes):

        if msg_type == MSG_CHOKE:
            conn.peer_choking = True
            log_choked(self.logger, self.peer_id, conn.remote_id)

        elif msg_type == MSG_UNCHOKE:
            conn.peer_choking = False
            log_unchoked(self.logger, self.peer_id, conn.remote_id)
            self._request_piece(conn)

        elif msg_type == MSG_INTERESTED:
            conn.peer_interested = True
            log_interested(self.logger, self.peer_id, conn.remote_id)

        elif msg_type == MSG_NOT_INTERESTED:
            conn.peer_interested = False
            log_not_interested(self.logger, self.peer_id, conn.remote_id)

        elif msg_type == MSG_HAVE:
            piece_index = struct.unpack("!I", payload)[0]
            log_have(self.logger, self.peer_id, conn.remote_id, piece_index)
            if conn.bitfield is None:
                conn.bitfield = make_bitfield_bytes(self.total_pieces)
            bitfield_set(conn.bitfield, piece_index)
            self._update_interest(conn)
            if not conn.peer_choking:
                self._request_piece(conn)

        elif msg_type == MSG_BITFIELD:
            conn.bitfield = bytearray(payload)
            self._update_interest(conn)
            # If we're already unchoked by this peer, start requesting immediately
            if not conn.peer_choking:
                self._request_piece(conn)

        elif msg_type == MSG_REQUEST:
            piece_index = struct.unpack("!I", payload)[0]
            if not conn.am_choking:
                data = self.fm.read_piece(piece_index)
                try:
                    conn.send(make_piece(piece_index, data))
                except Exception as e:
                    self.logger.debug(f"Error sending piece to {conn.remote_id}: {e}")

        elif msg_type == MSG_PIECE:
            piece_index = struct.unpack("!I", payload[:4])[0]
            data = payload[4:]
            conn.last_piece_time = time.time()

            with self.bitfield_lock:
                already_have = bitfield_has(self.bitfield, piece_index)

            if not already_have:
                self.fm.write_piece(piece_index, data)
                conn.add_downloaded(len(data))

                with self.bitfield_lock:
                    bitfield_set(self.bitfield, piece_index)
                    count = bitfield_count(self.bitfield, self.total_pieces)

                log_downloaded_piece(self.logger, self.peer_id, conn.remote_id, piece_index, count)

                if count == self.total_pieces:
                    log_download_complete(self.logger, self.peer_id)

                self._broadcast_have(piece_index)

                with self.connections_lock:
                    conns = list(self.connections.values())
                for c in conns:
                    self._update_interest(c)

            # Always request next piece immediately
            if not conn.peer_choking:
                self._request_piece(conn)

    # ------------------------------------------------------------------
    # Request — just pick any piece we need that the peer has
    # No pending tracking; watchdog handles re-requests if stuck
    # ------------------------------------------------------------------

    def _request_piece(self, conn: PeerConnection):
        if conn.bitfield is None or conn.peer_choking:
            return

        with self.bitfield_lock:
            bf_copy = bytearray(self.bitfield)

        # Take a snapshot of remote bitfield to avoid race with MSG_HAVE updates
        remote_bf = bytearray(conn.bitfield)

        candidates = [
            i for i in range(self.total_pieces)
            if not bitfield_has(bf_copy, i)
            and bitfield_has(remote_bf, i)
        ]

        if not candidates:
            return

        piece_index = random.choice(candidates)
        try:
            conn.send(make_request(piece_index))
        except Exception as e:
            self.logger.debug(f"Error sending request to {conn.remote_id}: {e}")

    # ------------------------------------------------------------------
    # Watchdog — re-kick ALL unchoked connections every 3 seconds
    # This is the anti-stall guarantee
    # ------------------------------------------------------------------

    def _watchdog_loop(self):
        while not self._shutdown.is_set():
            time.sleep(3)
            with self.bitfield_lock:
                have_all = bitfield_count(self.bitfield, self.total_pieces) == self.total_pieces
            if have_all:
                continue
            with self.connections_lock:
                conns = list(self.connections.values())
            for c in conns:
                if not c.peer_choking:
                    self._request_piece(c)

    # ------------------------------------------------------------------
    # Broadcast have
    # ------------------------------------------------------------------

    def _broadcast_have(self, piece_index: int):
        with self.connections_lock:
            conns = list(self.connections.values())
        msg = make_have(piece_index)
        for c in conns:
            try:
                c.send(msg)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Interest
    # ------------------------------------------------------------------

    def _update_interest(self, conn: PeerConnection):
        if conn.bitfield is None:
            return
        with self.bitfield_lock:
            bf_copy = bytearray(self.bitfield)

        interested = any(
            bitfield_has(conn.bitfield, i) and not bitfield_has(bf_copy, i)
            for i in range(self.total_pieces)
        )

        if interested and not conn.am_interested:
            conn.am_interested = True
            try:
                conn.send(make_interested())
            except Exception:
                pass
        elif not interested and conn.am_interested:
            conn.am_interested = False
            try:
                conn.send(make_not_interested())
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Preferred neighbors
    # ------------------------------------------------------------------

    def _preferred_neighbors_loop(self):
        while not self._shutdown.is_set():
            time.sleep(self.cfg["unchoking_interval"])
            self._recalculate_preferred()

    def _recalculate_preferred(self):
        k = self.cfg["num_preferred"]
        with self.connections_lock:
            conns = list(self.connections.values())
        for c in conns:
            c.compute_rate()

        with self.bitfield_lock:
            have_all = bitfield_count(self.bitfield, self.total_pieces) == self.total_pieces

        # Per spec: if we have the full file, pick k random interested peers.
        # If leecher, pick k peers by highest download rate (bytes received from them).
        # In both cases, only consider peers that are interested in us AND haven't
        # completed the file themselves (no point unchocking a peer that's done).
        candidates = [
            c for c in conns
            if c.peer_interested
            and (c.bitfield is None or bitfield_count(c.bitfield, self.total_pieces) < self.total_pieces)
        ]
        # Always fall back to all connections so we never deadlock
        if not candidates:
            candidates = [c for c in conns if c.bitfield is None or
                          bitfield_count(c.bitfield, self.total_pieces) < self.total_pieces]
        if not candidates:
            candidates = list(conns)

        if have_all:
            # Seeder: rotate randomly so all leechers get service over time
            chosen = random.sample(candidates, min(k, len(candidates)))
        else:
            # Leecher: prefer peers who are sending us the most data
            chosen = sorted(candidates, key=lambda c: c.download_rate, reverse=True)[:k]

        new_preferred = {c.remote_id for c in chosen}

        with self.neighbor_lock:
            self.preferred = new_preferred
            opt = self.optimistic

        if new_preferred:
            log_preferred_neighbors(self.logger, self.peer_id, sorted(new_preferred))

        for c in conns:
            rid = c.remote_id
            if rid in new_preferred:
                if c.am_choking:
                    c.am_choking = False
                    try:
                        c.send(make_unchoke())
                    except Exception:
                        pass
            elif rid != opt:
                if not c.am_choking:
                    c.am_choking = True
                    try:
                        c.send(make_choke())
                    except Exception:
                        pass

    # ------------------------------------------------------------------
    # Optimistic unchoke
    # ------------------------------------------------------------------

    def _optimistic_unchoke_loop(self):
        while not self._shutdown.is_set():
            time.sleep(self.cfg["optimistic_interval"])
            self._recalculate_optimistic()

    def _recalculate_optimistic(self):
        with self.connections_lock:
            conns = list(self.connections.values())
        with self.neighbor_lock:
            preferred = self.preferred
            old_opt = self.optimistic

        candidates = [c for c in conns
                      if c.am_choking and c.peer_interested and c.remote_id not in preferred]

        if not candidates:
            return

        chosen = random.choice(candidates)
        new_opt = chosen.remote_id

        with self.neighbor_lock:
            self.optimistic = new_opt

        log_optimistic_unchoke(self.logger, self.peer_id, new_opt)

        chosen.am_choking = False
        try:
            chosen.send(make_unchoke())
        except Exception:
            pass

        if old_opt is not None and old_opt != new_opt:
            with self.neighbor_lock:
                pref = self.preferred
            if old_opt not in pref:
                old_conn = self.connections.get(old_opt)
                if old_conn and not old_conn.am_choking:
                    old_conn.am_choking = True
                    try:
                        old_conn.send(make_choke())
                    except Exception:
                        pass

    # ------------------------------------------------------------------
    # Completion
    # ------------------------------------------------------------------

    def _all_peers_done(self) -> bool:
        with self.connections_lock:
            conns = list(self.connections.values())
        with self.bitfield_lock:
            my_count = bitfield_count(self.bitfield, self.total_pieces)

        if my_count < self.total_pieces:
            return False

        # All connected peers with a known bitfield must have the full file
        for c in conns:
            if c.bitfield is None:
                return False
            if bitfield_count(c.bitfield, self.total_pieces) < self.total_pieces:
                return False

        # Must be connected to at least one other peer to confirm we're done
        return len(conns) > 0

    def _wait_for_completion(self):
        while not self._shutdown.is_set():
            if self._all_peers_done():
                self._shutdown.set()
                break
            time.sleep(2)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python peerProcess.py <peer_id>")
        sys.exit(1)
    peer_id = int(sys.argv[1])
    cfg_dir = os.path.dirname(os.path.abspath(__file__))
    peer = Peer(peer_id, cfg_dir)
    peer.start()
