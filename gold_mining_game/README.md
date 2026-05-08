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

### Test Coverage
- ✓ Game state serialization
- ✓ ZooKeeper integration
- ✓ Game logic (clamping, spawning, nearest gold)
- ✓ Distributed consistency with simulated lag
- ✓ State persistence

## Distributed Deployment

To run players on different machines:

**Machine A (ZooKeeper + Game Server)**
```bash
docker run -d -p 2181:2181 zookeeper
python game_server.py
```

**Machine B (Player Client)**
```bash
python player_client.py <MACHINE_A_IP>:2181
```

**Machine C (Another Player)**
```bash
python player_client.py <MACHINE_A_IP>:2181
```

## Design Highlights

- **Consistency Model**: Eventual Consistency via ZooKeeper
- **Coordination**: ZooKeeper znodes store game state
- **Scalability**: Supports multiple concurrent players
- **Fault Tolerance**: Handles network delays, client disconnections
- **Simple Architecture**: Centralized server with polling clients

See `ARCHITECTURE.md` for complete design documentation including component diagrams, 
consistency model rationale, class hierarchies, and interaction sequences. This content 
can be incorporated into your report.docx file.

## Game Rules

1. Players and bots spawn randomly on a 20x20 grid
2. Gold appears randomly on the map
3. Players move using WASD keys
4. Bots automatically move toward nearest gold
5. Collecting gold increases your score
6. The human player attempts to outcompete the bots

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
- All components are intentionally kept simple and readable
- See ARCHITECTURE.md for design rationale and consistency model details
