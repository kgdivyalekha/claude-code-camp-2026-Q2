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

    # ---------- MUD connection -----------------------------------------

    @property
    def mud_host(self) -> str:
        return self.dig("mud", "host") or "localhost"

    @property
    def mud_port(self) -> int:
        return self.dig("mud", "port") or 4000

    @property
    def mud_username(self) -> Optional[str]:
        return self.dig("mud", "username")

    @property
    def mud_password(self) -> Optional[str]:
        return self.dig("mud", "password")

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
        return f"<Boukensha.Config dir={self.dir} tasks={','.join(self.tasks().keys())}>"

    def __repr__(self) -> str:
        return str(self)

    def _resolve_dir(self) -> Path:
        raw = os.environ.get("BOUKENSHA_DIR") or str(self.DEFAULT_DIR)
        return Path(raw).expanduser().resolve()

    def _load_env(self) -> None:
        env_file = self.dir / ".env"
        if env_file.exists():
            load_dotenv(env_file)

    def _load_settings(self) -> dict[str, Any]:
        settings_file = self.dir / "settings.yaml"
        if settings_file.exists():
            return yaml.safe_load(settings_file.read_text()) or {}
        return {}
