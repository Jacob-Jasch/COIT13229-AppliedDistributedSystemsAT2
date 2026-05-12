"""Tests for the Gold Miner distributed prototype.

These tests focus on the assignment's main distributed-system ideas: shared
state, lag/lost updates, separate bot clients, turn-based bot coordination,
and ZooKeeper ephemeral nodes.
"""

import threading
import time
import unittest

from kazoo.client import KazooClient

from bot_client import BotClient
from game_server import GameServer
from player_client import PlayerClient
from game_state import GameState, HEIGHT, NUM_GOLD, WIDTH, clamp_position, nearest_gold, spawn_positions

ZK_HOSTS = "127.0.0.1:2181"


class ZooKeeperTestCase(unittest.TestCase):
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
            self.skipTest("ZooKeeper is not available on 127.0.0.1:2181")

    def safe_delete(self, path):
        if self.zk.exists(path):
            self.zk.delete(path, recursive=True)


class TestBasicGameLogic(unittest.TestCase):
    def test_spawn_positions_unique(self):
        positions = spawn_positions(5)
        self.assertEqual(len(positions), len(set(positions)))

    def test_spawn_positions_avoids_excluded_positions(self):
        excluded = {(0, 0), (1, 1), (2, 2)}
        positions = spawn_positions(10, exclude=excluded)
        for pos in positions:
            self.assertNotIn(pos, excluded)

    def test_spawn_positions_within_bounds(self):
        for x, y in spawn_positions(10):
            self.assertGreaterEqual(x, 0)
            self.assertLess(x, WIDTH)
            self.assertGreaterEqual(y, 0)
            self.assertLess(y, HEIGHT)

    def test_clamp_position(self):
        self.assertEqual(clamp_position(-5, -10), (0, 0))
        self.assertEqual(clamp_position(WIDTH + 5, HEIGHT + 10), (WIDTH - 1, HEIGHT - 1))

    def test_nearest_gold(self):
        self.assertEqual(nearest_gold(4, 4, [(5, 5), (15, 15), (0, 0)]), (5, 5))


class TestZooKeeperIntegration(ZooKeeperTestCase):
    def test_zookeeper_connection(self):
        self.assertTrue(self.zk.connected)

    def test_game_state_persistence(self):
        root = "/test_game_state_persistence"
        self.safe_delete(root)
        self.zk.ensure_path(root)

        state = GameState()
        state.turn = 3
        state.player_x = 7
        state.player_y = 8
        state.player_score = 2
        state.golds = [(1, 1), (2, 2)]

        path = f"{root}/game_state"
        self.zk.create(path, state.to_json())
        loaded = GameState.from_json(self.zk.get(path)[0])

        self.assertEqual(loaded.turn, 3)
        self.assertEqual(loaded.player_x, 7)
        self.assertEqual(loaded.player_y, 8)
        self.assertEqual(loaded.player_score, 2)
        self.assertEqual(loaded.golds, [(1, 1), (2, 2)])
        self.safe_delete(root)


class TestDistributedFaults(ZooKeeperTestCase):
    def test_simulated_lag(self):
        root = "/test_simulated_lag"
        self.safe_delete(root)
        self.zk.ensure_path(root)
        path = f"{root}/game_state"
        self.zk.create(path, GameState().to_json())

        for expected_score in range(1, 6):
            time.sleep(0.2)  # artificial lag
            state = GameState.from_json(self.zk.get(path)[0])
            state.player_score += 1
            self.zk.set(path, state.to_json())
            self.assertEqual(GameState.from_json(self.zk.get(path)[0]).player_score, expected_score)

        self.safe_delete(root)

    def test_simulated_lost_message(self):
        root = "/test_simulated_lost_message"
        self.safe_delete(root)
        self.zk.ensure_path(root)
        path = f"{root}/game_state"
        self.zk.create(path, GameState().to_json())

        state = GameState.from_json(self.zk.get(path)[0])
        state.player_score += 1
        self.zk.set(path, state.to_json())

        lost_update = GameState.from_json(self.zk.get(path)[0])
        lost_update.player_score += 1  # deliberately not written back

        state = GameState.from_json(self.zk.get(path)[0])
        state.player_score += 1
        self.zk.set(path, state.to_json())

        final_state = GameState.from_json(self.zk.get(path)[0])
        self.assertEqual(final_state.player_score, 2)
        self.safe_delete(root)

    def test_eventual_consistency_after_delayed_update(self):
        root = "/test_eventual_consistency"
        self.safe_delete(root)
        self.zk.ensure_path(root)
        path = f"{root}/game_state"

        state = GameState()
        state.player_x = 1
        state.player_y = 1
        self.zk.create(path, state.to_json())

        old_read = GameState.from_json(self.zk.get(path)[0])
        self.assertEqual((old_read.player_x, old_read.player_y), (1, 1))

        time.sleep(0.5)
        state.player_x = 9
        state.player_y = 9
        self.zk.set(path, state.to_json())

        final_read = GameState.from_json(self.zk.get(path)[0])
        self.assertEqual((final_read.player_x, final_read.player_y), (9, 9))
        self.safe_delete(root)


class TestDistributedBots(ZooKeeperTestCase):
    def start_server(self, root):
        self.safe_delete(root)
        server = GameServer(game_root=root, bot_timeout_seconds=1.5)
        thread = threading.Thread(target=lambda: server.run(duration_seconds=10))
        thread.start()
        time.sleep(0.5)
        return server, thread

    def stop_all(self, server, server_thread, client=None, bots=None, bot_threads=None):
        bots = bots or []
        bot_threads = bot_threads or []

        if client:
            client.cleanup()
        for bot in bots:
            bot.cleanup()
        server.cleanup()

        for thread in bot_threads:
            thread.join(timeout=2)
        server_thread.join(timeout=2)
        self.safe_delete(server.game_root)

    def wait_for_bots(self, server, expected_count, timeout=5):
        end = time.time() + timeout
        while time.time() < end:
            if len(server.state.bots) >= expected_count:
                return True
            time.sleep(0.1)
        return False

    def play_one_player_turn(self, client, move="d"):
        state = client.get_game_state()
        self.assertIsNotNone(state)
        self.assertTrue(client.send_move(move, state.turn))
        return client.wait_for_turn_to_finish(state.turn, timeout=5)

    def test_bot_client_connection(self):
        root = "/test_bot_client_connection"
        server, server_thread = self.start_server(root)
        bot = BotClient("test_bot", game_root=root)
        bot_thread = threading.Thread(target=bot.play)
        bot_thread.start()
        client = PlayerClient(game_root=root)

        try:
            client.wait_for_game(timeout=5)
            self.assertTrue(self.wait_for_bots(server, 1))
            updated = self.play_one_player_turn(client)
            self.assertIn("test_bot", updated.bots)
            self.assertEqual(updated.turn, 1)
            self.assertEqual(len(updated.golds), NUM_GOLD)
        finally:
            self.stop_all(server, server_thread, client, [bot], [bot_thread])

    def test_multiple_bot_clients_take_one_turn_each(self):
        root = "/test_multiple_bot_clients"
        server, server_thread = self.start_server(root)
        bots = [BotClient(f"bot_{i}", game_root=root) for i in range(3)]
        bot_threads = [threading.Thread(target=bot.play) for bot in bots]
        client = PlayerClient(game_root=root)

        for thread in bot_threads:
            thread.start()

        try:
            client.wait_for_game(timeout=5)
            self.assertTrue(self.wait_for_bots(server, 3))

            before = client.get_game_state()
            before_positions = {bot_id: (bot["x"], bot["y"]) for bot_id, bot in before.bots.items()}
            after = self.play_one_player_turn(client)
            after_positions = {bot_id: (bot["x"], bot["y"]) for bot_id, bot in after.bots.items()}

            self.assertEqual(after.turn, before.turn + 1)
            self.assertEqual(len(after.bots), 3)
            self.assertEqual(len(after.golds), NUM_GOLD)
            self.assertEqual(len(after.golds), len(set(after.golds)))

            for bot_id, before_pos in before_positions.items():
                after_pos = after_positions[bot_id]
                distance = abs(after_pos[0] - before_pos[0]) + abs(after_pos[1] - before_pos[1])
                self.assertLessEqual(distance, 1)
        finally:
            self.stop_all(server, server_thread, client, bots, bot_threads)

    def test_node_crash_ephemeral_node_removed(self):
        root = "/test_node_crash"
        path = f"{root}/members/bot_1"
        self.safe_delete(root)
        self.zk.ensure_path(f"{root}/members")

        bot_zk = KazooClient(hosts=ZK_HOSTS)
        bot_zk.start(timeout=5)
        try:
            bot_zk.create(path, b"active", ephemeral=True)
            self.assertIsNotNone(self.zk.exists(path))
            bot_zk.stop()
            bot_zk.close()
            time.sleep(2)
            self.assertIsNone(self.zk.exists(path))
        finally:
            if bot_zk.connected:
                bot_zk.stop()
            bot_zk.close()
            self.safe_delete(root)


if __name__ == "__main__":
    unittest.main(verbosity=2)
