#!/usr/bin/env python3
"""
Event Store - Writes events to SQLite database in real-time as agent runs.
Used by agents to log token usage and costs automatically.
"""

import sqlite3
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any


class EventStore:
    def __init__(self, db_path: str = ".boukensha/events.db"):
        self.db_path = db_path
        self._ensure_db_exists()

    def _ensure_db_exists(self):
        """Create database and tables if they don't exist."""
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create events table if it doesn't exist
        cursor.execute("""
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
        """)

        # Create indexes for faster queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_session_phase
            ON events(session_id, phase)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_session_turn
            ON events(session_id, turn)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_actor
            ON events(session_id, actor)
        """)

        # Set pragmas for better performance
        cursor.execute("PRAGMA journal_mode = WAL")
        cursor.execute("PRAGMA synchronous = NORMAL")
        cursor.execute("PRAGMA mmap_size = " + str(256 * 1024 * 1024))
        cursor.execute("PRAGMA busy_timeout = 5000")
        cursor.execute("PRAGMA foreign_keys = ON")

        conn.commit()
        conn.close()

    def log_event(self, event: Dict[str, Any]) -> bool:
        """Log a single event from the agent."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            session_id = event.get("session_id")
            phase = event.get("phase")

            if not session_id or not phase:
                return False

            actor = event.get("actor")
            turn = event.get("turn") or event.get("n")
            iteration = event.get("iteration")
            at = event.get("at", datetime.utcnow().isoformat())
            tool = event.get("name") or event.get("tool")
            ok_val = event.get("ok")
            ok = 1 if ok_val is True else (0 if ok_val is False else ok_val)
            input_tokens = event.get("input_tokens")
            output_tokens = event.get("output_tokens")
            cache_read_tokens = event.get("cache_read_input_tokens")
            cache_write_tokens = event.get("cache_creation_input_tokens")
            cost_usd = event.get("cost_usd")
            model = event.get("model")
            provider = event.get("provider")
            tools_sent = event.get("tools_sent")
            room = event.get("room")
            details = json.dumps(event)

            cursor.execute("""
                INSERT INTO events (
                    session_id, actor, turn, iteration, at, phase, tool, ok,
                    input_tokens, output_tokens, cache_read_tokens, cache_write_tokens,
                    tools_sent, cost_usd, model, provider, room, details
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                session_id, actor, turn, iteration, at, phase, tool, ok,
                input_tokens, output_tokens, cache_read_tokens, cache_write_tokens,
                tools_sent, cost_usd, model, provider, room, details
            ])

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            print(f"Error logging event: {e}")
            return False

    def log_from_jsonl(self, session_file: str) -> int:
        """Load all events from a JSONL session file."""
        if not os.path.exists(session_file):
            return 0

        count = 0
        try:
            with open(session_file) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        event = json.loads(line)
                        if self.log_event(event):
                            count += 1
                    except json.JSONDecodeError:
                        continue

            return count
        except Exception as e:
            print(f"Error loading JSONL file: {e}")
            return 0

    def get_session_cost(self, session_id: str) -> float:
        """Get total cost for a session."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT COALESCE(SUM(cost_usd), 0) as total
                FROM events
                WHERE session_id = ? AND phase = 'response'
            """, [session_id])

            result = cursor.fetchone()
            conn.close()

            return float(result[0]) if result else 0.0
        except Exception as e:
            print(f"Error getting session cost: {e}")
            return 0.0

    def get_session_stats(self, session_id: str) -> Dict[str, Any]:
        """Get statistics for a session."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    COUNT(DISTINCT turn) as turns,
                    COALESCE(SUM(input_tokens), 0) as input_tokens,
                    COALESCE(SUM(output_tokens), 0) as output_tokens,
                    COALESCE(SUM(cost_usd), 0) as total_cost
                FROM events
                WHERE session_id = ? AND phase = 'response'
            """, [session_id])

            row = cursor.fetchone()
            conn.close()

            if row:
                return {
                    "turns": row[0],
                    "input_tokens": row[1],
                    "output_tokens": row[2],
                    "total_cost": row[3]
                }
            return {"turns": 0, "input_tokens": 0, "output_tokens": 0, "total_cost": 0}
        except Exception as e:
            print(f"Error getting session stats: {e}")
            return {}


if __name__ == "__main__":
    store = EventStore()
    session_file = ".boukensha/sessions/example-session.jsonl"
    count = store.log_from_jsonl(session_file)
    print(f"Loaded {count} events")
