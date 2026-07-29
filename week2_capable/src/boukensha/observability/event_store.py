"""Live JSONL → SQLite mirror. Append-only, fire-and-forget.

EventStore subscribes to Logger and writes events to events.db. A DB write failure
degrades to a warning and can never interrupt a turn. This is the foundation for
all observability in week 2.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from boukensha.db import open_db


class EventStore:
    """Live event capture from Logger into SQLite.

    Events are inserted as-is from the JSONL stream. Schema columns extract commonly
    needed fields; rare fields live in `details` as the full JSON.
    """

    def __init__(self, db_path: str = ".boukensha/events.db"):
        """Initialize the event store and schema.

        Args:
            db_path: Path to events.db. Parent directories created if missing.
        """
        self.db_path = db_path
        self.conn = open_db(db_path)
        self._init_schema()

    def attach(self, logger: Any) -> None:
        """Subscribe this store to a Logger instance.

        Args:
            logger: A Logger instance. Will call logger.subscribe() to register our handler.
        """
        logger.subscribe(self._on_event)

    def _on_event(self, event: Dict[str, Any]) -> None:
        """Handle a single logged event (fires on every logger write).

        Args:
            event: The event dict from logger._write_log (before session_id/turn/at are added).
        """
        try:
            self._insert(event)
        except sqlite3.Error as e:
            # Degrade to a warning — DB failure must never end a turn
            from boukensha import state
            state.warn(f"events.db write failed, continuing: {e}")

    def _insert(self, event: Dict[str, Any]) -> None:
        """Insert an event into the database.

        Extracts known fields and stores the full JSON in `details`.

        Args:
            event: Event dict with at minimum: phase, session_id, turn, actor.
        """
        phase = event.get("phase")
        session_id = event.get("session_id")
        actor = event.get("actor")
        turn = event.get("turn")
        at = event.get("at")

        # Extract fields relevant to token accounting and tool tracking
        iteration = event.get("iteration")
        tool = event.get("name") or event.get("tool")  # both "name" and "tool" are used
        ok = event.get("ok")

        # Token fields (only appear on "response" events)
        input_tokens = event.get("input_tokens")
        output_tokens = event.get("output_tokens")
        cache_read_tokens = event.get("cache_read_input_tokens")
        cache_write_tokens = event.get("cache_creation_input_tokens")
        cost_usd = event.get("cost_usd")

        # Metadata
        model = event.get("model")
        provider = event.get("provider")
        tools_sent = event.get("tools_sent")
        room = event.get("room")

        # Full event as JSON for posterity
        details = json.dumps(event, default=str)

        self.conn.execute(
            """
            INSERT INTO events
            (session_id, actor, turn, iteration, at, phase, tool, ok,
             input_tokens, output_tokens, cache_read_tokens, cache_write_tokens,
             tools_sent, cost_usd, model, provider, room, details)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id, actor, turn, iteration, at, phase, tool, ok,
                input_tokens, output_tokens, cache_read_tokens, cache_write_tokens,
                tools_sent, cost_usd, model, provider, room, details,
            ),
        )
        self.conn.commit()

    def _init_schema(self) -> None:
        """Create the events table if it doesn't exist."""
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id          TEXT NOT NULL,
                actor               TEXT,
                turn                INTEGER,
                iteration           INTEGER,
                at                  TEXT NOT NULL,
                phase               TEXT NOT NULL,
                tool                TEXT,
                ok                  INTEGER,
                input_tokens        INTEGER,
                output_tokens       INTEGER,
                cache_read_tokens   INTEGER,
                cache_write_tokens  INTEGER,
                tools_sent          INTEGER,
                cost_usd            REAL,
                model               TEXT,
                provider            TEXT,
                room                TEXT,
                details             TEXT NOT NULL
            )
            """
        )

        # Create indexes for common queries
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_session_phase ON events(session_id, phase)"
        )
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_events_session_turn ON events(session_id, turn)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_events_actor ON events(session_id, actor)")

        self.conn.commit()

    @classmethod
    def rebuild_from_jsonl(cls, jsonl_path: str, db_path: str = ".boukensha/events.db") -> "EventStore":
        """Backfill events.db from a JSONL session log.

        This is how we analyze week 1 sessions to establish the token baseline.
        A corrupt DB is `rm` plus rebuild; this method recovers cleanly.

        Args:
            jsonl_path: Path to a .boukensha/sessions/*.jsonl file.
            db_path: Path to events.db. Will be overwritten.

        Returns:
            EventStore instance with the rebuilt database.
        """
        # Delete and recreate
        db_file = Path(db_path)
        if db_file.exists():
            db_file.unlink()

        store = cls(db_path)

        # Read JSONL and insert each line
        jsonl_file = Path(jsonl_path)
        if not jsonl_file.exists():
            raise FileNotFoundError(f"JSONL file not found: {jsonl_path}")

        for line in jsonl_file.read_text().splitlines():
            if not line.strip():
                continue
            event = json.loads(line)
            store._insert(event)

        return store

    def close(self) -> None:
        """Close the database connection."""
        if self.conn:
            self.conn.close()

    def __enter__(self) -> "EventStore":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
