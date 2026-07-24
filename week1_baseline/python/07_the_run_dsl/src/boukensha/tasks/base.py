from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional


class Base(ABC):
    """Abstract stateless task. All behaviour is expressed as classmethods
    that accept a settings dict — no instances are created. Concrete
    subclasses define ``task_name``."""

    DEFAULT_MAX_ITERATIONS = 25
    DEFAULT_MAX_OUTPUT_TOKENS = 1024

    @classmethod
    @abstractmethod
    def task_name(cls) -> str:
        raise NotImplementedError(f"{cls.__name__} must define task_name()")

    @classmethod
    def provider(cls, settings: dict[str, Any]) -> str:
        value = settings.get("provider")
        if not value:
            raise ValueError(f"tasks.{cls.task_name()}.provider is required in settings.yaml")
        return value

    @classmethod
    def model(cls, settings: dict[str, Any]) -> str:
        value = settings.get("model")
        if not value:
            raise ValueError(f"tasks.{cls.task_name()}.model is required in settings.yaml")
        return value

    @classmethod
    def is_prompt_override(cls, settings: dict[str, Any], prompt: str = "system") -> bool:
        node = settings.get("prompt_override")
        if not isinstance(node, dict):
            return False
        return node.get(prompt) is True

    @classmethod
    def max_iterations(cls, settings: dict[str, Any]) -> int:
        value = cls._fetch(settings, "max_iterations")
        if value is None:
            return cls.DEFAULT_MAX_ITERATIONS
        return int(value)

    @classmethod
    def max_output_tokens(cls, settings: dict[str, Any]) -> int:
        value = cls._fetch(settings, "max_output_tokens")
        if value is None:
            return cls.DEFAULT_MAX_OUTPUT_TOKENS
        return int(value)

    @classmethod
    def prompt(
        cls,
        settings: dict[str, Any],
        name: str = "system",
        user_prompts_dir: Optional[Path] = None,
        default_prompts_dir: Optional[Path] = None,
    ) -> Optional[str]:
        if cls.is_prompt_override(settings, name):
            text = cls._read_user_prompt(name, user_prompts_dir)
            if text:
                return text

        return cls._read_default_prompt(name, default_prompts_dir)

    @classmethod
    def system_prompt(
        cls,
        settings: dict[str, Any],
        user_prompts_dir: Optional[Path] = None,
        default_prompts_dir: Optional[Path] = None,
    ) -> Optional[str]:
        return cls.prompt(
            settings, "system", user_prompts_dir=user_prompts_dir, default_prompts_dir=default_prompts_dir
        )

    @classmethod
    def _read_user_prompt(cls, prompt_name: str, user_prompts_dir: Optional[Path]) -> Optional[str]:
        if not user_prompts_dir:
            return None
        return cls._read_file(Path(user_prompts_dir) / cls.task_name() / f"{prompt_name}.md")

    @classmethod
    def _read_default_prompt(cls, prompt_name: str, default_prompts_dir: Optional[Path]) -> Optional[str]:
        if not default_prompts_dir:
            return None
        return cls._read_file(Path(default_prompts_dir) / f"{prompt_name}.md")

    @staticmethod
    def _read_file(path: Path) -> Optional[str]:
        return path.read_text().strip() if path.exists() else None

    @staticmethod
    def _fetch(settings: dict[str, Any], key: str) -> Any:
        """Fetch a key from settings, handling both string and other types."""
        if not isinstance(settings, dict):
            return None
        return settings.get(key)
