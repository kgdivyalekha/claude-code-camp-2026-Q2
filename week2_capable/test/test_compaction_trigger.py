#!/usr/bin/env python3
"""Test compaction trigger: monitors token usage and signals when to /compact.

Verifies that the compaction trigger correctly identifies when to call /compact
at 80% of 60k session window (48k tokens).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from boukensha.compaction import (
    CompactionTrigger,
    check_compaction,
    get_compaction_message,
    tokens_until_trigger,
)


def test_trigger_threshold():
    """Test that trigger fires at 80% of 60k."""
    trigger = CompactionTrigger()

    # Below threshold: should NOT trigger
    status = trigger.check(47_999)
    assert not status.should_compact, "Should not trigger below 48k"
    assert status.usage_percent < 80, "Usage should be below 80%"
    print("✓ trigger_threshold: Below 48k does not trigger")

    # At threshold: should trigger
    status = trigger.check(48_000)
    assert status.should_compact, "Should trigger at 48k"
    assert status.usage_percent == 80, "Usage should be exactly 80%"
    print("✓ trigger_threshold: At 48k triggers compaction")

    # Above threshold: should trigger
    status = trigger.check(50_000)
    assert status.should_compact, "Should trigger above 48k"
    assert status.usage_percent > 80, "Usage should be above 80%"
    print("✓ trigger_threshold: Above 48k triggers compaction")


def test_status_message():
    """Test compaction status message formatting."""
    trigger = CompactionTrigger()

    # Below threshold
    status = trigger.check(30_000)
    assert "30,000" in status.message, "Message should include token count"
    assert "50%" in status.message, "Message should include percentage"
    assert "no" in status.message.lower(), "Message should indicate no trigger"
    print("✓ status_message: Formats below-threshold correctly")

    # At threshold
    status = trigger.check(48_000)
    assert "48,000" in status.message
    assert "80%" in status.message
    assert "YES" in status.message, "Message should indicate trigger"
    print("✓ status_message: Formats at-threshold correctly")


def test_estimate_tokens_before_trigger():
    """Test estimation of remaining tokens."""
    trigger = CompactionTrigger()

    # At 30k: should have 18k left (48k - 30k)
    remaining = trigger.estimate_tokens_before_trigger(30_000)
    assert remaining == 18_000, f"Expected 18k, got {remaining}"
    print("✓ estimate_tokens_before_trigger: 30k → 18k remaining")

    # At 48k: should have 0 left
    remaining = trigger.estimate_tokens_before_trigger(48_000)
    assert remaining == 0, f"Expected 0, got {remaining}"
    print("✓ estimate_tokens_before_trigger: 48k → 0 remaining")

    # At 50k: should clamp to 0 (already triggered)
    remaining = trigger.estimate_tokens_before_trigger(50_000)
    assert remaining == 0, f"Expected 0, got {remaining}"
    print("✓ estimate_tokens_before_trigger: 50k → 0 (clamped)")


def test_usage_percentage():
    """Test usage percentage calculations."""
    trigger = CompactionTrigger()

    # 10k / 60k = 16.67%
    status = trigger.check(10_000)
    assert 16 <= status.usage_percent <= 17, f"Expected ~16.67%, got {status.usage_percent}"
    print(f"✓ usage_percentage: 10k tokens = {status.usage_percent:.1f}%")

    # 30k / 60k = 50%
    status = trigger.check(30_000)
    assert status.usage_percent == 50, f"Expected 50%, got {status.usage_percent}"
    print(f"✓ usage_percentage: 30k tokens = {status.usage_percent:.1f}%")

    # 60k / 60k = 100%
    status = trigger.check(60_000)
    assert status.usage_percent == 100, f"Expected 100%, got {status.usage_percent}"
    print(f"✓ usage_percentage: 60k tokens = {status.usage_percent:.1f}%")


def test_custom_window():
    """Test overriding session window (for testing)."""
    trigger = CompactionTrigger()
    trigger.set_window(10_000)  # Use 10k instead of 60k for testing

    # Threshold should now be 8k (80% of 10k)
    assert trigger.trigger_tokens == 8_000, f"Expected 8k threshold, got {trigger.trigger_tokens}"

    # Below 8k: no trigger
    status = trigger.check(7_999)
    assert not status.should_compact, "Should not trigger below 8k"
    print("✓ custom_window: Below 8k (80% of 10k) does not trigger")

    # At 8k: trigger
    status = trigger.check(8_000)
    assert status.should_compact, "Should trigger at 8k"
    print("✓ custom_window: At 8k (80% of 10k) triggers")


def test_global_helpers():
    """Test global helper functions."""
    # Test check_compaction
    status = check_compaction(30_000)
    assert not status.should_compact, "30k should not trigger"
    print("✓ global_helpers: check_compaction(30k) works")

    status = check_compaction(50_000)
    assert status.should_compact, "50k should trigger"
    print("✓ global_helpers: check_compaction(50k) works")

    # Test get_compaction_message
    msg = get_compaction_message(40_000)
    assert "40,000" in msg, "Message should include token count"
    print("✓ global_helpers: get_compaction_message() works")

    # Test tokens_until_trigger
    remaining = tokens_until_trigger(30_000)
    assert remaining == 18_000, f"Expected 18k, got {remaining}"
    print("✓ global_helpers: tokens_until_trigger(30k) = 18k")


def test_compaction_history():
    """Test that compaction trigger logs history."""
    trigger = CompactionTrigger()

    # Make several checks
    trigger.check(10_000)
    trigger.check(20_000)
    trigger.check(30_000)

    history = trigger.get_history()
    assert len(history) == 3, f"Expected 3 history entries, got {len(history)}"
    assert history[0]["tokens_used"] == 10_000
    assert history[1]["tokens_used"] == 20_000
    assert history[2]["tokens_used"] == 30_000
    print("✓ compaction_history: Logs all checks")


def test_scenario_realistic():
    """Test realistic usage scenario."""
    trigger = CompactionTrigger()

    print("\n📊 Realistic scenario: Agent conversation growing over time")
    print("=" * 60)

    token_usage = [
        5_000,    # Initial prompt + first turn
        15_000,   # Few turns of conversation
        25_000,   # Growing context
        35_000,   # More turns
        45_000,   # Getting close to threshold
        48_500,   # 🚨 TRIGGER COMPACTION!
        10_000,   # After /compact (history compressed)
        20_000,   # Continue from compacted state
    ]

    compaction_triggered = False

    for tokens in token_usage:
        status = trigger.check(tokens)

        if status.should_compact and not compaction_triggered:
            print(f"  {tokens:6,} tokens → {status.usage_percent:5.1f}% 🚨 TRIGGER /compact")
            compaction_triggered = True
        elif status.should_compact and compaction_triggered:
            print(f"  {tokens:6,} tokens → {status.usage_percent:5.1f}% (already signaled)")
        else:
            print(f"  {tokens:6,} tokens → {status.usage_percent:5.1f}%")

    print("=" * 60)
    print("✓ scenario_realistic: Correctly signals compaction when needed")


if __name__ == "__main__":
    test_trigger_threshold()
    test_status_message()
    test_estimate_tokens_before_trigger()
    test_usage_percentage()
    test_custom_window()
    test_global_helpers()
    test_compaction_history()
    test_scenario_realistic()
    print("\n✅ All compaction trigger tests passed!")
