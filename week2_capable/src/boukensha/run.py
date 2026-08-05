import os
import sys
import uuid
from typing import Any, Callable, Dict, Optional

from .agent import Agent
from .backends.anthropic import Anthropic
from .backends.gemini import Gemini
from .backends.ollama import Ollama
from .backends.ollama_cloud import OllamaCloud
from .backends.openai import OpenAI
from .client import Client
from .config import Config
from .context import Context
from .logger import Logger
from .models import Models
from .observability.event_store import EventStore
from .prompt_builder import PromptBuilder
from .registry import Registry
from .repl import Repl
from .run_dsl import RunDSL
from .state import config as boukensha_config
from .tasks.player import Player
from .tools import mcp as tools_mcp

try:
    from .tui import Tui
except ImportError:
    Tui = None  # type: ignore[assignment,misc]

# M5 integration: optional GuardedRegistry and control imports
try:
    from .control.guarded_registry import GuardedRegistry
    from .control.actors import Actor, Role
    from .control.permissions import AllowList
    from .control.hooks import HookRegistry
    from .control.audit import AuditLog
except ImportError:
    GuardedRegistry = None  # type: ignore[assignment,misc]

# M7 integration: optional compression hooks and world memory
try:
    from .tokens.compress import CompressionHooks
    from .world.db import WorldDB
    from .observability.navigation import NavigationTracker
except ImportError:
    CompressionHooks = None  # type: ignore[assignment,misc]
    WorldDB = None  # type: ignore[assignment,misc]
    NavigationTracker = None  # type: ignore[assignment,misc]

__version__ = "0.12.0"

_API_KEY_ENV_VARS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "ollama_cloud": "OLLAMA_API_KEY",
}


def _register_mcp_servers(registry: Registry, cfg: Config) -> Dict[str, int]:
    """Register every server in settings.yaml's ``mcp_servers:`` block. This
    is the agent's ONLY source of tools — boukensha ships none of its own.
    Nothing here knows what any particular server does; a MUD daemon and a
    filesystem server are registered by the identical code path.

    A server marked ``required: False`` that fails to spawn is a warning, not
    a fatal error — the agent runs without its tools. A name collision is
    never excused that way: it means the config asks for two tools with one
    name, and answering by dropping one of them silently is the worst option
    available.

    Returns ``{server_name: tool_count}`` for the servers that came up.
    """
    summary: Dict[str, int] = {}
    for name, entry in cfg.mcp_servers.items():
        try:
            client = tools_mcp.register(
                registry,
                command=entry["command"],
                args=entry["args"],
                env=entry["env"],
                prefix=entry["prefix"],
            )
            summary[name] = len(client.tools)
        except tools_mcp.CollisionError:
            raise
        except Exception as e:
            if entry["required"]:
                raise RuntimeError(f"boukensha: MCP server '{name}' failed to start: {e}") from e
            print(
                f"[boukensha] optional MCP server '{name}' failed to start: {e} "
                "— continuing without its tools",
                file=sys.stderr,
            )
    return summary


def _wrap_with_guarded_registry(registry: Registry, session_id: str, logger: Logger) -> Registry:
    """Wrap a registry with GuardedRegistry for M5 permission recording.

    Returns a GuardedRegistry if available, otherwise returns the original registry.
    Creates an AuditLog in .boukensha/events.db to record all tool decisions.
    Wires in M7 compression hooks if available.
    """
    if GuardedRegistry is None:
        return registry

    try:
        # Create actor for this session
        actor = Actor(session_id, session_id, Role.ADMIN, session_id)

        # Permissive default policy: allow all tools
        policy = AllowList(["*__*"])

        # Set up hooks and audit
        hooks = HookRegistry()
        audit = AuditLog(".boukensha/events.db")

        # M7: Register compression hooks if available
        if CompressionHooks is not None and WorldDB is not None:
            try:
                world_db = WorldDB()
                compression = CompressionHooks(world_db, logger=logger)

                # Register compression hooks with high priority (run last)
                hooks.register(
                    "after_tool_call",
                    compression.compress_repeat_rooms,
                    priority=90,
                )
                hooks.register(
                    "after_tool_call",
                    compression.strip_banners,
                    priority=85,
                )
                hooks.register(
                    "after_tool_call",
                    compression.collapse_failures,
                    priority=80,
                )
            except Exception as e:
                print(f"[boukensha] warning: compression hooks setup failed: {e}", file=sys.stderr)

        # M6: Register NavigationTracker if available
        if NavigationTracker is not None and WorldDB is not None:
            try:
                world_db = WorldDB()
                nav_tracker = NavigationTracker(world_db)

                def _navigation_hook(actor, name, args, result):
                    """Adapter to let NavigationTracker observe tool results."""
                    # Strip MCP prefix (e.g., "tbamud__look" -> "look")
                    base_name = name.split("__", 1)[-1] if "__" in name else name

                    if base_name == "look":
                        nav_tracker.on_look_result(result, actor=actor.id if actor else None)
                    elif base_name == "move":
                        # move args should have direction; current room should be cached
                        direction = args.get("direction", "unknown")
                        current = nav_tracker.get_current_room()
                        if current:
                            nav_tracker.on_move_result(
                                result,
                                from_room_id=current,
                                direction=direction,
                                actor=actor.id if actor else None,
                            )
                    return None  # Don't rewrite result

                # Register with low priority (run first, before compression)
                hooks.register(
                    "after_tool_call",
                    _navigation_hook,
                    priority=10,
                )
            except Exception as e:
                print(f"[boukensha] warning: NavigationTracker setup failed: {e}", file=sys.stderr)

        # Wrap and return
        return GuardedRegistry(
            registry,
            actor=actor,
            policy=policy,
            hooks=hooks,
            logger=logger,
            audit=audit,
        )
    except Exception as e:
        print(f"[boukensha] warning: GuardedRegistry initialization failed: {e}", file=sys.stderr)
        return registry


def run(
    task: str,
    system: Optional[str] = None,
    model: Optional[str] = None,
    backend: Optional[str] = None,
    api_key: Optional[str] = None,
    ollama_host: str = "http://localhost:11434",
    log: Optional[str] = None,
    context_window: Optional[int] = None,
    max_output_tokens: Optional[int] = None,
    working_dir: Optional[str] = None,
    configure: Optional[Callable[[RunDSL], None]] = None,
) -> str:
    """The top-level entry point. Wires together every primitive so the
    caller only has to describe *what* to do, not *how* to plumb it.

    The agent ships with NO tools of its own. Every tool it can call arrives
    over an MCP connection, declared in settings.yaml's ``mcp_servers:``
    block (see ``Config.mcp_servers``). Want file access? Point at a
    filesystem MCP server. Want to play a MUD? Point at ``mud-manager --mcp``.
    Boukensha is the host; the servers own the tools.

    ``working_dir``: recorded on the Context as the agent's notion of "where
    it is". It registers nothing — an MCP server that touches the filesystem
    is rooted by its own spawn args. Defaults to the current working
    directory.

    ``context_window``: the model's input token ceiling, used to compute
    context usage and trigger auto-compaction. Defaults to a per-model
    lookup via ``Models.context_window``; override for a non-standard model.

        result = run(task="Summarise lib/boukensha.rb")
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
    if working_dir is None:
        working_dir = os.getcwd()
    if context_window is None:
        context_window = Models.context_window(model)

    ctx = Context(
        system=system,
        context_window=context_window,
        working_dir=working_dir,
        compaction_threshold=cfg.agent_compaction_threshold,
    )
    registry = Registry(ctx)

    _register_mcp_servers(registry, cfg)

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
    effective_max_iterations = cfg.agent_max_iterations
    effective_max_turn_tokens = cfg.agent_max_turn_tokens
    effective_max_output_tokens = (
        max_output_tokens if max_output_tokens is not None else cfg.agent_max_output_tokens
    )
    logger = Logger(
        log=log,
        snapshot={
            "max_iterations": effective_max_iterations,
            "max_turn_tokens": effective_max_turn_tokens,
            "max_output_tokens": effective_max_output_tokens,
            "context_window": context_window,
            "model": model,
            "provider": backend,
        },
    )

    # Automatically attach EventStore to capture events to events.db (M3 optimization)
    event_store = None
    try:
        event_store = EventStore()
        event_store.attach(logger)
    except Exception as e:
        print(f"[boukensha] warning: EventStore initialization failed: {e}", file=sys.stderr)

    # M5 integration: wrap registry with GuardedRegistry for audit trail
    registry = _wrap_with_guarded_registry(registry, task, logger)

    agent = Agent(
        context=ctx,
        registry=registry,
        builder=builder,
        client=client,
        logger=logger,
        max_iterations=effective_max_iterations,
        max_turn_tokens=effective_max_turn_tokens,
        max_output_tokens=effective_max_output_tokens,
    )

    ctx.add_message("user", task)
    try:
        return agent.run()
    finally:
        logger.close()
        if event_store:
            event_store.close()


def repl(
    system: Optional[str] = None,
    model: Optional[str] = None,
    backend: Optional[str] = None,
    api_key: Optional[str] = None,
    ollama_host: str = "http://localhost:11434",
    log: Optional[str] = None,
    context_window: Optional[int] = None,
    max_output_tokens: Optional[int] = None,
    working_dir: Optional[str] = None,
    configure: Optional[Callable[[RunDSL], None]] = None,
    tui: bool = True,
) -> None:
    """Interactive REPL — see ``run()`` for full option documentation.

    Options are the same as ``run()``, minus ``task`` (the user supplies
    tasks interactively).

    ``tui``: ``True`` (default) wraps the REPL in a Textual-based four-zone
    terminal UI. Pass ``tui=False`` to fall back to the plain terminal REPL.
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
    if working_dir is None:
        working_dir = os.getcwd()
    if context_window is None:
        context_window = Models.context_window(model)

    ctx = Context(
        system=system,
        context_window=context_window,
        working_dir=working_dir,
        compaction_threshold=cfg.agent_compaction_threshold,
    )
    registry = Registry(ctx)

    servers = _register_mcp_servers(registry, cfg)

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
    effective_max_iterations = cfg.agent_max_iterations
    effective_max_turn_tokens = cfg.agent_max_turn_tokens
    effective_max_output_tokens = (
        max_output_tokens if max_output_tokens is not None else cfg.agent_max_output_tokens
    )
    logger = Logger(
        log=log,
        snapshot={
            "max_iterations": effective_max_iterations,
            "max_turn_tokens": effective_max_turn_tokens,
            "max_output_tokens": effective_max_output_tokens,
            "context_window": context_window,
            "model": model,
            "provider": backend,
        },
    )

    # Automatically attach EventStore to capture events to events.db (M3 optimization)
    event_store = None
    try:
        event_store = EventStore()
        event_store.attach(logger)
    except Exception as e:
        print(f"[boukensha] warning: EventStore initialization failed: {e}", file=sys.stderr)

    # M5 integration: wrap registry with GuardedRegistry for audit trail
    # Use a session ID based on timestamp for REPL sessions
    session_id = f"repl-{uuid.uuid4().hex[:12]}"
    registry = _wrap_with_guarded_registry(registry, session_id, logger)

    repl_instance = Repl(
        context=ctx,
        registry=registry,
        builder=builder,
        client=client,
        logger=logger,
        max_iterations=effective_max_iterations,
        max_turn_tokens=effective_max_turn_tokens,
        max_output_tokens=effective_max_output_tokens,
        config_dir=str(cfg.dir),
        provider=backend,
        model=model,
        version=__version__,
        api_key=api_key,
        servers=servers,
    )
    try:
        if tui and Tui is not None:
            Tui(repl_instance).run()
        else:
            repl_instance.start()
    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        logger.close()
        if event_store:
            event_store.close()
