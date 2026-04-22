import struct

MSG_CHOKE = 0
MSG_UNCHOKE = 1
MSG_INTERESTED = 2
MSG_NOT_INTERESTED = 3
MSG_HAVE = 4
MSG_BITFIELD = 5
MSG_REQUEST = 6
MSG_PIECE = 7

def create_message(msg_type, payload=b""):
    """Build a length-prefixed message: [4-byte length][1-byte type][payload]"""
    length = len(payload) + 1  # +1 for the type byte
    return struct.pack(">IB", length, msg_type) + payload

def parse_message(data):
    """Unpacks a received message into (type, payload). Data must include the 4-byte length header."""
    if len(data) < 5:
        return None, None
    length, msg_type = struct.unpack(">IB", data[:5])
    payload = data[5:5 + length - 1]
    return msg_type, payload

# --- Payload builders ---

def make_have_payload(piece_index):
    return struct.pack(">I", piece_index)

def parse_have_payload(payload):
    return struct.unpack(">I", payload)[0]

def make_request_payload(piece_index, piece_size):
    """REQUEST: [4-byte index][4-byte begin=0][4-byte length]"""
    return struct.pack(">III", piece_index, 0, piece_size)

def parse_request_payload(payload):
    """Returns (piece_index, begin, length)"""
    return struct.unpack(">III", payload[:12])

def make_piece_payload(piece_index, data):
    """PIECE: [4-byte index][4-byte begin=0][data]"""
    return struct.pack(">II", piece_index, 0) + data

def parse_piece_payload(payload):
    """Returns (piece_index, data) — begin offset is ignored (always 0)"""
    piece_index, begin = struct.unpack(">II", payload[:8])
    data = payload[8:]
    return piece_index, data