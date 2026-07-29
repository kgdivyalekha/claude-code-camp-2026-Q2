from typing import Any, ClassVar, Dict, List, Optional, Union

from ..context import Context
from ..message import Message
from ..tool import Tool
from .base import BackendBase


class Anthropic(BackendBase):
    BASE_URL: ClassVar[str] = "https://api.anthropic.com/v1/messages"
    MODELS: ClassVar[Dict[str, Dict[str, Any]]] = {
        "claude-haiku-4-5": {
            "context_window": 200_000,
            "cost_per_million": {"input": 1.0, "output": 5.0},
            "usage_unit": "tokens",
        },
        "claude-haiku-4-5-20251001": {
            "context_window": 200_000,
            "cost_per_million": {"input": 1.0, "output": 5.0},
            "usage_unit": "tokens",
        },
        "claude-sonnet-4-6": {
            "context_window": 1_000_000,
            "cost_per_million": {"input": 3.0, "output": 15.0},
            "usage_unit": "tokens",
        },
        "claude-opus-4-8": {
            "context_window": 1_000_000,
            "cost_per_million": {"input": 5.0, "output": 25.0},
            "usage_unit": "tokens",
        },
    }

    def __init__(self, api_key: str, model: str) -> None:
        super().__init__(model)
        self.api_key = api_key

    def to_messages(self, messages: List[Message]) -> List[Dict[str, Any]]:
        result = []
        for msg in messages:
            if msg.role == "tool_result":
                result.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": msg.tool_use_id,
                        "content": msg.content,
                    }],
                })
            elif msg.role == "assistant":
                result.append({
                    "role": "assistant",
                    "content": self._assistant_content(msg.content),
                })
            else:
                result.append({"role": msg.role, "content": msg.content})
        return result

    def to_tools(self, tools: Dict[str, Tool]) -> List[Dict[str, Any]]:
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": {
                    "type": "object",
                    "properties": self._filter_properties(tool.parameters),
                    "required": self._get_required_params(tool.parameters),
                },
            }
            for tool in tools.values()
        ]

    def _filter_properties(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Filter out the 'required' field from parameter definitions for the schema."""
        return {
            name: {k: v for k, v in param.items() if k != "required"}
            for name, param in parameters.items()
        }

    def _get_required_params(self, parameters: Dict[str, Any]) -> List[str]:
        """Extract only the truly required parameter names."""
        return [name for name, param in parameters.items() if isinstance(param, dict) and param.get("required", False)]

    def to_payload(
        self,
        context: Context,
        max_output_tokens: int = 1024,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        return {
            "model": self.model,
            "system": context.system,
            "max_tokens": max_output_tokens,
            "tools": tools if tools is not None else self.to_tools(context.tools),
            "messages": self.to_messages(context.messages),
        }

    def headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }

    def url(self) -> str:
        return self.BASE_URL

    def parse_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        stop_reason = "tool_use" if response.get("stop_reason") == "tool_use" else "end_turn"
        content = [self._normalize_block(b) for b in (response.get("content") or [])]
        return {"stop_reason": stop_reason, "content": content}

    def _normalize_block(self, block: Dict[str, Any]) -> Dict[str, Any]:
        if block.get("type") == "thinking":
            return {
                "type": "reasoning",
                "text": str(block.get("thinking") or ""),
                "signature": block.get("signature"),
            }
        if block.get("type") == "redacted_thinking":
            return {
                "type": "reasoning",
                "text": "",
                "redacted": True,
                "signature": block.get("data"),
            }
        return block

    # Rebuilds Anthropic assistant content from normalized blocks (the
    # inverse of parse_response). Text-only turns are stored as a bare
    # String and pass through unchanged; "reasoning" blocks are re-emitted
    # as native thinking/redacted_thinking blocks so signatures round-trip
    # intact.
    def _assistant_content(
        self, content: Union[str, List[Dict[str, Any]]]
    ) -> Union[str, List[Dict[str, Any]]]:
        if isinstance(content, str):
            return content
        return [self._denormalize_block(b) for b in content]

    def _denormalize_block(self, block: Dict[str, Any]) -> Dict[str, Any]:
        if block.get("type") != "reasoning":
            return block
        if block.get("redacted"):
            return {"type": "redacted_thinking", "data": block.get("signature")}
        return {
            "type": "thinking",
            "thinking": str(block.get("text") or ""),
            "signature": block.get("signature"),
        }
