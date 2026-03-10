Networking Project

Maksym Marek
Patric McCormack
Jack Ozerovitch
Andres Paez

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
1) Ensure all .py source files and the .cfg are in the main root directory.

2) The project assumes that subdirectories for each peer (peer_1001, peer_1002, etc) already exist.

3) To run the project, launch via PowerShell in a single window:
    Start-Process python "peerProcess.py 1001"
    Start-Process python "peerProcess.py 1002"
    Start-Process python "peerProcess.py 1003"

This will open each peer in a new, independent terminal where you can monitor the activity and handshakes from each side.



