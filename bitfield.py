import math

class Bitfield:
    def __init__(self, common_cfg, has_file):
        # Calculate total pieces: ceil(FileSize / PieceSize)
        self.file_size = int(common_cfg['FileSize'])
        self.piece_size = int(common_cfg['PieceSize'])
        self.num_pieces = math.ceil(self.file_size / self.piece_size)
        
        # Initialize the bitfield: all 1s if we have the file, all 0s if not
        if has_file:
            self.bits = [1] * self.num_pieces
        else:
            self.bits = [0] * self.num_pieces

    def get_bytes(self):
        """Converts the list of bits into a byte array to send over TCP."""
        byte_arr = bytearray()
        for i in range(0, self.num_pieces, 8):
            byte = 0
            for j in range(8):
                if i + j < self.num_pieces:
                    if self.bits[i + j] == 1:
                        # Set the specific bit in the byte
                        byte |= (1 << (7 - j))
            byte_arr.append(byte)
        return byte_arr

    def has_piece(self, index):
        return self.bits[index] == 1

    def set_piece(self, index):
        self.bits[index] = 1