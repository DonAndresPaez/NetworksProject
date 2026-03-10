import java.io.*;
import java.util.*;

/**
 * Reads PeerInfo.cfg and starts each peer process on its designated host via SSH.
 * For localhost testing, all peers are started locally.
 */
public class StartRemotePeers {

    public static void main(String[] args) {
        List<PeerInfo> peers = PeerInfo.loadAll("PeerInfo.cfg");
        String workingDir = System.getProperty("user.dir");

        for (PeerInfo peer : peers) {
            try {
                String host = peer.hostName;
                if (host.equals("localhost") || host.equals("127.0.0.1")) {
                    // Start locally
                    System.out.println("Starting peer " + peer.peerId + " locally...");
                    ProcessBuilder pb = new ProcessBuilder("java", "peerProcess", String.valueOf(peer.peerId));
                    pb.directory(new File(workingDir));
                    pb.redirectErrorStream(true);
                    Process p = pb.start();
                    // Read output in a separate thread
                    final int id = peer.peerId;
                    new Thread(() -> {
                        try (BufferedReader br = new BufferedReader(new InputStreamReader(p.getInputStream()))) {
                            String line;
                            while ((line = br.readLine()) != null) {
                                System.out.println("[Peer " + id + "] " + line);
                            }
                        } catch (IOException e) { /* ignore */ }
                    }).start();
                } else {
                    // Start via SSH
                    System.out.println("Starting peer " + peer.peerId + " on " + host + "...");
                    ProcessBuilder pb = new ProcessBuilder(
                        "ssh", host,
                        "cd " + workingDir + " && java peerProcess " + peer.peerId
                    );
                    pb.redirectErrorStream(true);
                    Process p = pb.start();
                    final int id = peer.peerId;
                    new Thread(() -> {
                        try (BufferedReader br = new BufferedReader(new InputStreamReader(p.getInputStream()))) {
                            String line;
                            while ((line = br.readLine()) != null) {
                                System.out.println("[Peer " + id + "] " + line);
                            }
                        } catch (IOException e) { /* ignore */ }
                    }).start();
                }
                Thread.sleep(500); // Small delay between starting peers
            } catch (Exception e) {
                System.err.println("Failed to start peer " + peer.peerId + ": " + e.getMessage());
            }
        }
    }
}
