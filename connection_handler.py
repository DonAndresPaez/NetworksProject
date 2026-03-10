import struct
import threading


CHOKE = 0
UNCHOKE = 1
INTERESTED = 2
NOT_INTERESTED = 3
HAVE = 4
BITFIELD = 5
REQUEST = 6
PIECE = 7

HANDSHAKE_HEADER = b"P2PFILESHARINGPROJ"


class ConnectionHandler(threading.Thread):
    def __init__(self, peer_proc, sock, initiator, remote_peer_id=-1):
        super().__init__(daemon=True)
        self.peer_proc = peer_proc
        self.sock = sock
        self.initiator = initiator
        self.remote_peer_id = remote_peer_id
        self.remote_bitfield = [False] * peer_proc.file_manager.num_pieces

        self.am_choking = True        # we are choking the remote peer
        self.am_interested = False    # we are interested in remote
        self.peer_choking = True      # remote is choking us
        self.peer_interested = False  # remote is interested in us
        self.downloaded_bytes = 0
        self.downloaded_bytes_prev = 0
        self.pending_request = -1

        self._send_lock = threading.Lock()

    def run(self):
        try:
            if self.initiator:
                self._send_handshake()
                self._receive_handshake()
            else:
                self._receive_handshake()
                self._send_handshake()
                self.peer_proc.logger.log_tcp_connection_from(self.remote_peer_id)

            self.peer_proc.register_connection(self.remote_peer_id, self)

            # Send bitfield if we have any pieces
            if self.peer_proc.file_manager.get_pieces_count() > 0:
                self.send_bitfield()

            # Message loop
            while self.peer_proc.running:
                length_bytes = self._recv_exact(4)
                if not length_bytes:
                    break
                length = struct.unpack("!I", length_bytes)[0]
                if length < 1:
                    continue
                type_byte = self._recv_exact(1)
                if not type_byte:
                    break
                msg_type = type_byte[0]
                payload = b""
                if length > 1:
                    payload = self._recv_exact(length - 1)
                    if not payload:
                        break
                self._handle_message(msg_type, payload)
        except (ConnectionError, OSError):
            pass
        finally:
            self.close()

    def _recv_exact(self, n):
        data = b""
        while len(data) < n:
            chunk = self.sock.recv(n - len(data))
            if not chunk:
                return None
            data += chunk
        return data

    def _send_handshake(self):
        handshake = bytearray(32)
        handshake[0:18] = HANDSHAKE_HEADER
        # bytes 18-27 are zero
        peer_id = self.peer_proc.peer_id
        struct.pack_into("!I", handshake, 28, peer_id)
        with self._send_lock:
            self.sock.sendall(handshake)

    def _receive_handshake(self):
        data = self._recv_exact(32)
        if not data:
            raise ConnectionError("Failed to receive handshake")

        header = data[0:18]
        if header != HANDSHAKE_HEADER:
            raise ConnectionError(f"Invalid handshake header: {header}")

        received_id = struct.unpack("!I", data[28:32])[0]

        if self.initiator and received_id != self.remote_peer_id:
            raise ConnectionError(f"Unexpected peer ID: {received_id}")

        self.remote_peer_id = received_id

    def _handle_message(self, msg_type, payload):
        if msg_type == CHOKE:
            self._handle_choke()
        elif msg_type == UNCHOKE:
            self._handle_unchoke()
        elif msg_type == INTERESTED:
            self._handle_interested()
        elif msg_type == NOT_INTERESTED:
            self._handle_not_interested()
        elif msg_type == HAVE:
            self._handle_have(payload)
        elif msg_type == BITFIELD:
            self._handle_bitfield(payload)
        elif msg_type == REQUEST:
            self._handle_request(payload)
        elif msg_type == PIECE:
            self._handle_piece(payload)

    def _handle_choke(self):
        self.peer_choking = True
        self.peer_proc.logger.log_choking(self.remote_peer_id)
        if self.pending_request >= 0:
            self.peer_proc.cancel_request(self.pending_request)
            self.pending_request = -1

    def _handle_unchoke(self):
        self.peer_choking = False
        self.peer_proc.logger.log_unchoking(self.remote_peer_id)
        self._request_piece()

    def _handle_interested(self):
        self.peer_interested = True
        self.peer_proc.logger.log_interested(self.remote_peer_id)

    def _handle_not_interested(self):
        self.peer_interested = False
        self.peer_proc.logger.log_not_interested(self.remote_peer_id)

    def _handle_have(self, payload):
        piece_index = struct.unpack("!I", payload)[0]
        self.remote_bitfield[piece_index] = True
        self.peer_proc.logger.log_have(self.remote_peer_id, piece_index)
        self.update_interest_state()

    def _handle_bitfield(self, payload):
        num_pieces = self.peer_proc.file_manager.num_pieces
        for i in range(num_pieces):
            self.remote_bitfield[i] = (payload[i // 8] & (1 << (7 - i % 8))) != 0
        self.update_interest_state()

    def _handle_request(self, payload):
        if not self.am_choking:
            piece_index = struct.unpack("!I", payload)[0]
            piece_data = self.peer_proc.file_manager.get_piece(piece_index)
            if piece_data is not None:
                self.send_piece(piece_index, piece_data)

    def _handle_piece(self, payload):
        piece_index = struct.unpack("!I", payload[0:4])[0]
        piece_data = payload[4:]

        self.downloaded_bytes += len(piece_data)
        self.pending_request = -1

        self.peer_proc.piece_received(piece_index, piece_data, self.remote_peer_id)

        if not self.peer_choking:
            self._request_piece()

    def update_interest_state(self):
        fm = self.peer_proc.file_manager
        should_be_interested = False
        for i in range(fm.num_pieces):
            if not fm.has_piece_at(i) and self.remote_bitfield[i]:
                should_be_interested = True
                break

        if should_be_interested and not self.am_interested:
            self.am_interested = True
            self.send_interested()
        elif not should_be_interested and self.am_interested:
            self.am_interested = False
            self.send_not_interested()

    def _request_piece(self):
        piece_index = self.peer_proc.select_piece_to_request(self.remote_peer_id)
        if piece_index >= 0:
            self.pending_request = piece_index
            self.send_request(piece_index)

    # --- Send methods ---

    def send_choke(self):
        self._send_message(CHOKE, b"")

    def send_unchoke(self):
        self._send_message(UNCHOKE, b"")

    def send_interested(self):
        self._send_message(INTERESTED, b"")

    def send_not_interested(self):
        self._send_message(NOT_INTERESTED, b"")

    def send_have(self, piece_index):
        self._send_message(HAVE, struct.pack("!I", piece_index))

    def send_bitfield(self):
        bitfield = self.peer_proc.file_manager.get_bitfield()
        self._send_message(BITFIELD, bitfield)

    def send_request(self, piece_index):
        self._send_message(REQUEST, struct.pack("!I", piece_index))

    def send_piece(self, piece_index, data):
        payload = struct.pack("!I", piece_index) + data
        self._send_message(PIECE, payload)

    def _send_message(self, msg_type, payload):
        try:
            header = struct.pack("!IB", 1 + len(payload), msg_type)
            with self._send_lock:
                self.sock.sendall(header + payload)
        except (ConnectionError, OSError):
            pass

    # --- Query methods ---

    def has_remote_piece(self, index):
        return self.remote_bitfield[index]

    def has_remote_all_pieces(self):
        return all(self.remote_bitfield)

    def close(self):
        if self.pending_request >= 0:
            self.peer_proc.cancel_request(self.pending_request)
            self.pending_request = -1
        try:
            self.sock.close()
        except OSError:
            pass
