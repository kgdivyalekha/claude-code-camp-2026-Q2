#!/usr/bin/env python3
"""
Example: Practice skill using send_raw command

The 'practice' tool from mud_manager appears to have limited exposure,
so we use send_raw as an escape hatch to send arbitrary MUD commands.

This demonstrates how to use send_raw to practice any skill.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import boukensha


def main():
    """Use send_raw to practice kick at the guildmaster."""

    task = """
    Navigate to the Tournament and Practice Yard at the Guild of Swordsmen.

    Path:
    1. From your current location, go to Market Square (south from Temple Square)
    2. Go east to Main Street
    3. Go east to Guild of Swordsmen entrance
    4. Go east to Bar of Swordsmen
    5. Go south to Tournament and Practice Yard

    Once you reach the guildmaster, use the send_raw command to practice:
    - send_raw with command: "practice kick"
    - send_raw with command: "practice punch"
    - send_raw with command: "practice dodge"

    These are native MUD commands that can be executed through send_raw.
    """

    print("=" * 70)
    print("PRACTICE SKILL - Using send_raw")
    print("=" * 70)
    print(f"\nTask: {task}\n")

    # Run with send_raw available
    result = boukensha.run(task)

    print("\n" + "=" * 70)
    print("Result:")
    print("=" * 70)
    print(result)


if __name__ == "__main__":
    main()
