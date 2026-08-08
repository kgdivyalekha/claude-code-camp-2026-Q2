#!/usr/bin/env python3
"""
Example: Practice skill - now built-in and always available!

Previously required: add_practice_tool configure callback
Now: practice is a standard tool, just like look, examine, drink

Usage:
    python3 examples/practice_skill_builtin.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import boukensha


def main():
    """Run agent with built-in practice tool (no special setup needed)."""

    # Simple task - the practice tool is NOW ALWAYS AVAILABLE
    task = """
    Navigate to the Tournament and Practice Yard where the guildmaster is located.

    Path from current location:
    1. Go south to Market Square
    2. Go east to Main Street
    3. Go east to Guild of Swordsmen entrance
    4. Go east to Bar of Swordsmen
    5. Go south to Tournament and Practice Yard

    Once you're there, practice the kick skill using: practice kick
    The practice command is now a built-in tool, just like look and examine!
    """

    print("=" * 70)
    print("PRACTICE SKILL - Built-in Tool Example")
    print("=" * 70)
    print(f"\nTask: {task}\n")

    # NO CONFIGURE NEEDED! practice is now built-in
    result = boukensha.run(task)

    print("\n" + "=" * 70)
    print("Result:")
    print("=" * 70)
    print(result)


if __name__ == "__main__":
    main()
