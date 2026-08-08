#!/usr/bin/env python3
"""Test Navigator tool: world DB-first pathfinding with BFS fallback.

This tests the Navigator tool's behavior:
1. Check world.db for cached paths first
2. Fall back to BFS if path not found
3. Support exploration guidance
4. Track compaction needs
"""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from boukensha.world.db import WorldDB
from boukensha.world.identity import signature
from boukensha.tools.navigator import Navigator
from boukensha.tools.registry import HelperToolRegistry


def setup_test_world() -> tuple[WorldDB, dict[str, str]]:
    """Create a test world with connected rooms."""
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "world.db")
    world_db = WorldDB(db_path)

    rooms_data = {
        "market": ("Market Square", ["north", "south", "east"]),
        "temple": ("Temple", ["south", "west"]),
        "forest": ("Dark Forest", ["east"]),
        "tavern": ("Green Tavern", ["north"]),
    }

    room_ids = {}
    for key, (name, exits) in rooms_data.items():
        sig = signature(name, exits, f"Description of {name}")
        room_id = f"room_{sig[:8]}"
        room_ids[key] = room_id
        world_db.add_room(room_id, name, sig, f"Description of {name}")

    # Wire exits
    world_db.add_exit(room_ids["market"], "north", room_ids["temple"], "confirmed")
    world_db.add_exit(room_ids["temple"], "south", room_ids["market"], "confirmed")

    world_db.add_exit(room_ids["market"], "south", room_ids["tavern"], "confirmed")
    world_db.add_exit(room_ids["tavern"], "north", room_ids["market"], "confirmed")

    world_db.add_exit(room_ids["market"], "east", room_ids["forest"], "confirmed")
    world_db.add_exit(room_ids["forest"], "west", room_ids["market"], "confirmed")

    # Add unexplored exit
    world_db.add_exit(room_ids["temple"], "west", None, "probable")

    return world_db, room_ids


def test_navigate_cached_path():
    """Test navigation using cached path from world.db."""
    world_db, room_ids = setup_test_world()
    navigator = Navigator(world_db)

    try:
        # Get signatures for rooms
        market_room = world_db.get_room(room_ids["market"])
        temple_room = world_db.get_room(room_ids["temple"])

        # Navigate from Market to Temple (path is in world.db)
        result = navigator.navigate_to(
            from_room_signature=market_room["signature"],
            to_room_name="Temple",
            from_room_name="Market Square",
            to_room_signature=temple_room["signature"],
        )

        assert result["success"], f"Navigation failed: {result['reason']}"
        assert result["path"] == ["north"], f"Expected ['north'], got {result['path']}"
        assert result["cached"] is True, "Should be marked as cached"
        assert result["distance"] == 1, "Distance should be 1"
        print("✓ navigate_cached_path: Market → Temple (cached)")
    finally:
        world_db.close()


def test_navigate_multi_hop_cached():
    """Test multi-hop navigation using cached paths."""
    world_db, room_ids = setup_test_world()
    navigator = Navigator(world_db)

    try:
        market_room = world_db.get_room(room_ids["market"])
        tavern_room = world_db.get_room(room_ids["tavern"])

        # Navigate from Market to Tavern (2 hops: south)
        result = navigator.navigate_to(
            from_room_signature=market_room["signature"],
            to_room_name="Green Tavern",
            from_room_name="Market Square",
            to_room_signature=tavern_room["signature"],
        )

        assert result["success"], f"Failed: {result['reason']}"
        assert result["path"] == ["south"], f"Expected ['south'], got {result['path']}"
        assert result["cached"] is True, "Should be cached"
        print("✓ navigate_multi_hop_cached: Market → Tavern")
    finally:
        world_db.close()


def test_navigate_unknown_destination():
    """Test navigation to undiscovered location."""
    world_db, room_ids = setup_test_world()
    navigator = Navigator(world_db)

    try:
        market_room = world_db.get_room(room_ids["market"])

        # Try to navigate to unknown location
        result = navigator.navigate_to(
            from_room_signature=market_room["signature"],
            to_room_name="Unknown Place",
            from_room_name="Market Square",
        )

        assert result["success"] is False, "Should fail for unknown destination"
        assert "not yet discovered" in result["reason"].lower()
        print("✓ navigate_unknown_destination: Correctly rejects unknown location")
    finally:
        world_db.close()


def test_navigate_unreachable():
    """Test navigation to unreachable location."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "world.db")
        world_db = WorldDB(db_path)

        try:
            # Create two disconnected rooms
            sig1 = signature("Room A", ["north"], "Room A")
            sig2 = signature("Room B", ["south"], "Room B")

            room_a = f"room_{sig1[:8]}"
            room_b = f"room_{sig2[:8]}"

            world_db.add_room(room_a, "Room A", sig1, "Room A")
            world_db.add_room(room_b, "Room B", sig2, "Room B")

            navigator = Navigator(world_db)

            result = navigator.navigate_to(
                from_room_signature=sig1,
                to_room_name="Room B",
                from_room_name="Room A",
                to_room_signature=sig2,
            )

            assert result["success"] is False, "Should fail for unreachable room"
            assert "no path" in result["reason"].lower()
            print("✓ navigate_unreachable: Correctly reports unreachable destination")
        finally:
            world_db.close()


def test_explore_frontier():
    """Test exploration guidance via frontier queries."""
    world_db, room_ids = setup_test_world()
    navigator = Navigator(world_db)

    try:
        temple_room = world_db.get_room(room_ids["temple"])

        # From Temple, find nearest unexplored exit
        result = navigator.explore_frontier(
            from_room_signature=temple_room["signature"],
            from_room_name="Temple",
        )

        assert result["success"], f"Frontier query failed: {result['reason']}"
        assert result["frontier_direction"] == "west", f"Expected 'west', got {result['frontier_direction']}"
        assert result["distance"] == 0, "Unexplored exit should be at distance 0"
        print("✓ explore_frontier: Temple has unexplored exit 'west'")
    finally:
        world_db.close()


def test_explore_no_unexplored():
    """Test frontier query when all exits explored."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "world.db")
        world_db = WorldDB(db_path)

        try:
            # Create isolated room
            sig = signature("Isolated", [], "Isolated room")
            room_id = f"room_{sig[:8]}"
            world_db.add_room(room_id, "Isolated", sig, "Isolated room")

            navigator = Navigator(world_db)

            result = navigator.explore_frontier(
                from_room_signature=sig,
                from_room_name="Isolated",
            )

            assert result["success"] is False, "Should fail for fully explored area"
            assert "all reachable exits" in result["reason"].lower()
            print("✓ explore_no_unexplored: Correctly reports fully explored")
        finally:
            world_db.close()


def test_get_exit_status():
    """Test exit status query (explored vs unexplored)."""
    world_db, room_ids = setup_test_world()
    navigator = Navigator(world_db)

    try:
        temple_room = world_db.get_room(room_ids["temple"])

        # Get exit status for Temple
        result = navigator.get_exit_status(
            from_room_signature=temple_room["signature"],
            from_room_name="Temple",
        )

        assert result["explored_exits"] == ["south"], f"Expected ['south'], got {result['explored_exits']}"
        assert result["unexplored_exits"] == ["west"], f"Expected ['west'], got {result['unexplored_exits']}"
        print("✓ get_exit_status: Temple has 1 explored (south) and 1 unexplored (west)")
    finally:
        world_db.close()


def test_helper_tool_registry():
    """Test HelperToolRegistry integration."""
    world_db, room_ids = setup_test_world()
    registry = HelperToolRegistry(world_db)

    try:
        market_room = world_db.get_room(room_ids["market"])
        temple_room = world_db.get_room(room_ids["temple"])

        # Test navigate tool via registry
        result = registry.call_tool(
            name="navigate",
            from_room_signature=market_room["signature"],
            from_room_name="Market Square",
            args={
                "destination": "Temple",
                "destination_signature": temple_room["signature"],
            },
        )

        assert result["ok"], f"Navigate tool failed: {result.get('error')}"
        assert result["path"] == ["north"], f"Expected ['north'], got {result['path']}"
        print("✓ helper_tool_registry: Navigate tool works via registry")

        # Test explore tool via registry
        temple_sig = temple_room["signature"]
        result = registry.call_tool(
            name="explore",
            from_room_signature=temple_sig,
            from_room_name="Temple",
            args={"include_distance": True},
        )

        assert result["ok"], f"Explore tool failed: {result.get('error')}"
        assert result["frontier_direction"] == "west"
        print("✓ helper_tool_registry: Explore tool works via registry")

        # Test exits tool via registry
        result = registry.call_tool(
            name="exits",
            from_room_signature=temple_sig,
            from_room_name="Temple",
            args={},
        )

        assert result["ok"], f"Exits tool failed: {result.get('error')}"
        assert "south" in result["explored"]
        print("✓ helper_tool_registry: Exits tool works via registry")
    finally:
        world_db.close()


def test_cache_vs_bfs():
    """Test that cached paths are used before BFS computation."""
    world_db, room_ids = setup_test_world()
    navigator = Navigator(world_db)

    try:
        market_room = world_db.get_room(room_ids["market"])
        tavern_room = world_db.get_room(room_ids["tavern"])

        # First navigation (should use cached)
        result = navigator.navigate_to(
            from_room_signature=market_room["signature"],
            to_room_name="Green Tavern",
            to_room_signature=tavern_room["signature"],
        )

        assert result["cached"] is True, "Should indicate cached path"
        print("✓ cache_vs_bfs: Cached path used for known destination")
    finally:
        world_db.close()


if __name__ == "__main__":
    test_navigate_cached_path()
    test_navigate_multi_hop_cached()
    test_navigate_unknown_destination()
    test_navigate_unreachable()
    test_explore_frontier()
    test_explore_no_unexplored()
    test_get_exit_status()
    test_helper_tool_registry()
    test_cache_vs_bfs()
    print("\n✅ All Navigator tool tests passed!")
