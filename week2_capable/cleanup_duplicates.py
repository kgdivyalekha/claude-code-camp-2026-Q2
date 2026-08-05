#!/usr/bin/env python3
"""Cleanup duplicate rooms in world.db"""

import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent / '.boukensha' / 'world.db'

if not DB_PATH.exists():
    print(f"❌ Database not found: {DB_PATH}")
    sys.exit(1)

print(f"🔍 Scanning for duplicate rooms in {DB_PATH}...")

conn = sqlite3.connect(str(DB_PATH))
conn.row_factory = sqlite3.Row
conn.execute("PRAGMA busy_timeout = 10000")

# Find duplicates
cursor = conn.execute("""
    SELECT name, GROUP_CONCAT(id, ',') as ids, COUNT(*) as count
    FROM rooms
    GROUP BY name
    HAVING COUNT(*) > 1
    ORDER BY count DESC
""")

duplicates = cursor.fetchall()

if not duplicates:
    print("✓ No duplicates found!")
    conn.close()
    sys.exit(0)

print(f"\n📊 Found {len(duplicates)} duplicate room names:\n")
for row in duplicates:
    print(f"  • {row['name']} ({row['count']} copies)")

total_merged = 0

print("\n🔗 Merging duplicates...\n")

for group in duplicates:
    name = group['name']
    room_ids = [rid.strip() for rid in group['ids'].split(',')]

    if len(room_ids) < 2:
        continue

    primary_id = room_ids[0]
    secondary_ids = room_ids[1:]

    print(f"  📍 {name}")
    print(f"     Primary: {primary_id}")
    print(f"     Secondary: {', '.join(secondary_ids)}")

    # For each secondary room
    for secondary_id in secondary_ids:
        # Redirect all exits pointing to secondary to primary
        conn.execute(
            "UPDATE exits SET target_room_id = ? WHERE target_room_id = ?",
            (primary_id, secondary_id)
        )

        # Delete the secondary room
        conn.execute("DELETE FROM rooms WHERE id = ?", (secondary_id,))

        total_merged += 1
        print(f"     ✓ Deleted {secondary_id}")

    print()

conn.commit()
conn.close()

print(f"✅ Done! Merged {total_merged} duplicate room entries.")
print("   Refresh the map to see the cleaned up rooms.")
