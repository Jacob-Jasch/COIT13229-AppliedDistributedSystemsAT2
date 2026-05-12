"""
Distributed system tests for the Gold Miner game.
"""

import unittest
import time
from kazoo.client import KazooClient

from game_state import GameState, spawn_positions, clamp_position, nearest_gold


ZK_HOSTS = "127.0.0.1:2181"


class TestBasicGameLogic(unittest.TestCase):
    def test_spawn_positions_unique(self):
        positions = spawn_positions(5)
        self.assertEqual(len(positions), len(set(positions)))

    def test_spawn_positions_within_bounds(self):
        positions = spawn_positions(10)

        from game_state import WIDTH, HEIGHT

        for x, y in positions:
            self.assertGreaterEqual(x, 0)
            self.assertLess(x, WIDTH)
            self.assertGreaterEqual(y, 0)
            self.assertLess(y, HEIGHT)

    def test_clamp_position(self):
        x, y = clamp_position(-5, -10)
        self.assertEqual((x, y), (0, 0))

        from game_state import WIDTH, HEIGHT

        x, y = clamp_position(WIDTH + 5, HEIGHT + 10)
        self.assertEqual((x, y), (WIDTH - 1, HEIGHT - 1))

    def test_nearest_gold(self):
        golds = [(5, 5), (15, 15), (0, 0)]
        nearest = nearest_gold(4, 4, golds)
        self.assertEqual(nearest, (5, 5))


class TestZooKeeperIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.zk = KazooClient(hosts=ZK_HOSTS)
        try:
            cls.zk.start(timeout=5)
            cls.zk_available = True
        except Exception:
            cls.zk_available = False

    @classmethod
    def tearDownClass(cls):
        if cls.zk_available:
            cls.zk.stop()
            cls.zk.close()

    def setUp(self):
        if not self.zk_available:
            self.skipTest("ZooKeeper is not available. Start ZooKeeper on 127.0.0.1:2181.")

    def safe_delete(self, path):
        if self.zk.exists(path):
            self.zk.delete(path, recursive=True)

    def test_zookeeper_connection(self):
        self.assertTrue(self.zk.connected)

    def test_game_state_persistence(self):
        game_root = "/test_game_state_persistence"
        self.safe_delete(game_root)

        self.zk.create(game_root)

        state = GameState()
        state.player_x = 7
        state.player_y = 8
        state.player_score = 2
        state.golds = [(1, 1), (2, 2)]

        state_path = f"{game_root}/game_state"
        self.zk.create(state_path, state.to_json())

        data, _ = self.zk.get(state_path)
        loaded_state = GameState.from_json(data)

        self.assertEqual(loaded_state.player_x, 7)
        self.assertEqual(loaded_state.player_y, 8)
        self.assertEqual(loaded_state.player_score, 2)
        self.assertEqual(len(loaded_state.golds), 2)

        self.safe_delete(game_root)

    def test_game_state_update(self):
        game_root = "/test_game_state_update"
        self.safe_delete(game_root)

        self.zk.create(game_root)

        state_path = f"{game_root}/game_state"

        state = GameState()
        state.player_x = 1
        state.player_y = 1
        self.zk.create(state_path, state.to_json())

        loaded_state = GameState.from_json(self.zk.get(state_path)[0])
        loaded_state.player_x = 10
        loaded_state.player_y = 12
        self.zk.set(state_path, loaded_state.to_json())

        updated_state = GameState.from_json(self.zk.get(state_path)[0])

        self.assertEqual(updated_state.player_x, 10)
        self.assertEqual(updated_state.player_y, 12)

        self.safe_delete(game_root)


class TestDistributedFaults(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.zk = KazooClient(hosts=ZK_HOSTS)
        try:
            cls.zk.start(timeout=5)
            cls.zk_available = True
        except Exception:
            cls.zk_available = False

    @classmethod
    def tearDownClass(cls):
        if cls.zk_available:
            cls.zk.stop()
            cls.zk.close()

    def setUp(self):
        if not self.zk_available:
            self.skipTest("ZooKeeper is not available. Start ZooKeeper on 127.0.0.1:2181.")

    def safe_delete(self, path):
        if self.zk.exists(path):
            self.zk.delete(path, recursive=True)

    def test_simulated_lag(self):
        game_root = "/test_simulated_lag"
        self.safe_delete(game_root)

        self.zk.create(game_root)
        state_path = f"{game_root}/game_state"

        state = GameState()
        state.player_score = 0
        self.zk.create(state_path, state.to_json())

        number_of_updates = 5

        for _ in range(number_of_updates):
            time.sleep(0.2)

            current_state = GameState.from_json(self.zk.get(state_path)[0])
            current_state.player_score += 1
            self.zk.set(state_path, current_state.to_json())

        final_state = GameState.from_json(self.zk.get(state_path)[0])

        self.assertEqual(final_state.player_score, number_of_updates)

        self.safe_delete(game_root)

    def test_simulated_lost_message(self):
        game_root = "/test_simulated_lost_message"
        self.safe_delete(game_root)

        self.zk.create(game_root)
        state_path = f"{game_root}/game_state"

        state = GameState()
        state.player_score = 0
        self.zk.create(state_path, state.to_json())

        current_state = GameState.from_json(self.zk.get(state_path)[0])
        current_state.player_score += 1
        self.zk.set(state_path, current_state.to_json())

        lost_update = GameState.from_json(self.zk.get(state_path)[0])
        lost_update.player_score += 1

        current_state = GameState.from_json(self.zk.get(state_path)[0])
        current_state.player_score += 1
        self.zk.set(state_path, current_state.to_json())

        final_state = GameState.from_json(self.zk.get(state_path)[0])

        self.assertEqual(final_state.player_score, 2)

        self.safe_delete(game_root)

    def test_node_crash_ephemeral_node_removed(self):
        game_root = "/test_node_crash"
        bot_path = f"{game_root}/bot_1"

        self.safe_delete(game_root)
        self.zk.create(game_root)

        bot_zk = KazooClient(hosts=ZK_HOSTS)
        bot_zk.start(timeout=5)

        try:
            bot_zk.create(bot_path, b"active", ephemeral=True)

            self.assertIsNotNone(self.zk.exists(bot_path))

            bot_zk.stop()
            bot_zk.close()

            time.sleep(2)

            self.assertIsNone(self.zk.exists(bot_path))

        finally:
            if bot_zk.connected:
                bot_zk.stop()
                bot_zk.close()

            self.safe_delete(game_root)

    def test_eventual_consistency_after_delayed_update(self):
        game_root = "/test_eventual_consistency"
        self.safe_delete(game_root)

        self.zk.create(game_root)
        state_path = f"{game_root}/game_state"

        initial_state = GameState()
        initial_state.player_x = 1
        initial_state.player_y = 1
        self.zk.create(state_path, initial_state.to_json())

        old_read = GameState.from_json(self.zk.get(state_path)[0])
        self.assertEqual(old_read.player_x, 1)
        self.assertEqual(old_read.player_y, 1)

        time.sleep(0.5)

        updated_state = GameState.from_json(self.zk.get(state_path)[0])
        updated_state.player_x = 9
        updated_state.player_y = 9
        self.zk.set(state_path, updated_state.to_json())

        final_read = GameState.from_json(self.zk.get(state_path)[0])

        self.assertEqual(final_read.player_x, 9)
        self.assertEqual(final_read.player_y, 9)

        self.safe_delete(game_root)


if __name__ == "__main__":
    unittest.main(verbosity=2)