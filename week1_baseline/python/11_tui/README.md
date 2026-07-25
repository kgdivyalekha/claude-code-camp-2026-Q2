# Step 11 — A Terminal UI

Boukensha now ships a full terminal UI (TUI) built on
[Textual](https://github.com/Textualize/textual). The plain REPL is still
there and can be selected with `tui=False` (or `--no-tui` from the
`boukensha` console script).

## What's new

### `boukensha.Tui`

Wraps a `Repl` instance and replaces its raw `print()`/stdin I/O with a
structured four-zone display:

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
while the agent is running. When idle it shows context tokens used and turn
count.

The **status line** always shows: version · model · context tokens used ·
registered tool count · wall-clock time.

**Keyboard shortcuts:**

| Key | Action |
|-----|--------|
| `Enter` | Submit input or slash command |
| `Esc` | Request cancellation of the running agent turn |
| `Ctrl+L` | Clear conversation history |
| `PgUp` / `PgDn` | Scroll conversation viewport |
| `Ctrl+C` / `Ctrl+D` | Quit |

The agent runs in a background thread so the UI stays responsive during long
turns. All widget mutation happens on Textual's own event-loop thread — the
background thread only enqueues output/log events onto a `queue.Queue`,
drained on every tick (mirroring the same producer/consumer pattern ruby's
charm-based `Tui` uses with `Queue`).

### `boukensha.repl` — new `tui=` keyword

```python
from boukensha import repl

repl(tui=True)    # default — launches the Textual TUI
repl(tui=False)   # falls back to the plain terminal REPL
```

The `boukensha --no-tui` console-script flag sets `tui=False` from the
command line.

### `Repl` refactored for composability

`Repl` no longer hard-codes `print()`/`sys.stdin`. Three methods let `Tui`
(or any other front-end) drive it:

| Method | Purpose |
|--------|---------|
| `on_output(callback)` | Route all REPL output through a callback instead of stdout |
| `handle_command(input)` | Process a slash command; returns `"quit"`, `"command"`, or `None` |
| `run_turn(input)` | Run one agent turn and route the result through `on_output` |

`banner()` is also a public method now (previously a private `_banner()`).
`context`, `logger`, `model`, and `version` were already plain public
attributes — Python has no `attr_reader`-vs-instance-variable distinction for
this refactor to bridge, unlike ruby.

### `Logger.subscribe`

```python
logger.subscribe(lambda event: ...)
```

Every structured log event (`iteration`, `tool_call`, `tool_result`,
`response`, etc.) is broadcast to all registered subscribers as well as being
written to the JSONL file. This predates step 11 but `Tui` is its first
consumer — it uses `subscribe` to update the live progress line in real time
without polling.

### Cooperative cancellation (`Agent.cancel_event` / `TurnCancelled`)

`Agent` accepts an optional `cancel_event` (a `threading.Event`). At the top
of every loop iteration it checks the event and raises `TurnCancelled` if
set. `Repl.run_turn` builds a fresh event per turn and passes it to the
`Agent` it constructs, catching `TurnCancelled` and printing `(interrupted)`
through `on_output` — the same place `LoopError`/`ApiError` are already
handled.

## The `boukensha` command

`pip install -e .` installs a `boukensha` console script into the active
venv (`[project.scripts]` in `pyproject.toml`, entry point
`boukensha.cli:main`) — the Python analogue of ruby's gem-installed
`bin/boukensha`. It takes an optional `--no-tui` flag and otherwise resolves
config the same way as everywhere else in this step (`BOUKENSHA_DIR` env
var, else `~/.boukensha`):

```sh
source venv/bin/activate      # from repo root
pip install -e week1_baseline/python/11_tui
BOUKENSHA_DIR=.boukensha boukensha              # TUI
BOUKENSHA_DIR=.boukensha boukensha --no-tui     # plain REPL

# or via the launcher script, which forwards argv:
./week1_baseline/bin/python/11_tui
./week1_baseline/bin/python/11_tui --no-tui
```

This is a Python venv script, unrelated to (and non-conflicting with) any
Ruby `boukensha` gem executable on your `PATH` — it only exists while the
venv is active.

## The one-shot demo

`examples/example.py` is unchanged in behavior from step 10 — it still calls
`boukensha.run(task=...)` once and exits. The interactive TUI is reached only
through the `boukensha` console script above, exactly mirroring ruby's split
between `examples/example.rb` (one-shot) and `bin/boukensha` (interactive):

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
