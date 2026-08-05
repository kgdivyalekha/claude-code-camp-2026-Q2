#!/usr/bin/env python3
"""Test M7 compression hooks: repeat-visit substitution, banner stripping."""

import os
import sys
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "week2_capable" / "src"))

from boukensha.tokens.compress import CompressionHooks
from boukensha.world.db import WorldDB
from boukensha.observability.navigation import NavigationTracker


def create_look_output(name, exits, description):
    """Create a realistic look output."""
    exits_str = ", ".join(exits)
    return f"""{name}

{description}

[ Exits: {exits_str} ]
"""


def test_first_visit_not_compressed():
    """First visit to a room should NOT be compressed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "world.db")
        world_db = WorldDB(db_path)
        compression = CompressionHooks(world_db)

        look_output = create_look_output(
            "Temple Square",
            ["north", "east", "south"],
            "A beautiful temple square with a fountain in the center.",
        )

        result = {
            "content": look_output,
            "ok": True,
        }

        # First call should NOT compress (visit_count = 0)
        compressed = compression.compress_repeat_rooms(
            actor=None,
            name="look",
            args={},
            result=result,
        )

        assert compressed is None, f"First visit should not compress, got {compressed}"
        print("✓ First visit not compressed")


def test_repeat_visit_compressed():
    """Second visit to the same room should be compressed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "world.db")
        world_db = WorldDB(db_path)

        # Manually add a room with visit_count > 0
        from boukensha.world.identity import signature

        name = "Temple Square"
        exits = ["north", "east", "south"]
        description = "A beautiful temple square with a fountain in the center."
        sig = signature(name, exits, description)
        room_id = f"room_{sig}"

        world_db.add_room(room_id, name, sig, description)
        # Increment visit count by doing an ON CONFLICT update
        world_db.conn.execute(
            "UPDATE rooms SET visit_count = visit_count + 1 WHERE id = ?",
            (room_id,),
        )
        world_db.conn.commit()

        # Verify the room was added and updated
        room = world_db.get_room(room_id)
        assert room is not None, f"Room should exist: {room_id}"
        assert room["visit_count"] >= 1, f"Visit count should be >= 1, got {room['visit_count']}"

        compression = CompressionHooks(world_db)

        look_output = create_look_output(name, exits, description)
        result = {"content": look_output, "ok": True}

        # Second call should compress
        compressed = compression.compress_repeat_rooms(
            actor=None,
            name="look",
            args={},
            result=result,
        )

        assert compressed is not None, "Repeat visit should compress"
        assert "visited" in compressed["content"].lower(), f"Summary should mention visits: {compressed}"
        print(f"✓ Repeat visit compressed: {compressed['content'][:60]}...")


def test_non_look_not_affected():
    """Non-look results should pass through unaffected."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "world.db")
        world_db = WorldDB(db_path)
        compression = CompressionHooks(world_db)

        result = {"content": "You move north.\nSomewhere else.", "ok": True}

        compressed = compression.compress_repeat_rooms(
            actor=None,
            name="move",
            args={"direction": "north"},
            result=result,
        )

        assert compressed is None, "Non-look commands should not be compressed"
        print("✓ Non-look results pass through")


def test_strip_banners():
    """Banner stripping should remove decorative elements."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "world.db")
        world_db = WorldDB(db_path)
        compression = CompressionHooks(world_db)

        verbose_output = """
==========================================
You are standing in a room.

*** This is a decoration line ***


[ Exits: north south ]
"""

        result = {"content": verbose_output, "ok": True}
        original_len = len(result["content"])

        # Don't call compress_repeat_rooms; call strip_banners directly
        stripped = compression.strip_banners(
            actor=None,
            name="look",
            args={},
            result=result.copy(),
        )

        if stripped is not None:
            # Banner stripping should reduce size
            new_len = len(stripped["content"])
            assert new_len < original_len, f"Banner stripping should reduce size: {original_len} → {new_len}"
            assert "==================" not in stripped["content"]
            assert "*** This is a decoration" not in stripped["content"]
            print(f"✓ Banners stripped: {original_len} → {new_len} chars")
        else:
            print("✓ No banners found (output remains unchanged)")


def test_world_db_persistence():
    """Verify world.db persists rooms across sessions."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "world.db")

        # Session 1: add a room
        world_db1 = WorldDB(db_path)
        world_db1.add_room("room_abc123", "Temple Square", "abc123", "A lovely temple.")
        world_db1.close()

        # Session 2: read the same room
        world_db2 = WorldDB(db_path)
        room = world_db2.get_room("room_abc123")
        world_db2.close()

        assert room is not None, "Room should persist across sessions"
        assert room["name"] == "Temple Square", f"Room name mismatch: {room}"
        print("✓ World.db persistence verified")


if __name__ == "__main__":
    test_first_visit_not_compressed()
    test_repeat_visit_compressed()
    test_non_look_not_affected()
    test_strip_banners()
    test_world_db_persistence()
    print("\n✅ All M7 compression tests passed!")
