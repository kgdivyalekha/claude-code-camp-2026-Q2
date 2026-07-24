from typing import Optional

from .config import Config

_quiet = False
_debug = False
_config: Optional[Config] = None


def config() -> Config:
    """Memoized default Config instance."""
    global _config
    if _config is None:
        _config = Config()
    return _config


def quiet() -> None:
    global _quiet
    _quiet = True


def loud() -> None:
    global _quiet
    _quiet = False


def is_quiet() -> bool:
    return _quiet


def debug() -> None:
    global _debug
    _debug = True


def is_debug() -> bool:
    return _debug
