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
    length = len(payload) + 1
    return struct.pack(">IB", length, msg_type) + payload

def parse_message(data):
    """Unpacks a received message into (type, payload)."""
    if len(data) < 5:
        return None, None
    length, msg_type = struct.unpack(">IB", data[:5])
    payload = data[5:]
    return msg_type, payload