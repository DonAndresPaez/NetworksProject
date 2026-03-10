"""
logger.py - Logging for each peer process
"""

import logging
import os
from datetime import datetime


def setup_logger(peer_id, log_dir="."):
    log_file = os.path.join(log_dir, f"log_peer_{peer_id}.log")
    logger = logging.getLogger(f"peer_{peer_id}")
    logger.setLevel(logging.DEBUG)

    fh = logging.FileHandler(log_file)
    fh.setLevel(logging.DEBUG)

    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)

    fmt = logging.Formatter("%(message)s")
    fh.setFormatter(fmt)
    ch.setFormatter(fmt)

    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger


def _ts():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log_tcp_connect(logger, p1, p2):
    logger.info(f"[{_ts()}]: Peer {p1} makes a connection to Peer {p2}.")


def log_tcp_connected_from(logger, p1, p2):
    logger.info(f"[{_ts()}]: Peer {p1} is connected from Peer {p2}.")


def log_preferred_neighbors(logger, peer_id, neighbors):
    ids = ",".join(str(n) for n in neighbors)
    logger.info(f"[{_ts()}]: Peer {peer_id} has the preferred neighbors {ids}.")


def log_optimistic_unchoke(logger, peer_id, neighbor_id):
    logger.info(f"[{_ts()}]: Peer {peer_id} has the optimistically unchoked neighbor {neighbor_id}.")


def log_unchoked(logger, p1, p2):
    logger.info(f"[{_ts()}]: Peer {p1} is unchoked by {p2}.")


def log_choked(logger, p1, p2):
    logger.info(f"[{_ts()}]: Peer {p1} is choked by {p2}.")


def log_have(logger, p1, p2, piece_index):
    logger.info(f"[{_ts()}]: Peer {p1} received the 'have' message from {p2} for the piece {piece_index}.")


def log_interested(logger, p1, p2):
    logger.info(f"[{_ts()}]: Peer {p1} received the 'interested' message from {p2}.")


def log_not_interested(logger, p1, p2):
    logger.info(f"[{_ts()}]: Peer {p1} received the 'not interested' message from {p2}.")


def log_downloaded_piece(logger, p1, p2, piece_index, num_pieces):
    logger.info(
        f"[{_ts()}]: Peer {p1} has downloaded the piece {piece_index} from {p2}. "
        f"Now the number of pieces it has is {num_pieces}."
    )


def log_download_complete(logger, peer_id):
    logger.info(f"[{_ts()}]: Peer {peer_id} has downloaded the complete file.")
