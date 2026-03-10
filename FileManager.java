import java.io.*;

public class FileManager {
    private int peerId;
    private CommonConfig config;
    private byte[][] pieces;
    private boolean[] hasPiece;
    private int numPieces;
    private int piecesCount;
    private String dirPath;

    public FileManager(int peerId, CommonConfig config, boolean hasFile) {
        this.peerId = peerId;
        this.config = config;
        this.numPieces = config.getNumberOfPieces();
        this.pieces = new byte[numPieces][];
        this.hasPiece = new boolean[numPieces];
        this.piecesCount = 0;
        this.dirPath = "peer_" + peerId;

        new File(dirPath).mkdirs();

        if (hasFile) {
            loadFile();
        }
    }

    private void loadFile() {
        String filePath = dirPath + File.separator + config.fileName;
        try (RandomAccessFile raf = new RandomAccessFile(filePath, "r")) {
            for (int i = 0; i < numPieces; i++) {
                int size = getPieceSize(i);
                pieces[i] = new byte[size];
                raf.readFully(pieces[i]);
                hasPiece[i] = true;
                piecesCount++;
            }
        } catch (IOException e) {
            e.printStackTrace();
        }
    }

    public synchronized int getPieceSize(int index) {
        if (index == numPieces - 1) {
            int lastSize = config.fileSize % config.pieceSize;
            return lastSize == 0 ? config.pieceSize : lastSize;
        }
        return config.pieceSize;
    }

    public synchronized boolean hasPiece(int index) {
        return hasPiece[index];
    }

    public synchronized boolean hasAllPieces() {
        return piecesCount == numPieces;
    }

    public synchronized int getPiecesCount() {
        return piecesCount;
    }

    public synchronized byte[] getPiece(int index) {
        return pieces[index];
    }

    public synchronized void setPiece(int index, byte[] data) {
        if (!hasPiece[index]) {
            pieces[index] = data;
            hasPiece[index] = true;
            piecesCount++;

            if (hasAllPieces()) {
                saveFile();
            }
        }
    }

    public synchronized byte[] getBitfield() {
        int bitfieldSize = (int) Math.ceil((double) numPieces / 8);
        byte[] bitfield = new byte[bitfieldSize];
        for (int i = 0; i < numPieces; i++) {
            if (hasPiece[i]) {
                bitfield[i / 8] |= (1 << (7 - i % 8));
            }
        }
        return bitfield;
    }

    public int getNumPieces() {
        return numPieces;
    }

    private void saveFile() {
        String filePath = dirPath + File.separator + config.fileName;
        try (FileOutputStream fos = new FileOutputStream(filePath)) {
            for (int i = 0; i < numPieces; i++) {
                fos.write(pieces[i]);
            }
        } catch (IOException e) {
            e.printStackTrace();
        }
    }
}
