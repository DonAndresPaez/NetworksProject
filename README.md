# Networking Project - P2P File Sharing (BitTorrent-style)

## Team Members & Roles

*(Fill in your team member names and roles here)*

## Overview

A peer-to-peer file sharing system inspired by BitTorrent, implementing the choking-unchoking mechanism, piece exchange protocol, and multi-peer file distribution over TCP.

## Files

| File | Description |
|------|-------------|
| `peerProcess.java` | Main peer process entry point. Reads configs, manages connections, runs choking/unchoking timers, and coordinates file exchange. |
| `ConnectionHandler.java` | Handles a single TCP connection with another peer. Manages handshake, message sending/receiving, and protocol state. |
| `FileManager.java` | Manages file pieces: reading/writing pieces, bitfield tracking, and assembling the complete file. |
| `PeerLogger.java` | Writes log entries for all protocol events (connections, choke/unchoke, piece downloads, etc.). |
| `CommonConfig.java` | Parses `Common.cfg` configuration file. |
| `PeerInfo.java` | Parses `PeerInfo.cfg` peer information file. |
| `StartRemotePeers.java` | Utility to start all peer processes (locally or via SSH on remote hosts). |

## How to Compile

```bash
javac peerProcess.java
```

Or compile all files:

```bash
javac *.java
```

## How to Run

### Setup

1. Place `Common.cfg` and `PeerInfo.cfg` in the working directory.
2. Create subdirectories `peer_[peerID]/` for each peer.
3. For peers that have the file (marked `1` in `PeerInfo.cfg`), place the data file in their subdirectory.

### Starting Peers

Start each peer **in the order listed in `PeerInfo.cfg`**:

```bash
java peerProcess 1001
java peerProcess 1002
java peerProcess 1003
```

Or use the startup utility to launch all peers:

```bash
java StartRemotePeers
```

### Example with localhost

1. Edit `PeerInfo.cfg` to use `localhost`:
   ```
   1001 localhost 6001 1
   1002 localhost 6002 0
   1003 localhost 6003 0
   ```

2. Create peer directories and place the file:
   ```bash
   mkdir peer_1001 peer_1002 peer_1003
   cp myfile.dat peer_1001/myfile.dat
   ```

3. Open separate terminals and start each peer in order.

## Protocol

- **Handshake**: 32-byte message (18-byte header `P2PFILESHARINGPROJ` + 10 zero bytes + 4-byte peer ID)
- **Messages**: choke, unchoke, interested, not interested, have, bitfield, request, piece
- **Choking**: Every `UnchokingInterval` seconds, select `k` preferred neighbors based on download rate
- **Optimistic Unchoking**: Every `OptimisticUnchokingInterval` seconds, randomly unchoke one choked interested neighbor
- **Termination**: Each peer exits when all peers have the complete file

## Logging

Each peer writes to `log_peer_[peerID].log` in the working directory.

