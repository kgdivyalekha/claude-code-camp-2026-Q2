import os
import sys
from pathlib import Path
import importlib.util

# Add local src directory to path so we can import the local boukensha package
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Import local structs first
from boukensha import Context, Tool, Message

# Now explicitly import Config and Player from the installed boukensha
# Remove our local boukensha from sys.modules to avoid conflicts
if 'boukensha' in sys.modules:
    del sys.modules['boukensha']
if 'boukensha.config' in sys.modules:
    del sys.modules['boukensha.config']
if 'boukensha.tasks' in sys.modules:
    del sys.modules['boukensha.tasks']
if 'boukensha.tasks.player' in sys.modules:
    del sys.modules['boukensha.tasks.player']

# Remove local src from path
sys.path.pop(0)

# Now import from the installed boukensha
from boukensha import Config, Player

os.environ.setdefault(
    "BOUKENSHA_DIR",
    str(Path(__file__).resolve().parent.parent.parent / ".boukensha")
)

config = Config()
player_settings = config.tasks("player") or {}
system_prompt = Player.system_prompt(
    player_settings,
    user_prompts_dir=config.user_prompts_dir
)

ctx = Context(
    task=Player,
    system=system_prompt
)

ctx.register_tool(
    Tool(
        "move",
        "Move the player in a direction (north, south, east, west, up, down)",
        {"direction": {"type": "string", "description": "The direction to move"}},
        lambda direction: f"You move {direction} into a torch-lit corridor."
    )
)

ctx.add_message("user", "Explore north and tell me what you find.")
ctx.add_message("assistant", "Sure, let me head north and take a look.")

print("=== Boukensha Step 1: Struct Skeleton ===")
print()
print(f"Config:   {config}")
print(f"Context:  {ctx}")
print(f"Tool:     {ctx.tools['move']}")
print("Messages:")
for m in ctx.messages:
    print(f"  {m}")
