"""Analytics query surface over events.db.

This is the instrument panel for token accounting. Every optimization is measured
here: before/after breakdowns, cost per room, cache effectiveness, etc.
"""

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from boukensha.db import open_db


@dataclass
class TokenBreakdown:
    """Token usage by category."""
    schema_tokens: int = 0       # tool definitions in payload
    history_tokens: int = 0      # message history re-send
    result_tokens: int = 0       # tool result content
    output_tokens: int = 0       # model generation
    cache_read_tokens: int = 0   # cached input tokens (cheap)
    cache_write_tokens: int = 0  # cache fill cost (premium)
    total_input_tokens: int = 0
    total_output_tokens: int = 0


@dataclass
class CostSummary:
    """Cost breakdown."""
    total_usd: float = 0.0
    input_cost_usd: float = 0.0
    output_cost_usd: float = 0.0
    cache_read_cost_usd: float = 0.0
    cache_write_cost_usd: float = 0.0
    turns: int = 0
    cost_per_turn_usd: float = 0.0
    cost_per_input_mtok: float = 0.0


class Analytics:
    """Query surface for token economy and observability metrics."""

    def __init__(self, db_path: str = ".boukensha/events.db"):
        """Initialize analytics over an events.db.

        Args:
            db_path: Path to events.db.
        """
        if not Path(db_path).exists():
            raise FileNotFoundError(f"events.db not found at {db_path}")
        self.conn = open_db(db_path)

    def token_breakdown(self, session_id: str) -> TokenBreakdown:
        """Breakdown of token usage by category.

        Returns:
            TokenBreakdown with totals for schema, history, results, output.
        """
        # Token accounting note from the plan: usage lives ONLY on "response" events.
        # Tool calls and results carry no usage; only the final response does.
        row = self.conn.execute(
            """
            SELECT
                COALESCE(SUM(input_tokens), 0) as input_tokens,
                COALESCE(SUM(output_tokens), 0) as output_tokens,
                COALESCE(SUM(cache_read_tokens), 0) as cache_read_tokens,
                COALESCE(SUM(cache_write_tokens), 0) as cache_write_tokens
            FROM events
            WHERE session_id = ? AND phase = 'response'
            """,
            (session_id,),
        ).fetchone()

        if not row:
            return TokenBreakdown()

        input_tokens, output_tokens, cache_read, cache_write = row

        # Estimate breakdown (not perfect but directional)
        # Schema is ~2000-2500 tokens per call, sent on every iteration
        response_count = self.conn.execute(
            "SELECT COUNT(*) FROM events WHERE session_id = ? AND phase = 'response'",
            (session_id,),
        ).fetchone()[0]

        # Rough estimates: schema ~2200 tokens per response
        schema_tokens = max(0, int(response_count * 2200))
        total_input = input_tokens + cache_read + cache_write

        # The rest is history + results
        remaining = total_input - schema_tokens
        history_tokens = max(0, remaining // 2)
        result_tokens = max(0, remaining - history_tokens)

        return TokenBreakdown(
            schema_tokens=schema_tokens,
            history_tokens=history_tokens,
            result_tokens=result_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read,
            cache_write_tokens=cache_write,
            total_input_tokens=total_input,
            total_output_tokens=output_tokens,
        )

    def tokens_per_turn(self, session_id: str, actor: Optional[str] = None) -> List[Dict[str, Any]]:
        """Per-turn token breakdown.

        Args:
            session_id: Session ID.
            actor: Optional actor filter.

        Returns:
            List of dicts with turn, input_tokens, output_tokens, iterations, cost_usd.
        """
        query = """
            SELECT
                turn,
                COALESCE(SUM(input_tokens + COALESCE(cache_read_tokens, 0) + COALESCE(cache_write_tokens, 0)), 0) as input_tokens,
                COALESCE(SUM(output_tokens), 0) as output_tokens,
                COUNT(DISTINCT iteration) as iterations,
                COALESCE(SUM(cost_usd), 0) as cost_usd
            FROM events
            WHERE session_id = ? AND phase = 'response'
        """
        params = [session_id]

        if actor:
            query += " AND actor = ?"
            params.append(actor)

        query += " GROUP BY turn ORDER BY turn"

        rows = self.conn.execute(query, params).fetchall()
        return [
            {
                "turn": row[0],
                "input_tokens": row[1],
                "output_tokens": row[2],
                "iterations": row[3],
                "cost_usd": row[4],
            }
            for row in rows
        ]

    def cost_summary(self, session_id: str) -> CostSummary:
        """Overall cost summary for a session.

        Args:
            session_id: Session ID.

        Returns:
            CostSummary with totals, per-turn average, and breakdown by input/output/cache.
        """
        row = self.conn.execute(
            """
            SELECT
                COALESCE(SUM(cost_usd), 0) as total_cost,
                COALESCE(SUM(input_tokens + COALESCE(cache_read_tokens, 0)), 0) as input_tokens,
                COALESCE(SUM(output_tokens), 0) as output_tokens,
                COALESCE(SUM(COALESCE(cache_read_tokens, 0)), 0) as cache_read_tokens,
                COALESCE(SUM(COALESCE(cache_write_tokens, 0)), 0) as cache_write_tokens,
                COUNT(DISTINCT turn) as turn_count,
                COUNT(*) as response_event_count
            FROM events
            WHERE session_id = ? AND phase = 'response'
            """,
            (session_id,),
        ).fetchone()

        # Get the model to determine correct pricing
        model_row = self.conn.execute(
            "SELECT model FROM events WHERE session_id = ? AND phase = 'response' LIMIT 1",
            (session_id,),
        ).fetchone()
        model = model_row[0] if model_row else "claude-haiku-4-5"

        if not row or row[5] == 0:
            return CostSummary()

        total_cost, input_tokens, output_tokens, cache_read, cache_write, turn_count, response_count = row

        # Use actual model pricing, default to Haiku
        rates = self._model_pricing_rates(model)
        input_cost = (input_tokens / 1_000_000) * rates["input"]
        output_cost = (output_tokens / 1_000_000) * rates["output"]
        estimated_total = input_cost + output_cost

        # Bug: cost_usd is only populated on the final response event, not all of them.
        # With multiple iterations, total_cost is significantly underestimated.
        # Always use the estimated total, which accounts for all tokens from all API calls.
        final_cost = estimated_total

        return CostSummary(
            total_usd=final_cost,
            input_cost_usd=input_cost,
            output_cost_usd=output_cost,
            cache_read_cost_usd=(cache_read / 1_000_000) * rates["cache_read"] if cache_read > 0 else 0,
            cache_write_cost_usd=(cache_write / 1_000_000) * rates["cache_write"] if cache_write > 0 else 0,
            turns=turn_count,
            cost_per_turn_usd=final_cost / turn_count if turn_count > 0 else 0,
            cost_per_input_mtok=(input_cost / input_tokens * 1_000_000) if input_tokens > 0 else 0,
        )

    def schema_overhead(self, session_id: str) -> Dict[str, Any]:
        """Estimate schema (tool definition) token cost.

        Args:
            session_id: Session ID.

        Returns:
            Dict with tools_sent count, estimated schema tokens, and percentage of input.
        """
        row = self.conn.execute(
            """
            SELECT
                COUNT(*) as response_count,
                COALESCE(AVG(tools_sent), 0) as avg_tools_sent,
                COALESCE(SUM(input_tokens + COALESCE(cache_read_tokens, 0) + COALESCE(cache_write_tokens, 0)), 0) as total_input
            FROM events
            WHERE session_id = ? AND phase = 'response'
            """,
            (session_id,),
        ).fetchone()

        if not row or row[0] == 0:
            return {"tools_sent": 0, "schema_tokens": 0, "percent_of_input": 0}

        response_count, avg_tools_sent, total_input = row

        # Rough estimate: 85 tokens per tool schema (varies by detail level)
        schema_tokens = int(response_count * avg_tools_sent * 85)
        percent = (schema_tokens / total_input * 100) if total_input > 0 else 0

        return {
            "tools_sent": avg_tools_sent,
            "schema_tokens": schema_tokens,
            "percent_of_input": round(percent, 1),
        }

    def cache_effectiveness(self, session_id: str) -> Dict[str, Any]:
        """Cache hit rate and cost impact.

        Args:
            session_id: Session ID.

        Returns:
            Dict with cache_read_tokens, cache_write_tokens, hit_rate, cost_saving_usd.
        """
        row = self.conn.execute(
            """
            SELECT
                COALESCE(SUM(COALESCE(cache_read_tokens, 0)), 0) as cache_read,
                COALESCE(SUM(COALESCE(cache_write_tokens, 0)), 0) as cache_write,
                COALESCE(SUM(input_tokens), 0) as uncached_input
            FROM events
            WHERE session_id = ? AND phase = 'response'
            """,
            (session_id,),
        ).fetchone()

        if not row:
            return {"cache_read_tokens": 0, "cache_write_tokens": 0, "hit_rate": 0, "cost_saving_usd": 0}

        cache_read, cache_write, uncached_input = row
        total_input = cache_read + cache_write + uncached_input

        hit_rate = (cache_read / total_input * 100) if total_input > 0 else 0

        # With cache: $0.30 per 1M read, $3.75 per 1M write
        # Without cache: $3.00 per 1M
        cache_read_cost = (cache_read / 1_000_000) * 0.30
        cache_write_cost = (cache_write / 1_000_000) * 3.75
        uncached_cost = (uncached_input / 1_000_000) * 3.00
        no_cache_cost = ((cache_read + cache_write + uncached_input) / 1_000_000) * 3.00

        actual_cost = cache_read_cost + cache_write_cost + uncached_cost
        cost_saving = no_cache_cost - actual_cost

        return {
            "cache_read_tokens": cache_read,
            "cache_write_tokens": cache_write,
            "hit_rate": round(hit_rate, 1),
            "cost_saving_usd": round(cost_saving, 4),
        }

    def iterations_per_turn(self, session_id: str, actor: Optional[str] = None) -> List[Dict[str, Any]]:
        """Iteration counts per turn (cost scales ~N×context).

        Args:
            session_id: Session ID.
            actor: Optional actor filter.

        Returns:
            List of dicts with turn, iterations, input_tokens.
        """
        query = """
            SELECT
                turn,
                COUNT(DISTINCT iteration) as iterations,
                COALESCE(SUM(input_tokens), 0) as input_tokens
            FROM events
            WHERE session_id = ? AND phase = 'response'
        """
        params = [session_id]

        if actor:
            query += " AND actor = ?"
            params.append(actor)

        query += " GROUP BY turn ORDER BY turn"

        rows = self.conn.execute(query, params).fetchall()
        return [
            {
                "turn": row[0],
                "iterations": row[1],
                "input_tokens": row[2],
            }
            for row in rows
        ]

    def context_pressure(self, session_id: str) -> List[Dict[str, Any]]:
        """Input tokens per turn vs. the context window.

        Returns:
            List of dicts with turn, input_tokens, percent_of_window.
        """
        # Assume 200K token window
        CONTEXT_WINDOW = 200_000

        query = """
            SELECT
                turn,
                COALESCE(SUM(input_tokens + COALESCE(cache_read_tokens, 0) + COALESCE(cache_write_tokens, 0)), 0) as input_tokens
            FROM events
            WHERE session_id = ? AND phase = 'response'
            GROUP BY turn
            ORDER BY turn
        """

        rows = self.conn.execute(query, (session_id,)).fetchall()
        return [
            {
                "turn": row[0],
                "input_tokens": row[1],
                "percent_of_window": round(row[1] / CONTEXT_WINDOW * 100, 1),
            }
            for row in rows
        ]

    def tool_usage(self, session_id: str, actor: Optional[str] = None) -> List[Dict[str, Any]]:
        """Tool call counts by tool name.

        Args:
            session_id: Session ID.
            actor: Optional actor filter.

        Returns:
            List of dicts with tool, call_count, success_count, error_count.
        """
        query = """
            SELECT
                tool,
                COUNT(*) as call_count,
                SUM(CASE WHEN ok = 1 THEN 1 ELSE 0 END) as success_count,
                SUM(CASE WHEN ok = 0 THEN 1 ELSE 0 END) as error_count
            FROM events
            WHERE session_id = ? AND phase = 'tool_result'
        """
        params = [session_id]

        if actor:
            query += " AND actor = ?"
            params.append(actor)

        query += " GROUP BY tool ORDER BY call_count DESC"

        rows = self.conn.execute(query, params).fetchall()
        return [
            {
                "tool": row[0],
                "call_count": row[1],
                "success_count": row[2] or 0,
                "error_count": row[3] or 0,
            }
            for row in rows
        ]

    def close(self) -> None:
        """Close the database connection."""
        if self.conn:
            self.conn.close()

    def __enter__(self) -> "Analytics":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def _model_pricing_rates(self, model: str) -> Dict[str, float]:
        """Get pricing rates for a model.

        Args:
            model: Model name.

        Returns:
            Dict with input, output, cache_read, cache_write rates per 1M tokens.
        """
        model_lower = (model or "").lower()

        # Pricing per 1M tokens
        if "fable" in model_lower:
            return {"input": 10.0, "output": 50.0, "cache_read": 3.0, "cache_write": 12.5}
        elif "opus-5" in model_lower:
            return {"input": 15.0, "output": 75.0, "cache_read": 4.5, "cache_write": 18.75}
        elif "opus" in model_lower:
            return {"input": 5.0, "output": 25.0, "cache_read": 1.5, "cache_write": 6.25}
        elif "sonnet-5" in model_lower:
            return {"input": 3.0, "output": 15.0, "cache_read": 0.9, "cache_write": 3.75}
        elif "sonnet" in model_lower:
            return {"input": 3.0, "output": 15.0, "cache_read": 0.9, "cache_write": 3.75}
        elif "haiku" in model_lower:
            return {"input": 1.0, "output": 5.0, "cache_read": 0.3, "cache_write": 1.25}
        else:
            # Default fallback to Haiku
            return {"input": 1.0, "output": 5.0, "cache_read": 0.3, "cache_write": 1.25}
