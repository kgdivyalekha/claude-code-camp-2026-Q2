from typing import Any, Dict, List

from .context import Context


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

    def to_tools(self) -> List[Dict[str, Any]]:
        return self.backend.to_tools(self.context.tools)

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
