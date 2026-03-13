import socket
import struct
import threading
import time
import os
from config_reader import parseCommonCfg

MSG_CHOKE          = 0
MSG_UNCHOKE        = 1
MSG_INTERESTED     = 2
MSG_NOT_INTERESTED = 3
MSG_HAVE           = 4
MSG_BITFIELD       = 5
MSG_REQUEST        = 6
MSG_PIECE          = 7

HANDSHAKE_HEADER = b"P2PFILESHARINGPROJ"
TEST_PORT        = 19999
SENDER_ID        = 1001
RECEIVER_ID      = 1002
PIECE_INDEX      = 0
NUM_PIECES       = 3

results = {}


def make_msg(msg_type, payload=b""):
    length = len(payload) + 1
    return struct.pack(">IB", length, msg_type) + payload


def recv_exact(sock, n):
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf


def recv_msg(sock):
    header = recv_exact(sock, 4)
    if not header:
        return None, None
    msg_length = struct.unpack(">I", header)[0]
    payload = recv_exact(sock, msg_length)
    if payload is None:
        return None, None
    return payload[0], payload[1:]


def make_handshake(peer_id):
    return struct.pack(">18s10xI", HANDSHAKE_HEADER, peer_id)


def parse_handshake(data):
    if len(data) != 32:
        return None
    header, peer_id = struct.unpack(">18s10xI", data)
    return peer_id if header == HANDSHAKE_HEADER else None


def make_bitfield_bytes(bits):
    byte_arr = bytearray()
    for i in range(0, len(bits), 8):
        byte = 0
        for j in range(8):
            if i + j < len(bits) and bits[i + j]:
                byte |= (1 << (7 - j))
        byte_arr.append(byte)
    return bytes(byte_arr)


def parse_bitfield_bytes(raw, num_pieces):
    bits = []
    for byte in raw:
        for j in range(7, -1, -1):
            bits.append((byte >> j) & 1)
    return bits[:num_pieces]


def read_piece(peer_id, piece_index, piece_size, file_size):
    path = os.path.join(f"peer_{peer_id}", "thefile")
    offset = piece_index * piece_size
    length = min(piece_size, file_size - offset)
    with open(path, "rb") as f:
        f.seek(offset)
        return f.read(length)


def save_piece(peer_id, piece_index, piece_size, data):
    folder = f"peer_{peer_id}"
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, "thefile")
    mode = "r+b" if os.path.exists(path) else "wb"
    with open(path, mode) as f:
        f.seek(piece_index * piece_size)
        f.write(data)
    print(f"[Receiver] Saved piece {piece_index} to {path}")


def sender_thread(piece_data):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", TEST_PORT))
    server.listen(1)
    results["sender_ready"] = True

    conn, _ = server.accept()
    try:
        remote_id = parse_handshake(recv_exact(conn, 32))
        assert remote_id == RECEIVER_ID
        conn.send(make_handshake(SENDER_ID))
        print(f"[Sender] Handshake OK with peer {remote_id}")

        conn.send(make_msg(MSG_BITFIELD, make_bitfield_bytes([1] * NUM_PIECES)))
        print("[Sender] Sent bitfield")

        msg_type, payload = recv_msg(conn)
        assert msg_type == MSG_BITFIELD
        print(f"[Sender] Got receiver bitfield: {parse_bitfield_bytes(payload, NUM_PIECES)}")

        msg_type, _ = recv_msg(conn)
        assert msg_type == MSG_INTERESTED
        print("[Sender] Receiver is interested")

        conn.send(make_msg(MSG_UNCHOKE))
        print("[Sender] Sent UNCHOKE")

        msg_type, payload = recv_msg(conn)
        assert msg_type == MSG_REQUEST
        req_index, req_begin, req_length = struct.unpack(">III", payload)
        print(f"[Sender] Got request for piece {req_index} offset {req_begin} len {req_length}")

        conn.send(make_msg(MSG_PIECE, struct.pack(">II", req_index, req_begin) + piece_data))
        print(f"[Sender] Sent piece {req_index} ({len(piece_data)} bytes)")

        results["sender_passed"] = True
    except AssertionError as e:
        results["sender_error"] = str(e)
    finally:
        conn.close()
        server.close()


def receiver_thread(piece_size):
    while not results.get("sender_ready"):
        time.sleep(0.05)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(("127.0.0.1", TEST_PORT))
    try:
        sock.send(make_handshake(RECEIVER_ID))
        remote_id = parse_handshake(recv_exact(sock, 32))
        assert remote_id == SENDER_ID
        print(f"[Receiver] Handshake OK with peer {remote_id}")

        msg_type, payload = recv_msg(sock)
        assert msg_type == MSG_BITFIELD
        sender_bits = parse_bitfield_bytes(payload, NUM_PIECES)
        print(f"[Receiver] Got sender bitfield: {sender_bits}")

        sock.send(make_msg(MSG_BITFIELD, make_bitfield_bytes([0] * NUM_PIECES)))
        print("[Receiver] Sent own bitfield")

        sock.send(make_msg(MSG_INTERESTED))
        print("[Receiver] Sent INTERESTED")

        msg_type, _ = recv_msg(sock)
        assert msg_type == MSG_UNCHOKE
        print("[Receiver] Got UNCHOKE")

        sock.send(make_msg(MSG_REQUEST, struct.pack(">III", PIECE_INDEX, 0, piece_size)))
        print(f"[Receiver] Sent REQUEST for piece {PIECE_INDEX}")

        msg_type, payload = recv_msg(sock)
        assert msg_type == MSG_PIECE
        piece_index, piece_begin = struct.unpack(">II", payload[:8])
        received_data = payload[8:]
        print(f"[Receiver] Got piece {piece_index} offset {piece_begin} ({len(received_data)} bytes)")

        save_piece(RECEIVER_ID, piece_index, piece_size, received_data)

        results["receiver_passed"] = True
        results["received_data"]   = received_data
    except AssertionError as e:
        results["receiver_error"] = str(e)
    finally:
        sock.close()


def run_test():
    common_cfg = parseCommonCfg('Common.cfg')
    piece_size = common_cfg['PieceSize']
    file_size  = common_cfg['FileSize']

    piece_data = read_piece(SENDER_ID, PIECE_INDEX, piece_size, file_size)

    print("=" * 60)
    print("  TEST: File piece request and transfer between peers")
    print("=" * 60)

    s = threading.Thread(target=sender_thread,   args=(piece_data,), daemon=True)
    r = threading.Thread(target=receiver_thread, args=(len(piece_data),), daemon=True)
    s.start()
    r.start()
    s.join(timeout=10)
    r.join(timeout=10)

    print("\n--- Results ---")

    if results.get("sender_error"):
        print(f"[FAIL] Sender error: {results['sender_error']}")
    if results.get("receiver_error"):
        print(f"[FAIL] Receiver error: {results['receiver_error']}")

    if results.get("sender_passed") and results.get("receiver_passed"):
        received = results["received_data"]
        if received == piece_data:
            print("[ OK ] Piece data transferred correctly!")
            print(f"[ OK ] {len(received)} bytes received, content matches original.")
            print(f"[ OK ] File saved to peer_{RECEIVER_ID}/thefile")
            print("\n✅  PASS — File pieces are successfully requested and sent between peers.")
            return True
        else:
            print(f"[FAIL] Data mismatch! Expected {len(piece_data)} bytes, got {len(received)} bytes")
            print("\n❌  FAIL")
            return False
    else:
        print("\n❌  FAIL — One or both peers did not complete the exchange.")
        return False


if __name__ == "__main__":
    success = run_test()
    exit(0 if success else 1)
