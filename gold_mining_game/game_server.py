import json
import random
import time

from kazoo.client import KazooClient
from kazoo.exceptions import KazooException, NoNodeError

from game_state import (
    NUM_GOLD,
    VALID_MOVES,
    WAITING_FOR_BOTS,
    WAITING_FOR_PLAYER,
    GameState,
    clamp_position,
    occupied_positions,
    spawn_positions,
)


class GameServer:
    def __init__(self, zk_hosts="127.0.0.1:2181", game_root="/gold_mining_game", bot_timeout_seconds=2.0):
        self.zk = KazooClient(hosts=zk_hosts)
        self.zk.start(timeout=5)
        self.game_root = game_root
        self.state_path = f"{game_root}/game_state"
        self.moves_path = f"{game_root}/moves"
        self.player_move_path = f"{self.moves_path}/player"
        self.bot_moves_path = f"{self.moves_path}/bots"
        self.members_path = f"{game_root}/members"
        self.reset_path = f"{game_root}/reset_request"
        self.bot_timeout_seconds = bot_timeout_seconds
        self.running = True
        self.state = GameState()
        self._setup_zookeeper()
        self.reset_game()

    def _setup_zookeeper(self):
        if self.zk.exists(self.game_root):
            self.zk.delete(self.game_root, recursive=True)
        self.zk.ensure_path(self.bot_moves_path)
        self.zk.ensure_path(self.members_path)

    def reset_game(self):
        self.state = GameState()
        self.state.player_x, self.state.player_y = spawn_positions(1)[0]
        self.state.golds = spawn_positions(NUM_GOLD, exclude=occupied_positions(self.state, include_gold=False))
        self._save_state()

    def _save_state(self):
        data = self.state.to_json()
        if self.zk.exists(self.state_path):
            self.zk.set(self.state_path, data)
        else:
            self.zk.create(self.state_path, data, makepath=True)

    def _move_payload(self, move, turn):
        return json.dumps({"turn": turn, "move": move}).encode("utf-8")

    def _parse_move_payload(self, data):
        text = data.decode("utf-8")
        try:
            payload = json.loads(text)
            turn = payload.get("turn")
            move = payload.get("move")
        except json.JSONDecodeError:
            turn = self.state.turn
            move = text
        if move not in VALID_MOVES:
            return None, None
        return turn, move

    def _read_and_delete_move_for_turn(self, path, turn):
        try:
            data, _ = self.zk.get(path)
            self.zk.delete(path)
            move_turn, move = self._parse_move_payload(data)
            return move if move_turn == turn else None
        except NoNodeError:
            return None

    def _read_player_move(self):
        return self._read_and_delete_move_for_turn(self.player_move_path, self.state.turn)

    def _read_bot_moves(self, expected_bots):
        moves = {}
        for bot_id in expected_bots:
            move = self._read_and_delete_move_for_turn(f"{self.bot_moves_path}/{bot_id}", self.state.turn)
            if move:
                moves[bot_id] = move
        return moves

    def _clear_bot_moves(self):
        try:
            for child in self.zk.get_children(self.bot_moves_path):
                path = f"{self.bot_moves_path}/{child}"
                if self.zk.exists(path):
                    self.zk.delete(path)
        except KazooException:
            if self.running:
                raise

    def _active_bots(self):
        try:
            return sorted(child for child in self.zk.get_children(self.members_path) if child != "player")
        except KazooException:
            if self.running:
                raise
            return []

    def _sync_bot_members(self):
        active = set(self._active_bots())
        changed = False

        for bot_id in active:
            if bot_id not in self.state.bots:
                self._spawn_bot_if_needed(bot_id)
                changed = True

        for bot_id in list(self.state.bots):
            if bot_id not in active:
                del self.state.bots[bot_id]
                changed = True

        return sorted(active), changed

    def _spawn_bot_if_needed(self, bot_id):
        if bot_id in self.state.bots:
            return
        x, y = spawn_positions(1, exclude=occupied_positions(self.state))[0]
        self.state.bots[bot_id] = {"x": x, "y": y, "score": 0}

    def _spawn_gold(self):
        return spawn_positions(1, exclude=occupied_positions(self.state))[0]

    def _apply_move(self, participant_id, move):
        dx, dy = VALID_MOVES[move]

        if participant_id == "player":
            self.state.player_x, self.state.player_y = clamp_position(
                self.state.player_x + dx,
                self.state.player_y + dy,
            )
            self._collect_gold("player")
            return

        if participant_id not in self.state.bots:
            return
        bot = self.state.bots[participant_id]
        bot["x"], bot["y"] = clamp_position(bot["x"] + dx, bot["y"] + dy)
        self._collect_gold(participant_id)

    def _collect_gold(self, participant_id):
        if participant_id == "player":
            x, y = self.state.player_x, self.state.player_y
        else:
            bot = self.state.bots[participant_id]
            x, y = bot["x"], bot["y"]

        position = (x, y)
        if position not in self.state.golds:
            return

        self.state.golds.remove(position)
        if participant_id == "player":
            self.state.player_score += 1
        else:
            self.state.bots[participant_id]["score"] += 1

        self.state.golds.append(self._spawn_gold())

    def _reset_requested(self):
        if not self.zk.exists(self.reset_path):
            return False
        self.zk.delete(self.reset_path)
        return True

    def _wait_for_bot_moves(self, expected_bots):
        if not expected_bots:
            return {}

        deadline = time.time() + self.bot_timeout_seconds
        moves = {}

        while self.running and time.time() < deadline and len(moves) < len(expected_bots):
            moves.update(self._read_bot_moves(expected_bots))
            if len(moves) < len(expected_bots):
                time.sleep(0.05)

        self._clear_bot_moves()
        return moves

    def _play_one_turn(self, player_move):
        self._sync_bot_members()
        self._apply_move("player", player_move)

        self.state.phase = WAITING_FOR_BOTS
        self._save_state()

        expected_bots, _ = self._sync_bot_members()
        bot_moves = self._wait_for_bot_moves(expected_bots)
        for bot_id, move in sorted(bot_moves.items()):
            self._apply_move(bot_id, move)

        self.state.turn += 1
        self.state.phase = WAITING_FOR_PLAYER
        self._save_state()

    def run(self, duration_seconds=300):
        print("Game Server started. Waiting for player turns and bot turns...")
        start = time.time()

        try:
            while self.running and time.time() - start < duration_seconds:
                if self._reset_requested():
                    self.reset_game()

                _, changed = self._sync_bot_members()
                if changed:
                    self._save_state()

                player_move = self._read_player_move()
                if player_move:
                    self._play_one_turn(player_move)
                else:
                    time.sleep(0.05)
        except KeyboardInterrupt:
            print("\nServer shutting down...")
        except KazooException as exc:
            if self.running:
                print(f"ZooKeeper error: {exc}")
        finally:
            self.cleanup()

    def cleanup(self):
        self.running = False
        if self.zk.connected:
            self.zk.stop()
        self.zk.close()


if __name__ == "__main__":
    import sys

    zk_host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1:2181"
    GameServer(zk_host).run()
