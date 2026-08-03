"""GuardedRegistry: Permissions + hooks + audit at the tool dispatch choke point.

Wraps the inner Registry. Same surface (tool/tool_names/dispatch), drops
into run.py anywhere a Registry is passed.
"""

from typing import Any, Dict, Optional

from ..logger import Logger
from ..registry import Registry
from .actors import Actor
from .audit import AuditLog
from .hooks import HookRegistry, ToolBlocked
from .permissions import Decision, Policy


class PermissionDenied(Exception):
    """Tool call denied by policy. Caught by Agent._handle_tool_calls and
    converted to an ERROR tool result the model reads."""
    pass


class GuardedRegistry:
    """Decorates a Registry with permission checks, hooks, and audit.

    The only place tools are dispatched, so this is where:
    - Permissions are enforced
    - Before/after hooks run
    - Results are compressed
    - Audit trail is written
    """

    def __init__(
        self,
        inner: Registry,
        *,
        actor: Actor,
        policy: Policy,
        hooks: HookRegistry,
        logger: Logger,
        audit: AuditLog,
    ):
        self._inner = inner
        self._actor = actor
        self._policy = policy
        self._hooks = hooks
        self._log = logger
        self._audit = audit

    def tool(self, *args, **kwargs) -> None:
        """Register a tool. Delegates to inner Registry."""
        return self._inner.tool(*args, **kwargs)

    def tool_names(self) -> list[str]:
        """List registered tool names. Delegates to inner Registry."""
        return self._inner.tool_names()

    def dispatch(self, name: str, args: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Dispatch a tool call, enforcing permissions and running hooks.

        Flow:
        1. Check permissions
        2. Log permission check
        3. Record in audit trail
        4. Trigger before_tool_call hook
        5. Call inner registry
        6. Trigger after_tool_call hook (result compression happens here)
        7. Return result or raise

        Raises:
            PermissionDenied if policy denies (becomes ERROR tool result)
            Any exception from the tool (propagates to Agent._handle_tool_calls)
        """
        args = args or {}

        # Check permissions
        decision = self._policy.check(self._actor, name, args)
        self._log.event(
            "permission_check",
            actor=self._actor.id,
            tool=name,
            verdict=decision.verdict,
            rule=decision.rule,
        )
        self._audit.record(self._actor, name, args, decision)

        # Enforce deny
        if decision.verdict == "deny":
            raise PermissionDenied(decision.reason)

        # Ask operator (not implemented in this milestone; treated as allow for now)
        if decision.verdict == "ask":
            # TODO: in interactive mode, prompt operator
            pass

        # Before hook (can rewrite args or block)
        try:
            rewritten = self._hooks.trigger(
                "before_tool_call",
                actor=self._actor,
                name=name,
                args=args,
            )
            if rewritten is not None:
                args = rewritten
        except ToolBlocked as e:
            raise PermissionDenied(f"blocked by hook: {e}")

        # Call the tool
        try:
            result = self._inner.dispatch(name, args)
        except Exception as e:
            self._hooks.trigger("on_tool_error", actor=self._actor, name=name, error=e)
            raise

        # After hook (can rewrite result — this is where compression lives)
        rewritten = self._hooks.trigger(
            "after_tool_call",
            actor=self._actor,
            name=name,
            args=args,
            result=result,
        )
        if rewritten is not None:
            result = rewritten

        return result
