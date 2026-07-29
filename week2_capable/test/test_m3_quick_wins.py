"""
M3 Quick Wins Tests

Verify the three foundational token economy fixes:
1. Parameter requiredness preserved through to_boukensha_params → Tool → to_tools
2. Pair-safe compaction that never splits tool_use/tool_result pairs
3. Tool description trimming to reduce schema overhead
"""

import unittest
from src.boukensha.context import Context
from src.boukensha.message import Message
from src.boukensha.tool import Tool
from src.boukensha.tools.mcp import to_boukensha_params
from src.boukensha.backends.anthropic import Anthropic


class TestParameterRequiredness(unittest.TestCase):
    """M3.1: Parameter requiredness is preserved through the whole chain."""

    def test_to_boukensha_params_preserves_required(self):
        """to_boukensha_params correctly marks required vs optional parameters."""
        input_schema = {
            "properties": {
                "target": {"type": "string", "description": "The target room name."},
                "force": {"type": "boolean", "description": "Force the move."},
            },
            "required": ["target"],
        }

        params = to_boukensha_params(input_schema)

        self.assertTrue(params["target"]["required"], "target should be required")
        self.assertFalse(params["force"]["required"], "force should be optional")

    def test_anthropic_backend_extracts_required(self):
        """Anthropic backend correctly builds input_schema with top-level required list."""
        backend = Anthropic(api_key="test-key", model="claude-haiku-4-5")

        tools = {
            "look": Tool(
                name="look",
                description="Describe the current room.",
                parameters={
                    "room": {"type": "string", "description": "Room name", "required": False},
                },
                block=lambda: {},
            ),
        }

        tool_defs = backend.to_tools(tools)

        self.assertEqual(len(tool_defs), 1)
        self.assertEqual(tool_defs[0]["name"], "look")
        # required list should be empty since room is optional
        self.assertEqual(tool_defs[0]["input_schema"]["required"], [])
        # the parameter itself should NOT have a "required" key in the schema
        self.assertNotIn("required", tool_defs[0]["input_schema"]["properties"]["room"])

    def test_all_required_parameters(self):
        """All required parameters are correctly identified."""
        tools = {
            "move": Tool(
                name="move",
                description="Move in a direction.",
                parameters={
                    "direction": {"type": "string", "description": "Direction", "required": True},
                },
                block=lambda: {},
            ),
        }

        backend = Anthropic(api_key="test-key", model="claude-haiku-4-5")
        tool_defs = backend.to_tools(tools)

        self.assertEqual(tool_defs[0]["input_schema"]["required"], ["direction"])


class TestDescriptionTrimming(unittest.TestCase):
    """M3.3: Tool descriptions are trimmed to reduce schema tokens."""

    def test_trim_to_first_sentence(self):
        """Descriptions are trimmed to first sentence."""
        input_schema = {
            "properties": {
                "target": {
                    "type": "string",
                    "description": "The target room name. This is optional. You can also specify force.",
                },
            },
            "required": [],
        }

        params = to_boukensha_params(input_schema)

        # Should only include first sentence
        self.assertEqual(params["target"]["description"], "The target room name")

    def test_trim_to_max_chars(self):
        """Long descriptions are clamped to max_desc_chars."""
        input_schema = {
            "properties": {
                "target": {
                    "type": "string",
                    "description": "This is a very long description that goes on and on "
                                  "and contains way too much information for what should be "
                                  "a concise tool parameter description.",
                },
            },
            "required": [],
        }

        params = to_boukensha_params(input_schema, max_desc_chars=50)

        # Should be clamped to ~50 chars
        self.assertLessEqual(len(params["target"]["description"]), 55)
        self.assertTrue(params["target"]["description"].endswith("…"))

    def test_enum_appended_when_fits(self):
        """Enum values are appended if they fit within max_desc_chars."""
        input_schema = {
            "properties": {
                "kind": {
                    "type": "string",
                    "description": "Check what.",
                    "enum": ["score", "inventory", "exits"],
                },
            },
            "required": [],
        }

        params = to_boukensha_params(input_schema, max_desc_chars=200)

        # Should include the enum list since it fits
        self.assertIn("score", params["kind"]["description"])
        self.assertIn("inventory", params["kind"]["description"])


class TestPairSafeCompaction(unittest.TestCase):
    """M3.2: Compaction never splits tool_use/tool_result pairs."""

    def test_compaction_respects_pair_boundaries(self):
        """Compaction finds boundaries that don't split pairs."""
        ctx = Context()

        # Build a message sequence with tool pairs:
        # 0. user: "look"
        # 1. assistant: tool_use[id="1"] for "look"
        # 2. tool_result[id="1"]: room description
        # 3. assistant: tool_use[id="2"] for "move"
        # 4. tool_result[id="2"]: move result
        ctx.messages = [
            Message(role="user", content="What do I see?"),
            Message(
                role="assistant",
                content=[{"type": "tool_use", "id": "look_1", "name": "look", "input": {}}],
            ),
            Message(role="tool_result", content="A dark room.", tool_use_id="look_1"),
            Message(
                role="assistant",
                content=[{"type": "tool_use", "id": "move_1", "name": "move", "input": {"direction": "north"}}],
            ),
            Message(role="tool_result", content="You move north.", tool_use_id="move_1"),
        ]

        # Compacting to 60% (should drop 2 msgs) from a 5-msg sequence
        dropped = ctx.compact_messages(target_fraction=0.60)

        # Should drop messages at a safe boundary (after a tool_result pair)
        # We want to reach 3 msgs (60% of 5), so drop 2
        self.assertEqual(dropped, 2)

        # Should be left with: assistant (move), tool_result (move)
        self.assertEqual(len(ctx.messages), 3)
        self.assertEqual(ctx.messages[0].role, "assistant")
        self.assertEqual(ctx.messages[1].role, "tool_result")
        self.assertEqual(ctx.messages[2].role, "tool_result")

    def test_compaction_never_leaves_orphaned_tool_use(self):
        """Compaction never drops a tool_result while keeping its tool_use."""
        ctx = Context()

        # Messages where compaction could incorrectly split a pair
        ctx.messages = [
            Message(role="user", content="Start"),
            Message(
                role="assistant",
                content=[{"type": "tool_use", "id": "a", "name": "look", "input": {}}],
            ),
            Message(role="tool_result", content="Result A", tool_use_id="a"),
            Message(
                role="assistant",
                content=[{"type": "tool_use", "id": "b", "name": "move", "input": {}}],
            ),
            # Only one message: either tool_use without result, or result without use
        ]

        # If we try to drop 2 messages (to reach 60%), it should be safe
        # The "b" tool_use is orphaned, so a safe boundary is after "a"'s result
        dropped = ctx.compact_messages(target_fraction=0.60)

        # Should never leave a tool_use without its result
        for i, msg in enumerate(ctx.messages):
            if msg.role == "assistant" and isinstance(msg.content, list):
                for block in msg.content:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        # Find if there's a corresponding tool_result
                        tool_id = block.get("id")
                        has_result = any(
                            m.role == "tool_result" and m.tool_use_id == tool_id
                            for m in ctx.messages
                        )
                        self.assertTrue(has_result, f"tool_use {tool_id} missing its result")

    def test_compaction_respects_minimum_messages(self):
        """Compaction keeps at least 2 messages."""
        ctx = Context()

        # Minimal message set
        ctx.messages = [
            Message(role="user", content="Hello"),
            Message(role="assistant", content="Hi"),
        ]

        # Try to compact (should not drop anything)
        dropped = ctx.compact_messages(target_fraction=0.30)

        self.assertEqual(dropped, 0)
        self.assertEqual(len(ctx.messages), 2)

    def test_empty_context_compaction(self):
        """Compaction handles empty or near-empty contexts gracefully."""
        ctx = Context()

        # Empty
        dropped = ctx.compact_messages()
        self.assertEqual(dropped, 0)

        # Single message
        ctx.messages = [Message(role="user", content="Hello")]
        dropped = ctx.compact_messages()
        self.assertEqual(dropped, 0)


class TestM3Integration(unittest.TestCase):
    """Integration: all M3 fixes work together."""

    def test_required_params_reach_anthropic_payload(self):
        """Required params flow correctly through MCP → Tool → Anthropic payload."""
        # Simulate what happens when an MCP tool is registered
        input_schema = {
            "properties": {
                "target": {"type": "string", "description": "Target room. Move north or south."},
                "speed": {"type": "string", "description": "How fast?", "enum": ["slow", "fast"]},
            },
            "required": ["target"],
        }

        # Step 1: MCP → Tool parameters
        params = to_boukensha_params(input_schema)
        tool = Tool(name="move", description="Move in a direction.", parameters=params, block=lambda: {})

        # Step 2: Tool → Anthropic payload
        backend = Anthropic(api_key="test", model="claude-haiku-4-5")
        payload_tools = backend.to_tools({"move": tool})

        # Verify the flow:
        # - Only "target" should be in required
        # - No parameter should have a "required" key in properties
        self.assertEqual(payload_tools[0]["input_schema"]["required"], ["target"])
        for prop in payload_tools[0]["input_schema"]["properties"].values():
            self.assertNotIn("required", prop)


if __name__ == "__main__":
    unittest.main()
