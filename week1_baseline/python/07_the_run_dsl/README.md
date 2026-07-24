# The Run DSL

`boukensha.run(...)` is a single top-level entry point. Every previous step required manually creating and wiring together a `Context`, `Registry`, `Backend`, `PromptBuilder`, `Client`, `Logger`, and `Agent`. This step hides all of that behind one function call plus an optional tool-registration callback.

## New Files (Step 07)

| File | Description |
|---|---|
| `src/boukensha/run.py` | The `run()` entry point — resolves defaults, wires every primitive together, runs the agent, and always closes the logger |
| `src/boukensha/run_dsl.py` | `RunDSL` — a tiny object exposing only a `tool` decorator, passed into your `configure` callback |

## Carried Forward (Steps 00-06)

| File | Description |
|---|---|
| `src/boukensha/agent.py` | The agent loop — sends requests, dispatches tools, and knows when to stop |
| `src/boukensha/logger.py` | Structured JSONL event logging for every phase of an agent turn (now also supports `turn(n)` and `subscribe(callback)`) |
| `src/boukensha/state.py` | Package-wide runtime state: cached `Config`, `quiet`/`loud`, `debug` |
| `src/boukensha/client.py` | Makes HTTP requests to LLM APIs with retry logic and error handling |
| `src/boukensha/prompt_builder.py` | Delegates serialization and response parsing to the active backend |
| `src/boukensha/tasks/base.py`, `src/boukensha/tasks/player.py` | Task configuration helpers |
| `src/boukensha/backends/*.py` | Per-provider serialization, response parsing, and model metadata |
| `prompts/system.md` | Default system prompt used when a task does not override it |

## Before and after

**Step 6 — manual plumbing:**

```python
from boukensha import Config, Context, PromptBuilder, Client, Registry, Agent, Logger
from boukensha.tasks import Player
from boukensha.backends import Anthropic

config = Config()
player_settings = config.tasks("player") or {}
system_prompt = Player.system_prompt(player_settings, user_prompts_dir=config.user_prompts_dir, default_prompts_dir=Config.PROMPTS_DIR)

ctx = Context(task=Player, system=system_prompt)
registry = Registry(ctx)
backend = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"], model=Player.model(player_settings))
builder = PromptBuilder(ctx, backend)
client = Client(builder)
logger = Logger()
agent = Agent(context=ctx, registry=registry, builder=builder, client=client, logger=logger, task_settings=player_settings)

registry.tool("read_file", description="Read a file", parameters={"path": {"type": "string"}}, block=lambda path: open(path).read())

ctx.add_message("user", "Read lib/boukensha.rb")
agent.run()
```

**Step 7 — just describe what you want:**

```python
import boukensha


def register_tools(dsl):
    @dsl.tool(
        "read_file",
        description="Read a file",
        parameters={"path": {"type": "string", "description": "File path"}},
    )
    def read_file(path):
        return open(path).read()


result = boukensha.run(task="Read lib/boukensha.rb", configure=register_tools)
```

`configure` may be omitted entirely for tool-free runs. The lower-level classes (`Context`, `Registry`, `Agent`, etc.) remain available for advanced/manual construction — `run()` is a convenience wrapper around them, not a replacement API.

## `boukensha.run(...)`

| Option | Default | Description |
|---|---|---|
| `task` | *(required)* | The user message handed to the agent |
| `system` | task's system prompt | System prompt |
| `model` | task's configured model | Model name |
| `backend` | task's configured provider | `"anthropic"`, `"openai"`, `"gemini"`, `"ollama"`, or `"ollama_cloud"` |
| `api_key` | matching `*_API_KEY` env var | Not needed for `"ollama"` |
| `ollama_host` | `"http://localhost:11434"` | Ollama base URL |
| `log` | `None` | Optional JSONL path override; defaults to `.boukensha/sessions/<session-id>.jsonl` |
| `max_output_tokens` | task's configured limit | Per-reply output cap |
| `configure` | `None` | Callback receiving a `RunDSL` instance for tool registration |

Only `None` counts as "omitted" for every optional argument above — an explicit `max_output_tokens=0` is honored as-is, never silently replaced by the task's configured default.

## `RunDSL`

The object passed into your `configure` callback. It exposes exactly one method, `tool`, used as a decorator:

```python
def register_tools(dsl):
    @dsl.tool(
        "list_directory",
        description="List the files in a directory",
        parameters={"path": {"type": "string", "description": "The directory path to list"}},
    )
    def list_directory(path):
        return ", ".join(os.listdir(path))
```

`configure` is invoked with the `RunDSL` instance before the backend is constructed, so tool registration only depends on the `Context`/`Registry`.

## Task Configuration

Step 7 uses the same task-based settings shape as prior steps:

```yaml
tasks:
  player:
    provider: anthropic
    model: claude-haiku-4-5
    prompt_override:
      system: true
```

## Logger Additions

`Logger` gains two members in this step, both currently unused by `Agent`/`run()` — plumbing for a future step:

| Method | Phase | Logs |
|---|---|---|
| `turn(n)` | `turn` | a bare iteration counter, distinct from `iteration`/`turn_end` |
| `subscribe(callback)` | — | registers a callback invoked synchronously with each event dict, after the JSONL line has been written and flushed |

Subscribers see the same event dict passed to the JSONL writer — before `session_id`/`at` are merged in — and never see the `session_start` event (it's written inside `Logger.__init__`, before any caller has a chance to subscribe).

## `LoopError`

`boukensha.errors` re-exposes `LoopError`, dropped in Step 6 for being unused. It remains unused in this step too — carried purely for parity with the underlying Ruby reference, not because anything raises it yet.

## Run Example

```sh
./week1_baseline/bin/python/07_the_run_dsl
```

The example registers two tools (`read_file`, `list_directory`) and asks the agent to read `README.md` and summarize the framework. The logger writes a session JSONL file under `.boukensha/sessions`.
