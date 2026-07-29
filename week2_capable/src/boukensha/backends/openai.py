import json
from typing import Any, ClassVar, Dict, List, Optional, Union

from ..context import Context
from ..message import Message
from ..tool import Tool
from .base import BackendBase


class OpenAI(BackendBase):
    # https://platform.openai.com/docs/api-reference/responses
    #
    # gpt-5.x rejects `reasoning_effort` + tools on /v1/chat/completions
    # ("Please use /v1/responses"), so this backend targets the Responses
    # API instead of chat completions. That changes more than the URL:
    # messages become `input` items, the system prompt becomes a top-level
    # `instructions` string, tool defs are flat (no `function:` wrapper),
    # and tool results round-trip via `function_call_output` items matched
    # by `call_id` rather than a `{role: "tool"}` message.
    BASE_URL: ClassVar[str] = "https://api.openai.com/v1/responses"
    MODELS: ClassVar[Dict[str, Dict[str, Any]]] = {
        "gpt-5.5": {
            "context_window": 1_000_000,
            "cost_per_million": {"input": 5.0, "output": 30.0},
            "usage_unit": "tokens",
        },
        "gpt-5.4-mini": {
            "context_window": 400_000,
            "cost_per_million": {"input": 0.75, "output": 4.5},
            "usage_unit": "tokens",
        },
        "gpt-5.4-nano": {
            "context_window": 400_000,
            "cost_per_million": {"input": 0.2, "output": 1.25},
            "usage_unit": "tokens",
        },
    }

    def __init__(self, api_key: str, model: str) -> None:
        super().__init__(model)
        self.api_key = api_key

    def to_input(self, messages: List[Message]) -> List[Dict[str, Any]]:
        result: List[Dict[str, Any]] = []
        for msg in messages:
            if msg.role == "tool_result":
                result.append({
                    "type": "function_call_output",
                    "call_id": msg.tool_use_id,
                    "output": str(msg.content),
                })
            elif msg.role == "assistant":
                result.extend(self._assistant_items(msg.content))
            else:
                result.append({"role": msg.role, "content": msg.content})
        return result

    def to_tools(self, tools: Dict[str, Tool]) -> List[Dict[str, Any]]:
        return [
            {
                "type": "function",
                "name": tool.name,
                "description": tool.description,
                "parameters": {
                    "type": "object",
                    "properties": tool.parameters,
                    "required": list(tool.parameters.keys()),
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
            "instructions": context.system,
            "input": self.to_input(context.messages),
            "tools": tools if tools is not None else self.to_tools(context.tools),
            "max_output_tokens": max_output_tokens,
            "reasoning": {"effort": "none"},
        }

    def headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    def url(self) -> str:
        return self.BASE_URL

    # Normalizes a Responses API `output[]` array into the common shape:
    #   {"stop_reason": "tool_use" | "end_turn", "content": [{"type": ...}]}
    def parse_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        function_calls: List[Dict[str, Any]] = []
        content: List[Dict[str, Any]] = []

        for item in response.get("output") or []:
            item_type = item.get("type")
            if item_type == "reasoning":
                text = "".join(s.get("text", "") for s in (item.get("summary") or []))
                content.append({"type": "reasoning", "text": text})
            elif item_type == "message":
                text = "".join(
                    c.get("text", "")
                    for c in (item.get("content") or [])
                    if c.get("type") == "output_text"
                )
                if text:
                    content.append({"type": "text", "text": text})
            elif item_type == "function_call":
                function_calls.append(item)

        for fc in function_calls:
            try:
                arguments = json.loads(fc.get("arguments") or "{}")
            except json.JSONDecodeError:
                arguments = {}
            content.append({
                "type": "tool_use",
                "id": fc.get("call_id"),
                "name": fc.get("name"),
                "input": arguments,
            })

        stop_reason = "tool_use" if function_calls else "end_turn"
        return {"stop_reason": stop_reason, "content": content}

    # Rebuilds Responses input items from normalized content blocks (the
    # inverse of parse_response). Reasoning blocks are dropped -- gpt-5.x
    # doesn't need them echoed back when reasoning effort is "none".
    def _assistant_items(self, content: Union[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        blocks = content if isinstance(content, list) else [{"type": "text", "text": str(content)}]

        text = "".join(b["text"] for b in blocks if b.get("type") == "text")
        items: List[Dict[str, Any]] = []
        if text:
            items.append({"role": "assistant", "content": text})

        for b in blocks:
            if b.get("type") != "tool_use":
                continue
            items.append({
                "type": "function_call",
                "call_id": b["id"],
                "name": b["name"],
                "arguments": json.dumps(b["input"]),
            })

        return items
