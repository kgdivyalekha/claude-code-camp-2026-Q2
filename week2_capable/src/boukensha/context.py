import math
import os
from typing import Any, Dict, List, Optional, Union

from .message import Message


class Context:
    def __init__(
        self,
        system: str,
        context_window: int = 200_000,
        working_dir: Optional[str] = None,
        compaction_threshold: float = 0.85,
    ):
        self.system: str = system
        self.context_window: int = context_window
        self.compaction_threshold: float = compaction_threshold
        self.working_dir: Optional[str] = (
            os.path.abspath(os.path.expanduser(working_dir)) if working_dir else None
        )
        self.messages: list = []
        self.tools: Dict[str, Any] = {}
        self.current_tokens: int = 0
        self.turn_tokens: int = 0
        self.current_phase: str = "exploring"  # M4: phase-aware tool gating
        self.turns_since_combat: int = 0  # Track turns to detect phase changes

    def register_tool(self, tool: Any) -> None:
        self.tools[tool.name] = tool

    def add_message(
        self,
        role: str,
        content: Union[str, List[Dict[str, Any]]],
        tool_use_id: Optional[str] = None,
    ) -> None:
        self.messages.append(Message(role, content, tool_use_id))

    # Update the known context size from the last API response's input_tokens.
    def update_tokens(self, n: Any) -> None:
        self.current_tokens = int(n or 0)

    # Reset the cumulative per-turn spend counter. Called at the top of a turn.
    def reset_turn_tokens(self) -> None:
        self.turn_tokens = 0

    # Add one API call's input+output tokens to the cumulative per-turn total.
    # This is the spend budget -- distinct from current_tokens (window pressure).
    def add_turn_tokens(self, input_tokens: Any, output_tokens: Any) -> None:
        self.turn_tokens += int(input_tokens or 0) + int(output_tokens or 0)

    # Fraction of the context window currently in use (0.0-1.0).
    def usage_fraction(self) -> float:
        return self.current_tokens / self.context_window if self.context_window > 0 else 0.0

    # Integer percentage (0-100).
    def usage_pct(self) -> int:
        return round(self.usage_fraction() * 100)

    # True when we should compact before the next API call. Defaults to the
    # configured compaction_threshold (a fraction of context_window).
    def needs_compaction(self, threshold: Optional[float] = None) -> bool:
        if threshold is None:
            threshold = self.compaction_threshold
        return self.usage_fraction() >= threshold

    # Drop the oldest 40% of messages to free space, keeping at least 2.
    # Resets current_tokens to 0 (will be updated by the next API response).
    # Returns the number of messages dropped.
    def compact_messages(self, target_fraction: float = 0.60) -> int:
        """Drop oldest messages to reach target_fraction of context window.

        MUST respect tool_use/tool_result pairing: never drop at a boundary that
        would separate a tool_use block from its matching tool_result message.
        The Anthropic API requires every tool_use to be followed by its tool_result
        in sequence; splitting them causes a 400 error and forces a retry.

        Strategy:
        1. Identify all tool_use/tool_result pairs and their boundaries
        2. Find the earliest boundary after which we can drop without splitting a pair
        3. Keep at least 2 messages (system + first turn)
        """
        if len(self.messages) <= 2:
            return 0

        # Calculate how many messages to drop to reach target
        target_msgs = max(2, int(len(self.messages) * target_fraction))
        msgs_to_drop = len(self.messages) - target_msgs

        if msgs_to_drop <= 0:
            return 0

        # Find all tool_use ids in assistant messages (only the first occurrence counts as the "use")
        tool_use_ids = set()
        for i, msg in enumerate(self.messages):
            if msg.role == "assistant" and isinstance(msg.content, list):
                for block in msg.content:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        tool_use_ids.add(block.get("id"))

        # Find boundaries that are safe to cut at (after a tool_result for all known tool_use ids)
        safe_boundaries = []
        pending_tool_uses = set()

        for i, msg in enumerate(self.messages):
            # Track tool_use ids we haven't seen results for yet
            if msg.role == "assistant" and isinstance(msg.content, list):
                for block in msg.content:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        pending_tool_uses.add(block.get("id"))

            # Mark when we see a tool_result
            if msg.role == "tool_result" and msg.tool_use_id:
                pending_tool_uses.discard(msg.tool_use_id)

            # A boundary is safe if no tool_use is waiting for its result
            if not pending_tool_uses:
                safe_boundaries.append(i + 1)

        # Find the best safe boundary to drop from (earliest that drops enough messages)
        drop_at = None
        for boundary in safe_boundaries:
            if boundary >= msgs_to_drop:
                drop_at = boundary
                break

        # Fallback: if no perfect safe boundary, drop as close as possible without breaking pairs
        if drop_at is None and safe_boundaries:
            drop_at = safe_boundaries[-1]

        # If still no boundary found, don't drop (safer than corrupting)
        if drop_at is None or drop_at >= len(self.messages) - 1:
            return 0

        drop_count = drop_at
        self.messages = self.messages[drop_count:]
        self.current_tokens = 0
        return drop_count

    # Drop all conversation history, keeping tools and system prompt intact.
    def clear_messages(self) -> None:
        self.messages = []
        self.current_tokens = 0

    def tool_count(self) -> int:
        return len(self.tools)

    def turn_count(self) -> int:
        return len(self.messages)

    # M4: Phase-aware tool gating
    def set_phase(self, phase: str) -> None:
        """Set current game phase for tool gating (M4).

        Phases: "exploring", "fighting", "trading", "full"
        """
        if phase in ("exploring", "fighting", "trading", "full"):
            self.current_phase = phase

    def detect_phase_from_result(self, tool_result: str) -> Optional[str]:
        """Detect phase change from a tool result.

        Returns the new phase if detected, None if no change.
        """
        result_lower = tool_result.lower()

        # Combat indicators
        if any(word in result_lower for word in ["attack", "hit", "damage", "combat", "round", "battle", "enemy"]):
            if self.current_phase != "fighting":
                self.turns_since_combat = 0
                return "fighting"
            self.turns_since_combat = 0

        # Trading indicators
        elif any(word in result_lower for word in ["shop", "buy", "sell", "trade", "merchant", "vendor"]):
            if self.current_phase != "trading":
                return "trading"

        # Exploration (no combat for N turns)
        else:
            self.turns_since_combat += 1
            if self.turns_since_combat > 3 and self.current_phase != "exploring":
                return "exploring"

        return None

    def __repr__(self) -> str:
        return (
            f"<Context turns={self.turn_count()} tools={self.tool_count()} "
            f"window={self.context_window} current={self.current_tokens}>"
        )

    def __str__(self) -> str:
        return self.__repr__()
