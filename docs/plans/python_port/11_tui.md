# Python Port Plan — 11 · A Terminal UI

## Goal

Port the step-11 delta into the already-copied
`week1_baseline/python/11_tui` snapshot (confirmed identical to completed
Python step 10, `10_standard_tool_library`, via `diff -rq` — the directory
already exists as an untracked copy; this plan's job is entirely the delta
below, not the copy itself).

The end state: `boukensha.repl()` gains a `tui:` keyword (default `True`)
that wraps the existing plain-text REPL in a structured, full-screen terminal
UI — a scrollable conversation viewport, a live progress line while the
agent is working, a single-line input box, and an always-on status bar. The
`Repl` class keeps owning all session logic (turn counting, slash commands,
agent dispatch); the TUI only replaces how it reads input and writes output.

## Source of truth and scope

Diffing `10_standard_tool_library` against `11_tui` directly in ruby shows a
small, contained set of changes:

| Ruby file | What changed |
|---|---|
| `Gemfile`, `boukensha.gemspec`, `Gemfile.lock` | add the `charm` gem (bubbletea + lipgloss + bubbles + friends), a per-platform native dependency |
| `lib/boukensha/version.rb` | `0.10.0` → `0.11.1` |
| `lib/boukensha/tui.rb` | **new.** `Boukensha::Tui` — wraps a `Repl`, drives a bubbletea event loop, four-zone layout |
| `lib/boukensha/repl.rb` | `Repl` refactored for composability: `attr_reader :logger, :context, :model, :version` added; `banner` moves from private to public; `on_output(&block)` (redirect output through a callback instead of `puts`/`gets`); `handle_command(input)` (slash-command dispatch extracted from `start`, now public, returns `:quit`/`:command`/`nil`); `run_turn(input)` (already public, now routed through a private `output` helper instead of `puts`); `start` rewritten to call `handle_command`/`output` and skip printing `PROMPT` when an `@output_cb` is registered |
| `lib/boukensha.rb` | `repl` gains `tui: true`; when true and `defined?(Tui)`, `Tui.new(repl).start` instead of `repl.start` |
| `lib/boukensha_loader.rb` | CLI gains `--no-tui`, threading `tui: !no_tui` into `Boukensha.repl` |
| `examples/example.rb` | **comment-only.** Still calls `Boukensha.run` (one-shot); a new comment clarifies the TUI is launched separately via `bin/boukensha` and this file doesn't exercise it |
| `README.md` | documents the TUI, `Repl`'s new public surface, `Logger#subscribe` (predates this step, now documented), `tui:`/`--no-tui` |
| `patches/bubbletea/*` | **new, do not port.** A C-extension patch for a burst-input bug in the `bubbletea` gem's Go FFI binding (multi-byte `read()` chunks lost all but the first key). This is a bug in ruby's *native-extension binding* to a separate Go runtime — it has no Python analogue because the library this plan uses is pure Python with no FFI boundary of that shape. |
| `lib/boukensha/logger.rb`, `lib/boukensha/context.rb`, `lib/boukensha/agent.rb` | **no diff** between the two ruby step directories. `Logger#subscribe`, `Context#tool_count`, and `Agent::MAX_ITERATIONS` all predate step 11 and are already ported in Python (confirmed present at `src/boukensha/logger.py:subscribe`, `src/boukensha/context.py:tool_count`, `src/boukensha/agent.py:MAX_ITERATIONS = 25`) — nothing to do here beyond consuming them from `Tui`. |
| `test/*` | **no diff.** Ruby ships no automated test coverage for `Tui` itself — porting has no reference test suite to match line-for-line. |

Four judgment calls this plan makes, called out so they don't read as
accidental deviations in review:

**1. `charm` (bubbletea/lipgloss/bubbles) → Textual.** There is no Python
binding to Bubble Tea. This port targets
[Textual](https://github.com/Textualize/textual) rather than `prompt_toolkit`
or `urwid`: it's the closest conceptual match to bubbletea's
reactive-model/update/view loop (async event loop, timers, a scrollable log
widget, CSS-like styling standing in for lipgloss), it's pure Python with no
native per-platform build step (unlike `charm`'s native gems — exactly why
ruby needed the `patches/bubbletea` workaround in the first place), and it
ships a headless test harness (`App.run_test()` / `Pilot`) that ruby's charm
setup has no equivalent of. Add `"textual"` to `pyproject.toml`'s
`dependencies` (it pulls in `rich` transitively; matches this repo's
convention of a `pyproject.toml`-based dependency list rather than a bare
`requirements.txt`).

**2. `Thread#raise(Interrupt)` for Esc-cancel → cooperative cancellation.**
Ruby's `Tui#handle_key` does `@turn_thread.raise(Interrupt) if
@turn_thread&.alive?`, asynchronously injecting an exception into the
background thread wherever it currently is — including mid-blocking-I/O,
since MRI checks for pending thread interrupts around blocking reads. Python
has no safe equivalent: injecting an async exception into another thread
(`ctypes.pythonapi.PyThreadState_SetAsyncExc`) only fires the next time that
thread returns to Python bytecode, so it cannot cut short a blocking HTTP
call already in flight the way ruby's can — it would only take effect once
that call returns anyway, i.e. too late to matter. Rather than ship a
fragile ctypes hack that *looks* like ruby's behavior but silently doesn't
deliver it during the one case that matters (a long-running model call),
this plan adds a small, honest cooperative-cancellation hook to `Agent`
instead: an optional `cancel_event` (a `threading.Event`) checked at the top
of each loop iteration, raising a lightweight `TurnCancelled` exception.
**Accepted gap:** Esc still won't interrupt a single in-flight backend call,
only takes effect at the next iteration/tool-call boundary — call this out
in code review as a deliberate, documented divergence, not a missed port.

**3. Where the interactive TUI actually launches from.** In ruby, the TUI is
reached *only* through the installed gem's `bin/boukensha` executable (via
`boukensha_loader.rb`, which step 10's plan already excluded from the Python
port — no Python gem/loader concept exists). `examples/example.rb` is a
deliberately separate, unchanged one-shot `Boukensha.run` demo; ruby's own
step-11 diff to it is comment-only, and its new comment says exactly this:
*"This is the one-shot (Boukensha.run) demo. The interactive TUI is launched
separately via bin/boukensha and isn't exercised by this file."*
Confirmed locally that Python's `examples/example.py` already mirrors this
split precisely, and did so **before** this step: it calls
`boukensha.run(task=...)` (one-shot), not `repl()` — the same as ruby's
`example.rb`. So `examples/example.py` needs only the equivalent
comment-only touch-up; it must **not** be changed to call `repl()`.

That leaves the question ruby answers with `bin/boukensha`: what does a user
actually run to see the TUI? Python already has the structural analogue,
just not yet wired for `tui:` — `week1_baseline/python/10_standard_tool_library/src/boukensha/cli.py`
(shipped since step 10, registered as the `boukensha` console script via
`pyproject.toml`'s `[project.scripts]`), whose docstring already says *"Mirrors
ruby's `bin/boukensha`: ... just start the interactive REPL"* and whose body
is exactly `boukensha.repl()`. This is the correct, already-established place
to add `--no-tui` handling — not a new file, and not a change to
`examples/example.py`. The step-11 launcher
(`week1_baseline/bin/python/11_tui`) should therefore invoke the installed
`boukensha` console script (forwarding argv) instead of exec'ing
`examples/example.py` the way every prior step's launcher does — a
deliberate, one-line divergence from that convention, because
`examples/example.py` intentionally does not exercise the TUI (matching
ruby), and this step's launcher exists to demonstrate the TUI.

**4. Guarding the `Tui` import.** Ruby's `lib/boukensha.rb` checks
`defined?(Tui)` before using it, tolerating a boot where the charm gem isn't
loaded. Python mirrors this with a top-level `try/except ImportError` around
`from .tui import Tui` (falling back to `Tui = None`), so a `boukensha`
install missing the `textual` extra still works with `tui=False` / `--no-tui`
instead of crashing at import time.

## Python API shape

`repl` gains one new keyword, matching ruby; `run` does not (the TUI only
wraps interactive sessions):

```python
from boukensha import repl

repl()               # default — launches the Textual TUI
repl(tui=False)       # plain terminal REPL, unchanged from step 10
```

```
boukensha              # installed console script — launches the TUI
boukensha --no-tui     # falls back to the plain REPL
```

## Implementation plan

### 1. Bump the version and add the dependency

- `src/boukensha/run.py`: `__version__ = "0.11.1"` (this is where
  `__version__` actually lives locally — `__init__.py` only re-exports it via
  `from .run import run, repl, __version__`).
- `pyproject.toml`: bump `version = "0.11.1"`, update the `description` to
  mention the TUI, and add `"textual"` to `dependencies`.

### 2. Refactor `Repl` for composability

`src/boukensha/repl.py`:

- Add `self._output_cb = None` in `__init__`.
- Add `on_output(self, callback)` storing `callback`.
- Add a private `_output(self, s)`: call `self._output_cb(str(s))` if set,
  else `print(s)`.
- Extract the slash-command `if/elif` chain out of `start()` into a public
  `handle_command(self, task)` returning `"quit"`, `"command"`, or `None`
  (not a command), using `_output` instead of `print` for every message it
  emits (`"Goodbye."`, `HELP`, the quiet/loud/clear confirmations).
- Rename `_run_turn` to a public `run_turn(self, task)`; replace its
  `print()` calls (the blank line + result, and both error branches) with
  `_output`.
- Rename `_banner` to a public `banner(self)` (drop the leading underscore —
  ruby's equivalent move is `banner` shifting above its `private` keyword),
  and update the one internal call site (`start()`).
- Rewrite `start()` to: call `self._output(self.banner())`; only print the
  literal `PROMPT` to stdout when `self._output_cb is None` (matches ruby's
  `unless @output_cb` — Textual drives input itself, no stdout prompt
  needed); read a line; call `handle_command`; break on `"quit"`, `continue`
  on `"command"`; otherwise call `run_turn`.
- `_servers_status_string` stays private (ruby keeps it below `private` too).
- No change needed to make `context`, `model`, `version`, `logger` public —
  they were already plain public attributes; Python has no `attr_reader`
  equivalent to add. (Ruby needed this step because its instance variables
  are private by default; Python's aren't.)

### 3. Add cooperative cancellation to `Agent`

- `src/boukensha/errors.py`: add `class TurnCancelled(Exception): pass`.
- `src/boukensha/agent.py`: add `cancel_event=None` to `Agent.__init__`,
  stored as `self.cancel_event`. At the top of the `while True:` loop in
  `Agent.run()`, immediately after the existing
  `if self._iteration_limit_reached():` block and before
  `self.iteration += 1`, add:
  ```python
  if self.cancel_event is not None and self.cancel_event.is_set():
      raise TurnCancelled()
  ```
- `Repl.run_turn`: construct a fresh `self._cancel_event = threading.Event()`
  per call (exposed as an instance attribute so a driving `Tui` can `.set()`
  it), pass `cancel_event=self._cancel_event` into the `Agent(...)` it
  builds, and add `except TurnCancelled:` alongside the existing
  `LoopError`/`ApiError` handling, routing `"(interrupted)"` through
  `_output`.

### 4. Port `Tui` as a Textual `App`

Add `src/boukensha/tui.py` with a `Tui` class wrapping a `Repl`, mirroring
`Boukensha::Tui` (`week1_baseline/ruby/11_tui/lib/boukensha/tui.rb`)
zone-for-zone:

- **Constants**: `SPINNER_FRAMES = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]`
  (ruby's exact 10-glyph Braille set), `TICK_MS = 60`.
- **Layout** (`compose()`): a `RichLog` (`wrap=True, markup=True,
  auto_scroll=True`) for the conversation viewport; a `Static` for the
  progress/idle-status line; an `Input` (single-line — ruby's `TextArea` is
  pinned to `height = 1`, so `Input` is the faithful match, not a multi-line
  widget) with `placeholder="Type a message…"`; a `Static` for the always-on
  status bar.
- **Startup** (`on_mount`): append `self._repl.banner()` to the log; call
  `self._repl.on_output(self._on_repl_output)`; call
  `self._repl.logger.subscribe(self._on_event)`; start
  `self.set_interval(TICK_MS / 1000, self._tick)` driving the spinner frame
  and elapsed-time counter while a turn is active, and refreshing the status
  clock either way.
- **Event queue**: `_on_repl_output` and `_on_event` (the logger subscriber)
  are called from the *background turn thread*, not the Textual event loop —
  mirror ruby's `Queue` + drain-on-tick pattern exactly rather than mutating
  Textual widgets directly from that thread: push onto a `queue.Queue`, and
  have `_tick` drain it (non-blocking `get_nowait()` loop) and apply the
  updates. This is not just style-parity with ruby; it's the correct thing
  to do under Textual too — only the app's own event-loop thread should
  mutate widget state.
- **Live progress state**: a plain dict (`active`, `spinner_idx`,
  `start_time`, `elapsed`, `current_action`, `iteration`,
  `tool_call_count`, `turn_input_tokens`, `turn_output_tokens`), rebuilt
  fresh in `_launch_turn` exactly like ruby's `@live` hash. Render it into
  the progress `Static` on every `_tick`: when active, the spinner-frame
  line (`"{frame} {action}  (iter {iter}/{max} · {secs}s · ↑ {itok} · ↓
  {otok} · {calls} calls)"`, `max` from `Agent.MAX_ITERATIONS`); when idle,
  `"  [ready]   ctx {used}   {turns} turns"` using session-accumulated input
  tokens and turn count.
- **Status bar**: `" boukensha v{version} · {model}  ·  ctx {used}  ·
  {tools} tools  ·  {clock} "`, left-justified/padded to the terminal width
  — reuse `self._repl.context.tool_count()`, `self._repl.model`,
  `self._repl.version` (all public per step 2).
- **Keybindings** (Textual `BINDINGS` + `on_input_submitted`):
  - `ctrl+c`, `ctrl+d` → quit (`self.exit()`).
  - `escape` → if a turn thread is running, `self._cancel_event.set()` (see
    step 3) instead of ruby's `Thread#raise` — the one documented behavioral
    gap (accepted above).
  - `ctrl+l` → `self._repl.handle_command("/clear")`, reset the TUI's own
    `turn_count` to `0`.
  - `pageup`/`pagedown` → scroll the `RichLog` (`scroll_up(5)`/
    `scroll_down(5)`, matching ruby's `@viewport.scroll_up(5)`/
    `scroll_down(5)`).
  - `Input.Submitted` (Textual's enter-key event, replacing ruby's manual
    `"enter"` case in `handle_key`): read `event.value`, clear the input; if
    it starts with `/`, call `self._repl.handle_command(...)`, exit on
    `"quit"`; else append `"> {input}"` to the log and call
    `self._launch_turn(input)`.
- **Agent thread** (`_launch_turn`): identical shape to ruby's —
  `threading.Thread(target=self._run_turn_thread, args=(input,),
  daemon=True).start()`, where the thread body calls `self._repl.run_turn`,
  catches `TurnCancelled` (enqueue `{"phase": "turn_interrupted"}`) and any
  other `Exception` (enqueue `{"phase": "turn_error", "error": str(e)}`), and
  always enqueues `{"phase": "turn_complete"}` in a `finally` block so the
  progress line always clears even on an unexpected error.
- **Event handling** (`_on_event`, draining the queue on tick): dispatch on
  `event["phase"]` exactly matching ruby's `handle_event` cases —
  `"iteration"` (update `iteration`/`current_action`), `"tool_call"` (update
  `current_action`, increment `tool_call_count`), `"tool_result"` (set
  `current_action = "Awaiting result…"`), `"response"` (accumulate
  `turn_input_tokens`/`turn_output_tokens` and the session-level totals from
  `event["usage"]`), `"turn_complete"` (`active = False`, increment
  `turn_count`), `"turn_interrupted"` (append `"[interrupted]"` to the log),
  `"turn_error"` (append `"[error] {error}"`, `active = False`). These are
  the same phase names already emitted by `Logger` (confirmed in
  `logger.py`: `iteration`, `tool_call`, `tool_result`, `response`) plus the
  three TUI-internal ones (`turn_complete`/`turn_interrupted`/`turn_error`)
  enqueued directly by `_launch_turn`'s thread wrapper, not by the `Logger`.
- **Styling**: Textual CSS (a `Tui.CSS` class attribute) for the four ANSI
  colors ruby's `ANSI_COLORS`/`lip()` helper hard-codes (cyan progress line,
  dim/idle line, bold-green prompt, white-on-gray status bar) — same four
  roles, expressed as Textual CSS selectors instead of per-call
  `Lipgloss::Style` construction.

### 5. Wire `tui=` into `repl()`

- `src/boukensha/run.py`: guard-import at module top,
  ```python
  try:
      from .tui import Tui
  except ImportError:
      Tui = None
  ```
  (judgment call 4). Add `tui: bool = True` to `repl(...)`'s signature.
  Change the tail of `repl()` from constructing `Repl(...)` and immediately
  calling `.start()` to:
  ```python
  repl_instance = Repl(...)
  if tui and Tui is not None:
      Tui(repl_instance).run()   # Textual App.run(), not .start()
  else:
      repl_instance.start()
  ```
  (Textual's own convention names the entry point `run()`; there is
  intentionally no `Tui.start` so there's exactly one way to launch it.)
- `src/boukensha/__init__.py`: add `Tui` and `TurnCancelled` to the imports
  and `__all__` (mirroring the existing "New in this step" comment-block
  convention already used for `mcp`/`tools` in step 10).
- `run()` (the one-shot, non-interactive function) is untouched — ruby's own
  `Tui` only ever wraps `Repl`, never `Agent.run` directly.

### 6. Wire `--no-tui` into `cli.py`, touch up the example, add the launcher

- `src/boukensha/cli.py` (already exists, installed as the `boukensha`
  console script via `pyproject.toml`'s `[project.scripts]`, and already the
  Python analogue of ruby's `bin/boukensha`): update `main()` to check
  `"--no-tui" in sys.argv` and call `boukensha.repl(tui=not no_tui)`,
  matching ruby's `boukensha_loader.rb`
  (`no_tui = ARGV.delete("--no-tui"); Boukensha.repl(tui: !no_tui)`). Update
  its module docstring to mention `--no-tui`. Do **not** add
  `BOUKENSHA_PATH`/`~/.boukensharc`-style path resolution — step 10's plan
  already scoped that out as gem-loader-only, and nothing about the TUI
  changes that call.
- `examples/example.py`: comment-only touch-up mirroring ruby's actual
  step-11 diff to `example.rb` — add a note that this remains the one-shot
  `boukensha.run()` demo and the interactive TUI is launched separately via
  the `boukensha` console script (`week1_baseline/bin/python/11_tui`). Do
  **not** change its call from `run(task=...)` to `repl(...)` (judgment
  call 3) — that would be a bigger behavioral change than anything ruby's
  own step-11 diff makes to `example.rb`.
- Add `week1_baseline/bin/python/11_tui`:
  ```bash
  #!/bin/bash
  cd "$(dirname "$0")/../../python/11_tui" || exit 1
  source ../../../venv/bin/activate
  pip install -e . > /dev/null 2>&1
  boukensha "$@"
  ```
  This deliberately diverges from every prior step's launcher (`python3
  examples/example.py`) by invoking the installed console script instead,
  and forwards argv so `week1_baseline/bin/python/11_tui --no-tui` reaches
  `cli.py`'s `--no-tui` check (judgment call 3).

### 7. Rewrite the README

Replace the copied step-10 README with step-11 documentation: the Textual
TUI's four-zone layout (reuse ruby's ASCII diagram — the shape is
identical), the keybinding table, `repl(tui=...)` and the `boukensha
--no-tui` console-script flag, `Repl`'s new public surface (`on_output`,
`handle_command`, `run_turn`, `banner`), `Logger.subscribe` (predates this
step — document it now since `Tui` is its first consumer), and a short
"Technical Considerations" note on the Esc/cancellation gap from judgment
call 2. Do not carry forward ruby's `charm`/native-gem/patch narrative —
Textual has no analogous native-extension concern.

## Target files

```text
week1_baseline/python/11_tui/                 (already copied from 10_standard_tool_library)
  pyproject.toml                              version 0.11.1, add textual dependency
  README.md                                   replace step-10 documentation
  src/boukensha/
    __init__.py                               export Tui, TurnCancelled
    run.py                                    __version__ bump; guarded Tui import; tui= wiring in repl()
    agent.py                                  add cancel_event param + TurnCancelled check
    errors.py                                 add TurnCancelled
    repl.py                                   on_output, handle_command, public run_turn/banner
    tui.py                                    new: Textual App wrapping Repl
    cli.py                                    add --no-tui argv handling
  examples/example.py                         comment-only touch-up (still one-shot run(), unchanged behavior)
week1_baseline/bin/python/11_tui              new launcher — execs installed `boukensha` console script, forwards argv
```

Everything else under `week1_baseline/python/11_tui/` (`config.py`,
`context.py`, `registry.py`, `run_dsl.py`, `logger.py`, `client.py`,
`message.py`, `prompt_builder.py`, `tool.py`, `state.py`, `backends/`,
`mcp/`, `tools/`, `tasks/`, `examples/mcp_mud_demo.py`, `test/`) carries over
from `10_standard_tool_library` unchanged — there is no ruby diff touching
them.

## Dependency Chain

```
11_tui (Tui, tui=, on_output, handle_command, public run_turn/banner, cancel_event/TurnCancelled, --no-tui)
    ↓ extends/depends on
10_standard_tool_library (Mcp::Client, Tools::Mcp, working_dir, mcp_servers, tool_names)
    ↓ extends/depends on
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

**Action**: Verify `10_standard_tool_library` is installed/importable
(`pip install -e .` against the repo-root `venv`) before starting this port.

## Verification

Ruby ships no automated `Tui` test suite to match, so verification here leans
more on direct interaction than step 10's did:

1. Compile every step-11 Python file; import `repl`, `Repl`, `Tui`, `Agent`,
   `TurnCancelled` from `boukensha`.
2. Assert `Repl.handle_command` returns `"quit"` for `/exit`/`/quit`,
   `"command"` for `/help`/`/quiet`/`/loud`/`/clear` (and performs their
   side effects), and `None` for a non-command string — with no stdout
   printing when `on_output` is registered, only calls to the callback.
3. Assert `Repl.run_turn`, given a fake client/backend, routes its result (or
   `LoopError`/`ApiError`/`TurnCancelled` message) through a registered
   `on_output` callback instead of `print`.
4. Assert `Agent.run()` raises `TurnCancelled` promptly once `cancel_event`
   is set, at the next iteration boundary, without needing a real backend
   call to complete first.
5. Using Textual's headless test harness (`async with app.run_test() as
   pilot`), drive the TUI without a real terminal: type into the input and
   press enter, assert a fake/stubbed `Repl` receives the input and the
   conversation log grows; press `ctrl+l` and assert `/clear` fires; press
   `escape` mid-turn and assert the cancel event gets set; press `ctrl+c`/
   `ctrl+d` and assert the app exits. This is more coverage than ruby has for
   its own `Tui`, made possible by Textual's harness — call this out as a
   net improvement, not scope creep.
6. Assert `boukensha.cli.main()` calls `repl(tui=True)` by default and
   `repl(tui=False)` when `--no-tui` is present in `sys.argv` (patch
   `boukensha.repl` in the test rather than launching a real TUI).
7. Manually run `week1_baseline/bin/python/11_tui` end-to-end against the
   repo's `.boukensha/settings.yaml`: confirm the four zones render, typing
   is not dropped under fast/pasted input (the very bug ruby needed a native
   patch for — Textual should not exhibit it, but check), the progress line
   animates during a real turn, `PgUp`/`PgDn` scroll history, and
   `week1_baseline/bin/python/11_tui --no-tui` falls back to the identical
   plain-text REPL from step 10. Separately confirm
   `python3 examples/example.py` still runs the unchanged one-shot demo
   (never the TUI).

## Acceptance criteria

- `week1_baseline/python/11_tui` exists as a copy-plus-delta of
  `10_standard_tool_library`, with no unrelated files changed.
- `repl(tui=True)` (the default) launches a Textual-based four-zone TUI;
  `repl(tui=False)` / `boukensha --no-tui` is byte-for-byte the same plain
  REPL step 10 shipped.
- `Repl` exposes `on_output`, `handle_command`, a public `run_turn`, and a
  public `banner`, matching ruby's refactor; nothing in `Repl`'s own
  turn/session logic moved into `Tui`.
- Esc interrupts a running turn at the next iteration/tool-call boundary via
  cooperative cancellation (`Agent(cancel_event=...)` / `TurnCancelled`) —
  the one intentional, documented behavioral gap versus ruby's
  `Thread#raise(Interrupt)`, which can (rarely) cut off mid-network-call.
- `examples/example.py` is unchanged in behavior (still the one-shot
  `run()` demo); the interactive TUI is reached only through the `boukensha`
  console script (`cli.py`), exactly mirroring ruby's `bin/boukensha` /
  `examples/example.rb` split.
- No `patches/`-equivalent exists or is needed — Textual is pure Python with
  no native-extension input-buffering bug to work around.
- `pyproject.toml` gains exactly one new dependency (`textual`); no gem-
  packaging, native-build, or rc-file/loader-path-resolution concepts are
  introduced.

## Not Ported (out of scope for this step)

- `patches/bubbletea/*` — a native-extension (Go FFI) input-buffering bug fix
  with no Python analogue, since Textual has no such native boundary.
- Ruby's gem/native-dependency plumbing for `charm` (`Gemfile`,
  `boukensha.gemspec` version bump beyond what maps to `pyproject.toml`,
  `Gemfile.lock`, `boukensha-0.11.1.gem`).
- `boukensha_loader.rb`'s `BOUKENSHA_PATH`/`~/.boukensharc` step-selection
  and rc-file resolution — already excluded by step 10's plan (no Python gem
  install with multiple selectable versions); `cli.py` stays a fixed,
  minimal entry point (`main()` + `--no-tui`), nothing more.
