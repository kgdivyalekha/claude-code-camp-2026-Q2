#!/usr/bin/env python3
"""Add keywords column to existing world.db if missing."""

import sqlite3
import sys

db_path = ".boukensha/world.db"

print("Checking schema...")
conn = sqlite3.connect(db_path, timeout=30.0)

# Check existing schema
cursor = conn.execute("PRAGMA table_info(rooms)")
columns = {row[1] for row in cursor.fetchall()}

print(f"Found {len(columns)} columns in rooms table")

if 'keywords' not in columns:
    print("[INFO] keywords column missing - adding it...")
    try:
        conn.execute("ALTER TABLE rooms ADD COLUMN keywords TEXT")
        conn.commit()
        print("[OK] Successfully added keywords column")
    except Exception as e:
        print(f"[ERROR] Failed to add column: {e}")
        sys.exit(1)
else:
    print("[OK] keywords column already exists")

# Verify
cursor = conn.execute("PRAGMA table_info(rooms)")
columns_after = {row[1] for row in cursor.fetchall()}
print(f"Schema now has {len(columns_after)} columns")

conn.close()
print("Done!")
