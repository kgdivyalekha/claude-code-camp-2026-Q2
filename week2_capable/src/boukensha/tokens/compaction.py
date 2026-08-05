"""Phase-aware message compaction: evict stale content before dropping history.

Week 1's blind 40% drop is replaced with:
1. Drop stale tool results (older than N exchanges)
2. Collapse old exchanges into summaries
3. Only then drop whole message pairs on boundaries
"""

from typing import Any, Dict, List, Optional, Tuple


class CompactionStrategy:
    """Smarter history eviction: cheap-first, with measured impact."""

    def __init__(
        self,
        stale_result_age: int = 8,
        max_collapsed_summary: int = 100,
    ):
        """Initialize compaction strategy.

        Args:
            stale_result_age: Mark tool results older than this many exchanges as stale
            max_collapsed_summary: Max chars for a collapsed exchange summary
        """
        self.stale_result_age = stale_result_age
        self.max_collapsed_summary = max_collapsed_summary

    def compact_messages(
        self,
        messages: List[Dict[str, Any]],
        target_size: int,
        current_size: int,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Compact message history to fit within target size.

        Strategy: evict stale results → collapse old exchanges → drop pairs.

        Args:
            messages: Full message list (system + message history + tool results)
            target_size: Number of messages to keep
            current_size: Current message count

        Returns:
            (compacted_messages, metrics: {evicted_results, collapsed_exchanges, dropped_pairs})
        """
        if current_size <= target_size:
            return messages, {"evicted_results": 0, "collapsed_exchanges": 0, "dropped_pairs": 0}

        compacted = messages.copy()
        metrics = {"evicted_results": 0, "collapsed_exchanges": 0, "dropped_pairs": 0}

        # Step 1: Drop stale tool results
        compacted, evicted = self._drop_stale_results(compacted, self.stale_result_age)
        metrics["evicted_results"] = evicted

        if len(compacted) <= target_size:
            return compacted, metrics

        # Step 2: Collapse old exchanges into summaries
        compacted, collapsed = self._collapse_old_exchanges(compacted)
        metrics["collapsed_exchanges"] = collapsed

        if len(compacted) <= target_size:
            return compacted, metrics

        # Step 3: Drop oldest message pairs (on boundaries to preserve tool_use/tool_result pairs)
        compacted, dropped = self._drop_message_pairs(compacted, target_size)
        metrics["dropped_pairs"] = dropped

        return compacted, metrics

    def _drop_stale_results(
        self,
        messages: List[Dict[str, Any]],
        age_threshold: int,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Remove tool_result messages older than age_threshold exchanges.

        A tool_use at position i has a tool_result at i+1. If i is older than the
        threshold, we can drop the result but should keep the assistant reasoning.
        """
        if not messages:
            return messages, 0

        result_count = sum(1 for m in messages if m.get("role") == "user" and m.get("name") == "tool_result")
        if result_count == 0:
            return messages, 0

        # Find the cutoff: keep only the newest age_threshold tool_result messages
        tool_results_idx = [i for i, m in enumerate(messages) if m.get("role") == "user" and m.get("name") == "tool_result"]
        if len(tool_results_idx) <= age_threshold:
            return messages, 0

        # Drop results older than the age threshold
        cutoff_idx = tool_results_idx[-age_threshold]
        compacted = [m for i, m in enumerate(messages) if i < cutoff_idx or m.get("role") == "user"]

        # Count what was evicted (only tool_results, not the tool_use calls)
        evicted = sum(
            1
            for i, m in enumerate(messages)
            if cutoff_idx <= i and m.get("role") == "user" and m.get("name") == "tool_result"
        )

        return compacted, evicted

    def _collapse_old_exchanges(
        self,
        messages: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Collapse sequences of old tool_use/tool_result pairs into summaries.

        A sequence like [assistant, tool_use, tool_result, assistant, tool_use, tool_result]
        can become [assistant, "Tried 2 actions, both succeeded. [summary]"].
        """
        # Stub for now: this requires tracking which exchanges are "old" (pre-compaction)
        # and generating meaningful summaries without re-running the agent.
        #
        # Full implementation would:
        # 1. Identify "action blocks": runs of tool_use/tool_result pairs
        # 2. For each old block, extract key outcomes (moved here, picked up item, etc.)
        # 3. Replace the block with a single assistant message summarizing it
        #
        # For M7, we measure the impact of step 1 (drop stale results) first.
        return messages, 0

    def _drop_message_pairs(
        self,
        messages: List[Dict[str, Any]],
        target_size: int,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Drop oldest message pairs, respecting tool_use/tool_result boundaries.

        Never split a tool_use from its tool_result. Find the nearest pair boundary
        and cut there.
        """
        if len(messages) <= target_size:
            return messages, 0

        # Identify all tool_use positions
        tool_use_positions = [i for i, m in enumerate(messages) if m.get("role") == "user" and m.get("name") != "tool_result"]

        # Find the oldest pair boundary we can cut at
        # Strategy: cut before the oldest tool_use that doesn't have a corresponding result
        drop_count = len(messages) - target_size
        pair_drop = (drop_count + 1) // 2  # Drop this many pairs

        # Find the cut point: first pair_drop tool_use/result pairs
        if len(tool_use_positions) < pair_drop:
            # Can't drop that many pairs; drop as many as we can
            pair_drop = len(tool_use_positions)

        if pair_drop == 0:
            return messages, 0

        # Cut after the pair_drop-th tool_use (and its result)
        last_pair_idx = tool_use_positions[pair_drop - 1]
        cut_idx = last_pair_idx + 2  # tool_use + tool_result

        compacted = messages[cut_idx:]
        dropped = pair_drop

        return compacted, dropped
