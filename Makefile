JCC = javac
JFLAGS =

SOURCES = peerProcess.java ConnectionHandler.java FileManager.java \
          PeerLogger.java CommonConfig.java PeerInfo.java StartRemotePeers.java

CLASSES = $(SOURCES:.java=.class)

all: $(CLASSES)

%.class: %.java
	$(JCC) $(JFLAGS) $<

peerProcess.class: peerProcess.java ConnectionHandler.java FileManager.java PeerLogger.java CommonConfig.java PeerInfo.java
	$(JCC) $(JFLAGS) peerProcess.java

StartRemotePeers.class: StartRemotePeers.java PeerInfo.java
	$(JCC) $(JFLAGS) StartRemotePeers.java

clean:
	rm -f *.class

.PHONY: all clean
