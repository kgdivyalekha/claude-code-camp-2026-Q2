from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

import yaml
from dotenv import load_dotenv


class Config:
    """Resolves the ``.boukensha`` config directory in this order:

    1. ``BOUKENSHA_DIR`` environment variable (set before loading ``.env``)
    2. ``~/.boukensha`` (default)
    """

    DEFAULT_DIR = Path.home() / ".boukensha"

    # Default prompts shipped alongside the library code (sibling of src/).
    PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"

    def __init__(self) -> None:
        self.dir: Path = self._resolve_dir()
        self._load_env()
        self.settings: dict[str, Any] = self._load_settings()

    # ---------- provider --------------------------------------------------

    @property
    def provider_type(self) -> str:
        return self.dig("tasks", "player", "provider") or "anthropic"

    @property
    def model(self) -> str:
        return self.dig("tasks", "player", "model") or "claude-haiku-4-5"

    # ---------- tasks -------------------------------------------------

    def tasks(self, name: Optional[str] = None) -> Any:
        """With no argument: full tasks dict from settings.yaml.
        With a name: that task's settings dict, e.g. tasks("player")."""
        all_tasks = self.dig("tasks") or {}
        return all_tasks.get(name) if name else all_tasks

    @property
    def user_prompts_dir(self) -> Path:
        """The user's prompts directory for task prompt overrides."""
        return self.dir / "prompts"

    # ---------- MCP servers ---------------------------------------------

    @property
    def mcp_servers(self) -> dict:
        """MCP servers to plug into the agent, keyed by name. This is where
        ALL of the agent's tools come from — boukensha ships none of its own:

            mcp_servers:
              mud:
                command: mud-manager
                args:    [--mcp]
                prefix:  tbamud
                env:
                  MUD_HOST: your.mud.host      # a stdio server's credentials
                  MUD_NAME: Gandalf            # travel by environment

        Returns {"mud": {"command":, "args":, "env":, "prefix":, "required":}}
        with defaults applied. ``required: false`` lets a server fail to
        spawn without taking the agent down with it.
        """
        raw = self.dig("mcp_servers") or {}
        out: dict = {}
        for name, entry in raw.items():
            entry = entry if isinstance(entry, dict) else {}
            required = entry.get("required")
            out[str(name)] = {
                "command": str(entry.get("command", "")),
                "args": [str(a) for a in (entry.get("args") or [])],
                "env": {str(k): str(v) for k, v in (entry.get("env") or {}).items()},
                "prefix": str(entry["prefix"]) if entry.get("prefix") is not None else None,
                "required": True if required is None else bool(required),
            }
        return out

    # ---------- agent limits ----------------------------------------------
    # Static per-turn circuit breakers, read where the agent is constructed.
    # A value of 0 or nil means "disabled" (no ceiling) — useful for debugging.

    @property
    def agent_max_iterations(self) -> int:
        v = self.dig("agent", "max_iterations")
        return 25 if v is None else int(v)

    @property
    def agent_max_output_tokens(self) -> int:
        v = self.dig("agent", "max_output_tokens")
        return 1024 if v is None else int(v)

    @property
    def agent_max_turn_tokens(self) -> int:
        v = self.dig("agent", "max_turn_tokens")
        return 60_000 if v is None else int(v)

    @property
    def agent_compaction_threshold(self) -> float:
        v = self.dig("agent", "compaction_threshold")
        return 0.85 if v is None else float(v)

    # ---------- low-level helpers ---------------------------------------

    def dig(self, *keys: str) -> Any:
        """Fetch a nested key path from settings, e.g. dig("mud", "host")."""
        node: Any = self.settings
        for key in keys:
            if isinstance(node, dict):
                node = node.get(key)
            else:
                return None
        return node

    def __str__(self) -> str:
        return f"<Boukensha.Config dir={self.dir} provider={self.provider_type} model={self.model}>"

    def __repr__(self) -> str:
        return str(self)

    def _resolve_dir(self) -> Path:
        # 1. Explicit override
        env_dir = os.environ.get("BOUKENSHA_DIR")
        if env_dir:
            return Path(env_dir).expanduser().resolve()

        # 2. ~/.boukensha default
        return self.DEFAULT_DIR.expanduser().resolve()

    def _load_env(self) -> None:
        env_file = self.dir / ".env"
        if env_file.exists():
            load_dotenv(env_file)

    def _load_settings(self) -> dict[str, Any]:
        settings_file = self.dir / "settings.yaml"
        if settings_file.exists():
            return yaml.safe_load(settings_file.read_text()) or {}
        return {}
