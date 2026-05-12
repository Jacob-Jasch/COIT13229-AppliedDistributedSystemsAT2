"""Quick startup test for the turn-based distributed Gold Miner game."""

import threading
import time

from bot_client import BotClient
from game_server import GameServer
from player_client import PlayerClient


def run_in_thread(target):
    thread = threading.Thread(target=target)
    thread.start()
    return thread


def test_game_startup():
    print("=" * 60)
    print("STARTUP TEST")
    print("=" * 60)

    root = "/gold_mining_game_startup_test"
    server = GameServer(game_root=root, bot_timeout_seconds=2.0)
    server_thread = run_in_thread(lambda: server.run(duration_seconds=10))

    bots = [BotClient(f"bot_{i}", game_root=root) for i in range(3)]
    bot_threads = [run_in_thread(bot.play) for bot in bots]

    client = PlayerClient(game_root=root)

    try:
        time.sleep(1)
        client.wait_for_game(timeout=5)
        print("Player client connected")

        state = client.get_game_state()
        print("Initial state:")
        print(f"- Turn: {state.turn}")
        print(f"- Player position: ({state.player_x}, {state.player_y})")
        print(f"- Player score: {state.player_score}")
        print(f"- Bots connected so far: {len(state.bots)}")
        print(f"- Gold locations: {len(state.golds)}")

        client.send_move("w", state.turn)
        print("Player move sent; waiting for bots and next turn")
        updated = client.wait_for_turn_to_finish(state.turn, timeout=5)

        print("Updated state:")
        print(f"- Turn: {updated.turn}")
        print(f"- Player position: ({updated.player_x}, {updated.player_y})")
        print(f"- Player score: {updated.player_score}")
        print(f"- Bots: {len(updated.bots)}")
        print(f"- Gold locations: {len(updated.golds)}")
        for bot_id, bot_data in sorted(updated.bots.items()):
            print(f"- {bot_id}: position ({bot_data['x']}, {bot_data['y']}), score {bot_data['score']}")

        if updated.turn >= 1 and len(updated.bots) >= 3 and len(updated.golds) == 5:
            print("\nPASSED")
        else:
            print("\nFAILED: expected next turn, 3 bots, and 5 gold positions")
    finally:
        client.cleanup()
        for bot in bots:
            bot.cleanup()
        server.cleanup()

        for thread in bot_threads:
            thread.join(timeout=2)
        server_thread.join(timeout=2)


if __name__ == "__main__":
    test_game_startup()
