"""Extensible event system for tool calls, movements, and game state changes."""

import asyncio
import logging
import threading
from queue import Queue
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


class ToolBlocked(Exception):
    """Raised by before_tool_call hook to prevent a tool call."""
    pass


class HookRegistry:
    """Sync and async event dispatch with priority ordering.

    Sync hooks (before/after/rewrite) run immediately and can block or transform.
    Async hooks (observe) run in a worker thread, never block.
    """

    def __init__(self, max_async_queue: int = 100):
        self._handlers: Dict[str, list[tuple[int, Callable, bool]]] = {}  # event → [(priority, handler, is_async)]
        self._async_queue: Queue = Queue(maxsize=max_async_queue)
        self._worker_thread = threading.Thread(target=self._async_worker, daemon=True)
        self._worker_thread.start()

    def register(self, event: str, handler: Callable, priority: int = 50, async_: bool = False) -> None:
        """Register a handler for an event.

        Args:
            event: Event name (e.g., 'after_tool_call')
            handler: Callable that receives event payload as kwargs
            priority: Higher priority runs first (0-100, default 50)
            async_: If True, runs in worker thread; must be observer only
        """
        if event not in self._handlers:
            self._handlers[event] = []

        self._handlers[event].append((priority, handler, async_))
        self._handlers[event].sort(key=lambda x: -x[0])  # Sort by priority descending

    def trigger(self, event: str, **payload) -> Any:
        """Trigger an event, running all registered handlers.

        Sync handlers run immediately; their return values are chained
        (if a handler returns a value, the next handler receives it as payload).

        Async handlers are queued and may drop if queue is full.

        Returns:
            The final return value from the last sync handler, or None if no sync handler returned anything.
        """
        if event not in self._handlers:
            return None

        result = None
        for priority, handler, is_async in self._handlers[event]:
            if is_async:
                # Queue async handler; don't wait for result
                try:
                    self._async_queue.put_nowait((handler, payload))
                except:
                    logger.warning(f"hook queue full, dropping {event} handler")
            else:
                # Sync handler: run immediately
                try:
                    handler_result = handler(**payload)
                    if handler_result is not None:
                        result = handler_result
                        payload = handler_result if isinstance(handler_result, dict) else payload
                except ToolBlocked:
                    raise  # Let ToolBlocked propagate to GuardedRegistry
                except Exception as e:
                    logger.exception(f"hook failed: {event}.{handler.__name__}: {e}")

        return result

    def _async_worker(self) -> None:
        """Worker thread for async hooks."""
        while True:
            try:
                handler, payload = self._async_queue.get()
                handler(**payload)
            except Exception as e:
                logger.exception(f"async hook error: {e}")

    def list_handlers(self, event: Optional[str] = None) -> Dict[str, list]:
        """List registered handlers."""
        if event:
            return {event: [h.__name__ for _, h, _ in self._handlers.get(event, [])]}
        return {k: [h.__name__ for _, h, _ in v] for k, v in self._handlers.items()}


# Standard hook events and their signatures

HOOK_EVENTS = {
    # Sync blocking/rewriting hooks
    "before_tool_call": {
        "description": "Can block (raise ToolBlocked) or rewrite args",
        "params": ["actor", "name", "args"],
        "sync_only": True,
    },
    "after_tool_call": {
        "description": "Can rewrite result (return dict)",
        "params": ["actor", "name", "args", "result"],
        "sync_only": True,
    },
    "on_tool_error": {
        "description": "Called when a tool raises; can observe only",
        "params": ["actor", "name", "error"],
        "sync_only": False,
    },

    # Navigation events
    "after_movement": {
        "description": "Called after successful move; async observer",
        "params": ["actor", "from_room", "to_room", "direction"],
        "sync_only": False,
    },
    "on_room_discovered": {
        "description": "Called when a new room is parsed; async observer",
        "params": ["actor", "room"],
        "sync_only": False,
    },

    # Phase and state events
    "on_phase_change": {
        "description": "Called when game phase changes; observer",
        "params": ["actor", "old_phase", "new_phase"],
        "sync_only": False,
    },
    "on_turn_end": {
        "description": "Called at end of turn; async observer",
        "params": ["actor", "reason", "iterations", "tokens"],
        "sync_only": False,
    },
    "on_budget_warning": {
        "description": "Called when approaching budget ceiling",
        "params": ["actor", "spent", "ceiling"],
        "sync_only": False,
    },
}
