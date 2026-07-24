import json
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import state

DEFAULT_SESSION_DIR = "sessions"


class Logger:
    """Records each agent run as structured JSON Lines under .boukensha/sessions/."""

    def __init__(
        self,
        session_id: Optional[str] = None,
        dir: Optional[str] = None,
        log: Optional[str] = None,
        snapshot: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.session_id = session_id or self._generate_session_id()
        self.path = Path(log) if log else Path(dir or self._default_dir()) / f"{self.session_id}.jsonl"

        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._log_file = open(self.path, "a")
        self._write_log({"phase": "session_start", **(snapshot or {})})

    def iteration(self, n: int, max: int) -> None:
        self._write_log({"phase": "iteration", "n": n, "max": max})

    def limit_reached(self, kind: str, n: int, max: int) -> None:
        self._write_log({"phase": "limit_reached", "kind": kind, "n": n, "max": max})

    def turn_end(self, reason: str, iterations: int, tokens: Optional[int] = None) -> None:
        self._write_log({
            "phase": "turn_end",
            "reason": reason,
            "iterations": iterations,
            "tokens": tokens,
        })

    def prompt(self, messages: List[Any], tools: Dict[str, Any]) -> None:
        self._write_log({
            "phase": "prompt",
            "message_count": len(messages),
            "messages": [self._serialize_message(m) for m in messages],
            "tool_count": len(tools),
            "tools": list(tools.keys()),
        })

    def tool_call(self, name: str, args: Dict[str, Any]) -> None:
        self._write_log({"phase": "tool_call", "name": name, "args": args})

    def tool_result(
        self, name: str, result: Any, ok: bool = True, error: Optional[str] = None
    ) -> None:
        self._write_log({
            "phase": "tool_result",
            "name": name,
            "result": str(result),
            "ok": ok,
            "error": error,
        })

    def response(
        self,
        text: str,
        usage: Optional[Dict[str, Any]] = None,
        stop_reason: Optional[str] = None,
        task: Optional[Any] = None,
        backend: Optional[Any] = None,
    ) -> None:
        event: Dict[str, Any] = {
            "phase": "response",
            "text": str(text).strip(),
            "usage": usage,
            "stop_reason": stop_reason,
        }
        event.update(self._execution_metadata(task=task, backend=backend, usage=usage))
        self._write_log(event)

    def raw(self, data: Any) -> None:
        if not state.is_debug():
            return
        self._write_log({"phase": "raw", "data": data})

    def close(self) -> None:
        if self._log_file:
            self._log_file.close()

    def __enter__(self) -> "Logger":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _default_dir(self) -> Path:
        return Path(state.config().dir) / DEFAULT_SESSION_DIR

    def _write_log(self, event: Dict[str, Any]) -> None:
        record = {
            **event,
            "session_id": self.session_id,
            "at": datetime.now().astimezone().isoformat(),
        }
        self._log_file.write(json.dumps(record, default=str) + "\n")
        self._log_file.flush()

    @staticmethod
    def _generate_session_id() -> str:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        return f"{ts}-{secrets.token_hex(4)}"

    @staticmethod
    def _serialize_message(msg: Any) -> Dict[str, Any]:
        return {"role": msg.role, "content": msg.content}

    def _execution_metadata(
        self, task: Optional[Any], backend: Optional[Any], usage: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        if not (task or backend or usage):
            return {}

        tokens = self._usage_tokens(usage)
        metadata = {
            "task": self._task_name(task),
            "provider": self._provider_name(backend),
            "model": getattr(backend, "model", None),
            "usage_unit": getattr(backend, "usage_unit", None),
            "usage_level": getattr(backend, "usage_level", None),
            "input_tokens": tokens.get("input"),
            "output_tokens": tokens.get("output"),
            "cost_usd": self._estimate_cost(backend, tokens),
        }
        return {k: v for k, v in metadata.items() if v is not None}

    @staticmethod
    def _task_name(task: Optional[Any]) -> Optional[str]:
        if task is None:
            return None
        task_name_attr = getattr(task, "task_name", None)
        return task_name_attr() if callable(task_name_attr) else str(task)

    @staticmethod
    def _provider_name(backend: Optional[Any]) -> Optional[str]:
        if backend is None:
            return None
        name = backend.__class__.__name__
        return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name).lower()

    def _usage_tokens(self, usage: Optional[Dict[str, Any]]) -> Dict[str, Optional[int]]:
        usage = usage or {}
        return {
            "input": self._first_integer(
                usage, "input_tokens", "prompt_tokens", "promptTokenCount", "prompt_eval_count"
            ),
            "output": self._first_integer(
                usage, "output_tokens", "completion_tokens", "candidatesTokenCount", "eval_count"
            ),
        }

    @staticmethod
    def _first_integer(d: Dict[str, Any], *keys: str) -> Optional[int]:
        for key in keys:
            value = d.get(key)
            if value is not None:
                try:
                    return int(value)
                except (TypeError, ValueError):
                    return None
        return None

    @staticmethod
    def _estimate_cost(backend: Optional[Any], tokens: Dict[str, Optional[int]]) -> Optional[float]:
        if backend is None or not hasattr(backend, "estimate_cost"):
            return None
        if tokens.get("input") is None or tokens.get("output") is None:
            return None
        return backend.estimate_cost(input_tokens=tokens["input"], output_tokens=tokens["output"])
