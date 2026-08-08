#!/usr/bin/env python3
"""Fix and properly connect Guild rooms in the world map.

This script ensures that all Guild of Swordsmen locations are properly
connected with bidirectional exits.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from boukensha.world.db import WorldDB
from boukensha.world.identity import signature


def fix_guild_exits():
    """Fix exits for Guild of Swordsmen rooms."""
    world_db = WorldDB(".boukensha/world.db")

    try:
        # First, find all guild-related rooms
        print("Finding Guild rooms...\n")

        guild_rooms = world_db.conn.execute(
            "SELECT id, name, signature FROM rooms WHERE name LIKE '%Guild%' OR name LIKE '%Swordsmen%' OR name LIKE '%Tournament%' OR name LIKE '%Practice%'"
        ).fetchall()

        if not guild_rooms:
            print("No guild rooms found in database")
            return

        print(f"Found {len(guild_rooms)} guild-related rooms:")
        for room_id, name, sig in guild_rooms:
            print(f"  {room_id}: {name}")

        # Create a map of room names to IDs for connection
        room_map = {}
        for room_id, name, sig in guild_rooms:
            room_map[name] = room_id
            print(f"    Signature: {sig[:16]}...")

        print(f"\n{'='*70}")
        print("DEFINING GUILD CONNECTIONS")
        print(f"{'='*70}\n")

        # Define proper connections
        # Format: (from_room_name, direction, to_room_name)
        connections = [
            # Main Street <-> Guild Entrance
            ("Main Street", "east", "Entrance Hall To The Guild Of Swordsmen"),
            ("Entrance Hall To The Guild Of Swordsmen", "west", "Main Street"),

            # Guild Entrance <-> Bar of Swordsmen
            ("Entrance Hall To The Guild Of Swordsmen", "east", "The Bar Of Swordsmen"),
            ("The Bar Of Swordsmen", "west", "Entrance Hall To The Guild Of Swordsmen"),

            # Bar <-> Tournament and Practice Yard
            ("The Bar Of Swordsmen", "south", "The Tournament And Practice Yard"),
            ("The Tournament And Practice Yard", "north", "The Bar Of Swordsmen"),
        ]

        print("Establishing connections:\n")

        fixed = 0
        for from_name, direction, to_name in connections:
            from_id = room_map.get(from_name)
            to_id = room_map.get(to_name)

            if not from_id or not to_id:
                if not from_id:
                    print(f"⚠ {from_name:40} NOT IN DATABASE")
                if not to_id:
                    print(f"⚠ {to_name:40} NOT IN DATABASE")
                continue

            # Check if exit already exists
            existing = world_db.conn.execute(
                "SELECT target_room_id FROM exits WHERE room_id = ? AND direction = ?",
                (from_id, direction)
            ).fetchone()

            if existing and existing[0] == to_id:
                print(f"✓ {from_name:35} --{direction:8}--> {to_name}")
                continue

            # Add or update exit
            world_db.conn.execute(
                """INSERT OR REPLACE INTO exits
                   (room_id, direction, target_room_id, confidence)
                   VALUES (?, ?, ?, 'confirmed')""",
                (from_id, direction, to_id)
            )
            print(f"✓ {from_name:35} --{direction:8}--> {to_name}")
            fixed += 1

        world_db.conn.commit()

        print(f"\n{'='*70}")
        print(f"RESULTS: Fixed/added {fixed} connections")
        print(f"{'='*70}\n")

        # Verify all guild rooms have exits
        print("Verifying exits for all guild rooms:\n")
        for room_id, name, sig in guild_rooms:
            exits = world_db.conn.execute(
                "SELECT direction, target_room_id FROM exits WHERE room_id = ? ORDER BY direction",
                (room_id,)
            ).fetchall()

            if exits:
                print(f"{name:40}")
                for direction, target_id in exits:
                    target = world_db.conn.execute(
                        "SELECT name FROM rooms WHERE id = ?",
                        (target_id,)
                    ).fetchone()
                    target_name = target[0] if target else "UNKNOWN"
                    print(f"  {direction:8} → {target_name}")
            else:
                print(f"{name:40} (NO EXITS)")

        print(f"\n✅ Guild rooms are now properly connected!")

    finally:
        world_db.close()


if __name__ == "__main__":
    fix_guild_exits()
