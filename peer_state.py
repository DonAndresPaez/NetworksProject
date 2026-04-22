import threading
import random

class PeerState:
    """Tracks all state for a single remote peer neighbor."""
    def __init__(self, peer_id):
        self.peer_id = peer_id
        self.sock = None
        self.bitfield = None          # Bitfield object tracking what they have
        self.am_choking = True        # We are choking them (we won't send pieces)
        self.am_interested = False    # We are interested in them
        self.peer_choking = True      # They are choking us (they won't send us pieces)
        self.peer_interested = False  # They are interested in us
        self.download_rate = 0        # Bytes downloaded from them in last interval
        self.bytes_downloaded = 0     # Accumulator for current interval
        self.lock = threading.Lock()

    def reset_download_rate(self):
        with self.lock:
            self.download_rate = self.bytes_downloaded
            self.bytes_downloaded = 0

    def add_downloaded(self, num_bytes):
        with self.lock:
            self.bytes_downloaded += num_bytes


class PeerManager:
    """Central state manager for all neighbors."""
    def __init__(self):
        self.peers = {}   # peer_id -> PeerState
        self.lock = threading.Lock()

    def add_peer(self, peer_id, sock):
        with self.lock:
            state = PeerState(peer_id)
            state.sock = sock
            self.peers[peer_id] = state
        return state

    def get(self, peer_id):
        return self.peers.get(peer_id)

    def all_peers(self):
        with self.lock:
            return list(self.peers.values())

    def interested_in_us(self):
        """Peers that are interested in our data."""
        with self.lock:
            return [p for p in self.peers.values() if p.peer_interested]

    def reset_all_rates(self):
        for p in self.all_peers():
            p.reset_download_rate()