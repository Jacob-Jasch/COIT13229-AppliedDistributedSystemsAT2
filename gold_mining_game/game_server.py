"""
Distributed Game Server using ZooKeeper
Coordinates game state and updates for all connected players and bots
"""
import time
import random
from kazoo.client import KazooClient
from game_state import GameState, spawn_positions, clamp_position, draw_board, clear_screen
from game_state import WIDTH, HEIGHT, NUM_BOTS, NUM_GOLD


class GameServer:
    def __init__(self, zk_hosts="127.0.0.1:2181"):
        self.zk = KazooClient(hosts=zk_hosts)
        self.zk.start()
        self.game_root = "/gold_mining_game"
        self._init_zk_structure()
        self.state = GameState()
        self._init_game_state()
        self.running = True

    def _init_zk_structure(self):
        """Initialize ZooKeeper node structure"""
        # Create root path
        if not self.zk.exists(self.game_root):
            self.zk.create(self.game_root)

        # Create game state path
        game_state_path = f"{self.game_root}/game_state"
        if self.zk.exists(game_state_path):
            self.zk.delete(game_state_path)
        self.zk.create(game_state_path)

    def _init_game_state(self):
        """Initialize game state"""
        pos = spawn_positions(1)[0]
        self.state.player_x = pos[0]
        self.state.player_y = pos[1]
        self.state.player_score = 0

        # Initialize bots
        bot_positions = spawn_positions(NUM_BOTS)
        for i, (bx, by) in enumerate(bot_positions):
            self.state.bots[f"bot_{i}"] = {"x": bx, "y": by, "score": 0}

        # Initialize gold
        self.state.golds = spawn_positions(NUM_GOLD)

        self._save_state()
    
    def reset_game(self):
        """Reset game state - clear scores and respawn all entities"""
        self._init_game_state()

    def _save_state(self):
        """Save current game state to ZooKeeper"""
        state_data = self.state.to_json()
        state_path = f"{self.game_root}/game_state"
        if self.zk.exists(state_path):
            self.zk.set(state_path, state_data)
        else:
            self.zk.create(state_path, state_data)

    def _load_state(self):
        """Load game state from ZooKeeper"""
        state_path = f"{self.game_root}/game_state"
        data, _ = self.zk.get(state_path)
        self.state = GameState.from_json(data)

    def _check_reset_request(self):
        """Check if player requested game reset"""
        reset_path = f"{self.game_root}/reset_request"
        if self.zk.exists(reset_path):
            self.zk.delete(reset_path)
            return True
        return False

    def _get_player_move(self):
        """Get pending player move from ZooKeeper"""
        move_path = f"{self.game_root}/player_move"
        if self.zk.exists(move_path):
            data, _ = self.zk.get(move_path)
            try:
                move = data.decode('utf-8')
                self.zk.delete(move_path)
                return move
            except:
                return None
        return None

    def _apply_player_move(self, move):
        """Apply player movement"""
        dx, dy = 0, 0
        if move == "w":
            dy = -1
        elif move == "s":
            dy = 1
        elif move == "a":
            dx = -1
        elif move == "d":
            dx = 1
        else:
            return

        self.state.player_x, self.state.player_y = clamp_position(
            self.state.player_x + dx, self.state.player_y + dy
        )
        self._check_gold_collected("player")

    def _check_gold_collected(self, entity_type, bot_id=None):
        """Check if entity collected gold"""
        if entity_type == "player":
            x, y = self.state.player_x, self.state.player_y
        else:
            x, y = self.state.bots[bot_id]["x"], self.state.bots[bot_id]["y"]

        if (x, y) in self.state.golds:
            self.state.golds.remove((x, y))
            if entity_type == "player":
                self.state.player_score += 1
            else:
                self.state.bots[bot_id]["score"] += 1
            # Spawn new gold
            self.state.golds.append((random.randint(0, WIDTH-1), random.randint(0, HEIGHT-1)))

    def _move_bots(self):
        """Move all bots toward nearest gold"""
        for bot_id, bot_data in self.state.bots.items():
            target = self._nearest_gold(bot_data["x"], bot_data["y"])
            if target:
                dx = target[0] - bot_data["x"]
                dy = target[1] - bot_data["y"]

                if abs(dx) > abs(dy):
                    bot_data["x"] += 1 if dx > 0 else -1
                elif abs(dy) > abs(dx):
                    bot_data["y"] += 1 if dy > 0 else -1
                else:
                    if random.random() < 0.5:
                        bot_data["x"] += 1 if dx > 0 else -1
                    else:
                        bot_data["y"] += 1 if dy > 0 else -1

                bot_data["x"], bot_data["y"] = clamp_position(bot_data["x"], bot_data["y"])
                self._check_gold_collected("bot", bot_id)

    def _nearest_gold(self, x, y):
        """Find nearest gold"""
        if not self.state.golds:
            return None
        return min(self.state.golds, key=lambda g: abs(g[0] - x) + abs(g[1] - y))

    def run(self, duration_seconds=300):
        """Run the game server"""
        print("Game Server started. Waiting for players to connect...")
        start_time = time.time()

        try:
            while self.running and (time.time() - start_time) < duration_seconds:
                # Check for reset request
                if self._check_reset_request():
                    print("Game reset requested")
                    self.reset_game()

                # Check for player move
                move = self._get_player_move()
                if move:
                    self._apply_player_move(move)
                    # Only move bots when player makes a valid move
                    self._move_bots()
                    # Save state
                    self._save_state()
                else:
                    # Small delay when no move
                    time.sleep(0.05)

        except KeyboardInterrupt:
            print("\nServer shutting down...")
        finally:
            self.cleanup()

    def cleanup(self):
        """Cleanup ZooKeeper connections"""
        if self.zk.connected:
            self.zk.stop()


if __name__ == "__main__":
    import sys
    zk_host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1:2181"
    server = GameServer(zk_host)
    server.run()
