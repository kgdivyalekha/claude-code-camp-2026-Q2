# The REPL Loop

`boukensha.repl(...)` is an interactive, multi-turn entry point built on top of the run DSL. Where `run()` sends one task and returns, `repl()` reads tasks from stdin in a loop, keeps the whole conversation in a shared `Context`, and lets every later turn see earlier user and assistant messages.

| | `run()` | `repl()` |
|---|---|---|
| Entry point | `boukensha.run(task="…")` | `boukensha.repl(...)` |
| Turns | one | many |
| History | discarded when the call returns | accumulates across turns |
| User interaction | none | `boukensha> ` stdin prompt |

## New Files (Step 08)

| File | Description |
|---|---|
| `src/boukensha/repl.py` | `Repl` — the prompt loop, built-in commands, banner, and per-turn `Agent` construction |
| `src/boukensha/run.py` | Gains `repl()` alongside the existing `run()`; also defines `__version__` |

## Changes from Step 07

| File | Change |
|---|---|
| `src/boukensha/context.py` | Adds `clear_messages()` — empties conversation history while keeping `task`/`system`/`tools` intact |
| `src/boukensha/agent.py` | Persists the final assistant reply to `context` on every return path (normal completion, iteration-limit wrap-up, and the `ApiError`-fallback wrap-up), so a later turn can see it |
| `src/boukensha/client.py` | A final HTTP 401 now raises `ApiError("authentication failed (401) — check your API key")` instead of the generic message; retry behavior is unchanged (401 was never retryable) |
| `src/boukensha/config.py` | `_resolve_dir()` gains a middle precedence tier: `BOUKENSHA_DIR` → `.boukensha` in the current working directory, if it exists → `~/.boukensha` |

`src/boukensha/logger.py` is **not** changed in this step — `Logger.turn()` and `Logger.subscribe()` were already added in `07_the_run_dsl` and carry forward untouched.

## Carried Forward (Steps 00-07)

| File | Description |
|---|---|
| `src/boukensha/run_dsl.py` | `RunDSL` — a tiny object exposing only a `tool` decorator, passed into your `configure` callback |
| `src/boukensha/logger.py` | Structured JSONL event logging for every phase of an agent turn, plus `turn(n)` and `subscribe(callback)` |
| `src/boukensha/state.py` | Package-wide runtime state: cached `Config`, `quiet`/`loud`, `debug` |
| `src/boukensha/client.py` | Makes HTTP requests to LLM APIs with retry logic and error handling |
| `src/boukensha/prompt_builder.py` | Delegates serialization and response parsing to the active backend |
| `src/boukensha/tasks/base.py`, `src/boukensha/tasks/player.py` | Task configuration helpers |
| `src/boukensha/backends/*.py` | Per-provider serialization, response parsing, and model metadata |
| `prompts/system.md` | Default system prompt used when a task does not override it |

## `Repl`

The interactive session loop. Built-in commands (not sent to the agent):

| Command | Effect |
|---|---|
| `/quiet` | Suppress logging output (toggles the same package-wide flag as Step 06; see the limitation below) |
| `/loud` | Re-enable logging output |
| `/clear` | Wipe conversation history — tools and the system prompt stay registered |
| `/help` | Print the command list |
| `/exit` / `/quit` | Leave the REPL |
| Ctrl-D (EOF) | Leave the REPL |
| Ctrl-C | Interrupted — leave the REPL gracefully |

Any other input, including an unrecognized `/something`, is sent to the agent as an ordinary task.

Each turn constructs a fresh `Agent` — this intentionally resets its per-turn iteration counter — while `context`, `registry`, `builder`, `client`, and `logger` remain shared across the whole session.

## `boukensha.repl(...)`

Same options as `run()`, minus `task` (the user supplies tasks interactively):

| Option | Default | Description |
|---|---|---|
| `system` | task's system prompt | System prompt |
| `model` | task's configured model | Model name |
| `backend` | task's configured provider | `"anthropic"`, `"openai"`, `"gemini"`, `"ollama"`, or `"ollama_cloud"` |
| `api_key` | matching `*_API_KEY` env var | Not needed for `"ollama"` |
| `ollama_host` | `"http://localhost:11434"` | Ollama base URL |
| `log` | `None` | Optional JSONL path override; defaults to `.boukensha/sessions/<session-id>.jsonl` |
| `max_output_tokens` | task's configured limit | Per-reply output cap |
| `configure` | `None` | Callback receiving a `RunDSL` instance for tool registration |

Only `None` counts as "omitted" for every optional argument above — an explicit `max_output_tokens=0` is honored as-is, matching `run()`.

```python
import boukensha


def register_tools(dsl):
    @dsl.tool(
        "read_file",
        description="Read a file from disk",
        parameters={"path": {"type": "string", "description": "File path"}},
    )
    def read_file(path):
        return open(path).read()


boukensha.repl(model="claude-haiku-4-5", configure=register_tools)
```

```
╔══════════════════════════════════════╗
║  BOUKENSHA MUD Assistant (v0.8.0)     ║
╚══════════════════════════════════════╝
  config:    /home/you/.boukensha
  provider:  anthropic (claude-haiku-4-5)  ✓ API key set

  /quiet or /loud   toggle logging
  /clear           reset conversation history
  /exit or /quit    leave the REPL

boukensha> list the files in the lib directory
…
boukensha> now read one of them and explain the loop
…
boukensha> /quiet
(logging suppressed — type /loud to re-enable)
boukensha> what was the first file I asked you about?
…
boukensha> /exit
Goodbye.
```

The last question demonstrates persistent history: the agent answers from the accumulated transcript, not just the last message.

## Current limitation

`/quiet` and `/loud` only toggle the existing `state.quiet()`/`state.loud()` package flag from Step 06 — the JSONL session logger does not currently read that flag and keeps writing regardless. This matches the underlying Ruby reference and is not fixed in this step.

## `Client` — friendlier authentication errors

A request that fails with a final HTTP 401 now raises a concise `ApiError`:

```
authentication failed (401) — check your API key
```

401 was never in the retryable status set and still isn't — this only changes the error message on an already-terminal failure.

## `Config` directory resolution

`Config._resolve_dir()` now checks three tiers, in order:

1. `BOUKENSHA_DIR` environment variable
2. `.boukensha` in the current working directory, if it exists as a directory
3. `~/.boukensha` (default)

Any caller that already sets `BOUKENSHA_DIR` (every example and launcher in this repo) is unaffected — the new tier only applies when the variable is unset and a `./.boukensha` directory happens to be present.

## Task Configuration

Step 08 uses the same task-based settings shape as prior steps:

```yaml
tasks:
  player:
    provider: anthropic
    model: claude-haiku-4-5
    prompt_override:
      system: true
```

## Run Example

```sh
./week1_baseline/bin/python/08_the_repl_loop
```

The example registers two tools (`read_file`, `list_directory`) rooted at the sibling `07_the_run_dsl` directory and starts an interactive session. The logger writes a session JSONL file under `.boukensha/sessions`.
