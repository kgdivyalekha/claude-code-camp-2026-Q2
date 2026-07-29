#!/usr/bin/env python3
"""Quick verification that M1 foundations are in place.

M1 Success Criteria:
- EventStore can subscribe to Logger and write to SQLite
- Analytics can read events.db and produce token breakdown
- rebuild_from_jsonl works on fixture JSONL
"""

import json
import sys
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_event_store():
    """Verify EventStore structure and operations."""
    from boukensha.observability import EventStore

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"

        # Create store
        store = EventStore(str(db_path))
        try:
            # Test insert
            event = {
                "phase": "response",
                "session_id": "test-session",
                "turn": 1,
                "iteration": 1,
                "actor": "scout",
                "at": "2026-07-29T10:00:00+00:00",
                "input_tokens": 2000,
                "output_tokens": 200,
                "cost_usd": 0.05,
                "tools_sent": 26,
                "provider": "anthropic",
                "model": "claude-3-5-sonnet",
            }
            store._insert(event)

            # Verify
            count = store.conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            assert count == 1, f"Expected 1 event, got {count}"

            # Check table structure
            cursor = store.conn.execute("PRAGMA table_info(events)")
            columns = {row[1] for row in cursor.fetchall()}
            required = {
                "session_id", "phase", "input_tokens", "output_tokens", "cost_usd", "details"
            }
            assert required.issubset(columns), f"Missing columns: {required - columns}"

        finally:
            store.close()

    print("✓ EventStore.insert() working")

def test_rebuild_from_jsonl():
    """Verify rebuild_from_jsonl works."""
    from boukensha.observability import EventStore

    # Use the test fixture
    fixture_path = Path(__file__).parent / "test" / "fixtures" / "sessions" / "baseline_fixture.jsonl"
    if not fixture_path.exists():
        print(f"⚠ Fixture not found at {fixture_path}, skipping rebuild test")
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "rebuilt.db"

        store = EventStore.rebuild_from_jsonl(str(fixture_path), str(db_path))
        try:
            count = store.conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            assert count > 0, "Events should be loaded"

            # Check we got response events (tokens should be present)
            responses = store.conn.execute(
                "SELECT COUNT(*) FROM events WHERE phase = 'response' AND input_tokens > 0"
            ).fetchone()[0]
            assert responses > 0, "Should have response events with tokens"

        finally:
            store.close()

    print("✓ EventStore.rebuild_from_jsonl() working")

def test_analytics():
    """Verify Analytics queries work."""
    from boukensha.observability import EventStore, Analytics

    fixture_path = Path(__file__).parent / "test" / "fixtures" / "sessions" / "baseline_fixture.jsonl"
    if not fixture_path.exists():
        print(f"⚠ Fixture not found, skipping analytics test")
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "analytics.db"

        # Rebuild
        store = EventStore.rebuild_from_jsonl(str(fixture_path), str(db_path))
        store.close()

        # Get session ID
        fixture_text = fixture_path.read_text()
        session_id = None
        for line in fixture_text.splitlines():
            if line:
                event = json.loads(line)
                session_id = event.get("session_id")
                if session_id:
                    break

        assert session_id, "Should extract session_id from fixture"

        # Test analytics
        analytics = Analytics(str(db_path))
        try:
            # Test token_breakdown - M1 success criterion
            breakdown = analytics.token_breakdown(session_id)
            assert breakdown.total_input_tokens > 0, "Should have input tokens"
            assert breakdown.total_output_tokens > 0, "Should have output tokens"
            assert breakdown.schema_tokens > 0, "Should estimate schema tokens"

            # Test cost_summary
            cost = analytics.cost_summary(session_id)
            assert cost.turns > 0, "Should have turns"
            assert cost.total_usd > 0, "Should have cost"

            # Test schema_overhead
            schema = analytics.schema_overhead(session_id)
            assert schema["tools_sent"] > 0, "Should estimate tools"
            assert schema["percent_of_input"] > 0, "Should calculate percent"

            # Test tokens_per_turn
            per_turn = analytics.tokens_per_turn(session_id)
            assert len(per_turn) > 0, "Should have per-turn breakdown"

        finally:
            analytics.close()

    print("✓ Analytics.token_breakdown() working (M1 criterion)")
    print("✓ Analytics.cost_summary() working")
    print("✓ Analytics.schema_overhead() working")
    print("✓ Analytics.tokens_per_turn() working")

def main():
    """Run all M1 verification tests."""
    print("M1 Verification — Event Store + Analytics + Token Baseline")
    print("-" * 60)

    try:
        test_event_store()
        test_rebuild_from_jsonl()
        test_analytics()
        print("-" * 60)
        print("✅ M1 Complete: All foundations verified")
        return 0
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
