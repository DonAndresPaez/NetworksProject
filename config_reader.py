import math

def parseCommonCfg(file_path):
    config = {}
    with open(file_path,'r') as f:
        for line in f:
            if not line.strip():
                continue
            parts = line.split()

            # Parse to int if it is a number, else, keep as string
            key, value = parts[0], parts[1]
            if value.isdigit():
                config[key] = int(value)
            else:
                config[key] = value

            # This is helpful for the messenger role since we need the number of pieces in which a message is gonna be divided.
            if 'FileSize' in config and 'PieceSize' in config:
                config['TotalPieces'] = math.ceil(config['FileSize']/config['PieceSize'])
                config['LastPieceSize'] = config['FileSize'] % config['PieceSize'] or config['PieceSize']
    return config
    
def parsePeerInfo(file_path):
    peers = []
    with open(file_path,'r') as f:
        for line in f:
            if not line.strip():
                continue
            p_id, host, port, has_file = line.split()

            peers.append({
                'id': int(p_id),
                'host': host,
                'port': int(port),
                'has_file': bool(int(has_file)) # 1 means complete file, 0 means no pieces
            })
    return peers

            
