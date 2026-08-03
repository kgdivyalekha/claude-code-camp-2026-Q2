"""
M4: ToolGate Tests

Verify phase-aware tool visibility works correctly.
"""

import unittest
from src.boukensha.tokens.gate import ToolGate


class TestToolGateVisibility(unittest.TestCase):
    """M4.1: Tool visibility by phase."""

    def setUp(self):
        self.gate = ToolGate()

    def test_exploring_phase_tools(self):
        """Exploring phase shows only perception + movement."""
        visible = self.gate.visible("exploring")

        # Should have 7 tools
        self.assertEqual(len(visible), 7)

        # Should include perception
        self.assertIn("look", visible)
        self.assertIn("examine", visible)
        self.assertIn("check", visible)

        # Should include movement
        self.assertIn("move", visible)
        self.assertIn("flee", visible)
        self.assertIn("track", visible)
        self.assertIn("set_position", visible)

        # Should NOT include combat
        self.assertNotIn("attack", visible)
        self.assertNotIn("skill_strike", visible)

        # Should NOT include inventory
        self.assertNotIn("get_item", visible)
        self.assertNotIn("equip_item", visible)

    def test_fighting_phase_tools(self):
        """Fighting phase adds combat to perception + movement."""
        visible = self.gate.visible("fighting")

        # Should have ~10 tools
        self.assertEqual(len(visible), 10)

        # Should include perception + movement
        self.assertIn("look", visible)
        self.assertIn("move", visible)

        # Should include combat
        self.assertIn("attack", visible)
        self.assertIn("skill_strike", visible)
        self.assertIn("consider", visible)

        # Should NOT include inventory
        self.assertNotIn("get_item", visible)

    def test_trading_phase_tools(self):
        """Trading phase includes perception + inventory + utility (no movement or combat)."""
        visible = self.gate.visible("trading")

        # Should have 14 tools
        self.assertEqual(len(visible), 14)

        # Should include perception
        self.assertIn("look", visible)
        self.assertIn("check", visible)

        # Should include inventory
        self.assertIn("get_item", visible)
        self.assertIn("drop_item", visible)
        self.assertIn("equip_item", visible)

        # Should include utility
        self.assertIn("shop", visible)
        self.assertIn("practice", visible)

        # Should NOT include combat
        self.assertNotIn("attack", visible)

        # Should NOT include movement (movement is trading-specific reduction)
        self.assertNotIn("move", visible)
        self.assertNotIn("flee", visible)

    def test_full_phase_tools(self):
        """Full phase shows all 26 tools."""
        visible = self.gate.visible("full")

        # Should have all 26 tools
        self.assertEqual(len(visible), 26)

        # Check representation of all categories
        self.assertIn("look", visible)  # perception
        self.assertIn("move", visible)  # movement
        self.assertIn("attack", visible)  # combat
        self.assertIn("say", visible)  # communication
        self.assertIn("get_item", visible)  # inventory
        self.assertIn("cast_spell", visible)  # magic
        self.assertIn("shop", visible)  # utility

    def test_always_visible_floor(self):
        """look and check are always visible; move visible except in trading."""
        always_visible = {"look", "check"}
        move_visible_phases = {"exploring", "fighting", "full"}

        for phase in ["exploring", "fighting", "trading", "full"]:
            visible = self.gate.visible(phase)

            # look and check always visible
            for tool in always_visible:
                self.assertIn(
                    tool, visible, f"{tool} should be visible in {phase} phase"
                )

            # move visible except in trading (schema reduction)
            if phase in move_visible_phases:
                self.assertIn("move", visible, f"move should be visible in {phase} phase")
            else:
                self.assertNotIn("move", visible, f"move intentionally excluded from {phase} phase")

    def test_invalid_phase_defaults_to_full(self):
        """Invalid phase name defaults to full visibility."""
        visible = self.gate.visible("invalid_phase")

        # Should default to full phase
        self.assertEqual(len(visible), 26)

    def test_tools_sent_count(self):
        """tools_sent() returns accurate count for each phase."""
        self.assertEqual(self.gate.tools_sent("exploring"), 7)
        self.assertEqual(self.gate.tools_sent("fighting"), 10)
        self.assertEqual(self.gate.tools_sent("trading"), 14)
        self.assertEqual(self.gate.tools_sent("full"), 26)


class TestToolGatePhaseDetection(unittest.TestCase):
    """M4.2: Detect which phase a tool belongs to."""

    def setUp(self):
        self.gate = ToolGate()

    def test_tool_phase_lookup(self):
        """Get minimum phase where tool becomes visible."""
        # Perception tools appear in all phases
        self.assertEqual(self.gate.get_phase_for_tool("look"), "exploring")
        self.assertEqual(self.gate.get_phase_for_tool("check"), "exploring")

        # Combat tools appear starting in fighting
        self.assertEqual(self.gate.get_phase_for_tool("attack"), "fighting")

        # Inventory tools appear in trading phase
        self.assertEqual(
            self.gate.get_phase_for_tool("get_item"), "trading"
        )

        # Unknown tool
        self.assertIsNone(self.gate.get_phase_for_tool("unknown_tool"))

    def test_always_visible_in_floor(self):
        """Check floor tools are always visible."""
        for tool in ["look", "move", "check"]:
            self.assertTrue(
                self.gate.is_always_visible(tool),
                f"{tool} should be in always-visible floor"
            )

        # Non-floor tools
        self.assertFalse(self.gate.is_always_visible("attack"))


class TestToolGateSchemaReduction(unittest.TestCase):
    """M4.3: Verify schema overhead reduction metrics."""

    def setUp(self):
        self.gate = ToolGate()

    def test_schema_reduction_exploring(self):
        """Exploring phase reduces schema from 26 to 7 tools (73%)."""
        full_count = self.gate.tools_sent("full")
        exploring_count = self.gate.tools_sent("exploring")

        reduction = (full_count - exploring_count) / full_count
        self.assertAlmostEqual(reduction, 0.73, places=1)  # ~73%

    def test_schema_reduction_fighting(self):
        """Fighting phase reduces schema from 26 to 10 tools (62%)."""
        full_count = self.gate.tools_sent("full")
        fighting_count = self.gate.tools_sent("fighting")

        reduction = (full_count - fighting_count) / full_count
        self.assertAlmostEqual(reduction, 0.62, places=1)  # ~62%

    def test_schema_reduction_trading(self):
        """Trading phase reduces schema from 26 to 14 tools (46%)."""
        full_count = self.gate.tools_sent("full")
        trading_count = self.gate.tools_sent("trading")

        reduction = (full_count - trading_count) / full_count
        self.assertAlmostEqual(reduction, 0.46, places=1)  # ~46%


if __name__ == "__main__":
    unittest.main()
