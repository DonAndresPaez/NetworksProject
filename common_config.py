import math


class CommonConfig:
    def __init__(self):
        self.number_of_preferred_neighbors = 0
        self.unchoking_interval = 0
        self.optimistic_unchoking_interval = 0
        self.file_name = ""
        self.file_size = 0
        self.piece_size = 0

    def get_number_of_pieces(self):
        return math.ceil(self.file_size / self.piece_size)

    @staticmethod
    def load(path):
        config = CommonConfig()
        with open(path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split()
                key, value = parts[0], parts[1]
                if key == "NumberOfPreferredNeighbors":
                    config.number_of_preferred_neighbors = int(value)
                elif key == "UnchokingInterval":
                    config.unchoking_interval = int(value)
                elif key == "OptimisticUnchokingInterval":
                    config.optimistic_unchoking_interval = int(value)
                elif key == "FileName":
                    config.file_name = value
                elif key == "FileSize":
                    config.file_size = int(value)
                elif key == "PieceSize":
                    config.piece_size = int(value)
        return config
