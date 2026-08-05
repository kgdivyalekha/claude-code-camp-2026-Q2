#!/usr/bin/env python3
"""Test M9: Pathfinding and frontier queries integration.

M9 delivers:
- BFS pathfinding over the world graph (find_path)
- Frontier queries for exploration (nearest_unexplored)
- Integration into repeat-visit compression summaries
- Agent can walk queried routes end-to-end
"""

import os
import sys
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from boukensha.world.db import WorldDB
from boukensha.world.pathfind import find_path, nearest_unexplored
from boukensha.world.identity import signature
from boukensha.tokens.compress import CompressionHooks


def setup_test_map() -> tuple[WorldDB, dict[str, str]]:
    """Build a test map and return (db, room_id_map).

    Map structure:
         Market Square (start) --- north --- Temple
         |                                    |
         south                              south
         |                                    |
         Alley ------------- east ---------- Park
    """
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "world.db")
    world_db = WorldDB(db_path)

    rooms = {
        "market": ("Market Square", ["north", "south", "east"]),
        "temple": ("Temple", ["south", "west"]),
        "alley": ("Dark Alley", ["north", "east", "west"]),
        "park": ("Park", ["west", "south"]),
    }

    room_ids = {}
    for key, (name, _exits) in rooms.items():
        # Create realistic signature
        sig = signature(name, rooms[key][1], f"Description of {name}")
        room_id = f"room_{sig[:8]}"
        room_ids[key] = room_id
        world_db.add_room(room_id, name, sig, f"A detailed description of {name}.")

    # Wire exits: Market -> Temple (north), Market -> Alley (south)
    world_db.add_exit(room_ids["market"], "north", room_ids["temple"], "confirmed")
    world_db.add_exit(room_ids["temple"], "south", room_ids["market"], "confirmed")

    world_db.add_exit(room_ids["market"], "south", room_ids["alley"], "confirmed")
    world_db.add_exit(room_ids["alley"], "north", room_ids["market"], "confirmed")

    # Park connection: Alley -> Park (east), Park -> Alley (west)
    world_db.add_exit(room_ids["alley"], "east", room_ids["park"], "confirmed")
    world_db.add_exit(room_ids["park"], "west", room_ids["alley"], "confirmed")

    # Add an unexplored exit from temple (south has a path back to market, but let's add east as unexplored)
    world_db.add_exit(room_ids["temple"], "east", None, "probable")

    return world_db, room_ids


def test_find_path_direct():
    """Test direct pathfinding: Market -> Temple."""
    world_db, room_ids = setup_test_map()

    path = find_path(world_db, room_ids["market"], room_ids["temple"])
    assert path is not None, "Should find path Market -> Temple"
    assert path == ["north"], f"Expected ['north'], got {path}"
    print("✓ find_path: Market -> Temple direct")


def test_find_path_multi_hop():
    """Test pathfinding across multiple hops: Market -> Park."""
    world_db, room_ids = setup_test_map()

    # Market -> Alley -> Park (2 hops)
    path = find_path(world_db, room_ids["market"], room_ids["park"])
    assert path is not None, "Should find path Market -> Park"
    assert len(path) == 2, f"Expected 2 hops, got {len(path)}: {path}"
    assert path == ["south", "east"], f"Expected ['south', 'east'], got {path}"
    print("✓ find_path: Market -> Park (multi-hop)")


def test_find_path_unreachable():
    """Test pathfinding when destination is unreachable."""
    world_db, room_ids = setup_test_map()

    # Add a disconnected room
    sig = signature("Isolated Room", [], "A lonely place")
    isolated_id = f"room_{sig[:8]}"
    world_db.add_room(isolated_id, "Isolated Room", sig, "You are alone.")

    # Should return None (unreachable)
    path = find_path(world_db, room_ids["market"], isolated_id)
    assert path is None, "Isolated room should be unreachable"
    print("✓ find_path: Unreachable returns None")


def test_find_path_same_room():
    """Test pathfinding to the same room."""
    world_db, room_ids = setup_test_map()

    path = find_path(world_db, room_ids["market"], room_ids["market"])
    assert path == [], "Path to same room should be empty list"
    print("✓ find_path: Same room returns []")


def test_nearest_unexplored_found():
    """Test frontier query: nearest unexplored exit."""
    world_db, room_ids = setup_test_map()

    frontier = nearest_unexplored(world_db, room_ids["market"])
    # Market has a south exit (confirmed) and north exit (confirmed).
    # Temple has an east exit that's unexplored.
    # So from Market: north -> Temple (1 hop), then east is unexplored

    assert frontier is not None, "Should find unexplored exit"
    target_id, distance, path, unexplored_dir = frontier
    assert target_id == room_ids["temple"], f"Should reach Temple, got {target_id}"
    assert distance == 1, f"Should be 1 hop away, got {distance}"
    assert path == ["north"], f"Expected path ['north'], got {path}"
    assert unexplored_dir == "east", f"Expected unexplored 'east', got {unexplored_dir}"
    print("✓ nearest_unexplored: Found frontier at Temple (east)")


def test_nearest_unexplored_none():
    """Test frontier query when all reachable exits are explored."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "world.db")
        world_db = WorldDB(db_path)

        # Single isolated room, no exits
        sig = signature("Isolated", [], "Alone")
        room_id = f"room_{sig[:8]}"
        world_db.add_room(room_id, "Isolated", sig, "Alone.")

        frontier = nearest_unexplored(world_db, room_id)
        assert frontier is None, "No frontiers in isolated room"
        print("✓ nearest_unexplored: None when all explored")


def test_frontier_info_in_summary():
    """Test that frontier queries are included in repeat-visit compression."""
    world_db, room_ids = setup_test_map()
    compression = CompressionHooks(world_db)

    # Simulate a second visit to Temple
    temple_room = world_db.get_room(room_ids["temple"])
    world_db.conn.execute(
        "UPDATE rooms SET visit_count = visit_count + 1 WHERE id = ?",
        (room_ids["temple"],),
    )
    world_db.conn.commit()

    # Create a look output for Temple
    look_output = f"""Temple

A sacred place of worship, adorned with ancient carvings.

[ Exits: south east ]
"""

    result = {"content": look_output, "ok": True}

    # Compress repeat visit
    compressed = compression.compress_repeat_rooms(
        actor=None,
        name="look",
        args={},
        result=result,
    )

    assert compressed is not None, "Repeat visit should compress"
    summary = compressed["content"]
    assert "visited" in summary.lower(), f"Should mention visit count: {summary}"
    assert "unexplored" in summary.lower(), f"Should mention unexplored: {summary}"
    assert "east" in summary.lower(), f"Should name unexplored directions: {summary}"
    print(f"✓ Frontier in summary: {summary[:80]}...")


def test_compression_tokens_saved():
    """Verify that compressed summaries actually save tokens."""
    world_db, room_ids = setup_test_map()
    compression = CompressionHooks(world_db)

    # Add a room and mark it as visited
    world_db.conn.execute(
        "UPDATE rooms SET visit_count = visit_count + 1 WHERE id = ?",
        (room_ids["market"],),
    )
    world_db.conn.commit()

    # Create verbose look output (first visit baseline)
    verbose_look = """Market Square

The bustling heart of town. Merchants hawk their wares from colorful stalls.
A fountain bubbles peacefully in the center, where children play. The air
smells of spices and fresh bread. To the north lies the Temple district.
To the south, the working quarter. Well-beaten paths lead in all directions.

[ Exits: north south east ]
"""

    result = {"content": verbose_look, "ok": True}
    compressed = compression.compress_repeat_rooms(None, "look", {}, result)

    assert compressed is not None, "Should compress repeat visit"
    original_tokens = compression._estimate_tokens(verbose_look)
    compressed_tokens = compression._estimate_tokens(compressed["content"])

    # Compression should save at least 70% of tokens
    savings_pct = (original_tokens - compressed_tokens) / original_tokens * 100
    assert savings_pct >= 70, f"Should save ≥70% tokens, saved {savings_pct:.0f}%"
    print(f"✓ Compression saved {savings_pct:.0f}% tokens ({original_tokens} → {compressed_tokens})")


def test_pathfinding_with_blocked_exits():
    """Test that pathfinding skips blocked exits."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "world.db")
        world_db = WorldDB(db_path)

        # Two rooms: A -> B (direct), A -> C (blocked), C -> B (unexplored)
        sig_a = signature("Room A", ["north", "east"], "Room A")
        sig_b = signature("Room B", ["south"], "Room B")
        sig_c = signature("Room C", [], "Room C")

        room_a = f"room_{sig_a[:8]}"
        room_b = f"room_{sig_b[:8]}"
        room_c = f"room_{sig_c[:8]}"

        world_db.add_room(room_a, "Room A", sig_a, "A.")
        world_db.add_room(room_b, "Room B", sig_b, "B.")
        world_db.add_room(room_c, "Room C", sig_c, "C.")

        # A -> north -> B (open)
        world_db.add_exit(room_a, "north", room_b, "confirmed")
        world_db.add_exit(room_b, "south", room_a, "confirmed")

        # A -> east -> C (blocked)
        world_db.add_exit(room_a, "east", room_c, "probable")
        world_db.block_exit(room_a, "east", "locked door")

        # Pathfinding should use the north path (blocked exits are skipped via NULL target)
        path = find_path(world_db, room_a, room_b)
        assert path == ["north"], f"Should use north path, got {path}"
        print("✓ Pathfinding respects blocked exits")


def test_end_to_end_route_walking():
    """Simulate an agent walking a queried route end-to-end.

    This is the success criterion for M9: agent walks a queried route.
    """
    world_db, room_ids = setup_test_map()

    # Start at Market, find route to Park
    start = room_ids["market"]
    goal = room_ids["park"]

    # Query the route
    route = find_path(world_db, start, goal)
    assert route is not None and len(route) > 0, "Should have a route"

    # Simulate walking the route
    current_room = start
    for i, direction in enumerate(route):
        next_room_id = world_db.get_exit_by_direction(current_room, direction)
        assert next_room_id is not None, f"Step {i}: Can't move {direction} from {current_room}"
        current_room = next_room_id
        print(f"  → Walked {direction} (step {i + 1}/{len(route)})")

    # Verify we reached the goal
    assert current_room == goal, f"Should reach goal {goal}, got {current_room}"
    print(f"✓ End-to-end route walking: {' -> '.join(route)}")


if __name__ == "__main__":
    test_find_path_direct()
    test_find_path_multi_hop()
    test_find_path_unreachable()
    test_find_path_same_room()
    test_nearest_unexplored_found()
    test_nearest_unexplored_none()
    test_frontier_info_in_summary()
    test_compression_tokens_saved()
    test_pathfinding_with_blocked_exits()
    test_end_to_end_route_walking()
    print("\n✅ All M9 pathfinding tests passed!")
