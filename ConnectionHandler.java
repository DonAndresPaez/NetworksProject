import java.io.*;
import java.net.*;
import java.util.*;

public class ConnectionHandler implements Runnable {
    static final byte CHOKE = 0;
    static final byte UNCHOKE = 1;
    static final byte INTERESTED = 2;
    static final byte NOT_INTERESTED = 3;
    static final byte HAVE = 4;
    static final byte BITFIELD = 5;
    static final byte REQUEST = 6;
    static final byte PIECE = 7;

    peerProcess peerProc;
    Socket socket;
    DataInputStream in;
    DataOutputStream out;
    int remotePeerId;
    boolean[] remoteBitfield;
    volatile boolean amChoking = true;       // we are choking the remote peer
    volatile boolean amInterested = false;   // we are interested in remote
    volatile boolean peerChoking = true;     // remote is choking us
    volatile boolean peerInterested = false; // remote is interested in us
    volatile long downloadedBytes = 0;
    volatile long downloadedBytesPrev = 0;
    volatile int pendingRequest = -1;
    boolean initiator;

    public ConnectionHandler(peerProcess peerProc, Socket socket, boolean initiator) {
        this(peerProc, socket, initiator, -1);
    }

    public ConnectionHandler(peerProcess peerProc, Socket socket, boolean initiator, int remotePeerId) {
        this.peerProc = peerProc;
        this.socket = socket;
        this.initiator = initiator;
        this.remotePeerId = remotePeerId;
        this.remoteBitfield = new boolean[peerProc.getFileManager().getNumPieces()];
    }

    public void run() {
        try {
            out = new DataOutputStream(new BufferedOutputStream(socket.getOutputStream()));
            in = new DataInputStream(new BufferedInputStream(socket.getInputStream()));

            if (initiator) {
                sendHandshake();
                receiveHandshake();
            } else {
                receiveHandshake();
                sendHandshake();
                peerProc.getLogger().logTCPConnectionFrom(remotePeerId);
            }

            peerProc.registerConnection(remotePeerId, this);

            // Send bitfield if we have any pieces
            if (peerProc.getFileManager().getPiecesCount() > 0) {
                sendBitfield();
            }

            // Message loop
            while (peerProc.isRunning()) {
                int length = in.readInt();
                if (length < 1) continue;
                byte type = in.readByte();
                byte[] payload = new byte[length - 1];
                if (length > 1) {
                    in.readFully(payload);
                }
                handleMessage(type, payload);
            }
        } catch (IOException e) {
            // Connection closed or lost
        } finally {
            close();
        }
    }

    private void sendHandshake() throws IOException {
        byte[] handshake = new byte[32];
        byte[] header = "P2PFILESHARINGPROJ".getBytes("US-ASCII");
        System.arraycopy(header, 0, handshake, 0, 18);
        // bytes 18-27 are zero (default)
        int id = peerProc.getPeerId();
        handshake[28] = (byte) (id >> 24);
        handshake[29] = (byte) (id >> 16);
        handshake[30] = (byte) (id >> 8);
        handshake[31] = (byte) id;
        synchronized (out) {
            out.write(handshake);
            out.flush();
        }
    }

    private void receiveHandshake() throws IOException {
        byte[] handshake = new byte[32];
        in.readFully(handshake);

        String header = new String(handshake, 0, 18, "US-ASCII");
        if (!header.equals("P2PFILESHARINGPROJ")) {
            throw new IOException("Invalid handshake header: " + header);
        }

        int receivedId = ((handshake[28] & 0xFF) << 24) |
                          ((handshake[29] & 0xFF) << 16) |
                          ((handshake[30] & 0xFF) << 8) |
                          (handshake[31] & 0xFF);

        if (initiator && receivedId != remotePeerId) {
            throw new IOException("Unexpected peer ID: " + receivedId);
        }

        remotePeerId = receivedId;
    }

    private void handleMessage(byte type, byte[] payload) {
        switch (type) {
            case CHOKE:
                handleChoke();
                break;
            case UNCHOKE:
                handleUnchoke();
                break;
            case INTERESTED:
                handleInterested();
                break;
            case NOT_INTERESTED:
                handleNotInterested();
                break;
            case HAVE:
                handleHave(payload);
                break;
            case BITFIELD:
                handleBitfield(payload);
                break;
            case REQUEST:
                handleRequest(payload);
                break;
            case PIECE:
                handlePiece(payload);
                break;
        }
    }

    private void handleChoke() {
        peerChoking = true;
        peerProc.getLogger().logChoking(remotePeerId);
        if (pendingRequest >= 0) {
            peerProc.cancelRequest(pendingRequest);
            pendingRequest = -1;
        }
    }

    private void handleUnchoke() {
        peerChoking = false;
        peerProc.getLogger().logUnchoking(remotePeerId);
        requestPiece();
    }

    private void handleInterested() {
        peerInterested = true;
        peerProc.getLogger().logInterested(remotePeerId);
    }

    private void handleNotInterested() {
        peerInterested = false;
        peerProc.getLogger().logNotInterested(remotePeerId);
    }

    private void handleHave(byte[] payload) {
        int pieceIndex = byteArrayToInt(payload);
        remoteBitfield[pieceIndex] = true;
        peerProc.getLogger().logHave(remotePeerId, pieceIndex);
        updateInterestState();
    }

    private void handleBitfield(byte[] payload) {
        int numPieces = peerProc.getFileManager().getNumPieces();
        for (int i = 0; i < numPieces; i++) {
            remoteBitfield[i] = (payload[i / 8] & (1 << (7 - i % 8))) != 0;
        }
        updateInterestState();
    }

    private void handleRequest(byte[] payload) {
        if (!amChoking) {
            int pieceIndex = byteArrayToInt(payload);
            byte[] pieceData = peerProc.getFileManager().getPiece(pieceIndex);
            if (pieceData != null) {
                sendPiece(pieceIndex, pieceData);
            }
        }
    }

    private void handlePiece(byte[] payload) {
        int pieceIndex = byteArrayToInt(Arrays.copyOfRange(payload, 0, 4));
        byte[] pieceData = Arrays.copyOfRange(payload, 4, payload.length);

        downloadedBytes += pieceData.length;
        pendingRequest = -1;

        peerProc.pieceReceived(pieceIndex, pieceData, remotePeerId);

        // Request next piece if still unchoked
        if (!peerChoking) {
            requestPiece();
        }
    }

    public void updateInterestState() {
        boolean shouldBeInterested = false;
        FileManager fm = peerProc.getFileManager();
        for (int i = 0; i < fm.getNumPieces(); i++) {
            if (!fm.hasPiece(i) && remoteBitfield[i]) {
                shouldBeInterested = true;
                break;
            }
        }

        if (shouldBeInterested && !amInterested) {
            amInterested = true;
            sendInterested();
        } else if (!shouldBeInterested && amInterested) {
            amInterested = false;
            sendNotInterested();
        }
    }

    private void requestPiece() {
        int pieceIndex = peerProc.selectPieceToRequest(remotePeerId);
        if (pieceIndex >= 0) {
            pendingRequest = pieceIndex;
            sendRequest(pieceIndex);
        }
    }

    // --- Send methods ---

    public void sendChoke() {
        sendMessage(CHOKE, new byte[0]);
    }

    public void sendUnchoke() {
        sendMessage(UNCHOKE, new byte[0]);
    }

    public void sendInterested() {
        sendMessage(INTERESTED, new byte[0]);
    }

    public void sendNotInterested() {
        sendMessage(NOT_INTERESTED, new byte[0]);
    }

    public void sendHave(int pieceIndex) {
        sendMessage(HAVE, intToByteArray(pieceIndex));
    }

    public void sendBitfield() {
        byte[] bitfield = peerProc.getFileManager().getBitfield();
        sendMessage(BITFIELD, bitfield);
    }

    public void sendRequest(int pieceIndex) {
        sendMessage(REQUEST, intToByteArray(pieceIndex));
    }

    public void sendPiece(int pieceIndex, byte[] data) {
        byte[] payload = new byte[4 + data.length];
        byte[] indexBytes = intToByteArray(pieceIndex);
        System.arraycopy(indexBytes, 0, payload, 0, 4);
        System.arraycopy(data, 0, payload, 4, data.length);
        sendMessage(PIECE, payload);
    }

    private void sendMessage(byte type, byte[] payload) {
        try {
            synchronized (out) {
                out.writeInt(1 + payload.length);
                out.writeByte(type);
                if (payload.length > 0) {
                    out.write(payload);
                }
                out.flush();
            }
        } catch (IOException e) {
            // Connection lost
        }
    }

    // --- Query methods ---

    public boolean hasRemotePiece(int index) {
        return remoteBitfield[index];
    }

    public boolean hasRemoteAllPieces() {
        for (boolean b : remoteBitfield) {
            if (!b) return false;
        }
        return true;
    }

    public void close() {
        try {
            if (pendingRequest >= 0) {
                peerProc.cancelRequest(pendingRequest);
                pendingRequest = -1;
            }
            socket.close();
        } catch (IOException e) {
            // ignore
        }
    }

    // --- Utility ---

    private static int byteArrayToInt(byte[] bytes) {
        return ((bytes[0] & 0xFF) << 24) | ((bytes[1] & 0xFF) << 16) |
               ((bytes[2] & 0xFF) << 8) | (bytes[3] & 0xFF);
    }

    private static byte[] intToByteArray(int value) {
        return new byte[] {
            (byte) (value >> 24), (byte) (value >> 16),
            (byte) (value >> 8), (byte) value
        };
    }
}
