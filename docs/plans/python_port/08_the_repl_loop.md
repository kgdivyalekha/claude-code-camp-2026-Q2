# Python Port: Boukensha The REPL Loop (08_the_repl_loop)

**Status**: Planning — This document defines the port plan for `week1_baseline/ruby/08_the_repl_loop/` to Python. 

Step 7 gave callers a single-shot `boukensha.run(task=...)`. Step 8 adds an interactive, multi-turn entry point, `boukensha.repl(...)`, that shares the same configuration/provider/limits/logger plumbing but keeps a `Context` alive across many tasks read from stdin, so later turns see earlier user and assistant messages. `run()` is untouched as a public API and keeps working exactly as before.

`week1_baseline/python/08_the_repl_loop/` already exists in the tree as a byte-for-byte copy of the completed `07_the_run_dsl` step (confirmed: its `pyproject.toml` still reads `version = "0.7.0"` and its `__init__.py`/`examples/example.py` are the step-7 files). This plan describes the delta to apply on top of that copy — it does not start from a fresh `cp -r`.

## Decisions

These decisions build on 00_config through 07_the_run_dsl:

- **Conversation history now survives across turns, via two small, additive changes**: `Context` gains `clear_messages()` (empties `self.messages` in place, keeping `task`/`system`/`tools` untouched), and `Agent.run()`/`Agent._wrap_up()` append the final assistant reply to `self.context` on every return path (normal completion, iteration-limit wrap-up, and the `ApiError`-fallback wrap-up path) right before returning. Ruby does this with `@context.add_message(:assistant, text)` in three spots; the Python port mirrors all three. `run()`'s one-shot behavior is unaffected — its private, single-use `Context` now also retains the final reply briefly before being discarded, which is harmless and required for `Agent` to have one implementation shared by both `run()` and `repl()`.

- **`Repl` is a new class in its own module** (`src/boukensha/repl.py`), not folded into `run.py`: it owns the prompt loop, built-in slash commands, banner rendering, and per-turn `Agent` construction. It receives already-constructed shared objects (`context`, `registry`, `builder`, `client`, `logger`, `task_settings`, effective limits, config dir, provider, model, version, api_key) from `repl()` — mirroring how Ruby's `Repl.new(...)` is handed everything `Boukensha.repl` already built, rather than constructing any of it itself.

- **`repl()` is a new module-level function added to `src/boukensha/__init__.py`'s public surface**, following the run-DSL precedent of putting non-trivial orchestration in its own file rather than growing `__init__.py`. Unlike `run()` (which lives in `run.py`), `repl()`'s orchestration is added directly alongside `run()` in `run.py` since it duplicates the bulk of `run()`'s provider/config resolution — see the dedicated note below on avoiding drift between the two. `repl()` takes the same keyword options as `run()` **minus `task`** (replaced by interactive stdin input) and **plus no new ones** — `configure`, `system`, `model`, `backend`, `api_key`, `ollama_host`, `log`, `max_output_tokens` only.

- **A public version constant is introduced**: Ruby adds `lib/boukensha/version.rb` (`VERSION = "0.8.0"`) and requires it first in `lib/boukensha.rb`. The Python port adds `__version__ = "0.8.0"` to `src/boukensha/__init__.py` (no separate `version.py` module — Python packages conventionally expose `__version__` directly on the package, and there's no other consumer of a standalone version module in this codebase). `Repl`'s banner reads this constant for its startup banner.

- **`Client.call()` gets a friendlier 401 message; nothing else about its retry behavior changes**: Ruby's diff adds a single `if response.code.to_i == 401` check before the general non-2xx `ApiError` raise, short-circuiting to `"authentication failed (401) — check your API key"`. 401 is not in `RETRYABLE_STATUS_CODES` in either language, so this is purely a message change on an already-non-retryable path — no new retry logic. Port this check into both of Python's two non-2xx raise sites (the direct `urllib.request.urlopen` non-2xx branch and the `urllib.error.HTTPError` except branch), since Python's `Client.call` — unlike Ruby's single `unless response.is_a?(Net::HTTPSuccess)` check — already splits "non-2xx success response" and "non-2xx via raised HTTPError" into two code paths that both need the same 401 special-case.

- **`Config._resolve_dir()` gains a middle precedence tier**: Ruby's order becomes (1) explicit `BOUKENSHA_DIR` env var, (2) a `.boukensha` directory that already exists under the current working directory, (3) `~/.boukensha`. Python's existing `_resolve_dir` only has tiers (1) and (3) (`os.environ.get("BOUKENSHA_DIR") or str(self.DEFAULT_DIR)`); insert the cwd-`.boukensha`-if-it-exists check between them. This only changes behavior when no `BOUKENSHA_DIR` is set **and** a `./.boukensha` directory is actually present — every existing test/example that sets `BOUKENSHA_DIR` explicitly is unaffected. Update the class docstring to describe all three tiers (it currently only documents two).

- **`Logger` is unchanged in this step**: the Ruby README's own wording for this diff ("`Logger#turn` — New method... prints a header at the start of each REPL turn") is stale/misleading — a direct `diff` of `lib/boukensha/logger.rb` between Ruby's `07_the_run_dsl` and `08_the_repl_loop` produces **zero output** (confirmed). `Logger.turn()` and `Logger.subscribe()` were already added to both the Ruby and Python trees in step 07 (see the `07_the_run_dsl` plan) and carry forward untouched. Ruby's `/quiet`/`/loud` REPL commands only flip the existing `Boukensha.quiet!`/`Boukensha.loud!` module flag (`state.py`'s `quiet()`/`loud()` in Python) — the JSONL logger does not currently read that flag and keeps writing regardless. Port this limitation as-is; do not invent a console-logging system that respects quiet/loud to "complete" the feature — that's out of scope for this step in both languages.

- **`context.py`, `config.py`'s other properties, `prompt_builder.py`, `registry.py`, `tool.py`, `message.py`, `tasks/*.py`, `backends/*.py`, `state.py` are otherwise unchanged**: confirmed via `diff` against Ruby's `07_the_run_dsl` — only `context.rb` (adds `clear_messages!`), `config.rb` (resolve_dir precedence), `client.rb` (401 message), `agent.rb` (assistant-message persistence), and the two new files (`repl.rb`, `version.rb`) differ. Everything else, including `logger.rb`, `registry.rb`, `prompt_builder.rb`, and all `backends/*.rb`, is byte-identical to 07. Copy Python's existing (already step-7) versions forward as-is.

- **Only `None` counts as "omitted" when resolving `repl()`'s optional arguments** — same rule as `run()` from step 7, applied identically here since `repl()` duplicates `run()`'s resolution logic for `system`/`model`/`backend`/`max_output_tokens`/`api_key`. An explicit `max_output_tokens=0` must survive into `repl()` unchanged.

## Target Python Structure (as planned)

```
week1_baseline/python/08_the_repl_loop/
├── src/
│   └── boukensha/
│       ├── __init__.py              # Package exports (modify: add repl, Repl, __version__)
│       ├── run.py                   # run() unchanged; add repl() alongside it (modify)
│       ├── repl.py                  # Repl class (NEW)
│       ├── run_dsl.py               # RunDSL class (copy, unchanged)
│       ├── state.py                 # (copy, unchanged)
│       ├── logger.py                # (copy, unchanged — turn()/subscribe() already ported in 07)
│       ├── agent.py                 # Agent class (modify: persist final assistant message)
│       ├── client.py                # Client class (modify: friendly 401 message)
│       ├── config.py                # Config class (modify: cwd .boukensha fallback tier)
│       ├── tool.py                  # Tool dataclass (copy, unchanged)
│       ├── message.py               # Message dataclass (copy, unchanged)
│       ├── context.py               # Context class (modify: add clear_messages())
│       ├── errors.py                # (copy, unchanged)
│       ├── registry.py              # Registry class (copy, unchanged)
│       ├── prompt_builder.py        # PromptBuilder class (copy, unchanged)
│       ├── tasks/                   # (copy, unchanged)
│       └── backends/                # (copy, unchanged)
├── examples/
│   └── example.py                   # Rewritten to use boukensha.repl() (modify)
├── prompts/
│   └── system.md                    # (copy, unchanged)
├── pyproject.toml                   # Package config (modify: bump version to 0.8.0)
└── README.md                        # Usage documentation (NEW content, ported from Ruby README)
```

### Already Ported (from 07_the_run_dsl, unchanged)
- **tool.py**, **message.py**, **errors.py**, **registry.py**, **prompt_builder.py**, **state.py**, **logger.py** (including `turn()`/`subscribe()`), **run_dsl.py**
- **tasks/base.py**, **tasks/player.py**
- **backends/base.py**, **backends/anthropic.py**, **backends/gemini.py**, **backends/ollama.py**, **backends/ollama_cloud.py**, **backends/openai.py**
- **prompts/system.md**

### New in This Step
- **repl.py**: `Repl` class
- **`repl()`** function, added to the existing `run.py`
- **`__version__`** constant in `__init__.py`

### Modified in This Step
- **context.py**: Add `clear_messages()`
- **agent.py**: Persist the final assistant reply on every return path
- **client.py**: Raise a friendly `ApiError` message on a final HTTP 401
- **config.py**: Add the cwd-`.boukensha` precedence tier; update docstring
- **run.py**: Add `repl()` alongside the existing `run()`
- **__init__.py**: Export `repl`, `Repl`, `__version__`
- **examples/example.py**: Rewritten around `boukensha.repl(configure=...)` instead of `boukensha.run(task=...)`

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
pip install -e week1_baseline/python/07_the_run_dsl
```

### 2. Install 08_the_repl_loop
```bash
pip install -e week1_baseline/python/08_the_repl_loop
```

### 3. Run it
```bash
./week1_baseline/bin/python/08_the_repl_loop
```

---

## Porting Plan: File by File

### 1. Confirm the Starting Point

`week1_baseline/python/08_the_repl_loop/` already exists as a copy of the completed `07_the_run_dsl` step (its `pyproject.toml` still says `0.7.0`, its `__init__.py`/`examples/example.py` are the step-7 versions). No `cp -r` is needed — apply the modifications below directly in place.

---

### 2. `Context.clear_messages()` (`lib/boukensha/context.rb` → `src/boukensha/context.py`)

**Ruby diff**:
```ruby
    # Drop all conversation history, keeping tools and system prompt intact.
    # Used by the REPL's `clear` command.
    def clear_messages!
      @messages = []
    end
```

**Python** (add to existing `context.py`, after `add_message`):
```python
    def clear_messages(self) -> None:
        self.messages = []
```

**Key translation notes**:
- Ruby's trailing `!` (mutating-method naming convention) has no Python equivalent; the method is simply named `clear_messages` (no bang), matching the rest of this port's naming (`add_message`, not `add_message!`).
- Both languages rebind `@messages`/`self.messages` to a brand-new empty list rather than calling `.clear()` in place. This matches Ruby's `@messages = []` exactly; anything holding a reference to the *old* list object (there is no such caller in this codebase — `context.messages` is always read fresh off the `Context` instance) would stop seeing updates, but this is also true of Ruby's `@messages = []`, so it's not a divergence to fix.

---

### 3. `Agent` — persist the final assistant reply (`lib/boukensha/agent.rb` → `src/boukensha/agent.py`)

**Ruby diff** (three call sites, each right before an existing `return`):
```ruby
          text = extract_text(parsed[:content])
          log_response(text: text, response: response)
          @logger.turn_end(reason: "completed", iterations: @iteration)
          @context.add_message(:assistant, text)
          return text
```
```ruby
      text     = fallback_message(reason) if text.strip.empty?
      log_response(text: text, response: response)
      @logger.turn_end(reason: reason, iterations: @iteration)
      @context.add_message(:assistant, text)
      text
    rescue ApiError
      msg = fallback_message(reason)
      @logger.turn_end(reason: reason, iterations: @iteration)
      @context.add_message(:assistant, msg)
      msg
    end
```

**Python** (`src/boukensha/agent.py`, three matching edits):
```python
            else:
                text = self._extract_text(parsed["content"])
                self._log_response(text=text, response=response)
                self.logger.turn_end(reason="completed", iterations=self.iteration)
                self.context.add_message("assistant", text)
                return text
```
```python
            if not text.strip():
                text = self._fallback_message(reason)
            self._log_response(text=text, response=response)
            self.logger.turn_end(reason=reason, iterations=self.iteration)
            self.context.add_message("assistant", text)
            return text
        except ApiError:
            msg = self._fallback_message(reason)
            self.logger.turn_end(reason=reason, iterations=self.iteration)
            self.context.add_message("assistant", msg)
            return msg
```

**Key translation notes**:
- Exactly three insertion points, matching Ruby one-for-one: the no-tool completion branch in `run()`, the successful branch of `_wrap_up()`, and the `except ApiError` branch of `_wrap_up()`. Do **not** add a fourth call inside `_handle_tool_calls` — Ruby's tool-use branch already calls `@context.add_message(:assistant, content)` for the *raw content blocks* (not the final text), and that line is unchanged; the new persistence is specifically about the *terminal* text reply, once per turn.
- This changes `run()`'s (step 7) behavior only in that its throwaway `Context` now briefly holds the final reply before the whole object goes out of scope — there is no observable difference in `run()`'s return value or side effects, since nothing reads `context.messages` after `run()` returns.

---

### 4. `Client` — friendly HTTP 401 message (`lib/boukensha/client.rb` → `src/boukensha/client.py`)

**Ruby diff**:
```ruby
      unless response.is_a?(Net::HTTPSuccess)
        if response.code.to_i == 401
          raise ApiError, "authentication failed (401) — check your API key"
        end
        raise ApiError, "API request failed after #{attempts} attempt#{'s' unless attempts == 1} (#{response.code}): #{response.body}"
      end
```

**Python** (two matching edits in the existing `call()` method — the direct-success-check branch and the `HTTPError` branch):
```python
                # Non-2xx response — check if retryable
                if status_code in self.RETRYABLE_STATUS_CODES and attempts <= self.MAX_RETRIES:
                    time.sleep(self._retry_delay(attempts))
                    continue

                if status_code == 401:
                    raise ApiError("authentication failed (401) — check your API key")

                # Non-2xx, non-retryable — raise
                plural = "s" if attempts != 1 else ""
                raise ApiError(
                    f"API request failed after {attempts} attempt{plural} ({status_code}): {response_body}"
                )
```
```python
            except urllib.error.HTTPError as e:
                # HTTPError has status code and body
                status_code = e.code
                response_body = e.read().decode("utf-8")

                if status_code in self.RETRYABLE_STATUS_CODES and attempts <= self.MAX_RETRIES:
                    time.sleep(self._retry_delay(attempts))
                    continue

                if status_code == 401:
                    raise ApiError("authentication failed (401) — check your API key") from e

                plural = "s" if attempts != 1 else ""
                raise ApiError(
                    f"API request failed after {attempts} attempt{plural} ({status_code}): {response_body}"
                ) from e
```

**Key translation notes**:
- 401 is not present in `RETRYABLE_STATUS_CODES` in either language, so the retryable check always falls through for a 401 — the new check only needs to sit after the retry check and before the generic raise, exactly mirroring Ruby's placement.
- Python's `call()` has two structurally separate non-2xx raise sites (one reached when `urlopen` returns a non-2xx response object directly, one reached via the `HTTPError` exception path), where Ruby's single `Net::HTTP` call always raises via the same `unless response.is_a?(Net::HTTPSuccess)` check. Both Python sites need the identical 401 special-case — this is a consequence of `urllib`'s API shape, not a deliberate behavior difference to introduce.
- Preserve `from e` on the `HTTPError` branch's new raise, consistent with the existing `raise ApiError(...) from e` a few lines below it.

---

### 5. `Config` — cwd `.boukensha` fallback tier (`lib/boukensha/config.rb` → `src/boukensha/config.py`)

**Ruby diff**:
```ruby
    def resolve_dir
      # 1. Explicit override
      return Pathname.new(ENV["BOUKENSHA_DIR"]).expand_path.to_s if ENV["BOUKENSHA_DIR"]

      # 2. .boukensha in the current working directory
      cwd_dir = Pathname.new(Dir.pwd).join(".boukensha")
      return cwd_dir.to_s if cwd_dir.directory?

      # 3. ~/.boukensha default
      Pathname.new(DEFAULT_DIR).expand_path.to_s
    end
```

**Python** (replace the existing `_resolve_dir`):
```python
    def _resolve_dir(self) -> Path:
        # 1. Explicit override
        env_dir = os.environ.get("BOUKENSHA_DIR")
        if env_dir:
            return Path(env_dir).expanduser().resolve()

        # 2. .boukensha in the current working directory
        cwd_dir = Path.cwd() / ".boukensha"
        if cwd_dir.is_dir():
            return cwd_dir

        # 3. ~/.boukensha default
        return self.DEFAULT_DIR.expanduser().resolve()
```

And update the class docstring:
```python
class Config:
    """Resolves the ``.boukensha`` config directory in this order:

    1. ``BOUKENSHA_DIR`` environment variable (set before loading ``.env``)
    2. ``.boukensha`` in the current working directory, if it exists
    3. ``~/.boukensha`` (default)
    """
```

**Key translation notes**:
- Ruby's tier 2 uses `Dir.pwd` (process working directory at call time); Python's equivalent is `Path.cwd()`, not `Path(".")` — both resolve against the *current* working directory, but `Path.cwd()` makes the intent explicit and matches `Pathname.new(Dir.pwd)` directly.
- Ruby's `cwd_dir.directory?` (true only if it exists **and** is a directory) → Python's `cwd_dir.is_dir()` — same semantics; a stray file named `.boukensha` in cwd does not satisfy tier 2 in either language, and falls through to tier 3.
- Behavior is unchanged when `BOUKENSHA_DIR` is explicitly set (as every existing example/launcher does) or when no `./.boukensha` directory exists — the new tier only activates for a caller running from a directory that happens to contain a `.boukensha` subdirectory and has not set the env var.

---

### 6. `__version__` (`lib/boukensha/version.rb` → `src/boukensha/__init__.py`)

**Ruby** (full new file, `lib/boukensha/version.rb`):
```ruby
module Boukensha
  VERSION = "0.8.0"
end
```

**Python**: no new module. Add directly to `src/boukensha/__init__.py`:
```python
__version__ = "0.8.0"
```

**Key translation notes**:
- Python packages conventionally expose version as a `__version__` attribute on the package itself, not a separate submodule — there is no other consumer in this codebase (no `version.py` is imported anywhere else) that would justify mirroring Ruby's separate `version.rb` file 1:1. `Repl`'s banner reads `boukensha.__version__` (passed in by `repl()` as the `version` constructor argument), matching Ruby's `Repl.new(..., version: VERSION, ...)`.

---

### 7. `Repl` (`lib/boukensha/repl.rb` → `src/boukensha/repl.py`)

**Ruby** (full file, see `week1_baseline/ruby/08_the_repl_loop/lib/boukensha/repl.rb`): a class with `PROMPT = "boukensha> "`, a `HELP` heredoc, an `initialize` accepting `context:, registry:, builder:, client:, logger:, config_dir:, provider:, model:, version:, api_key:, task_settings:, max_iterations:, max_output_tokens:`, a public `start` that prints a banner then loops reading `$stdin.gets`, and private `banner`/`run_turn` helpers.

**Python** (`src/boukensha/repl.py`, new file):
```python
import sys
from typing import Any, Dict, Optional

from . import state
from .agent import Agent
from .builder_types import PromptBuilder  # see note below — import from prompt_builder
from .client import Client
from .context import Context
from .errors import ApiError, LoopError
from .logger import Logger
from .registry import Registry

PROMPT = "boukensha> "

HELP = """Commands:
  /quiet   suppress logging output
  /loud    re-enable logging output
  /clear   wipe conversation history (tools stay)
  /exit    leave the REPL
  /help    show this message
"""


class Repl:
    """The interactive session loop.

    Wraps the same primitives as a single ``run()`` call, but instead of
    running once it stays alive: it reads a task from the user, runs the
    agent, prints the reply, and loops back to the prompt.

    The Context is shared across every turn so conversation history
    accumulates naturally.
    """

    def __init__(
        self,
        context: Context,
        registry: Registry,
        builder: "PromptBuilder",
        client: Client,
        logger: Logger,
        config_dir: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        version: Optional[str] = None,
        api_key: Optional[str] = None,
        task_settings: Optional[Dict[str, Any]] = None,
        max_iterations: Optional[int] = None,
        max_output_tokens: Optional[int] = None,
    ) -> None:
        self.context = context
        self.registry = registry
        self.builder = builder
        self.client = client
        self.logger = logger
        self.task_settings = task_settings
        self.max_iterations = max_iterations
        self.max_output_tokens = max_output_tokens
        self.config_dir = config_dir
        self.provider = provider
        self.model = model
        self.version = version
        self.api_key = api_key
        self.turn = 0

    def start(self) -> None:
        print(self._banner())

        while True:
            print(PROMPT, end="")
            sys.stdout.flush()

            line = sys.stdin.readline()
            if not line:
                break  # EOF / Ctrl-D

            command = line.strip()
            if not command:
                continue

            if command in ("/exit", "/quit"):
                print("Goodbye.")
                break
            elif command == "/help":
                print(HELP)
                continue
            elif command == "/quiet":
                state.quiet()
                print("(logging suppressed — type /loud to re-enable)")
                continue
            elif command == "/loud":
                state.loud()
                print("(logging enabled)")
                continue
            elif command == "/clear":
                self.context.clear_messages()
                self.turn = 0
                print("(conversation history cleared)")
                continue

            self._run_turn(command)

    def _banner(self) -> str:
        key_status = (
            "✗ API key not set"
            if not self.api_key or not self.api_key.strip()
            else "✓ API key set"
        )
        provider_line = f"{self.provider or 'default'} ({self.model or 'default'})  {key_status}"
        config_exists = bool(self.config_dir) and Path(self.config_dir).is_dir()
        config_line = (
            str(self.config_dir)
            if config_exists
            else f"{self.config_dir or '(default)'}  ✗ directory not found"
        )
        ver = self.version or "?.?.?"

        return (
            "\n"
            "╔══════════════════════════════════════╗\n"
            f"║  BOUKENSHA MUD Assistant (v{ver}){' ' * (9 - len(ver))}║\n"
            "╚══════════════════════════════════════╝\n"
            f"  config:    {config_line}\n"
            f"  provider:  {provider_line}\n"
            "\n"
            "  /quiet or /loud   toggle logging\n"
            "  /clear           reset conversation history\n"
            "  /exit or /quit    leave the REPL\n"
        )

    def _run_turn(self, task: str) -> None:
        self.turn += 1
        self.logger.turn(self.turn)

        self.context.add_message("user", task)

        agent = Agent(
            context=self.context,
            registry=self.registry,
            builder=self.builder,
            client=self.client,
            logger=self.logger,
            task_settings=self.task_settings,
            max_iterations=self.max_iterations,
            max_output_tokens=self.max_output_tokens,
        )
        try:
            result = agent.run()
        except LoopError as e:
            print(f"\n[error] {e}")
            return
        except ApiError as e:
            print(f"\n[error] API call failed: {e}")
            return

        # Print the final response outside of the logger so it is always
        # visible, even when state.quiet() is active.
        print()
        print(result)
```

**Key translation notes**:
- `PROMPT`/`HELP` are module-level constants in Python (not class constants like Ruby's `PROMPT =`/`HELP =` inside `class Repl`), since Python has no equivalent to Ruby's implicit "constant defined inside a class body is namespaced under it" that callers would ever need to reach externally — `Repl.PROMPT`-style access isn't used anywhere in Ruby's own code either. If external access to `Repl.PROMPT` is wanted for parity, keep them as class attributes instead; either is acceptable since nothing outside `repl.py` reads them. *(Decide and keep consistent; the example above uses module constants for simplicity.)*
- Ruby's `$stdin.gets` returns `nil` on EOF and a string (including the trailing newline) otherwise; Python's `sys.stdin.readline()` returns `""` on EOF and a string (including the trailing newline) otherwise — `if not line: break` correctly captures Python's EOF case without misfiring on a blank-but-present line (`"\n"` is truthy, `""` is falsy).
- Ruby's `case input when "/exit", "/quit" ... end` → Python `if/elif` chain compared against the stripped command string. Unrecognized slash-prefixed input (e.g. `/foo`) falls through to `_run_turn` exactly like Ruby — it is *not* rejected as an "unknown command" error, it's sent to the agent as an ordinary task.
- `Boukensha.quiet!`/`Boukensha.loud!` (module-level self-methods calling into the same package's `@quiet` flag) → `state.quiet()`/`state.loud()`, the existing step-06 functions already re-exported from `boukensha/__init__.py`. Import them from `.state`, not `boukensha` itself, to avoid a circular import (same reasoning `run.py` already applies for `boukensha_config`).
- `@logger.turn(n: @turn)` (keyword arg) → `self.logger.turn(self.turn)` (positional) — matches how `Logger.turn` was already defined as a plain positional-or-keyword `n: int` parameter in the 07 port (see that step's Decisions).
- Constructing a fresh `Agent` every turn is intentional (matches Ruby's `Agent.new(...)` inside `run_turn`): it resets the per-turn `iteration` counter to 0 for each new task while `context`/`registry`/`client`/`logger` — and therefore all conversation history and side effects — remain shared across turns.
- `rescue LoopError => e` / `rescue ApiError => e` around only the agent-run call (not the whole `start` loop) → Python's `try/except` wraps only `agent.run()` inside `_run_turn`, letting any other exception type propagate up through `start()` and out of `repl()` uncaught, matching Ruby's behavior of only rescuing these two specific error classes at this level.
- Needs `from pathlib import Path` for the config-dir-exists check in `_banner` (add to the imports at the top of the file; omitted from the visual excerpt above for brevity — include it in the actual file).
- The `builder_types` import shown above is a placeholder to avoid a real circular-import risk: `repl.py` should import `PromptBuilder` from `.prompt_builder` directly, the same as `run.py` already does — there's no such module as `builder_types` in this codebase. Use `from .prompt_builder import PromptBuilder`.

---

### 8. `repl()` (`lib/boukensha.rb` → `src/boukensha/run.py`)

**Ruby** (new `self.repl` method in `lib/boukensha.rb`, alongside the unchanged `self.run`): resolves `system`/`model`/`backend`/`api_key` exactly like `run` (same fallbacks, same `case backend when ...`), builds `Context`/`Registry`, runs the `configure` block via `RunDSL.new(registry).instance_eval(&block)`, builds the backend/builder/client/logger exactly like `run`, then constructs `Repl.new(...)` (passing `config_dir: cfg.dir`, `provider: backend`, `model: model`, `version: VERSION`, `api_key: api_key` in addition to everything `run` passes to `Agent`) and calls `.start`. Wraps the whole thing in `rescue Interrupt` (prints `"\nInterrupted."`) and an `ensure logger&.close`.

**Python** (add to the existing `src/boukensha/run.py`, alongside `run()`):
```python
from .repl import Repl


def repl(
    system: Optional[str] = None,
    model: Optional[str] = None,
    backend: Optional[str] = None,
    api_key: Optional[str] = None,
    ollama_host: str = "http://localhost:11434",
    log: Optional[str] = None,
    max_output_tokens: Optional[int] = None,
    configure: Optional[Callable[[RunDSL], None]] = None,
) -> None:
    """Interactive REPL: register tools once, then loop — reading tasks from
    stdin, running the agent, and printing replies — until the user exits or
    sends EOF.

    Conversation history accumulates across every turn so the agent always
    sees the full transcript.

    Options are the same as ``run()``, minus ``task`` (the user supplies
    tasks interactively).
    """
    cfg = boukensha_config()  # loads .env; populates os.environ
    task_class = Player
    task_settings = cfg.tasks(task_class.task_name()) or {}

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

    try:
        Repl(
            context=ctx,
            registry=registry,
            builder=builder,
            client=client,
            logger=logger,
            task_settings=task_settings,
            max_iterations=effective_max_iterations,
            max_output_tokens=effective_max_output_tokens,
            config_dir=str(cfg.dir),
            provider=backend,
            model=model,
            version=__version__,
            api_key=api_key,
        ).start()
    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        logger.close()
```

And import `__version__` at the top of `run.py` from the package's own `__init__` — see the note below on avoiding a circular import.

**Key translation notes**:
- Ruby's `rescue Interrupt` (raised on Ctrl-C in a blocking `$stdin.gets`) → Python's `except KeyboardInterrupt`, the direct equivalent raised by the same signal during a blocking `sys.stdin.readline()`.
- Ruby's `ensure logger&.close` (safe-navigation, in case `logger` was never assigned) → Python's `finally: logger.close()` is safe unguarded here for the same reason established in the 07 plan: by the time the `try` block is entered, `logger = Logger(...)` has already succeeded, so `logger` is always bound: if `Logger(...)` itself raises, execution never reaches the `try`, so there is nothing to clean up.
- `RunDSL.new(registry).instance_eval(&block) if block` → `if configure is not None: configure(RunDSL(registry))`, identical to `run()`'s existing translation — this ordering (tool registration before backend construction) must be preserved exactly.
- **Avoiding logic drift between `run()` and `repl()`**: since `repl()` re-resolves `system`/`model`/`backend`/`api_key`/backend-construction/`builder`/`client`/effective-limits/`logger`-snapshot in a way that is line-for-line identical to `run()`'s existing code (this mirrors Ruby's own `lib/boukensha.rb`, which duplicates the same block rather than extracting a shared private helper), the port may either (a) duplicate the block exactly as shown above, matching Ruby 1:1, or (b) extract a small private helper (e.g. `_resolve_run_context(...)` returning `(ctx, registry, builder, client, effective_max_iterations, effective_max_output_tokens, logger, backend, model)`) shared by both `run()` and `repl()`. Ruby does not do this itself (no such helper exists in `lib/boukensha.rb`), so option (a) is the more faithful port; option (b) is acceptable *only* as a mechanical, behavior-preserving refactor — do not let it change resolution order, the `None`-vs-falsy handling, or the backend dispatch dict/`case`. Whichever is chosen, do not let `run()`'s existing behavior change as a side effect.
- **Circular import**: `run.py` needs `__version__` from `boukensha/__init__.py`, but `__init__.py` also imports `repl`/`run` from `run.py`. Avoid the cycle by defining `__version__` as a plain string literal directly in `run.py` too (e.g. a local `_VERSION = "0.8.0"` constant in `run.py`, used for the `Repl(version=...)` argument), and have `__init__.py`'s `__version__ = "0.8.0"` be the single source of truth that `run.py` does **not** import back — i.e., duplicate the literal `"0.8.0"` string in both places (matching how Ruby avoids this entirely differently, via `require_relative "boukensha/version"` at the very top of `lib/boukensha.rb`, before anything else, so there's no cycle in Ruby's `require` graph to begin with). Alternatively, keep `__version__` defined in `run.py` itself and have `__init__.py` do `from .run import __version__` — this is the cleaner option and avoids duplicating the literal; prefer it.

---

### 9. Package Exports (`lib/boukensha.rb`'s `require_relative` list → `src/boukensha/__init__.py`)

**Python** (modify existing file):
```python
# Boukensha agent loop — backends, tasks, registry, builder, client, agent, logger, run DSL, and REPL
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

# From prior step (07_the_run_dsl)
from .run_dsl import RunDSL  # noqa: F401

# New in this step (08_the_repl_loop)
from .run import run, repl, __version__  # noqa: F401
from .repl import Repl  # noqa: F401

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
    "repl",
    "Repl",
    "__version__",
    "tasks",
    "backends",
]
```

**Change**: Add `repl` and `__version__` to the `run` import line, add a new `Repl` import from `repl.py`, and extend `__all__` with `"repl"`, `"Repl"`, `"__version__"`.

---

### 10. Example (`examples/example.rb` → `examples/example.py`)

**Ruby** (full file):
```ruby
ENV["BOUKENSHA_DIR"] ||= File.expand_path("../../../../.boukensha", __dir__)
require_relative "../lib/boukensha"

# Config is loaded automatically inside Boukensha.repl — system prompt, model,
# and API key all come from ~/.boukensha (or BOUKENSHA_DIR) by default.

puts "Config: #{Boukensha.config}"
puts

# The base directory tools will operate relative to — the step 7 folder makes
# a good playground since it already has source files to read.
base_dir = File.expand_path("../../07_the_run_dsl", __dir__)

Boukensha.repl do
  tool "read_file",
    description: "Read the contents of a file from disk",
    parameters:  { path: { type: "string", description: "File path (relative to the working directory)" } } do |path:|
    File.read(File.expand_path(path, base_dir))
  end

  tool "list_directory",
    description: "List the files in a directory",
    parameters:  { path: { type: "string", description: "Directory path (relative to the working directory, or '.' for root)" } } do |path:|
    Dir.entries(File.expand_path(path, base_dir))
       .reject { |f| f.start_with?(".") }
       .sort
       .join(", ")
  end
end
```

**Python** (rewrite `examples/example.py`):
```python
import os
from pathlib import Path

import boukensha

os.environ.setdefault(
    "BOUKENSHA_DIR",
    str(Path(__file__).resolve().parent.parent.parent.parent.parent / ".boukensha"),
)

# Config is loaded automatically inside boukensha.repl() — system prompt,
# model, and API key all come from ~/.boukensha (or BOUKENSHA_DIR) by default.

print(f"Config: {boukensha.config()}")
print()

# The base directory tools operate relative to — the step 7 folder makes a
# good playground since it already has source files to read.
base_dir = Path(__file__).resolve().parent.parent.parent / "07_the_run_dsl"


def register_tools(dsl: boukensha.RunDSL) -> None:
    @dsl.tool(
        "read_file",
        description="Read the contents of a file from disk",
        parameters={
            "path": {
                "type": "string",
                "description": "File path (relative to the working directory)",
            }
        },
    )
    def read_file(path: str) -> str:
        return (base_dir / path).read_text()

    @dsl.tool(
        "list_directory",
        description="List the files in a directory",
        parameters={
            "path": {
                "type": "string",
                "description": "Directory path (relative to the working directory, or '.' for root)",
            }
        },
    )
    def list_directory(path: str) -> str:
        return ", ".join(
            sorted(f for f in os.listdir(str(base_dir / path)) if not f.startswith("."))
        )


boukensha.repl(configure=register_tools)
```

**Key translation notes**:
- Ruby's `Boukensha.repl do ... end` (implicit block) → Python's `boukensha.repl(configure=register_tools)`, the same `configure=`-callback convention already established for `run()` in step 7 — no new DSL-translation concerns beyond what's already documented there.
- `base_dir` now points at the sibling `07_the_run_dsl` directory (both languages), not the example's own step directory — this matches Ruby's diff exactly (`File.expand_path("../../07_the_run_dsl", __dir__)`) and gives the REPL session real, pre-existing files to explore across multiple turns.
- Ruby's `.reject { |f| f.start_with?(".") }.sort.join(", ")` → Python's `sorted(f for f in ... if not f.startswith("."))` then `", ".join(...)` — note the *order* of `sort` vs. `reject`/`filter` doesn't matter for correctness here (filtering then sorting is equivalent to sorting then filtering, since neither is order-dependent on the other), but the Python version filters-then-sorts to read left-to-right the same as Ruby's chain.
- No `result = ...` / `puts result` block at the end — unlike step 7's one-shot `run()`, `repl()` returns `None` (it drives the interactive session itself and prints replies turn-by-turn); the example's final call is a bare statement.

---

### 11. Update pyproject.toml

Bump version from `0.7.0` to `0.8.0`:
```toml
[project]
name = "boukensha"
version = "0.8.0"
description = "Boukensha REPL loop — an interactive, multi-turn session built on the run DSL, with persistent conversation history"
# ... rest unchanged
```

---

### 12. Update README.md

Replace the step 7 README with step 8 content, ported from the Ruby `README.md`. Key sections:

- **What this step adds**: a comparison table (one turn vs. many; discarded vs. accumulating history; no user interaction vs. a stdin prompt) contrasting `run()` and `repl()`.
- **New primitives**: `Repl` (the session loop and its built-in commands table: `/quiet`, `/loud`, `/clear`, `/help`, `/exit`/`/quit`, Ctrl-D, Ctrl-C) and `repl()` (same signature as `run()` minus `task`, plus the `configure=` callback convention from step 7).
- **Changes from step 7**: `Context.clear_messages()`, `Agent` now persisting the final reply so later turns see it, the friendly HTTP 401 message, and the `.boukensha`-in-cwd config precedence tier. Explicitly note that `Logger.turn()`/`subscribe()` are *not* new in this step (already shipped in 07) — don't repeat Ruby's stale README claim that they're new here.
- **Current limitation**: `/quiet`/`/loud` only toggle the existing package-level flag; the JSONL session logger does not currently read it and keeps writing regardless.
- **Run Example**: `./week1_baseline/bin/python/08_the_repl_loop`, including a short sample transcript showing multi-turn memory (e.g. asking "what was the first file I asked you about?" after a `/clear`-free session).

---

## Dependency Chain

```
08_the_repl_loop (Repl, repl, __version__)
    ↓ extends/depends on
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

Keep verification fully offline: drive `Repl.start()` with scripted `sys.stdin`/captured `sys.stdout` (or an injected readable/writable stream) and a fake `Agent`/`Client`/backend, so nothing here requires a real provider request or API key.

### Unit-level verification (as you build):
1. **Import surface**: `from boukensha import repl, Repl, run, __version__` succeeds; the existing `run` import still works unchanged.
2. **`Context.clear_messages()`**: after adding several messages, call it and assert `context.messages == []`, while `context.task`, `context.system`, and `context.tools` are untouched.
3. **`Agent` persists the final reply**: with a fake client, exercise (a) normal no-tool completion, (b) the iteration-limit wrap-up success path, and (c) the wrap-up path where the wrap-up call raises `ApiError`; assert in each case that exactly one new assistant message equal to the returned string was appended, and that tool-use intermediate messages (already added by `_handle_tool_calls`) are not duplicated.
4. **`Repl.start()` command handling**: script stdin with blank lines, `/help`, `/quiet`, `/loud`, `/clear`, an unrecognized `/foo`, `/exit`, `/quit`, and EOF (empty read). Assert built-in commands never reach `Agent`/`client`, `/foo` *does* reach the agent as an ordinary task, prompts/messages match expected text, and `/clear` resets both `context.messages` and `self.turn` to 0.
5. **Multi-turn history accumulation**: script two ordinary turns; assert a fresh `Agent` is constructed each turn (its `iteration` starts at 0 each time) while `context.messages` contains both complete user/assistant exchanges by the second turn, and `logger.turn(n)` is invoked with `1` then `2`.
6. **Per-turn error handling**: make a scripted turn's `agent.run()` raise `LoopError`, then another raise `ApiError`; assert the friendly `"[error] ..."` message prints and the loop continues to the next prompt without exiting. Make a turn raise an unrelated exception and assert it propagates out of `start()` (not swallowed).
7. **`repl()` argument resolution and dispatch**: with `task_settings` stubbed, verify `system`/`model`/`backend`/`max_output_tokens` fall back to the task-class defaults only when `None` — including that an explicit `max_output_tokens=0` survives unchanged — mirroring the equivalent `run()` tests from step 7. Verify all five backends construct with the right kwargs and an unknown backend raises `ValueError` without a network call.
8. **`repl()` configure-callback ordering and cleanup**: assert `configure` is invoked with a `RunDSL` exactly once, before any backend is constructed; assert the constructed `Repl` receives `config_dir`, `provider`, `model`, `version`, and `api_key` matching resolved values; assert `logger.close()` is called exactly once on normal `Repl.start()` return, on `KeyboardInterrupt`, and if `Repl.start()` raises unexpectedly (exception still propagates after cleanup).
9. **`Client` HTTP 401**: feed the client a final (non-retried, or retries-exhausted) 401 response and assert the raised `ApiError` message is exactly `"authentication failed (401) — check your API key"`; feed a final non-401, non-2xx response and assert the existing detailed message is unchanged; assert 401 is never retried even when it's the very first response.
10. **`Config._resolve_dir()` precedence**: in an isolated temp working directory, test (a) `BOUKENSHA_DIR` set → used regardless of cwd contents, (b) `BOUKENSHA_DIR` unset, `./.boukensha` exists as a directory in cwd → that path used, (c) `BOUKENSHA_DIR` unset, no `./.boukensha` → falls back to `~/.boukensha`. Confirm a `./.boukensha` that is a plain *file* (not a directory) does **not** satisfy tier 2.
11. **Launcher smoke test**: run `week1_baseline/bin/python/08_the_repl_loop` with scripted `/exit` on stdin far enough to validate path/import/config/banner setup without a network call.

### Full integration test (requires provider credentials):
```bash
source venv/bin/activate
pip install -e week1_baseline/python/08_the_repl_loop
./week1_baseline/bin/python/08_the_repl_loop
# try a multi-turn session, e.g.:
#   list the files in the lib directory
#   now read one of them and explain it
#   /quiet
#   what was the first file I asked you about?
#   /exit
cat ~/.boukensha/sessions/*.jsonl | tail -5   # inspect the newest session log
```

## Acceptance Criteria

- `boukensha.repl(...)` starts an interactive session; an optional `configure` callback registers tools once via `RunDSL`, exactly like `run()`'s convention, and `run()` itself is unaffected and still works for one-shot calls.
- Conversation history accumulates across turns: later tasks in the same session can reference earlier user and assistant messages, because `Agent` now persists its final reply on every return path and `Repl` shares one `Context` across turns.
- `/clear` wipes conversation history only — tools and the system prompt remain registered — and resets the turn counter used for both the banner-adjacent turn count and `Logger.turn(n)`.
- `/quiet`, `/loud`, `/help`, `/exit`, `/quit`, EOF, and Ctrl-C all behave as documented; recoverable per-turn errors (`LoopError`, `ApiError`) print a friendly message and return to the prompt rather than ending the session; any other exception still propagates.
- All five backends remain selectable through `repl()`'s `backend` keyword with the same `None`-vs-falsy resolution rules as `run()`, including a surviving explicit `max_output_tokens=0`.
- `Client.call()` raises a concise, dedicated `ApiError` message on a final HTTP 401, with no change to retry behavior (401 was never retryable and still isn't) or to any other non-2xx status's message.
- `Config` resolves its directory in three tiers — explicit `BOUKENSHA_DIR`, then an existing `./.boukensha` in the current working directory, then `~/.boukensha` — with existing callers that always set `BOUKENSHA_DIR` completely unaffected.
- The `Logger` used by both `run()` and `repl()` is always closed exactly once, on normal exit, EOF, `KeyboardInterrupt`, or an unexpected exception, without swallowing the original exception; `Logger.turn()`/`subscribe()` behavior is unchanged from step 7 (no new functionality invented here).
- `examples/example.py` demonstrates an interactive multi-turn session using `boukensha.repl(configure=...)` against the sibling `07_the_run_dsl` directory's files.
- `LoopError`, `UnknownToolError`, `ApiError`, `UnsupportedModelError`, `RunDSL`, and every prior-step export remain importable and behaviorally unchanged.

---

## Common Pitfalls

### 1. Don't let `/quiet`/`/loud` "complete" the feature by wiring them into the JSONL logger
**Problem**: Seeing `/quiet` and `/loud` as REPL commands strongly suggests they should suppress the structured session log, since that's the most obvious interpretation of "quiet."
**Fix**: Ruby's own implementation only flips `Boukensha.quiet!`/`Boukensha.loud!` — the same module-level flag from step 6 — and the JSONL `Logger` never reads it, in either language. Port exactly this (a no-op-as-far-as-the-log-file-goes toggle) and document it as a known limitation in the README, rather than inventing new logger-gating behavior that Ruby doesn't have.

### 2. Persisting the final assistant reply in three places, not one
**Problem**: It's easy to add `context.add_message("assistant", text)` only to the "happy path" no-tool completion and miss that both wrap-up branches (the success case and the `ApiError`-fallback case) also need it, since a REPL session can hit either of those mid-conversation and still needs the reply remembered for the next turn.
**Fix**: Match Ruby's three insertion points exactly (see Section 3) — normal completion, successful wrap-up, and the `except ApiError` wrap-up fallback. Write test 3 in the Verification section to cover all three paths explicitly.

### 3. A fresh `Agent` every turn is correct, not a missed-sharing bug
**Problem**: Since `context`/`registry`/`client`/`logger` are all shared across turns, it can look like `Agent` itself should be constructed once in `repl()`/`Repl.__init__` and reused, to "match" the sharing of everything else.
**Fix**: Ruby's `run_turn` explicitly builds a new `Agent.new(...)` every turn, and the Python port must too — this is what resets the per-turn `@iteration`/`self.iteration` counter to 0 for each new task, so the `max_iterations` ceiling applies per-turn rather than accumulating across the whole session. Only `context`, `registry`, `builder`, `client`, and `logger` are the long-lived, shared objects; `Agent` itself is turn-scoped.

### 4. `Config`'s new cwd tier only activates in a narrow, easy-to-miss condition
**Problem**: It's tempting to write the check as "does `./.boukensha` exist" (any file or symlink) rather than specifically "is it a directory," or to check it *before* `BOUKENSHA_DIR`, both of which would silently change behavior for existing callers/tests.
**Fix**: Preserve Ruby's exact precedence and directory-only check: `BOUKENSHA_DIR` env var wins unconditionally if set (regardless of cwd contents); only when it's unset does a `./.boukensha` *directory* (not file) in cwd get used; otherwise fall back to `~/.boukensha`. Write test 10 specifically to lock in all three tiers plus the file-vs-directory distinction.

### 5. HTTP 401 must not become retryable
**Problem**: Adding a new status-code branch near the existing `RETRYABLE_STATUS_CODES` check can tempt a "while we're here" addition of 401 to the retryable set, reasoning that a transient auth hiccup might resolve on retry.
**Fix**: Don't. Neither Ruby nor the existing Python `RETRYABLE_STATUS_CODES` set includes 401, and the whole point of this change is a clearer *message* for what is still a non-retryable, terminal failure — an invalid/missing API key will not become valid on the next attempt. Keep 401 entirely outside `RETRYABLE_STATUS_CODES`; only change the error text.

### 6. Don't invent a `version.py` module or import it circularly
**Problem**: The most literal reading of "Ruby adds `lib/boukensha/version.rb` and requires it first" is to add a Python `version.py` and have both `__init__.py` and `run.py` import from it — but if `run.py` needs the constant for `Repl(version=...)` and `__init__.py` needs it for `__version__` while also importing `run`/`repl` from `run.py`, a naive arrangement can create a cycle.
**Fix**: Define `__version__ = "0.8.0"` directly in `run.py` (no separate `version.py` module) and have `__init__.py` do `from .run import run, repl, __version__` — a one-directional import, no cycle. See Section 8's dedicated translation note.

---

## Files to Create/Modify

1. Modify `src/boukensha/context.py` — add `clear_messages()`
2. Modify `src/boukensha/agent.py` — persist the final assistant reply on all three return paths
3. Modify `src/boukensha/client.py` — friendly `ApiError` message on a final HTTP 401, in both non-2xx raise sites
4. Modify `src/boukensha/config.py` — add the cwd-`.boukensha` precedence tier; update docstring
5. Create `src/boukensha/repl.py` — `Repl` class
6. Modify `src/boukensha/run.py` — add `repl()` alongside the existing `run()`; define `__version__ = "0.8.0"`
7. Modify `src/boukensha/__init__.py` — export `repl`, `Repl`, `__version__`
8. Rewrite `examples/example.py` — use `boukensha.repl(configure=...)` against the sibling `07_the_run_dsl` directory
9. Update `pyproject.toml` — version bump to 0.8.0
10. Update `README.md` — replace with Step 8 (REPL Loop) content, correcting the Ruby README's stale "Step 7"/`Logger#turn`-is-new claims
11. Create `week1_baseline/bin/python/08_the_repl_loop` — executable launcher (mirrors `07_the_run_dsl`'s launcher, `cd` target updated to `08_the_repl_loop`)

## Not Ported (unrelated to the REPL loop, skip)

- Ruby's `logger.rb` — zero-line diff against `07_the_run_dsl`; `turn()`/`subscribe()` were already ported in the Python 07 step, and the Ruby README's claim that `Logger#turn` is new in this step is stale/incorrect.
- Any change to `registry.rb`, `prompt_builder.rb`, `tool.rb`, `message.rb`, `tasks/*.rb`, `backends/*.rb` — all byte-identical to `07_the_run_dsl` per `diff`.
- A logger-level implementation of `/quiet`/`/loud` that actually suppresses JSONL output — out of scope; Ruby doesn't do this either (see Common Pitfall #1).
