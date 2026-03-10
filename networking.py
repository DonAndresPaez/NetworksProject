import socket
import threading
import struct
from handshake import create_handshake, verify_handshake
from message_handler import create_message, MSG_BITFIELD

class PeerConnector:
    def __init__(self, my_id, my_port, peer_list, logger, bitfield):
        self.my_id = my_id
        self.my_port = my_port
        self.peer_list = peer_list
        self.logger = logger
        self.bitfield = bitfield 
        self.connections = {}

    def start_server(self):
        try:
            server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_sock.bind(('0.0.0.0', self.my_port))
            server_sock.listen(5)
            print(f"[Server] Listening on port {self.my_port}...")

            while True:
                client_sock, addr = server_sock.accept()
                t = threading.Thread(target=self.handle_incoming, args=(client_sock,))
                t.daemon = True
                t.start()
        except Exception as e:
            print(f"[Server Error] {e}")

    def connect_to_previous_peers(self):
        for peer in self.peer_list:
            if peer['id'] < self.my_id:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.connect((peer['host'], peer['port']))
                    
                    # 1. Handshake
                    sock.send(create_handshake(self.my_id))
                    response = sock.recv(32)
                    
                    if len(response) == 32 and verify_handshake(response, peer['id']):
                        self.logger.log_tcp_connection_to(peer['id'])
                        self.connections[peer['id']] = sock
                        
                        # 2. Bitfield Exchange
                        bitfield_msg = create_message(MSG_BITFIELD, self.bitfield.get_bytes())
                        sock.send(bitfield_msg)
                        receiver = threading.Thread(target=self.receive_loop, args=(sock, peer['id']))
                        receiver.daemon = True
                        receiver.start()
                        print(f"[Client] Handshake + Bitfield sent to {peer['id']}")
                    else:
                        sock.close()
                except Exception as e:
                    print(f"[Client Error] {peer['id']}: {e}")

    def handle_incoming(self, sock):
        try:
            # 1. Handshake
            data = sock.recv(32)
            if len(data) == 32:
                _, remote_id = struct.unpack(">18s10xI", data)
                if verify_handshake(data, remote_id):
                    sock.send(create_handshake(self.my_id))
                    self.logger.log_tcp_connected_from(remote_id)
                    self.connections[remote_id] = sock
                    
                    # 2. Bitfield Exchange
                    bitfield_msg = create_message(MSG_BITFIELD, self.bitfield.get_bytes())
                    sock.send(bitfield_msg)
                    receiver = threading.Thread(target=self.receive_loop, args=(sock, remote_id))
                    receiver.daemon = True
                    receiver.start()
                    print(f"[Server] Handshake + Bitfield sent to {remote_id}")
                else:
                    sock.close()
        except Exception as e:
            print(f"[Handle Error] {e}")

    def receive_loop(self, sock, remote_id):
        """Background thread that listens for incoming P2P messages."""
        import struct
        from message_handler import parse_message
        
        try:
            while True:
                # 1. Read the 4-byte length
                header = sock.recv(4)
                if not header: break
                msg_length = struct.unpack(">I", header)[0]
                
                # 2. Read the full payload (Type + Content)
                payload = b""
                while len(payload) < msg_length:
                    chunk = sock.recv(msg_length - len(payload))
                    if not chunk: break
                    payload += chunk
                
                # 3. Handle the message type
                msg_type = payload[0]
                if msg_type == 5:
                    print(f"[Receive] Peer {remote_id} sent their Bitfield Map!")
                
        except Exception as e:
            print(f"[Receive Error] {remote_id}: {e}")