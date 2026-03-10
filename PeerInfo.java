import java.io.*;
import java.util.*;

public class PeerInfo {
    int peerId;
    String hostName;
    int port;
    boolean hasFile;

    public PeerInfo(int peerId, String hostName, int port, boolean hasFile) {
        this.peerId = peerId;
        this.hostName = hostName;
        this.port = port;
        this.hasFile = hasFile;
    }

    public static List<PeerInfo> loadAll(String path) {
        List<PeerInfo> list = new ArrayList<>();
        try (BufferedReader br = new BufferedReader(new FileReader(path))) {
            String line;
            while ((line = br.readLine()) != null) {
                line = line.trim();
                if (line.isEmpty()) continue;
                String[] parts = line.split("\\s+");
                int id = Integer.parseInt(parts[0]);
                String host = parts[1];
                int port = Integer.parseInt(parts[2]);
                boolean hasFile = parts[3].trim().equals("1");
                list.add(new PeerInfo(id, host, port, hasFile));
            }
        } catch (IOException e) {
            e.printStackTrace();
        }
        return list;
    }
}
