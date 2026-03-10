import subprocess
import sys
import os
import time

from peer_info import PeerInfoEntry


def main():
    peers = PeerInfoEntry.load_all("PeerInfo.cfg")
    working_dir = os.getcwd()

    processes = []
    for peer in peers:
        host = peer.host_name
        if host in ("localhost", "127.0.0.1"):
            print(f"Starting peer {peer.peer_id} locally...")
            p = subprocess.Popen(
                [sys.executable, "peerProcess.py", str(peer.peer_id)],
                cwd=working_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            processes.append((peer.peer_id, p))
        else:
            print(f"Starting peer {peer.peer_id} on {host}...")
            p = subprocess.Popen(
                ["ssh", host, f"cd {working_dir} && python3 peerProcess.py {peer.peer_id}"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            processes.append((peer.peer_id, p))
        time.sleep(0.5)

    # Print output from each process
    for peer_id, p in processes:
        p.wait()
        output = p.stdout.read()
        if output:
            for line in output.strip().splitlines():
                print(f"[Peer {peer_id}] {line}")


if __name__ == "__main__":
    main()
