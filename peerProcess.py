import sys, time, threading
from config_reader import parseCommonCfg, parsePeerInfo
from networking import PeerConnector
from logger import PeerLogger
from bitfield import Bitfield
from piece_manager import PieceManager

def main():
    if len(sys.argv) < 2:
        print("[Error] Usage: python peerProcess.py [PeerID]")
        return
        
    my_id = int(sys.argv[1])
    common = parseCommonCfg('Common.cfg')
    peers = parsePeerInfo('PeerInfo.cfg')
    
    my_info = next((p for p in peers if p['id'] == my_id), None)
    if not my_info:
        print(f"[Error] Peer {my_id} not found in PeerInfo.cfg")
        return

    logger = PeerLogger(my_id)
    bitfield = Bitfield(common, my_info['has_file'])
    pm = PieceManager(my_id, common)
    
    conn = PeerConnector(my_id, my_info['port'], peers, logger, bitfield, pm, common)
    
    # Server Thread
    threading.Thread(target=conn.start_server, daemon=True).start()
    time.sleep(1)
    conn.connect_to_previous_peers()

    def run_timers():
        p = int(common['UnchokingInterval'])
        m = int(common['OptimisticUnchokingInterval'])
        last_p = last_m = time.time()
        
        expected_neighbors = len(peers) - 1 

        while conn.running:
            now = time.time()
            if now - last_p >= p:
                conn.select_preferred()
                last_p = now
            if now - last_m >= m:
                conn.select_optimistic()
                last_m = now
            
            # Check if all peers have the complete file [cite: 161, 242]
            if (bitfield.is_complete() and 
                len(conn.neighbor_bits) == expected_neighbors and 
                all(all(x == 1 for x in b) for b in conn.neighbor_bits.values())):
                
                print(f"--- [Success] Swarm completion detected. Terminating Peer {my_id}. ---")
                conn.running = False
                break
                
            time.sleep(1)

    run_timers()

if __name__ == "__main__":
    main()