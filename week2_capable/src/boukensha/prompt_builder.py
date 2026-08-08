from typing import Any, Dict, List, Optional, TYPE_CHECKING

from .context import Context
from .tokens.gate import gate  # M4: Tool gating

if TYPE_CHECKING:
    from .control.actors import Actor
    from .control.permissions import Policy


class PromptBuilder:
    """Delegates context serialization to a backend strategy.

    PromptBuilder does not make API calls — it only prepares the payload
    format expected by the backend's API.
    """

    def __init__(self, context: Context, backend: Any) -> None:
        self.context = context
        self.backend = backend

    def to_messages(self) -> List[Dict[str, Any]]:
        return self.backend.to_messages(self.context.messages)

    def to_tools(
        self,
        phase: Optional[str] = None,
        actor: Optional["Actor"] = None,
        policy: Optional["Policy"] = None,
    ) -> List[Dict[str, Any]]:
        """Get tools for API payload, filtered by phase (M4) and permissions (M5).

        Args:
            phase: Game phase for tool gating ("exploring", "fighting", "trading", "full").
                   If None, uses context's current_phase.
            actor: Actor making the request (for M5 permission pruning).
            policy: Permission policy (for M5 permission pruning).

        Returns:
            List of tool definitions formatted for the backend API.
            Tools are filtered by phase (M4) and then by permissions (M5).
        """
        if phase is None:
            phase = self.context.current_phase

        # M4: Filter tools by phase
        # Note: gate() expects base tool names (e.g., "look") but tools are registered
        # with prefixes (e.g., "tbamud__look"). Strip prefix before filtering.
        visible_names = gate().visible(phase)
        visible_tools = {
            name: tool for name, tool in self.context.tools.items()
            if name.split("__", 1)[-1] in visible_names
        }

        # M5: Prune tools that are statically denied by policy
        if actor is not None and policy is not None:
            denied = policy.statically_denied(actor)
            visible_tools = {
                name: tool for name, tool in visible_tools.items()
                if name not in denied
            }

        return self.backend.to_tools(visible_tools)

    def to_api_payload(
        self, max_output_tokens: int = 1024, tools: Any = None, enable_cache: bool = True
    ) -> Dict[str, Any]:
        return self.backend.to_payload(
            self.context, max_output_tokens=max_output_tokens, tools=tools, enable_cache=enable_cache
        )

    def headers(self) -> Dict[str, str]:
        return self.backend.headers()

    def url(self) -> str:
        return self.backend.url()

    def parse_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        return self.backend.parse_response(response)
