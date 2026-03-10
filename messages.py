"""
messages.py - Message construction and parsing for the P2P protocol.

Message format:
  [4-byte length][1-byte type][variable payload]

Handshake format (32 bytes):
  [18-byte header 'P2PFILESHARINGPROJ'][10-byte zeros][4-byte peer ID]
"""

import struct

# Message type constants
MSG_CHOKE = 0
MSG_UNCHOKE = 1
MSG_INTERESTED = 2
MSG_NOT_INTERESTED = 3
MSG_HAVE = 4
MSG_BITFIELD = 5
MSG_REQUEST = 6
MSG_PIECE = 7

HANDSHAKE_HEADER = b"P2PFILESHARINGPROJ"
HANDSHAKE_LEN = 32


# ---------------------------------------------------------------------------
# Handshake
# ---------------------------------------------------------------------------

def make_handshake(peer_id: int) -> bytes:
    """Build a 32-byte handshake message."""
    return HANDSHAKE_HEADER + b"\x00" * 10 + struct.pack("!I", peer_id)


def parse_handshake(data: bytes) -> int:
    """Parse handshake bytes and return peer_id. Raises ValueError on bad header."""
    if len(data) < HANDSHAKE_LEN:
        raise ValueError("Handshake too short")
    header = data[:18]
    if header != HANDSHAKE_HEADER:
        raise ValueError(f"Bad handshake header: {header!r}")
    peer_id = struct.unpack("!I", data[28:32])[0]
    return peer_id


# ---------------------------------------------------------------------------
# Generic actual messages
# ---------------------------------------------------------------------------

def make_message(msg_type: int, payload: bytes = b"") -> bytes:
    """Build a length-prefixed message."""
    length = 1 + len(payload)          # type byte + payload
    return struct.pack("!IB", length, msg_type) + payload


def make_choke() -> bytes:
    return make_message(MSG_CHOKE)


def make_unchoke() -> bytes:
    return make_message(MSG_UNCHOKE)


def make_interested() -> bytes:
    return make_message(MSG_INTERESTED)


def make_not_interested() -> bytes:
    return make_message(MSG_NOT_INTERESTED)


def make_have(piece_index: int) -> bytes:
    return make_message(MSG_HAVE, struct.pack("!I", piece_index))


def make_bitfield(bitfield: bytearray) -> bytes:
    return make_message(MSG_BITFIELD, bytes(bitfield))


def make_request(piece_index: int) -> bytes:
    return make_message(MSG_REQUEST, struct.pack("!I", piece_index))


def make_piece(piece_index: int, data: bytes) -> bytes:
    payload = struct.pack("!I", piece_index) + data
    return make_message(MSG_PIECE, payload)


# ---------------------------------------------------------------------------
# Receiving helpers
# ---------------------------------------------------------------------------

def recv_exact(sock, n: int) -> bytes:
    """Read exactly n bytes from sock, blocking."""
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("Socket closed while reading")
        buf += chunk
    return buf


def recv_handshake(sock) -> int:
    """Receive and parse a handshake; returns remote peer_id."""
    data = recv_exact(sock, HANDSHAKE_LEN)
    return parse_handshake(data)


def recv_message(sock):
    """
    Receive one message from sock.
    Returns (msg_type, payload_bytes) or raises ConnectionError.
    """
    header = recv_exact(sock, 5)               # 4-byte length + 1-byte type
    length, msg_type = struct.unpack("!IB", header)
    payload_len = length - 1
    payload = recv_exact(sock, payload_len) if payload_len > 0 else b""
    return msg_type, payload


# ---------------------------------------------------------------------------
# Bitfield helpers
# ---------------------------------------------------------------------------

def make_bitfield_bytes(num_pieces: int, have_all: bool = False) -> bytearray:
    """Create a bytearray bitfield for num_pieces pieces."""
    num_bytes = (num_pieces + 7) // 8
    bf = bytearray(num_bytes)
    if have_all:
        for i in range(num_pieces):
            bf[i // 8] |= (1 << (7 - (i % 8)))
    return bf


def bitfield_has(bf: bytearray, index: int) -> bool:
    return bool(bf[index // 8] & (1 << (7 - (index % 8))))


def bitfield_set(bf: bytearray, index: int):
    bf[index // 8] |= (1 << (7 - (index % 8)))


def bitfield_count(bf: bytearray, num_pieces: int) -> int:
    return sum(1 for i in range(num_pieces) if bitfield_has(bf, i))
