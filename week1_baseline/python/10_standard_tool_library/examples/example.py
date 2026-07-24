import os
from pathlib import Path

# Set BOUKENSHA_DIR to the project's .boukensha directory BEFORE importing boukensha
# This ensures config loads from the correct location
project_root = Path(__file__).resolve().parent.parent.parent.parent.parent
os.environ["BOUKENSHA_DIR"] = str(project_root / ".boukensha")

import boukensha

# Config is loaded automatically inside boukensha.repl() — system prompt, model,
# and API key all come from ~/.boukensha (or BOUKENSHA_DIR) by default.

cfg = boukensha.config()
print(f"Config: {cfg}")
print(f"BOUKENSHA_DIR: {cfg.dir}")

# Debug: show what's loaded
player_settings = cfg.tasks("player")
print(f"Player settings: {player_settings}")
if player_settings:
    print(f"  Provider: {player_settings.get('provider')}")
    print(f"  Model: {player_settings.get('model')}")
print()

# The working directory for FileSystem and Shell tools
# Using the week0_explore directory as a safe sandbox
working_dir = project_root / "week0_explore"

print(f"Working directory for tools: {working_dir}")
print()

# Start the REPL with FileSystem and Shell tools registered
# FileSystem tools: pwd, list_directory, read_file, write_file, delete_file, search_files
# Shell tool: run_command (with optional allow-list and timeout)
boukensha.repl(
    working_dir=str(working_dir),
    allowed_commands=None,  # Allow all commands (None = no restrictions)
    shell_timeout=30        # 30 second timeout for shell commands
)
