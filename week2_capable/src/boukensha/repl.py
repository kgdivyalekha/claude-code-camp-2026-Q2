import sys
import threading
from pathlib import Path
from typing import Callable, Dict, Optional

from . import state
from .agent import Agent
from .client import Client
from .context import Context
from .errors import ApiError, LoopError, TurnCancelled
from .logger import Logger
from .prompt_builder import PromptBuilder
from .registry import Registry

PROMPT = "boukensha> "

HELP = """Commands:
  /quiet    suppress logging output
  /loud     re-enable logging output
  /clear    wipe conversation history (tools stay)
  /compact  drop oldest 40% of messages to free context
  /exit     leave the REPL
  /help     show this message
"""


class Repl:
    """The interactive session loop.

    Wraps the same primitives as a single ``run()`` call, but instead of
    running once it stays alive: it reads a task from the user, runs the
    agent, prints the reply, and loops back to the prompt.

    The Context is shared across every turn so conversation history
    accumulates naturally — the agent sees the full transcript each time
    it is called.
    """

    def __init__(
        self,
        context: Context,
        registry: Registry,
        builder: PromptBuilder,
        client: Client,
        logger: Logger,
        config_dir: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        version: Optional[str] = None,
        api_key: Optional[str] = None,
        servers: Optional[Dict[str, int]] = None,
        max_iterations: Optional[int] = None,
        max_turn_tokens: Optional[int] = None,
        max_output_tokens: Optional[int] = None,
    ) -> None:
        self.context = context
        self.registry = registry
        self.builder = builder
        self.client = client
        self.logger = logger
        self.max_iterations = max_iterations
        self.max_turn_tokens = max_turn_tokens
        self.max_output_tokens = max_output_tokens
        self.config_dir = config_dir
        self.provider = provider
        self.model = model
        self.version = version
        self.api_key = api_key
        self.servers = servers
        self.turn = 0
        self._output_cb: Optional[Callable[[str], None]] = None
        self._cancel_event: Optional[threading.Event] = None

    def on_output(self, callback: Callable[[str], None]) -> None:
        """Register a callback that receives every string the REPL would
        otherwise print to stdout. When set, print() is suppressed entirely
        and all output is routed through the callback instead. Used by Tui.
        """
        self._output_cb = callback

    def start(self) -> None:
        self._output(self.banner())

        while True:
            if self._output_cb is None:
                print(PROMPT, end="")
                sys.stdout.flush()

            line = sys.stdin.readline()
            if not line:
                break  # EOF / Ctrl-D

            command = line.strip()
            if not command:
                continue

            result = self.handle_command(command)
            if result == "quit":
                break
            if result == "command":
                continue

            self.run_turn(command)

    def handle_command(self, task: str) -> Optional[str]:
        """Handle a slash command. Returns "quit", "command", or None (not a
        command). Output is routed through the registered on_output callback
        if present.
        """
        if task in ("/exit", "/quit"):
            self._output("Goodbye.")
            return "quit"
        elif task == "/help":
            self._output(HELP)
            return "command"
        elif task == "/quiet":
            state.quiet()
            self._output("(logging suppressed — type /loud to re-enable)")
            return "command"
        elif task == "/loud":
            state.loud()
            self._output("(logging enabled)")
            return "command"
        elif task == "/clear":
            self.context.clear_messages()
            self.turn = 0
            self._output("(conversation history cleared)")
            return "command"
        elif task == "/compact":
            dropped = self.context.compact_messages()
            self._output(f"(compacted context — {dropped} messages dropped)")
            return "command"
        return None

    def banner(self) -> str:
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
        servers_stat = self._servers_status_string()

        return (
            "\n"
            "╔══════════════════════════════════════╗\n"
            f"║  BOUKENSHA MUD Assistant (v{ver}){' ' * (9 - len(ver))}║\n"
            "╚══════════════════════════════════════╝\n"
            f"  config:    {config_line}\n"
            f"  provider:  {provider_line}\n"
            f"  servers:   {servers_stat}\n"
            "\n"
            "  /quiet or /loud   toggle logging\n"
            "  /clear           reset conversation history\n"
            "  /compact         free context (drop oldest messages)\n"
            "  /exit or /quit    leave the REPL\n"
        )

    def _servers_status_string(self) -> str:
        # Build the MCP servers line shown in the banner. Every tool the
        # agent has came from one of these, so this doubles as "what can I
        # actually do?". No probing needed: a server that answers tools/list
        # is already connected, and one that didn't is either absent here or
        # took the agent down at boot.
        if not self.servers:
            return "(none configured — the agent has no tools)"
        return "  ".join(f"{name} ({count})" for name, count in self.servers.items())

    def run_turn(self, task: str) -> None:
        self.turn += 1
        self.logger.turn(self.turn)

        self.context.add_message("user", task)

        self._cancel_event = threading.Event()
        agent = Agent(
            context=self.context,
            registry=self.registry,
            builder=self.builder,
            client=self.client,
            logger=self.logger,
            max_iterations=self.max_iterations,
            max_turn_tokens=self.max_turn_tokens,
            max_output_tokens=self.max_output_tokens,
            cancel_event=self._cancel_event,
        )
        try:
            result = agent.run()
        except TurnCancelled:
            self._output("(interrupted)")
            return
        except LoopError as e:
            self._output(f"\n[error] {e}")
            return
        except ApiError as e:
            self._output(f"\n[error] API call failed: {e}")
            return

        # Print the final response outside of the logger so it is always
        # visible, even when state.quiet() is active.
        self._output("")
        self._output(result)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _output(self, s: str) -> None:
        if self._output_cb is not None:
            self._output_cb(str(s))
        else:
            print(s)
