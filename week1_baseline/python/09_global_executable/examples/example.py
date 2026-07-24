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

# The base directory tools will operate relative to — the step 07 folder makes
# a good playground since it already has source files to read.
base_dir = Path(__file__).resolve().parent.parent.parent.parent/ "07_the_run_dsl"


def register_tools(dsl):
    """Register tools for the REPL."""
    dsl.tool(
        "read_file",
        description="Read the contents of a file from disk",
        parameters={
            "path": {
                "type": "string",
                "description": "File path (relative to the working directory)",
            }
        },
        fn=lambda path: (base_dir / path).read_text(),
    )

    dsl.tool(
        "list_directory",
        description="List the files in a directory",
        parameters={
            "path": {
                "type": "string",
                "description": "Directory path (relative to the working directory, or '.' for root)",
            }
        },
        fn=lambda path: ", ".join(
            sorted([f for f in os.listdir(str(base_dir / path)) if not f.startswith(".")])
        ),
    )


boukensha.repl(tools_fn=register_tools)
