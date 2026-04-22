import socket
import threading
import struct
import random
import time

from handshake import create_handshake, verify_handshake
from message_handler import (
    create_message, parse_message,
    MSG_CHOKE, MSG_UNCHOKE, MSG_INTERESTED, MSG_NOT_INTERESTED,
    MSG_HAVE, MSG_BITFIELD, MSG_REQUEST, MSG_PIECE,
    make_have_payload, parse_have_payload,
    make_request_payload, parse_request_payload,
    make_piece_payload, parse_piece_payload
)
from bitfield import Bitfield
from peer_state import PeerManager, PeerState


class PeerConnector:
    def __init__(self, my_id, my_port, peer_list, logger, bitfield, common_cfg, file_manager):
        self.my_id = my_id
        self.my_port = my_port
        self.peer_list = peer_list
        self.logger = logger
        self.bitfield = bitfield          # My own Bitfield
        self.common_cfg = common_cfg
        self.file_manager = file_manager
        self.peer_manager = PeerManager()

        self.num_preferred = common_cfg['NumberOfPreferredNeighbors']
        self.unchoke_interval = common_cfg['UnchokingInterval']
        self.opt_unchoke_interval = common_cfg['OptimisticUnchokingInterval']
        self.num_pieces = bitfield.num_pieces

        # Track which pieces are currently requested (to avoid duplicate requests)
        self.requested_pieces = set()
        self.requested_lock = threading.Lock()

        # Track all peer IDs we expect to connect to (for termination check)
        self.all_peer_ids = [p['id'] for p in peer_list if p['id'] != my_id]

        # Neighbor bitfields (peer_id -> list of bits)
        self.neighbor_bitfields = {}
        self.nb_lock = threading.Lock()

        self.done = False  # Set True when everyone has the file

    # ------------------------------------------------------------------ #
    #  SERVER                                                              #
    # ------------------------------------------------------------------ #

    def start_server(self):
        try:
            server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_sock.bind(('0.0.0.0', self.my_port))
            server_sock.listen(20)
            print(f"[Server] Listening on port {self.my_port}...")
            while not self.done:
                try:
                    server_sock.settimeout(1.0)
                    client_sock, addr = server_sock.accept()
                    t = threading.Thread(target=self.handle_incoming, args=(client_sock,), daemon=True)
                    t.start()
                except socket.timeout:
                    continue
        except Exception as e:
            print(f"[Server Error] {e}")

    # ------------------------------------------------------------------ #
    #  CLIENT – connect to peers that started before us                   #
    # ------------------------------------------------------------------ #

    def connect_to_previous_peers(self):
        for peer in self.peer_list:
            if peer['id'] < self.my_id:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.connect((peer['host'], peer['port']))

                    # Handshake
                    sock.send(create_handshake(self.my_id))
                    response = self._recv_exact(sock, 32)
                    if response and verify_handshake(response, peer['id']):
                        self.logger.log_tcp_connection_to(peer['id'])
                        state = self.peer_manager.add_peer(peer['id'], sock)

                        # Send our bitfield
                        self._send_bitfield(sock)

                        # Start receive loop
                        t = threading.Thread(target=self.receive_loop, args=(sock, peer['id'], state), daemon=True)
                        t.start()
                        print(f"[Client] Connected + Bitfield sent to {peer['id']}")
                    else:
                        sock.close()
                except Exception as e:
                    print(f"[Client Error] Peer {peer['id']}: {e}")

    # ------------------------------------------------------------------ #
    #  INCOMING CONNECTION HANDLER                                         #
    # ------------------------------------------------------------------ #

    def handle_incoming(self, sock):
        try:
            data = self._recv_exact(sock, 32)
            if not data:
                sock.close()
                return
            _, remote_id = struct.unpack(">18s10xI", data)
            if verify_handshake(data, remote_id):
                sock.send(create_handshake(self.my_id))
                self.logger.log_tcp_connected_from(remote_id)
                state = self.peer_manager.add_peer(remote_id, sock)

                # Send our bitfield
                self._send_bitfield(sock)

                t = threading.Thread(target=self.receive_loop, args=(sock, remote_id, state), daemon=True)
                t.start()
                print(f"[Server] Connected + Bitfield sent to {remote_id}")
            else:
                sock.close()
        except Exception as e:
            print(f"[Handle Error] {e}")

    # ------------------------------------------------------------------ #
    #  RECEIVE LOOP – runs in background per connection                   #
    # ------------------------------------------------------------------ #

    def receive_loop(self, sock, remote_id, state: PeerState):
        try:
            while not self.done:
                # Read 4-byte length header
                header = self._recv_exact(sock, 4)
                if not header:
                    break
                msg_length = struct.unpack(">I", header)[0]
                if msg_length == 0:
                    continue

                # Read message body (type byte + payload)
                body = self._recv_exact(sock, msg_length)
                if not body:
                    break

                msg_type = body[0]
                payload = body[1:]

                self._handle_message(msg_type, payload, remote_id, state, sock)

        except Exception as e:
            print(f"[Receive Error] Peer {remote_id}: {e}")

    def _handle_message(self, msg_type, payload, remote_id, state: PeerState, sock):
        if msg_type == MSG_BITFIELD:
            self._on_bitfield(payload, remote_id, state, sock)

        elif msg_type == MSG_HAVE:
            piece_index = parse_have_payload(payload)
            self.logger.log_have(remote_id, piece_index)
            with self.nb_lock:
                if remote_id in self.neighbor_bitfields:
                    self.neighbor_bitfields[remote_id][piece_index] = 1
            # Decide interest
            self._send_interest_based_on_neighbor(remote_id, state, sock)

        elif msg_type == MSG_INTERESTED:
            self.logger.log_interested(remote_id)
            state.peer_interested = True

        elif msg_type == MSG_NOT_INTERESTED:
            self.logger.log_not_interested(remote_id)
            state.peer_interested = False

        elif msg_type == MSG_UNCHOKE:
            self.logger.log_unchoked_by(remote_id)
            state.peer_choking = False
            # Now we can request a piece from them
            self._request_piece_from(remote_id, state, sock)

        elif msg_type == MSG_CHOKE:
            self.logger.log_choked_by(remote_id)
            state.peer_choking = True

        elif msg_type == MSG_REQUEST:
            piece_index, _begin, _length = parse_request_payload(payload)
            if not state.am_choking:
                piece_data = self.file_manager.get_piece(piece_index)
                if piece_data:
                    piece_msg = create_message(MSG_PIECE, make_piece_payload(piece_index, piece_data))
                    self._send_safe(sock, piece_msg)

        elif msg_type == MSG_PIECE:
            piece_index, data = parse_piece_payload(payload)
            self.file_manager.save_piece(piece_index, data)
            self.bitfield.set_piece(piece_index)
            state.add_downloaded(len(data))

            with self.requested_lock:
                self.requested_pieces.discard(piece_index)

            num_have = sum(self.bitfield.bits)
            self.logger.log_download_piece(remote_id, piece_index, num_have)

            # Broadcast HAVE to all neighbors
            have_msg = create_message(MSG_HAVE, make_have_payload(piece_index))
            for p in self.peer_manager.all_peers():
                self._send_safe(p.sock, have_msg)

            # Check if we just completed the file
            if num_have == self.num_pieces:
                self.logger.log_download_complete()
                # Update neighbor interest state (we may no longer be interested in some)
                self._refresh_all_interest()

            # Check global completion
            self._check_global_completion()

            # Keep requesting if still unchoked
            if not state.peer_choking:
                self._request_piece_from(remote_id, state, sock)

    # ------------------------------------------------------------------ #
    #  BITFIELD HANDLING                                                   #
    # ------------------------------------------------------------------ #

    def _on_bitfield(self, payload, remote_id, state, sock):
        bits = []
        for byte in payload:
            for bit_pos in range(7, -1, -1):
                bits.append((byte >> bit_pos) & 1)
        bits = bits[:self.num_pieces]  # Trim spare bits

        with self.nb_lock:
            self.neighbor_bitfields[remote_id] = bits

        self._send_interest_based_on_neighbor(remote_id, state, sock)

    def _send_interest_based_on_neighbor(self, remote_id, state, sock):
        """Send INTERESTED or NOT_INTERESTED based on whether neighbor has pieces we need."""
        with self.nb_lock:
            nb_bits = self.neighbor_bitfields.get(remote_id, [])

        interested = any(
            i < len(nb_bits) and nb_bits[i] == 1 and not self.bitfield.has_piece(i)
            for i in range(self.num_pieces)
        )

        if interested and not state.am_interested:
            state.am_interested = True
            self._send_safe(sock, create_message(MSG_INTERESTED))
        elif not interested and state.am_interested:
            state.am_interested = False
            self._send_safe(sock, create_message(MSG_NOT_INTERESTED))

    def _refresh_all_interest(self):
        """Re-evaluate interest with all neighbors (e.g. after completing a piece)."""
        for p in self.peer_manager.all_peers():
            self._send_interest_based_on_neighbor(p.peer_id, p, p.sock)

    # ------------------------------------------------------------------ #
    #  PIECE REQUESTING                                                    #
    # ------------------------------------------------------------------ #

    def _request_piece_from(self, remote_id, state, sock):
        """Select a random piece to request from this peer."""
        with self.nb_lock:
            nb_bits = self.neighbor_bitfields.get(remote_id, [])

        with self.requested_lock:
            candidates = [
                i for i in range(self.num_pieces)
                if i < len(nb_bits)
                and nb_bits[i] == 1
                and not self.bitfield.has_piece(i)
                and i not in self.requested_pieces
            ]
            if not candidates:
                return
            piece_index = random.choice(candidates)
            self.requested_pieces.add(piece_index)

        req_msg = create_message(MSG_REQUEST, make_request_payload(piece_index, self.common_cfg['PieceSize']))
        self._send_safe(sock, req_msg)

    # ------------------------------------------------------------------ #
    #  CHOKING / UNCHOKING SCHEDULERS                                      #
    # ------------------------------------------------------------------ #

    def start_unchoke_scheduler(self):
        t = threading.Thread(target=self._unchoke_loop, daemon=True)
        t.start()

    def start_optimistic_unchoke_scheduler(self):
        t = threading.Thread(target=self._optimistic_unchoke_loop, daemon=True)
        t.start()

    def _unchoke_loop(self):
        """Every p seconds, recalculate preferred neighbors."""
        while not self.done:
            time.sleep(self.unchoke_interval)
            self._recalculate_preferred_neighbors()
            self.peer_manager.reset_all_rates()

    def _recalculate_preferred_neighbors(self):
        interested_peers = self.peer_manager.interested_in_us()
        if not interested_peers:
            return

        k = self.num_preferred

        # If we have the complete file, choose randomly
        if self.bitfield.is_complete():
            chosen = random.sample(interested_peers, min(k, len(interested_peers)))
        else:
            # Sort by download rate descending; random tie-break handled by shuffle first
            random.shuffle(interested_peers)
            chosen = sorted(interested_peers, key=lambda p: p.download_rate, reverse=True)[:k]

        chosen_ids = {p.peer_id for p in chosen}
        self.logger.log_change_preferred_neighbors(sorted(chosen_ids))

        for p in self.peer_manager.all_peers():
            if hasattr(self, '_opt_unchoked_id') and p.peer_id == self._opt_unchoked_id:
                continue
            if p.peer_id in chosen_ids:
                if p.am_choking:
                    p.am_choking = False
                    self._send_safe(p.sock, create_message(MSG_UNCHOKE))
            else:
                if not p.am_choking:
                    p.am_choking = True
                    self._send_safe(p.sock, create_message(MSG_CHOKE))

    def _optimistic_unchoke_loop(self):
        """Every m seconds, pick a random choked-but-interested neighbor to unchoke."""
        self._opt_unchoked_id = None
        while not self.done:
            time.sleep(self.opt_unchoke_interval)
            self._pick_optimistic_unchoked()

    def _pick_optimistic_unchoked(self):
        candidates = [
            p for p in self.peer_manager.all_peers()
            if p.am_choking and p.peer_interested
        ]
        if not candidates:
            return

        # Choke previous optimistic if it's not a preferred neighbor
        if self._opt_unchoked_id is not None:
            old = self.peer_manager.get(self._opt_unchoked_id)
            if old and old.am_choking is False:
                # It was unchoked by us; check if it's still a preferred neighbor
                # If we just choke it here, the preferred neighbor loop handles unchoked ones
                old.am_choking = True
                self._send_safe(old.sock, create_message(MSG_CHOKE))

        chosen = random.choice(candidates)
        self._opt_unchoked_id = chosen.peer_id
        chosen.am_choking = False
        self._send_safe(chosen.sock, create_message(MSG_UNCHOKE))
        self.logger.log_change_optimistic_unchoked(chosen.peer_id)

    # ------------------------------------------------------------------ #
    #  TERMINATION CHECK                                                   #
    # ------------------------------------------------------------------ #

    def _check_global_completion(self):
        """Check if all peers (including ourselves) have the complete file."""
        if not self.bitfield.is_complete():
            return

        with self.nb_lock:
            for pid in self.all_peer_ids:
                bits = self.neighbor_bitfields.get(pid, [])
                if len(bits) < self.num_pieces or not all(b == 1 for b in bits):
                    return  # Someone still missing pieces

        print(f"[Done] All peers have the complete file. Peer {self.my_id} shutting down.")
        self.done = True

    # ------------------------------------------------------------------ #
    #  UTILITIES                                                           #
    # ------------------------------------------------------------------ #

    def _send_bitfield(self, sock):
        """Send our bitfield only if we have at least one piece."""
        if any(b == 1 for b in self.bitfield.bits):
            bf_msg = create_message(MSG_BITFIELD, self.bitfield.get_bytes())
            self._send_safe(sock, bf_msg)

    def _send_safe(self, sock, data):
        try:
            sock.sendall(data)
        except Exception as e:
            print(f"[Send Error] {e}")

    def _recv_exact(self, sock, n):
        """Receive exactly n bytes from socket."""
        buf = b""
        while len(buf) < n:
            try:
                chunk = sock.recv(n - len(buf))
                if not chunk:
                    return None
                buf += chunk
            except Exception:
                return None
        return buf