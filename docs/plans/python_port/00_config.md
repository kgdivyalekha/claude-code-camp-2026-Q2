# Python Port: Boukensha Configuration (00_config)

**Status**: Implemented — `week1_baseline/python/00_config/` is up and passing
the smoke test, matching `week1_baseline/ruby/00_config/` output.

Port the Ruby Boukensha configuration library (`week1_baseline/ruby/00_config/`) to Python
with full feature parity. This document combines the quick-start checklist with the
Ruby → Python pattern reference so both live in one place.

## Decisions

These were open questions during planning; resolved and applied to the implementation:

- **Launcher layout**: `week1_baseline/bin/` has `ruby/` and `python/` subfolders.
  `bin/ruby/00_config` was fixed to `cd ../../ruby/00_config` (it moved one level
  deeper than the old `bin/00_config`). `bin/python/00_config` is new, mirrors the
  same shape, and runs `python3 examples/example.py`.
- **Virtualenv**: one shared venv at the **project root** (`<repo-root>/venv`,
  already existed for `llama_gateway.py`), not a per-step `.venv`. Every Python
  step installs into it via `pip install -e path/to/step`. Both bin launchers
  assume their runtime is already set up (Ruby assumes `bundle install` ran;
  Python assumes the root venv is activated and the package installed) — neither
  script creates/activates anything itself.
- **`prompt_override?` naming**: Ruby's `?`-suffix has no Python equivalent.
  Settled on `is_prompt_override` (explicit boolean-predicate naming) — apply
  this convention consistently in later ports.
- **Package name**: `boukensha`, same as the Ruby module.
- **Testing**: no pytest suite. Like the Ruby side, `examples/example.py` is the
  only smoke test.

## Target Python Structure (as built)

```
week1_baseline/python/00_config/
├── src/
│   └── boukensha/
│       ├── __init__.py           # Package exports (Config, Player)
│       ├── config.py             # Config class (main)
│       └── tasks/
│           ├── __init__.py
│           ├── base.py           # Base task class (ABC)
│           └── player.py         # Player task
├── examples/
│   └── example.py                # Usage example / smoke test
├── prompts/
│   └── system.md                 # Default system prompt
├── pyproject.toml                # Package config (installed with pip -e)
└── README.md                     # Usage documentation
```

No `exceptions.py`, no `tests/`, no `pydantic` dependency — dropped from the
original draft plan below to stay a faithful, minimal 1:1 port (Ruby uses
plain `ArgumentError`/`NotImplementedError`, so Python uses plain
`ValueError`/`NotImplementedError`; no test suite means no test-only tooling).

## Quick Setup

### 1. Shared root venv (once per repo, not per step)
```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -e week1_baseline/python/00_config
```

### 2. Run it
```bash
./week1_baseline/bin/python/00_config
```

---

## Ruby to Python Patterns

### 1. Module/Class Structure

**Ruby**:
```ruby
module Boukensha
  class Config
    # ...
  end
end
```

**Python**:
```python
# boukensha/__init__.py
from .config import Config

__all__ = ["Config"]

# boukensha/config.py
class Config:
    # ...
```

### 2. Require/Import Dependencies

**Ruby**:
```ruby
require "yaml"
require "dotenv"
require_relative "boukensha/config"
```

**Python**:
```python
import yaml
from dotenv import load_dotenv
from .config import Config
```

### 3. Attributes and Properties

**Ruby**:
```ruby
class Config
  attr_reader :dir, :settings
end
```

**Python**:
```python
class Config:
    def __init__(self):
        self.dir: Path = ...
        self.settings: Dict[str, Any] = ...
```

### 4. Method Naming Conventions

| Ruby | Python | Example |
|------|--------|---------|
| snake_case methods | snake_case methods | `load_settings()` |
| `predicate?` | `is_` prefix (decided above) | `is_prompt_override()` |
| Private methods | `_private_method()` | `def _resolve_dir()` |

### 5. Nil/None Handling

**Ruby**:
```ruby
value || "default"
value&.upcase  # optional chaining
```

**Python**:
```python
value or "default"
value.upper() if value else None  # conditional
```

### 6. Class Methods and Abstract Methods

**Ruby**:
```ruby
class Base
  def self.task_name
    raise NotImplementedError, "#{self} must define .task_name"
  end
end

class Player
  def self.task_name
    "player"
  end

  def self.provider(settings)
    settings[:provider] || raise ArgumentError
  end
end
```

**Python**:
```python
from abc import ABC, abstractmethod

class Base(ABC):
    @classmethod
    @abstractmethod
    def task_name(cls) -> str:
        """Subclasses must define task_name."""
        raise NotImplementedError(f"{cls.__name__} must define task_name()")

class Player(Base):
    @classmethod
    def task_name(cls) -> str:
        return "player"

    @classmethod
    def provider(cls, settings: Dict[str, Any]) -> str:
        value = settings.get("provider")
        if not value:
            raise ValueError("provider is required")
        return value
```

---

## File and Path Handling

| Concept | Ruby | Python |
|---------|------|--------|
| Home dir | `Dir.home` | `Path.home()` |
| Join paths | `File.join(a, b)` | `Path(a) / b` |
| Check existence | `File.exist?(path)` | `Path(path).exists()` |
| Read file | `File.read(file).strip` | `Path(file).read_text().strip()` |

```python
from pathlib import Path

Path.home() / ".boukensha"
Path(path).exists()
Path(file).read_text().strip()
Path(dir) / "subdir" / "file.txt"
```

---

## Dictionary/Hash Access

### Symbol vs String Keys

**Ruby** (hashes can use both symbols and strings as keys):
```ruby
hash = { "key" => "value1", :key => "value2" }
hash[:key]  # "value2"
hash["key"] # "value1"
```

**Python** (dicts use strings only; `yaml.safe_load` always produces string
keys, so there is no symbol/string split to reconcile):
```python
def dig(self, *keys):
    node = self.settings
    for key in keys:
        if isinstance(node, dict):
            node = node.get(key)
        else:
            return None
    return node
```

### Safe Nested Access

**Ruby**:
```ruby
settings[:mud][:host]      # Raises KeyError if :mud missing
settings.dig(:mud, :host)  # Returns nil if missing
```

**Python**:
```python
host = settings.get("mud", {}).get("host")   # dict.get() chaining
host = config.dig("mud", "host")             # our dig() helper
```

---

## Environment Variables

**Ruby**:
```ruby
ENV.fetch("BOUKENSHA_DIR", nil)
ENV["BOUKENSHA_DIR"] || DEFAULT_DIR

require "dotenv"
Dotenv.load(env_file) if File.exist?(env_file)
```

**Python**:
```python
import os
from dotenv import load_dotenv
from pathlib import Path

env_file = Path(dir) / ".env"
if env_file.exists():
    load_dotenv(env_file)

value = os.environ.get("BOUKENSHA_DIR") or DEFAULT_DIR
```

---

## Type System

**Ruby** is implicitly typed; **Python** should annotate everything:

```python
from pathlib import Path
from typing import Any, Dict, Optional

class Config:
    dir: Path
    settings: Dict[str, Any]

    def dig(self, *keys: str) -> Any:
        ...

    def tasks(self, name: Optional[str] = None) -> Dict[str, Any]:
        ...
```

(Pydantic was considered for settings validation but dropped — see Decisions
above. Revisit only if a later step needs real schema validation.)

---

## Common Pitfalls

### 1. YAML Safe Loading
**Wrong**: `yaml.load(open("settings.yaml"))` — unsafe.
**Correct**:
```python
with open("settings.yaml") as f:
    yaml.safe_load(f)
```

### 2. Path Type Consistency
**Inconsistent**: `self.dir = dir` (could be str, Path, or None).
**Better**:
```python
def __init__(self, dir: Optional[str] = None):
    self.dir: Path = Path(dir or self._resolve_dir())
```

### 3. Optional Chaining Errors
**Crashes**: `result.upper()` when `result` may be `None`.
**Safe**: `result.upper() if result else None`

### 4. Private Method Convention
Prefix internal methods with `_` (e.g. `_resolve_dir()`) — there's no Ruby-style convention to fall back on.

### Additional gotchas hit while porting
- **YAML module not found** → `pip install pyyaml`
- **python-dotenv not loading .env** → call `load_dotenv()` after the `.env` file exists, not before
- **Prompt file not found** → confirm `user_prompts_dir` and `default_prompts_dir` are passed correctly

---

## Quick Reference: Key Translations

| Concept | Ruby | Python |
|---------|------|--------|
| Home dir | `Dir.home` | `Path.home()` |
| Join paths | `File.join(a, b)` | `Path(a) / b` |
| Check existence | `File.exist?(path)` | `Path(path).exists()` |
| Read file | `File.read(file)` | `Path(file).read_text()` |
| Module | `module Foo` | `# boukensha/foo.py` |
| Private | Ruby convention | `_private_method()` |
| Type hints | None | `def foo() -> str:` |
| YAML load | `YAML.safe_load()` | `yaml.safe_load()` |
| Env vars | `ENV["KEY"]` | `os.environ["KEY"]` |
| Dict access | `hash[:key]` | `dict.get("key")` |
| Class method | `def self.foo` | `@classmethod` |
| Predicate | `prompt_override?` | `is_prompt_override()` |

---

## Verifying Success

```bash
source venv/bin/activate
python -c "from boukensha import Config; print('Import works')"
./week1_baseline/bin/python/00_config
```

Confirmed working — output matches the Ruby version's shape (provider,
model, prompt override, system prompt preview, MUD host/user, API key
presence, and the `Config` repr).

## What NOT to Do

- Don't hard-code paths (use `Path` and the config system)
- Don't expose internal methods (`_private` methods)
- Don't skip tests for "simple" code — but also don't add a pytest suite
  here; the example script is the agreed-upon smoke test for this step
- Don't use `yaml.load()` without `safe_load()`
- Don't ignore type hints — annotate everything
- Don't create a per-step `.venv` — reuse the shared root `venv`

## References

- Ruby source: `week1_baseline/ruby/00_config/`
- Python implementation: `week1_baseline/python/00_config/`
- Launchers: `week1_baseline/bin/ruby/00_config`, `week1_baseline/bin/python/00_config`
