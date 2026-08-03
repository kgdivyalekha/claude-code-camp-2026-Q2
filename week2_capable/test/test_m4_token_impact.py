"""
M4: Token Impact Measurement

Verify that ToolGate phase restrictions actually reduce token usage.
"""

import unittest
import json
from src.boukensha.tokens.gate import ToolGate
from src.boukensha.backends.anthropic import Anthropic


class TestM4TokenReduction(unittest.TestCase):
    """M4.5: Measure token savings from phase-based tool gating."""

    def setUp(self):
        self.gate = ToolGate()
        self.backend = Anthropic(api_key="test-key", model="claude-haiku-4-5")

    def test_exploring_phase_reduces_token_overhead(self):
        """Exploring phase reduces schema token overhead by ~73%."""
        # Get full tool set (26 tools)
        full_tools = self._get_all_tools()
        full_payload = self.backend.to_tools(full_tools)
        full_schema_json = json.dumps(full_payload)
        full_tokens = len(full_schema_json) // 4  # Rough estimate: 4 chars per token

        # Get exploring phase tools (7 tools)
        exploring_tool_names = self.gate.visible("exploring")
        exploring_tools = {k: v for k, v in full_tools.items() if k in exploring_tool_names}
        exploring_payload = self.backend.to_tools(exploring_tools)
        exploring_schema_json = json.dumps(exploring_payload)
        exploring_tokens = len(exploring_schema_json) // 4

        # Calculate reduction
        reduction_pct = (full_tokens - exploring_tokens) / full_tokens * 100

        print(f"\nFull schema tokens: ~{full_tokens}")
        print(f"Exploring schema tokens: ~{exploring_tokens}")
        print(f"Reduction: ~{reduction_pct:.1f}%")

        # Verify at least 65% reduction
        self.assertGreater(reduction_pct, 65, "Should reduce tokens by at least 65%")

    def test_capability_regression_no_tool_loss(self):
        """Verify no tools are lost when gating is applied."""
        # Get all tools
        all_tool_names = set(self._get_all_tools().keys())

        # Collect all tools visible in any phase
        visible_across_phases = set()
        for phase in ["exploring", "fighting", "trading", "full"]:
            visible = self.gate.visible(phase)
            visible_across_phases.update(visible)

        # All tools should be visible in some phase
        missing = all_tool_names - visible_across_phases
        self.assertEqual(len(missing), 0, f"Tools lost in gating: {missing}")

    def test_phase_tool_progression(self):
        """Phases are designed to reduce schema overhead at different stages.

        Note: Not strictly cumulative—trading removes combat/movement but adds inventory/utility.
        """
        exploring = set(self.gate.visible("exploring"))
        fighting = set(self.gate.visible("fighting"))
        trading = set(self.gate.visible("trading"))
        full = set(self.gate.visible("full"))

        # Verify phase progression
        self.assertTrue(exploring.issubset(fighting), "Fighting includes all exploring tools")
        self.assertTrue(trading.issubset(full), "Full includes all trading tools")
        self.assertTrue(fighting.issubset(full), "Full includes all fighting tools")

        # Verify phase counts match design
        self.assertEqual(len(exploring), 7, "Exploring: perception + movement")
        self.assertEqual(len(fighting), 10, "Fighting: exploring + combat")
        self.assertEqual(len(trading), 14, "Trading: perception + inventory + utility (no movement/combat)")
        self.assertEqual(len(full), 26, "Full: all categories")

    def test_core_tools_available(self):
        """look and check always visible; move visible except in trading phase."""
        always_visible = {"look", "check"}
        move_visible_phases = {"exploring", "fighting", "full"}

        for phase in ["exploring", "fighting", "trading", "full"]:
            visible = set(self.gate.visible(phase))

            # look and check always visible
            for tool in always_visible:
                self.assertIn(tool, visible, f"{tool} missing in {phase}")

            # move visible in most phases, intentionally excluded from trading
            if phase in move_visible_phases:
                self.assertIn("move", visible, f"move should be in {phase}")
            else:
                self.assertNotIn("move", visible, f"move excluded from {phase} for schema reduction")

    def _get_all_tools(self):
        """Return a mock set of tools defined in ToolGate for testing."""
        from src.boukensha.tool import Tool

        tools = {}
        # Use only tools actually defined in ToolGate.CATEGORIES
        tool_specs = [
            # Perception
            ("look", "Describe the current room."),
            ("examine", "Examine an object or NPC in detail."),
            ("check", "Check your status, inventory, or exits."),

            # Movement
            ("move", "Move in a direction."),
            ("flee", "Flee from combat or danger."),
            ("set_position", "Manually set your position for testing."),
            ("track", "Track a creature or follow a trail."),

            # Combat
            ("attack", "Attack an enemy in combat."),
            ("skill_strike", "Use a special combat skill."),
            ("consider", "Evaluate an enemy's strength."),

            # Communication
            ("say", "Speak to characters."),
            ("tell", "Send a private message."),
            ("channel_say", "Say on a channel."),

            # Inventory
            ("get_item", "Pick up an item."),
            ("drop_item", "Drop an item from inventory."),
            ("put_item", "Put an item in a container."),
            ("equip_item", "Equip armor or weapon."),
            ("consume_item", "Consume an item."),

            # Magic
            ("cast_spell", "Cast a spell."),
            ("use_magic_item", "Use a magic item."),

            # Utility
            ("shop", "Interact with a shopkeeper."),
            ("practice", "Practice a skill with a trainer."),
            ("save_character", "Save your character."),
            ("send_raw", "Send raw MUD command."),
            ("poll", "Poll the server."),
            ("mud_status", "Check MUD status."),
        ]

        for name, desc in tool_specs:
            tools[name] = Tool(
                name=name,
                description=desc,
                parameters={},
                block=lambda: {},
            )

        return tools


if __name__ == "__main__":
    unittest.main()
