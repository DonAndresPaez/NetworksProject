import socket
import sys
import threading
import time
import random

from common_config import CommonConfig
from peer_info import PeerInfoEntry
from file_manager import FileManager
from peer_logger import PeerLogger
from connection_handler import ConnectionHandler


class PeerProcess:
    def __init__(self, peer_id):
        self.peer_id = peer_id
        self.common_config = None
        self.peer_info_list = None
        self.file_manager = None
        self.logger = None
        self.connections = {}       # remote_peer_id -> ConnectionHandler
        self.requested_pieces = set()
        self.running = True
        self.optimistically_unchoked_id = -1
        self.preferred_neighbor_ids = set()
        self._lock = threading.Lock()

    def start(self):
        self.common_config = CommonConfig.load("Common.cfg")
        self.peer_info_list = PeerInfoEntry.load_all("PeerInfo.cfg")

        my_info = None
        for pi in self.peer_info_list:
            if pi.peer_id == self.peer_id:
                my_info = pi
                break

        if my_info is None:
            print(f"Peer ID {self.peer_id} not found in PeerInfo.cfg", file=sys.stderr)
            return

        self.file_manager = FileManager(self.peer_id, self.common_config, my_info.has_file)
        self.logger = PeerLogger(self.peer_id)

        # Start server thread
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind(("", my_info.port))
        server_sock.listen(10)
        server_sock.settimeout(1.0)

        def accept_loop():
            while self.running:
                try:
                    conn, _ = server_sock.accept()
                    handler = ConnectionHandler(self, conn, initiator=False)
                    handler.start()
                except socket.timeout:
                    continue
                except OSError:
                    break

        server_thread = threading.Thread(target=accept_loop, daemon=True)
        server_thread.start()

        # Connect to all peers listed before this one in PeerInfo.cfg
        for pi in self.peer_info_list:
            if pi.peer_id == self.peer_id:
                break
            connected = False
            for attempt in range(10):
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.connect((pi.host_name, pi.port))
                    handler = ConnectionHandler(self, sock, initiator=True, remote_peer_id=pi.peer_id)
                    handler.start()
                    self.logger.log_tcp_connection_to(pi.peer_id)
                    connected = True
                    break
                except ConnectionRefusedError:
                    time.sleep(1)
            if not connected:
                print(f"Could not connect to peer {pi.peer_id}", file=sys.stderr)

        # Schedule preferred neighbors selection
        def preferred_loop():
            while self.running:
                time.sleep(self.common_config.unchoking_interval)
                if not self.running:
                    break
                try:
                    self.select_preferred_neighbors()
                except Exception as e:
                    import traceback
                    traceback.print_exc()

        # Schedule optimistic unchoking
        def optimistic_loop():
            while self.running:
                time.sleep(self.common_config.optimistic_unchoking_interval)
                if not self.running:
                    break
                try:
                    self.select_optimistically_unchoked_neighbor()
                except Exception as e:
                    import traceback
                    traceback.print_exc()

        threading.Thread(target=preferred_loop, daemon=True).start()
        threading.Thread(target=optimistic_loop, daemon=True).start()

        # Wait for all peers to complete
        while self.running:
            time.sleep(1)
            if self.check_all_complete():
                self.running = False
                time.sleep(2)
                break

        # Cleanup
        try:
            server_sock.close()
        except OSError:
            pass
        for handler in list(self.connections.values()):
            handler.close()
        self.logger.close()
        print(f"Peer {self.peer_id} has finished.")

    def register_connection(self, remote_peer_id, handler):
        with self._lock:
            self.connections[remote_peer_id] = handler

    def select_preferred_neighbors(self):
        with self._lock:
            k = self.common_config.number_of_preferred_neighbors

            interested = [h for h in self.connections.values() if h.peer_interested]
            random.shuffle(interested)

            if self.file_manager.has_all_pieces():
                selected = interested[:k]
            else:
                interested.sort(key=lambda h: h.downloaded_bytes_prev, reverse=True)
                selected = interested[:k]

            new_preferred = set()
            preferred_list = []
            for h in selected:
                new_preferred.add(h.remote_peer_id)
                preferred_list.append(h.remote_peer_id)

            if preferred_list:
                self.logger.log_preferred_neighbors(preferred_list)

            for handler in self.connections.values():
                if handler.remote_peer_id in new_preferred:
                    if handler.am_choking:
                        handler.am_choking = False
                        handler.send_unchoke()
                elif handler.remote_peer_id != self.optimistically_unchoked_id:
                    if not handler.am_choking:
                        handler.am_choking = True
                        handler.send_choke()

            self.preferred_neighbor_ids = new_preferred

            for handler in self.connections.values():
                handler.downloaded_bytes_prev = handler.downloaded_bytes
                handler.downloaded_bytes = 0

    def select_optimistically_unchoked_neighbor(self):
        with self._lock:
            candidates = [
                h for h in self.connections.values()
                if h.am_choking and h.peer_interested
            ]

            # Choke previous optimistic if not preferred
            if self.optimistically_unchoked_id != -1 and self.optimistically_unchoked_id not in self.preferred_neighbor_ids:
                prev = self.connections.get(self.optimistically_unchoked_id)
                if prev is not None and not prev.am_choking:
                    prev.am_choking = True
                    prev.send_choke()

            if not candidates:
                self.optimistically_unchoked_id = -1
                return

            selected = random.choice(candidates)
            self.optimistically_unchoked_id = selected.remote_peer_id
            selected.am_choking = False
            selected.send_unchoke()

            self.logger.log_optimistically_unchoked_neighbor(selected.remote_peer_id)

    def select_piece_to_request(self, remote_peer_id):
        with self._lock:
            handler = self.connections.get(remote_peer_id)
            if handler is None:
                return -1

            available = []
            for i in range(self.file_manager.num_pieces):
                if (not self.file_manager.has_piece_at(i)
                        and handler.has_remote_piece(i)
                        and i not in self.requested_pieces):
                    available.append(i)

            if not available:
                return -1

            selected = random.choice(available)
            self.requested_pieces.add(selected)
            return selected

    def cancel_request(self, piece_index):
        with self._lock:
            self.requested_pieces.discard(piece_index)

    def piece_received(self, piece_index, data, from_peer_id):
        with self._lock:
            if self.file_manager.has_piece_at(piece_index):
                self.requested_pieces.discard(piece_index)
                return

            self.requested_pieces.discard(piece_index)
            self.file_manager.set_piece(piece_index, data)

            self.logger.log_downloaded_piece(
                from_peer_id, piece_index, self.file_manager.get_pieces_count()
            )

            if self.file_manager.has_all_pieces():
                self.logger.log_download_complete()

            # Send 'have' to all neighbors
            for handler in self.connections.values():
                handler.send_have(piece_index)

            # Update interest state for all connections
            for handler in self.connections.values():
                handler.update_interest_state()

    def check_all_complete(self):
        with self._lock:
            if not self.file_manager.has_all_pieces():
                return False
            for pi in self.peer_info_list:
                if pi.peer_id == self.peer_id:
                    continue
                handler = self.connections.get(pi.peer_id)
                if handler is None:
                    return False
                if not handler.has_remote_all_pieces():
                    return False
            return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python peerProcess.py <peerID>")
        sys.exit(1)
    peer_id = int(sys.argv[1])
    process = PeerProcess(peer_id)
    process.start()
