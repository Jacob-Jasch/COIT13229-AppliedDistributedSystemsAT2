import json
import os
import random

WIDTH = 20
HEIGHT = 20
NUM_GOLD = 5
VALID_MOVES = {"w": (0, -1), "a": (-1, 0), "s": (0, 1), "d": (1, 0)}

WAITING_FOR_PLAYER = "waiting_for_player"
WAITING_FOR_BOTS = "waiting_for_bots"

RESET = "\033[0m"
GOLD = "\033[33m"
PLAYER = "\033[32m"
BOT = "\033[31m"
COLLISION = "\033[35m"


class GameState:

    def __init__(self):
        self.turn = 0
        self.phase = WAITING_FOR_PLAYER
        self.player_x = 0
        self.player_y = 0
        self.player_score = 0
        self.bots = {}      # bot_id -> {"x": int, "y": int, "score": int}
        self.golds = []     # list of (x, y) positions

    def to_dict(self):
        return {
            "turn": self.turn,
            "phase": self.phase,
            "player": {
                "x": self.player_x,
                "y": self.player_y,
                "score": self.player_score,
            },
            "bots": self.bots,
            "golds": self.golds,
        }

    def from_dict(self, data):
        self.turn = data.get("turn", 0)
        self.phase = data.get("phase", WAITING_FOR_PLAYER)
        player = data.get("player", {})
        self.player_x = player.get("x", 0)
        self.player_y = player.get("y", 0)
        self.player_score = player.get("score", 0)
        self.bots = data.get("bots", {})
        self.golds = [tuple(pos) for pos in data.get("golds", [])]

    def to_json(self):
        return json.dumps(self.to_dict()).encode("utf-8")

    @staticmethod
    def from_json(data):
        state = GameState()
        state.from_dict(json.loads(data.decode("utf-8")))
        return state


def clamp_position(x, y, width=WIDTH, height=HEIGHT):
    return max(0, min(width - 1, x)), max(0, min(height - 1, y))


def spawn_positions(count, width=WIDTH, height=HEIGHT, exclude=None):
    excluded = set(exclude or [])
    max_positions = width * height
    if count + len(excluded) > max_positions:
        raise ValueError("Not enough free board spaces to spawn positions")

    positions = set()
    while len(positions) < count:
        pos = (random.randint(0, width - 1), random.randint(0, height - 1))
        if pos not in excluded and pos not in positions:
            positions.add(pos)
    return list(positions)


def occupied_positions(state, include_gold=True):
    occupied = {(state.player_x, state.player_y)}
    occupied.update((bot["x"], bot["y"]) for bot in state.bots.values())
    if include_gold:
        occupied.update(state.golds)
    return occupied


def nearest_gold(x, y, golds):
    if not golds:
        return None
    return min(golds, key=lambda g: abs(g[0] - x) + abs(g[1] - y))


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def draw_board(state):
    grid = [["." for _ in range(WIDTH)] for _ in range(HEIGHT)]

    for gx, gy in state.golds:
        if 0 <= gx < WIDTH and 0 <= gy < HEIGHT:
            grid[gy][gx] = GOLD + "$" + RESET

    for bot_data in state.bots.values():
        bx, by = bot_data["x"], bot_data["y"]
        if 0 <= bx < WIDTH and 0 <= by < HEIGHT:
            if grid[by][bx] != ".":
                grid[by][bx] = COLLISION + "*" + RESET
            else:
                grid[by][bx] = BOT + "B" + RESET

    if 0 <= state.player_x < WIDTH and 0 <= state.player_y < HEIGHT:
        if grid[state.player_y][state.player_x] != ".":
            grid[state.player_y][state.player_x] = COLLISION + "*" + RESET
        else:
            grid[state.player_y][state.player_x] = PLAYER + "P" + RESET

    for row in grid:
        print(" ".join(row))

    print(f"\nTurn: {state.turn} ({state.phase})")
    print(f"Player score: {state.player_score}")
    for bot_id, bot_data in sorted(state.bots.items()):
        print(f"{bot_id} score: {bot_data['score']}")
    print("\nPress Q to quit the game, or R to reset.")
