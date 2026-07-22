# Python Port: Boukensha Struct Skeleton (01_struct_skeleton)

**Status**: Planning — This document defines the port plan for `week1_baseline/ruby/01_struct_skeleton/` to Python.

Expand the 00_config port with lightweight data structures for passing tool, message, and context
around the agent pipeline. Uses Python dataclasses (or NamedTuples) as equivalents to Ruby Structs.
Full feature parity with the Ruby version, including repr strings and all method signatures.

## Decisions

These decisions build on 00_config and establish patterns for the struct port:

- **Struct equivalents**: Ruby's `Struct.new(...)` becomes Python `@dataclass` with `repr=False`
  and a custom `__repr__()` method matching Ruby's `to_s` output. Alternative: `NamedTuple` for
  immutability, but dataclasses provide flexibility for later extensions.

- **Parameters field (dict vs. nested)**: Ruby's `parameters` is a nested Hash; Python dict is
  identical. No translation needed — the example shows
  `{ direction: { type: "string", description: "The direction to move" } }` which maps 1:1 to
  Python dict.

- **Block/callable field**: Ruby's `block` (Proc) becomes a Python callable (lambda or function).
  Stored as-is in the dataclass field; no special wrapping needed.

- **Tool/Message immutability**: Ruby Structs are mutable by default; Python dataclasses are mutable.
  For now, keep mutable to allow optional future extensions. If true immutability is needed later,
  replace `@dataclass` with `@dataclass(frozen=True)` or switch to `NamedTuple`.

- **Context.tool_count, turn_count shortcuts**: Ruby uses method definition shortcuts
  (`def tool_count = @tools.size`). Python uses `@property` decorators for read-only access.
  Keep as plain methods for consistency with Ruby's callable style.

- **Config as shared dependency**: Context and Task classes depend on Config methods
  (via Player example). Config port (00_config) must complete first, or Context/Task tests
  mock the Config interface.

## Target Python Structure (as planned)

```
week1_baseline/python/01_struct_skeleton/
├── src/
│   └── boukensha/
│       ├── __init__.py              # Package exports (Config, Context, Tool, Message, Tasks)
│       ├── config.py                # Re-export from 00_config
│       ├── tool.py                  # Tool dataclass
│       ├── message.py               # Message dataclass
│       ├── context.py               # Context class
│       └── tasks/
│           ├── __init__.py
│           ├── base.py              # Base task class (ABC)
│           └── player.py            # Player task
├── examples/
│   └── example.py                   # Usage example / smoke test
├── pyproject.toml                   # Package config (installed with pip -e)
└── README.md                         # Usage documentation
```

### Reuse from 00_config
- `Config` class (already ported in `week1_baseline/python/00_config/src/boukensha/config.py`)
- `Tasks.Base` and `Tasks.Player` (already ported; will be re-exported)
- `prompts/system.md` (shared location, no duplication)

## Quick Setup

### 1. Ensure 00_config is ported and working
```bash
source venv/bin/activate
pip install -e week1_baseline/python/00_config
```

### 2. Install 01_struct_skeleton (includes 00_config as a dependency)
```bash
pip install -e week1_baseline/python/01_struct_skeleton
```

### 3. Run it
```bash
./week1_baseline/bin/python/01_struct_skeleton
```

---

## Porting Plan: File by File

### 1. Tool (`lib/boukensha/tool.rb` → `src/boukensha/tool.py`)

**Ruby**:
```ruby
module Boukensha
  Tool = Struct.new(:name, :description, :parameters, :block) do
    def to_s
      "#<Tool name=#{name} description=#{description.to_s[0..40]} params=#{parameters.keys}>"
    end
  end
end
```

**Python**:
```python
from dataclasses import dataclass
from typing import Any, Callable, Dict

@dataclass
class Tool:
    name: str
    description: str
    parameters: Dict[str, Any]
    block: Callable

    def __repr__(self) -> str:
        desc_preview = str(self.description)[:41]
        params = list(self.parameters.keys())
        return f"<Tool name={self.name} description={desc_preview} params={params}>"
    
    def __str__(self) -> str:
        return self.__repr__()
```

**Key translation**:
- Struct → dataclass
- Ruby `to_s` → Python `__repr__()` (also assign to `__str__()` for consistency)
- String slice `[0..40]` → `[:41]` (Python slicing is exclusive end)
- `.keys` → `list(...keys)`

**Testing**:
- Create a Tool with sample parameters; verify `repr()` matches expected format
- Verify `block` callable can be invoked: `tool.block("north")`

---

### 2. Message (`lib/boukensha/message.rb` → `src/boukensha/message.py`)

**Ruby**:
```ruby
module Boukensha
  Message = Struct.new(:role, :content, :tool_use_id) do
    def to_s
      id_tag = tool_use_id ? " [#{tool_use_id}]" : ""
      "#<Message role=#{role}#{id_tag} content=#{content.to_s[0..60]}...>"
    end
  end
end
```

**Python**:
```python
from dataclasses import dataclass
from typing import Any, Optional

@dataclass
class Message:
    role: str
    content: str
    tool_use_id: Optional[str] = None

    def __repr__(self) -> str:
        id_tag = f" [{self.tool_use_id}]" if self.tool_use_id else ""
        content_preview = str(self.content)[:61]
        return f"<Message role={self.role}{id_tag} content={content_preview}...>"
    
    def __str__(self) -> str:
        return self.__repr__()
```

**Key translation**:
- Optional third field → `Optional[str] = None`
- Ternary operator: `tool_use_id ? X : Y` → `X if tool_use_id else Y`
- String slice `[0..60]` → `[:61]`

**Testing**:
- Create Messages with and without `tool_use_id`; verify `repr()` format
- Test with various `role` values (user, assistant, tool_result)

---

### 3. Context (`lib/boukensha/context.rb` → `src/boukensha/context.py`)

**Ruby**:
```ruby
class Context
  attr_reader :task, :system, :messages, :tools

  def initialize(task:, system: nil)
    @task         = task
    @system       = system
    @messages     = []
    @tools        = {}
  end

  def register_tool(tool)
    @tools[tool.name] = tool
  end

  def add_message(role, content, tool_use_id: nil)
    @messages << Message.new(role, content, tool_use_id)
  end

  def tool_count = @tools.size
  def turn_count = @messages.size

  def to_s
    "#<Context task=#{task&.task_name} turns=#{turn_count} tools=#{tool_count}>"
  end
end
```

**Python**:
```python
from typing import Any, Dict, Optional, Type
from .tool import Tool
from .message import Message

class Context:
    def __init__(self, task: Optional[Type] = None, system: Optional[str] = None):
        self.task: Optional[Type] = task
        self.system: Optional[str] = system
        self.messages: list[Message] = []
        self.tools: Dict[str, Tool] = {}

    def register_tool(self, tool: Tool) -> None:
        self.tools[tool.name] = tool

    def add_message(self, role: str, content: str, tool_use_id: Optional[str] = None) -> None:
        self.messages.append(Message(role, content, tool_use_id))

    def tool_count(self) -> int:
        return len(self.tools)

    def turn_count(self) -> int:
        return len(self.messages)

    def __repr__(self) -> str:
        task_name = self.task.task_name if self.task else None
        return f"<Context task={task_name} turns={self.turn_count()} tools={self.tool_count()}>"

    def __str__(self) -> str:
        return self.__repr__()
```

**Key translation**:
- `attr_reader` → explicit attributes in `__init__`
- Ruby method shorthand `def tool_count = ...` → Python method `def tool_count(self) -> int:`
- `task&.task_name` (safe navigation) → `self.task.task_name if self.task else None`
- `@tools[tool.name] = tool` → `self.tools[tool.name] = tool`

**Testing**:
- Initialize Context with and without task/system
- Register multiple tools; verify `tool_count()` and `tools` dict
- Add messages with and without `tool_use_id`; verify `turn_count()` and `messages` list
- Verify `repr()` format matches Ruby output

---

### 4. Task Base (`lib/boukensha/tasks/base.rb` → `src/boukensha/tasks/base.py`)

**Already ported in 00_config; no changes needed for 01_struct_skeleton.**
Re-export it in `__init__.py`.

---

### 5. Task Player (`lib/boukensha/tasks/player.rb` → `src/boukensha/tasks/player.py`)

**Already ported in 00_config; no changes needed for 01_struct_skeleton.**
Re-export it in `__init__.py`.

---

### 6. Package Exports (`lib/boukensha.rb` → `src/boukensha/__init__.py`)

**Ruby**:
```ruby
require_relative "boukensha/config"
require_relative "boukensha/tasks/player"
require_relative "boukensha/tool"
require_relative "boukensha/message"
require_relative "boukensha/context"
```

**Python**:
```python
# src/boukensha/__init__.py
from .config import Config
from .tool import Tool
from .message import Message
from .context import Context
from .tasks.base import Base as TaskBase
from .tasks.player import Player

__all__ = [
    "Config",
    "Tool",
    "Message",
    "Context",
    "TaskBase",
    "Player",
]
```

**Key translation**:
- Requires → imports
- Export via `__all__` for clarity

---

### 7. Example (`examples/example.rb` → `examples/example.py`)

**Ruby**:
```ruby
require_relative "../lib/boukensha"
ENV["BOUKENSHA_DIR"] ||= File.expand_path("/../../../.boukensha", __dir__)

config = Boukensha::Config.new
player_settings = config.tasks(:player)
system_prompt = Boukensha::Tasks::Player.system_prompt(
  player_settings,
  user_prompts_dir: config.user_prompts_dir
)

ctx = Boukensha::Context.new(
  task: Boukensha::Tasks::Player,
  system: system_prompt
)

ctx.register_tool(
  Boukensha::Tool.new(
    "move",
    "Move the player in a direction (north, south, east, west, up, down)",
    { direction: { type: "string", description: "The direction to move" } },
    ->(direction) { "You move #{direction} into a torch-lit corridor." }
  )
)

ctx.add_message(:user, "Explore north and tell me what you find.")
ctx.add_message(:assistant, "Sure, let me head north and take a look.")

puts "=== Boukensha Step 1: Struct Skeleton ==="
puts
puts "Config:   #{config}"
puts "Context:  #{ctx}"
puts "Tool:     #{ctx.tools['move']}"
puts "Messages:"
ctx.messages.each { |m| puts "  #{m}" }
```

**Python**:
```python
import os
from pathlib import Path
from boukensha import Config, Context, Tool, Player

os.environ.setdefault(
    "BOUKENSHA_DIR",
    str(Path(__file__).resolve().parent.parent.parent / ".boukensha")
)

config = Config()
player_settings = config.tasks("player")
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
```

**Key translation**:
- `require_relative` → `from` imports
- `ENV["KEY"] ||= ...` → `os.environ.setdefault(...)`
- `File.expand_path` + `__dir__` → `Path(__file__).resolve().parent...`
- Proc `->(x) { ... }` → lambda `lambda x: ...`
- String interpolation `#{...}` → f-strings `f"..."`
- Symbol arguments `:player` → string `"player"`
- `puts` → `print`
- `.each { |m| ... }` → `for m in ...: ...`

---

## Dependency Chain

```
01_struct_skeleton (Tool, Message, Context)
    ↓ depends on
00_config (Config, Tasks.Base, Tasks.Player)
```

**Action**: Verify 00_config is installed before porting 01_struct_skeleton:
```bash
pip list | grep boukensha
```

---

## Testing / Verification Strategy

### Unit-level verification (as you build):
1. **Tool**: Create a Tool; invoke its `__repr__()`; test `block` callable
2. **Message**: Create Messages with/without `tool_use_id`; verify `__repr__()`
3. **Context**: Register tools, add messages; verify `tool_count()`, `turn_count()`, `__repr__()`
4. **Example smoke test**: Run `python examples/example.py`; verify output matches Ruby's shape

### Full integration test:
```bash
source venv/bin/activate
pip install -e week1_baseline/python/01_struct_skeleton
./week1_baseline/bin/python/01_struct_skeleton
```

### Expected output:
```
=== Boukensha Step 1: Struct Skeleton ===

Config:   <Boukensha::Config dir=~/.boukensha tasks=player>
Context:  <Context task=player turns=2 tools=1>
Tool:     <Tool name=move description=Move the player in a direction (nort... params=['direction']>
Messages:
  <Message role=user content=Explore north and tell me what you find....>
  <Message role=assistant content=Sure, let me head north and take a look....>
```

(Exact formatting may vary slightly; core fields must match.)

---

## Common Pitfalls

### 1. Import order and circular dependencies
**Problem**: `context.py` imports `Tool` and `Message`, which might import `Context`.
**Fix**: Define Tool, Message, and Context in separate files with one-way imports.

### 2. String slicing off by one
**Ruby**: `str[0..40]` includes index 40 (41 chars total).
**Python**: `str[:41]` includes indices 0–40 (41 chars total).
Use `[:41]` to match Ruby's `[0..40]`.

### 3. Optional/None handling
**Wrong**: Trying to call `task.task_name` when `task` might be `None`.
**Right**: Use conditional check or `getattr(..., None)`:
```python
task_name = self.task.task_name if self.task else None
```

### 4. Dataclass repr collision
**Problem**: `@dataclass` auto-generates `__repr__()`, overriding your custom one.
**Fix**: Use `@dataclass(repr=False)` to disable auto-generation, then define your own.

---

## Verifying Success

```bash
source venv/bin/activate
python -c "from boukensha import Tool, Message, Context; print('Imports work')"
./week1_baseline/bin/python/01_struct_skeleton
diff <(./week1_baseline/bin/ruby/01_struct_skeleton 2>&1) \
     <(./week1_baseline/bin/python/01_struct_skeleton 2>&1)
```

The outputs should be structurally identical (exact formatting may vary).

---

## Additional Resources

- **Ruby source**: `week1_baseline/ruby/01_struct_skeleton/`
- **Python 00_config reference**: `week1_baseline/python/00_config/`
- **00_config plan**: `docs/plans/python_port/00_config.md`
- **Python dataclasses guide**: https://docs.python.org/3/library/dataclasses.html
- **NamedTuple alternative**: https://docs.python.org/3/library/typing.html#typing.NamedTuple

---

## What NOT to Do

- Don't hard-code paths (use `Path` and the config system)
- Don't skip repr/str methods — they are part of the contract
- Don't use `yaml.load()` without `safe_load()`
- Don't ignore type hints — annotate everything
- Don't redefine Config/Tasks — import and re-export from 00_config
- Don't use mutable default arguments (e.g., `def __init__(self, tools={}):`) — Python gotcha
- Don't forget `@dataclass(repr=False)` when defining custom `__repr__()`
