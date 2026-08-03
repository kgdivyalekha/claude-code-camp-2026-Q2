from typing import Any, Dict, List, Optional

from .context import Context
from .tokens.gate import gate  # M4: Tool gating


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

    def to_tools(self, phase: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get tools for API payload, optionally filtered by phase (M4).

        Args:
            phase: Game phase for tool gating ("exploring", "fighting", "trading", "full").
                   If None, uses context's current_phase.

        Returns:
            List of tool definitions formatted for the backend API.
        """
        if phase is None:
            phase = self.context.current_phase

        # M4: Filter tools by phase
        visible_tools = gate().visible_tools_dict(phase, self.context.tools)
        return self.backend.to_tools(visible_tools)

    def to_api_payload(
        self, max_output_tokens: int = 1024, tools: Any = None
    ) -> Dict[str, Any]:
        return self.backend.to_payload(
            self.context, max_output_tokens=max_output_tokens, tools=tools
        )

    def headers(self) -> Dict[str, str]:
        return self.backend.headers()

    def url(self) -> str:
        return self.backend.url()

    def parse_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        return self.backend.parse_response(response)
