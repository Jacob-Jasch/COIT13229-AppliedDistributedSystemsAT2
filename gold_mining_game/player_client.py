"""Human player client for Gold Miner."""

import json
import time

from kazoo.client import KazooClient
from kazoo.exceptions import NoNodeError, NodeExistsError

from game_state import GameState, WAITING_FOR_PLAYER, clear_screen, draw_board


class PlayerClient:
    def __init__(self, zk_hosts="127.0.0.1:2181", game_root="/gold_mining_game"):
        self.zk = KazooClient(hosts=zk_hosts)
        self.zk.start(timeout=5)
        self.game_root = game_root
        self.state_path = f"{game_root}/game_state"
        self.player_move_path = f"{game_root}/moves/player"
        self.member_path = f"{game_root}/members/player"
        self.running = True

    def wait_for_game(self, timeout=10):
        start = time.time()
        while not self.zk.exists(self.state_path) and time.time() - start < timeout:
            print("Waiting for game server...")
            time.sleep(1)
        if not self.zk.exists(self.state_path):
            raise RuntimeError("Game server not found")
        self._register()
        print("Connected to game server!")

    def _register(self):
        try:
            self.zk.create(self.member_path, b"active", ephemeral=True, makepath=True)
        except NodeExistsError:
            self.zk.delete(self.member_path)
            self.zk.create(self.member_path, b"active", ephemeral=True, makepath=True)

    def get_game_state(self):
        if not self.zk.exists(self.state_path):
            return None
        data, _ = self.zk.get(self.state_path)
        return GameState.from_json(data)

    def _write_move(self, path, move, turn):
        data = json.dumps({"turn": turn, "move": move}).encode("utf-8")
        try:
            self.zk.create(path, data, makepath=True)
        except NodeExistsError:
            self.zk.set(path, data)
        except NoNodeError:
            self.zk.ensure_path(path.rsplit("/", 1)[0])
            self.zk.create(path, data)

    def send_move(self, move, turn=None):
        if move not in {"w", "a", "s", "d"}:
            return False
        if turn is None:
            state = self.get_game_state()
            if not state:
                return False
            turn = state.turn
        self._write_move(self.player_move_path, move, turn)
        return True

    def wait_for_turn_to_finish(self, previous_turn, timeout=5):
        start = time.time()
        while time.time() - start < timeout:
            state = self.get_game_state()
            if state and state.turn > previous_turn and state.phase == WAITING_FOR_PLAYER:
                return state
            time.sleep(0.1)
        return self.get_game_state()

    def request_reset(self):
        path = f"{self.game_root}/reset_request"
        try:
            self.zk.create(path, b"1", makepath=True)
        except NodeExistsError:
            self.zk.set(path, b"1")

    def play(self):
        try:
            self.wait_for_game()
            print("\nUse W/A/S/D to move, R to reset, Q to quit.")
            print("Turn-based mode: after you move, bots take one move, then the next turn begins.")

            while self.running:
                clear_screen()
                state = self.get_game_state()
                if state:
                    draw_board(state)

                move = input("\nMove: ").lower().strip()
                if move == "q":
                    break
                if move == "r":
                    self.request_reset()
                    time.sleep(0.2)
                    continue

                if state and self.send_move(move, state.turn):
                    print("Waiting for bots to take their turn...")
                    self.wait_for_turn_to_finish(state.turn)
        except KeyboardInterrupt:
            print("\nDisconnecting...")
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
    PlayerClient(zk_host).play()
