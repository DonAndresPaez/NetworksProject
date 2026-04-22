import datetime

class PeerLogger:
    def __init__(self, peer_id):
        self.peer_id = peer_id
        self.log_filename = f"log_peer_{peer_id}.log"
        with open(self.log_filename, "w") as f:
            f.write(f"[{self.get_time()}]: Peer {peer_id} log initialized.\n")

    def get_time(self):
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _write(self, message):
        print(message.strip())
        with open(self.log_filename, "a") as f:
            f.write(message)

    def log_tcp_connection_to(self, peer_id_2):
        msg = f"[{self.get_time()}]: Peer {self.peer_id} makes a connection to Peer {peer_id_2}.\n"
        self._write(msg)

    def log_tcp_connected_from(self, peer_id_2):
        msg = f"[{self.get_time()}]: Peer {self.peer_id} is connected from Peer {peer_id_2}.\n"
        self._write(msg)

    def log_change_preferred_neighbors(self, neighbor_ids):
        id_list = ",".join(str(i) for i in neighbor_ids)
        msg = f"[{self.get_time()}]: Peer {self.peer_id} has the preferred neighbors [{id_list}].\n"
        self._write(msg)

    def log_change_optimistic_unchoked(self, neighbor_id):
        msg = f"[{self.get_time()}]: Peer {self.peer_id} has the optimistically unchoked neighbor {neighbor_id}.\n"
        self._write(msg)

    def log_unchoked_by(self, peer_id_2):
        msg = f"[{self.get_time()}]: Peer {self.peer_id} is unchoked by {peer_id_2}.\n"
        self._write(msg)

    def log_choked_by(self, peer_id_2):
        msg = f"[{self.get_time()}]: Peer {self.peer_id} is choked by {peer_id_2}.\n"
        self._write(msg)

    def log_have(self, peer_id_2, piece_index):
        msg = f"[{self.get_time()}]: Peer {self.peer_id} received the 'have' message from {peer_id_2} for the piece {piece_index}.\n"
        self._write(msg)

    def log_interested(self, peer_id_2):
        msg = f"[{self.get_time()}]: Peer {self.peer_id} received the 'interested' message from {peer_id_2}.\n"
        self._write(msg)

    def log_not_interested(self, peer_id_2):
        msg = f"[{self.get_time()}]: Peer {self.peer_id} received the 'not interested' message from {peer_id_2}.\n"
        self._write(msg)

    def log_download_piece(self, peer_id_2, piece_index, num_pieces):
        msg = f"[{self.get_time()}]: Peer {self.peer_id} has downloaded the piece {piece_index} from {peer_id_2}. Now the number of pieces it has is {num_pieces}.\n"
        self._write(msg)

    def log_download_complete(self):
        msg = f"[{self.get_time()}]: Peer {self.peer_id} has downloaded the complete file.\n"
        self._write(msg)