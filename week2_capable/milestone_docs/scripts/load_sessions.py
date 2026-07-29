#!/usr/bin/env python3
"""Load all sessions from JSONL files into the database."""

import os
from pathlib import Path
from event_store import EventStore


def load_all_sessions():
    """Load all sessions from fixture and .boukensha/sessions directory."""
    store = EventStore()

    total_loaded = 0
    sessions_dir = Path(".boukensha/sessions")
    sessions_dir.mkdir(parents=True, exist_ok=True)

    # Load fixture if it exists
    fixture_path = Path("test/fixtures/sessions/baseline_fixture.jsonl")
    if fixture_path.exists():
        print(f"Loading fixture: {fixture_path}")
        count = store.log_from_jsonl(str(fixture_path))
        print(f"  ✓ Loaded {count} events")
        total_loaded += count

    # Load all sessions from .boukensha/sessions/
    session_files = sorted(sessions_dir.glob("*.jsonl"))
    if session_files:
        print(f"\nLoading sessions from {sessions_dir}:")
        for session_file in session_files:
            print(f"  {session_file.name}...", end=" ", flush=True)
            count = store.log_from_jsonl(str(session_file))
            print(f"✓ {count} events")
            total_loaded += count

            # Show stats
            session_id = session_file.stem
            stats = store.get_session_stats(session_id)
            if stats.get("turns"):
                print(f"    Turns: {stats['turns']}, Cost: ${stats['total_cost']:.4f}")
    else:
        print(f"No sessions found in {sessions_dir}")

    print(f"\n✓ Total: {total_loaded} events loaded")
    return total_loaded


if __name__ == "__main__":
    load_all_sessions()
