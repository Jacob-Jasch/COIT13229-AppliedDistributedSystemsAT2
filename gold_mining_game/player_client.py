"""
Player Client - Distributed Gold Mining Game
Allows a human player to connect to the game server and play
"""
import time
from kazoo.client import KazooClient
from game_state import GameState, draw_board, clear_screen


class PlayerClient:
    def __init__(self, zk_hosts="127.0.0.1:2181"):
        self.zk = KazooClient(hosts=zk_hosts)
        self.zk.start()
        self.game_root = "/gold_mining_game"
        self.game_state_path = f"{self.game_root}/game_state"
        self.running = True

    def wait_for_game(self, timeout=10):
        """Wait for game server to be ready"""
        start = time.time()
        while not self.zk.exists(self.game_state_path) and (time.time() - start) < timeout:
            print(f"Waiting for game server... ({int(time.time() - start)}s)")
            time.sleep(1)
        if not self.zk.exists(self.game_state_path):
            raise Exception("Game server not found")
        print("Connected to game server!")

    def get_game_state(self):
        """Fetch current game state from ZooKeeper"""
        if self.zk.exists(self.game_state_path):
            data, _ = self.zk.get(self.game_state_path)
            return GameState.from_json(data)
        return None

    def send_move(self, move):
        """Send player move to game server"""
        move_path = f"{self.game_root}/player_move"
        if self.zk.exists(move_path):
            self.zk.set(move_path, move.encode('utf-8'))
        else:
            self.zk.create(move_path, move.encode('utf-8'))
    
    def request_reset(self):
        """Request game reset from server"""
        reset_path = f"{self.game_root}/reset_request"
        if self.zk.exists(reset_path):
            self.zk.set(reset_path, b"1")
        else:
            self.zk.create(reset_path, b"1")
        print("Reset requested...")

    def play(self):
        """Main game loop for player"""
        try:
            self.wait_for_game()
            print("\nGame started! Use WASD to move, Q to quit, R to reset")
            time.sleep(2)

            while self.running:
                clear_screen()
                state = self.get_game_state()
                if state:
                    draw_board(state)

                move = input("\nMove (WASD, Q to quit, R to reset): ").lower()

                if move == "q":
                    self.running = False
                    break
                
                if move == "r":
                    self.request_reset()
                    continue

                # Only send valid moves - invalid moves don't advance the game
                if move not in ["w", "a", "s", "d"]:
                    continue
                
                self.send_move(move)
                time.sleep(0.1)

        except KeyboardInterrupt:
            print("\nDisconnecting...")
        finally:
            self.cleanup()

    def cleanup(self):
        """Cleanup connections"""
        if self.zk.connected:
            self.zk.stop()


if __name__ == "__main__":
    import sys
    zk_host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1:2181"
    client = PlayerClient(zk_host)
    client.play()
