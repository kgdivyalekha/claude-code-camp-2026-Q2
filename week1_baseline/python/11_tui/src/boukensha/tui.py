"""Tui wraps a Repl instance and replaces its raw print()/stdin I/O with a
structured four-zone display powered by Textual — the Python analogue of
ruby's charm-based Boukensha::Tui (bubbletea + lipgloss + bubbles).

The Repl continues to own session logic (turn counting, /commands, Agent
dispatch). Tui registers output/event callbacks on the Repl and drives the
Textual event loop.

Layout (top -> bottom):
    +------------------------------------------------+
    |  conversation viewport (scrollable)             |
    +------------------------------------------------+
    |  <spinner> live progress line (idle when quiet) |
    +------------------------------------------------+
    |  boukensha> input box                           |
    +------------------------------------------------+
    |  status line (always-on)                        |
    +------------------------------------------------+
"""

import queue
import threading
import time
from typing import Any, Dict, Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Input, RichLog, Static

from .agent import Agent
from .repl import PROMPT, Repl

SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
TICK_MS = 60


class Tui(App):
    """Wraps a Repl in a full-screen, four-zone Textual UI."""

    CSS = """
    Screen {
        layout: vertical;
    }
    RichLog#log {
        height: 1fr;
        border: none;
    }
    Static#progress {
        height: 1;
        color: #00ffff;
    }
    Input#input {
        height: 3;
        border: tall #00ff00;
    }
    Static#status {
        height: 1;
        background: #808080;
        color: #ffffff;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", show=False),
        Binding("ctrl+d", "quit", show=False),
        Binding("escape", "cancel_turn", "Cancel"),
        Binding("ctrl+l", "clear", "Clear"),
        Binding("pageup", "scroll_up", "Scroll up"),
        Binding("pagedown", "scroll_down", "Scroll down"),
    ]

    def __init__(self, repl: Repl) -> None:
        super().__init__()
        self._repl = repl
        # Named _ctx, not _context: textual.app.App already defines an
        # internal _context attribute (contextvars-based message-pump
        # state) — shadowing it with our own value silently corrupts
        # Textual's event loop and hangs the app before on_mount ever runs.
        self._ctx = repl.context
        self._events: "queue.Queue[Dict[str, Any]]" = queue.Queue()

        self._turn_count = 0
        self._session_input_tokens = 0
        self._session_output_tokens = 0
        self._turn_thread: Optional[threading.Thread] = None

        self._live: Dict[str, Any] = self._idle_live()

    # ------------------------------------------------------------------
    # Textual App interface
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Vertical(
            RichLog(id="log", wrap=True, markup=True, auto_scroll=True),
            Static(id="progress"),
            Input(id="input", placeholder="Type a message…"),
            Static(id="status"),
        )

    def on_mount(self) -> None:
        log = self.query_one("#log", RichLog)
        log.write(self._repl.banner())

        input_widget = self.query_one("#input", Input)
        input_widget.border_title = PROMPT
        input_widget.focus()

        self._repl.on_output(self._on_repl_output)
        self._repl.logger.subscribe(self._on_event)

        self._render_progress()
        self._render_status()
        self.set_interval(TICK_MS / 1000, self._tick)

    # ------------------------------------------------------------------
    # Keybindings
    # ------------------------------------------------------------------

    def action_cancel_turn(self) -> None:
        # Cooperative cancellation only: this sets a flag Agent.run() checks
        # at the next iteration boundary. It cannot interrupt a single
        # in-flight backend call the way ruby's Thread#raise(Interrupt) can —
        # a deliberate, documented gap (see docs/plans/python_port/11_tui.md).
        if self._turn_thread is not None and self._turn_thread.is_alive():
            cancel_event = self._repl._cancel_event
            if cancel_event is not None:
                cancel_event.set()

    def action_clear(self) -> None:
        self._repl.handle_command("/clear")
        self._turn_count = 0

    def action_scroll_up(self) -> None:
        self.query_one("#log", RichLog).scroll_relative(y=-5, animate=False)

    def action_scroll_down(self) -> None:
        self.query_one("#log", RichLog).scroll_relative(y=5, animate=False)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        input_widget = self.query_one("#input", Input)
        input_widget.value = ""
        if not text:
            return

        if text.startswith("/"):
            result = self._repl.handle_command(text)
            if result == "quit":
                self.exit()
                return
            if text == "/clear":
                self._turn_count = 0
            return

        self.query_one("#log", RichLog).write(f"> {text}")
        self._launch_turn(text)

    # ------------------------------------------------------------------
    # Agent thread
    # ------------------------------------------------------------------

    def _launch_turn(self, text: str) -> None:
        self._live = {
            "active": True,
            "spinner_idx": 0,
            "start_time": time.time(),
            "elapsed": 0.0,
            "current_action": "Thinking…",
            "iteration": 0,
            "tool_call_count": 0,
            "turn_input_tokens": 0,
            "turn_output_tokens": 0,
        }

        self._turn_thread = threading.Thread(
            target=self._run_turn_thread, args=(text,), daemon=True
        )
        self._turn_thread.start()

    def _run_turn_thread(self, text: str) -> None:
        # Repl.run_turn already catches TurnCancelled/LoopError/ApiError
        # internally and routes a friendly message through on_output, so
        # only genuinely unexpected exceptions surface here.
        try:
            self._repl.run_turn(text)
        except Exception as e:  # noqa: BLE001 - last-resort safety net
            self._events.put({"phase": "turn_error", "error": str(e)})
        finally:
            self._events.put({"phase": "turn_complete"})

    # ------------------------------------------------------------------
    # Output / event callbacks (called from the background turn thread —
    # never touch widgets here, only enqueue; _tick drains on the app's own
    # event-loop thread)
    # ------------------------------------------------------------------

    def _on_repl_output(self, text: str) -> None:
        self._events.put({"phase": "output", "text": text})

    def _on_event(self, event: Dict[str, Any]) -> None:
        self._events.put(event)

    # ------------------------------------------------------------------
    # Tick: drain the event queue, advance the spinner, refresh the display
    # ------------------------------------------------------------------

    def _tick(self) -> None:
        self._drain_events()
        if self._live["active"]:
            self._live["spinner_idx"] = (self._live["spinner_idx"] + 1) % len(SPINNER_FRAMES)
            self._live["elapsed"] = time.time() - self._live["start_time"]
        self._render_progress()
        self._render_status()

    def _drain_events(self) -> None:
        while True:
            try:
                event = self._events.get_nowait()
            except queue.Empty:
                return
            self._handle_event(event)

    def _handle_event(self, event: Dict[str, Any]) -> None:
        phase = str(event.get("phase"))

        if phase == "output":
            self.query_one("#log", RichLog).write(event.get("text", ""))

        elif phase == "iteration":
            self._live["iteration"] = int(event.get("n") or 0)
            self._live["current_action"] = "Thinking…"

        elif phase == "tool_call":
            self._live["current_action"] = f"Calling tool: {event.get('name')}"
            self._live["tool_call_count"] += 1

        elif phase == "tool_result":
            self._live["current_action"] = "Awaiting result…"

        elif phase == "response":
            usage = event.get("usage") or {}
            itok = int(usage.get("input_tokens") or 0)
            otok = int(usage.get("output_tokens") or 0)
            self._live["turn_input_tokens"] += itok
            self._live["turn_output_tokens"] += otok
            self._session_input_tokens += itok
            self._session_output_tokens += otok

        elif phase == "turn_complete":
            self._live = self._idle_live()
            self._turn_count += 1
            self._turn_thread = None

        elif phase == "turn_error":
            self._live = self._idle_live()
            self.query_one("#log", RichLog).write(f"[error] {event.get('error')}")

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _idle_live(self) -> Dict[str, Any]:
        return {
            "active": False,
            "spinner_idx": 0,
            "start_time": None,
            "elapsed": 0.0,
            "current_action": "idle",
            "iteration": 0,
            "tool_call_count": 0,
            "turn_input_tokens": 0,
            "turn_output_tokens": 0,
        }

    def _render_progress(self) -> None:
        progress = self.query_one("#progress", Static)
        if self._live["active"]:
            frame = SPINNER_FRAMES[self._live["spinner_idx"]]
            action = self._live["current_action"]
            iteration = self._live["iteration"]
            max_iterations = Agent.MAX_ITERATIONS
            secs = int(self._live["elapsed"])
            itok = self._fmt_tokens(self._live["turn_input_tokens"])
            otok = self._fmt_tokens(self._live["turn_output_tokens"])
            calls = self._live["tool_call_count"]
            progress.update(
                f"[cyan]{frame} {action}  (iter {iteration}/{max_iterations} · "
                f"{secs}s · ↑ {itok} · ↓ {otok} · {calls} calls)[/cyan]"
            )
        else:
            used = self._fmt_tokens(self._session_input_tokens)
            progress.update(f"[dim]  [ready]   ctx {used}   {self._turn_count} turns[/dim]")

    def _render_status(self) -> None:
        status = self.query_one("#status", Static)
        ver = self._repl.version or "?.?.?"
        model = self._repl.model or "(model)"
        used = self._fmt_tokens(self._session_input_tokens)
        tools = self._ctx.tool_count()
        clock = time.strftime("%H:%M:%S")
        status.update(
            f" boukensha v{ver} · {model}  ·  ctx {used}  ·  {tools} tools  ·  {clock} "
        )

    @staticmethod
    def _fmt_tokens(n: Any) -> str:
        n = int(n or 0)
        return f"{n / 1000:.1f}k" if n >= 1000 else str(n)
