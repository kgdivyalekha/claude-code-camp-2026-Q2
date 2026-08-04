"""Tests for M6: WorldDB + identity reconciliation + NavigationTracker."""

import os
import tempfile
import unittest

from boukensha.observability.navigation import NavigationTracker
from boukensha.world.db import WorldDB
from boukensha.world.identity import RoomReconciler, signature
from boukensha.world.pathfind import find_path, nearest_unexplored


class TestWorldIdentity(unittest.TestCase):
    """Room identity and signature tests."""

    def test_signature_unique_per_room_combo(self):
        """Same name + different exits = different signatures."""
        sig1 = signature("Temple Square", ["north", "east"], "A grand stone plaza")
        sig2 = signature("Temple Square", ["north", "south", "east"], "A grand stone plaza")
        self.assertNotEqual(sig1, sig2)

    def test_signature_order_invariant(self):
        """Exit order doesn't matter for signature."""
        sig1 = signature("Room", ["north", "east"], "desc")
        sig2 = signature("Room", ["east", "north"], "desc")
        self.assertEqual(sig1, sig2)

    def test_signature_deterministic(self):
        """Same inputs always produce same signature."""
        sig1 = signature("Market", ["north", "south"], "Busy plaza")
        sig2 = signature("Market", ["north", "south"], "Busy plaza")
        self.assertEqual(sig1, sig2)


class TestWorldDB(unittest.TestCase):
    """WorldDB persistence and queries."""

    def setUp(self):
        """Create a temp database for each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        self.world_db = WorldDB(self.db_path)

    def tearDown(self):
        """Clean up."""
        self.world_db.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        os.rmdir(self.temp_dir)

    def test_add_and_retrieve_room(self):
        """Add a room and retrieve it."""
        self.world_db.add_room(
            "room_abc123",
            "Market Square",
            "abc123",
            "A bustling marketplace",
            "probable",
            "scout",
        )

        room = self.world_db.get_room("room_abc123")
        self.assertIsNotNone(room)
        self.assertEqual(room["name"], "Market Square")
        self.assertEqual(room["signature"], "abc123")
        self.assertEqual(room["discovered_by"], "scout")

    def test_add_exit(self):
        """Add exits between rooms."""
        self.world_db.add_room("room_1", "Square", "sig1", "desc")
        self.world_db.add_room("room_2", "Temple", "sig2", "desc")

        self.world_db.add_exit("room_1", "north", "room_2", "probable")

        exits = self.world_db.get_exits("room_1")
        self.assertEqual(exits["north"], "room_2")

    def test_untraversed_exit(self):
        """Add an exit that hasn't been traversed yet."""
        self.world_db.add_room("room_1", "Square", "sig1", "desc")
        self.world_db.add_exit("room_1", "east", None, "probable")

        exit_target = self.world_db.get_exit_by_direction("room_1", "east")
        self.assertIsNone(exit_target)

    def test_confirm_exit(self):
        """Confirm an exit after successful movement."""
        self.world_db.add_room("room_1", "Square", "sig1", "desc")
        self.world_db.add_exit("room_1", "north", "room_2", "probable")

        self.world_db.confirm_exit("room_1", "north", "room_2")

        # Check confidence updated
        cursor = self.world_db.conn.execute(
            "SELECT confidence FROM exits WHERE room_id = ? AND direction = ?",
            ("room_1", "north"),
        )
        row = cursor.fetchone()
        self.assertEqual(row[0], "confirmed")

    def test_room_count(self):
        """Count total rooms."""
        self.world_db.add_room("room_1", "Square", "sig1", "desc")
        self.world_db.add_room("room_2", "Temple", "sig2", "desc")
        self.assertEqual(self.world_db.room_count(), 2)


class TestRoomReconciliation(unittest.TestCase):
    """Room identity reconciliation."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        self.world_db = WorldDB(self.db_path)
        self.reconciler = RoomReconciler(self.world_db)

    def tearDown(self):
        self.world_db.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        os.rmdir(self.temp_dir)

    def test_new_room_creation(self):
        """First observation of a room creates it."""
        room_id = self.reconciler.reconcile(
            "Market Square",
            ["north", "south", "east"],
            "A busy marketplace with merchants",
            "scout",
        )

        room = self.world_db.get_room(room_id)
        self.assertIsNotNone(room)
        self.assertEqual(room["name"], "Market Square")
        self.assertEqual(room["confidence"], "probable")

    def test_same_room_reidentified(self):
        """Revisiting a room with same signature identifies it."""
        room_id_1 = self.reconciler.reconcile(
            "Market Square",
            ["north", "south", "east"],
            "A busy marketplace",
            "scout",
        )

        # Same signature should be identified
        room_id_2 = self.reconciler.reconcile(
            "Market Square",
            ["north", "south", "east"],
            "A busy marketplace",
            "scout",
        )

        self.assertEqual(room_id_1, room_id_2)

    def test_different_same_named_rooms_are_distinct(self):
        """tbaMUD: same name, different exits = different rooms."""
        room_id_1 = self.reconciler.reconcile(
            "Forest Path",
            ["north", "south"],
            "A path through tall oaks",
            "scout",
        )

        room_id_2 = self.reconciler.reconcile(
            "Forest Path",
            ["east", "west"],
            "A winding path through trees",
            "scout",
        )

        # Different signatures, so different room IDs
        self.assertNotEqual(room_id_1, room_id_2)

    def test_reverse_direction_mapping(self):
        """Cardinal directions map correctly in reverse."""
        self.assertEqual(self.reconciler._reverse_direction("north"), "south")
        self.assertEqual(self.reconciler._reverse_direction("n"), "s")
        self.assertEqual(self.reconciler._reverse_direction("east"), "west")
        self.assertEqual(self.reconciler._reverse_direction("up"), "down")


class TestPathfinding(unittest.TestCase):
    """Pathfinding over world graph."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        self.world_db = WorldDB(self.db_path)
        self._setup_graph()

    def tearDown(self):
        self.world_db.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        os.rmdir(self.temp_dir)

    def _setup_graph(self):
        """Create a simple graph:
        Square --[N]--> Temple
        Square --[E]--> Market
        Market --[N]--> Tower
        """
        self.world_db.add_room("room_1", "Square", "sig1", "desc")
        self.world_db.add_room("room_2", "Temple", "sig2", "desc")
        self.world_db.add_room("room_3", "Market", "sig3", "desc")
        self.world_db.add_room("room_4", "Tower", "sig4", "desc")

        self.world_db.add_exit("room_1", "north", "room_2", "confirmed")
        self.world_db.add_exit("room_1", "east", "room_3", "confirmed")
        self.world_db.add_exit("room_3", "north", "room_4", "confirmed")

    def test_direct_path(self):
        """Find a direct path between adjacent rooms."""
        path = find_path(self.world_db, "room_1", "room_2")
        self.assertEqual(path, ["north"])

    def test_multi_hop_path(self):
        """Find a path requiring multiple moves."""
        path = find_path(self.world_db, "room_1", "room_4")
        self.assertEqual(path, ["east", "north"])

    def test_same_room_path(self):
        """Path from a room to itself is empty."""
        path = find_path(self.world_db, "room_1", "room_1")
        self.assertEqual(path, [])

    def test_unreachable_room(self):
        """Unreachable destination returns None."""
        self.world_db.add_room("room_5", "Island", "sig5", "desc")
        path = find_path(self.world_db, "room_1", "room_5")
        self.assertIsNone(path)

    def test_nearest_unexplored(self):
        """Find closest room with unexplored exit."""
        # room_1 has an unexplored exit west
        self.world_db.add_exit("room_1", "west", None, "probable")

        result = nearest_unexplored(self.world_db, "room_1")
        self.assertIsNotNone(result)
        room_id, distance, path, direction = result
        self.assertEqual(room_id, "room_1")
        self.assertEqual(distance, 0)
        self.assertEqual(direction, "west")


class TestNavigationTracker(unittest.TestCase):
    """NavigationTracker: parse look output into world.db."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        self.world_db = WorldDB(self.db_path)
        self.tracker = NavigationTracker(self.world_db)

    def tearDown(self):
        self.world_db.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        os.rmdir(self.temp_dir)

    def test_parse_look_basic(self):
        """Parse a standard look output."""
        look_output = """Market Square
A bustling marketplace filled with merchants hawking their wares.
[ Exits: north south east ]"""

        room_id = self.tracker.on_look_result(look_output, "scout")
        self.assertIsNotNone(room_id)

        room = self.world_db.get_room(room_id)
        self.assertEqual(room["name"], "Market Square")
        self.assertIn("north", self.world_db.get_exits(room_id))
        self.assertIn("south", self.world_db.get_exits(room_id))
        self.assertIn("east", self.world_db.get_exits(room_id))

    def test_parse_look_with_noise(self):
        """Parse look output with async spam (mobs, weather, etc)."""
        look_output = """Temple
A sacred temple with high vaulted ceilings.
A goblin arrives from the north.
[ Exits: north west down ]"""

        room_id = self.tracker.on_look_result(look_output, "scout")
        self.assertIsNotNone(room_id)

        exits = self.world_db.get_exits(room_id)
        self.assertIn("north", exits)
        self.assertIn("west", exits)
        self.assertIn("down", exits)

    def test_current_room_tracking(self):
        """Tracker remembers current room."""
        look_output = """Square
A town square.
[ Exits: north south ]"""

        room_id = self.tracker.on_look_result(look_output)
        self.assertEqual(self.tracker.get_current_room(), room_id)

    def test_move_success(self):
        """Parse successful movement."""
        # First look
        look1 = """Square\nA town square.\n[ Exits: north south ]"""
        room_1 = self.tracker.on_look_result(look1, "scout")

        # Move north (gets a new look as result)
        look2 = """Temple\nA sacred temple.\n[ Exits: south ]"""
        room_2 = self.tracker.on_move_result(look2, room_1, "north", "scout")

        self.assertIsNotNone(room_2)
        self.assertNotEqual(room_1, room_2)

        # Check reciprocal exit
        exits_2 = self.world_db.get_exits(room_2)
        self.assertIn("south", exits_2)

    def test_move_blocked(self):
        """Parse blocked movement."""
        look1 = """Square\nA town square.\n[ Exits: north south ]"""
        room_1 = self.tracker.on_look_result(look1, "scout")

        # Try to move east (blocked)
        blocked_msg = "You can't go that way."
        result = self.tracker.on_move_result(blocked_msg, room_1, "east", "scout")

        self.assertIsNone(result)

        # Check that exit is marked as blocked
        cursor = self.world_db.conn.execute(
            "SELECT blocked_reason FROM exits WHERE room_id = ? AND direction = ?",
            (room_1, "east"),
        )
        row = cursor.fetchone()
        self.assertIsNotNone(row)


if __name__ == "__main__":
    unittest.main()
