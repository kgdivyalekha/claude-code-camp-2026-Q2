#!/usr/bin/env python3
"""Analyze token breakdown for all sessions in events.db"""

import sqlite3
from pathlib import Path
from typing import Dict, List, Tuple

db_path = ".boukensha/events.db"

if not Path(db_path).exists():
    print(f"Error: {db_path} not found")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get all unique session IDs
cursor.execute("SELECT DISTINCT session_id FROM events ORDER BY session_id")
sessions = [row[0] for row in cursor.fetchall()]

print(f"Found {len(sessions)} session(s)\n")
print("=" * 100)

for session_id in sessions:
    print(f"\nSession: {session_id}")
    print("-" * 100)

    # Get response events for this session
    cursor.execute("""
        SELECT
            COUNT(*) as response_count,
            COALESCE(SUM(input_tokens), 0) as total_input,
            COALESCE(SUM(output_tokens), 0) as total_output,
            COALESCE(SUM(COALESCE(cache_read_tokens, 0)), 0) as total_cache_read,
            COALESCE(SUM(COALESCE(cache_write_tokens, 0)), 0) as total_cache_write,
            COALESCE(SUM(cost_usd), 0) as total_cost,
            COUNT(DISTINCT turn) as turn_count,
            COALESCE(AVG(tools_sent), 0) as avg_tools_sent
        FROM events
        WHERE session_id = ? AND phase = 'response'
    """, (session_id,))

    result = cursor.fetchone()
    if not result:
        print("  No response events found\n")
        continue

    (response_count, total_input, total_output, cache_read, cache_write,
     total_cost, turn_count, avg_tools_sent) = result

    # Estimate schema overhead
    schema_tokens = int(response_count * 2200)  # ~2200 tokens per response
    schema_pct = (schema_tokens / total_input * 100) if total_input > 0 else 0

    # Cache effectiveness
    cache_hit_rate = (cache_read / (total_input + cache_read) * 100) if (total_input + cache_read) > 0 else 0

    # Cost breakdown
    input_cost = total_cost * 0.67 if total_cost > 0 else 0  # Rough estimate
    output_cost = total_cost * 0.33 if total_cost > 0 else 0

    print(f"  Responses:          {response_count}")
    print(f"  Turns:              {turn_count}")
    print(f"  Avg tools sent:     {avg_tools_sent:.1f}")
    print()
    print(f"  Token Breakdown:")
    print(f"    Total input:      {total_input:,} tokens")
    print(f"    Total output:     {total_output:,} tokens")
    print(f"    Cache read:       {cache_read:,} tokens ({cache_hit_rate:.1f}% hit rate)")
    print(f"    Cache write:      {cache_write:,} tokens")
    print()
    print(f"  Schema Overhead (§3.1 lever):")
    print(f"    Estimated:        {schema_tokens:,} tokens ({schema_pct:.1f}% of input)")
    print()
    print(f"  Cost Analysis:")
    print(f"    Total:            ${total_cost:.4f}")
    print(f"    Per turn:         ${total_cost / turn_count:.4f}" if turn_count > 0 else "    Per turn:         N/A")
    print(f"    Input cost:       ${input_cost:.4f}")
    print(f"    Output cost:      ${output_cost:.4f}")
    print()

    # Per-turn breakdown
    cursor.execute("""
        SELECT
            turn,
            COUNT(*) as responses,
            COALESCE(SUM(input_tokens), 0) as input_tokens,
            COALESCE(SUM(output_tokens), 0) as output_tokens,
            COALESCE(SUM(cost_usd), 0) as cost_usd,
            COALESCE(AVG(tools_sent), 0) as avg_tools
        FROM events
        WHERE session_id = ? AND phase = 'response'
        GROUP BY turn
        ORDER BY turn
    """, (session_id,))

    turns = cursor.fetchall()
    if turns:
        print(f"  Per-Turn Details:")
        print(f"    {'Turn':<6} {'Input':<10} {'Output':<10} {'Tools':<8} {'Cost':<10} {'Iterations':<12}")
        print(f"    {'-'*6} {'-'*10} {'-'*10} {'-'*8} {'-'*10} {'-'*12}")

        for turn, responses, turn_input, turn_output, turn_cost, avg_tools in turns:
            print(f"    {turn:<6} {turn_input:<10,} {turn_output:<10,} {avg_tools:<8.1f} ${turn_cost:<9.4f} {responses:<12}")

    print()

conn.close()
print("=" * 100)
