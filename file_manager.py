"""
file_manager.py - Handles reading/writing file pieces for a peer.

Each peer stores data in: peer_<peerID>/<FileName>
"""

import os
import math


class FileManager:
    def __init__(self, peer_id: int, cfg: dict, base_dir: str = "."):
        self.peer_id = peer_id
        self.file_name = cfg["file_name"]
        self.file_size = cfg["file_size"]
        self.piece_size = cfg["piece_size"]
        self.num_pieces = math.ceil(self.file_size / self.piece_size)

        self.peer_dir = os.path.join(base_dir, str(peer_id))
        os.makedirs(self.peer_dir, exist_ok=True)
        self.file_path = os.path.join(self.peer_dir, self.file_name)

        # Pre-create file of correct size if it doesn't exist
        if not os.path.exists(self.file_path):
            with open(self.file_path, "wb") as f:
                f.write(b"\x00" * self.file_size)

    def piece_offset(self, index: int) -> int:
        return index * self.piece_size

    def piece_length(self, index: int) -> int:
        if index == self.num_pieces - 1:
            remaining = self.file_size - (index * self.piece_size)
            return remaining
        return self.piece_size

    def read_piece(self, index: int) -> bytes:
        offset = self.piece_offset(index)
        length = self.piece_length(index)
        with open(self.file_path, "rb") as f:
            f.seek(offset)
            return f.read(length)

    def write_piece(self, index: int, data: bytes):
        offset = self.piece_offset(index)
        with open(self.file_path, "r+b") as f:
            f.seek(offset)
            f.write(data)
