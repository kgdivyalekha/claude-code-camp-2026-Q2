#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Populate keywords column for all discovered rooms in world.db.

This script:
1. Connects to the world database
2. Iterates through all rooms with descriptions
3. Extracts keywords from each room's description
4. Updates both the keywords column and keywords table
"""

import sys
import os
import time
from pathlib import Path
from datetime import datetime

# Force UTF-8 encoding
os.environ['PYTHONIOENCODING'] = 'utf-8'

sys.path.insert(0, str(Path(__file__).parent / "src"))

from boukensha.world.db import WorldDB
from boukensha.world.keywords import KeywordExtractor


def populate_keywords(db_path: str = ".boukensha/world.db"):
    """Populate keywords for all discovered rooms."""

    # First, ensure keywords column exists
    import sqlite3
    try:
        conn = sqlite3.connect(db_path, timeout=2.0)
        cursor = conn.execute("PRAGMA table_info(rooms)")
        columns = {row[1] for row in cursor.fetchall()}
        if 'keywords' not in columns:
            print("[INFO] Adding keywords column to schema...")
            conn.execute("ALTER TABLE rooms ADD COLUMN keywords TEXT")
            conn.commit()
            print("[OK] Added keywords column")
        conn.close()
    except Exception as e:
        print(f"[WARN] Could not check/update schema: {e}")

    # Try to connect with retries
    world_db = None
    for attempt in range(3):
        try:
            world_db = WorldDB(db_path)
            print("[OK] Connected to database")
            break
        except Exception as e:
            if attempt < 2:
                print(f"Waiting for database lock... (attempt {attempt+1}/3)")
                time.sleep(1)
            else:
                print(f"Failed to connect: {e}")
                sys.exit(1)

    try:
        # Get all rooms
        all_rooms = world_db.conn.execute(
            "SELECT id, name, description FROM rooms WHERE description IS NOT NULL ORDER BY visit_count DESC"
        ).fetchall()

        print(f"Found {len(all_rooms)} rooms with descriptions\n")

        updated = 0
        skipped = 0

        for room_id, name, description in all_rooms:
            # Check if keywords already exist
            existing = world_db.conn.execute(
                "SELECT COUNT(*) FROM keywords WHERE room_id = ?",
                (room_id,)
            ).fetchone()[0]

            if existing > 0:
                print(f"[SKIP] {name:40} (keywords already exist)")
                skipped += 1
                continue

            # Extract keywords
            keywords = KeywordExtractor.extract(
                description=description,
                room_name=name,
                limit=10
            )

            if keywords:
                # Update keywords column in rooms table
                keywords_str = ", ".join(keywords)
                world_db.conn.execute(
                    "UPDATE rooms SET keywords = ? WHERE id = ?",
                    (keywords_str, room_id)
                )

                # Add to keywords table
                now = datetime.now().isoformat()
                for keyword in keywords:
                    world_db.conn.execute(
                        """INSERT INTO keywords
                           (keyword, room_id, extracted_from, confidence, added_at)
                           VALUES (?, ?, ?, ?, ?)""",
                        (keyword, room_id, "description", "auto", now)
                    )

                print(f"[OK] {name:40} -> {keywords}")
                updated += 1
            else:
                print(f"[SKIP] {name:40} (no keywords found)")
                skipped += 1

        world_db.conn.commit()

        print(f"\n{'='*70}")
        print(f"Summary:")
        print(f"  Updated: {updated} rooms")
        print(f"  Skipped: {skipped} rooms (no keywords or already have them)")
        print(f"  Total:   {updated + skipped} rooms")
        print(f"{'='*70}")

    finally:
        world_db.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Populate keywords in world database"
    )
    parser.add_argument(
        "--db",
        default=".boukensha/world.db",
        help="Path to world.db (default: .boukensha/world.db)"
    )
    args = parser.parse_args()

    populate_keywords(args.db)
