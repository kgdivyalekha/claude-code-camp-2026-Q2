"""M8: Prompt caching + combined measurement tests.

Tests verify:
1. Cache control markers are added to system message and tools
2. Cache tokens are properly extracted and logged
3. Cache effectiveness calculations work correctly
4. Combined measurement shows all M3-M8 optimizations together
"""

import json
import sqlite3
import tempfile
from pathlib import Path
from typing import Any, Dict

import pytest

from boukensha.backends.anthropic import Anthropic
from boukensha.context import Context
from boukensha.logger import Logger
from boukensha.message import Message
from boukensha.observability.analytics import Analytics
from boukensha.prompt_builder import PromptBuilder
from boukensha.tool import Tool


class TestPromptCachingPayload:
    """Test that cache_control markers are correctly added to payloads."""

    def test_system_message_has_cache_control(self):
        """System message should include cache_control ephemeral marker."""
        backend = Anthropic(api_key="test", model="claude-haiku-4-5")
        context = Context(task=None, system="You are a helpful assistant.")

        payload = backend.to_payload(context, enable_cache=True)

        # System should be a list with cache_control
        assert isinstance(payload["system"], list)
        assert len(payload["system"]) == 1
        assert payload["system"][0]["type"] == "text"
        assert payload["system"][0]["text"] == "You are a helpful assistant."
        assert payload["system"][0]["cache_control"] == {"type": "ephemeral"}

    def test_tools_have_cache_control_on_last(self):
        """Last tool in list should have cache_control ephemeral marker."""
        backend = Anthropic(api_key="test", model="claude-haiku-4-5")
        context = Context(task=None, system="System")

        # Add tools
        tool1 = Tool(name="tool1", description="Tool 1")
        tool2 = Tool(name="tool2", description="Tool 2")
        context.register_tool(tool1)
        context.register_tool(tool2)

        payload = backend.to_payload(context, enable_cache=True)

        # All tools except last should not have cache_control
        assert "cache_control" not in payload["tools"][0]
        # Last tool should have cache_control
        assert payload["tools"][-1]["cache_control"] == {"type": "ephemeral"}

    def test_cache_control_disabled(self):
        """When enable_cache=False, no cache_control markers should be present."""
        backend = Anthropic(api_key="test", model="claude-haiku-4-5")
        context = Context(task=None, system="System")
        context.register_tool(Tool(name="test", description="Test"))

        payload = backend.to_payload(context, enable_cache=False)

        # System should be plain string
        assert isinstance(payload["system"], str)
        # Tools should not have cache_control
        for tool in payload["tools"]:
            assert "cache_control" not in tool

    def test_empty_system_skips_cache_control(self):
        """When system is empty, should skip cache_control."""
        backend = Anthropic(api_key="test", model="claude-haiku-4-5")
        context = Context(task=None, system="")

        payload = backend.to_payload(context, enable_cache=True)

        # System should be empty string (no cache_control added)
        assert payload["system"] == ""


class TestCacheTokenTracking:
    """Test that cache tokens are properly extracted and logged."""

    def test_logger_extracts_cache_tokens(self):
        """Logger should extract cache_read_input_tokens and cache_creation_input_tokens."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = Logger(session_id="test-cache", dir=tmpdir)

            # Simulate API response with cache tokens
            usage = {
                "input_tokens": 1000,
                "output_tokens": 100,
                "cache_read_input_tokens": 500,  # Cache hit
                "cache_creation_input_tokens": 0,  # No cache write
            }
            backend = Anthropic(api_key="test", model="claude-haiku-4-5")
            logger.response(
                text="Response text",
                usage=usage,
                stop_reason="end_turn",
                backend=backend
            )
            logger.close()

            # Read back the logged event
            with open(logger.path) as f:
                lines = f.readlines()

            # Find the response event
            events = [json.loads(line) for line in lines if line.strip()]
            response_events = [e for e in events if e.get("phase") == "response"]

            assert len(response_events) > 0
            resp = response_events[0]
            assert resp["cache_read_input_tokens"] == 500
            assert resp["cache_creation_input_tokens"] == 0

    def test_logger_handles_missing_cache_tokens(self):
        """Logger should gracefully handle responses without cache tokens."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = Logger(session_id="test-no-cache", dir=tmpdir)

            # API response without cache tokens
            usage = {
                "input_tokens": 1000,
                "output_tokens": 100,
            }
            backend = Anthropic(api_key="test", model="claude-haiku-4-5")
            logger.response(
                text="Response text",
                usage=usage,
                stop_reason="end_turn",
                backend=backend
            )
            logger.close()

            # Read back
            with open(logger.path) as f:
                lines = f.readlines()

            events = [json.loads(line) for line in lines if line.strip()]
            response_events = [e for e in events if e.get("phase") == "response"]

            resp = response_events[0]
            # Missing cache tokens should not be in the response
            assert "cache_read_input_tokens" not in resp or resp.get("cache_read_input_tokens") is None
            assert "cache_creation_input_tokens" not in resp or resp.get("cache_creation_input_tokens") is None


class TestCacheEffectiveness:
    """Test cache effectiveness analytics."""

    def test_cache_hit_rate_calculation(self):
        """Analytics should correctly calculate cache hit rate."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "events.db"

            # Create events.db with cache data
            conn = sqlite3.connect(db_path)
            conn.execute("""
                CREATE TABLE events (
                    id INTEGER PRIMARY KEY,
                    session_id TEXT,
                    phase TEXT,
                    input_tokens INTEGER,
                    output_tokens INTEGER,
                    cache_read_tokens INTEGER,
                    cache_write_tokens INTEGER,
                    cost_usd REAL,
                    model TEXT,
                    provider TEXT,
                    details TEXT
                )
            """)

            # Insert events with cache tokens
            # First call: writes cache (no read)
            conn.execute(
                """INSERT INTO events
                   (session_id, phase, input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, model, provider, details)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                ("session-1", "response", 2000, 100, 0, 1000, "claude-haiku-4-5", "anthropic", "{}")
            )

            # Second call: reads cache
            conn.execute(
                """INSERT INTO events
                   (session_id, phase, input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, model, provider, details)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                ("session-1", "response", 100, 100, 1000, 0, "claude-haiku-4-5", "anthropic", "{}")
            )

            conn.commit()
            conn.close()

            # Query cache effectiveness
            analytics = Analytics(str(db_path))
            result = analytics.cache_effectiveness("session-1")

            # Total input = 2000 + 100 + 0 + 1000 = 3100
            # Cache read = 1000
            # Hit rate = 1000 / 3100 * 100 = 32.3%
            assert result["cache_read_tokens"] == 1000
            assert result["cache_write_tokens"] == 1000
            assert 32.0 < result["hit_rate"] < 33.0  # Allow for rounding
            assert result["cost_saving_usd"] > 0  # Should show savings

    def test_no_cache_hit_rate_when_no_cache(self):
        """Analytics should return 0 hit rate when no cache tokens present."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "events.db"

            conn = sqlite3.connect(db_path)
            conn.execute("""
                CREATE TABLE events (
                    id INTEGER PRIMARY KEY,
                    session_id TEXT,
                    phase TEXT,
                    input_tokens INTEGER,
                    output_tokens INTEGER,
                    cache_read_tokens INTEGER,
                    cache_write_tokens INTEGER,
                    cost_usd REAL,
                    model TEXT,
                    provider TEXT,
                    details TEXT
                )
            """)

            # No cache data
            conn.execute(
                """INSERT INTO events
                   (session_id, phase, input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, model, provider, details)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                ("session-1", "response", 2000, 100, 0, 0, "claude-haiku-4-5", "anthropic", "{}")
            )

            conn.commit()
            conn.close()

            analytics = Analytics(str(db_path))
            result = analytics.cache_effectiveness("session-1")

            assert result["cache_read_tokens"] == 0
            assert result["cache_write_tokens"] == 0
            assert result["hit_rate"] == 0


class TestCombinedMeasurement:
    """Test combined measurement of all M3-M8 optimizations."""

    def test_combined_token_savings(self):
        """Combined measurement should show total savings from M3-M8."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "events.db"

            conn = sqlite3.connect(db_path)
            conn.execute("""
                CREATE TABLE events (
                    id INTEGER PRIMARY KEY,
                    session_id TEXT,
                    phase TEXT,
                    input_tokens INTEGER,
                    output_tokens INTEGER,
                    cache_read_tokens INTEGER,
                    cache_write_tokens INTEGER,
                    cost_usd REAL,
                    model TEXT,
                    provider TEXT,
                    tools_sent INTEGER,
                    details TEXT
                )
            """)

            # Simulate a realistic scenario with all optimizations
            # M3: Description trimming (reduced schema)
            # M4: Tool gating (7 tools vs 26)
            # M6: World DB compression
            # M7: Repeat room compression
            # M8: Prompt caching

            for i in range(1, 11):  # 10 turns
                # Each turn has multiple iterations
                for it in range(1, 4):  # 3 iterations per turn
                    # M3+M4 combined: 7 tools × ~80 tokens = ~560 tokens schema
                    # M6+M7: Compressed results = ~100 tokens for repeats
                    # M8: Cache hits on some calls

                    input_tokens = 500 + (i * 50)  # Accumulating context
                    cache_read = 300 if it > 1 else 0  # Cache after first iteration

                    conn.execute(
                        """INSERT INTO events
                           (session_id, phase, input_tokens, output_tokens, cache_read_tokens,
                            cache_write_tokens, model, provider, tools_sent, details)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        ("combined-test", "response", input_tokens, 50, cache_read, 500 if it == 1 else 0,
                         "claude-haiku-4-5", "anthropic", 7, "{}")
                    )

            conn.commit()
            conn.close()

            analytics = Analytics(str(db_path))

            # Check all metrics
            breakdown = analytics.token_breakdown("combined-test")
            cost = analytics.cost_summary("combined-test")
            cache = analytics.cache_effectiveness("combined-test")
            schema = analytics.schema_overhead("combined-test")

            # Verify measurements
            assert breakdown.total_input_tokens > 0
            assert breakdown.cache_read_tokens > 0  # M8 should show cache reads
            assert cost.total_usd > 0
            assert cache.hit_rate > 0  # M8 should show hit rate
            assert schema.tools_sent == 7  # M4 should show gated tools


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
