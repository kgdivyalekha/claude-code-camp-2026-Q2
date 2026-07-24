#!/usr/bin/env python3
"""Test script to debug the loader resolution."""

import os
import sys

# Add the step's src directory to Python path
step_root = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(step_root, "src")
sys.path.insert(0, src_path)

from boukensha.boukensha_loader import resolve

print("Testing resolve():")
print(f"  BOUKENSHA_PATH={os.environ.get('BOUKENSHA_PATH', '(not set)')}")
print(f"  ~/.boukensharc exists: {os.path.exists(os.path.expanduser('~/.boukensharc'))}")

try:
    lib_path = resolve()
    print(f"  Resolved to: {lib_path}")
    print(f"  File exists: {os.path.exists(lib_path)}")
except SystemExit as e:
    print(f"  ERROR: SystemExit {e.code}")
except Exception as e:
    print(f"  ERROR: {e}")
