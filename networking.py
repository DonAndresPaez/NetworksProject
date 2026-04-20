import socket, threading, struct, random
from handshake import create_handshake, verify_handshake
from message_handler import *

class PeerConnector:
    def __init__(self, my_id, my_port, peer_list, logger, bitfield, piece_manager, common_cfg):
        self.my_id = my_id
        self.my_port = my_port 
        self.peer_list = peer_list
        self.logger = logger
        self.bitfield = bitfield
        self.piece_manager = piece_manager
        self.common_cfg = common_cfg
        
        self.sockets = {}        # {id: socket}
        self.neighbor_bits = {}  # {id: [bits]}
        self.download_rates = {} # {id: piece_count} [cite: 165]
        self.is_choked_by = {}   # {id: bool}
        self.interested_peers = set() # Peers interested in ME [cite: 166]
        
        self.preferred = []      # Currently unchoked
        self.optimistic = None
        self.running = True

    def start_server(self):
        """Starts the server to listen for incoming TCP connections[cite: 250]."""
        try:
            server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_sock.bind(('0.0.0.0', self.my_port))
            server_sock.listen(10)
            
            while self.running:
                client_sock, addr = server_sock.accept()
                threading.Thread(target=self.handle_incoming, args=(client_sock,), daemon=True).start()
        except Exception as e:
            print(f"[Server Error]: {e}")

    def handle_incoming(self, sock):
        """Handles the handshake for peers connecting to us [cite: 152-153]."""
        try:
            handshake_data = sock.recv(32)
            if len(handshake_data) == 32:
                # Extract the remote peer ID from the handshake
                _, remote_id = struct.unpack(">18s10xI", handshake_data)
                
                # Respond with our handshake
                sock.send(create_handshake(self.my_id))
                self.logger.log_tcp_connected_from(remote_id)
                self.init_peer(remote_id, sock)
        except Exception as e:
            sock.close()

    def connect_to_previous_peers(self):
        for peer in self.peer_list:
            if peer['id'] < self.my_id: 
                try:
                    s = socket.socket()
                    s.connect((peer['host'], peer['port']))
                    s.send(create_handshake(self.my_id))
                    if verify_handshake(s.recv(32), peer['id']):
                        self.logger.log_tcp_connection_to(peer['id'])
                        self.init_peer(peer['id'], s)
                except Exception: pass

    def init_peer(self, remote_id, sock):
        self.sockets[remote_id] = sock
        self.is_choked_by[remote_id] = True
        self.download_rates[remote_id] = 0
        sock.send(create_message(MSG_BITFIELD, self.bitfield.get_bytes()))
        threading.Thread(target=self.receive_loop, args=(sock, remote_id), daemon=True).start()

    def receive_loop(self, sock, remote_id):
        try:
            while self.running:
                header = sock.recv(4)
                if not header: break
                length = struct.unpack(">I", header)[0]
                payload = b""
                while len(payload) < length:
                    payload += sock.recv(length - len(payload))
                
                msg_type, data = payload[0], payload[1:]
                self.handle_msg(remote_id, msg_type, data)
        except: pass

    def handle_msg(self, remote_id, msg_type, data):
        sock = self.sockets[remote_id]
        if msg_type == MSG_CHOKE:
            self.is_choked_by[remote_id] = True
            self.logger.log_choked(remote_id)
        elif msg_type == MSG_UNCHOKE:
            self.is_choked_by[remote_id] = False
            self.logger.log_unchoked(remote_id)
            self.request_piece(remote_id) 
        elif msg_type == MSG_BITFIELD:
            self.neighbor_bits[remote_id] = self.bitfield.parse_byte_array(data)
            self.send_interest(remote_id)
        elif msg_type == MSG_HAVE:
            idx = struct.unpack(">I", data)[0]
            self.neighbor_bits[remote_id][idx] = 1
            self.logger.log_have(remote_id, idx)
            self.send_interest(remote_id)
        elif msg_type == MSG_INTERESTED:
            self.interested_peers.add(remote_id)
            self.logger.log_interested(remote_id)
        elif msg_type == MSG_NOT_INTERESTED:
            self.interested_peers.discard(remote_id)
            self.logger.log_not_interested(remote_id)
        elif msg_type == MSG_REQUEST:
            idx = struct.unpack(">I", data)[0]
            if remote_id in self.preferred or remote_id == self.optimistic:
                piece = self.piece_manager.read_piece(idx)
                sock.send(create_message(MSG_PIECE, struct.pack(">I", idx) + piece))
        elif msg_type == MSG_PIECE:
            idx = struct.unpack(">I", data[:4])[0]
            self.piece_manager.write_piece(idx, data[4:])
            self.bitfield.set_piece(idx)
            self.download_rates[remote_id] += 1
            self.logger.log_download(remote_id, idx, self.bitfield.get_count())
            
            # Broadcast Have [cite: 184]
            for s in self.sockets.values():
                s.send(create_message(MSG_HAVE, struct.pack(">I", idx)))
            
            if self.bitfield.is_complete(): self.logger.log_completion()
            if not self.is_choked_by[remote_id]: self.request_piece(remote_id)

    def send_interest(self, remote_id):
        target_bits = self.neighbor_bits[remote_id]
        if any(target_bits[i] == 1 and self.bitfield.bits[i] == 0 for i in range(len(target_bits))):
            self.sockets[remote_id].send(create_message(MSG_INTERESTED)) [cite: 181]
        else:
            self.sockets[remote_id].send(create_message(MSG_NOT_INTERESTED))

    def request_piece(self, remote_id):
        target_bits = self.neighbor_bits[remote_id]
        possible = [i for i in range(len(target_bits)) if target_bits[i] == 1 and self.bitfield.bits[i] == 0]
        if possible:
            idx = random.choice(possible) [cite: 190-191]
            self.sockets[remote_id].send(create_message(MSG_REQUEST, struct.pack(">I", idx)))

    def select_preferred(self):
        candidates = list(self.interested_peers)
        if not candidates: return
        
        if self.bitfield.is_complete():
            random.shuffle(candidates)
        else:
            candidates.sort(key=lambda x: self.download_rates.get(x, 0), reverse=True)
        
        k = int(self.common_cfg['NumberOfPreferredNeighbors'])
        new_pref = candidates[:k]
        
        for pid, s in self.sockets.items():
            if pid in new_pref and pid not in self.preferred:
                s.send(create_message(MSG_UNCHOKE))
            elif pid in self.preferred and pid not in new_pref and pid != self.optimistic:
                s.send(create_message(MSG_CHOKE))
        
        self.preferred = new_pref
        self.logger.log_preferred_neighbors(self.preferred)
        for pid in self.download_rates: self.download_rates[pid] = 0

    def select_optimistic(self):
        choked_interested = [p for p in self.interested_peers if p not in self.preferred]
        if choked_interested:
            new_opt = random.choice(choked_interested)
            if self.optimistic and self.optimistic not in self.preferred:
                self.sockets[self.optimistic].send(create_message(MSG_CHOKE))
            self.sockets[new_opt].send(create_message(MSG_UNCHOKE)) 
            self.optimistic = new_opt
            self.logger.log_optimistic_neighbor(new_opt)