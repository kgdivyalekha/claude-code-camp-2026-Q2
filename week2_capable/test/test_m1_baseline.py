"""M1 validation: Event store + Analytics + Token baseline.

This test verifies that we can:
1. Rebuild events.db from a JSONL session
2. Run analytics queries to measure token usage
3. Produce a token baseline report (the M1 deliverable)
"""

import json
import tempfile
import unittest
from pathlib import Path

from boukensha.observability import EventStore, Analytics


class TestM1Baseline(unittest.TestCase):
    """M1 Success Criteria: `token_breakdown()` on a real week 1 session works."""

    @classmethod
    def setUpClass(cls):
        """Set up test fixture."""
        cls.fixture_path = Path(__file__).parent / "fixtures" / "sessions" / "baseline_fixture.jsonl"
        if not cls.fixture_path.exists():
            raise FileNotFoundError(f"Fixture not found: {cls.fixture_path}")

    def test_m1_event_store_rebuild(self):
        """M1: EventStore can rebuild from JSONL."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "events.db"

            # Rebuild from fixture
            store = EventStore.rebuild_from_jsonl(str(self.fixture_path), str(db_path))
            try:
                event_count = store.conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
                self.assertGreater(event_count, 0, "Events should be loaded from JSONL")

                # Check structure
                response_count = store.conn.execute(
                    "SELECT COUNT(*) FROM events WHERE phase = 'response'"
                ).fetchone()[0]
                self.assertGreater(response_count, 0, "Should have response events")

                turn_count = store.conn.execute(
                    "SELECT COUNT(DISTINCT turn) FROM events"
                ).fetchone()[0]
                self.assertGreater(turn_count, 0, "Should have turn events")
            finally:
                store.close()

    def test_m1_token_breakdown(self):
        """M1: Analytics can compute token breakdown."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "events.db"
            EventStore.rebuild_from_jsonl(str(self.fixture_path), str(db_path))

            analytics = Analytics(str(db_path))
            try:
                # Get session ID from fixture
                fixture_data = self.fixture_path.read_text()
                session_id = None
                for line in fixture_data.splitlines():
                    if line:
                        event = json.loads(line)
                        session_id = event.get("session_id")
                        if session_id:
                            break

                self.assertIsNotNone(session_id, "Should extract session_id from fixture")

                # Test token_breakdown - the M1 success criterion
                breakdown = analytics.token_breakdown(session_id)
                self.assertIsNotNone(breakdown)
                self.assertGreater(breakdown.total_input_tokens, 0, "Should have input tokens")
                self.assertGreater(breakdown.total_output_tokens, 0, "Should have output tokens")
                self.assertGreater(breakdown.schema_tokens, 0, "Should estimate schema tokens")

                print(f"\n=== M1 Token Breakdown ===")
                print(f"Total input:  {breakdown.total_input_tokens:,} tokens")
                print(f"Total output: {breakdown.total_output_tokens:,} tokens")
                print(f"Schema (est): {breakdown.schema_tokens:,} tokens")
                print(f"History (est): {breakdown.history_tokens:,} tokens")
                print(f"Results (est): {breakdown.result_tokens:,} tokens")

            finally:
                analytics.close()

    def test_m1_cost_summary(self):
        """M1: Analytics can compute cost summary."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "events.db"
            EventStore.rebuild_from_jsonl(str(self.fixture_path), str(db_path))

            analytics = Analytics(str(db_path))
            try:
                fixture_data = self.fixture_path.read_text()
                session_id = None
                for line in fixture_data.splitlines():
                    if line:
                        event = json.loads(line)
                        session_id = event.get("session_id")
                        if session_id:
                            break

                cost = analytics.cost_summary(session_id)
                self.assertIsNotNone(cost)
                self.assertGreater(cost.turns, 0, "Should have turns")
                self.assertGreater(cost.total_usd, 0, "Should have cost")

                print(f"\n=== M1 Cost Summary ===")
                print(f"Total cost: ${cost.total_usd:.4f}")
                print(f"Turns: {cost.turns}")
                print(f"Cost per turn: ${cost.cost_per_turn_usd:.4f}")

            finally:
                analytics.close()

    def test_m1_schema_overhead(self):
        """M1: Measure schema overhead (§3.2 optimization lever)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "events.db"
            EventStore.rebuild_from_jsonl(str(self.fixture_path), str(db_path))

            analytics = Analytics(str(db_path))
            try:
                fixture_data = self.fixture_path.read_text()
                session_id = None
                for line in fixture_data.splitlines():
                    if line:
                        event = json.loads(line)
                        session_id = event.get("session_id")
                        if session_id:
                            break

                schema = analytics.schema_overhead(session_id)
                self.assertGreater(schema["tools_sent"], 0, "Should estimate tools sent")
                self.assertGreater(schema["schema_tokens"], 0, "Should estimate schema tokens")
                self.assertGreater(schema["percent_of_input"], 0, "Should calculate percent")

                print(f"\n=== M1 Schema Overhead (§3.2 lever) ===")
                print(f"Tools sent: {schema['tools_sent']}")
                print(f"Schema tokens: {schema['schema_tokens']:,}")
                print(f"Percent of input: {schema['percent_of_input']}%")

                # Plan says schema should be ~30% of input (2000-2500 of ~7000-8000)
                self.assertGreater(schema["percent_of_input"], 10, "Schema should be significant")

            finally:
                analytics.close()

    def test_m1_cache_effectiveness(self):
        """M1: Measure cache effectiveness (§3.5 optimization lever)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "events.db"
            EventStore.rebuild_from_jsonl(str(self.fixture_path), str(db_path))

            analytics = Analytics(str(db_path))
            try:
                fixture_data = self.fixture_path.read_text()
                session_id = None
                for line in fixture_data.splitlines():
                    if line:
                        event = json.loads(line)
                        session_id = event.get("session_id")
                        if session_id:
                            break

                cache = analytics.cache_effectiveness(session_id)
                self.assertIsNotNone(cache)
                self.assertGreater(cache["hit_rate"], 0, "Should have cache hits in fixture")

                print(f"\n=== M1 Cache Effectiveness (§3.5 lever) ===")
                print(f"Cache read tokens: {cache['cache_read_tokens']:,}")
                print(f"Cache hit rate: {cache['hit_rate']}%")
                print(f"Cost saving: ${cache['cost_saving_usd']:.4f}")

            finally:
                analytics.close()

    def test_m1_tokens_per_turn(self):
        """M1: Break down tokens per turn."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "events.db"
            EventStore.rebuild_from_jsonl(str(self.fixture_path), str(db_path))

            analytics = Analytics(str(db_path))
            try:
                fixture_data = self.fixture_path.read_text()
                session_id = None
                for line in fixture_data.splitlines():
                    if line:
                        event = json.loads(line)
                        session_id = event.get("session_id")
                        if session_id:
                            break

                per_turn = analytics.tokens_per_turn(session_id)
                self.assertGreater(len(per_turn), 0, "Should have per-turn breakdown")

                print(f"\n=== M1 Tokens Per Turn ===")
                for row in per_turn:
                    print(
                        f"Turn {row['turn']}: {row['input_tokens']:,} input, "
                        f"{row['output_tokens']} output, {row['iterations']} iterations"
                    )

            finally:
                analytics.close()


if __name__ == "__main__":
    unittest.main()
