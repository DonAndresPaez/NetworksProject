import math
import os
import threading


class FileManager:
    def __init__(self, peer_id, config, has_file):
        self.peer_id = peer_id
        self.config = config
        self.num_pieces = config.get_number_of_pieces()
        self.pieces = [None] * self.num_pieces
        self.has_piece = [False] * self.num_pieces
        self.pieces_count = 0
        self.dir_path = f"peer_{peer_id}"
        self._lock = threading.Lock()

        os.makedirs(self.dir_path, exist_ok=True)

        if has_file:
            self._load_file()

    def _load_file(self):
        file_path = os.path.join(self.dir_path, self.config.file_name)
        with open(file_path, "rb") as f:
            for i in range(self.num_pieces):
                size = self.get_piece_size(i)
                data = f.read(size)
                self.pieces[i] = data
                self.has_piece[i] = True
                self.pieces_count += 1

    def get_piece_size(self, index):
        if index == self.num_pieces - 1:
            last_size = self.config.file_size % self.config.piece_size
            return last_size if last_size != 0 else self.config.piece_size
        return self.config.piece_size

    def has_piece_at(self, index):
        with self._lock:
            return self.has_piece[index]

    def has_all_pieces(self):
        with self._lock:
            return self.pieces_count == self.num_pieces

    def get_pieces_count(self):
        with self._lock:
            return self.pieces_count

    def get_piece(self, index):
        with self._lock:
            return self.pieces[index]

    def set_piece(self, index, data):
        with self._lock:
            if not self.has_piece[index]:
                self.pieces[index] = data
                self.has_piece[index] = True
                self.pieces_count += 1
                if self.pieces_count == self.num_pieces:
                    self._save_file()

    def get_bitfield(self):
        with self._lock:
            bitfield_size = math.ceil(self.num_pieces / 8)
            bitfield = bytearray(bitfield_size)
            for i in range(self.num_pieces):
                if self.has_piece[i]:
                    bitfield[i // 8] |= (1 << (7 - i % 8))
            return bytes(bitfield)

    def _save_file(self):
        file_path = os.path.join(self.dir_path, self.config.file_name)
        with open(file_path, "wb") as f:
            for i in range(self.num_pieces):
                f.write(self.pieces[i])
