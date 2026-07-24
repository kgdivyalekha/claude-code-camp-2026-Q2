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
        self.logger = logger if logger is not None else Logger()
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
            if not text.strip():
                text = self._fallback_message(reason)
            self._log_response(text=text, response=response)
            self.logger.turn_end(reason=reason, iterations=self.iteration)
            return text
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

    def _handle_tool_calls(self, content: List[Dict[str, Any]], response: Dict[str, Any]) -> None:
        """Log reasoning, store the assistant message, then dispatch each tool call."""
        tool_calls = [b for b in content if b.get("type") == "tool_use"]

        reasoning = self._extract_text(content)
        placeholder = f"(tool use — {len(tool_calls)} call{'s' if len(tool_calls) != 1 else ''})"
        self._log_response(
            text=reasoning if reasoning.strip() else placeholder, response=response
        )

        self.context.add_message("assistant", content)

        for block in tool_calls:
            name = block["name"]
            args = block["input"]
            use_id = block["id"]

            self.logger.tool_call(name=name, args=args)
            try:
                result = self.registry.dispatch(name, args)
                self.logger.tool_result(name=name, result=result, ok=True)
            except Exception as e:
                result = f"ERROR: {type(e).__name__}: {e}"
                self.logger.tool_result(name=name, result=result, ok=False, error=str(e))

            self.context.add_message("tool_result", str(result), tool_use_id=use_id)

    def _log_response(self, text: str, response: Dict[str, Any]) -> None:
        self.logger.response(
            text=text,
            usage=self._normalized_usage(response),
            stop_reason=response.get("stop_reason"),
            task=self.context.task,
            backend=self.builder.backend,
        )

    @staticmethod
    def _normalized_usage(response: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if response.get("usage"):
            return response["usage"]
        if response.get("usageMetadata"):
            return response["usageMetadata"]

        usage = {}
        for key in ("prompt_eval_count", "eval_count"):
            if key in response:
                usage[key] = response[key]
        return usage or None
