"""
M4: Phase Transition Tests

Verify phase detection from tool results works correctly.
"""

import unittest
from src.boukensha.context import Context


class TestPhaseTransitions(unittest.TestCase):
    """M4.4: Test phase detection from tool results."""

    def setUp(self):
        self.ctx = Context(system="Test system")
        self.ctx.set_phase("exploring")

    def test_combat_detection(self):
        """Combat keywords trigger fighting phase."""
        combat_results = [
            "You attack the goblin. You hit! Damage: 15 HP",
            "The goblin counter-attacks! Round 2 of battle.",
            "You are in combat with an enemy warrior",
        ]

        for result in combat_results:
            new_phase = self.ctx.detect_phase_from_result(result)
            if self.ctx.current_phase != "fighting":
                self.assertEqual(new_phase, "fighting", f"Failed for: {result}")
                self.ctx.set_phase("fighting")

    def test_trading_detection(self):
        """Shop keywords trigger trading phase."""
        self.ctx.set_phase("exploring")

        trading_results = [
            "Welcome to the shop! What would you like to buy?",
            "The merchant says: I have fine wares to trade.",
            "You can buy or sell items with the vendor here.",
        ]

        for result in trading_results:
            new_phase = self.ctx.detect_phase_from_result(result)
            if self.ctx.current_phase != "trading":
                self.assertEqual(new_phase, "trading", f"Failed for: {result}")
                self.ctx.set_phase("trading")

    def test_exploration_persistence(self):
        """Exploration phase persists without combat indicators."""
        self.ctx.set_phase("exploring")

        exploration_results = [
            "You are in a dark forest.",
            "You move north.",
            "There are no enemies here.",
        ]

        for result in exploration_results:
            new_phase = self.ctx.detect_phase_from_result(result)
            # Phase should not change
            self.assertIsNone(new_phase)
            self.assertEqual(self.ctx.current_phase, "exploring")

    def test_combat_to_exploring_transition(self):
        """Fighting phase returns to exploring after N turns without combat."""
        self.ctx.set_phase("fighting")
        self.ctx.turns_since_combat = 0

        non_combat_results = [
            "You successfully flee the battle.",
            "The area is quiet now.",
            "No enemies in sight.",
        ]

        # First few turns should stay in fighting mode.
        # detect_phase_from_result() increments turns_since_combat automatically,
        # so we don't manually increment (that was causing the test to fail).
        for result in non_combat_results:
            new_phase = self.ctx.detect_phase_from_result(result)
            # Should stay in fighting until turns_since_combat > 3
            self.assertNotEqual(new_phase, "exploring",
                f"Should not transition to exploring yet (turns={self.ctx.turns_since_combat})")

        # Verify that after enough turns without combat, it transitions
        self.ctx.turns_since_combat = 4
        new_phase = self.ctx.detect_phase_from_result("You explore quietly.")
        self.assertEqual(new_phase, "exploring")

    def test_combat_resets_counter(self):
        """Combat keywords reset the turns_since_combat counter."""
        self.ctx.set_phase("exploring")
        self.ctx.turns_since_combat = 10

        combat_result = "A goblin attacks you!"
        new_phase = self.ctx.detect_phase_from_result(combat_result)

        # Counter should reset to 0
        self.assertEqual(self.ctx.turns_since_combat, 0)

    def test_phase_methods(self):
        """Test set_phase and current_phase tracking."""
        # Start in exploring
        self.assertEqual(self.ctx.current_phase, "exploring")

        # Set to fighting
        self.ctx.set_phase("fighting")
        self.assertEqual(self.ctx.current_phase, "fighting")

        # Set to trading
        self.ctx.set_phase("trading")
        self.assertEqual(self.ctx.current_phase, "trading")

        # Set to full
        self.ctx.set_phase("full")
        self.assertEqual(self.ctx.current_phase, "full")

    def test_invalid_phase_not_set(self):
        """Invalid phase names are rejected."""
        self.ctx.set_phase("exploring")
        original_phase = self.ctx.current_phase

        # Try to set invalid phase
        self.ctx.set_phase("invalid_phase")

        # Should remain unchanged
        self.assertEqual(self.ctx.current_phase, original_phase)


if __name__ == "__main__":
    unittest.main()
