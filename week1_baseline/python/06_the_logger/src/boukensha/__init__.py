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

# From prior step (04_api_client)
from .client import Client  # noqa: F401

# From prior step (05_agent_loop)
from .agent import Agent  # noqa: F401

# New in this step (06_the_logger)
from .logger import Logger  # noqa: F401

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
    "tasks",
    "backends",
    "config",
    "debug_on",
    "debug_off",
    "debug_enabled",
    "quiet_on",
    "loud_on",
    "quiet_enabled",
]
