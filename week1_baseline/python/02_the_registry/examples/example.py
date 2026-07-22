import os
import sys
from pathlib import Path

# Add local src directory to path so we can import the local boukensha package
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Import local structs first
from boukensha import Context, Tool, Message, Registry, UnknownToolError

# Now remove local src from path and clear boukensha from sys.modules
sys.path.pop(0)
sys.modules.pop('boukensha', None)
sys.modules.pop('boukensha.config', None)
sys.modules.pop('boukensha.tasks', None)
sys.modules.pop('boukensha.tasks.player', None)

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

ctx = Context(task=Player, system=system_prompt)
registry = Registry(ctx)

# Register tools through the registry
registry.tool(
    "move",
    description="Move the player in a direction (north, south, east, west, up, down)",
    parameters={"direction": {"type": "string"}},
    block=lambda direction: f"You move {direction} into a torch-lit corridor."
)

registry.tool(
    "shout",
    description="Shout a message so everyone in the zone can hear it",
    parameters={"message": {"type": "string"}},
    block=lambda message: message.upper()
)

print("=== BOUKENSHA Step 2: Tool Registry ===")
print()
print(f"Config:  {config}")
print(f"Context: {ctx}")
print("Tools:")
for tool in ctx.tools.values():
    print(f"  {tool}")
print()

print("Dispatching 'shout' with message='dragon spotted'...")
result = registry.dispatch("shout", {"message": "dragon spotted"})
print(f"Result: {result}")
print()

print("Dispatching 'move' with direction='north'...")
result = registry.dispatch("move", {"direction": "north"})
print(f"Result: {result}")
print()

try:
    registry.dispatch("flee")
except UnknownToolError as e:
    print(f"UnknownToolError caught: {e}")
