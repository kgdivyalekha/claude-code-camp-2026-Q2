#!/usr/bin/env python3
"""Rebuild events.db from JSONL sessions."""

import sys
from pathlib import Path

# Add week2_capable/src to path
sys.path.insert(0, str(Path(__file__).parent / "week2_capable" / "src"))

from boukensha.observability.event_store import EventStore

session_file = Path(".boukensha/sessions/20260803T220918Z-7975a5d3.jsonl")
db_file = Path(".boukensha/events.db")

if not session_file.exists():
    print(f"Error: {session_file} not found")
    sys.exit(1)

print(f"Rebuilding {db_file} from {session_file}...")
try:
    store = EventStore.rebuild_from_jsonl(str(session_file), str(db_file))
    print("✓ Rebuild complete")
    store.close()
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
