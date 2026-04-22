import sys
import time
import threading

from config_reader import parseCommonCfg, parsePeerInfo
from networking import PeerConnector
from logger import PeerLogger
from bitfield import Bitfield
from file_manager import FileManager


def main():
    print("--- [Initialization] Starting Peer Process ---")

    if len(sys.argv) < 2:
        print("[Error] Usage: python peerProcess.py [PeerID]")
        return

    my_id = int(sys.argv[1])

    try:
        common_cfg = parseCommonCfg('Common.cfg')
        peer_list = parsePeerInfo('PeerInfo.cfg')

        my_info = next((p for p in peer_list if p['id'] == my_id), None)
        if not my_info:
            print(f"[Error] Peer {my_id} not found in PeerInfo.cfg")
            return

        has_file = my_info['has_file']

        # Set up logger
        logger = PeerLogger(my_id)

        # Set up bitfield
        my_bitfield = Bitfield(common_cfg, has_file)

        # Set up file manager and initialize file on disk
        file_mgr = FileManager(my_id, common_cfg)
        file_mgr.init_file(has_file)

        # Set up connector (all protocol logic lives here)
        connector = PeerConnector(
            my_id=my_id,
            my_port=my_info['port'],
            peer_list=peer_list,
            logger=logger,
            bitfield=my_bitfield,
            common_cfg=common_cfg,
            file_manager=file_mgr
        )

        # Start TCP server in background
        server_thread = threading.Thread(target=connector.start_server, daemon=True)
        server_thread.start()

        # Brief pause to let server bind before we start connecting outward
        time.sleep(0.5)

        # Connect to all peers that started before us (lower IDs)
        connector.connect_to_previous_peers()

        # Start choking/unchoking schedulers
        connector.start_unchoke_scheduler()
        connector.start_optimistic_unchoke_scheduler()

        print(f"--- [Active] Peer {my_id} is running. Press Ctrl+C to exit. ---")

        while not connector.done:
            time.sleep(1)

        print(f"[Shutdown] Peer {my_id} has finished.")

    except KeyboardInterrupt:
        print(f"\n[Shutdown] Peer {my_id} closing.")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[Critical Error] {e}")


if __name__ == "__main__":
    main()