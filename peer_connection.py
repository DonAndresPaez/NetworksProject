"""
peer_connection.py - State for a single peer-to-peer connection.
"""

import threading
import time


class PeerConnection:
    def __init__(self, remote_id: int, sock, local_id: int):
        self.remote_id = remote_id
        self.sock = sock
        self.local_id = local_id

        self.am_choking = True
        self.am_interested = False
        self.peer_choking = True
        self.peer_interested = False

        self.bitfield = None
        self.last_piece_time = time.time()

        self.bytes_downloaded = 0
        self.download_rate = 0.0
        self._lock = threading.Lock()

        # Serialize all sends on this socket — critical for correctness
        self.send_lock = threading.Lock()

    def send(self, data: bytes):
        """Thread-safe send."""
        with self.send_lock:
            self.sock.sendall(data)

    def add_downloaded(self, n: int):
        with self._lock:
            self.bytes_downloaded += n

    def compute_rate(self):
        with self._lock:
            rate = self.bytes_downloaded
            self.bytes_downloaded = 0
            self.download_rate = rate
        return rate
