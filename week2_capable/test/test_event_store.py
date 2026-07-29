"""Test suite for EventStore and Analytics."""

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from boukensha.observability import EventStore, Analytics


class TestEventStore(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmpdir.name) / "events.db"

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_event_store_creates_schema(self):
        """EventStore should create events table and indexes."""
        store = EventStore(str(self.db_path))
        try:
            # Check table exists
            tables = store.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='events'"
            ).fetchall()
            self.assertEqual(len(tables), 1)

            # Check indexes
            indexes = store.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
            ).fetchall()
            self.assertGreaterEqual(len(indexes), 3)
        finally:
            store.close()

    def test_event_insert_extracts_fields(self):
        """EventStore should extract and insert event fields."""
        store = EventStore(str(self.db_path))
        try:
            event = {
                "phase": "response",
                "session_id": "test-session",
                "turn": 1,
                "actor": "scout",
                "at": "2026-07-29T10:00:00+00:00",
                "input_tokens": 1500,
                "output_tokens": 200,
                "cost_usd": 0.05,
                "provider": "anthropic",
                "model": "claude-3-5-sonnet",
            }

            store._insert(event)

            # Read back
            row = store.conn.execute(
                "SELECT phase, session_id, turn, actor, input_tokens, output_tokens, cost_usd "
                "FROM events WHERE session_id = ?",
                ("test-session",),
            ).fetchone()

            self.assertIsNotNone(row)
            self.assertEqual(row[0], "response")
            self.assertEqual(row[1], "test-session")
            self.assertEqual(row[2], 1)
            self.assertEqual(row[3], "scout")
            self.assertEqual(row[4], 1500)
            self.assertEqual(row[5], 200)
            self.assertAlmostEqual(row[6], 0.05)
        finally:
            store.close()

    def test_rebuild_from_jsonl(self):
        """EventStore should rebuild from a JSONL file."""
        # Create a test JSONL file
        jsonl_file = Path(self.tmpdir.name) / "test.jsonl"
        events = [
            {"phase": "session_start", "session_id": "test-1", "at": "2026-07-29T10:00:00+00:00"},
            {
                "phase": "response",
                "session_id": "test-1",
                "turn": 1,
                "input_tokens": 2000,
                "output_tokens": 100,
                "cost_usd": 0.04,
                "at": "2026-07-29T10:00:05+00:00",
            },
            {
                "phase": "response",
                "session_id": "test-1",
                "turn": 1,
                "input_tokens": 1800,
                "output_tokens": 150,
                "cost_usd": 0.05,
                "at": "2026-07-29T10:00:10+00:00",
            },
        ]
        jsonl_file.write_text("\n".join(json.dumps(e) for e in events))

        # Rebuild
        store = EventStore.rebuild_from_jsonl(str(jsonl_file), str(self.db_path))
        try:
            count = store.conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            self.assertEqual(count, 3)

            # Check response events are there
            responses = store.conn.execute(
                "SELECT COUNT(*) FROM events WHERE phase = 'response'"
            ).fetchone()[0]
            self.assertEqual(responses, 2)
        finally:
            store.close()


class TestAnalytics(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmpdir.name) / "events.db"
        self._setup_test_data()

    def tearDown(self):
        self.tmpdir.cleanup()

    def _setup_test_data(self):
        """Create a test database with sample events."""
        store = EventStore(str(self.db_path))
        try:
            # Simulate a 3-turn session
            for turn in range(1, 4):
                for iteration in range(1, 3):  # 2 iterations per turn
                    event = {
                        "phase": "response",
                        "session_id": "baseline-1",
                        "turn": turn,
                        "iteration": iteration,
                        "actor": "scout",
                        "at": f"2026-07-29T10:00:{turn*10+iteration}+00:00",
                        "input_tokens": 2000 + turn * 100,
                        "output_tokens": 200 + turn * 20,
                        "cache_read_tokens": turn * 50 if turn > 1 else 0,
                        "cache_write_tokens": 500 if turn == 1 else 0,
                        "cost_usd": 0.05 + turn * 0.01,
                        "tools_sent": 26,
                        "provider": "anthropic",
                        "model": "claude-3-5-sonnet",
                    }
                    store._insert(event)
        finally:
            store.close()

    def test_cost_summary(self):
        """Analytics should compute cost summary."""
        analytics = Analytics(str(self.db_path))
        try:
            summary = analytics.cost_summary("baseline-1")

            self.assertGreater(summary.turns, 0)
            self.assertGreater(summary.total_usd, 0)
            self.assertGreater(summary.cost_per_turn_usd, 0)
            self.assertGreater(summary.input_cost_usd, 0)
        finally:
            analytics.close()

    def test_tokens_per_turn(self):
        """Analytics should break down tokens per turn."""
        analytics = Analytics(str(self.db_path))
        try:
            per_turn = analytics.tokens_per_turn("baseline-1")

            self.assertEqual(len(per_turn), 3)  # 3 turns
            self.assertEqual(per_turn[0]["turn"], 1)
            self.assertGreater(per_turn[0]["input_tokens"], 0)
            self.assertGreater(per_turn[0]["iterations"], 0)
        finally:
            analytics.close()

    def test_token_breakdown(self):
        """Analytics should estimate token breakdown."""
        analytics = Analytics(str(self.db_path))
        try:
            breakdown = analytics.token_breakdown("baseline-1")

            self.assertGreater(breakdown.total_input_tokens, 0)
            self.assertGreater(breakdown.total_output_tokens, 0)
            self.assertGreater(breakdown.schema_tokens, 0)
            # Cache read should be present in turns 2-3
            self.assertGreater(breakdown.cache_read_tokens, 0)
        finally:
            analytics.close()

    def test_schema_overhead(self):
        """Analytics should compute schema overhead."""
        analytics = Analytics(str(self.db_path))
        try:
            overhead = analytics.schema_overhead("baseline-1")

            self.assertGreater(overhead["tools_sent"], 0)
            self.assertGreater(overhead["schema_tokens"], 0)
            self.assertGreater(overhead["percent_of_input"], 0)
            self.assertLess(overhead["percent_of_input"], 100)
        finally:
            analytics.close()

    def test_cache_effectiveness(self):
        """Analytics should measure cache hit rate."""
        analytics = Analytics(str(self.db_path))
        try:
            cache = analytics.cache_effectiveness("baseline-1")

            self.assertGreater(cache["cache_read_tokens"], 0)
            self.assertGreater(cache["hit_rate"], 0)
            self.assertLess(cache["hit_rate"], 100)
        finally:
            analytics.close()

    def test_tool_usage(self):
        """Analytics should report tool usage stats."""
        # Add tool results
        store = EventStore(str(self.db_path))
        try:
            for i in range(3):
                event = {
                    "phase": "tool_result",
                    "session_id": "baseline-1",
                    "name": "look",
                    "ok": 1,
                    "at": "2026-07-29T10:00:30+00:00",
                }
                store._insert(event)
        finally:
            store.close()

        analytics = Analytics(str(self.db_path))
        try:
            tools = analytics.tool_usage("baseline-1")

            self.assertEqual(len(tools), 1)
            self.assertEqual(tools[0]["tool"], "look")
            self.assertEqual(tools[0]["call_count"], 3)
            self.assertEqual(tools[0]["success_count"], 3)
        finally:
            analytics.close()


if __name__ == "__main__":
    unittest.main()
