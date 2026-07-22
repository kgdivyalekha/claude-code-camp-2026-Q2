# Python Port: Boukensha Tool Registry (02_the_registry)

**Status**: Planning — This document defines the port plan for `week1_baseline/ruby/02_the_registry/` to Python.

Expand the struct skeleton (01_struct_skeleton) with a Tool Registry — a dispatcher that manages tool
registration and execution. The Registry receives string-keyed arguments from the agent API and converts
them to keyword arguments before invoking tool blocks. Full feature parity with Ruby version, including
the `UnknownToolError` exception and argument transformation logic.

## Decisions

These decisions build on 00_config and 01_struct_skeleton, establishing patterns for registries:

- **Registry ownership of tools**: The Registry wraps a Context and provides a fluent interface for
  tool registration via `tool(name, description, parameters, block)`. Tools are still stored in Context's
  `tools` dict, but registration goes through Registry for validation and consistency.

- **Error handling**: Ruby's custom `UnknownToolError` becomes Python's `UnknownToolError` (custom exception).
  Raised in `dispatch()` when a tool name is not found. No fallback or default behavior.

- **Argument transformation**: JSON APIs return string-keyed dicts (e.g., `{"message": "..."}`) but
  Python callables expect keyword arguments. The Registry's `dispatch()` method transforms keys to
  match the callable signature. This is explicit and visible for learning.

- **Block/Callable convention**: Ruby blocks passed to `tool()` become Python callables (lambdas or
  functions). The `dispatch()` method calls them as `block(**kwargs)` where kwargs are the transformed
  arguments.

- **No validation on registration**: Unlike some frameworks, we don't validate block signatures at
  registration time. If a tool is registered with parameters `{message: ...}` but the block only accepts
  `direction`, it will fail at dispatch time. This teaches the importance of contracts.

- **Context dependency**: Registry depends on an existing Context instance. It's a stateful wrapper
  around Context, not a standalone data structure. They form a cohesive pair.

## Target Python Structure (as planned)

```
week1_baseline/python/02_the_registry/
├── src/
│   └── boukensha/
│       ├── __init__.py              # Package exports (Config, Context, Tool, Message, Registry, UnknownToolError)
│       ├── config.py                # Re-export from 00_config (or skip)
│       ├── tool.py                  # Tool dataclass (from 01_struct_skeleton)
│       ├── message.py               # Message dataclass (from 01_struct_skeleton)
│       ├── context.py               # Context class (from 01_struct_skeleton)
│       ├── errors.py                # UnknownToolError exception
│       ├── registry.py              # Registry class (NEW)
│       └── tasks/
│           ├── __init__.py
│           ├── base.py              # Base task class (from 00_config)
│           └── player.py            # Player task (from 00_config)
├── examples/
│   └── example.py                   # Usage example / smoke test
├── pyproject.toml                   # Package config
└── README.md                         # Usage documentation
```

### Reuse from Prior Steps
- **00_config**: Config, Tasks.Base, Tasks.Player
- **01_struct_skeleton**: Tool, Message, Context

### New in This Step
- **errors.py**: UnknownToolError exception
- **registry.py**: Registry class with tool registration and dispatch

## Quick Setup

### 1. Ensure 00_config and 01_struct_skeleton are ported
```bash
source venv/bin/activate
pip install -e week1_baseline/python/00_config
pip install -e week1_baseline/python/01_struct_skeleton
```

### 2. Install 02_the_registry
```bash
pip install -e week1_baseline/python/02_the_registry
```

### 3. Run it
```bash
./week1_baseline/bin/python/02_the_registry
```

---

## Porting Plan: File by File

### 1. UnknownToolError (`lib/boukensha/errors.rb` → `src/boukensha/errors.py`)

**Ruby**:
```ruby
module Boukensha
  class UnknownToolError < StandardError; end
end
```

**Python**:
```python
class UnknownToolError(Exception):
    """Raised when dispatch() is called with an unknown tool name."""
    pass
```

**Key translation**:
- `StandardError` → `Exception` (Python base exception)
- No body needed for simple exception subclasses

**Testing**:
- Catch UnknownToolError when dispatching unknown tool name
- Verify error message format: "No tool registered as 'toolname'"

---

### 2. Registry (`lib/boukensha/registry.rb` → `src/boukensha/registry.py`)

**Ruby**:
```ruby
module Boukensha
  class Registry
    def initialize(context)
      @context = context
    end

    def tool(name, description:, parameters: {}, &block)
      tool = Tool.new(name.to_s, description, parameters, block)
      @context.register_tool(tool)
      tool
    end

    def dispatch(name, args = {})
      tool = @context.tools[name.to_s]
      raise UnknownToolError, "No tool registered as '#{name}'" unless tool
      tool.block.call(**args.transform_keys(&:to_sym))
    end
  end
end
```

**Python**:
```python
from typing import Any, Callable, Dict, Optional
from .tool import Tool
from .errors import UnknownToolError


class Registry:
    def __init__(self, context: Any) -> None:
        self.context = context

    def tool(
        self,
        name: str,
        *,
        description: str,
        parameters: Optional[Dict[str, Any]] = None,
        block: Optional[Callable] = None
    ) -> Tool:
        """
        Register a tool with the context.
        
        Usage:
            registry.tool("move", description="...", parameters={...})(lambda direction: ...)
            # OR pass block directly:
            registry.tool("move", description="...", parameters={...}, block=lambda: ...)
        """
        if parameters is None:
            parameters = {}
        
        if block is None:
            # Return decorator if block not provided
            def decorator(fn: Callable) -> Tool:
                tool = Tool(name, description, parameters, fn)
                self.context.register_tool(tool)
                return tool
            return decorator
        else:
            # Create tool directly if block provided
            tool = Tool(name, description, parameters, block)
            self.context.register_tool(tool)
            return tool

    def dispatch(self, name: str, args: Optional[Dict[str, Any]] = None) -> Any:
        """
        Dispatch a tool by name with the given arguments.
        
        Transforms string-keyed args to keyword args before calling the block.
        Raises UnknownToolError if the tool is not registered.
        """
        if args is None:
            args = {}
        
        tool = self.context.tools.get(name)
        if not tool:
            raise UnknownToolError(f"No tool registered as '{name}'")
        
        # Transform string keys to keyword arguments
        kwargs = {str(k): v for k, v in args.items()}
        return tool.block(**kwargs)
```

**Key translation**:
- `initialize` → `__init__`
- Keyword arguments: Ruby's `description:, parameters: {}` → Python `*, description: str, parameters: Optional[Dict] = None`
- `@context` → `self.context`
- `name.to_s` → `str(name)` (but already a string in most cases)
- `&block` → callable parameter; also support as decorator
- `tool.block.call(**...)` → `tool.block(**...)`
- `transform_keys(&:to_sym)` → dict comprehension with `str(k)` (Python dicts use strings)
- `unless tool` → `if not tool`

**Testing**:
- Register two tools via `registry.tool()`
- Dispatch each tool with correct string-keyed args
- Verify kwargs are passed correctly to the block
- Catch UnknownToolError when dispatching unknown tool
- Verify error message format

---

### 3. Package Exports (`lib/boukensha.rb` → `src/boukensha/__init__.py`)

Update the __init__.py to include the Registry and UnknownToolError:

**Python**:
```python
# Local struct classes
from .tool import Tool  # noqa: F401
from .message import Message  # noqa: F401
from .context import Context  # noqa: F401

# New in this step: Registry and error
from .errors import UnknownToolError  # noqa: F401
from .registry import Registry  # noqa: F401

# Import from the installed boukensha package (00_config)
try:
    import sys
    if 'boukensha' in sys.modules:
        installed_boukensha = sys.modules['boukensha']
        Config = getattr(installed_boukensha, 'Config', None)
        TaskBase = getattr(installed_boukensha, 'Base', None)
        Player = getattr(installed_boukensha, 'Player', None)
        
        if not (Config and Player):
            from boukensha.config import Config  # noqa: F401
            from boukensha.tasks.base import Base as TaskBase  # noqa: F401
            from boukensha.tasks.player import Player  # noqa: F401
except (ImportError, AttributeError):
    raise ImportError(
        "02_the_registry requires 00_config to be installed. "
        "Run: pip install -e ../00_config"
    )

__all__ = [
    "Config",
    "Tool",
    "Message",
    "Context",
    "Registry",
    "UnknownToolError",
    "TaskBase",
    "Player",
]
```

---

### 4. Example (`examples/example.rb` → `examples/example.py`)

**Ruby**:
```ruby
ENV["BOUKENSHA_DIR"] ||= File.expand_path("../../../../.boukensha", __dir__)
require_relative "../lib/boukensha"

config          = Boukensha::Config.new
player_settings = config.tasks(:player)
system_prompt   = Boukensha::Tasks::Player.system_prompt(
  player_settings,
  user_prompts_dir: config.user_prompts_dir
)

ctx      = Boukensha::Context.new(task: Boukensha::Tasks::Player, system: system_prompt)
registry = Boukensha::Registry.new(ctx)

registry.tool("move",
  description: "Move the player in a direction (north, south, east, west, up, down)",
  parameters: { direction: { type: "string" } }
) do |direction:|
  "You move #{direction} into a torch-lit corridor."
end

registry.tool("shout",
  description: "Shout a message so everyone in the zone can hear it",
  parameters: { message: { type: "string" } }
) do |message:|
  message.upcase
end

puts "=== BOUKENSHA Step 2: Tool Registry ==="
puts
puts "Config:  #{config}"
puts "Context: #{ctx}"
puts "Tools:"
ctx.tools.each_value { |t| puts "  #{t}" }
puts

puts "Dispatching 'shout' with message='dragon spotted'..."
result = registry.dispatch("shout", { "message" => "dragon spotted" })
puts "Result: #{result}"
puts

puts "Dispatching 'move' with direction='north'..."
result = registry.dispatch("move", { "direction" => "north" })
puts "Result: #{result}"
puts

begin
  registry.dispatch("flee")
rescue Boukensha::UnknownToolError => e
  puts "UnknownToolError caught: #{e.message}"
end
```

**Python**:
```python
import os
import sys
from pathlib import Path

# Add local src directory to path so we can import the local boukensha package
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Import local structs first
from boukensha import Context, Tool, Message, Registry, UnknownToolError

# Now remove local src from path and import from installed boukensha
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
```

**Key translation**:
- `require_relative` → `sys.path` + `from ... import ...`
- `Boukensha::Config` → imported Config
- Symbol parameters `:player` → string `"player"`
- Block syntax `do |param:| ... end` → lambda `lambda param: ...`
- `puts` → `print`
- `.each_value { ... }` → `for ... in .values(): ...`
- `message.upcase` → `message.upper()`
- `begin...rescue...end` → `try...except...`

---

## Dependency Chain

```
02_the_registry (Registry, UnknownToolError)
    ↓ extends/depends on
01_struct_skeleton (Tool, Message, Context)
    ↓ depends on
00_config (Config, Tasks.Base, Tasks.Player)
```

**Action**: Verify both prior steps are installed before porting 02_the_registry:
```bash
pip list | grep boukensha
```

---

## Testing / Verification Strategy

### Unit-level verification (as you build):
1. **UnknownToolError**: Create the exception; verify it's catchable and has message
2. **Registry.tool()**: Register a tool; verify it's added to context.tools
3. **Registry.dispatch()**: 
   - Dispatch a registered tool with string-keyed args
   - Verify kwargs are transformed correctly
   - Verify result matches block output
4. **Error handling**: Try to dispatch an unknown tool; catch the error
5. **Example smoke test**: Run `python examples/example.py`; verify output matches Ruby's shape

### Full integration test:
```bash
source venv/bin/activate
pip install -e week1_baseline/python/02_the_registry
./week1_baseline/bin/python/02_the_registry
```

### Expected output:
```
=== BOUKENSHA Step 2: Tool Registry ===

Config:  <Boukensha.Config dir=~/.boukensha tasks=player>
Context: <Context task=player turns=0 tools=2>
Tools:
  <Tool name=move description="Move the player in a direction (nort..." params=['direction']>
  <Tool name=shout description="Shout a message so everyone in the z..." params=['message']>

Dispatching 'shout' with message='dragon spotted'...
Result: DRAGON SPOTTED

Dispatching 'move' with direction='north'...
Result: You move north into a torch-lit corridor.

UnknownToolError caught: No tool registered as 'flee'
```

---

## Common Pitfalls

### 1. Argument transformation logic
**Problem**: Passing dict with string keys directly to `lambda` expecting keyword args.
**Fix**: Use `tool.block(**args)` where args is a dict; Python unpacks it correctly.
**Why**: The API returns `{"message": "text"}` but blocks expect `message="text"` (as kwargs).

### 2. Type handling in dispatch
**Problem**: `args.get("message")` returns None, then block fails silently.
**Fix**: Validate required parameters before dispatch, or let the error bubble up.
**Teaching point**: Missing error boundaries is how bugs escape to production.

### 3. Block signature mismatch
**Problem**: Block expects `direction=`, but dispatch is called with `{"message": ...}`.
**Fix**: No runtime validation; TypeError from Python when unpacking wrong kwargs.
**Teaching point**: Contracts matter; API and block signatures must align.

### 4. Exception inheritance
**Problem**: Catching `Exception` instead of `UnknownToolError` silently swallows specific errors.
**Fix**: Catch the specific exception type.
**Teaching point**: Explicit error handling prevents bugs.

### 5. Context mutation through Registry
**Problem**: Registry modifies Context.tools; unexpected side effects if not documented.
**Fix**: Registry clearly owns the context's tool registration; treat them as a pair.
**Teaching point**: Clear ownership prevents confusion in larger systems.

---

## Verifying Success

```bash
source venv/bin/activate
python -c "from boukensha import Registry, UnknownToolError; print('Imports work')"
./week1_baseline/bin/python/02_the_registry
```

The output should match the Ruby version's structure (exact formatting may vary).

Compare with Ruby:
```bash
diff <(cd week1_baseline/ruby/02_the_registry && ruby examples/example.rb 2>&1) \
     <(cd week1_baseline/python/02_the_registry && python3 examples/example.py 2>&1)
```

---

## Additional Resources

- **Ruby source**: `week1_baseline/ruby/02_the_registry/`
- **Python 00_config reference**: `week1_baseline/python/00_config/`
- **Python 01_struct_skeleton reference**: `week1_baseline/python/01_struct_skeleton/`
- **00_config plan**: `docs/plans/python_port/00_config.md`
- **01_struct_skeleton plan**: `docs/plans/python_port/01_struct_skeleton.md`
- **Python exception docs**: https://docs.python.org/3/tutorial/errors.html

---

## What NOT to Do

- Don't use `dict.get()` and ignore missing keys — let errors surface
- Don't validate block signatures at registration time — that's a later concern
- Don't swallow UnknownToolError — it's a real error, not a fallback case
- Don't create a global registry — pass Context to Registry; keep scope clear
- Don't hardcode tool behavior — tools should be fully driven by blocks
- Don't skip the argument transformation — it's a critical learning point
- Don't redefine Config/Context/Tool — import and re-use from prior steps

---

## Files to Create/Modify

1. ✓ Create `src/boukensha/errors.py` — UnknownToolError exception
2. ✓ Create `src/boukensha/registry.py` — Registry class
3. ✓ Copy `src/boukensha/tool.py` from 01_struct_skeleton
4. ✓ Copy `src/boukensha/message.py` from 01_struct_skeleton
5. ✓ Copy `src/boukensha/context.py` from 01_struct_skeleton
6. ✓ Create `src/boukensha/__init__.py` — exports
7. ✓ Create `src/boukensha/tasks/__init__.py` — re-exports from 00_config
8. ✓ Create `examples/example.py` — smoke test
9. ✓ Create `pyproject.toml` — package config
10. ✓ Create `README.md` — usage docs
11. ✓ Create `week1_baseline/bin/python/02_the_registry` — executable launcher
