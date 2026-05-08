"""
Test suite for distributed gold mining game
Tests game state management, ZooKeeper integration, and fault tolerance
"""
import unittest
import time
import json
from kazoo.client import KazooClient
from game_state import GameState, spawn_positions, clamp_position, nearest_gold
from game_server import GameServer


class TestGameState(unittest.TestCase):
    """Test game state serialization and deserialization"""

    def test_game_state_to_json(self):
        """Test converting game state to JSON"""
        state = GameState()
        state.player_x = 5
        state.player_y = 10
        state.player_score = 3
        state.bots = {"bot_0": {"x": 2, "y": 3, "score": 1}}
        state.golds = [(1, 1), (5, 5)]

        json_data = state.to_json()
        self.assertIsInstance(json_data, bytes)

    def test_game_state_from_json(self):
        """Test loading game state from JSON"""
        state1 = GameState()
        state1.player_x = 5
        state1.player_y = 10
        state1.player_score = 3
        state1.bots = {"bot_0": {"x": 2, "y": 3, "score": 1}}
        state1.golds = [(1, 1), (5, 5)]

        json_data = state1.to_json()
        state2 = GameState.from_json(json_data)

        self.assertEqual(state2.player_x, 5)
        self.assertEqual(state2.player_y, 10)
        self.assertEqual(state2.player_score, 3)
        self.assertEqual(state2.bots["bot_0"]["x"], 2)


class TestGameLogic(unittest.TestCase):
    """Test game logic functions"""

    def test_spawn_positions_unique(self):
        """Test that spawn_positions returns unique positions"""
        positions = spawn_positions(5)
        self.assertEqual(len(positions), len(set(positions)))

    def test_spawn_positions_within_bounds(self):
        """Test that spawned positions are within game bounds"""
        positions = spawn_positions(10)
        from game_state import WIDTH, HEIGHT
        for x, y in positions:
            self.assertGreaterEqual(x, 0)
            self.assertLess(x, WIDTH)
            self.assertGreaterEqual(y, 0)
            self.assertLess(y, HEIGHT)

    def test_clamp_position(self):
        """Test position clamping"""
        x, y = clamp_position(-5, -10)
        self.assertEqual((x, y), (0, 0))

        from game_state import WIDTH, HEIGHT
        x, y = clamp_position(WIDTH + 5, HEIGHT + 10)
        self.assertEqual((x, y), (WIDTH - 1, HEIGHT - 1))

    def test_nearest_gold(self):
        """Test finding nearest gold"""
        golds = [(5, 5), (15, 15), (0, 0)]
        nearest = nearest_gold(4, 4, golds)
        self.assertEqual(nearest, (5, 5))


class TestGameServer(unittest.TestCase):
    """Test game server ZooKeeper integration"""

    @classmethod
    def setUpClass(cls):
        """Setup ZooKeeper client for tests"""
        cls.zk = KazooClient(hosts="127.0.0.1:2181")
        try:
            cls.zk.start()
            cls.zk_available = True
        except:
            cls.zk_available = False

    @classmethod
    def tearDownClass(cls):
        """Cleanup ZooKeeper connection"""
        if cls.zk_available and cls.zk.connected:
            cls.zk.stop()

    def setUp(self):
        """Setup test fixtures"""
        if not self.zk_available:
            self.skipTest("ZooKeeper not available")

    def test_zk_connection(self):
        """Test ZooKeeper connectivity"""
        self.assertTrue(self.zk.connected, "Could not connect to ZooKeeper")

    def test_game_state_persistence(self):
        """Test that game state is persisted to ZooKeeper"""
        game_root = "/test_game_state"
        if self.zk.exists(game_root):
            self.zk.delete(game_root, recursive=True)

        self.zk.create(game_root)

        # Create and save state
        state = GameState()
        state.player_x = 7
        state.player_y = 8
        state.golds = [(1, 1), (2, 2)]

        state_path = f"{game_root}/game_state"
        self.zk.create(state_path, state.to_json())

        # Load and verify
        data, _ = self.zk.get(state_path)
        loaded_state = GameState.from_json(data)

        self.assertEqual(loaded_state.player_x, 7)
        self.assertEqual(loaded_state.player_y, 8)
        self.assertEqual(len(loaded_state.golds), 2)

        # Cleanup
        self.zk.delete(game_root, recursive=True)

    def test_game_state_updates(self):
        """Test updating game state in ZooKeeper"""
        game_root = "/test_game_updates"
        if self.zk.exists(game_root):
            self.zk.delete(game_root, recursive=True)

        self.zk.create(game_root)
        state_path = f"{game_root}/game_state"

        # Initial state
        state1 = GameState()
        state1.player_x = 1
        self.zk.create(state_path, state1.to_json())

        # Update state
        state2 = GameState.from_json(self.zk.get(state_path)[0])
        state2.player_x = 10
        self.zk.set(state_path, state2.to_json())

        # Verify update
        state3 = GameState.from_json(self.zk.get(state_path)[0])
        self.assertEqual(state3.player_x, 10)

        # Cleanup
        self.zk.delete(game_root, recursive=True)


class TestDistributedConsistency(unittest.TestCase):
    """Test consistency with simulated delays and faults"""

    @classmethod
    def setUpClass(cls):
        """Setup ZooKeeper client"""
        cls.zk = KazooClient(hosts="127.0.0.1:2181")
        try:
            cls.zk.start()
            cls.zk_available = True
        except:
            cls.zk_available = False

    @classmethod
    def tearDownClass(cls):
        """Cleanup"""
        if cls.zk_available and cls.zk.connected:
            cls.zk.stop()

    def setUp(self):
        if not self.zk_available:
            self.skipTest("ZooKeeper not available")

    def test_simulated_lag(self):
        """Test with simulated network lag"""
        game_root = "/test_lag"
        if self.zk.exists(game_root):
            self.zk.delete(game_root, recursive=True)

        self.zk.create(game_root)
        state_path = f"{game_root}/game_state"

        state = GameState()
        state.player_score = 0
        self.zk.create(state_path, state.to_json())

        # Simulate multiple updates with delays
        for i in range(5):
            time.sleep(0.2)  # Simulated lag
            state = GameState.from_json(self.zk.get(state_path)[0])
            state.player_score += 1
            self.zk.set(state_path, state.to_json())

        final_state = GameState.from_json(self.zk.get(state_path)[0])
        self.assertEqual(final_state.player_score, 5)

        self.zk.delete(game_root, recursive=True)

    def test_state_consistency_multiple_reads(self):
        """Test state consistency with multiple rapid reads"""
        game_root = "/test_consistency"
        if self.zk.exists(game_root):
            self.zk.delete(game_root, recursive=True)

        self.zk.create(game_root)
        state_path = f"{game_root}/game_state"

        state = GameState()
        state.player_x = 5
        state.golds = [(1, 1), (2, 2), (3, 3)]
        self.zk.create(state_path, state.to_json())

        # Rapid reads should be consistent
        for _ in range(10):
            state_read = GameState.from_json(self.zk.get(state_path)[0])
            self.assertEqual(state_read.player_x, 5)
            self.assertEqual(len(state_read.golds), 3)

        self.zk.delete(game_root, recursive=True)


if __name__ == "__main__":
    unittest.main()
