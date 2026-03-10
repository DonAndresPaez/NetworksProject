class PeerInfoEntry:
    def __init__(self, peer_id, host_name, port, has_file):
        self.peer_id = peer_id
        self.host_name = host_name
        self.port = port
        self.has_file = has_file

    @staticmethod
    def load_all(path):
        peers = []
        with open(path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split()
                peer_id = int(parts[0])
                host_name = parts[1]
                port = int(parts[2])
                has_file = parts[3].strip() == "1"
                peers.append(PeerInfoEntry(peer_id, host_name, port, has_file))
        return peers
