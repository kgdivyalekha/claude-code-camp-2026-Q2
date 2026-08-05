#!/usr/bin/env python3
"""Run a test session to capture M7 compression metrics."""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "week2_capable" / "src"))

from boukensha.run import run
from datetime import datetime
import json

# Run a short agent task that explores and revisits rooms
print("=" * 70)
print("M7 Compression Test Session")
print("=" * 70)
print()
print("Starting agent task: explore fountain and revisit rooms")
print()

try:
    result = run(
        task="Explore the fountain area. Look around, move to different rooms, and come back to check the fountain again. Make sure to revisit at least 2 rooms.",
        model="claude-haiku-4-5",
        backend="anthropic",
        max_output_tokens=512,
    )

    print()
    print("Agent completed task:")
    print(result[:200] + "..." if len(result) > 200 else result)
    print()

    # Find the session file just created
    sessions_dir = Path(".boukensha/sessions")
    if sessions_dir.exists():
        session_files = sorted(sessions_dir.glob("*.jsonl"))
        if session_files:
            latest_session = session_files[-1]
            print(f"✓ Session recorded: {latest_session.name}")
            print()

            # Analyze compression metrics
            compression_events = []
            total_saved = 0
            look_calls = []

            with open(latest_session) as f:
                for line in f:
                    event = json.loads(line)
                    if event.get("phase") == "tokens.compressed":
                        compression_events.append(event)
                        total_saved += event.get("saved", 0)
                    elif event.get("phase") == "tool_call" and event.get("name") == "tbamud__look":
                        look_calls.append(event)

            print("=" * 70)
            print("M7 COMPRESSION METRICS")
            print("=" * 70)
            print()
            print(f"Look commands executed: {len(look_calls)}")
            print(f"Compression events triggered: {len(compression_events)}")
            print(f"Total tokens saved: {total_saved}")
            print()

            if compression_events:
                print("Compression details:")
                print("-" * 70)
                for i, evt in enumerate(compression_events, 1):
                    before = evt.get("before_tokens", 0)
                    after = evt.get("after_tokens", 0)
                    saved = evt.get("saved", 0)
                    visit_count = evt.get("visit_count", "?")
                    room_id = evt.get("room_id", "unknown")

                    if before > 0:
                        ratio = (saved / before * 100) if before > 0 else 0
                        print(f"{i}. Room visit #{visit_count}")
                        print(f"   {before:4d} → {after:4d} tokens ({saved:3d} saved, {ratio:.0f}% reduction)")
                        print(f"   Room: {room_id}")
                        print()
                print("-" * 70)
                print(f"✅ M7 compression is WORKING!")
                print(f"   Average savings per compression: {total_saved // len(compression_events) if compression_events else 0} tokens")
            else:
                print("⚠️  No compression events captured")
                print("   (Rooms may not have been revisited in this session)")
                print()
                print("To trigger compression:")
                print("  1. Agent explores room A (look)")
                print("  2. Agent moves away")
                print("  3. Agent returns and looks at room A again")
                print("  4. Second look should compress")

            print()
            print(f"Full session: .boukensha/sessions/{latest_session.name}")

except Exception as e:
    print(f"❌ Error running session: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
