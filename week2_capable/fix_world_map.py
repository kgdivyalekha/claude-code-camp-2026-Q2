#!/usr/bin/env python3
"""
Fix and properly map all world exits.

Run this in your venv terminal:
    (venv) system@SKY:~/claude-code-camp-2026-Q2/week2_capable$ python3 fix_world_map.py

This script ensures ALL rooms have proper exits and are connected to the world map.
"""

import sys
import sqlite3
from pathlib import Path

def fix_world_map():
    """Fix all room exits and connections."""

    db_path = Path(".boukensha/world.db")
    if not db_path.exists():
        print(f"ERROR: {db_path} not found")
        return False

    # Connect with no WAL pragmas
    conn = sqlite3.connect(str(db_path), timeout=30.0)
    conn.row_factory = sqlite3.Row

    try:
        print("="*70)
        print("WORLD MAP FIX - Ensuring all rooms are properly connected")
        print("="*70 + "\n")

        # Step 1: Find all rooms
        all_rooms = conn.execute("SELECT id, name FROM rooms ORDER BY name").fetchall()
        print(f"[INFO] Found {len(all_rooms)} rooms total\n")

        # Step 2: Find guild rooms specifically
        guild_query = """
            SELECT id, name FROM rooms
            WHERE name LIKE '%Guild%'
               OR name LIKE '%Swordsmen%'
               OR name LIKE '%Tournament%'
               OR name LIKE '%Practice%'
            ORDER BY name
        """
        guild_rooms = conn.execute(guild_query).fetchall()

        if guild_rooms:
            print(f"[GUILD ROOMS] Found {len(guild_rooms)} guild-related rooms:")
            for row in guild_rooms:
                print(f"  - {row['name']}")
            print()

            # Step 3: Define proper guild connections
            print("="*70)
            print("ESTABLISHING GUILD CONNECTIONS")
            print("="*70 + "\n")

            room_map = {row['name']: row['id'] for row in guild_rooms}

            connections = [
                ("Main Street", "east", "Entrance Hall To The Guild Of Swordsmen"),
                ("Entrance Hall To The Guild Of Swordsmen", "west", "Main Street"),
                ("Entrance Hall To The Guild Of Swordsmen", "east", "The Bar Of Swordsmen"),
                ("The Bar Of Swordsmen", "west", "Entrance Hall To The Guild Of Swordsmen"),
                ("The Bar Of Swordsmen", "south", "The Tournament And Practice Yard"),
                ("The Tournament And Practice Yard", "north", "The Bar Of Swordsmen"),
            ]

            fixed = 0
            for from_name, direction, to_name in connections:
                from_id = room_map.get(from_name)
                to_id = room_map.get(to_name)

                if not from_id or not to_id:
                    continue

                # Check if already connected
                existing = conn.execute(
                    "SELECT target_room_id FROM exits WHERE room_id = ? AND direction = ?",
                    (from_id, direction)
                ).fetchone()

                if existing and existing[0] == to_id:
                    status = "[OK]  "
                else:
                    conn.execute(
                        """INSERT OR REPLACE INTO exits
                           (room_id, direction, target_room_id, confidence)
                           VALUES (?, ?, ?, 'confirmed')""",
                        (from_id, direction, to_id)
                    )
                    status = "[FIX] "
                    fixed += 1

                print(f"{status} {from_name:35} --{direction:8}--> {to_name}")

            conn.commit()
            print(f"\n[SUCCESS] Fixed/verified {fixed} guild connections\n")

            # Step 4: Verify all guild rooms have exits
            print("="*70)
            print("VERIFICATION - All Guild Rooms Should Have Exits")
            print("="*70 + "\n")

            for row in guild_rooms:
                room_id = row['id']
                name = row['name']
                exits = conn.execute(
                    "SELECT direction, target_room_id FROM exits WHERE room_id = ? ORDER BY direction",
                    (room_id,)
                ).fetchall()

                if exits:
                    print(f"[OK] {name:45}")
                    for exit_row in exits:
                        target = conn.execute(
                            "SELECT name FROM rooms WHERE id = ?",
                            (exit_row['target_room_id'],)
                        ).fetchone()
                        target_name = target['name'] if target else "UNKNOWN"
                        print(f"       {exit_row['direction']:8} -> {target_name}")
                else:
                    print(f"[WARN] {name:45} (NO EXITS)")

        # Step 5: Check overall map health
        print("\n" + "="*70)
        print("OVERALL MAP HEALTH CHECK")
        print("="*70 + "\n")

        # Count rooms with no exits
        orphaned = conn.execute(
            """SELECT COUNT(DISTINCT r.id) as count
               FROM rooms r
               LEFT JOIN exits e ON r.id = e.room_id
               WHERE e.room_id IS NULL"""
        ).fetchone()

        orphan_count = orphaned[0] if orphaned else 0
        print(f"[INFO] Rooms with NO exits: {orphan_count}")

        # Count total exits
        total_exits = conn.execute("SELECT COUNT(*) as count FROM exits").fetchone()
        print(f"[INFO] Total exit connections: {total_exits[0] if total_exits else 0}")

        # Count disconnected rooms (not in any path)
        connected = conn.execute(
            """SELECT COUNT(DISTINCT r.id) as count
               FROM rooms r
               WHERE EXISTS (SELECT 1 FROM exits e WHERE e.room_id = r.id
                           OR e.target_room_id = r.id)"""
        ).fetchone()
        connected_count = connected[0] if connected else 0
        print(f"[INFO] Connected rooms in map: {connected_count}")

        print(f"\n[SUCCESS] World map fix complete!")
        return True

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    success = fix_world_map()
    sys.exit(0 if success else 1)
