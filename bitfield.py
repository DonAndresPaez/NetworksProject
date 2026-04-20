import math

class Bitfield:
    def __init__(self, common_cfg, has_file):
        self.num_pieces = math.ceil(int(common_cfg['FileSize']) / int(common_cfg['PieceSize']))
        self.bits = [1] * self.num_pieces if has_file else [0] * self.num_pieces

    def get_bytes(self):
        """Converts bit list to bytes for 'bitfield' message [cite: 139-141]."""
        byte_arr = bytearray()
        for i in range(0, self.num_pieces, 8):
            byte = 0
            for j in range(8):
                if i + j < self.num_pieces and self.bits[i + j] == 1:
                    byte |= (1 << (7 - j))
            byte_arr.append(byte)
        return byte_arr

    def parse_byte_array(self, byte_arr):
        """Converts received bytes back into a bit list [cite: 140-141]."""
        bits = []
        for byte in byte_arr:
            for j in range(8):
                if len(bits) < self.num_pieces:
                    bits.append((byte >> (7 - j)) & 1)
        return bits

    def is_complete(self):
        return all(b == 1 for b in self.bits)

    def set_piece(self, index):
        self.bits[index] = 1

    def get_count(self):
        return sum(self.bits)