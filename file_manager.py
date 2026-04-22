import os
import math

class FileManager:
    """Handles piece-level file I/O for a peer."""

    def __init__(self, peer_id, common_cfg):
        self.peer_id = peer_id
        self.file_name = common_cfg['FileName']
        self.file_size = common_cfg['FileSize']
        self.piece_size = common_cfg['PieceSize']
        self.num_pieces = math.ceil(self.file_size / self.piece_size)
        self.last_piece_size = self.file_size % self.piece_size or self.piece_size

        # Each peer uses its own subdirectory
        self.dir = f"peer_{peer_id}"
        os.makedirs(self.dir, exist_ok=True)
        self.file_path = os.path.join(self.dir, self.file_name)

    def init_file(self, has_file):
        """
        If the peer already has the file, it should be in the subdirectory.
        If not, create an empty placeholder file of the right size.
        """
        if has_file:
            if not os.path.exists(self.file_path):
                print(f"[FileManager] WARNING: peer_{self.peer_id} marked has_file=1 but file not found at {self.file_path}")
        else:
            # Create empty file if it doesn't exist
            if not os.path.exists(self.file_path):
                with open(self.file_path, 'wb') as f:
                    f.write(b'\x00' * self.file_size)

    def get_piece(self, index):
        """Read and return the bytes for a given piece index."""
        offset = index * self.piece_size
        size = self.piece_size if index < self.num_pieces - 1 else self.last_piece_size
        try:
            with open(self.file_path, 'rb') as f:
                f.seek(offset)
                return f.read(size)
        except Exception as e:
            print(f"[FileManager] Error reading piece {index}: {e}")
            return None

    def save_piece(self, index, data):
        """Write piece data to the correct offset in the file."""
        offset = index * self.piece_size
        try:
            with open(self.file_path, 'r+b') as f:
                f.seek(offset)
                f.write(data)
        except Exception as e:
            print(f"[FileManager] Error saving piece {index}: {e}")