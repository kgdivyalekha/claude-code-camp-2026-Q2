from typing import Any, ClassVar, Dict, List, Optional, Union

from ..context import Context
from ..message import Message
from ..tool import Tool
from .base import BackendBase


class Gemini(BackendBase):
    BASE_URL: ClassVar[str] = "https://generativelanguage.googleapis.com/v1beta/models"
    MODELS: ClassVar[Dict[str, Dict[str, Any]]] = {
        "gemini-3.5-flash": {
            "context_window": 1_048_576,
            "cost_per_million": {"input": 1.5, "output": 9.0},
            "usage_unit": "tokens",
        },
        "gemini-3.1-flash-lite": {
            "context_window": 1_048_576,
            "cost_per_million": {"input": 0.25, "output": 1.5},
            "usage_unit": "tokens",
        },
        "gemini-2.5-pro": {
            "context_window": 1_048_576,
            "cost_per_million": {"input": 1.25, "output": 10.0},
            "usage_unit": "tokens",
        },
        "gemini-2.5-flash": {
            "context_window": 1_048_576,
            "cost_per_million": {"input": 0.30, "output": 2.50},
            "usage_unit": "tokens",
        },
        "gemini-2.5-flash-lite": {
            "context_window": 1_048_576,
            "cost_per_million": {"input": 0.10, "output": 0.40},
            "usage_unit": "tokens",
        },
    }

    def __init__(self, api_key: str, model: str) -> None:
        super().__init__(model)
        self.api_key = api_key

    def to_messages(self, messages: List[Message]) -> List[Dict[str, Any]]:
        result = []
        for msg in messages:
            if msg.role == "assistant":
                result.append({
                    "role": "model",
                    "parts": self._assistant_parts(msg.content),
                })
            elif msg.role == "tool_result":
                result.append({
                    "role": "user",
                    "parts": [{
                        "functionResponse": {
                            "name": msg.tool_use_id,
                            "response": {"content": msg.content},
                        }
                    }],
                })
            else:
                result.append({
                    "role": msg.role,
                    "parts": [{"text": msg.content}],
                })
        return result

    def to_tools(self, tools: Dict[str, Tool]) -> List[Dict[str, Any]]:
        if not tools:
            return []
        return [{
            "functionDeclarations": [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": {
                        "type": "object",
                        "properties": self._filter_properties(tool.parameters),
                        "required": self._get_required_params(tool.parameters),
                    },
                }
                for tool in tools.values()
            ]
        }]

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
            "systemInstruction": {"parts": [{"text": context.system}]},
            "contents": self.to_messages(context.messages),
            "tools": tools if tools is not None else self.to_tools(context.tools),
            "generationConfig": {
                "maxOutputTokens": max_output_tokens,
                "thinkingConfig": self._thinking_config(),
            },
        }

    def headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
        }

    def url(self) -> str:
        return f"{self.BASE_URL}/{self.model}:generateContent"

    def parse_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        candidates = response.get("candidates") or []
        parts = (candidates[0].get("content") or {}).get("parts") if candidates else []
        if parts is None:
            parts = []

        content = []
        tool_used = False

        for part in parts:
            if "functionCall" in part:
                fc = part["functionCall"]
                content.append({
                    "type": "tool_use",
                    "id": fc.get("name"),
                    "name": fc.get("name"),
                    "input": fc.get("args") or {},
                    "signature": part.get("thoughtSignature"),
                })
                tool_used = True
            elif part.get("thought"):
                content.append({
                    "type": "reasoning",
                    "text": part.get("text", ""),
                    "signature": part.get("thoughtSignature"),
                })
            elif "text" in part:
                content.append({"type": "text", "text": part["text"]})

        stop_reason = "tool_use" if tool_used else "end_turn"
        return {"stop_reason": stop_reason, "content": content}

    def _thinking_config(self) -> Dict[str, Any]:
        if self.model == "gemini-3.1-pro-preview-customtools":
            return {"thinkingLevel": "LOW"}  # full disable not supported on this model
        return {"thinkingBudget": 0}  # gemini-3.5-flash, gemini-3.1-flash-lite, etc.

    def _assistant_parts(self, content: Union[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        blocks = content if isinstance(content, list) else [{"type": "text", "text": str(content)}]
        result = []
        for b in blocks:
            if b.get("type") == "tool_use":
                part: Dict[str, Any] = {"functionCall": {"name": b["name"], "args": b["input"]}}
                if b.get("signature"):
                    part["thoughtSignature"] = b["signature"]
                result.append(part)
            elif b.get("type") == "reasoning":
                part = {"text": b.get("text", ""), "thought": True}
                if b.get("signature"):
                    part["thoughtSignature"] = b["signature"]
                result.append(part)
            else:
                result.append({"text": b["text"]})
        return result
