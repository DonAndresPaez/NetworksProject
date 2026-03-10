import sys
import time
import threading
import os
from config_reader import parseCommonCfg, parsePeerInfo
from networking import PeerConnector
from logger import PeerLogger
from bitfield import Bitfield

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

        logger = PeerLogger(my_id)
        has_file = (my_info['has_file'] == 1)
        my_bitfield = Bitfield(common_cfg, has_file)

        connector = PeerConnector(my_id, my_info['port'], peer_list, logger, my_bitfield)

        server_thread = threading.Thread(target=connector.start_server, daemon=True)
        server_thread.start()

        time.sleep(1)
        connector.connect_to_previous_peers()

        print(f"--- [Active] Peer {my_id} is running. Press Ctrl+C to exit. ---")
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print(f"\n[Shutdown] Peer {my_id} closing.")
    except Exception as e:
        print(f"[Critical Error] {e}")


if __name__ == "__main__":
    main()