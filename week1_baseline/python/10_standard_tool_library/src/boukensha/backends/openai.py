import json
from typing import Any, ClassVar, Dict, List, Optional, Union

from ..context import Context
from ..message import Message
from ..tool import Tool
from .base import BackendBase


class OpenAI(BackendBase):
    BASE_URL: ClassVar[str] = "https://api.openai.com/v1/chat/completions"
    MODELS: ClassVar[Dict[str, Dict[str, Any]]] = {
        "gpt-5.5": {
            "context_window": 1_000_000,
            "cost_per_million": {"input": 5.0, "output": 30.0},
            "usage_unit": "tokens",
        },
        "gpt-5.4": {
            "context_window": 1_000_000,
            "cost_per_million": {"input": 2.5, "output": 15.0},
            "usage_unit": "tokens",
        },
        "gpt-5.4-mini": {
            "context_window": 400_000,
            "cost_per_million": {"input": 0.75, "output": 4.5},
            "usage_unit": "tokens",
        },
    }

    def __init__(self, api_key: str, model: str) -> None:
        super().__init__(model)
        self.api_key = api_key

    def to_messages(
        self, system: Optional[str], messages: List[Message]
    ) -> List[Dict[str, Any]]:
        result = []
        if system:
            result.append({"role": "system", "content": system})
        for msg in messages:
            if msg.role == "tool_result":
                result.append({
                    "role": "tool",
                    "tool_call_id": msg.tool_use_id,
                    "content": msg.content,
                })
            elif msg.role == "assistant":
                result.append(self._assistant_message(msg.content))
            else:
                result.append({"role": msg.role, "content": msg.content})
        return result

    def to_tools(self, tools: Dict[str, Tool]) -> List[Dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": {
                        "type": "object",
                        "properties": tool.parameters,
                        "required": list(tool.parameters.keys()),
                    },
                },
            }
            for tool in tools.values()
        ]

    def to_payload(
        self,
        context: Context,
        max_output_tokens: int = 1024,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        return {
            "model": self.model,
            "messages": self.to_messages(context.system, context.messages),
            "tools": tools if tools is not None else self.to_tools(context.tools),
            "max_completion_tokens": max_output_tokens,
        }

    def headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    def url(self) -> str:
        return self.BASE_URL

    def parse_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        message = ((response.get("choices") or [{}])[0].get("message")) or {}
        tool_calls = message.get("tool_calls") or []

        content = []
        if message.get("content"):
            content.append({"type": "text", "text": message["content"]})

        for tc in tool_calls:
            fn = tc.get("function") or {}
            try:
                arguments = json.loads(fn.get("arguments") or "{}")
            except json.JSONDecodeError:
                arguments = {}
            content.append({
                "type": "tool_use",
                "id": tc["id"],
                "name": fn.get("name"),
                "input": arguments,
            })

        stop_reason = "tool_use" if tool_calls else "end_turn"
        return {"stop_reason": stop_reason, "content": content}

    def _assistant_message(self, content: Union[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        blocks = content if isinstance(content, list) else [{"type": "text", "text": str(content)}]
        text_blocks = [b for b in blocks if b.get("type") == "text"]
        tool_blocks = [b for b in blocks if b.get("type") == "tool_use"]

        message = {"role": "assistant", "content": "".join(b["text"] for b in text_blocks)}
        if tool_blocks:
            message["tool_calls"] = [
                {
                    "id": b["id"],
                    "type": "function",
                    "function": {
                        "name": b["name"],
                        "arguments": json.dumps(b["input"]),
                    },
                }
                for b in tool_blocks
            ]
        return message
