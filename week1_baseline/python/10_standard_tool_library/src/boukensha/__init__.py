# Boukensha agent loop with logging — backends, tasks, registry, builder, client, agent, and logger
# Re-uses config, struct, registry, prompt builder, and client classes from prior steps

# Local struct, config, and registry classes
from .config import Config  # noqa: F401
from .tool import Tool  # noqa: F401
from .message import Message  # noqa: F401
from .context import Context  # noqa: F401
from .errors import UnknownToolError, UnsupportedModelError, ApiError, LoopError  # noqa: F401
from .registry import Registry  # noqa: F401

# From prior step (03_prompt_builder)
from .prompt_builder import PromptBuilder  # noqa: F401
from . import tasks  # noqa: F401
from . import backends  # noqa: F401

# New in step 10 (10_standard_tool_library)
from . import tools  # noqa: F401

# From prior step (04_api_client)
from .client import Client  # noqa: F401

# From prior step (05_agent_loop)
from .agent import Agent  # noqa: F401

# New in this step (06_the_logger)
from .logger import Logger  # noqa: F401

# New in step 08 (08_the_repl_loop)
from .version import VERSION  # noqa: F401
from .repl import Repl  # noqa: F401

# Module-level state for singleton config and debug/quiet flags
_config = None
_debug = False
_quiet = False


def config():
    """Lazy-load and return the singleton Config instance."""
    global _config
    if _config is None:
        _config = Config()
    return _config


def debug_on():
    """Enable debug logging (raw API responses)."""
    global _debug
    _debug = True


def debug_off():
    """Disable debug logging."""
    global _debug
    _debug = False


def debug_enabled():
    """Check if debug logging is enabled."""
    return _debug


def quiet_on():
    """Enable quiet mode (suppress logging output)."""
    global _quiet
    _quiet = True


def loud_on():
    """Disable quiet mode (enable logging output)."""
    global _quiet
    _quiet = False


def quiet_enabled():
    """Check if quiet mode is enabled."""
    return _quiet


def quiet():
    """Enable quiet mode (suppress logging output) — alias for quiet_on()."""
    quiet_on()


def loud():
    """Disable quiet mode (enable logging output) — alias for loud_on()."""
    loud_on()


def run(
    task,
    system=None,
    model=None,
    backend=None,
    api_key=None,
    ollama_host="http://localhost:11434",
    log=None,
    max_output_tokens=None,
    tools_fn=None,
    working_dir=None,
    allowed_commands=None,
    shell_timeout=30,
):
    """One-shot run: send a single task, get a response, return.

    Args:
        task: The task description (user prompt)
        system: System prompt (defaults to config)
        model: Model name (defaults to config)
        backend: Backend provider name (defaults to config)
        api_key: API key for the backend
        ollama_host: Host for Ollama backend
        log: Logger output destination
        max_output_tokens: Maximum tokens in response
        tools_fn: Function that registers tools (receives registry)
        working_dir: Working directory for FileSystem and Shell tools
        allowed_commands: List of allowed commands for Shell tool (None = all allowed)
        shell_timeout: Timeout in seconds for Shell commands (default 30)
    """
    from . import PromptBuilder, Client, Agent, Logger, tasks as tasks_module
    from . import backends as backends_module

    cfg = config()
    task_class = tasks_module.Player
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
        backend = task_class.provider(task_settings).lower()
    if api_key is None:
        import os

        if backend == "anthropic":
            api_key = os.environ.get("ANTHROPIC_API_KEY")
        elif backend == "openai":
            api_key = os.environ.get("OPENAI_API_KEY")
        elif backend == "gemini":
            api_key = os.environ.get("GEMINI_API_KEY")
        elif backend == "ollama_cloud":
            api_key = os.environ.get("OLLAMA_API_KEY")

    ctx = Context(task=task_class, system=system)
    registry = Registry(ctx)

    # Register standard tool modules if working_dir is set
    if working_dir:
        from .tools import FileSystem, Shell
        FileSystem.register(registry, working_dir=working_dir)
        Shell.register(registry, working_dir=working_dir, timeout=shell_timeout, allowed_commands=allowed_commands)

    if tools_fn:
        from .run_dsl import RunDSL

        RunDSL(registry).instance_eval(tools_fn)

    if backend == "anthropic":
        be = backends_module.Anthropic(api_key=api_key, model=model)
    elif backend == "openai":
        be = backends_module.OpenAI(api_key=api_key, model=model)
    elif backend == "gemini":
        be = backends_module.Gemini(api_key=api_key, model=model)
    elif backend == "ollama":
        be = backends_module.Ollama(host=ollama_host, model=model)
    elif backend == "ollama_cloud":
        be = backends_module.OllamaCloud(api_key=api_key, model=model)
    else:
        raise ValueError(
            f"Unknown backend {backend}. Use 'anthropic', 'openai', 'gemini', 'ollama', or 'ollama_cloud'."
        )

    builder = PromptBuilder(ctx, be)
    client = Client(builder)
    effective_max_iterations = task_class.max_iterations(task_settings)
    effective_max_output_tokens = max_output_tokens or task_class.max_output_tokens(
        task_settings
    )
    logger = Logger(
        log=log,
        snapshot={
            "task": task_class.task_name(),
            "max_iterations": effective_max_iterations,
            "max_output_tokens": effective_max_output_tokens,
            "model": model,
            "provider": backend,
        },
    )

    agent = Agent(
        context=ctx,
        registry=registry,
        builder=builder,
        client=client,
        logger=logger,
        task_settings=task_settings,
        max_iterations=effective_max_iterations,
        max_output_tokens=effective_max_output_tokens,
    )

    ctx.add_message("user", task)
    try:
        return agent.run()
    finally:
        if logger:
            logger.close()


def repl(
    system=None,
    model=None,
    backend=None,
    api_key=None,
    ollama_host="http://localhost:11434",
    log=None,
    max_output_tokens=None,
    tools_fn=None,
    working_dir=None,
    allowed_commands=None,
    shell_timeout=30,
):
    """Interactive REPL: register tools once, then loop reading tasks from stdin.

    Conversation history accumulates across every turn so the agent always sees
    the full transcript. Options are the same as run(), minus the task parameter
    (the user supplies tasks interactively).

    Args:
        system: System prompt (defaults to config)
        model: Model name (defaults to config)
        backend: Backend provider name (defaults to config)
        api_key: API key for the backend
        ollama_host: Host for Ollama backend
        log: Logger output destination
        max_output_tokens: Maximum tokens in response
        tools_fn: Function that registers tools (receives registry)
        working_dir: Working directory for FileSystem and Shell tools
        allowed_commands: List of allowed commands for Shell tool (None = all allowed)
        shell_timeout: Timeout in seconds for Shell commands (default 30)
    """
    from . import PromptBuilder, Client, Logger, tasks as tasks_module
    from . import backends as backends_module

    cfg = config()
    task_class = tasks_module.Player
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
        backend = task_class.provider(task_settings).lower()
    if api_key is None:
        import os

        if backend == "anthropic":
            api_key = os.environ.get("ANTHROPIC_API_KEY")
        elif backend == "openai":
            api_key = os.environ.get("OPENAI_API_KEY")
        elif backend == "gemini":
            api_key = os.environ.get("GEMINI_API_KEY")
        elif backend == "ollama_cloud":
            api_key = os.environ.get("OLLAMA_API_KEY")

    ctx = Context(task=task_class, system=system)
    registry = Registry(ctx)

    if tools_fn:
        from .run_dsl import RunDSL

        RunDSL(registry).instance_eval(tools_fn)

    if backend == "anthropic":
        be = backends_module.Anthropic(api_key=api_key, model=model)
    elif backend == "openai":
        be = backends_module.OpenAI(api_key=api_key, model=model)
    elif backend == "gemini":
        be = backends_module.Gemini(api_key=api_key, model=model)
    elif backend == "ollama":
        be = backends_module.Ollama(host=ollama_host, model=model)
    elif backend == "ollama_cloud":
        be = backends_module.OllamaCloud(api_key=api_key, model=model)
    else:
        raise ValueError(
            f"Unknown backend {backend}. Use 'anthropic', 'openai', 'gemini', 'ollama', or 'ollama_cloud'."
        )

    builder = PromptBuilder(ctx, be)
    client = Client(builder)
    effective_max_iterations = task_class.max_iterations(task_settings)
    effective_max_output_tokens = max_output_tokens or task_class.max_output_tokens(
        task_settings
    )
    logger = Logger(
        log=log,
        snapshot={
            "task": task_class.task_name(),
            "max_iterations": effective_max_iterations,
            "max_output_tokens": effective_max_output_tokens,
            "model": model,
            "provider": backend,
        },
    )

    try:
        Repl(
            context=ctx,
            registry=registry,
            builder=builder,
            client=client,
            logger=logger,
            config_dir=cfg.dir,
            provider=backend,
            model=model,
            version=VERSION,
            api_key=api_key,
            task_settings=task_settings,
            max_iterations=effective_max_iterations,
            max_output_tokens=effective_max_output_tokens,
        ).start()
    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        if logger:
            logger.close()


__all__ = [
    "Config",
    "Tool",
    "Message",
    "Context",
    "Registry",
    "UnknownToolError",
    "UnsupportedModelError",
    "ApiError",
    "LoopError",
    "PromptBuilder",
    "Client",
    "Agent",
    "Logger",
    "Repl",
    "VERSION",
    "tasks",
    "backends",
    "config",
    "debug_on",
    "debug_off",
    "debug_enabled",
    "quiet_on",
    "loud_on",
    "quiet_enabled",
    "quiet",
    "loud",
    "run",
    "repl",
]
