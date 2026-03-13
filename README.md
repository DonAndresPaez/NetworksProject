Networking Project

Maksym Marek
Patric McCormack
Jack Ozerovitch
Andres Paez


Contributions

Maksym Marek
- networking.py: TCP server/client architecture, connection threading, receive loop
- test_file_transfer.py: End-to-end file piece transfer test
- main.ipynb: Jupyter automation notebook (peer launching, log viewing, test cell)

Patric McCormack
- peerProcess.py: Main entry point, peer initialization, thread orchestration
- bitfield.py: Bitfield construction, serialization, piece tracking

Jack Ozerovitch
- handshake.py: 32-byte handshake protocol, struct packing/unpacking, verification
- message_handler.py: Message protocol, type constants, create/parse functions

Andres Paez
- config_reader.py: Common.cfg and PeerInfo.cfg parsing, piece count calculations
- logger.py: Timestamped log file generation per peer


Project Structure

peerProcess.py -> Main entry point. Initializes the configurations, starts the logger, builds the bitfield, and launches the service/client threads.
networking.py -> Handles all TCP socket logic. Manages simultaneous incoming and outgoing connectiosn using a thread-per-connection model.
handshake.py -> Manages the 32-byte handshake protocol. It also has the struct logic for the 18-byte header and 4-byte PeerID.
message_handler.py -> Defines the actual message protocol. Constructs and parses the format for all post-handshake communication.
bitfield.py -> Tracks which file pieces the peer owns.
config_reader.py -> Parses Common.cfg and PeerInfo.cfg. Calculates values like the total number of pieces and the size of the final piece.
logger.py -> Implements the project logging format generating timestamped entries in a unique file created for each peer.


Implementation Status (Midpoint)

Configuration Parsing: Successfully reading environment variables and neighbor information.

TCP Networking: Symmetrical client/server architecture implemented.

Protocol Handshake: Full 32-byte binary exchange and verification complete.

Bitfield Exchange: Peers share their "piece map" immediately upon connection.

Interest Logic: Peers can analyze a neighbor's bitfield to determine if they need pieces from them.

Logging: Mandatory log file generation with correct timestamps.


How to Run:

Option 1: Automated (Jupyter Notebook)

1) Ensure Common.cfg and PeerInfo.cfg are in the root directory.

2) Open main.ipynb in Jupyter Notebook or VS Code.

3) Run the cells in order (click run all):
    - Step 1: Loads and displays the configuration.
    - Step 2: Launches all peers automatically as background processes.
    - Step 3: View log output from all peers (re-run anytime to refresh).
    - Step 4: Check which peers are still running.
    - Step 5: Stop all peers when finished.

*IMPORTANT* Proper funcaitonality will indicate peer 102 creates a new file.

Option 2: Manual (Multiple Terminals)

1) Ensure Common.cfg and PeerInfo.cfg are in the root directory.

2) Open multiple terminal windows (one per peer).

3) In each window, run in ascending order of PeerID:
    python peerProcess.py [PeerID]

   Example:
    Terminal 1: python peerProcess.py 1001
    Terminal 2: python peerProcess.py 1002
    ...
    Terminal 9: python peerProcess.py 1009

4) Stop each peer with Ctrl+C.

