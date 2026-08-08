#!/usr/bin/env python3
"""
MUD play example with practice skill tool enabled.

This example demonstrates practicing skills with the guildmaster.

Navigate to:
- Guild of Swordsmen (from Temple Square: south, east, east)
- Bar of Swordsmen (from Guild entrance: east)
- Tournament and Practice Yard (from Bar: south)

Then use the practice tool to train skills like kick, punch, dodge, etc.

Usage:
    python3 examples/practice_skill_example.py
"""

import os
from pathlib import Path

os.environ.setdefault(
    "BOUKENSHA_DIR",
    str(Path(__file__).resolve().parent.parent.parent / ".boukensha"),
)

import boukensha

# Import the tool adder
import sys
sys.path.insert(0, ".")
from add_practice_tool import add_practice_tool


def main():
    """Run a MUD session with practice skill enabled."""

    print("=" * 70)
    print("MUD PLAY WITH PRACTICE SKILL TOOL")
    print("=" * 70)
    print()
    print("This example enables the 'practice' tool for training with the guildmaster.")
    print()
    print("To practice a skill:")
    print("  1. Navigate to Guild of Swordsmen")
    print("  2. Go to Tournament and Practice Yard (south from Bar of Swordsmen)")
    print("  3. Use: practice <skill>")
    print()
    print("Available skills:")
    print("  - kick          (leg strike technique)")
    print("  - punch         (fist strike technique)")
    print("  - dodge         (evasion technique)")
    print("  - parry         (defense technique)")
    print("  - backstab      (precision strike)")
    print("  - headbutt      (head strike)")
    print("  - whirlwind     (multi-target strike)")
    print()
    print("=" * 70)
    print()

    cfg = boukensha.config()
    print(f"Config: {cfg}")
    print(f"API key set? {os.environ.get('ANTHROPIC_API_KEY') is not None}")
    print()

    # Run with practice tool enabled
    result = boukensha.run(
        task=(
            "Navigate to the Guild of Swordsmen and find the guildmaster. "
            "Go to the Tournament and Practice Yard. "
            "Then practice the kick skill with the guildmaster to improve your fighting abilities."
        ),
        configure=add_practice_tool,  # Enable practice tool
        working_dir=False,
    )

    print()
    print("=" * 70)
    print("RESULT:")
    print("=" * 70)
    print(result)


if __name__ == "__main__":
    main()
