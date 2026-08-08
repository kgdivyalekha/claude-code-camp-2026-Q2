"""Test proactive compaction at 80% of token budget (M8 enhancement)."""

import pytest
from boukensha.agent import Agent
from boukensha.context import Context
from boukensha.registry import Registry


class TestProactiveCompaction:
    """Test that agent compacts proactively at 80% of token budget."""

    def test_should_proactive_compact_calculates_threshold(self):
        """Should calculate 80% threshold correctly."""
        context = Context(task=None)
        registry = Registry()
        agent = Agent(
            context=context,
            registry=registry,
            builder=None,
            client=None,
            max_turn_tokens=1000,  # 1000 token budget
        )

        # At 0 tokens: should not compact
        context.add_turn_tokens(0, 0)
        assert agent._should_proactive_compact() is False

        # At 75% (750 tokens): should not compact yet
        context.add_turn_tokens(750, 0)
        assert agent._should_proactive_compact() is False

        # At 80% (800 tokens): should compact
        context.turn_tokens = 800
        assert agent._should_proactive_compact() is True

        # At 95% (950 tokens): should still compact
        context.turn_tokens = 950
        assert agent._should_proactive_compact() is True

        # At 100% (1000 tokens): should NOT compact (limit reached)
        context.turn_tokens = 1000
        assert agent._should_proactive_compact() is False

    def test_should_proactive_compact_disabled_when_no_limit(self):
        """Should not compact when max_turn_tokens is 0 (disabled)."""
        context = Context(task=None)
        registry = Registry()
        agent = Agent(
            context=context,
            registry=registry,
            builder=None,
            client=None,
            max_turn_tokens=0,  # Disabled
        )

        context.turn_tokens = 100
        assert agent._should_proactive_compact() is False

    def test_realistic_session_budget_scenario(self):
        """Test realistic 60k token budget (like session 20260808T003109Z)."""
        context = Context(task=None)
        registry = Registry()
        agent = Agent(
            context=context,
            registry=registry,
            builder=None,
            client=None,
            max_turn_tokens=60000,  # 60k token budget
        )

        # At 48k (80%): should compact
        context.turn_tokens = 48000
        assert agent._should_proactive_compact() is True

        # At 59k (98%): should still compact
        context.turn_tokens = 59000
        assert agent._should_proactive_compact() is True

        # At exactly 60k (100%): should not compact (hit limit)
        context.turn_tokens = 60000
        assert agent._should_proactive_compact() is False

        # Over limit (107%): should not compact
        context.turn_tokens = 64000
        assert agent._should_proactive_compact() is False

    def test_small_budget_scenario(self):
        """Test with very small budget to verify edge cases."""
        context = Context(task=None)
        registry = Registry()
        agent = Agent(
            context=context,
            registry=registry,
            builder=None,
            client=None,
            max_turn_tokens=100,  # Small 100 token budget
        )

        # 80% of 100 = 80
        context.turn_tokens = 79
        assert agent._should_proactive_compact() is False

        context.turn_tokens = 80
        assert agent._should_proactive_compact() is True

        context.turn_tokens = 99
        assert agent._should_proactive_compact() is True

        context.turn_tokens = 100
        assert agent._should_proactive_compact() is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
