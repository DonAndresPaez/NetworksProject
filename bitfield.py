import math

class Bitfield:
    def __init__(self, common_cfg, has_file):
        self.file_size = int(common_cfg['FileSize'])
        self.piece_size = int(common_cfg['PieceSize'])
        self.num_pieces = math.ceil(self.file_size / self.piece_size)

        if has_file:
            self.bits = [1] * self.num_pieces
        else:
            self.bits = [0] * self.num_pieces

    def get_bytes(self):
        """Convert bit list to byte array for transmission."""
        byte_arr = bytearray()
        for i in range(0, self.num_pieces, 8):
            byte = 0
            for j in range(8):
                if i + j < self.num_pieces and self.bits[i + j] == 1:
                    byte |= (1 << (7 - j))
            byte_arr.append(byte)
        return bytes(byte_arr)

    def has_piece(self, index):
        if 0 <= index < self.num_pieces:
            return self.bits[index] == 1
        return False

    def set_piece(self, index):
        if 0 <= index < self.num_pieces:
            self.bits[index] = 1

    def is_complete(self):
        return all(b == 1 for b in self.bits)

    def num_have(self):
        return sum(self.bits)