#!/usr/bin/env python3
"""
run_test.py - Run a local test with multiple peers.

Mirrors the real project config (6 peers, tree.jpg, PieceSize 16384).
For local testing, all peers run on localhost with staggered ports.

Usage:
    python run_test.py
    python run_test.py --peers 4               # fewer peers for faster test
    python run_test.py --file 1001/tree.jpg    # use actual project file
"""

import os
import subprocess
import sys
import time
import shutil
import math
import argparse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Matches real project spec exactly
DEFAULT_NUM_PEERS = 6
DEFAULT_FILE_NAME = "tree.jpg"
DEFAULT_FILE_SIZE = 24301474
DEFAULT_PIECE_SIZE = 16384
DEFAULT_NUM_PREFERRED = 3
DEFAULT_UNCHOKING_INTERVAL = 5
DEFAULT_OPTIMISTIC_INTERVAL = 10
BASE_PORT = 7001


def build_configs(num_peers, file_name, file_size, piece_size,
                  num_preferred, unchoke_interval, opt_interval):
    common = (
        f"NumberOfPreferredNeighbors {num_preferred}\n"
        f"UnchokingInterval {unchoke_interval}\n"
        f"OptimisticUnchokingInterval {opt_interval}\n"
        f"FileName {file_name}\n"
        f"FileSize {file_size}\n"
        f"PieceSize {piece_size}\n"
    )
    peer_ids = [1001 + i for i in range(num_peers)]
    lines = [
        f"{pid} localhost {BASE_PORT + i} {'1' if i == 0 else '0'}"
        for i, pid in enumerate(peer_ids)
    ]
    peer_info = "\n".join(lines) + "\n"
    return common, peer_info, peer_ids


def setup(peer_ids, file_name, file_size, source_file=None):
    seeder_id = peer_ids[0]

    # Clean and recreate peer dirs using bare ID names: 1001/, 1002/, ...
    for pid in peer_ids:
        d = os.path.join(SCRIPT_DIR, str(pid))
        if os.path.exists(d):
            shutil.rmtree(d)
        os.makedirs(d)

    seeder_dir = os.path.join(SCRIPT_DIR, str(seeder_id))

    if source_file and os.path.exists(source_file):
        shutil.copy(source_file, os.path.join(seeder_dir, file_name))
        actual_size = os.path.getsize(source_file)
        print(f"  Using real file: {source_file} ({actual_size:,} bytes)")
    else:
        # Generate a synthetic file of the correct size
        print(f"  Generating synthetic {file_name} ({file_size:,} bytes)...")
        chunk = bytes(range(256)) * 256
        dest = os.path.join(seeder_dir, file_name)
        written = 0
        with open(dest, "wb") as f:
            while written < file_size:
                to_write = min(len(chunk), file_size - written)
                f.write(chunk[:to_write])
                written += to_write


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--peers", type=int, default=DEFAULT_NUM_PEERS,
                        help="Number of peers (default: 6)")
    parser.add_argument("--file", type=str, default=None,
                        help="Path to real file to share (e.g. 1001/tree.jpg)")
    args = parser.parse_args()

    num_peers = args.peers
    file_name = DEFAULT_FILE_NAME
    file_size = DEFAULT_FILE_SIZE

    if args.file and os.path.exists(args.file):
        file_size = os.path.getsize(args.file)

    num_pieces = math.ceil(file_size / DEFAULT_PIECE_SIZE)

    common_cfg, peer_info_cfg, peer_ids = build_configs(
        num_peers, file_name, file_size,
        DEFAULT_PIECE_SIZE, DEFAULT_NUM_PREFERRED,
        DEFAULT_UNCHOKING_INTERVAL, DEFAULT_OPTIMISTIC_INTERVAL,
    )

    with open(os.path.join(SCRIPT_DIR, "Common.cfg"), "w") as f:
        f.write(common_cfg)
    with open(os.path.join(SCRIPT_DIR, "PeerInfo.cfg"), "w") as f:
        f.write(peer_info_cfg)

    print("=== Setup ===")
    print(f"  Peers     : {peer_ids}")
    print(f"  Seeder    : {peer_ids[0]}")
    print(f"  File      : {file_name}  ({file_size:,} bytes)")
    print(f"  Pieces    : {num_pieces}  ({DEFAULT_PIECE_SIZE:,} bytes each)")
    print(f"  Preferred : {DEFAULT_NUM_PREFERRED}  |  Unchoke: {DEFAULT_UNCHOKING_INTERVAL}s  |  Opt: {DEFAULT_OPTIMISTIC_INTERVAL}s")
    print()

    setup(peer_ids, file_name, file_size, source_file=args.file)

    print("=== Launching peers ===")
    procs = []
    for pid in peer_ids:
        cmd = [sys.executable, os.path.join(SCRIPT_DIR, "peerProcess.py"), str(pid)]
        p = subprocess.Popen(cmd, cwd=SCRIPT_DIR)
        procs.append((pid, p))
        time.sleep(0.4)
        print(f"  Started peer {pid}")

    print(f"\nAll {len(procs)} peers running. Waiting for completion...")
    print("Press Ctrl+C to abort.\n")

    try:
        for pid, p in procs:
            p.wait()
    except KeyboardInterrupt:
        print("\nAborting...")
        for pid, p in procs:
            p.terminate()
        return

    print("\n=== Results ===")
    seeder_path = os.path.join(SCRIPT_DIR, str(peer_ids[0]), file_name)
    with open(seeder_path, "rb") as f:
        expected = f.read()

    all_ok = True
    for pid in peer_ids[1:]:
        path = os.path.join(SCRIPT_DIR, str(pid), file_name)
        if os.path.exists(path):
            with open(path, "rb") as f:
                got = f.read()
            if got == expected:
                print(f"  Peer {pid}: ✓  ({len(got):,} bytes)")
            else:
                print(f"  Peer {pid}: ✗  MISMATCH — got {len(got):,} bytes, expected {len(expected):,}")
                all_ok = False
        else:
            print(f"  Peer {pid}: ✗  file not found at {path}")
            all_ok = False

    print()
    if all_ok:
        print("✓ All peers successfully downloaded the file!")
    else:
        print("✗ Some peers failed — check log_peer_*.log for details.")


if __name__ == "__main__":
    main()
