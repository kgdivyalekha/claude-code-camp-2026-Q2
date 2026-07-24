from typing import Any, ClassVar, Dict, List, Optional, Union

from ..context import Context
from ..message import Message
from ..tool import Tool
from .base import BackendBase


class OllamaCloud(BackendBase):
    BASE_URL: ClassVar[str] = "https://ollama.com"
    MODELS: ClassVar[Dict[str, Dict[str, Any]]] = {
        "gemma4:31b-cloud": {
            "context_window": 256_000,
            "cost_per_million": {"input": None, "output": None},
            "usage_unit": "ollama_cloud_usage",
            "usage_level": "medium",
        },
        "minimax-m3:cloud": {
            "context_window": 512_000,
            "advertised_context_window": 1_000_000,
            "cost_per_million": {"input": None, "output": None},
            "usage_unit": "ollama_cloud_usage",
            "usage_level": "high",
        },
        "kimi-k2.5:cloud": {
            "context_window": 256_000,
            "cost_per_million": {"input": None, "output": None},
            "usage_unit": "ollama_cloud_usage",
            "usage_level": "high",
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
                    "tool_name": msg.tool_use_id,
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
            "stream": False,
            "messages": self.to_messages(context.system, context.messages),
            "tools": tools if tools is not None else self.to_tools(context.tools),
        }

    def headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    def url(self) -> str:
        return f"{self.BASE_URL}/api/chat"

    def parse_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        message = response.get("message") or {}
        tool_calls = message.get("tool_calls") or []

        content = []
        if message.get("content"):
            content.append({"type": "text", "text": message["content"]})

        for tc in tool_calls:
            fn = tc.get("function") or {}
            content.append({
                "type": "tool_use",
                "id": fn.get("name"),
                "name": fn.get("name"),
                "input": fn.get("arguments") or {},
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
                {"function": {"name": b["name"], "arguments": b["input"]}}
                for b in tool_blocks
            ]
        return message
