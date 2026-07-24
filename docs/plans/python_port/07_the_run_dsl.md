# Python Port: Boukensha The Run DSL (07_the_run_dsl)

**Status**: Planning — This document defines the port plan for `week1_baseline/ruby/07_the_run_dsl/` to Python. Reconciled against the reference plan at `docs/plans/python_port/07_the_run_dsl.md` on the `omenking/claude-code-camp-2026-Q2` `main` branch.

Every previous step required manually creating and wiring together a `Context`, `Registry`, `Backend`, `PromptBuilder`, `Client`, `Logger`, and `Agent`. This step adds one top-level entry point, `Boukensha.run(task:, ...) { ... }`, that hides all of that plumbing behind a single call plus a small block-based DSL for registering tools. It is purely additive — no existing class's public behavior changes.

## Decisions

These decisions build on 00_config through 06_the_logger:

- **`RunDSL` is a new, deliberately tiny class**: Lives in `src/boukensha/run_dsl.py`. Ruby's `RunDSL#initialize(registry)` stores the registry and exposes exactly one method, `tool`, which forwards straight to `registry.tool`. Ruby achieves "the block runs with `self` as the DSL host" via `instance_eval(&block)`; Python has no direct equivalent for a `do ... end`-style block syntax. The port exposes `RunDSL` as an explicit-receiver object passed into a `configure` callback, and gives `RunDSL.tool` **decorator** syntax (`@dsl.tool(name, description=..., parameters=...)` wrapping a `def`) so registration still reads like Ruby's inline block body — see the dedicated translation note below.

- **`boukensha.run()` is a new module-level function, defined in its own module**: Ruby's `Boukensha.run` is a `self.` method defined directly on the `Boukensha` module, alongside `config`/`quiet!`/`debug!`. The Python port adds `run()` to a new `src/boukensha/run.py` — **not** `state.py` — since `run()` needs `Agent`, `Logger`, `Registry`, `Context`, `RunDSL`, `Player`, and every `Backend`, while `state.py` deliberately stays a leaf module with no dependency on any of those (a property earlier steps' plans relied on to avoid a circular import through `__init__.py`). `boukensha/__init__.py` imports and re-exports `run` from `run.py`, so the public API (`boukensha.run(...)`) is unchanged from putting it directly in `__init__.py` — this is purely an internal-file-organization choice to keep `__init__.py` from growing a 90-line orchestration function inline. `state.py` itself is untouched in this step.

- **`errors.py` gets `LoopError` back**: Ruby's `errors.rb` re-adds `LoopError` in this step (it was dropped in 06 as unused). It remains unused in 07 too — no code raises it anywhere in `lib/` or `examples/` (confirmed via `grep -rn LoopError` across the Ruby 07 tree, one hit: the class definition itself). The Python port mirrors this exactly: add `LoopError` back to `errors.py` and re-export it from `__init__.py`, but don't invent a call site for it — it's dead-code plumbing for a future step, same as `Logger.turn()`/`Logger.subscribe()` below.

- **`Logger` gains two new, currently-unused members**: `turn(n)` (writes a `{"phase": "turn", "n": n}` line — distinct from the existing `iteration`/`turn_end`) and `subscribe(callback)` (registers a callback invoked with the raw event dict on every `_write_log`, synchronously, after the line has been written and flushed but before `session_id`/`at` are merged in). Ruby's `agent.rb` is **unchanged** between 06 and 07 (confirmed via diff — zero lines differ), so nothing in the agent loop calls `turn()` or registers a subscriber yet, and `run()` doesn't call `.subscribe()` either. The session-start event written inside `Logger.__init__` happens before any caller has a chance to subscribe, so it's never observed by a subscriber. Port both as plumbing only, matching Ruby.

- **`config.py`'s MUD helpers and `context.py`/`config.py` whitespace-only diffs are not ported**: Ruby's `config.rb` diff in this step re-adds `mud_host`/`mud_port`/`mud_username`/`mud_password` (removed in Ruby 06) and reformats an `if`. The Python `config.py` already carries these four properties unchanged since 05/06 (it never removed them — see the 06 plan's note), so there is nothing to do here. Ruby's `context.rb` diff is whitespace/alignment only (extra spaces around `@ivar` assignments) plus a missing trailing newline — no behavioral change, so Python's `context.py` is untouched.

- **`agent.py`, `prompt_builder.py`, `registry.py`, `tool.py`, `message.py`, `client.py`, `tasks/*.py`, `backends/*.py`, `state.py` are unchanged**: Confirmed via `diff` against `06_the_logger` — every one of these Ruby files is byte-for-byte identical between 06 and 07. Copy them forward as-is. Do not alter `Registry.tool`'s existing signature (`block=` keyword, not decorator-capable) to accommodate `RunDSL` — `RunDSL.tool` supplies its own decorator sugar on top of the unmodified `Registry.tool` call underneath (see Section 2).

- **Only `None` counts as "omitted" when resolving `run()`'s optional arguments** — not falsiness: Ruby's `||=` only falls back when the left side is `nil` or `false` (Ruby's *only* two falsy values — `0` and `""` are both truthy in Ruby). A naive Python port using `x or fallback` would incorrectly override an explicit `max_output_tokens=0` (or an explicit empty-string `system=""`) with the computed default, since Python's `or` treats `0`, `""`, and `{}` as falsy too. Every optional keyword in `run()` (`system`, `model`, `backend`, `max_output_tokens`; `api_key` was already written correctly) must be resolved with an explicit `if x is None:` check, never `x or fallback`.

## Target Python Structure (as planned)

```
week1_baseline/python/07_the_run_dsl/
├── src/
│   └── boukensha/
│       ├── __init__.py              # Package exports (modify: add LoopError, RunDSL, run)
│       ├── run.py                   # run() function (NEW)
│       ├── run_dsl.py               # RunDSL class (NEW)
│       ├── state.py                 # Module-level quiet/debug/config state (copy, unchanged)
│       ├── logger.py                # Logger class (modify: add turn(), subscribe())
│       ├── agent.py                 # Agent class (copy, unchanged)
│       ├── client.py                # Client class (copy, unchanged)
│       ├── config.py                # Config class (copy, unchanged)
│       ├── tool.py                  # Tool dataclass (copy, unchanged)
│       ├── message.py               # Message dataclass (copy, unchanged)
│       ├── context.py               # Context class (copy, unchanged)
│       ├── errors.py                # Re-add LoopError
│       ├── registry.py              # Registry class (copy, unchanged)
│       ├── prompt_builder.py        # PromptBuilder class (copy, unchanged)
│       ├── tasks/                   # (copy, unchanged)
│       └── backends/                # (copy, unchanged)
├── examples/
│   └── example.py                   # Rewritten to use boukensha.run() + the decorator DSL (modify)
├── prompts/
│   └── system.md                    # (copy, unchanged)
├── pyproject.toml                   # Package config (copy, bump version to 0.7.0)
└── README.md                        # Usage documentation (NEW content, ported from Ruby README)
```

### Already Ported (from 06_the_logger, unchanged)
- **config.py**, **tool.py**, **message.py**, **context.py**, **registry.py**, **client.py**, **prompt_builder.py**, **agent.py**, **state.py**
- **tasks/base.py**, **tasks/player.py**
- **backends/base.py**, **backends/anthropic.py**, **backends/gemini.py**, **backends/ollama.py**, **backends/ollama_cloud.py**, **backends/openai.py**
- **prompts/system.md**

### New in This Step
- **run_dsl.py**: `RunDSL` class
- **run.py**: `run()` function

### Modified in This Step
- **logger.py**: Add `turn(n)` and `subscribe(callback)`
- **errors.py**: Re-add `LoopError`
- **__init__.py**: Export `LoopError`, `RunDSL`, and `run`
- **examples/example.py**: Rewritten around `boukensha.run(task=...)` and the `@dsl.tool(...)` decorator instead of manual wiring

## Quick Setup

### 1. Ensure prior steps are ported and installed
```bash
source venv/bin/activate
pip install -e week1_baseline/python/00_config
pip install -e week1_baseline/python/01_struct_skeleton
pip install -e week1_baseline/python/02_the_registry
pip install -e week1_baseline/python/03_prompt_builder
pip install -e week1_baseline/python/04_api_client
pip install -e week1_baseline/python/05_agent_loop
pip install -e week1_baseline/python/06_the_logger
```

### 2. Install 07_the_run_dsl
```bash
pip install -e week1_baseline/python/07_the_run_dsl
```

### 3. Run it
```bash
./week1_baseline/bin/python/07_the_run_dsl
```

---

## Porting Plan: File by File

### 1. Copy Prior Step as Template

```bash
cp -r week1_baseline/python/06_the_logger week1_baseline/python/07_the_run_dsl
```

---

### 2. `RunDSL` (`lib/boukensha/run_dsl.rb` → `src/boukensha/run_dsl.py`)

**Ruby** (full file):
```ruby
module Boukensha
  # RunDSL is the object that `self` becomes inside a Boukensha.run block.
  # It exposes only `tool`, keeping the DSL surface intentionally small.
  class RunDSL
    def initialize(registry)
      @registry = registry
    end

    def tool(name, description:, parameters: {}, &block)
      @registry.tool(name, description: description, parameters: parameters, &block)
    end
  end
end
```

**Python** (`src/boukensha/run_dsl.py`, new file):
```python
from typing import Any, Callable, Dict, Optional

from .registry import Registry


class RunDSL:
    """The object passed into a ``boukensha.run(..., configure=...)`` callback.

    Exposes only ``tool``, keeping the DSL surface intentionally small.
    ``tool`` is used as a decorator, mirroring how Ruby's inline block reads:

        def register_tools(dsl):
            @dsl.tool(
                "read_file",
                description="Read a file from disk",
                parameters={"path": {"type": "string"}},
            )
            def read_file(path):
                return Path(path).read_text()
    """

    def __init__(self, registry: Registry) -> None:
        self._registry = registry

    def tool(
        self,
        name: str,
        *,
        description: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Callable[[Callable], Callable]:
        def decorator(func: Callable) -> Callable:
            self._registry.tool(
                name, description=description, parameters=parameters or {}, block=func
            )
            return func

        return decorator
```

**Key translation notes**:
- Ruby's `RunDSL.new(registry).instance_eval(&block)` re-binds `self` inside the block to the `RunDSL` instance, so calls to bare `tool(...)` inside the block resolve to `RunDSL#tool`. Python has no `instance_eval` and no block-as-syntax; a Python callable passed as `configure=register_tools` must receive the DSL object as an explicit parameter. See "Translating the block DSL" below for how `run()`'s call site uses this.
- `&block` (implicit block param, then `&block` forwarded again to `@registry.tool`) → `RunDSL.tool` returns a **decorator function** that captures `func` when applied and forwards it as `Registry.tool`'s existing `block=` keyword. This keeps `Registry.tool` itself completely unchanged (it still only accepts `block=` as a plain keyword argument, not a decorator) — the decorator sugar lives entirely in `RunDSL`, one layer up.
- Ruby's `parameters: {}` default → Python's `parameters: Optional[Dict[str, Any]] = None` plus `parameters or {}` at the call site, matching the mutable-default-argument avoidance already used by `Registry.tool` itself (see 02_the_registry).

---

### 3. Errors — Re-add `LoopError` (`lib/boukensha/errors.rb` → `src/boukensha/errors.py`)

**Ruby**:
```ruby
module Boukensha
  class UnknownToolError < StandardError; end
  class ApiError         < StandardError; end
  class LoopError        < StandardError; end
  class UnsupportedModelError < StandardError; end
end
```

**Python** (add `LoopError` back to existing `errors.py`):
```python
class UnknownToolError(Exception):
    """Raised when dispatch() is called with an unknown tool name."""
    pass


class ApiError(Exception):
    """Raised when an API request fails after retries are exhausted."""
    pass


class LoopError(Exception):
    """Reserved for future use — not currently raised anywhere."""
    pass


class UnsupportedModelError(Exception):
    """Raised when a backend is initialized with an unsupported model."""
    pass
```

**Note**: Don't add a raise site for this anywhere — Ruby doesn't either in this step. It's carried purely for parity with the Ruby class hierarchy in case a later step starts raising it.

---

### 4. Logger — add `turn()` and `subscribe()` (`lib/boukensha/logger.rb` → `src/boukensha/logger.py`)

**Ruby diff** (against 06):
```ruby
    def turn(n:)
      write_log(phase: "turn", n: n)
    end
```
placed right after `initialize`, and:
```ruby
    def subscribe(&block)
      @subscribers ||= []
      @subscribers << block
    end
```
placed after `raw`, plus one line added to the existing private `write_log`:
```ruby
    def write_log(event)
      @log_io.puts JSON.generate(event.merge(session_id: @session_id, at: Time.now.iso8601))
      @log_io.flush
      @subscribers&.each { |s| s.call(event) }
    end
```

**Python** (add to existing `logger.py`):
```python
    def turn(self, n: int) -> None:
        self._write_log({"phase": "turn", "n": n})
```
placed right after `__init__`, and:
```python
    def subscribe(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        self._subscribers.append(callback)
```
with `_write_log` updated to notify subscribers, after writing and flushing:
```python
    def _write_log(self, event: Dict[str, Any]) -> None:
        record = {
            **event,
            "session_id": self.session_id,
            "at": datetime.now().astimezone().isoformat(),
        }
        self._log_file.write(json.dumps(record, default=str) + "\n")
        self._log_file.flush()
        for callback in self._subscribers:
            callback(event)
```

And in `__init__`, initialize `self._subscribers: List[Callable[[Dict[str, Any]], None]] = []` alongside the existing attributes (rather than Ruby's lazy `@subscribers ||= []` inside `subscribe`) — Python has no equivalent perf/readability reason to defer the list creation, and an eagerly-initialized empty list keeps `_write_log`'s notify loop branch-free. Because `self._subscribers` is initialized in `__init__` *before* the `session_start` event is written, and callers can only reach `subscribe()` after `Logger.__init__` has already returned, the `session_start` line is written with zero subscribers registered and is never observed by any callback — matching Ruby exactly (`@subscribers` is unset when `write_log` runs for `session_start`).

Add `from typing import Callable` to the existing `typing` import line.

**Key translation notes**:
- `@subscribers&.each { |s| s.call(event) }` (safe-navigation on a possibly-nil array) → since Python initializes `_subscribers` as `[]` up front instead of leaving it unset, the loop is just `for callback in self._subscribers: callback(event)` — no `None`-guard needed. This is a from-Ruby idiom translation, not a behavior change (an empty list iterates zero times, same as Ruby's `nil&.each` no-op).
- The subscriber receives the **pre-serialization** event dict (before `session_id`/`at` are merged in and before JSON encoding), called synchronously, in both languages, and only after the line has actually been written and flushed to disk — port this ordering exactly; don't pass the enriched `record` or the JSON string, and don't notify before the write.
- `turn(n:)` is a keyword-only param in Ruby; the Python port keeps it as a plain positional-or-keyword `n: int` for consistency with the rest of `Logger`'s single-int-arg methods, matching how `iteration`/`limit_reached` already take `n`/`max` this way in the existing 06 port.
- Don't add a background thread, buffering, or an error-swallowing policy around subscriber notification — if a callback raises, let the exception propagate normally, matching Ruby's unguarded `s.call(event)`.

---

### 5. `run()` (`lib/boukensha.rb` → `src/boukensha/run.py`)

**Ruby** (from `lib/boukensha.rb`, new method):
```ruby
def self.run(
  task:,
  system:       nil,
  model:        nil,
  backend:      nil,
  api_key:      nil,
  ollama_host:  "http://localhost:11434",
  log:          nil,
  max_output_tokens: nil,
  &block
)
  cfg           = config                           # loads .env; populates ENV
  task_class    = Tasks::Player
  task_settings = cfg.tasks(task_class.task_name)
  system      ||= task_class.system_prompt(task_settings, user_prompts_dir: cfg.user_prompts_dir, default_prompts_dir: Config::PROMPTS_DIR)
  model       ||= task_class.model(task_settings)
  backend     ||= task_class.provider(task_settings).to_sym
  api_key ||= case backend
              when :anthropic    then ENV["ANTHROPIC_API_KEY"]
              when :openai       then ENV["OPENAI_API_KEY"]
              when :gemini       then ENV["GEMINI_API_KEY"]
              when :ollama_cloud then ENV["OLLAMA_API_KEY"]
              end

  ctx      = Context.new(task: task_class, system: system)
  registry = Registry.new(ctx)

  RunDSL.new(registry).instance_eval(&block) if block

  be = case backend
       when :anthropic    then Backends::Anthropic.new(api_key: api_key, model: model)
       when :openai       then Backends::OpenAI.new(api_key: api_key, model: model)
       when :gemini       then Backends::Gemini.new(api_key: api_key, model: model)
       when :ollama       then Backends::Ollama.new(host: ollama_host, model: model)
       when :ollama_cloud then Backends::OllamaCloud.new(api_key: api_key, model: model)
       else raise ArgumentError, "Unknown backend #{backend.inspect}. Use :anthropic, :openai, :gemini, :ollama, or :ollama_cloud."
       end

  builder = PromptBuilder.new(ctx, be)
  client  = Client.new(builder)
  effective_max_iterations = task_class.max_iterations(task_settings)
  effective_max_output_tokens = max_output_tokens || task_class.max_output_tokens(task_settings)
  logger  = Logger.new(log: log, snapshot: {
    task:              task_class.task_name,
    max_iterations:    effective_max_iterations,
    max_output_tokens: effective_max_output_tokens,
    model:             model,
    provider:          backend
  })
  agent   = Agent.new(context: ctx, registry: registry, builder: builder, client: client, logger: logger,
                      task_settings: task_settings, max_iterations: effective_max_iterations, max_output_tokens: effective_max_output_tokens)

  ctx.add_message(:user, task)
  agent.run
ensure
  logger&.close
end
```

**Note on Ruby's `max_output_tokens || task_class.max_output_tokens(...)`**: in Ruby, `0` and `""` are truthy (only `nil`/`false` are falsy), so `||=`/`||` here already behaves as "only fall back when omitted." The direct transliteration to Python's `or` does **not** carry the same meaning (`0 or x` evaluates to `x` in Python) — see the dedicated note below and the Decisions section.

**Python** (`src/boukensha/run.py`, new file):
```python
import os
from typing import Any, Callable, Optional

from .agent import Agent
from .backends.anthropic import Anthropic
from .backends.gemini import Gemini
from .backends.ollama import Ollama
from .backends.ollama_cloud import OllamaCloud
from .backends.openai import OpenAI
from .client import Client
from .config import Config
from .context import Context
from .logger import Logger
from .prompt_builder import PromptBuilder
from .registry import Registry
from .run_dsl import RunDSL
from .state import config as boukensha_config
from .tasks.player import Player

_API_KEY_ENV_VARS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "ollama_cloud": "OLLAMA_API_KEY",
}


def run(
    task: str,
    system: Optional[str] = None,
    model: Optional[str] = None,
    backend: Optional[str] = None,
    api_key: Optional[str] = None,
    ollama_host: str = "http://localhost:11434",
    log: Optional[str] = None,
    max_output_tokens: Optional[int] = None,
    configure: Optional[Callable[[RunDSL], None]] = None,
) -> str:
    """The top-level entry point. Wires together every primitive so the
    caller only has to describe *what* to do, not *how* to plumb it.

        def register_tools(dsl):
            @dsl.tool(
                "read_file",
                description="Read a file from disk",
                parameters={"path": {"type": "string", "description": "File path"}},
            )
            def read_file(path):
                return Path(path).read_text()

        result = run(task="Summarise lib/boukensha.rb", configure=register_tools)
    """
    cfg = boukensha_config()  # loads .env; populates os.environ
    task_class = Player
    task_settings = cfg.tasks(task_class.task_name())

    if system is None:
        system = task_class.system_prompt(
            task_settings,
            user_prompts_dir=cfg.user_prompts_dir,
            default_prompts_dir=Config.PROMPTS_DIR,
        )
    if model is None:
        model = task_class.model(task_settings)
    if backend is None:
        backend = task_class.provider(task_settings)
    if api_key is None:
        api_key = os.environ.get(_API_KEY_ENV_VARS.get(backend, ""))

    ctx = Context(task=task_class, system=system)
    registry = Registry(ctx)

    if configure is not None:
        configure(RunDSL(registry))

    if backend == "anthropic":
        be: Any = Anthropic(api_key=api_key, model=model)
    elif backend == "openai":
        be = OpenAI(api_key=api_key, model=model)
    elif backend == "gemini":
        be = Gemini(api_key=api_key, model=model)
    elif backend == "ollama":
        be = Ollama(host=ollama_host, model=model)
    elif backend == "ollama_cloud":
        be = OllamaCloud(api_key=api_key, model=model)
    else:
        raise ValueError(
            f"Unknown backend {backend!r}. Use 'anthropic', 'openai', 'gemini', "
            f"'ollama', or 'ollama_cloud'."
        )

    builder = PromptBuilder(ctx, be)
    client = Client(builder)
    effective_max_iterations = task_class.max_iterations(task_settings)
    effective_max_output_tokens = (
        max_output_tokens if max_output_tokens is not None else task_class.max_output_tokens(task_settings)
    )
    logger = Logger(
        log=log,
        snapshot={
            "task": task_class.task_name(),
            "max_iterations": effective_max_iterations,
            "max_output_tokens": effective_max_output_tokens,
            "model": model,
            "provider": backend,
        },
    )
    agent = Agent(
        context=ctx,
        registry=registry,
        builder=builder,
        client=client,
        logger=logger,
        task_settings=task_settings,
        max_iterations=effective_max_iterations,
        max_output_tokens=effective_max_output_tokens,
    )

    ctx.add_message("user", task)
    try:
        return agent.run()
    finally:
        logger.close()
```

**Translating the block DSL**:
Ruby's `Boukensha.run(task: "...") { tool "read_file", description: "...", parameters: {...} { |path:| ... } }` relies on two Ruby-only features that don't have a direct Python equivalent: (1) blocks as an implicit trailing argument to any method, and (2) `instance_eval` to change what `self` means inside that block. The Python port can't reproduce "bare `tool(...)` calls resolving against a hidden DSL object" without them, so it exposes the DSL object explicitly instead: callers pass a `configure` callable that receives the `RunDSL` instance as its one argument and uses `@dsl.tool(...)` as a decorator inside it. This is the smallest change that preserves "one function call registers all your tools before the agent starts" while staying idiomatic Python — see Common Pitfall #1 for why a context-manager or thread-local-magic alternative was considered and rejected for this step.

**Key translation notes**:
- `cfg.tasks(task_class.task_name)` — Ruby's `task_name` is called without parens (works whether it's a method or a Ruby "attr"-like call); Python's `Player.task_name()` is an explicit classmethod call (see `tasks/base.py`), so parens are required — `task_class.task_name()`, not `task_class.task_name`.
- `system ||= ...` / `model ||= ...` / `backend ||= ...` / `max_output_tokens || ...` → **all** four must use `if x is None:` in Python, not `x or fallback`. This is the single most important correctness detail in this port — see the dedicated Decisions bullet and Common Pitfall below. (`api_key`'s resolution was already correctly written with `if api_key is None:` in earlier drafts of this plan; the other four need the same treatment.)
- `backend ||= task_class.provider(task_settings).to_sym` → Python has no meaningful symbol/string distinction here; keep `backend` as a plain `str` throughout (`"anthropic"`, `"ollama"`, etc.) and compare with `==` instead of Ruby's `case backend when :anthropic`. `Task.provider()` (in `tasks/base.py`) already returns a plain string, so no `.to_sym`-equivalent conversion is needed at all.
- `ENV["ANTHROPIC_API_KEY"]` / `case backend when :anthropic then ... when :openai then ...` (explicit `case` over 4 known keys, `nil` for `:ollama`) → the Python port uses a `_API_KEY_ENV_VARS` dict lookup with `.get(backend, "")`, which returns `os.environ.get("")` → `None` for `"ollama"` (not in the dict) exactly like Ruby's `case` falling through with no matching `when` clause returns `nil`. Don't simplify this into a blanket `f"{backend.upper()}_API_KEY"` pattern — Ruby's dispatch is deliberately an explicit enumerated list, not a name-derived convention, and `ollama_cloud` → `OLLAMA_API_KEY` (not `OLLAMA_CLOUD_API_KEY`) breaks any such convention anyway.
- `RunDSL.new(registry).instance_eval(&block) if block` → `if configure is not None: configure(RunDSL(registry))`. Order matters: this must happen *before* the backend/builder/client are constructed (matching Ruby's ordering), since tool registration only needs the `Context`/`Registry`, not any backend-specific object.
- `logger&.close` in Ruby's `ensure` (safe-navigation guards against `logger` being unset if an earlier line raised) → Python's `finally: logger.close()` is only reached once `logger` has been assigned, since `Logger(...)` construction happens several lines before any of the exception-prone agent/API code runs; if `Logger.__init__` itself raises (e.g. an unwritable directory), the `try` block was never entered, so there's no `NameError` risk to guard against with a Python equivalent of `&.`. Cleanup only needs to happen once the logger exists — failures before that point need no cleanup at all.
- `run.py` imports `config` from `state.py` and aliases it to `boukensha_config` locally to avoid shadowing the `run()`-local variable naming and to keep it visually distinct from the module-level `Config` class import — this is a naming choice, not a behavior difference from Ruby's unqualified `config` module method call.

---

### 6. Package Exports (`lib/boukensha.rb`'s `require_relative` list → `src/boukensha/__init__.py`)

**Python** (modify existing file):
```python
# Boukensha agent loop — backends, tasks, registry, builder, client, agent, logger, and run DSL
# Re-uses config, struct, registry, prompt builder, and client classes from prior steps

# Local struct, config, and registry classes
from .config import Config  # noqa: F401
from .tool import Tool  # noqa: F401
from .message import Message  # noqa: F401
from .context import Context  # noqa: F401
from .errors import UnknownToolError, UnsupportedModelError, ApiError, LoopError  # noqa: F401
from .registry import Registry  # noqa: F401

# From prior step (03_prompt_builder)
from .prompt_builder import PromptBuilder  # noqa: F401
from . import tasks  # noqa: F401
from . import backends  # noqa: F401

# From prior step (04_api_client)
from .client import Client  # noqa: F401

# From prior step (05_agent_loop)
from .agent import Agent  # noqa: F401

# From prior step (06_the_logger)
from .logger import Logger  # noqa: F401
from .state import config, quiet, loud, is_quiet, debug, is_debug  # noqa: F401

# New in this step (07_the_run_dsl)
from .run_dsl import RunDSL  # noqa: F401
from .run import run  # noqa: F401

__all__ = [
    "Config",
    "Tool",
    "Message",
    "Context",
    "Registry",
    "UnknownToolError",
    "UnsupportedModelError",
    "ApiError",
    "LoopError",
    "PromptBuilder",
    "Client",
    "Agent",
    "Logger",
    "RunDSL",
    "config",
    "quiet",
    "loud",
    "is_quiet",
    "debug",
    "is_debug",
    "run",
    "tasks",
    "backends",
]
```

**Change**: Add `LoopError` back to the `errors` import and `__all__`. Add `RunDSL` (from the new `run_dsl.py`) and `run` (from the new `run.py`) — `state.py`'s import line itself is unchanged from 06.

---

### 7. Example (`examples/example.rb` → `examples/example.py`)

**Ruby** (full file):
```ruby
ENV["BOUKENSHA_DIR"] ||= File.expand_path("../../../../.boukensha", __dir__)
require_relative "../lib/boukensha"

puts "=== BOUKENSHA Step 7: The Boukensha.run DSL ==="
puts
puts "Config: #{Boukensha.config}"
puts

base_dir = File.expand_path("..", __dir__)

result = Boukensha.run(
  task: "Read the README.md file and summarise what this MUD player assistant framework can do."
) do
  tool "read_file",
    description: "Read the contents of a file from disk",
    parameters:  { path: { type: "string", description: "The file path to read" } } do |path:|
    File.read(File.expand_path(path, base_dir))
  end

  tool "list_directory",
    description: "List the files in a directory",
    parameters:  { path: { type: "string", description: "The directory path to list" } } do |path:|
    Dir.entries(File.expand_path(path, base_dir))
       .reject { |f| f.start_with?(".") }
       .join(", ")
  end
end

puts
puts "=== FINAL RESPONSE ==="
puts result
```

**Python** (rewrite `examples/example.py`):
```python
import os
from pathlib import Path

import boukensha

os.environ.setdefault(
    "BOUKENSHA_DIR",
    str(Path(__file__).resolve().parent.parent.parent / ".boukensha"),
)

print("=== BOUKENSHA Step 7: The Boukensha.run DSL ===")
print()
print(f"Config: {boukensha.config()}")
print()

base_dir = Path(__file__).resolve().parent.parent


def register_tools(dsl: boukensha.RunDSL) -> None:
    @dsl.tool(
        "read_file",
        description="Read the contents of a file from disk",
        parameters={"path": {"type": "string", "description": "The file path to read"}},
    )
    def read_file(path: str) -> str:
        return (base_dir / path).read_text()

    @dsl.tool(
        "list_directory",
        description="List the files in a directory",
        parameters={"path": {"type": "string", "description": "The directory path to list"}},
    )
    def list_directory(path: str) -> str:
        return ", ".join(
            f for f in os.listdir(str(base_dir / path)) if not f.startswith(".")
        )


# Task defaults (system prompt, model, provider, credentials) come from the
# Boukensha config directory. Any of run()'s keyword arguments can override
# a specific default without touching the others.
result = boukensha.run(
    task="Read the README.md file and summarise what this MUD player assistant framework can do.",
    configure=register_tools,
)

print()
print("=== FINAL RESPONSE ===")
print(result)
```

**Key translation notes**:
- Ruby's example no longer imports `Config`, `Context`, `PromptBuilder`, `Client`, `Registry`, `Agent`, `Logger`, the task classes, or the backend classes directly — `Boukensha.run` hides all of it. The Python example mirrors this: only `import boukensha` is needed (no more `from boukensha import Config, Context, ...` block seen in every prior step's example).
- Ruby's inline `do |path:| ... end` blocks become Python `def`s decorated with `@dsl.tool(...)` — a direct visual parallel to the Ruby block body, rather than lambdas passed as a `block=` keyword.
- The `register_tools(dsl)` function stands in for Ruby's `instance_eval`'d block body; it's passed as `configure=register_tools` to `boukensha.run(...)`, per the "Translating the block DSL" note in Section 5.
- The lower-level classes (`Context`, `Registry`, `Agent`, etc.) remain available for advanced/manual construction exactly as before — `run()` is a convenience wrapper around them, not a replacement API.

---

### 8. Update pyproject.toml

Bump version from `0.6.0` to `0.7.0`:
```toml
[project]
name = "boukensha"
version = "0.7.0"
description = "Boukensha run DSL — a single entry point that wires context, registry, backend, prompt builder, client, logger, and agent together"
# ... rest unchanged
```

---

### 9. Update README.md

Replace the step 6 README with step 7 content, ported from the Ruby `README.md`. Key sections:

- **What this step adds**: one entry point, `boukensha.run(task=..., configure=...)`, replacing manual wiring of `Context`/`Registry`/`Backend`/`PromptBuilder`/`Client`/`Logger`/`Agent`; note that callers can omit `configure` entirely for tool-free runs, and can still reach for the lower-level classes directly for advanced construction.
- **The new primitives**: `RunDSL` (the `tool()`-only object passed into your `configure` callback, used as a decorator) and `run()` (accepts `task`, `system`, `model`, `backend`, `api_key`, `ollama_host`, `log`, `max_output_tokens`, `configure`)
- **Options table**: same shape as Ruby's, adapted to Python's keyword names (`backend` takes a plain string — `"anthropic"`, `"openai"`, `"gemini"`, `"ollama"`, `"ollama_cloud"` — not a Ruby symbol). Document the API as actually implemented (`max_output_tokens`), not Ruby's stale README prose, which still says "Step 6" and mentions unimplemented `token_budget:`/`max_tokens:` option names.
- **Before/after comparison**: manual step-6-style wiring vs. the one-call `boukensha.run(...)` form, using the Python syntax (a `configure` function using `@dsl.tool(...)` decorators, not an inline Ruby block)
- **Run Example**: `./week1_baseline/bin/python/07_the_run_dsl`

---

## Dependency Chain

```
07_the_run_dsl (RunDSL, run)
    ↓ extends/depends on
06_the_logger (Logger, state)
    ↓ extends/depends on
05_agent_loop (Agent)
    ↓ extends/depends on
04_api_client (Client, ApiError)
    ↓ extends/depends on
03_prompt_builder (PromptBuilder, Backends)
    ↓ extends/depends on
02_the_registry (Registry, UnknownToolError)
    ↓ extends/depends on
01_struct_skeleton (Tool, Message, Context)
    ↓ depends on
00_config (Config, Tasks.Base, Tasks.Player)
```

**Action**: Verify prior steps are installed before porting.

---

## Testing / Verification Strategy

Prefer fake/stub `client`/`backend` objects for `Agent`-level behavior (unchanged from 06) — this step's own surface (`run()`, `RunDSL`) is best verified by monkeypatching the backend constructors or stubbing `Client.call`/`PromptBuilder.parse_response`, so verification can run fully offline with no API keys.

### Unit-level verification (as you build):
1. **Import surface**: `from boukensha import RunDSL, run, LoopError, Logger, Agent` succeeds; `LoopError` is now importable again (re-added — confirm no other code in the tree accidentally starts relying on it being raised, since it still isn't).
2. **`RunDSL.tool` as a decorator**: construct a `Registry` against a bare `Context`, wrap it in a `RunDSL`, decorate a plain function with `@dsl.tool("x", description="d", parameters={})`, and assert (a) the tool lands in `context.tools["x"]` with the right description/parameters/block, (b) dispatching `"x"` calls through to the original function and returns its result, and (c) the decorator returns the original function unchanged (so it remains independently callable/testable).
3. **`run()` argument resolution — `None` vs. falsy**: with `task_settings` stubbed to a fixed dict, verify `system`/`model`/`backend` fall back to `Player.system_prompt`/`Player.model`/`Player.provider` only when the corresponding keyword is `None`, and that explicit keyword arguments always win — **including an explicit `max_output_tokens=0`**, which must survive unchanged and not be silently replaced by `Player.max_output_tokens(...)` (this is the truthiness pitfall called out in the Decisions section; write a test specifically for it).
4. **`run()` API key resolution**: for each of the four keyed backends (`anthropic`, `openai`, `gemini`, `ollama_cloud`), verify the correct env var is read when `api_key` is omitted; verify `ollama` needs no API key (resolves to `None` without raising); verify an explicit `api_key` always overrides the environment.
5. **`run()` backend construction**: for all five backend names, verify the right `Backends.*` class is instantiated with the right constructor kwargs (`api_key`/`model` for four of them; `host`/`model` for `ollama`); verify an unknown backend string raises `ValueError` with a message naming all five valid options, without attempting any network request.
6. **`run()` configure-callback ordering**: with a spy `configure` callable, assert it is invoked with a `RunDSL` instance exactly once, *before* any backend is constructed (patch the backend classes to record call order relative to the callback); assert all tools registered inside it are present in the agent's context by the time `agent.run()` is called; assert a `run()` call with `configure` omitted entirely still succeeds.
7. **`run()` snapshot/logging**: stub `Logger` and assert the `snapshot` passed to it contains `task`, `max_iterations`, `max_output_tokens`, `model`, and `provider` matching the resolved values (not the raw, possibly-`None` keyword arguments); assert `task` becomes the agent's initial user message and `run()` returns the agent's final string.
8. **`run()` cleanup on success and failure**: assert `logger.close()` is called exactly once whether `agent.run()` returns normally or raises; use a stub `Agent.run` that raises to confirm the `finally` path still closes the logger and does not swallow the original exception.
9. **`Logger.turn()`**: call it directly against a `Logger` pointed at a temp file; assert the exact `{"phase": "turn", "n": ...}` shape (plus the usual `session_id`/`at`).
10. **`Logger.subscribe()`**: register two callbacks in order; call any phase method; assert both were invoked exactly once, in registration order, with the pre-serialization event dict (no `session_id`/`at` keys), only after the JSONL line was actually written and flushed; verify a `Logger` with zero subscribers behaves identically to today (no exceptions, no-op notify loop); verify the `session_start` event from `__init__` is never delivered to a subscriber registered afterward.
11. **End-to-end with a fully stubbed backend**: patch `Backends.Anthropic` (or whichever `run()` selects) so its `Client.call`/`PromptBuilder.parse_response` return a canned end-turn response; call `boukensha.run(task="...", backend="anthropic", api_key="x", model="m", configure=register_tools)`; assert the returned string matches the canned response text and that a session JSONL file was written.
12. **Launcher smoke test**: run `week1_baseline/bin/python/07_the_run_dsl` far enough to validate its path/import setup without a network call (e.g. `python -c "import boukensha"` from the launcher's environment); only exercise a real provider when credentials or a local Ollama instance are intentionally available.

### Full integration test (requires provider credentials):
```bash
source venv/bin/activate
pip install -e week1_baseline/python/07_the_run_dsl
./week1_baseline/bin/python/07_the_run_dsl
cat ~/.boukensha/sessions/*.jsonl | tail -5   # inspect the newest session log
```

## Acceptance Criteria

- `boukensha.run(task="...")` with no other arguments successfully resolves system prompt, model, provider, and API key entirely from `~/.boukensha` config/env, exactly matching what step-6-style manual wiring would have required.
- A `configure` callable passed to `run()` can register one or more tools via the `RunDSL` object it receives, using `@dsl.tool(...)` decorator syntax, and those tools are dispatchable during the agent loop; `configure` may be omitted for tool-free runs.
- Every optional `run()` argument (`system`, `model`, `backend`, `max_output_tokens`) treats only `None` as "omitted" — an explicit falsy-but-valid value (e.g. `max_output_tokens=0`) is never silently replaced by a computed default.
- All five backends (`anthropic`, `openai`, `gemini`, `ollama`, `ollama_cloud`) are selectable via the `backend` keyword, with `ollama` requiring no API key.
- An unknown `backend` value raises `ValueError` naming the five valid choices, without attempting a network request.
- The `Logger` used internally by the `Agent` is always closed, whether the run completes normally or raises, and the original exception is never swallowed.
- `Logger.turn()` and `Logger.subscribe()` exist and behave as specified, even though nothing in `Agent` calls them yet (mirrors Ruby exactly — no invented consumer); subscribers observe flushed, pre-serialization events synchronously and never see `session_start`.
- `LoopError` is importable from `boukensha` again, with no invented raise site.
- `examples/example.py` demonstrates the same "read this file, list this directory" scenario as prior steps, using only `boukensha.run(...)` — no manual `Context`/`Registry`/`Backend`/`Client`/`Logger`/`Agent` construction.
- Step-6 behavior (agent loop, tool dispatch error handling, structured JSONL logging) is otherwise completely unchanged — confirmed by the fact that Ruby's `agent.rb` has zero diff lines between 06 and 07.

---

## Common Pitfalls

### 1. There is no faithful Python equivalent of `instance_eval(&block)`
**Problem**: Ruby's DSL trick — `RunDSL.new(registry).instance_eval(&block)` — lets a block written with bare, unqualified calls (`tool "x", description: ...`) resolve those calls against a hidden receiver object. Python has no block literals and no way to re-target `self` inside an arbitrary callable's body; a `def` always resolves names in its own lexical/module scope, never against an injected object, unless that object is passed in explicitly.
**Fix**: Require the caller's `configure` callback to accept the `RunDSL` instance as an explicit parameter (`def register_tools(dsl): ...`) and invoke it as `configure(RunDSL(registry))`, with `RunDSL.tool` returning a decorator so the registration body still reads close to Ruby's inline block. This was chosen over two alternatives considered and rejected: (a) a context-manager (`with boukensha.run_context(...) as dsl:`) — rejected because it changes `run()`'s calling convention from "one function call returns the result" to "a `with` block that returns it," which doesn't match Ruby's shape or step 07's "just describe what you want" framing; (b) monkeypatching a thread-local "current DSL" so bare module-level `tool(...)` calls could work — rejected as a much larger, fragile piece of magic to introduce for a step whose whole point is *reducing* incidental complexity.

### 2. `x or fallback` is not a safe translation of Ruby's `x ||= fallback`
**Problem**: Ruby's `||=`/`||` only fall back on `nil`/`false` — Ruby's only two falsy values. Python's `or` falls back on *any* falsy value, including `0`, `""`, `{}`, and `[]`. `max_output_tokens || task_class.max_output_tokens(task_settings)` in Ruby means "fall back only if omitted"; the literal-looking `max_output_tokens or task_class.max_output_tokens(task_settings)` in Python means "fall back if omitted **or explicitly zero**" — silently discarding a caller's legitimate `max_output_tokens=0`.
**Fix**: Use `if x is None: x = fallback` (or the ternary `x if x is not None else fallback`) for every optional `run()` argument — `system`, `model`, `backend`, and `max_output_tokens`. `api_key`'s resolution already uses `is None` correctly; make sure the other three match it exactly. Write test 3 in the Verification section specifically to catch a regression here.

### 3. `to_sym` has no meaningful Python counterpart here
**Problem**: It's tempting to translate `backend.to_sym` / `case ... when :anthropic` into some Python enum or literal-matching construct for "faithfulness."
**Fix**: Don't invent one. `Task.provider()` already returns a plain Python `str`, backend comparisons are plain `str ==` checks, and the `_API_KEY_ENV_VARS` dict is keyed by plain strings. A Ruby symbol here carries no behavior Python needs to reproduce — it's purely Ruby's convention for cheap, interned enum-like values.

### 4. Don't let `LoopError`'s re-addition tempt you into "fixing" it
**Problem**: Seeing `LoopError` come back after being removed in 06 might read as "oh, now's the time it becomes used" and invite adding a raise site as a well-intentioned improvement.
**Fix**: Resist it. `grep -rn LoopError week1_baseline/ruby/07_the_run_dsl` turns up exactly one hit — the class definition — confirming Ruby doesn't use it here either. Port the class, not a feature that doesn't exist yet.

### 5. `Logger.subscribe`'s callback timing
**Problem**: It's easy to wire the subscriber notification to fire on the *enriched* record (post `session_id`/`at` merge), before the write/flush, or after JSON serialization, since those all look like "the complete version of the event."
**Fix**: Match Ruby exactly — `@subscribers&.each { |s| s.call(event) }` runs *after* `@log_io.puts`/`@log_io.flush`, against the original `event` hash, the same one passed into `write_log` before `.merge(session_id:, at:)`. Port `_write_log` so the notify loop runs after the write, against the pre-merge `event` dict, not `record`.

### 6. Don't inline `run()`'s ~90 lines directly into `__init__.py`
**Problem**: The most literal reading of "Ruby defines `run` on the `Boukensha` module, and `__init__.py` is `boukensha`'s module-equivalent" is to paste the whole function body into `__init__.py`.
**Fix**: Keep `__init__.py` as a thin aggregator (imports + `__all__`), same as every prior step. Put the actual orchestration logic in `src/boukensha/run.py` and import `run` from there into `__init__.py`. The public surface (`boukensha.run(...)`) is identical either way; this only affects internal file organization, and keeps `__init__.py` from becoming the one file in the package that mixes "what does this package export" with "here's 90 lines of business logic."

---

## Files to Create/Modify

1. Copy entire `week1_baseline/python/06_the_logger/` to `week1_baseline/python/07_the_run_dsl/`
2. Create `src/boukensha/run_dsl.py` — `RunDSL` class
3. Create `src/boukensha/run.py` — `run()` function
4. Modify `src/boukensha/errors.py` — re-add `LoopError`
5. Modify `src/boukensha/logger.py` — add `turn(n)`, `subscribe(callback)`, and the notify-on-write hookup
6. Modify `src/boukensha/__init__.py` — export `LoopError`, `RunDSL`, `run` (`state.py` itself is untouched)
7. Rewrite `examples/example.py` — use `boukensha.run(task=..., configure=...)` and `@dsl.tool(...)` decorators instead of manual wiring
8. Update `pyproject.toml` — version bump to 0.7.0
9. Update `README.md` — replace with Step 7 (Run DSL) content, documenting the implemented API rather than Ruby's stale "Step 6"/`token_budget:` README prose
10. `week1_baseline/bin/python/07_the_run_dsl` — executable launcher (mirrors 06_the_logger's launcher, `cd` target updated to `07_the_run_dsl`)

## Not Ported (unrelated to the run DSL, skip)

- Ruby's `config.rb` re-adding `mud_host`/`mud_port`/`mud_username`/`mud_password` — Python's `config.py` never removed these, so there's nothing to re-add.
- Ruby's `context.rb` whitespace/alignment diff and missing trailing newline — no behavioral change; Python's `context.py` is untouched.
- Ruby's `agent.rb` — zero-line diff against 06; Python's `agent.py` is untouched.
