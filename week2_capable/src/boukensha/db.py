"""SQLite database connection factory with safe cross-process access.

WAL mode enables concurrent readers + one writer. mmap_size enables memory-mapped I/O.
These pragmas compose to support: Python agents writing, Ruby dashboard reading,
multi-actor writes via a serialized queue — all without SQLITE_BUSY contention.
"""

import sqlite3
from pathlib import Path


def open_db(path, mmap_bytes=256 * 1024 * 1024):
    """Open a SQLite connection with safety pragmas for concurrent access.

    Args:
        path: Database file path. Parent directories are created if missing.
        mmap_bytes: Memory-mapped I/O size. Set to 0 to disable. Silently falls back if unavailable.

    Returns:
        A configured sqlite3.Connection with WAL, mmap, and safe timeouts.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(
        str(path),
        timeout=5.0,           # Wait up to 5s if database is locked
        check_same_thread=False  # Allow multi-threaded access; we control serialization
    )

    # WAL mode: write-ahead logging. Readers don't block writers; writers don't block readers.
    conn.execute("PRAGMA journal_mode = WAL")

    # NORMAL sync: good enough with WAL, ~10x fewer fsyncs than FULL.
    conn.execute("PRAGMA synchronous = NORMAL")

    # Memory-mapped I/O: advisory, silently falls back if unavailable.
    if mmap_bytes > 0:
        conn.execute(f"PRAGMA mmap_size = {mmap_bytes}")

    # Retry with exponential backoff when database is busy.
    conn.execute("PRAGMA busy_timeout = 5000")

    # Foreign key constraints are OFF by default in SQLite.
    conn.execute("PRAGMA foreign_keys = ON")

    return conn
