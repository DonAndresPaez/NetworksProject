import datetime

class PeerLogger:
    def __init__(self, peer_id):
        self.peer_id = peer_id
        self.filename = f"log_peer_{peer_id}.log"
        with open(self.filename, "w") as f:
            f.write(f"[{self.now()}] Peer {peer_id} log initialized.\n")

    def now(self):
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def log_tcp_connection_to(self, target_id):
        self._write(f"Peer {self.peer_id} makes a connection to Peer {target_id}.")

    def log_tcp_connected_from(self, target_id):
        self._write(f"Peer {self.peer_id} is connected from Peer {target_id}.")

    def log_preferred_neighbors(self, neighbors):
        n_list = ",".join(map(str, neighbors))
        self._write(f"Peer {self.peer_id} has the preferred neighbors {n_list}.")

    def log_optimistic_neighbor(self, target_id):
        self._write(f"Peer {self.peer_id} has the optimistically unchoked neighbor {target_id}.")

    def log_unchoked(self, target_id):
        self._write(f"Peer {self.peer_id} is unchoked by {target_id}.") 

    def log_choked(self, target_id):
        self._write(f"Peer {self.peer_id} is choked by {target_id}.")

    def log_have(self, target_id, index):
        self._write(f"Peer {self.peer_id} received the 'have' message from {target_id} for the piece {index}.")

    def log_interested(self, target_id):
        self._write(f"Peer {self.peer_id} received the 'interested' message from {target_id}.")

    def log_not_interested(self, target_id):
        self._write(f"Peer {self.peer_id} received the 'not interested' message from {target_id}.")

    def log_download(self, target_id, index, total):
        self._write(f"Peer {self.peer_id} has downloaded the piece {index} from {target_id}. Now the number of pieces it has is {total}.")

    def log_completion(self):
        self._write(f"Peer {self.peer_id} has downloaded the complete file.")

    def _write(self, msg):
        print(f"[{self.now()}] {msg}")
        with open(self.filename, "a") as f:
            f.write(f"[{self.now()}] {msg}\n")