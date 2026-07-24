# Python Port: Boukensha The Logger (06_the_logger)

**Status**: Planning — This document defines the port plan for `week1_baseline/ruby/06_the_logger/` to Python.

`Boukensha::Logger` records each agent run as structured JSON Lines — one file per session under `.boukensha/sessions/<session-id>.jsonl`. It is a *file* logger, not user-facing display output: each line is a complete JSON object with `session_id`, `at`, and a `phase` field, plus phase-specific data (iteration counters, prompts, tool calls/results, model responses with token usage and estimated cost, and optional raw provider payloads when debug mode is on).

This step does **not** change the agent's control flow — `Agent#run` still loops the same way. It only wires a `Logger` instance through the loop so every phase of a turn gets recorded, and adds a small module-level state surface (`Boukensha.quiet!`, `Boukensha.debug!`, `Boukensha.config`) that the Logger and future steps can read.

## Decisions

These decisions build on 00_config through 05_agent_loop:

- **`Logger` is a new class, not a backend concern**: Lives in `src/boukensha/logger.py`. It only reads data handed to it by `Agent` — it never talks to the network or a backend directly (beyond duck-typed `backend.model` / `backend.usage_unit` / `backend.usage_level` / `backend.estimate_cost` attribute reads, all of which already exist on `BackendBase`, unchanged since 05_agent_loop).

- **`Agent` gains a `logger` parameter, default `Logger()`**: Ruby's `Agent#initialize` defaults `logger: Logger.new`. The Python port mirrors this with a default factory (Python can't use a mutable/side-effecting default argument directly, so the default is constructed per-call — see implementation note below).

- **Every phase of the loop gets a corresponding logger call**: `iteration`, `prompt`, `raw` (before parsing), `tool_call`/`tool_result` (now wrapped in error handling — tool exceptions are caught, logged, and turned into an `ERROR: ...` tool_result instead of crashing the agent), `response` (on both normal completion and wind-down), `turn_end`, and `limit_reached`.

- **Tool dispatch failures no longer crash the agent**: Ruby's `handle_tool_calls` now rescues `StandardError` around `@registry.dispatch`, logs `tool_result(ok: false, error: ...)`, and feeds `"ERROR: <class>: <message>"` back to the model as the tool result instead of propagating. The Python port mirrors this with `except Exception as e`.

- **Module-level state on the `boukensha` package**: Ruby's `Boukensha` module gains `@quiet`, `@debug`, `@config` class-level state and `self.config`, `self.quiet!`, `self.loud!`, `self.quiet?`, `self.debug!`, `self.debug?`. Python doesn't have `!`-suffixed methods, so the port uses plain verb/query names in a new `src/boukensha/state.py` module, re-exported from `__init__.py`:
  - `Boukensha.config` → `boukensha.config()` (memoized `Config()` instance)
  - `Boukensha.quiet!` → `boukensha.quiet()`
  - `Boukensha.loud!` → `boukensha.loud()`
  - `Boukensha.quiet?` → `boukensha.is_quiet()`
  - `Boukensha.debug!` → `boukensha.debug()`
  - `Boukensha.debug?` → `boukensha.is_debug()`

  `Logger._default_dir()` reads `boukensha.config().dir`; `Logger.raw()` checks `boukensha.is_debug()` before writing.

  **Note on module placement**: the reference plan extends `boukensha/__init__.py` directly with these functions rather than a separate `state.py` module, and flags that doing so requires careful import ordering to avoid a circular import (`__init__.py` would import `Logger`, and `Logger` needs to call back into `__init__.py` for `config()`/`is_debug()`). This port sidesteps that risk entirely by keeping the six functions in their own `state.py` module with no dependency on `logger.py` or `agent.py` — `logger.py` does `from . import state` and calls `state.is_debug()`/`state.config()`, `__init__.py` re-exports the same six names for the public `boukensha.config()` / `boukensha.debug()` call sites. Same public API, no ordering hazard.

  **`quiet()`/`loud()`/`is_quiet()` are plumbing only in this step**: nothing in `Logger` or `Agent` reads `is_quiet()` yet (mirroring Ruby, where `quiet?` exists on the module but isn't consumed until a later step). Don't invent console-output-suppression behavior around it — just carry the flag.

- **`LoopError` is removed**: Ruby's `errors.rb` drops `LoopError` in this step (it was added in 05 for "future use" but never raised — wind-down handles the runaway case instead). The Python port removes it from `errors.py` and from `__init__.py` exports to match.

- **`config.rb`'s MUD-connection helpers (`mud_host`, `mud_port`, `mud_username`, `mud_password`) are removed in Ruby 06, but this is unrelated cleanup, not a logger feature.** The Python `config.py` already carries the equivalent `mud_host`/`mud_port`/`mud_username`/`mud_password` properties from earlier steps; leave them as-is — this port only carries over changes that are part of the logger feature.

- **`context.rb`'s diff in Ruby 06 is whitespace/alignment only** (no behavioral change). The Python `context.py` needs no changes — it already exposes `.messages` and `.tools`, which is all `Logger.prompt()` needs.

- **`prompt_builder.rb` gains `attr_reader :backend`** in Ruby 06 so `Agent` can pass `@builder.backend` into `log_response`. The Python `PromptBuilder` already assigns `self.backend = backend` as a plain public attribute (done in an earlier step) — no change needed.

## Target Python Structure (as planned)

```
week1_baseline/python/06_the_logger/
├── src/
│   └── boukensha/
│       ├── __init__.py              # Package exports (modify: drop LoopError, add state re-exports)
│       ├── state.py                 # Module-level quiet/debug/config state (NEW)
│       ├── logger.py                # Logger class (NEW)
│       ├── agent.py                 # Agent class (modify: logger param + calls, tool-error handling)
│       ├── client.py                # Client class (copy, unchanged)
│       ├── config.py                # Config class (copy, unchanged)
│       ├── tool.py                  # Tool dataclass (copy, unchanged)
│       ├── message.py               # Message dataclass (copy, unchanged)
│       ├── context.py               # Context class (copy, unchanged)
│       ├── errors.py                # Remove LoopError
│       ├── registry.py              # Registry class (copy, unchanged)
│       ├── prompt_builder.py        # PromptBuilder class (copy, unchanged)
│       ├── tasks/                   # (copy, unchanged)
│       └── backends/                # (copy, unchanged — model metadata already present since 05)
├── examples/
│   └── example.py                   # Wire a Logger into the Agent (modify)
├── prompts/
│   └── system.md                    # (copy, unchanged)
├── pyproject.toml                   # Package config (copy, bump version to 0.6.0)
└── README.md                        # Usage documentation (NEW content, ported from Ruby README)
```

### Already Ported (from 05_agent_loop, unchanged)
- **config.py**, **tool.py**, **message.py**, **context.py**, **registry.py**, **client.py**, **prompt_builder.py**
- **tasks/base.py**, **tasks/player.py**
- **backends/base.py**, **backends/anthropic.py**, **backends/gemini.py**, **backends/ollama.py**, **backends/ollama_cloud.py**, **backends/openai.py**
- **prompts/system.md**

### New in This Step
- **state.py**: `config()`, `quiet()`, `loud()`, `is_quiet()`, `debug()`, `is_debug()`
- **logger.py**: `Logger` class

### Modified in This Step
- **agent.py**: Add `logger` parameter (default `Logger()`); log every phase; catch tool-dispatch exceptions
- **errors.py**: Remove `LoopError`
- **__init__.py**: Drop `LoopError` export; export `Logger` and the `state` functions
- **examples/example.py**: Construct a `Logger` and pass it into `Agent`; update banner text to "Step 6: The Logger"

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
```

### 2. Install 06_the_logger
```bash
pip install -e week1_baseline/python/06_the_logger
```

### 3. Run it
```bash
./week1_baseline/bin/python/06_the_logger
```

---

## Porting Plan: File by File

### 1. Copy Prior Step as Template

```bash
cp -r week1_baseline/python/05_agent_loop week1_baseline/python/06_the_logger
```

---

### 2. Module State (`lib/boukensha.rb` module methods → `src/boukensha/state.py`)

**Ruby** (from `lib/boukensha.rb`):
```ruby
module Boukensha
  @quiet  = false
  @debug  = false
  @config = nil

  def self.config
    @config ||= Config.new
  end

  def self.quiet!
    @quiet = true
  end

  def self.loud!
    @quiet = false
  end

  def self.quiet?
    @quiet
  end

  def self.debug!
    @debug = true
  end

  def self.debug?
    @debug
  end
end
```

**Python** (`src/boukensha/state.py`, new file):
```python
from typing import Optional

from .config import Config

_quiet = False
_debug = False
_config: Optional[Config] = None


def config() -> Config:
    """Memoized default Config instance."""
    global _config
    if _config is None:
        _config = Config()
    return _config


def quiet() -> None:
    global _quiet
    _quiet = True


def loud() -> None:
    global _quiet
    _quiet = False


def is_quiet() -> bool:
    return _quiet


def debug() -> None:
    global _debug
    _debug = True


def is_debug() -> bool:
    return _debug
```

**Key translation notes**:
- Ruby class-level `@ivar` on a module → Python module-level globals (a module is already a singleton, so this is the natural equivalent).
- `@config ||= Config.new` → `if _config is None: _config = Config()`.
- `self.quiet!` / `self.debug!` (mutator, no return value used) → `quiet()` / `debug()` (plain functions since Python has no `!` naming convention).
- `self.quiet?` / `self.debug?` → `is_quiet()` / `is_debug()` (Python has no `?` naming convention either).

---

### 3. Errors — Remove `LoopError` (`lib/boukensha/errors.rb` → `src/boukensha/errors.py`)

**Ruby**:
```ruby
module Boukensha
  class UnknownToolError < StandardError; end
  class ApiError         < StandardError; end
  class UnsupportedModelError < StandardError; end
end
```

**Python** (remove `LoopError` from existing `errors.py`):
```python
class UnknownToolError(Exception):
    """Raised when dispatch() is called with an unknown tool name."""
    pass


class UnsupportedModelError(Exception):
    """Raised when a backend is initialized with an unsupported model."""
    pass


class ApiError(Exception):
    """Raised when an API request fails after retries are exhausted."""
    pass
```

---

### 4. Logger (`lib/boukensha/logger.rb` → `src/boukensha/logger.py`)

**Ruby** (full file, 143 lines) — see `week1_baseline/ruby/06_the_logger/lib/boukensha/logger.rb` for the source. Key responsibilities:
- Generates a session id (`YYYYmmddTHHMMSSZ-<8 hex chars>`) unless one is passed in.
- Opens `<dir>/<session_id>.jsonl` in append mode (or an explicit `log:` path), creating parent directories.
- Writes a `session_start` line immediately, merging in an optional `snapshot` hash.
- One method per phase: `iteration`, `limit_reached`, `turn_end`, `prompt`, `tool_call`, `tool_result`, `response`, `raw`, plus `close`.
- `response` computes execution metadata (task name, provider, model, usage_unit/usage_level, normalized input/output token counts, estimated USD cost) and merges non-nil fields in.
- `raw` is a no-op unless `Boukensha.debug?` is true.
- `provider_name` derives a snake_case provider tag from the backend's Ruby class name (e.g. `Boukensha::Backends::OllamaCloud` → `ollama_cloud`) via a regex; Python derives it from `backend.__class__.__name__` the same way.

**Python** (`src/boukensha/logger.py`):
```python
import json
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import state

DEFAULT_SESSION_DIR = "sessions"


class Logger:
    """Records each agent run as structured JSON Lines under .boukensha/sessions/."""

    def __init__(
        self,
        session_id: Optional[str] = None,
        dir: Optional[str] = None,
        log: Optional[str] = None,
        snapshot: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.session_id = session_id or self._generate_session_id()
        self.path = Path(log) if log else Path(dir or self._default_dir()) / f"{self.session_id}.jsonl"

        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._log_file = open(self.path, "a")
        self._write_log({"phase": "session_start", **(snapshot or {})})

    def iteration(self, n: int, max: int) -> None:
        self._write_log({"phase": "iteration", "n": n, "max": max})

    def limit_reached(self, kind: str, n: int, max: int) -> None:
        self._write_log({"phase": "limit_reached", "kind": kind, "n": n, "max": max})

    def turn_end(self, reason: str, iterations: int, tokens: Optional[int] = None) -> None:
        self._write_log({
            "phase": "turn_end",
            "reason": reason,
            "iterations": iterations,
            "tokens": tokens,
        })

    def prompt(self, messages: List[Any], tools: Dict[str, Any]) -> None:
        self._write_log({
            "phase": "prompt",
            "message_count": len(messages),
            "messages": [self._serialize_message(m) for m in messages],
            "tool_count": len(tools),
            "tools": list(tools.keys()),
        })

    def tool_call(self, name: str, args: Dict[str, Any]) -> None:
        self._write_log({"phase": "tool_call", "name": name, "args": args})

    def tool_result(
        self, name: str, result: Any, ok: bool = True, error: Optional[str] = None
    ) -> None:
        self._write_log({
            "phase": "tool_result",
            "name": name,
            "result": str(result),
            "ok": ok,
            "error": error,
        })

    def response(
        self,
        text: str,
        usage: Optional[Dict[str, Any]] = None,
        stop_reason: Optional[str] = None,
        task: Optional[Any] = None,
        backend: Optional[Any] = None,
    ) -> None:
        event: Dict[str, Any] = {
            "phase": "response",
            "text": str(text).strip(),
            "usage": usage,
            "stop_reason": stop_reason,
        }
        event.update(self._execution_metadata(task=task, backend=backend, usage=usage))
        self._write_log(event)

    def raw(self, data: Any) -> None:
        if not state.is_debug():
            return
        self._write_log({"phase": "raw", "data": data})

    def close(self) -> None:
        if self._log_file:
            self._log_file.close()

    def __enter__(self) -> "Logger":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _default_dir(self) -> Path:
        return Path(state.config().dir) / DEFAULT_SESSION_DIR

    def _write_log(self, event: Dict[str, Any]) -> None:
        record = {
            **event,
            "session_id": self.session_id,
            "at": datetime.now().astimezone().isoformat(),
        }
        self._log_file.write(json.dumps(record, default=str) + "\n")
        self._log_file.flush()

    @staticmethod
    def _generate_session_id() -> str:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        return f"{ts}-{secrets.token_hex(4)}"

    @staticmethod
    def _serialize_message(msg: Any) -> Dict[str, Any]:
        return {"role": msg.role, "content": msg.content}

    def _execution_metadata(
        self, task: Optional[Any], backend: Optional[Any], usage: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        if not (task or backend or usage):
            return {}

        tokens = self._usage_tokens(usage)
        metadata = {
            "task": self._task_name(task),
            "provider": self._provider_name(backend),
            "model": getattr(backend, "model", None),
            "usage_unit": getattr(backend, "usage_unit", None),
            "usage_level": getattr(backend, "usage_level", None),
            "input_tokens": tokens.get("input"),
            "output_tokens": tokens.get("output"),
            "cost_usd": self._estimate_cost(backend, tokens),
        }
        return {k: v for k, v in metadata.items() if v is not None}

    @staticmethod
    def _task_name(task: Optional[Any]) -> Optional[str]:
        if task is None:
            return None
        task_name_attr = getattr(task, "task_name", None)
        return task_name_attr() if callable(task_name_attr) else str(task)

    @staticmethod
    def _provider_name(backend: Optional[Any]) -> Optional[str]:
        if backend is None:
            return None
        name = backend.__class__.__name__
        return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name).lower()

    def _usage_tokens(self, usage: Optional[Dict[str, Any]]) -> Dict[str, Optional[int]]:
        usage = usage or {}
        return {
            "input": self._first_integer(
                usage, "input_tokens", "prompt_tokens", "promptTokenCount", "prompt_eval_count"
            ),
            "output": self._first_integer(
                usage, "output_tokens", "completion_tokens", "candidatesTokenCount", "eval_count"
            ),
        }

    @staticmethod
    def _first_integer(d: Dict[str, Any], *keys: str) -> Optional[int]:
        for key in keys:
            value = d.get(key)
            if value is not None:
                try:
                    return int(value)
                except (TypeError, ValueError):
                    return None
        return None

    @staticmethod
    def _estimate_cost(backend: Optional[Any], tokens: Dict[str, Optional[int]]) -> Optional[float]:
        if backend is None or not hasattr(backend, "estimate_cost"):
            return None
        if tokens.get("input") is None or tokens.get("output") is None:
            return None
        return backend.estimate_cost(input_tokens=tokens["input"], output_tokens=tokens["output"])
```

**Key translation notes**:
- `SecureRandom.hex(4)` (4 random bytes → 8 hex chars) → `secrets.token_hex(4)`, **not** `uuid.uuid4().hex[:8]`. `secrets` is the stdlib module purpose-built as SecureRandom's counterpart (cryptographically strong, arbitrary byte count); truncating a UUID4 instead would work but throws away structure (some bits are fixed version/variant bits, not full entropy) for no benefit here.
- `Time.now.iso8601` → `datetime.now().astimezone().isoformat()` (includes UTC offset like Ruby's `iso8601`).
- `FileUtils.mkdir_p(File.dirname(@path))` → `self.path.parent.mkdir(parents=True, exist_ok=True)`.
- `JSON.generate(event.merge(...))` → `json.dumps({**event, ...}, default=str)`. The `default=str` fallback matters even though every phase method already stringifies obviously-risky values (`tool_result`'s `result`) — `tool_call`'s `args` and `raw`'s `data` are passed through as-is (dicts from `**kwargs`/parsed JSON), and a `default=str` safety net means an unexpected non-serializable value degrades to its `str()` representation instead of crashing the whole agent run mid-loop. It has no effect on ordinary dict/list/str/number payloads — only kicks in for otherwise-unserializable types.
- `hash[key] || hash[key.to_sym]` (Ruby dual string/symbol lookup) → not needed in Python; dict keys here are always strings, so `d.get(key)` is sufficient — drop the symbol fallback branch.
- `backend&.respond_to?(:usage_unit) ? backend.usage_unit : nil` → `getattr(backend, "usage_unit", None)`.
- `metadata.compact` (drops nil values) → dict comprehension filtering `v is not None`. Note this filtering applies only to the *execution metadata* sub-dict (`task`/`provider`/`model`/`usage_unit`/`usage_level`/`input_tokens`/`output_tokens`/`cost_usd`) — the base `response` event's `usage` and `stop_reason` fields are written even when `None`, matching Ruby's explicit JSON `null` for those two fields.
- Ruby's `gsub(/([a-z\d])([A-Z])/, '\1_\2')` snake-cases only at lower→upper boundaries; the Python regex uses a lookbehind/lookahead to insert `_` at the same boundary without consuming characters — same result (`OllamaCloud` → `Ollama_Cloud` → lowered → `ollama_cloud`).
- `require "json"`, `require "fileutils"`, `require "securerandom"`, `require "time"` → standard `json`, `pathlib`, `secrets`, `datetime` imports (all stdlib, no new dependency).
- `close` is not explicitly called anywhere in Ruby's `agent.rb`/`example.rb`, so the Python port doesn't need to call it either — added `__enter__`/`__exit__` as an optional convenience for callers who want `with Logger() as logger:`, purely additive and not part of the Ruby-visible contract.

---

### 5. Agent — Wire in the Logger (`lib/boukensha/agent.rb` → `src/boukensha/agent.py`)

**Ruby** (diff against 05, see conversation above for full diff). Summary of behavioral changes:
1. `initialize` gains `logger: Logger.new` and stores `@logger`.
2. In `run`, before returning from the iteration-limit branch: `@logger.limit_reached(kind: "max_iterations", n: @iteration, max: @max_iterations)`.
3. After incrementing `@iteration`: `@logger.iteration(...)` replaces the old `puts`, and a new `@logger.prompt(messages: @context.messages, tools: @context.tools)` call is added.
4. After the API call: `@logger.raw(data: response)`.
5. On `end_turn`: `log_response(text:, response:)` then `@logger.turn_end(reason: "completed", iterations: @iteration)` before returning.
6. `handle_tool_calls` now takes `response` as a second argument (needed for `log_response`), logs the reasoning text (or a placeholder like `"(tool use — 2 calls)"` when there's no text), and wraps `@registry.dispatch` in a `rescue StandardError` that logs `tool_result(ok: false, error: ...)` and turns the exception into an `"ERROR: <class>: <message>"` string fed back as the tool result instead of crashing.
7. `wrap_up` logs the response and `turn_end` on both the success path and the `rescue ApiError` fallback path.
8. New private helpers `log_response` and `normalized_usage` — the latter checks `response["usage"]` (OpenAI/Anthropic shape), falls back to `response["usageMetadata"]` (Gemini shape), then falls back to flat `prompt_eval_count`/`eval_count` keys (Ollama shape).

**Python** (`src/boukensha/agent.py`, modify existing file):
```python
from typing import Any, Dict, List, Optional

from .client import Client
from .context import Context
from .errors import ApiError
from .logger import Logger
from .prompt_builder import PromptBuilder
from .registry import Registry


class Agent:
    """The agent loop — sends requests, dispatches tools, and knows when to stop."""

    MAX_ITERATIONS = 25
    WRAP_UP_OUTPUT_TOKENS = 400
    WRAP_UP_DIRECTIVE = (
        "You have reached your action limit for this turn. Do not call any more tools. "
        "Briefly summarize what you accomplished, what is still unfinished, and the "
        "single next action you would take."
    )

    def __init__(
        self,
        context: Context,
        registry: Registry,
        builder: PromptBuilder,
        client: Client,
        logger: Optional[Logger] = None,
        task_settings: Optional[Dict[str, Any]] = None,
        max_iterations: Optional[int] = None,
        max_output_tokens: Optional[int] = None,
    ) -> None:
        self.context = context
        self.registry = registry
        self.builder = builder
        self.client = client
        self.logger = logger if logger is not None else Logger()
        self.max_iterations = self._resolve_max_iterations(task_settings, max_iterations)
        self.max_output_tokens = self._resolve_max_output_tokens(task_settings, max_output_tokens)
        self.iteration = 0

    def run(self) -> str:
        """Start the loop and return the final text response when the agent is done."""
        while True:
            if self._iteration_limit_reached():
                self.logger.limit_reached(
                    kind="max_iterations", n=self.iteration, max=self.max_iterations
                )
                return self._wrap_up("max_iterations")

            self.iteration += 1
            self.logger.iteration(n=self.iteration, max=self.max_iterations)
            self.logger.prompt(messages=self.context.messages, tools=self.context.tools)

            response = self.client.call(**self._call_opts())
            self.logger.raw(data=response)
            parsed = self.builder.parse_response(response)

            if parsed["stop_reason"] == "tool_use":
                self._handle_tool_calls(parsed["content"], response)
            else:
                text = self._extract_text(parsed["content"])
                self._log_response(text=text, response=response)
                self.logger.turn_end(reason="completed", iterations=self.iteration)
                return text

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _resolve_max_iterations(
        self,
        task_settings: Optional[Dict[str, Any]],
        explicit: Optional[int],
    ) -> int:
        if explicit is not None:
            return int(explicit)
        if task_settings and self.context.task is not None:
            try:
                return self.context.task.max_iterations(task_settings)
            except (AttributeError, TypeError):
                pass
        return self.MAX_ITERATIONS

    def _resolve_max_output_tokens(
        self,
        task_settings: Optional[Dict[str, Any]],
        explicit: Optional[int],
    ) -> Optional[int]:
        if explicit is not None:
            return explicit
        if task_settings and self.context.task is not None:
            try:
                return self.context.task.max_output_tokens(task_settings)
            except (AttributeError, TypeError):
                pass
        return None

    def _iteration_limit_reached(self) -> bool:
        return self.max_iterations > 0 and self.iteration >= self.max_iterations

    def _call_opts(self) -> Dict[str, Any]:
        opts: Dict[str, Any] = {}
        if self.max_output_tokens is not None:
            opts["max_output_tokens"] = self.max_output_tokens
        return opts

    def _wrap_up(self, reason: str) -> str:
        """One final, tools-disabled model call so the agent ends gracefully."""
        self.context.add_message("user", self.WRAP_UP_DIRECTIVE)
        try:
            response = self.client.call(
                tools=[],
                max_output_tokens=self.WRAP_UP_OUTPUT_TOKENS,
            )
            text = self._extract_text(
                self.builder.parse_response(response)["content"]
            )
            if not text.strip():
                text = self._fallback_message(reason)
            self._log_response(text=text, response=response)
            self.logger.turn_end(reason=reason, iterations=self.iteration)
            return text
        except ApiError:
            msg = self._fallback_message(reason)
            self.logger.turn_end(reason=reason, iterations=self.iteration)
            return msg

    def _fallback_message(self, reason: str) -> str:
        return (
            f"I reached my {self.max_iterations}-action limit for this turn before finishing "
            f"({reason}). Ask me to continue and I'll pick up from here."
        )

    @staticmethod
    def _extract_text(content: List[Dict[str, Any]]) -> str:
        return "".join(
            block["text"] for block in content if block.get("type") == "text"
        )

    def _handle_tool_calls(self, content: List[Dict[str, Any]], response: Dict[str, Any]) -> None:
        """Log reasoning, store the assistant message, then dispatch each tool call."""
        tool_calls = [b for b in content if b.get("type") == "tool_use"]

        reasoning = self._extract_text(content)
        placeholder = f"(tool use — {len(tool_calls)} call{'s' if len(tool_calls) != 1 else ''})"
        self._log_response(
            text=reasoning if reasoning.strip() else placeholder, response=response
        )

        self.context.add_message("assistant", content)

        for block in tool_calls:
            name = block["name"]
            args = block["input"]
            use_id = block["id"]

            self.logger.tool_call(name=name, args=args)
            try:
                result = self.registry.dispatch(name, args)
                self.logger.tool_result(name=name, result=result, ok=True)
            except Exception as e:
                result = f"ERROR: {type(e).__name__}: {e}"
                self.logger.tool_result(name=name, result=result, ok=False, error=str(e))

            self.context.add_message("tool_result", str(result), tool_use_id=use_id)

    def _log_response(self, text: str, response: Dict[str, Any]) -> None:
        self.logger.response(
            text=text,
            usage=self._normalized_usage(response),
            stop_reason=response.get("stop_reason"),
            task=self.context.task,
            backend=self.builder.backend,
        )

    @staticmethod
    def _normalized_usage(response: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if response.get("usage"):
            return response["usage"]
        if response.get("usageMetadata"):
            return response["usageMetadata"]

        usage = {}
        for key in ("prompt_eval_count", "eval_count"):
            if key in response:
                usage[key] = response[key]
        return usage or None
```

**Key translation notes**:
- `logger: Logger.new` as a Ruby keyword default (evaluated once per call, giving each `Agent` its own `Logger` instance) → Python can't put a side-effecting call directly in the signature default, so use `logger: Optional[Logger] = None` and `self.logger = logger if logger is not None else Logger()` in the body. This preserves "one fresh Logger per Agent unless one is passed in."
- `rescue StandardError => e` → `except Exception as e` (broad catch, matching Ruby's `StandardError` scope — not `BaseException`).
- `e.class` / `e.message` → `type(e).__name__` / `str(e)`.
- `"#{'s' if tool_calls.size != 1}"` → Python ternary-in-fstring: `'s' if len(tool_calls) != 1 else ''`.
- `response["stop_reason"]` (used generically in `normalized_usage`/`log_response`, distinct from the *normalized* `parsed["stop_reason"]`) reads the **raw** provider response, which may not have this key for every backend — use `.get()`, not `[]`.

---

### 6. Package Exports (`lib/boukensha.rb` → `src/boukensha/__init__.py`)

**Python** (modify existing file):
```python
# Boukensha agent loop — backends, tasks, registry, builder, client, agent, and logger
# Re-uses config, struct, registry, prompt builder, and client classes from prior steps

# Local struct, config, and registry classes
from .config import Config  # noqa: F401
from .tool import Tool  # noqa: F401
from .message import Message  # noqa: F401
from .context import Context  # noqa: F401
from .errors import UnknownToolError, UnsupportedModelError, ApiError  # noqa: F401
from .registry import Registry  # noqa: F401

# From prior step (03_prompt_builder)
from .prompt_builder import PromptBuilder  # noqa: F401
from . import tasks  # noqa: F401
from . import backends  # noqa: F401

# From prior step (04_api_client)
from .client import Client  # noqa: F401

# From prior step (05_agent_loop)
from .agent import Agent  # noqa: F401

# New in this step (06_the_logger)
from .logger import Logger  # noqa: F401
from .state import config, quiet, loud, is_quiet, debug, is_debug  # noqa: F401

__all__ = [
    "Config",
    "Tool",
    "Message",
    "Context",
    "Registry",
    "UnknownToolError",
    "UnsupportedModelError",
    "ApiError",
    "PromptBuilder",
    "Client",
    "Agent",
    "Logger",
    "config",
    "quiet",
    "loud",
    "is_quiet",
    "debug",
    "is_debug",
    "tasks",
    "backends",
]
```

**Change**: Remove `LoopError` (import and `__all__` entry). Add `Logger` and the six `state` functions.

**Note — naming collision**: `Config` (the class) and `config` (the state accessor function) both live in `boukensha`'s top-level namespace with different case. This mirrors Ruby's `Boukensha::Config` (class, `CamelCase`) vs. `Boukensha.config` (method, `snake_case`) — Python's case-sensitive namespace makes the same split unambiguous (`boukensha.Config` vs `boukensha.config()`).

---

### 7. Example (`examples/example.rb` → `examples/example.py`)

**Ruby** (diff against 05 — see conversation above). Changes: constructs `logger = Boukensha::Logger.new` and passes `logger:` into `Agent.new`; updates the banner from "Step 5: Agent Loop" to "Step 6: The Logger"; adds a comment explaining what the logger writes.

**Python** (modify existing `examples/example.py`):
```python
import os
from pathlib import Path

from boukensha import Config, Context, PromptBuilder, Client, Registry, Agent, Logger
from boukensha.tasks import Player
from boukensha.backends import Anthropic, Gemini, Ollama, OllamaCloud, OpenAI

os.environ.setdefault(
    "BOUKENSHA_DIR",
    str(Path(__file__).resolve().parent.parent.parent / ".boukensha"),
)

config = Config()
player_settings = config.tasks("player") or {}

system_prompt = Player.system_prompt(
    player_settings,
    user_prompts_dir=config.user_prompts_dir,
    default_prompts_dir=Config.PROMPTS_DIR,
)

base_dir = Path(__file__).resolve().parent.parent

ctx = Context(task=Player, system=system_prompt)
registry = Registry(ctx)

provider = Player.provider(player_settings)
model = Player.model(player_settings)

if provider == "anthropic":
    backend = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"], model=model)
elif provider == "openai":
    backend = OpenAI(api_key=os.environ["OPENAI_API_KEY"], model=model)
elif provider == "gemini":
    backend = Gemini(api_key=os.environ["GEMINI_API_KEY"], model=model)
elif provider == "ollama":
    backend = Ollama(model=model)
elif provider == "ollama_cloud":
    backend = OllamaCloud(api_key=os.environ["OLLAMA_API_KEY"], model=model)
else:
    raise ValueError(f"Unsupported provider for player task: {provider}")

builder = PromptBuilder(ctx, backend)
client = Client(builder)
# Writes structured JSONL events to .boukensha/sessions/<session-id>.jsonl.
# Call boukensha.debug() before running the agent to include the full raw
# API response in those lines.
logger = Logger()
agent = Agent(
    context=ctx,
    registry=registry,
    builder=builder,
    client=client,
    logger=logger,
    task_settings=player_settings,
)

registry.tool(
    "read_file",
    description="Read the contents of a file from disk",
    parameters={"path": {"type": "string", "description": "The file path to read"}},
    block=lambda path: (base_dir / path).read_text(),
)

registry.tool(
    "list_directory",
    description="List the files in a directory",
    parameters={"path": {"type": "string", "description": "The directory path to list"}},
    block=lambda path: ", ".join(
        f for f in os.listdir(str(base_dir / path)) if not f.startswith(".")
    ),
)

ctx.add_message("user", "Read the README.md file and summarise what this MUD player assistant framework can do.")

print("=== BOUKENSHA Step 6: The Logger ===")
print()
print(f"Config: {config}")
print(f"Provider: {provider}")
print(f"Model: {model}")
print(f"Max iterations: {Player.max_iterations(player_settings)}")
print(f"Max output tokens: {Player.max_output_tokens(player_settings)}")
print()

result = agent.run()

print()
print("=== FINAL RESPONSE ===")
print(result)
```

---

### 8. Update pyproject.toml

Bump version from `0.5.0` to `0.6.0`:
```toml
[project]
name = "boukensha"
version = "0.6.0"
description = "Boukensha logger — records each agent run as structured JSON Lines"
# ... rest unchanged
```

---

### 9. Update README.md

Replace the step 5 README with step 6 content, ported from the Ruby `README.md`. Key sections:

- **Session Logs**: where `.jsonl` files land and the line-per-event shape
- **Logger API**: table of methods (`iteration`, `prompt`, `tool_call`, `tool_result`, `response`, `raw`) and what each logs
- **Task Configuration**: same `tasks.player` YAML shape carried over from step 5
- **Default usage**: `logger = Logger()`, `agent = Agent(..., logger=logger)`
- **Custom session id / directory**: `Logger(session_id="manual-session")`, `Logger(dir="/tmp/boukensha-sessions")`
- **Debug Events**: `boukensha.debug()` before running the agent to include raw provider responses in the log
- **Run Example**: `./week1_baseline/bin/python/06_the_logger`

---

## Dependency Chain

```
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

Prefer fake/stub `client` and `backend` objects over real API calls for all `Agent`-level tests — the loop only ever calls `client.call(...)` and `builder.parse_response(...)`, both easy to stub, so verification of steps 6–9 below should run fully offline with no API keys.

### Unit-level verification (as you build):
1. **Import surface**: `from boukensha import Logger, config, quiet, loud, is_quiet, debug, is_debug, Agent` succeeds; `from boukensha import LoopError` now fails (removed, and confirmed unused anywhere else in the tree — `grep -r LoopError week1_baseline` returns nothing outside this plan).
2. **State module**: `config()` returns the same `Config` instance on repeated calls (memoized); `quiet()`/`loud()` flip `is_quiet()`; `debug()` flips `is_debug()` and stays flipped (no un-set method, matching Ruby — there's no `undebug!`). Both flags default to `False`.
3. **Logger init — fixed inputs**: construct with an explicit `session_id`, `dir` (a temp directory), and `snapshot`; assert the file is created at the expected path, `session_start` is the first line and is valid JSON, and every subsequent line carries the same `session_id` and a parseable ISO-8601 `at` timestamp.
4. **Logger init — path precedence**: verify an explicit `log` path wins over `dir`; verify the default (`dir`/`log` both omitted) resolves under `state.config().dir / "sessions"`; verify the generated session id matches `YYYYMMDDTHHMMSSZ-<8 lowercase hex chars>`.
5. **Every phase method**: call each of `iteration`, `limit_reached`, `turn_end`, `prompt`, `tool_call`, `tool_result`, `response`, `raw` (with debug on) directly against a `Logger` pointed at a temp file; assert the exact field set per line, that `prompt()` serializes messages as `{"role", "content"}` pairs (no `tool_use_id`), that `tool_result()` stringifies its `result`, and that calling `close()` twice doesn't raise.
6. **`response()` usage normalization**: feed sample usage dicts shaped like each of Anthropic (`input_tokens`/`output_tokens`), OpenAI (`prompt_tokens`/`completion_tokens`), Gemini (`promptTokenCount`/`candidatesTokenCount`), and Ollama (`prompt_eval_count`/`eval_count`); assert normalized `input_tokens`/`output_tokens` in the logged execution metadata, correct snake_case `provider`, and `cost_usd` present only when a fake backend exposes `estimate_cost` and both counts are available (omitted otherwise).
7. **`raw()` gating**: verify it writes nothing while `is_debug()` is False, and writes a `raw` line immediately after calling `debug()` — even for a `Logger` instance created before `debug()` was called (state is read live at call time, not captured at construction).
8. **Agent + tool error handling**: build an `Agent` with a fake `client`/`registry` where one registered tool raises; run one iteration and assert `run()` does not crash, the tool_result fed back to the model is `"ERROR: <ExceptionClass>: <message>"`, `logger.tool_result(ok=False, error=...)` was called, and the loop continues to the next iteration normally.
9. **Agent event ordering**: with a fake client that returns one tool-use response then one end-turn response, assert the exact event sequence — `iteration` → `prompt` → `raw` → `response` (reasoning/placeholder text) → assistant message appended → `tool_call`/`tool_result` pairs → next `iteration` → ... → final `response` → `turn_end(reason="completed")`.
10. **Wind-down paths**: force `max_iterations` down to a small number and cover three cases — (a) successful wind-down call with non-blank text, (b) wind-down call returns blank text (falls back to `_fallback_message`), (c) wind-down call raises `ApiError` (also falls back). Assert exactly one `limit_reached`, exactly one terminal request, a `response` log in cases (a)/(b) but not (c) (no provider response to describe), and exactly one `turn_end` in all three.
11. **Agent default logger**: construct two `Agent` instances without passing `logger`; verify they get distinct `Logger` instances writing to distinct files (not a shared singleton).
12. **Launcher smoke test**: run `week1_baseline/bin/python/06_the_logger` far enough to validate its path/import setup without making a network call (e.g. `python -c "import boukensha"` from the launcher's environment, or exercise it against a stub provider); only exercise a real provider when credentials or a local Ollama instance are intentionally available.

### Full integration test (requires provider credentials):
```bash
source venv/bin/activate
pip install -e week1_baseline/python/06_the_logger
./week1_baseline/bin/python/06_the_logger
cat ~/.boukensha/sessions/*.jsonl | tail -5   # inspect the newest session log
```

## Acceptance Criteria

- Creating an `Agent` without a `logger` argument automatically creates a session JSONL log under the configured Boukensha directory.
- Every normal agent path (tool-use iterations, plain completion, wind-down) logs enough ordered events to reconstruct prompts, provider responses, tool execution, limits, and turn completion.
- `response()` normalizes token usage across all five supported backends and computes `cost_usd` whenever model pricing and both token counts are available.
- A raised exception inside a dispatched tool is logged and turned into a tool result fed back to the model — it never crashes `Agent.run()`.
- Raw provider payloads (`raw()`) appear only after `boukensha.debug()` has been called.
- Every log line is valid, self-contained JSON, flushed to disk immediately after being written.
- Step-5 agent behavior is otherwise unchanged — the only user-visible difference is that console `print()` diagnostics for iterations/tool calls are replaced by structured JSONL events (nothing is printed to stdout by the loop itself anymore, aside from the example script's own banner/final-response prints).
- `README.md` and `examples/example.py` describe and demonstrate the step-6 API, and the new launcher starts from the correct directory.

---

## Common Pitfalls

### 1. Mutable/side-effecting default arguments
**Problem**: Ruby's `logger: Logger.new` keyword default is re-evaluated on every call, so each `Agent` gets its own fresh `Logger`. Python evaluates default argument expressions **once**, at function-definition time — `logger: Logger = Logger()` would share a single `Logger` (and a single open file handle) across every `Agent` instance ever constructed.
**Fix**: Use `logger: Optional[Logger] = None`, then `self.logger = logger if logger is not None else Logger()` inside `__init__`.

### 2. `StandardError` vs bare `except`
**Problem**: Ruby's `rescue StandardError => e` deliberately excludes things like `SystemExit`/`Interrupt` (those inherit from `Exception`, not `StandardError`). A bare Python `except:` would catch everything, including `KeyboardInterrupt` and `SystemExit`.
**Fix**: Use `except Exception as e:` — Python's `Exception` excludes `BaseException`-only signals like `KeyboardInterrupt`/`SystemExit`, matching Ruby's `StandardError` scope.

### 3. Module-level mutable state and test isolation
**Problem**: `state.py`'s `_quiet`/`_debug`/`_config` globals persist for the lifetime of the Python process. Tests that call `debug()` will leak that state into later tests unless explicitly reset.
**Fix**: If writing automated tests against `state.py`, reset the module globals (or reload the module) between test cases.

### 4. `hash[key] || hash[key.to_sym]` has no Python equivalent needed
**Problem**: Ruby's `first_integer` checks both string and symbol keys because Ruby hashes built from different sources (literals vs `JSON.parse`) may use either. Python dicts from `response.json()` or literals are always string-keyed.
**Fix**: Drop the symbol-fallback branch entirely in the Python port — just `d.get(key)`.

### 5. `response["stop_reason"]` vs `parsed["stop_reason"]`
**Problem**: `_log_response` reads `response.get("stop_reason")` — the **raw**, backend-specific response — not the normalized `parsed["stop_reason"]` computed by `parse_response`. Only Anthropic's raw response actually has a top-level `stop_reason` key; other backends will log `None` here, which matches Ruby's behavior (it also reads straight off the raw hash).
**Fix**: Don't try to "improve" this by using the normalized value — port the Ruby behavior as-is (raw lookup, `None`/`nil` for most non-Anthropic backends is expected and matches the reference implementation).

### 6. snake_case regex boundary
**Problem**: A naive `re.sub(r'([a-z])([A-Z])', r'\1_\2', name)` misses boundaries like `...cloudX` → digit/upper transitions handled by Ruby's `[a-z\d]` character class.
**Fix**: Include `0-9` in the lowercase-side character class: `re.sub(r'(?<=[a-z0-9])(?=[A-Z])', '_', name)` (lookaround avoids consuming characters, so no need to re-add the matched groups).

### 7. `uuid` is the wrong "random hex" primitive
**Problem**: `uuid.uuid4().hex[:8]` looks like an easy stand-in for `SecureRandom.hex(4)`, but a UUID4's hex string has fixed version/variant nibbles baked in near the front — truncating it doesn't give 8 independently-random hex characters, and it pulls in UUID semantics (version, variant) that have nothing to do with what a session-id suffix needs.
**Fix**: Use `secrets.token_hex(4)` — stdlib, no new dependency, and the direct Python counterpart to Ruby's `SecureRandom.hex(4)` (both return `2*n` random hex chars from `n` random bytes).

### 8. Silent JSON serialization failures
**Problem**: `json.dumps(record)` without a fallback raises `TypeError` on the first non-JSON-serializable value anywhere in a nested `tool_call` args dict or `raw` response payload — which would crash the agent loop from inside a logging call, the opposite of what a diagnostic logger should do.
**Fix**: Pass `default=str` to `json.dumps` so unexpected types degrade to their string form instead of raising. This is a safety net, not a behavior change for the normal case — every value Ruby's `JSON.generate` handles natively (dict/list/str/int/float/bool/None) serializes identically either way.

---

## Files to Create/Modify

1. Copy entire `week1_baseline/python/05_agent_loop/` to `week1_baseline/python/06_the_logger/`
2. Create `src/boukensha/state.py` — `config()`, `quiet()`, `loud()`, `is_quiet()`, `debug()`, `is_debug()`
3. Create `src/boukensha/logger.py` — `Logger` class
4. Modify `src/boukensha/errors.py` — remove `LoopError`
5. Modify `src/boukensha/agent.py` — add `logger` param + calls at every phase; catch tool-dispatch exceptions
6. Modify `src/boukensha/__init__.py` — drop `LoopError`; export `Logger` and `state` functions
7. Modify `examples/example.py` — construct and wire in a `Logger`; update banner text
8. Update `pyproject.toml` — version bump to 0.6.0
9. Update `README.md` — replace with Step 6 (Logger) content
10. `week1_baseline/bin/python/06_the_logger` — executable launcher (mirrors 05_agent_loop's launcher)

## Not Ported (unrelated to the logger, skip)

- Ruby's `config.rb` removal of `mud_host`/`mud_port`/`mud_username`/`mud_password` — dead-code cleanup, not part of the logger feature. Python's `config.py` keeps these unchanged.
- Ruby's `context.rb` whitespace realignment — no behavioral change; Python's `context.py` is untouched.
