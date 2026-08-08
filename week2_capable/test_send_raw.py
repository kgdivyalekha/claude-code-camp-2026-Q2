#!/usr/bin/env python3
"""
Test script to verify send_raw is available and can practice kick.
Run this to test if the practice command works.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from boukensha import run

# Test 1: Navigate to guildmaster and practice
result = run("""
Navigate to the guildmaster at the Tournament and Practice Yard.
Path: south to Market Square, east to Main Street, east to Guild entrance,
       east to Bar, south to Tournament Yard.

Once at the guildmaster, use send_raw to practice kick:
- send_raw command: practice kick

Report what tools you have available and whether send_raw works.
""")

print("\n" + "=" * 70)
print("TEST RESULT:")
print("=" * 70)
print(result)
