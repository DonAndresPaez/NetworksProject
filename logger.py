import datetime
import os

class PeerLogger:
    def __init__(self, peer_id):
        self.peer_id = peer_id
        # Log file naming convention
        self.log_filename = f"log_peer_{peer_id}.log"
        
        # Initialize or clear the log file
        with open(self.log_filename, "w") as f:
            f.write(f"[{self.get_time()}]: Peer {peer_id} log initialized.\n")

    def get_time(self):
        """Generates time in required format: date, hour, minute, second [cite: 191-192]."""
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def log_tcp_connection_to(self, peer_id_2):
        """Log for: [Time]: Peer [peer_ID 1] makes a connection to Peer [peer_ID 2][cite: 189]."""
        msg = f"[{self.get_time()}]: Peer {self.peer_id} makes a connection to Peer {peer_id_2}.\n"
        self._write(msg)

    def log_tcp_connected_from(self, peer_id_2):
        """Log for: [Time]: Peer [peer_ID 1] is connected from Peer [peer_ID 2][cite: 194]."""
        msg = f"[{self.get_time()}]: Peer {self.peer_id} is connected from Peer {peer_id_2}.\n"
        self._write(msg)

    def _write(self, message):
        print(message.strip()) # Print to console for debugging purposes
        with open(self.log_filename, "a") as f:
            f.write(message)