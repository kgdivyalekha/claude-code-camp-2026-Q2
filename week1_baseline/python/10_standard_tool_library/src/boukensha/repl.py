import sys
from pathlib import Path
from typing import Any, Dict, Optional

from . import state
from .agent import Agent
from .client import Client
from .context import Context
from .errors import ApiError, LoopError
from .logger import Logger
from .prompt_builder import PromptBuilder
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
        self.servers = servers
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
