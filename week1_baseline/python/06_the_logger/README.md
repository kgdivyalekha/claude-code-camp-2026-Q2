# The Logger

`Logger` records each agent run as structured JSON Lines. It is a file logger, not user-facing display output.

## New Files (Step 06)

| File | Description |
|---|---|
| `src/boukensha/logger.py` | Writes structured JSONL events for every phase of an agent turn |
| `src/boukensha/state.py` | Package-wide runtime state: cached `Config`, `quiet`/`loud`, `debug` |

## Carried Forward (Steps 00-05)

| File | Description |
|---|---|
| `src/boukensha/agent.py` | The agent loop — sends requests, dispatches tools, and knows when to stop (now instrumented with `Logger` calls) |
| `src/boukensha/client.py` | Makes HTTP requests to LLM APIs with retry logic and error handling |
| `src/boukensha/prompt_builder.py` | Delegates serialization and response parsing to the active backend |
| `src/boukensha/tasks/base.py`, `src/boukensha/tasks/player.py` | Task configuration helpers |
| `src/boukensha/backends/*.py` | Per-provider serialization, response parsing, and model metadata |
| `prompts/system.md` | Default system prompt used when a task does not override it |

## Session Logs

Each `Logger` instance creates a session id and writes one log file for that session:

```text
.boukensha/sessions/<session-id>.jsonl
```

Every line is a complete JSON object with `session_id`, `at`, and `phase` fields, plus phase-specific data. This keeps logs grep/tail friendly and machine readable.

```json
{"phase":"session_start","session_id":"20260528T143011Z-a1b2c3d4","at":"2026-05-28T10:30:11-04:00"}
{"phase":"iteration","n":1,"max":25,"session_id":"20260528T143011Z-a1b2c3d4","at":"2026-05-28T10:30:11-04:00"}
```

Model response lines include the active task, provider, model, normalized token counts, and estimated USD cost when the backend has token pricing data:

```json
{"phase":"response","task":"player","provider":"anthropic","model":"claude-haiku-4-5","input_tokens":1000,"output_tokens":100,"cost_usd":0.0015}
```

## Logger API

| Method | Phase | Logs |
|---|---|---|
| `iteration(n, max)` | `iteration` | loop counter |
| `limit_reached(kind, n, max)` | `limit_reached` | iteration ceiling hit before wind-down |
| `prompt(messages, tools)` | `prompt` | message count/content, tool count/names |
| `tool_call(name, args)` | `tool_call` | tool name and arguments |
| `tool_result(name, result, ok=True, error=None)` | `tool_result` | stringified tool result, success flag, error message |
| `response(text, usage=None, stop_reason=None, task=None, backend=None)` | `response` | response text, token usage, task/provider/model, estimated cost |
| `turn_end(reason, iterations, tokens=None)` | `turn_end` | why and after how many iterations the turn ended |
| `raw(data)` | `raw` | raw provider response, only when debug mode is enabled |

## Task Configuration

Step 6 uses the same task-based settings shape as prior steps:

```yaml
tasks:
  player:
    provider: anthropic
    model: claude-haiku-4-5
    prompt_override:
      system: true
```

When `prompt_override.system` is true, the player task reads `.boukensha/prompts/player/system.md`. Otherwise it falls back to this step's shipped `prompts/system.md`.

Default usage:

```python
from boukensha import Agent, Logger

logger = Logger()
agent = Agent(
    context=ctx,
    registry=registry,
    builder=builder,
    client=client,
    logger=logger,
    task_settings=player_settings,
)
```

If no `logger` is passed to `Agent`, one is constructed automatically.

You can also provide a session id or override the destination directory:

```python
Logger(session_id="manual-session")
Logger(dir="/tmp/boukensha-sessions")
```

For compatibility, `log=` still accepts an explicit file path (takes precedence over `dir`), but normal usage should write under `.boukensha/sessions`.

## Debug Events

Call `boukensha.debug()` before running the agent to include raw provider responses in the log:

```python
import boukensha

boukensha.debug()
```

`boukensha` also exposes `quiet()`/`loud()`/`is_quiet()` as package-wide state for future steps — Step 6 carries the flag but nothing consumes it yet.

## Tool Failures No Longer Crash the Agent

`Agent._handle_tool_calls` wraps each `registry.dispatch(...)` call in a `try/except`. If a tool raises, the exception is logged (`tool_result(ok=False, error=...)`) and turned into an `"ERROR: <ExceptionClass>: <message>"` string fed back to the model as the tool result — the loop continues instead of crashing.

## Considerations

**The Logger only reads data handed to it.** It never talks to the network or a backend directly, beyond duck-typed attribute reads (`backend.model`, `backend.usage_unit`, `backend.usage_level`, `backend.estimate_cost`) that already exist on every backend since Step 5.

**Console diagnostics are gone.** Step 5 printed `[iteration N/M]` and tool call/result lines to stdout. Step 6 replaces those with structured JSONL events — nothing about the loop itself prints to the console anymore.

**Assistant-message ordering is preserved.** The response log for a tool-use turn is written before the assistant message is added to context, which happens before any tool_call/tool_result events — same ordering guarantee as Step 5, now with logging interleaved.

## Run Example

```sh
./week1_baseline/bin/python/06_the_logger
```
