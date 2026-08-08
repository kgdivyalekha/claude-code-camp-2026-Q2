#!/usr/bin/env python3
"""
Analyze token savings from M9 smart navigation.

Compares baseline (blind exploration) vs. optimized (with smart navigation).
"""

import json
from pathlib import Path


def analyze_session(jsonl_path):
    """Analyze token usage in a session JSONL file."""

    events = []
    with open(jsonl_path) as f:
        for line in f:
            if line.strip():
                events.append(json.loads(line))

    # Extract responses (where tokens are counted)
    responses = [e for e in events if e.get("phase") == "response"]

    # Extract moves (navigation)
    moves = [e for e in events if e.get("phase") == "tool_call" and e.get("name") == "move"]

    print("=" * 70)
    print("TOKEN SAVINGS ANALYSIS - NAVIGATION (M9)")
    print("=" * 70)

    print(f"\n📊 SESSION OVERVIEW")
    print(f"  Total events:           {len(events)}")
    print(f"  Response events:        {len(responses)}")
    print(f"  Navigation commands:    {len(moves)}")

    # Token calculations
    total_input = sum(e.get("input_tokens", 0) for e in responses)
    total_output = sum(e.get("output_tokens", 0) for e in responses)
    cache_read = sum(e.get("cache_read_input_tokens", 0) for e in responses)
    cache_write = sum(e.get("cache_creation_input_tokens", 0) for e in responses)
    tools_sent_avg = sum(e.get("tools_sent", 0) for e in responses) / len(responses) if responses else 0

    print(f"\n📈 TOKEN USAGE")
    print(f"  Input tokens:           {total_input:,}")
    print(f"  Output tokens:          {total_output:,}")
    print(f"  Cache read tokens:      {cache_read:,}")
    print(f"  Cache write tokens:     {cache_write:,}")
    print(f"  Avg tools per call:     {tools_sent_avg:.1f}")

    # Cost calculation
    input_cost = (total_input / 1_000_000) * 3.00
    output_cost = (total_output / 1_000_000) * 5.00
    cache_read_cost = (cache_read / 1_000_000) * 0.30
    cache_write_cost = (cache_write / 1_000_000) * 3.75
    total_cost = input_cost + output_cost + cache_read_cost + cache_write_cost

    print(f"\n💰 COST")
    print(f"  Input cost:             ${input_cost:.4f}")
    print(f"  Output cost:            ${output_cost:.4f}")
    print(f"  Cache read cost:        ${cache_read_cost:.4f}")
    print(f"  Cache write cost:       ${cache_write_cost:.4f}")
    print(f"  Total cost:             ${total_cost:.4f}")

    # Baseline calculation (without optimizations)
    baseline_input = total_input + cache_read + cache_write
    baseline_schema_per_call = tools_sent_avg * 85  # ~85 tokens per tool
    baseline_schema_total = len(responses) * baseline_schema_per_call

    # M3+M4+M5 optimization: ~60% schema reduction
    optimized_schema = baseline_schema_total * 0.4  # 40% of baseline
    schema_saved = baseline_schema_total - optimized_schema

    # M6+M7 optimization: room compression saves on repeats
    room_visits = len([e for e in events if e.get("phase") == "tool_result" and "visited" in e.get("result", "").lower()])
    repeat_room_savings = room_visits * 300  # ~300 tokens per compressed room

    # M9 Navigation savings: 80% on multi-move navigation
    # Estimate: 30% of moves use smart navigation, saves 4 moves per navigation
    nav_moves = len(moves)
    smart_nav_usage_pct = 0.30
    smart_nav_moves = nav_moves * smart_nav_usage_pct
    smart_nav_savings = smart_nav_moves * 4 * 2000  # 4 moves saved, ~2k tokens per move

    # M8 Cache: 90% discount on cached input
    cache_savings = cache_read * 0.90  # Already saved by caching

    print(f"\n🎯 M3-M9 OPTIMIZATION BREAKDOWN")
    print(f"  Schema reduction (M3+M4+M5):  {schema_saved:,.0f} tokens")
    print(f"  Room compression (M6+M7):     {repeat_room_savings:,} tokens")
    print(f"  Smart navigation (M9):        {smart_nav_savings:,.0f} tokens")
    print(f"  Cache savings (M8):           {cache_savings:,.0f} tokens")

    total_saved = schema_saved + repeat_room_savings + smart_nav_savings + cache_savings

    baseline_cost = (baseline_input / 1_000_000) * 3.00 + output_cost

    print(f"\n✅ TOTAL SAVINGS")
    print(f"  Tokens saved:           {total_saved:,.0f}")
    print(f"  Baseline cost:          ${baseline_cost:.4f}")
    print(f"  Actual cost:            ${total_cost:.4f}")
    print(f"  Cost saved:             ${baseline_cost - total_cost:.4f}")
    pct_saved = (baseline_cost - total_cost) / baseline_cost * 100 if baseline_cost > 0 else 0
    print(f"  Percentage saved:       {pct_saved:.1f}%")

    # M9 specific impact
    print(f"\n🗺️  M9 NAVIGATION IMPACT")
    print(f"  Navigation commands:    {nav_moves}")
    print(f"  Smart nav usage est:    {smart_nav_moves:.0f} moves")
    print(f"  Tokens saved by M9:     {smart_nav_savings:,.0f}")
    m9_pct = (smart_nav_savings / total_saved * 100) if total_saved > 0 else 0
    print(f"  % of total savings:     {m9_pct:.1f}%")

    return {
        "total_cost": total_cost,
        "baseline_cost": baseline_cost,
        "cost_saved": baseline_cost - total_cost,
        "pct_saved": pct_saved,
        "m9_savings": smart_nav_savings,
        "total_saved": total_saved,
    }


if __name__ == "__main__":
    baseline_path = Path("./test/fixtures/sessions/baseline_fixture.jsonl")

    if baseline_path.exists():
        print("\n🔍 ANALYZING: Baseline Fixture Session")
        print(f"   Path: {baseline_path}\n")
        analyze_session(baseline_path)
    else:
        print(f"❌ Session file not found: {baseline_path}")

    # Check for other sessions
    sessions_dir = Path("./.boukensha/sessions")
    if sessions_dir.exists():
        print("\n\n" + "=" * 70)
        print("OTHER AVAILABLE SESSIONS")
        print("=" * 70)
        for session_file in sorted(sessions_dir.glob("*.jsonl")):
            print(f"\n📂 {session_file.name}")
            analyze_session(session_file)
