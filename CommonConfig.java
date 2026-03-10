import java.io.*;

public class CommonConfig {
    int numberOfPreferredNeighbors;
    int unchokingInterval;
    int optimisticUnchokingInterval;
    String fileName;
    int fileSize;
    int pieceSize;

    public int getNumberOfPieces() {
        return (int) Math.ceil((double) fileSize / pieceSize);
    }

    public static CommonConfig load(String path) {
        CommonConfig config = new CommonConfig();
        try (BufferedReader br = new BufferedReader(new FileReader(path))) {
            String line;
            while ((line = br.readLine()) != null) {
                line = line.trim();
                if (line.isEmpty()) continue;
                String[] parts = line.split("\\s+");
                switch (parts[0]) {
                    case "NumberOfPreferredNeighbors":
                        config.numberOfPreferredNeighbors = Integer.parseInt(parts[1]);
                        break;
                    case "UnchokingInterval":
                        config.unchokingInterval = Integer.parseInt(parts[1]);
                        break;
                    case "OptimisticUnchokingInterval":
                        config.optimisticUnchokingInterval = Integer.parseInt(parts[1]);
                        break;
                    case "FileName":
                        config.fileName = parts[1];
                        break;
                    case "FileSize":
                        config.fileSize = Integer.parseInt(parts[1]);
                        break;
                    case "PieceSize":
                        config.pieceSize = Integer.parseInt(parts[1]);
                        break;
                }
            }
        } catch (IOException e) {
            e.printStackTrace();
        }
        return config;
    }
}
