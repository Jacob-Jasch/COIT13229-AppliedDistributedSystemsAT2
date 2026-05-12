# Gold Miner Distributed Prototype

Small Python/ZooKeeper prototype for the COIT13229 AT2.

## Files

- `game_state.py` - shared game state, board drawing, and helper functions.
- `game_server.py` - authoritative turn-based server that processes moves and updates game state.
- `player_client.py` - human client that sends player moves.
- `bot_client.py` - autonomous bot client that waits for the bot phase before sending one move.
- `test_startup.py` - quick startup test.
- `test_distributed_game.py` - distributed system tests.

## Setup

Install requirements:

```bash
pip install -r requirements.txt
```

Start ZooKeeper on `127.0.0.1:2181` before running the game or tests.

## Run

On Windows:

```bat
start.bat
```

## Test

```bat
test.bat
```