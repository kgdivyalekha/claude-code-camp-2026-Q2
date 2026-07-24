from typing import Any, Dict, List, Optional

from .client import Client
from .context import Context
from .errors import ApiError
from .logger import Logger
from .prompt_builder import PromptBuilder
from .registry import Registry


class Agent:
    """The agent loop — sends requests, dispatches tools, and knows when to stop."""

    MAX_ITERATIONS = 25
    WRAP_UP_OUTPUT_TOKENS = 400
    WRAP_UP_DIRECTIVE = (
        "You have reached your action limit for this turn. Do not call any more tools. "
        "Briefly summarize what you accomplished, what is still unfinished, and the "
        "single next action you would take."
    )

    def __init__(
        self,
        context: Context,
        registry: Registry,
        builder: PromptBuilder,
        client: Client,
        logger: Optional[Logger] = None,
        task_settings: Optional[Dict[str, Any]] = None,
        max_iterations: Optional[int] = None,
        max_output_tokens: Optional[int] = None,
    ) -> None:
        self.context = context
        self.registry = registry
        self.builder = builder
        self.client = client
        self.logger = logger or Logger()
        self.max_iterations = self._resolve_max_iterations(task_settings, max_iterations)
        self.max_output_tokens = self._resolve_max_output_tokens(task_settings, max_output_tokens)
        self.iteration = 0

    def run(self) -> str:
        """Start the loop and return the final text response when the agent is done."""
        while True:
            if self._iteration_limit_reached():
                self.logger.limit_reached(
                    kind="max_iterations", n=self.iteration, max=self.max_iterations
                )
                return self._wrap_up("max_iterations")

            self.iteration += 1
            print(f"[iteration {self.iteration}/{self.max_iterations}]")
            self.logger.iteration(n=self.iteration, max=self.max_iterations)
            self.logger.prompt(messages=self.context.messages, tools=self.context.tools)

            response = self.client.call(**self._call_opts())
            self.logger.raw(data=response)
            parsed = self.builder.parse_response(response)

            if parsed["stop_reason"] == "tool_use":
                self._handle_tool_calls(parsed["content"], response)
            else:
                text = self._extract_text(parsed["content"])
                self._log_response(text=text, response=response)
                self.logger.turn_end(reason="completed", iterations=self.iteration)
                return text

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _resolve_max_iterations(
        self,
        task_settings: Optional[Dict[str, Any]],
        explicit: Optional[int],
    ) -> int:
        if explicit is not None:
            return int(explicit)
        if task_settings and self.context.task is not None:
            try:
                return self.context.task.max_iterations(task_settings)
            except (AttributeError, TypeError):
                pass
        return self.MAX_ITERATIONS

    def _resolve_max_output_tokens(
        self,
        task_settings: Optional[Dict[str, Any]],
        explicit: Optional[int],
    ) -> Optional[int]:
        if explicit is not None:
            return explicit
        if task_settings and self.context.task is not None:
            try:
                return self.context.task.max_output_tokens(task_settings)
            except (AttributeError, TypeError):
                pass
        return None

    def _iteration_limit_reached(self) -> bool:
        return self.max_iterations > 0 and self.iteration >= self.max_iterations

    def _call_opts(self) -> Dict[str, Any]:
        opts: Dict[str, Any] = {}
        if self.max_output_tokens is not None:
            opts["max_output_tokens"] = self.max_output_tokens
        return opts

    def _wrap_up(self, reason: str) -> str:
        """One final, tools-disabled model call so the agent ends gracefully."""
        self.context.add_message("user", self.WRAP_UP_DIRECTIVE)
        try:
            response = self.client.call(
                tools=[],
                max_output_tokens=self.WRAP_UP_OUTPUT_TOKENS,
            )
            text = self._extract_text(
                self.builder.parse_response(response)["content"]
            )
            if text.strip():
                self._log_response(text=text, response=response)
                self.logger.turn_end(reason=reason, iterations=self.iteration)
                return text
            msg = self._fallback_message(reason)
            self.logger.turn_end(reason=reason, iterations=self.iteration)
            return msg
        except ApiError:
            msg = self._fallback_message(reason)
            self.logger.turn_end(reason=reason, iterations=self.iteration)
            return msg

    def _fallback_message(self, reason: str) -> str:
        return (
            f"I reached my {self.max_iterations}-action limit for this turn before finishing "
            f"({reason}). Ask me to continue and I'll pick up from here."
        )

    @staticmethod
    def _extract_text(content: List[Dict[str, Any]]) -> str:
        return "".join(
            block["text"] for block in content if block.get("type") == "text"
        )

    def _handle_tool_calls(
        self, content: List[Dict[str, Any]], response: Dict[str, Any]
    ) -> None:
        """Store the assistant message, then dispatch each tool call."""
        tool_calls = [b for b in content if b.get("type") == "tool_use"]

        # Log response with reasoning or tool call summary
        reasoning = self._extract_text(content)
        if reasoning.strip():
            self._log_response(text=reasoning, response=response)
        else:
            call_summary = f"(tool use — {len(tool_calls)} call{'s' if len(tool_calls) != 1 else ''})"
            self._log_response(text=call_summary, response=response)

        self.context.add_message("assistant", content)

        for block in content:
            if block.get("type") != "tool_use":
                continue

            name = block["name"]
            args = block["input"]
            use_id = block["id"]

            print(f"  tool call → {name}({args})")
            self.logger.tool_call(name=name, args=args)

            try:
                result = self.registry.dispatch(name, args)
                result_str = str(result)
                self.logger.tool_result(name=name, result=result, ok=True)
            except Exception as e:
                result_str = f"ERROR: {type(e).__name__}: {e}"
                self.logger.tool_result(
                    name=name, result=result_str, ok=False, error=str(e)
                )

            print(f"  tool result → {result_str[:60]}")
            self.context.add_message("tool_result", result_str, tool_use_id=use_id)

    def _log_response(self, text: str, response: Dict[str, Any]) -> None:
        """Log a response with usage information."""
        self.logger.response(
            text=text,
            usage=self._normalized_usage(response),
            stop_reason=response.get("stop_reason"),
            task=self.context.task,
            backend=self.builder.backend,
        )

    def _normalized_usage(self, response: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract normalized usage data from response."""
        # Try direct usage fields first
        if response.get("usage"):
            return response["usage"]
        if response.get("usageMetadata"):
            return response["usageMetadata"]

        # Build usage from available fields for backends that don't provide it
        usage = {}
        for key in ["prompt_eval_count", "eval_count"]:
            if key in response:
                usage[key] = response[key]

        return usage if usage else None
