# Distributed Gold Mining Game using ZooKeeper

A distributed text-based gold mining game where human players compete against bots across a network using Apache ZooKeeper for coordination.

## Quick Start

### Prerequisites
- Python 3.7+
- Apache ZooKeeper or Docker
- kazoo library (see requirements.txt)

### Installation
```bash
pip install -r requirements.txt
```

### Setup ZooKeeper

**Option 1: Docker (Recommended)**
```bash
docker run -d --name zookeeper -p 2181:2181 zookeeper
```

**Option 2: Local Installation**
Download from https://zookeeper.apache.org and run:
```bash
./zkServer.sh start
```

### Run the Game

**Terminal 1: Start Game Server**
```bash
python game_server.py
```

**Terminal 2: Start Player Client**
```bash
python player_client.py
```

**Play**
- Use `WASD` to move your player (P)
- Collect gold ($) to increase your score
- Compete against bots (B)
- Press `Q` to quit

## Files Overview

| File | Purpose |
|------|---------|
| `game_state.py` | Shared game logic and ZooKeeper serialization |
| `game_server.py` | Central game coordinator - runs game loop and AI |
| `player_client.py` | Human player interface |
| `test_distributed_game.py` | Comprehensive test suite |
| `ARCHITECTURE.md` | Detailed design document (required reading) |
| `requirements.txt` | Python dependencies |

## Testing

Run all tests:
```bash
python -m unittest test_distributed_game -v
```

Run specific test class:
```bash
python -m unittest test_distributed_game.TestGameState -v
```

## Game Rules

1. Players and bots spawn randomly on a 20x20 grid
2. Gold appears randomly on the map
3. Players move using WASD keys
4. Bots automatically move toward nearest gold
5. Collecting gold increases your score
6. The human player attempts to win against the bots

## Troubleshooting

### "Could not connect to ZooKeeper"
- Ensure ZooKeeper is running on localhost:2181
- Or specify custom host: `python player_client.py 192.168.1.x:2181`

### "Game server not found"
- Ensure game_server.py is running first
- Server needs 2-3 seconds to initialize

### Tests fail with connection error
- ZooKeeper must be running for tests to pass
- Some tests will be skipped if ZooKeeper is unavailable

## Notes

- This is a prototype implementation for educational purposes
- The game demonstrates distributed coordination using ZooKeeper