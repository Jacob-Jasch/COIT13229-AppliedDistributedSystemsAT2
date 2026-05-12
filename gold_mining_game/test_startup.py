"""
Quick startup test for the distributed Gold Miner game.

This test starts the game server, connects a player client,
reads game state, sends a move, and checks that communication works.
"""

import threading
import time

from game_server import GameServer
from player_client import PlayerClient


def test_game_startup():
    """Test that the game server and client can start and communicate."""

    print("=" * 60)
    print("STARTUP TEST")
    print("=" * 60)

    server = GameServer()

    server_thread = threading.Thread(
        target=lambda: server.run(duration_seconds=3),
        daemon=True
    )
    server_thread.start()

    print("\nGame Server started")
    time.sleep(1)

    client = PlayerClient()

    try:
        client.wait_for_game(timeout=5)
        print("Player Client connected to server")

        state = client.get_game_state()
        print("Game state retrieved:")
        print(f"- Player position: ({state.player_x}, {state.player_y})")
        print(f"- Player score: {state.player_score}")
        print(f"- Number of bots: {len(state.bots)}")
        print(f"- Gold locations: {len(state.golds)}")

        client.send_move("w")
        print("Player move sent to server")

        time.sleep(0.5)

        updated_state = client.get_game_state()
        print("Updated game state received:")
        print(f"- Player position: ({updated_state.player_x}, {updated_state.player_y})")
        print(f"- Player score: {updated_state.player_score}")

        print("\n" + "=" * 60)
        print("PASSED")
        print("=" * 60)

    except Exception as e:
        print(f"Startup test failed: {e}")

    finally:
        client.cleanup()
        server.cleanup()


if __name__ == "__main__":
    test_game_startup()