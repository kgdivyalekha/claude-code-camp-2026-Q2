#!/usr/bin/env python3
"""Direct test of M7 compression without API calls.

Simulates room revisits and verifies compression metrics are logged.
"""

import sys
import json
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "week2_capable" / "src"))

from boukensha.tokens.compress import CompressionHooks
from boukensha.world.db import WorldDB
from boukensha.logger import Logger
from datetime import datetime

print("=" * 70)
print("M7 Compression Direct Test")
print("=" * 70)
print()

def create_look_output(name, exits, description):
    """Create realistic look output."""
    exits_str = ", ".join(exits)
    return {
        "content": f"""{name}

{description}

[ Exits: {exits_str} ]
""",
        "ok": True,
    }

# Create temp world.db and logger
with tempfile.TemporaryDirectory() as tmpdir:
    db_path = Path(tmpdir) / "world.db"
    log_path = Path(tmpdir) / "test.jsonl"

    world_db = WorldDB(str(db_path))

    # Create a logger that captures events
    logger = Logger(log=str(log_path), snapshot={"test": True})
    compression = CompressionHooks(world_db, logger=logger)

    print("Scenario: Agent explores fountain area, revisits rooms")
    print()

    # Simulate exploration sequence
    rooms_visited = [
        ("Market Square", ["north", "east", "south"], "A busy marketplace with merchants and travelers."),
        ("Temple of Water", ["north", "west"], "A serene temple with a central fountain."),
        ("Garden Path", ["south", "east", "north"], "A winding path through blooming gardens."),
    ]

    turn = 1
    look_count = 0

    print("Turn 1: Initial exploration")
    print("-" * 70)

    # Import NavigationTracker to populate world.db
    from boukensha.observability.navigation import NavigationTracker
    nav_tracker = NavigationTracker(world_db)

    for room_name, exits, description in rooms_visited:
        look_count += 1
        logger.turn(turn)

        look_output_str = f"""{room_name}

{description}

[ Exits: {", ".join(exits)} ]
"""

        print(f"  Look #{look_count}: {room_name}")

        # First, NavigationTracker adds room to world.db
        room_id = nav_tracker.on_look_result(look_output_str, actor="agent")
        print(f"    ✓ Room added to world.db: {room_id}")

        # Then compression checks it (will not compress first visit)
        look_output = {"content": look_output_str, "ok": True}
        result = compression.compress_repeat_rooms(
            actor=None,
            name="look",
            args={},
            result=look_output.copy(),
        )

        if result is not None:
            print(f"    ⚠️  Compressed (unexpected on first visit)")
        else:
            print(f"    ✓ First visit, no compression")

    print()
    print("Turn 2: Revisit rooms (compression should trigger)")
    print("-" * 70)
    turn = 2
    logger.turn(turn)

    for room_name, exits, description in rooms_visited:
        look_count += 1

        look_output_str = f"""{room_name}

{description}

[ Exits: {", ".join(exits)} ]
"""

        print(f"  Look #{look_count}: {room_name}")

        # NavigationTracker updates visit_count
        room_id = nav_tracker.on_look_result(look_output_str, actor="agent")

        # Compression should trigger now
        look_output = {"content": look_output_str, "ok": True}
        result = compression.compress_repeat_rooms(
            actor=None,
            name="look",
            args={},
            result=look_output.copy(),
        )

        if result is not None:
            content = result["content"]
            original_tokens = len(look_output_str) // 4
            compressed_tokens = len(content) // 4
            saved = original_tokens - compressed_tokens
            ratio = (saved / original_tokens * 100) if original_tokens > 0 else 0
            print(f"    ✅ Compressed! {original_tokens} → {compressed_tokens} tokens ({saved} saved, {ratio:.0f}%)")
            print(f"       Summary: {content[:60]}...")
        else:
            room_data = world_db.get_room(room_id)
            vc = room_data["visit_count"] if room_data else "unknown"
            print(f"    ⚠️  No compression (visit_count={vc})")

    logger.close()

    # Analyze the log file
    print()
    print("=" * 70)
    print("Compression Events in Log")
    print("=" * 70)
    print()

    compression_events = []
    total_saved = 0

    with open(log_path) as f:
        for line in f:
            if line.strip():
                event = json.loads(line)
                if event.get("phase") == "tokens.compressed":
                    compression_events.append(event)
                    total_saved += event.get("saved", 0)

    print(f"Events captured: {len(compression_events)}")
    print(f"Total tokens saved: {total_saved}")
    print()

    if compression_events:
        print("Compression details:")
        print("-" * 70)
        for i, evt in enumerate(compression_events, 1):
            before = evt.get("before_tokens", 0)
            after = evt.get("after_tokens", 0)
            saved = evt.get("saved", 0)
            room_id = evt.get("room_id", "unknown")
            visit_count = evt.get("visit_count", "?")

            if before > 0:
                ratio = (saved / before * 100)
                print(f"{i}. Room {room_id} (visit #{visit_count})")
                print(f"   Before: {before:4d} tokens")
                print(f"   After:  {after:4d} tokens")
                print(f"   Saved:  {saved:3d} tokens ({ratio:.0f}% reduction)")
                print()

        print("-" * 70)
        print()
        print("✅ M7 COMPRESSION SUCCESS!")
        print()
        print(f"Summary:")
        print(f"  • Rooms revisited: {len(compression_events)}")
        print(f"  • Total tokens saved: {total_saved}")
        print(f"  • Average savings per revisit: {total_saved // len(compression_events)} tokens")
        print(f"  • Average compression ratio: ~{total_saved / (total_saved + sum(e.get('after_tokens', 1) for e in compression_events)) * 100:.0f}%")
    else:
        print("❌ No compression events captured")
        print("Check that rooms are being added to world.db and revisited")

print()
print("=" * 70)
