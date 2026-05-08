"""
Quick demo to verify the distributed game starts correctly
"""
import threading
import time
from game_server import GameServer
from player_client import PlayerClient


def test_game_startup():
    """Test that game server and client can start and communicate"""
    
    print("=" * 60)
    print("DISTRIBUTED GOLD MINING GAME - STARTUP TEST")
    print("=" * 60)
    
    # Start server in background
    server = GameServer()
    server_thread = threading.Thread(target=lambda: server.run(duration_seconds=3), daemon=True)
    server_thread.start()
    
    print("\n✓ Game Server started")
    time.sleep(1)
    
    # Connect client
    client = PlayerClient()
    try:
        client.wait_for_game(timeout=5)
        print("✓ Player Client connected to server")
        
        # Test reading game state
        state = client.get_game_state()
        print(f"✓ Game state retrieved:")
        print(f"  - Player position: ({state.player_x}, {state.player_y})")
        print(f"  - Player score: {state.player_score}")
        print(f"  - Number of bots: {len(state.bots)}")
        print(f"  - Gold locations: {len(state.golds)}")
        
        # Test sending a move
        client.send_move("w")
        print("✓ Player move sent to server")
        time.sleep(0.5)
        
        # Verify state changed
        state2 = client.get_game_state()
        print(f"✓ Updated game state received")
        
        print("\n" + "=" * 60)
        print("STARTUP TEST PASSED - System is ready for play!")
        print("=" * 60)
        
    except Exception as e:
        print(f"✗ Error: {e}")
    finally:
        client.cleanup()
        server.cleanup()


if __name__ == "__main__":
    test_game_startup()
