#!/usr/bin/env python3
"""Demonstrate M7 compression metrics dashboard with example data."""

import json
import tempfile
from pathlib import Path

print("=" * 70)
print("M7 Compression Metrics Dashboard - Live Demo")
print("=" * 70)
print()

# Create a demo JSONL with compression events
demo_events = [
    {"phase": "session_start", "session_id": "demo-m7", "at": "2026-08-04T15:00:00Z"},
    {"phase": "turn", "n": 1, "session_id": "demo-m7", "at": "2026-08-04T15:00:05Z"},
    {"phase": "tokens.compressed", "tool": "look", "before_tokens": 412, "after_tokens": 24, "saved": 388, "room_id": "room_market_sq", "visit_count": 1, "session_id": "demo-m7"},
    {"phase": "tokens.compressed", "tool": "look", "before_tokens": 380, "after_tokens": 22, "saved": 358, "room_id": "room_temple", "visit_count": 1, "session_id": "demo-m7"},
    {"phase": "tokens.compressed", "tool": "look", "before_tokens": 395, "after_tokens": 20, "saved": 375, "room_id": "room_garden", "visit_count": 1, "session_id": "demo-m7"},
    {"phase": "tokens.compressed", "tool": "look", "before_tokens": 420, "after_tokens": 25, "saved": 395, "room_id": "room_fountain", "visit_count": 1, "session_id": "demo-m7"},
]

with tempfile.TemporaryDirectory() as tmpdir:
    session_file = Path(tmpdir) / "demo-m7.jsonl"
    with open(session_file, "w") as f:
        for event in demo_events:
            f.write(json.dumps(event) + "\n")

    # Analyze like log_viz would
    compressions = []
    total_saved = 0
    total_before = 0

    with open(session_file) as f:
        for line in f:
            event = json.loads(line)
            if event.get("phase") == "tokens.compressed":
                before = event["before_tokens"]
                after = event["after_tokens"]
                saved = event["saved"]

                compressions.append({
                    "tool": event["tool"],
                    "before_tokens": before,
                    "after_tokens": after,
                    "saved_tokens": saved,
                    "room_id": event["room_id"],
                    "visit_count": event["visit_count"],
                    "compression_ratio": (saved / before * 100) if before > 0 else 0,
                })

                total_saved += saved
                total_before += before

    avg_ratio = (total_saved / total_before * 100) if total_before > 0 else 0
    avg_savings = total_saved // len(compressions) if compressions else 0

    # Display HTML mockup
    print("DASHBOARD SECTION: M7 Compression Metrics")
    print("=" * 70)
    print()
    print("Metrics Grid:")
    print(f"  📊 Compressions Triggered: {len(compressions)}")
    print(f"  💾 Total Tokens Saved: {total_saved}")
    print(f"  📈 Avg Compression Ratio: {avg_ratio:.1f}%")
    print(f"  ⚡ Avg Savings/Compression: {avg_savings} tokens")
    print()
    print("Compression Details Table:")
    print("-" * 100)
    print(f"{'Room ID':<20} {'Tool':<15} {'Visit':<8} {'Before':<10} {'After':<10} {'Saved':<10} {'Ratio':<8}")
    print("-" * 100)
    for comp in compressions:
        room_display = comp["room_id"].replace("room_", "").ljust(20)
        tool = comp["tool"][:15].ljust(15)
        visit = f"#{comp['visit_count']}".ljust(8)
        before = str(comp["before_tokens"]).ljust(10)
        after = str(comp["after_tokens"]).ljust(10)
        saved = str(comp["saved_tokens"]).ljust(10)
        ratio = f"{comp['compression_ratio']:.0f}%".ljust(8)
        print(f"{room_display} {tool} {visit} {before} {after} {saved} {ratio}")
    print("-" * 100)
    print()
    print("Status Message:")
    print(f"  ✅ M7 compression active: room revisits compressed {avg_ratio:.0f}% on average.")
    print()
    print("=" * 70)
    print()
    print("HTML/ERB Implementation Details:")
    print()
    print("1. Metrics Grid")
    print("   ├─ Compressions Triggered: <%= @compression_metrics[:total_compressions] %>")
    print("   ├─ Total Tokens Saved: <%= fmt_tokens(@compression_metrics[:total_tokens_saved]) %>")
    print("   ├─ Avg Compression Ratio: <%= @compression_metrics[:average_compression_ratio] %>%")
    print("   └─ Avg Savings/Compression: <%= @compression_metrics[:average_savings_per_compression] %> tokens")
    print()
    print("2. Details Table with columns:")
    print("   ├─ Room ID (shortened with ellipsis)")
    print("   ├─ Tool name")
    print("   ├─ Visit count (#)")
    print("   ├─ Before tokens")
    print("   ├─ After tokens")
    print("   ├─ Saved tokens (bolded)")
    print("   └─ Compression ratio (styled with blue background)")
    print()
    print("3. Status Message")
    print("   └─ Shows compression active with average ratio")
    print()
    print("4. Styling")
    print("   ├─ Purple left border (§3.3 visual indicator)")
    print("   ├─ Blue ratio badges with rounded corners")
    print("   ├─ Info callout for sessions without compressions")
    print("   └─ Responsive design for mobile")
    print()
    print("=" * 70)
    print()
    print("✅ M7 Compression Dashboard is ready!")
    print()
    print("Integration points:")
    print("  • analytics.rb: new compression_metrics() method ✓")
    print("  • app.rb: endpoint loads @compression_metrics ✓")
    print("  • tokens.erb: section displays metrics and table ✓")
    print("  • CSS: styling for purple accent and ratio badges ✓")
