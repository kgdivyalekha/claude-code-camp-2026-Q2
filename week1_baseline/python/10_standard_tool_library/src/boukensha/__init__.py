# Boukensha agent loop — backends, tasks, registry, builder, client, agent, logger, run DSL, and REPL
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

# From prior step (06_the_logger)
from .logger import Logger  # noqa: F401
from .state import config, quiet, loud, is_quiet, debug, is_debug  # noqa: F401

# From prior step (07_the_run_dsl)
from .run_dsl import RunDSL  # noqa: F401

# From prior step (08_the_repl_loop)
from .repl import Repl  # noqa: F401

# New in this step (10_standard_tool_library)
from . import mcp  # noqa: F401
from . import tools  # noqa: F401
from .run import run, repl, __version__  # noqa: F401

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
    "RunDSL",
    "config",
    "quiet",
    "loud",
    "is_quiet",
    "debug",
    "is_debug",
    "run",
    "repl",
    "Repl",
    "__version__",
    "tasks",
    "backends",
    "mcp",
    "tools",
]
