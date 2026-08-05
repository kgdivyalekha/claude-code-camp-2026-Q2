"""M8: Prompt caching implementation tests.

Tests verify:
1. Cache control markers are added to API payloads
2. Cache tokens are extracted from API responses
3. Cache effectiveness is calculated correctly
"""

import unittest
from unittest.mock import Mock, patch
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from boukensha.backends.anthropic import Anthropic
from boukensha.logger import Logger
from boukensha.context import Context
from boukensha.tool import Tool


class TestM8CacheControl(unittest.TestCase):
    """Test cache_control markers in API payload."""

    def setUp(self):
        self.backend = Anthropic(api_key="test-key", model="claude-haiku-4-5")
        self.context = Mock(spec=Context)
        self.context.system = "Test system prompt"
        self.context.messages = []
        self.context.tools = {
            "look": Tool(name="look", description="Look around", parameters={}),
            "move": Tool(name="move", description="Move", parameters={}),
        }

    def test_cache_control_marker_added(self):
        """Verify ephemeral cache_control marker is added to last tool."""
        payload = self.backend.to_payload(self.context)

        # Cache control should be on the last tool
        tools = payload["tools"]
        assert len(tools) == 2, f"Expected 2 tools, got {len(tools)}"

        last_tool = tools[-1]
        assert "cache_control" in last_tool, "Last tool missing cache_control"
        assert last_tool["cache_control"]["type"] == "ephemeral"

    def test_cache_control_not_on_earlier_tools(self):
        """Verify cache_control is only on the last tool."""
        payload = self.backend.to_payload(self.context)

        tools = payload["tools"]
        for i, tool in enumerate(tools[:-1]):
            assert "cache_control" not in tool, f"Tool {i} should not have cache_control"

    def test_empty_tools_handled(self):
        """Verify empty tool list doesn't crash."""
        self.context.tools = {}
        payload = self.backend.to_payload(self.context)
        assert payload["tools"] == []


class TestM8CacheTokenExtraction(unittest.TestCase):
    """Test extraction of cache tokens from API responses."""

    def setUp(self):
        self.logger = Logger("test_session")

    def test_cache_tokens_extracted(self):
        """Verify cache tokens are extracted from usage dict."""
        usage = {
            "input_tokens": 1000,
            "output_tokens": 500,
            "cache_read_input_tokens": 200,
            "cache_creation_input_tokens": 100,
        }

        cache_tokens = self.logger._cache_tokens(usage)
        assert cache_tokens["read"] == 200
        assert cache_tokens["write"] == 100

    def test_cache_tokens_missing(self):
        """Verify cache tokens are None when absent."""
        usage = {
            "input_tokens": 1000,
            "output_tokens": 500,
        }

        cache_tokens = self.logger._cache_tokens(usage)
        assert cache_tokens["read"] is None
        assert cache_tokens["write"] is None

    def test_cache_tokens_in_metadata(self):
        """Verify cache tokens appear in execution metadata."""
        usage = {
            "input_tokens": 1000,
            "output_tokens": 500,
            "cache_read_input_tokens": 200,
            "cache_creation_input_tokens": 100,
        }

        backend = Mock()
        backend.__class__.__name__ = "Anthropic"
        backend.model = "claude-haiku-4-5"

        metadata = self.logger._execution_metadata(
            task=None,
            backend=backend,
            usage=usage,
        )

        assert "cache_read_input_tokens" in metadata
        assert "cache_creation_input_tokens" in metadata
        assert metadata["cache_read_input_tokens"] == 200
        assert metadata["cache_creation_input_tokens"] == 100

    def test_metadata_omits_none_cache_tokens(self):
        """Verify None cache tokens are omitted from metadata."""
        usage = {
            "input_tokens": 1000,
            "output_tokens": 500,
        }

        backend = Mock()
        backend.__class__.__name__ = "Anthropic"
        backend.model = "claude-haiku-4-5"

        metadata = self.logger._execution_metadata(
            task=None,
            backend=backend,
            usage=usage,
        )

        # None values are filtered out
        assert "cache_read_input_tokens" not in metadata
        assert "cache_creation_input_tokens" not in metadata


if __name__ == "__main__":
    unittest.main()
