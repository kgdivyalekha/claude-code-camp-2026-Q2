# Step 11 — the agent owns no tools.
#
# There is no `configure=` callback and no tool registration here, because
# boukensha has nothing of its own to register. Every tool this agent can
# call arrives from an MCP server listed in settings.yaml's `mcp_servers:`
# block — the MUD daemon, a filesystem server, anything that speaks MCP.
# Swapping what the agent can do is a config edit, not a code change.
#
# This is the one-shot (boukensha.run) demo. The interactive TUI is launched
# separately via the `boukensha` console script
# (week1_baseline/bin/python/11_tui) and isn't exercised by this file.
#
#   python3 examples/example.py
#   BOUKENSHA_DIR=/path/to/.boukensha python3 examples/example.py
#
# Point BOUKENSHA_DIR at a config that has an `mcp_servers: mud:` entry (the
# repo root's .boukensha does), and launch from the repo root so that entry's
# relative command path resolves.

import os
from pathlib import Path

os.environ.setdefault(
    "BOUKENSHA_DIR",
    str(Path(__file__).resolve().parent.parent.parent.parent.parent / ".boukensha"),
)

import boukensha

cfg = boukensha.config()
print(f"Config:  {cfg}")
print(f"Servers: {', '.join(cfg.mcp_servers.keys())}")
print(f"API key set? {os.environ.get('ANTHROPIC_API_KEY') is not None}")
print()

boukensha.run(
    task=(
        "Look at your surroundings, check your score, "
        "then look at the available exits and tell me what you see."
    )
    # system/model/api_key come from config automatically.
    # Tools come from mcp_servers — there is nothing to wire up here.
)
