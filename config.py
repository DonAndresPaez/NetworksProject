"""
config.py - Parse Common.cfg and PeerInfo.cfg
"""

import os


def read_common_config(path="Common.cfg"):
    cfg = {}
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, val = line.split()
            cfg[key] = val
    return {
        "num_preferred": int(cfg["NumberOfPreferredNeighbors"]),
        "unchoking_interval": int(cfg["UnchokingInterval"]),
        "optimistic_interval": int(cfg["OptimisticUnchokingInterval"]),
        "file_name": cfg["FileName"],
        "file_size": int(cfg["FileSize"]),
        "piece_size": int(cfg["PieceSize"]),
    }


def read_peer_info(path="PeerInfo.cfg"):
    peers = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            peers.append({
                "id": int(parts[0]),
                "host": parts[1],
                "port": int(parts[2]),
                  "has_file": parts[3] == "1",
            })
    return peers


def num_pieces(cfg):
    import math
    return math.ceil(cfg["file_size"] / cfg["piece_size"])
