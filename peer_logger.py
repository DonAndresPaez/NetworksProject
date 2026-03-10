import threading
from datetime import datetime


class PeerLogger:
    def __init__(self, peer_id):
        self.peer_id = peer_id
        self._lock = threading.Lock()
        self._file = open(f"log_peer_{peer_id}.log", "w")

    def _timestamp(self):
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _write(self, msg):
        with self._lock:
            self._file.write(msg + "\n")
            self._file.flush()

    def log_tcp_connection_to(self, remote_id):
        self._write(f"[{self._timestamp()}]: Peer {self.peer_id} makes a connection to Peer {remote_id}.")

    def log_tcp_connection_from(self, remote_id):
        self._write(f"[{self._timestamp()}]: Peer {self.peer_id} is connected from Peer {remote_id}.")

    def log_preferred_neighbors(self, neighbor_ids):
        ids = ", ".join(str(n) for n in neighbor_ids)
        self._write(f"[{self._timestamp()}]: Peer {self.peer_id} has the preferred neighbors {ids}.")

    def log_optimistically_unchoked_neighbor(self, neighbor_id):
        self._write(f"[{self._timestamp()}]: Peer {self.peer_id} has the optimistically unchoked neighbor {neighbor_id}.")

    def log_unchoking(self, remote_id):
        self._write(f"[{self._timestamp()}]: Peer {self.peer_id} is unchoked by {remote_id}.")

    def log_choking(self, remote_id):
        self._write(f"[{self._timestamp()}]: Peer {self.peer_id} is choked by {remote_id}.")

    def log_have(self, remote_id, piece_index):
        self._write(f"[{self._timestamp()}]: Peer {self.peer_id} received the 'have' message from {remote_id} for the piece {piece_index}.")

    def log_interested(self, remote_id):
        self._write(f"[{self._timestamp()}]: Peer {self.peer_id} received the 'interested' message from {remote_id}.")

    def log_not_interested(self, remote_id):
        self._write(f"[{self._timestamp()}]: Peer {self.peer_id} received the 'not interested' message from {remote_id}.")

    def log_downloaded_piece(self, remote_id, piece_index, total_pieces):
        self._write(f"[{self._timestamp()}]: Peer {self.peer_id} has downloaded the piece {piece_index} from {remote_id}. Now the number of pieces it has is {total_pieces}.")

    def log_download_complete(self):
        self._write(f"[{self._timestamp()}]: Peer {self.peer_id} has downloaded the complete file.")

    def close(self):
        with self._lock:
            self._file.close()
