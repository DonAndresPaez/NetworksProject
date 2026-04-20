import os

class PieceManager:
    def __init__(self, peer_id, common_cfg):
        self.file_path = os.path.join(f"peer_{peer_id}", common_cfg['FileName'])
        self.piece_size = int(common_cfg['PieceSize'])
        self.file_size = int(common_cfg['FileSize'])
        
        if not os.path.exists(os.path.dirname(self.file_path)):
            os.makedirs(os.path.dirname(self.file_path))

        # Initialize empty file if peer doesn't have it [cite: 282]
        if not os.path.exists(self.file_path):
            with open(self.file_path, "wb") as f:
                f.write(b'\x00' * self.file_size)

    def read_piece(self, index):
        with open(self.file_path, "rb") as f:
            f.seek(index * self.piece_size)
            return f.read(self.piece_size)

    def write_piece(self, index, data):
        with open(self.file_path, "r+b") as f:
            f.seek(index * self.piece_size)
            f.write(data)