#!/usr/bin/env python3
"""Measure token baseline from week 1 session JSONL files.

This script rebuilds events.db from existing JSONL sessions and produces
a token baseline report. Run this to verify §1.1 estimates before landing
any optimizations.

Usage:
    python3 measure_baseline.py <path-to-session.jsonl> [output-dir]
"""

import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from boukensha.observability import EventStore, Analytics


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 measure_baseline.py <session.jsonl> [output-dir]", file=sys.stderr)
        sys.exit(1)

    jsonl_path = Path(sys.argv[1])
    if not jsonl_path.exists():
        print(f"Error: {jsonl_path} not found", file=sys.stderr)
        sys.exit(1)

    output_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path.cwd()
    output_dir.mkdir(parents=True, exist_ok=True)

    db_path = output_dir / "events.db"

    print(f"Rebuilding {db_path} from {jsonl_path}")
    store = EventStore.rebuild_from_jsonl(str(jsonl_path), str(db_path))

    # Get session ID from the JSONL file
    session_id = None
    for line in jsonl_path.read_text().splitlines():
        if line:
            event = json.loads(line)
            session_id = event.get("session_id")
            if session_id:
                break

    if not session_id:
        print(f"Error: No session_id found in {jsonl_path}", file=sys.stderr)
        sys.exit(1)

    print(f"\nAnalyzing session: {session_id}\n")

    analytics = Analytics(str(db_path))
    try:
        # Cost summary
        cost = analytics.cost_summary(session_id)
        print("=== Cost Summary ===")
        print(f"Total cost:         ${cost.total_usd:.4f}")
        print(f"Turns:              {cost.turns}")
        print(f"Cost per turn:      ${cost.cost_per_turn_usd:.4f}")
        print(f"Input cost:         ${cost.input_cost_usd:.4f}")
        print(f"Output cost:        ${cost.output_cost_usd:.4f}")
        if cost.cache_read_cost_usd > 0:
            print(f"Cache read saving:  ${cost.cache_read_cost_usd:.4f}")
        if cost.cache_write_cost_usd > 0:
            print(f"Cache write cost:   ${cost.cache_write_cost_usd:.4f}")

        # Token breakdown
        breakdown = analytics.token_breakdown(session_id)
        print("\n=== Token Breakdown ===")
        print(f"Total input tokens:     {breakdown.total_input_tokens:,}")
        print(f"Total output tokens:    {breakdown.total_output_tokens:,}")
        print(f"Schema tokens (est):    {breakdown.schema_tokens:,}")
        print(f"History tokens (est):   {breakdown.history_tokens:,}")
        print(f"Result tokens (est):    {breakdown.result_tokens:,}")
        if breakdown.cache_read_tokens > 0:
            print(f"Cache read tokens:      {breakdown.cache_read_tokens:,}")
        if breakdown.cache_write_tokens > 0:
            print(f"Cache write tokens:     {breakdown.cache_write_tokens:,}")

        # Schema overhead
        schema = analytics.schema_overhead(session_id)
        print("\n=== Schema Overhead (§3.2 lever) ===")
        print(f"Average tools sent:     {schema['tools_sent']}")
        print(f"Schema tokens (est):    {schema['schema_tokens']:,}")
        print(f"Percent of input:       {schema['percent_of_input']}%")

        # Cache effectiveness
        cache = analytics.cache_effectiveness(session_id)
        print("\n=== Cache Effectiveness (§3.5 lever) ===")
        print(f"Cache hit rate:         {cache['hit_rate']}%")
        print(f"Cost saving:            ${cache['cost_saving_usd']:.4f}")

        # Per-turn breakdown
        per_turn = analytics.tokens_per_turn(session_id)
        if len(per_turn) <= 10:
            print("\n=== Tokens Per Turn ===")
            for row in per_turn:
                print(
                    f"Turn {row['turn']:2d}: {row['input_tokens']:6,} in, "
                    f"{row['output_tokens']:4,} out, {row['iterations']} iterations, "
                    f"${row['cost_usd']:.4f}"
                )
        else:
            print(f"\n=== Tokens Per Turn ({len(per_turn)} turns, showing first 5) ===")
            for row in per_turn[:5]:
                print(
                    f"Turn {row['turn']:2d}: {row['input_tokens']:6,} in, "
                    f"{row['output_tokens']:4,} out, {row['iterations']} iterations, "
                    f"${row['cost_usd']:.4f}"
                )
            print("  ...")

        # Iteration pressure
        iterations = analytics.iterations_per_turn(session_id)
        if iterations:
            print("\n=== Iteration Count (cost scales ~N×context) ===")
            avg_iter = sum(r["iterations"] for r in iterations) / len(iterations)
            max_iter = max(r["iterations"] for r in iterations)
            print(f"Average iterations per turn: {avg_iter:.1f}")
            print(f"Max iterations in a turn:    {max_iter}")
            if max_iter > 10:
                print("WARNING: High iteration count indicates potential for optimization")

        # Write summary to file
        summary_file = output_dir / "baseline_summary.txt"
        with open(summary_file, "w") as f:
            f.write(f"Token Baseline Measurement\n")
            f.write(f"Session: {session_id}\n")
            f.write(f"Total cost: ${cost.total_usd:.4f}\n")
            f.write(f"Total input tokens: {breakdown.total_input_tokens:,}\n")
            f.write(f"Total output tokens: {breakdown.total_output_tokens:,}\n")
            f.write(f"Turns: {cost.turns}\n")
            f.write(f"Schema overhead: {schema['percent_of_input']}% of input\n")
            f.write(f"Cache hit rate: {cache['hit_rate']}%\n")
            f.write(f"Avg iterations/turn: {avg_iter:.1f}\n")

        print(f"\n✅ Baseline summary written to {summary_file}")

    finally:
        analytics.close()
        store.close()


if __name__ == "__main__":
    main()
