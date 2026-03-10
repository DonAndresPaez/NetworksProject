import java.io.*;
import java.text.SimpleDateFormat;
import java.util.*;

public class PeerLogger {
    private PrintWriter writer;
    private int peerId;

    public PeerLogger(int peerId) {
        this.peerId = peerId;
        try {
            writer = new PrintWriter(new FileWriter("log_peer_" + peerId + ".log"), true);
        } catch (IOException e) {
            e.printStackTrace();
        }
    }

    private String getTimestamp() {
        return new SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new Date());
    }

    public synchronized void logTCPConnectionTo(int remotePeerId) {
        writer.println("[" + getTimestamp() + "]: Peer " + peerId +
                " makes a connection to Peer " + remotePeerId + ".");
    }

    public synchronized void logTCPConnectionFrom(int remotePeerId) {
        writer.println("[" + getTimestamp() + "]: Peer " + peerId +
                " is connected from Peer " + remotePeerId + ".");
    }

    public synchronized void logPreferredNeighbors(List<Integer> neighbors) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < neighbors.size(); i++) {
            if (i > 0) sb.append(", ");
            sb.append(neighbors.get(i));
        }
        writer.println("[" + getTimestamp() + "]: Peer " + peerId +
                " has the preferred neighbors " + sb.toString() + ".");
    }

    public synchronized void logOptimisticallyUnchokedNeighbor(int neighborId) {
        writer.println("[" + getTimestamp() + "]: Peer " + peerId +
                " has the optimistically unchoked neighbor " + neighborId + ".");
    }

    public synchronized void logUnchoking(int remotePeerId) {
        writer.println("[" + getTimestamp() + "]: Peer " + peerId +
                " is unchoked by " + remotePeerId + ".");
    }

    public synchronized void logChoking(int remotePeerId) {
        writer.println("[" + getTimestamp() + "]: Peer " + peerId +
                " is choked by " + remotePeerId + ".");
    }

    public synchronized void logHave(int remotePeerId, int pieceIndex) {
        writer.println("[" + getTimestamp() + "]: Peer " + peerId +
                " received the 'have' message from " + remotePeerId +
                " for the piece " + pieceIndex + ".");
    }

    public synchronized void logInterested(int remotePeerId) {
        writer.println("[" + getTimestamp() + "]: Peer " + peerId +
                " received the 'interested' message from " + remotePeerId + ".");
    }

    public synchronized void logNotInterested(int remotePeerId) {
        writer.println("[" + getTimestamp() + "]: Peer " + peerId +
                " received the 'not interested' message from " + remotePeerId + ".");
    }

    public synchronized void logDownloadedPiece(int remotePeerId, int pieceIndex, int totalPieces) {
        writer.println("[" + getTimestamp() + "]: Peer " + peerId +
                " has downloaded the piece " + pieceIndex + " from " + remotePeerId +
                ". Now the number of pieces it has is " + totalPieces + ".");
    }

    public synchronized void logDownloadComplete() {
        writer.println("[" + getTimestamp() + "]: Peer " + peerId +
                " has downloaded the complete file.");
    }

    public synchronized void close() {
        if (writer != null) {
            writer.close();
        }
    }
}
