import json
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


class Logger:
    """Session logger that writes events to JSONL format files."""

    DEFAULT_SESSION_DIR = "sessions"

    def __init__(
        self,
        session_id: Optional[str] = None,
        dir: Optional[str] = None,
        log: Optional[str] = None,
        snapshot: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.session_id = session_id or self._generate_session_id()
        self.path = log or str(
            Path(dir or self._default_dir()) / f"{self.session_id}.jsonl"
        )

        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._log_io = open(self.path, "a")
        self._write_log({"phase": "session_start", **(snapshot or {})})

    def iteration(self, n: int, max: int) -> None:
        """Log iteration start."""
        self._write_log({"phase": "iteration", "n": n, "max": max})

    def limit_reached(self, kind: str, n: int, max: int) -> None:
        """Log that a limit was reached."""
        self._write_log({"phase": "limit_reached", "kind": kind, "n": n, "max": max})

    def turn_end(
        self, reason: str, iterations: int, tokens: Optional[int] = None
    ) -> None:
        """Log end of turn."""
        self._write_log(
            {
                "phase": "turn_end",
                "reason": reason,
                "iterations": iterations,
                "tokens": tokens,
            }
        )

    def prompt(self, messages: Any, tools: Dict[str, Any]) -> None:
        """Log the prompt sent to API."""
        self._write_log(
            {
                "phase": "prompt",
                "message_count": len(messages),
                "messages": [self._serialize_message(m) for m in messages],
                "tool_count": len(tools),
                "tools": list(tools.keys()),
            }
        )

    def tool_call(self, name: str, args: Dict[str, Any]) -> None:
        """Log a tool call."""
        self._write_log({"phase": "tool_call", "name": name, "args": args})

    def tool_result(
        self,
        name: str,
        result: Any,
        ok: bool = True,
        error: Optional[str] = None,
    ) -> None:
        """Log tool execution result."""
        self._write_log(
            {
                "phase": "tool_result",
                "name": name,
                "result": str(result),
                "ok": ok,
                "error": error,
            }
        )

    def response(
        self,
        text: str,
        usage: Optional[Dict[str, Any]] = None,
        stop_reason: Optional[str] = None,
        task: Optional[Any] = None,
        backend: Optional[Any] = None,
    ) -> None:
        """Log an API response."""
        event = {
            "phase": "response",
            "text": text.strip() if isinstance(text, str) else str(text).strip(),
            "usage": usage,
            "stop_reason": stop_reason,
        }
        event.update(
            self._execution_metadata(task=task, backend=backend, usage=usage)
        )
        self._write_log(event)

    def raw(self, data: Any) -> None:
        """Log raw API response (debug mode only)."""
        # Note: In Python, we don't have a module-level Boukensha.debug? yet
        # This will be handled by the module functions
        self._write_log({"phase": "raw", "data": data})

    def close(self) -> None:
        """Close the log file."""
        if self._log_io:
            self._log_io.close()

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    def _default_dir(self) -> str:
        """Get the default sessions directory."""
        # Import here to avoid circular dependency
        from . import config

        cfg = config()
        return str(Path(cfg.dir) / self.DEFAULT_SESSION_DIR)

    def _write_log(self, event: Dict[str, Any]) -> None:
        """Write a log event as JSON line."""
        event["session_id"] = self.session_id
        event["at"] = datetime.now(timezone.utc).isoformat()
        self._log_io.write(json.dumps(event) + "\n")
        self._log_io.flush()

    def _generate_session_id(self) -> str:
        """Generate a session ID with timestamp and random hex."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        random_hex = secrets.token_hex(4)
        return f"{timestamp}-{random_hex}"

    def _serialize_message(self, msg: Any) -> Dict[str, Any]:
        """Serialize a message for logging."""
        return {"role": msg.role, "content": msg.content}

    def _execution_metadata(
        self,
        task: Optional[Any] = None,
        backend: Optional[Any] = None,
        usage: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Extract execution metadata from task, backend, and usage."""
        if not any([task, backend, usage]):
            return {}

        tokens = self._usage_tokens(usage)
        metadata = {
            "task": self._task_name(task),
            "provider": self._provider_name(backend),
            "model": backend.model if backend else None,
            "usage_unit": (
                backend.usage_unit
                if backend and hasattr(backend, "usage_unit")
                else None
            ),
            "usage_level": (
                backend.usage_level
                if backend and hasattr(backend, "usage_level")
                else None
            ),
            "input_tokens": tokens["input"],
            "output_tokens": tokens["output"],
            "cost_usd": self._estimate_cost(backend, tokens),
        }
        return {k: v for k, v in metadata.items() if v is not None}

    def _task_name(self, task: Optional[Any]) -> Optional[str]:
        """Get task name."""
        if not task:
            return None
        if hasattr(task, "task_name"):
            return task.task_name()
        return str(task)

    def _provider_name(self, backend: Optional[Any]) -> Optional[str]:
        """Get provider name from backend class."""
        if not backend:
            return None
        class_name = type(backend).__name__
        # Convert CamelCase to snake_case
        result = []
        for i, char in enumerate(class_name):
            if char.isupper() and i > 0:
                result.append("_")
            result.append(char.lower())
        return "".join(result)

    def _usage_tokens(self, usage: Optional[Dict[str, Any]]) -> Dict[str, Optional[int]]:
        """Extract input and output token counts from usage dict."""
        usage = usage or {}
        return {
            "input": self._first_integer(
                usage,
                "input_tokens",
                "prompt_tokens",
                "promptTokenCount",
                "prompt_eval_count",
            ),
            "output": self._first_integer(
                usage,
                "output_tokens",
                "completion_tokens",
                "candidatesTokenCount",
                "eval_count",
            ),
        }

    @staticmethod
    def _first_integer(
        hash_dict: Dict[str, Any], *keys: str
    ) -> Optional[int]:
        """Find first non-None integer value from dict by multiple key options."""
        for key in keys:
            value = hash_dict.get(key)
            if value is not None:
                try:
                    return int(value)
                except (ValueError, TypeError):
                    continue
        return None

    def _estimate_cost(
        self, backend: Optional[Any], tokens: Dict[str, Optional[int]]
    ) -> Optional[float]:
        """Estimate cost in USD if backend supports it."""
        if not backend or not hasattr(backend, "estimate_cost"):
            return None
        if not tokens["input"] or not tokens["output"]:
            return None
        try:
            return backend.estimate_cost(
                input_tokens=tokens["input"], output_tokens=tokens["output"]
            )
        except Exception:
            return None
