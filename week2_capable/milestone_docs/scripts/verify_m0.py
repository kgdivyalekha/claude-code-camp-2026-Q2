#!/usr/bin/env python3
"""Quick verification that M0 foundations are in place.

Tests:
1. Logger.event() method exists and works
2. Logger.set_actor() and turn() properly stamp records
3. db.open_db() creates SQLite connections with WAL and mmap
"""

import json
import sqlite3
import sys
import tempfile
from pathlib import Path

# Add src to path so we can import boukensha modules
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_logger():
    """Verify Logger has event() method and turn/actor stamping."""
    from boukensha.logger import Logger

    with tempfile.TemporaryDirectory() as tmpdir:
        logger = Logger(dir=tmpdir)

        # Test turn/actor stamping
        logger.turn(1)
        logger.set_actor("scout")
        logger.event("navigation.move", from_room="A", to_room="B", direction="north")

        logger.close()

        # Read back the JSONL to verify structure
        log_file = Path(tmpdir) / "sessions" / logger.session_id + ".jsonl"
        lines = log_file.read_text().strip().split("\n")

        # Last line should be our event with turn and actor set
        last_event = json.loads(lines[-1])
        assert last_event["phase"] == "navigation.move", "Event phase should match"
        assert last_event["turn"] == 1, "Turn should be stamped"
        assert last_event["actor"] == "scout", "Actor should be stamped"
        assert last_event["from_room"] == "A", "Custom field should be preserved"

    print("✓ Logger.event() and turn/actor stamping working")

def test_db():
    """Verify open_db creates WAL-enabled connections with mmap."""
    from boukensha.db import open_db

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"

        # Create connection
        conn = open_db(str(db_path))

        # Test WAL mode
        journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert journal_mode.lower() == "wal", f"Expected WAL, got {journal_mode}"

        # Test mmap_size is non-zero
        mmap_size = conn.execute("PRAGMA mmap_size").fetchone()[0]
        assert mmap_size > 0, f"mmap_size should be > 0, got {mmap_size}"

        # Test foreign_keys are ON
        fk_on = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        assert fk_on == 1, "Foreign keys should be ON"

        conn.close()

    print("✓ db.open_db() with WAL, mmap, and pragmas working")

def main():
    """Run all M0 verification tests."""
    print("M0 Verification — Foundations")
    print("-" * 40)

    try:
        test_logger()
        test_db()
        print("-" * 40)
        print("✅ M0 Complete: All foundations verified")
        return 0
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
