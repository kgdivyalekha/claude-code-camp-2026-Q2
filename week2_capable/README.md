# Step 12 — Context Management

When you call an LLM directly you are responsible for the context window.
There is no auto-compacting. This step adds proper token tracking, visual
warnings, and automatic compaction so the agent never silently blows past
the limit — carried on top of the MCP-host architecture and Textual TUI
introduced in earlier steps.

Boukensha ships **no tools of its own**. It is an MCP *host*: every tool the
agent can call comes from an MCP server declared in `settings.yaml`. Want
file access? Point at a filesystem MCP server. Want to play a MUD? Point at
`mud-manager --mcp`.

## What's new

### Accurate context tracking

`Context` now maintains two distinct token counts:

| Attribute | What it measures |
|-----------|-------------------|
| `context_window` | The model's maximum input token capacity, looked up per-model via `boukensha.Models.context_window` |
| `current_tokens` | Tokens actually used in the most recent API call (`usage.input_tokens` from the response) |

Previously the output-token cap (`max_output_tokens`) was easy to confuse
with the context window itself — that's fixed: `context_window` is a
model fact, looked up once, never conflated with a per-call output budget.

The `Agent` updates `current_tokens` after every API response (including
mid-turn tool-use calls), so the display always reflects what the next call
will actually send.

### Context colour coding

The TUI's progress and status lines colour the context indicator based on
how full the window is:

| Usage | Colour | Meaning |
|-------|--------|---------|
| < 70% | Dim | Normal |
| 70–84% | Yellow | Approaching limit |
| ≥ 85% | Red | Compaction imminent |

A `⚠` symbol also appears in the status bar at 85%+.

### Auto-compaction

At the start of each agent turn, if `current_tokens / context_window ≥ 0.85`
(configurable via `agent.compaction_threshold` in `settings.yaml`), the
`Agent` automatically compacts the context before making any API call:

```
[context compacted — 12 messages dropped to free space]
```

Compaction drops the oldest 40% of messages (keeping at least 2) and resets
`current_tokens` to 0. The first API call after compaction will report the
true new size.

### `Context.compact_messages`

```python
dropped = context.compact_messages(target_fraction=0.60)
# -> 12  (number of messages dropped)
```

### `/compact` command

Manual compaction from the REPL or TUI, alongside `/quiet` and `/loud`:

```
boukensha> /compact
(compacted context — 12 messages dropped)
```

### `Logger.compaction` event

```json
{"phase": "compaction", "before": 172000, "dropped": 12, "context_window": 200000}
```

Emitted whenever auto- or manual compaction runs. The TUI subscribes to
this event to show a compaction notice in the conversation view.

### `boukensha.run` / `boukensha.repl` — `context_window=` keyword

`context_window=` overrides the per-model default (looked up from
`boukensha.Models` for the configured model):

```python
boukensha.repl(context_window=128_000)  # override for a non-standard model
```

### Reasoning / thinking normalization

Every backend normalizes provider-native "thinking" output into a common
content-block shape (see `BackendBase`'s doc comment for the full contract):

```python
{"type": "reasoning", "text": "...", "signature": "...", "redacted": False}
```

Anthropic's `thinking`/`redacted_thinking` blocks, Gemini's
`thought`/`thoughtSignature`, and Ollama/Ollama Cloud's `message.thinking`
all map onto this shape. Reasoning blocks are logged via `Logger.reasoning`
and surfaced by `Agent._log_reasoning` as their own event, separate from the
response text. Tool-call preambles (text accompanying a `tool_use` response)
now go through a `Logger.plan` event instead of being folded into the
response placeholder.

### Two independent per-turn ceilings

`Agent` now stops a turn at whichever limit trips first: `max_iterations`
(tool-call rounds) or `max_turn_tokens` (cumulative input+output tokens for
the turn). Both are configurable under settings.yaml's `agent:` block
(`max_iterations`, `max_output_tokens`, `max_turn_tokens`,
`compaction_threshold`), read via `Config.agent_*` properties. This
replaces the previous `tasks.player.*`-derived resolution
(`Task.max_iterations(task_settings)`) — `Task.max_iterations` /
`Task.max_output_tokens` (`tasks/base.py`) are still defined, just no
longer called from `run()`/`repl()`.

### A known, inherited limitation: `response["usage"]` is read raw

`Agent._record_usage` (and every `logger.response(usage=...)` call) reads
`response.get("usage")` directly off the raw backend response, with no
cross-provider normalization. That key only exists in Anthropic's and the
rewritten OpenAI Responses API's raw response shapes — Gemini's usage lives
under `usageMetadata`, and Ollama/Ollama Cloud report
`prompt_eval_count`/`eval_count` with no `usage` key at all. Concretely:

- **Anthropic, OpenAI**: `current_tokens`/`turn_tokens` populate correctly;
  auto-compaction and `max_turn_tokens` trigger as expected; cost-estimation
  logging (`execution_metadata`) reports real figures.
- **Gemini, Ollama, Ollama Cloud**: `current_tokens`/`turn_tokens` stay `0`;
  auto-compaction and `max_turn_tokens` never trigger automatically; cost
  figures don't populate.

`/compact` (the manual command) works identically on every backend
regardless, since it doesn't depend on usage data. This is a faithfully
ported gap, not a Python-specific defect — see
`docs/plans/python_port/12_context.md` (judgment call 1) for the full
reasoning behind porting rather than papering over it.

## MCP host

### `boukensha.mcp.Client`

A minimal MCP-over-stdio client: spawn a server, handshake, `tools/list`,
`tools/call`. Used by `boukensha.tools.mcp.register` (the only module under
`tools/`) to register a server's discovered tools into a registry,
optionally scoping their names with `prefix=`.

### MCP servers replace the old built-in MUD tools

The gemspec-equivalent (`pyproject.toml`) declares **no tool dependencies at
all**. Servers are separate processes and bring their own; boukensha itself
needs only `textual`, for the TUI.

`working_dir=` survives on `boukensha.run`/`.repl`, but only as `Context`
metadata: it registers nothing.

## Terminal UI

`boukensha.Tui` wraps a `Repl` instance and replaces its raw
`print()`/stdin I/O with a structured four-zone display:

```
+------------------------------------------------+
|  conversation viewport (scrollable)             |
+------------------------------------------------+
|  <spinner> live progress line (idle when quiet) |
+------------------------------------------------+
|  boukensha> input box                           |
+------------------------------------------------+
|  status line (always-on)                        |
+------------------------------------------------+
```

The **progress line** shows a spinner, current action, iteration counter
(`n/MAX`), elapsed seconds, token counts (↑ in / ↓ out), and tool call count
while the agent is running. When idle it shows context usage (colour-coded,
see above) and turn count.

The **status line** always shows: version · model · context tokens
used/max (colour-coded, with a `⚠` at 85%+) · registered tool count ·
wall-clock time.

**Keyboard shortcuts:**

| Key | Action |
|-----|--------|
| `Enter` | Submit input or slash command |
| `Esc` | Request cancellation of the running agent turn |
| `Ctrl+L` | Clear conversation history |
| `PgUp` / `PgDn` | Scroll conversation viewport |
| `Ctrl+C` / `Ctrl+D` | Quit |

The agent runs in a background thread so the UI stays responsive during long
turns.

### `boukensha.repl` — `tui=` keyword

```python
from boukensha import repl

repl(tui=True)    # default — launches the Textual TUI
repl(tui=False)   # falls back to the plain terminal REPL
```

The `boukensha --no-tui` console-script flag sets `tui=False` from the
command line.

### `Repl`, composable

`Repl` doesn't hard-code `print()`/`sys.stdin`. Three methods let `Tui` (or
any other front-end) drive it:

| Method | Purpose |
|--------|---------|
| `on_output(callback)` | Route all REPL output through a callback instead of stdout |
| `handle_command(input)` | Process a slash command; returns `"quit"`, `"command"`, or `None` |
| `run_turn(input)` | Run one agent turn and route the result through `on_output` |

### `Logger.subscribe`

```python
logger.subscribe(lambda event: ...)
```

Every structured log event (`iteration`, `tool_call`, `tool_result`,
`response`, `compaction`, `reasoning`, `plan`, etc.) is broadcast to all
registered subscribers as well as being written to the JSONL file. `Tui`
uses this to update the live progress line and conversation view in real
time without polling.

### Cooperative cancellation (`Agent.cancel_event` / `TurnCancelled`)

`Agent` accepts an optional `cancel_event` (a `threading.Event`). At the top
of every loop iteration it checks the event and raises `TurnCancelled` if
set. `Repl.run_turn` builds a fresh event per turn and passes it to the
`Agent` it constructs. This is a Python-only mechanism (ruby cancels via
`Thread#raise(Interrupt)` inside its own `Tui`, with no equivalent in
`Agent`) — see Technical Considerations below.

## The `boukensha` command

`pip install -e .` installs a `boukensha` console script into the active
venv (`[project.scripts]` in `pyproject.toml`, entry point
`boukensha.cli:main`). It takes an optional `--no-tui` flag and otherwise
resolves config the same way as everywhere else in this step (`BOUKENSHA_DIR`
env var, else `~/.boukensha`):

```sh
source venv/bin/activate      # from repo root
pip install -e week1_baseline/python/12_context
BOUKENSHA_DIR=.boukensha boukensha              # TUI
BOUKENSHA_DIR=.boukensha boukensha --no-tui     # plain REPL

# or via the launcher script, which forwards argv:
./week1_baseline/bin/python/12_context
./week1_baseline/bin/python/12_context --no-tui
```

## The one-shot demo

`examples/example.py` calls `boukensha.run(task=...)` once and exits — the
interactive TUI (where `/compact` and the context gauge are visible) is
reached only through the `boukensha` console script above.

```sh
python3 examples/example.py
```

## Tests

```sh
python3 -m unittest discover -s test -t .
```

The `-t .` matters: without an explicit top-level directory, `unittest`
discover imports `test/*.py` as top-level modules instead of as the `test`
package, and `from .helper import McpTestHelper`'s relative import fails.

MCP client/tool-registration tests spawn the real `mud-manager` daemon from
the sibling `week0_explore/mud_manager` checkout against its own built-in
fake MUD; they are skipped automatically if that checkout is absent. No test
in this suite requires a paid provider API call.

## Technical Considerations

These are observations, not bugs to fix in this step — preserving them here
so later layers don't have to rediscover them:

- **`response["usage"]` is read raw, with no cross-provider normalization**
  (see "A known, inherited limitation" above). Automatic context/cost
  tracking is accurate for Anthropic and OpenAI, inert for
  Gemini/Ollama/Ollama Cloud. `/compact` is unaffected.
- **`Context.compact_messages`'s `target_fraction=` parameter is accepted
  but not read** — the drop count is always `ceil(len(messages) * 0.40)`
  regardless of what's passed. Harmless (nobody currently calls it with a
  non-default value) but worth knowing before relying on the parameter.
- **`PromptBuilder.to_messages()` calls `backend.to_messages(...)`**, an
  unused convenience method nothing in the real request path calls
  (`to_api_payload`/`to_payload` is what's actually used). It would raise a
  `TypeError`/`AttributeError` against `Ollama`/`OllamaCloud`/`OpenAI` if
  ever called — `OpenAI`'s method in particular is now named `to_input`,
  not `to_messages`. Dead code, not a live bug, but a footgun if extended.
- **Two settings namespaces exist for conceptually similar things**:
  `tasks.player.*` (provider/model/prompt overrides, still resolved via
  `Task.system_prompt`/`.model`/`.provider`) and `agent.*` (the new per-turn
  circuit breakers: `max_iterations`, `max_output_tokens`,
  `max_turn_tokens`, `compaction_threshold`, read via `Config.agent_*`).
  Worth consolidating in a later step; not attempted here.
- **Esc does not interrupt an in-flight backend call.** Ruby's Esc handler
  uses `Thread#raise(Interrupt)`, which (rarely, but really) can cut off a
  blocking HTTP call already in progress. Python has no safe equivalent —
  injecting an async exception into another thread only takes effect the
  next time that thread returns to Python bytecode, so it cannot pre-empt a
  request that's already in flight. This port instead uses cooperative
  cancellation: `Esc` sets a `threading.Event`, and `Agent.run()` checks it
  at the top of each loop iteration (i.e. between backend calls / tool
  dispatches), raising `TurnCancelled`. **Accepted gap**: pressing Esc during
  a single long model call won't do anything until that call returns, at
  which point the turn stops before the next iteration starts.
- Servers spawn **eagerly** at boot: every `mcp_servers:` entry costs a
  subprocess and a handshake even if the LLM never calls one of its tools.
  Fine at a couple of servers; revisit past that.
- Non-text MCP content blocks (images, embedded resources) are dropped
  rather than rendered — they yield an empty string, not an exception. No
  MUD tool can hit this.
- Every backend still advertises every listed parameter as required, which
  is wrong for third-party servers with genuinely optional params. Fixing it
  means plumbing `inputSchema["required"]` through `boukensha.tool.Tool`,
  which touches every backend's payload builder.
- There is no Python equivalent of ruby's `~/.boukensharc` /
  `boukensha_loader.rb` rc-file / step-selection mechanism — Python steps are
  selected by which package is `pip install -e`'d, not by an rc file pointing
  a shared executable at a step directory. `cli.py` stays a fixed, minimal
  entry point (`main()` + `--no-tui`), nothing more.
