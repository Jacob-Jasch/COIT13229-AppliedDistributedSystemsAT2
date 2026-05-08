"""
Shared game state and utilities for distributed gold mining game using ZooKeeper
"""
import json
import random

WIDTH = 20
HEIGHT = 20
NUM_BOTS = 3
NUM_GOLD = 5

# ANSI colors
RESET = "\033[0m"
GOLD = "\033[33m"
PLAYER = "\033[32m"
BOT = "\033[31m"


class GameState:
    """Manages game state data"""
    def __init__(self):
        self.player_x = 0
        self.player_y = 0
        self.player_score = 0
        self.bots = {}  # bot_id: {x, y, score}
        self.golds = []  # [(x, y), ...]

    def to_dict(self):
        return {
            "player": {"x": self.player_x, "y": self.player_y, "score": self.player_score},
            "bots": self.bots,
            "golds": self.golds
        }

    def from_dict(self, data):
        self.player_x = data["player"]["x"]
        self.player_y = data["player"]["y"]
        self.player_score = data["player"]["score"]
        self.bots = data["bots"]
        self.golds = data["golds"]

    def to_json(self):
        return json.dumps(self.to_dict()).encode('utf-8')

    @staticmethod
    def from_json(data):
        gs = GameState()
        gs.from_dict(json.loads(data.decode('utf-8')))
        return gs


def spawn_positions(count, width=WIDTH, height=HEIGHT):
    """Spawn unique random positions"""
    positions = set()
    while len(positions) < count:
        positions.add((random.randint(0, width-1), random.randint(0, height-1)))
    return list(positions)


def clamp_position(x, y, width=WIDTH, height=HEIGHT):
    """Clamp position to game bounds"""
    return max(0, min(width - 1, x)), max(0, min(height - 1, y))


def draw_board(state):
    """Draw the game board"""
    grid = [["." for _ in range(WIDTH)] for _ in range(HEIGHT)]

    for gx, gy in state.golds:
        if 0 <= gx < WIDTH and 0 <= gy < HEIGHT:
            grid[gy][gx] = GOLD + "$" + RESET

    for bot_id, bot_data in state.bots.items():
        bx, by = bot_data["x"], bot_data["y"]
        if 0 <= bx < WIDTH and 0 <= by < HEIGHT:
            grid[by][bx] = BOT + "B" + RESET

    if 0 <= state.player_x < WIDTH and 0 <= state.player_y < HEIGHT:
        grid[state.player_y][state.player_x] = PLAYER + "P" + RESET

    for row in grid:
        print(" ".join(row))

    print(f"\nPlayer Score: {state.player_score}")
    for bot_id, bot_data in state.bots.items():
        print(f"Bot {bot_id} Score: {bot_data['score']}")


def nearest_gold(x, y, golds):
    """Find nearest gold to position"""
    if not golds:
        return None
    return min(golds, key=lambda g: abs(g[0] - x) + abs(g[1] - y))


def clear_screen():
    """Clear terminal screen"""
    import os
    os.system("cls" if os.name == "nt" else "clear")
