"""Compaction trigger helper: monitors token usage and signals when to compact.

Implements the strategy: trigger /compact when reaching 80% of 60k session window.
- 60k * 0.8 = 48k tokens as the trigger threshold
- Prevents running out of tokens mid-objective
"""

from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class CompactionStatus:
    """Current compaction status."""
    should_compact: bool
    usage_percent: float
    tokens_used: int
    threshold: int
    message: str = ""


class CompactionTrigger:
    """Monitors token usage and signals when to trigger /compact.

    Strategy:
    - Session window: 60,000 tokens
    - Trigger threshold: 80% = 48,000 tokens
    - Rationale: Compact before hitting the ceiling, leaving headroom to complete
    """

    # Configuration
    SESSION_WINDOW = 60_000  # Total tokens available per session
    TRIGGER_THRESHOLD = 0.80  # Compact at 80% usage
    TRIGGER_TOKENS = int(SESSION_WINDOW * TRIGGER_THRESHOLD)  # 48,000 tokens

    def __init__(self):
        self.session_window = self.SESSION_WINDOW
        self.trigger_threshold = self.TRIGGER_THRESHOLD
        self.trigger_tokens = self.TRIGGER_TOKENS
        self.last_compaction_at = 0
        self._log_history = []

    def check(self, tokens_used: int) -> CompactionStatus:
        """Check if compaction should be triggered.

        Args:
            tokens_used: Current total tokens used in this session

        Returns:
            CompactionStatus with decision and metrics
        """
        usage_percent = (tokens_used / self.session_window) * 100

        # Determine if compaction needed
        should_compact = tokens_used >= self.trigger_tokens

        message = (
            f"Token usage: {tokens_used:,}/{self.session_window:,} ({usage_percent:.0f}%) | "
            f"Threshold: {self.trigger_tokens:,} | "
            f"Trigger: {'YES ⚠️' if should_compact else 'no'}"
        )

        status = CompactionStatus(
            should_compact=should_compact,
            usage_percent=usage_percent,
            tokens_used=tokens_used,
            threshold=self.trigger_tokens,
            message=message,
        )

        # Log for history
        self._log_history.append({
            "at": datetime.now().isoformat(),
            "tokens_used": tokens_used,
            "usage_percent": usage_percent,
            "should_compact": should_compact,
        })

        return status

    def get_status_message(self, tokens_used: int) -> str:
        """Get human-readable status message."""
        status = self.check(tokens_used)
        return status.message

    def estimate_tokens_before_trigger(self, tokens_used: int) -> int:
        """Estimate how many more tokens until trigger."""
        remaining = self.trigger_tokens - tokens_used
        return max(0, remaining)

    def set_window(self, window: int) -> None:
        """Override the session window (for testing or custom limits)."""
        self.session_window = window
        self.trigger_tokens = int(window * self.trigger_threshold)

    def reset(self) -> None:
        """Reset trigger for new session."""
        self.last_compaction_at = 0
        self._log_history = []

    def get_history(self) -> list:
        """Get history of compaction checks."""
        return self._log_history


# Global instance for easy access
_compaction_trigger = CompactionTrigger()


def check_compaction(tokens_used: int) -> CompactionStatus:
    """Global helper: check if compaction should be triggered.

    Usage:
        from boukensha.compaction import check_compaction

        status = check_compaction(current_tokens)
        if status.should_compact:
            print("⚠️ Trigger /compact now!")
    """
    return _compaction_trigger.check(tokens_used)


def get_compaction_message(tokens_used: int) -> str:
    """Get formatted compaction status message."""
    return _compaction_trigger.get_status_message(tokens_used)


def tokens_until_trigger(tokens_used: int) -> int:
    """Get remaining tokens before compaction trigger."""
    return _compaction_trigger.estimate_tokens_before_trigger(tokens_used)
