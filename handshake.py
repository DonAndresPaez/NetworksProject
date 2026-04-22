import struct

# This function will build the 32-byte message.
def create_handshake(peer_id):
    # '18s' = 18-byte string
    # '10x' = 10 padding bytes (zeros)
    # 'I' = 4-byte unsigned integer
    header = b"P2PFILESHARINGPROJ"
    
    # We use the header to create the full message here.
    return struct.pack(">18s10xI", header, peer_id)


# This function helps check if the receiving header is valid.
def verify_handshake(received_bytes, expected_peer_id):
    # Unpack the 32 bytes back into variables (The opposite of that is being done above)
    header, peer_id = struct.unpack(">18s10xI", received_bytes)
    
    # Check if the header matches and it's the right neighbor
    if header == b"P2PFILESHARINGPROJ" and peer_id == expected_peer_id:
        return True
    return False