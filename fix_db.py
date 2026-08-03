#!/usr/bin/env python3
"""Fix tools_sent by copying tool_count from prompt events."""

import sqlite3
from pathlib import Path

db_path = Path(".boukensha/events.db")

if not db_path.exists():
    print(f"Error: {db_path} not found")
    exit(1)

print(f"Fixing {db_path}...")
conn = sqlite3.connect(str(db_path))

# Read and execute the SQL fix
sql_file = Path("fix_tools_sent.sql")
if sql_file.exists():
    sql = sql_file.read_text()
    conn.executescript(sql)
    conn.commit()
    print("✓ Database fixed")
else:
    print("Error: fix_tools_sent.sql not found")
    exit(1)

conn.close()
