import json
import random
import time

from kazoo.client import KazooClient
from kazoo.exceptions import KazooException, NoNodeError, NodeExistsError

from game_state import WAITING_FOR_BOTS, GameState, nearest_gold


class BotClient:
    def __init__(self, bot_id, zk_hosts="127.0.0.1:2181", game_root="/gold_mining_game"):
        self.bot_id = bot_id
        self.zk = KazooClient(hosts=zk_hosts)
        self.zk.start(timeout=5)
        self.game_root = game_root
        self.state_path = f"{game_root}/game_state"
        self.move_path = f"{game_root}/moves/bots/{bot_id}"
        self.member_path = f"{game_root}/members/{bot_id}"
        self.running = True
        self.last_turn_sent = -1

    def wait_for_game(self, timeout=10):
        start = time.time()
        while not self.zk.exists(self.state_path) and time.time() - start < timeout:
            print(f"Bot {self.bot_id}: waiting for game server...")
            time.sleep(1)
        if not self.zk.exists(self.state_path):
            raise RuntimeError("Game server not found")
        self._register()
        print(f"Bot {self.bot_id}: connected")

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

    def choose_move(self, state):
        if self.bot_id not in state.bots:
            return random.choice(["w", "a", "s", "d"])

        bot = state.bots[self.bot_id]
        target = nearest_gold(bot["x"], bot["y"], state.golds)
        if not target:
            return random.choice(["w", "a", "s", "d"])

        dx = target[0] - bot["x"]
        dy = target[1] - bot["y"]

        if dx == 0 and dy == 0:
            return random.choice(["w", "a", "s", "d"])
        if abs(dx) > abs(dy):
            return "d" if dx > 0 else "a"
        if abs(dy) > abs(dx):
            return "s" if dy > 0 else "w"
        return random.choice(["d" if dx > 0 else "a", "s" if dy > 0 else "w"])

    def send_move(self, move, turn):
        data = json.dumps({"turn": turn, "move": move}).encode("utf-8")
        try:
            self.zk.create(self.move_path, data, makepath=True)
        except NodeExistsError:
            self.zk.set(self.move_path, data)
        except NoNodeError:
            self.zk.ensure_path(self.move_path.rsplit("/", 1)[0])
            self.zk.create(self.move_path, data)

    def play(self):
        try:
            self.wait_for_game()
            while self.running:
                state = self.get_game_state()

                if state and state.phase == WAITING_FOR_BOTS and state.turn != self.last_turn_sent:
                    self.send_move(self.choose_move(state), state.turn)
                    self.last_turn_sent = state.turn

                time.sleep(0.1)
        except KazooException as exc:
            if self.running:
                print(f"Bot {self.bot_id} ZooKeeper error: {exc}")
        except KeyboardInterrupt:
            pass
        finally:
            self.cleanup()

    def cleanup(self):
        self.running = False
        if self.zk.connected:
            self.zk.stop()
        self.zk.close()


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python bot_client.py <bot_id> [zk_host]")
        raise SystemExit(1)

    zk_host = sys.argv[2] if len(sys.argv) > 2 else "127.0.0.1:2181"
    BotClient(sys.argv[1], zk_host).play()
