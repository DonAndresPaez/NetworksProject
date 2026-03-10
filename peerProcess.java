import java.net.*;
import java.io.*;
import java.util.*;
import java.util.concurrent.*;

public class peerProcess {

    private int peerId;
    private CommonConfig commonConfig;
    private List<PeerInfo> peerInfoList;
    private FileManager fileManager;
    private PeerLogger logger;
    private final ConcurrentHashMap<Integer, ConnectionHandler> connections = new ConcurrentHashMap<>();
    private final Set<Integer> requestedPieces = Collections.synchronizedSet(new HashSet<>());
    private volatile boolean running = true;
    private volatile int optimisticallyUnchokedId = -1;
    private final Set<Integer> preferredNeighborIds = Collections.synchronizedSet(new HashSet<>());

    public static void main(String[] args) {
        if (args.length < 1) {
            System.out.println("Usage: java peerProcess <peerID>");
            return;
        }
        try {
            peerProcess process = new peerProcess(Integer.parseInt(args[0]));
            process.start();
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    public peerProcess(int peerId) {
        this.peerId = peerId;
    }

    public void start() throws Exception {
        commonConfig = CommonConfig.load("Common.cfg");
        peerInfoList = PeerInfo.loadAll("PeerInfo.cfg");

        PeerInfo myInfo = null;
        for (PeerInfo pi : peerInfoList) {
            if (pi.peerId == peerId) {
                myInfo = pi;
                break;
            }
        }
        if (myInfo == null) {
            System.err.println("Peer ID " + peerId + " not found in PeerInfo.cfg");
            return;
        }

        fileManager = new FileManager(peerId, commonConfig, myInfo.hasFile);
        logger = new PeerLogger(peerId);

        // Start server thread to accept incoming connections
        ServerSocket serverSocket = new ServerSocket(myInfo.port);
        Thread serverThread = new Thread(() -> {
            while (running) {
                try {
                    Socket socket = serverSocket.accept();
                    ConnectionHandler handler = new ConnectionHandler(this, socket, false);
                    new Thread(handler).start();
                } catch (IOException e) {
                    if (running) break;
                }
            }
        });
        serverThread.setDaemon(true);
        serverThread.start();

        // Connect to all peers that appear before this one in PeerInfo.cfg
        for (PeerInfo pi : peerInfoList) {
            if (pi.peerId == peerId) break;
            Socket socket = null;
            for (int attempt = 0; attempt < 10; attempt++) {
                try {
                    socket = new Socket(pi.hostName, pi.port);
                    break;
                } catch (ConnectException e) {
                    Thread.sleep(1000);
                }
            }
            if (socket != null) {
                ConnectionHandler handler = new ConnectionHandler(this, socket, true, pi.peerId);
                new Thread(handler).start();
                logger.logTCPConnectionTo(pi.peerId);
            } else {
                System.err.println("Could not connect to peer " + pi.peerId);
            }
        }

        // Schedule preferred neighbors selection (every unchokingInterval seconds)
        ScheduledExecutorService scheduler = Executors.newScheduledThreadPool(2);
        scheduler.scheduleAtFixedRate(() -> {
            try {
                selectPreferredNeighbors();
            } catch (Exception e) {
                e.printStackTrace();
            }
        }, commonConfig.unchokingInterval, commonConfig.unchokingInterval, TimeUnit.SECONDS);

        // Schedule optimistic unchoking (every optimisticUnchokingInterval seconds)
        scheduler.scheduleAtFixedRate(() -> {
            try {
                selectOptimisticallyUnchokedNeighbor();
            } catch (Exception e) {
                e.printStackTrace();
            }
        }, commonConfig.optimisticUnchokingInterval, commonConfig.optimisticUnchokingInterval, TimeUnit.SECONDS);

        // Wait for all peers to complete
        while (running) {
            Thread.sleep(1000);
            if (checkAllComplete()) {
                running = false;
                Thread.sleep(2000);
                break;
            }
        }

        // Cleanup
        scheduler.shutdownNow();
        try { serverSocket.close(); } catch (IOException e) { /* ignore */ }
        for (ConnectionHandler handler : connections.values()) {
            handler.close();
        }
        logger.close();
        System.out.println("Peer " + peerId + " has finished.");
    }

    public void registerConnection(int remotePeerId, ConnectionHandler handler) {
        connections.put(remotePeerId, handler);
    }

    public synchronized void selectPreferredNeighbors() {
        int k = commonConfig.numberOfPreferredNeighbors;

        List<ConnectionHandler> interestedNeighbors = new ArrayList<>();
        for (ConnectionHandler handler : connections.values()) {
            if (handler.peerInterested) {
                interestedNeighbors.add(handler);
            }
        }

        // Shuffle first for random tie-breaking (Java's sort is stable)
        Collections.shuffle(interestedNeighbors);

        List<ConnectionHandler> selected;
        if (fileManager.hasAllPieces()) {
            // Random selection among interested neighbors
            selected = interestedNeighbors.subList(0, Math.min(k, interestedNeighbors.size()));
        } else {
            // Sort by download rate descending
            interestedNeighbors.sort((a, b) -> Long.compare(b.downloadedBytesPrev, a.downloadedBytesPrev));
            selected = interestedNeighbors.subList(0, Math.min(k, interestedNeighbors.size()));
        }

        Set<Integer> newPreferred = new HashSet<>();
        List<Integer> preferredList = new ArrayList<>();
        for (ConnectionHandler h : selected) {
            newPreferred.add(h.remotePeerId);
            preferredList.add(h.remotePeerId);
        }

        if (!preferredList.isEmpty()) {
            logger.logPreferredNeighbors(preferredList);
        }

        // Update choke/unchoke states
        for (ConnectionHandler handler : connections.values()) {
            if (newPreferred.contains(handler.remotePeerId)) {
                if (handler.amChoking) {
                    handler.amChoking = false;
                    handler.sendUnchoke();
                }
            } else if (handler.remotePeerId != optimisticallyUnchokedId) {
                if (!handler.amChoking) {
                    handler.amChoking = true;
                    handler.sendChoke();
                }
            }
        }

        preferredNeighborIds.clear();
        preferredNeighborIds.addAll(newPreferred);

        // Snapshot download counters for next interval
        for (ConnectionHandler handler : connections.values()) {
            handler.downloadedBytesPrev = handler.downloadedBytes;
            handler.downloadedBytes = 0;
        }
    }

    public synchronized void selectOptimisticallyUnchokedNeighbor() {
        // Candidates: choked AND interested
        List<ConnectionHandler> candidates = new ArrayList<>();
        for (ConnectionHandler handler : connections.values()) {
            if (handler.amChoking && handler.peerInterested) {
                candidates.add(handler);
            }
        }

        // Choke previous optimistic (if not preferred)
        if (optimisticallyUnchokedId != -1 && !preferredNeighborIds.contains(optimisticallyUnchokedId)) {
            ConnectionHandler prev = connections.get(optimisticallyUnchokedId);
            if (prev != null && !prev.amChoking) {
                prev.amChoking = true;
                prev.sendChoke();
            }
        }

        if (candidates.isEmpty()) {
            optimisticallyUnchokedId = -1;
            return;
        }

        ConnectionHandler selected = candidates.get(new Random().nextInt(candidates.size()));
        optimisticallyUnchokedId = selected.remotePeerId;
        selected.amChoking = false;
        selected.sendUnchoke();

        logger.logOptimisticallyUnchokedNeighbor(selected.remotePeerId);
    }

    public synchronized int selectPieceToRequest(int remotePeerId) {
        ConnectionHandler handler = connections.get(remotePeerId);
        if (handler == null) return -1;

        List<Integer> available = new ArrayList<>();
        for (int i = 0; i < fileManager.getNumPieces(); i++) {
            if (!fileManager.hasPiece(i) && handler.hasRemotePiece(i) && !requestedPieces.contains(i)) {
                available.add(i);
            }
        }

        if (available.isEmpty()) return -1;

        int selected = available.get(new Random().nextInt(available.size()));
        requestedPieces.add(selected);
        return selected;
    }

    public synchronized void cancelRequest(int pieceIndex) {
        if (pieceIndex >= 0) {
            requestedPieces.remove(pieceIndex);
        }
    }

    public synchronized void pieceReceived(int pieceIndex, byte[] data, int fromPeerId) {
        if (fileManager.hasPiece(pieceIndex)) {
            requestedPieces.remove(pieceIndex);
            return;
        }

        requestedPieces.remove(pieceIndex);
        fileManager.setPiece(pieceIndex, data);

        logger.logDownloadedPiece(fromPeerId, pieceIndex, fileManager.getPiecesCount());

        if (fileManager.hasAllPieces()) {
            logger.logDownloadComplete();
        }

        // Send 'have' to all neighbors
        for (ConnectionHandler handler : connections.values()) {
            handler.sendHave(pieceIndex);
        }

        // Update interest state for all neighbors
        for (ConnectionHandler handler : connections.values()) {
            handler.updateInterestState();
        }
    }

    public boolean checkAllComplete() {
        if (!fileManager.hasAllPieces()) return false;

        for (PeerInfo pi : peerInfoList) {
            if (pi.peerId == peerId) continue;
            ConnectionHandler handler = connections.get(pi.peerId);
            if (handler == null) return false;
            if (!handler.hasRemoteAllPieces()) return false;
        }

        return true;
    }

    // --- Getters ---

    public int getPeerId() {
        return peerId;
    }

    public CommonConfig getCommonConfig() {
        return commonConfig;
    }

    public FileManager getFileManager() {
        return fileManager;
    }

    public PeerLogger getLogger() {
        return logger;
    }

    public boolean isRunning() {
        return running;
    }
}
