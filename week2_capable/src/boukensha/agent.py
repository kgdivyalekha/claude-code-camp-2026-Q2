import threading
from typing import Any, Dict, List, Optional

from .client import Client
from .context import Context
from .errors import ApiError, TurnCancelled
from .logger import Logger
from .prompt_builder import PromptBuilder
from .registry import Registry

# M5 integration: optional GuardedRegistry imports
try:
    from .control.guarded_registry import GuardedRegistry
except ImportError:
    GuardedRegistry = None  # M5 not available


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
        max_iterations: Optional[int] = None,
        max_turn_tokens: Optional[int] = None,
        max_output_tokens: Optional[int] = None,
        cancel_event: Optional[threading.Event] = None,
    ) -> None:
        self.context = context
        self.registry = registry
        self.builder = builder
        self.client = client
        self.logger = logger if logger is not None else Logger()
        self.max_iterations = int(max_iterations or self.MAX_ITERATIONS)
        self.max_turn_tokens = int(max_turn_tokens or 0)  # 0 = disabled
        self.max_output_tokens = max_output_tokens
        self.cancel_event = cancel_event
        self.iteration = 0

    def run(self) -> str:
        """Start the loop and return the final text response when the agent is done."""
        self.context.reset_turn_tokens()
        self._compact_if_needed()

        while True:
            # Two independent ceilings; stop at whichever trips first. Limits
            # are *trigger thresholds*, not hard caps: when one is reached we
            # stop starting new work iterations and make exactly one terminal
            # wind-down call (counted in tokens, but not as another iteration).
            if self._iteration_limit_reached():
                self.logger.limit_reached(
                    kind="max_iterations", n=self.iteration, max=self.max_iterations
                )
                return self._wrap_up("max_iterations")

            if self._token_limit_reached():
                self.logger.limit_reached(
                    kind="max_tokens", n=self.context.turn_tokens, max=self.max_turn_tokens
                )
                return self._wrap_up("max_tokens")

            if self.cancel_event is not None and self.cancel_event.is_set():
                raise TurnCancelled()

            self.iteration += 1
            self.logger.iteration(n=self.iteration, max=self.max_iterations)
            self.logger.prompt(
                messages=self.context.messages,
                tools=self.context.tools,
                context_window=self.context.context_window,
            )

            response = self.client.call(**self._call_opts())
            self.logger.raw(data=response)
            parsed = self.builder.parse_response(response)
            self._record_usage(response)
            self._log_reasoning(parsed["content"])

            if parsed["stop_reason"] == "tool_use":
                self._handle_tool_calls(parsed["content"], response)
            else:
                text = self._extract_text(parsed["content"])
                self.logger.response(
                    text=text,
                    usage=response.get("usage"),
                    stop_reason=parsed["stop_reason"],
                    task=None,
                    backend=self.builder.backend,
                )
                self.logger.turn_end(
                    reason="completed", iterations=self.iteration, tokens=self.context.turn_tokens
                )
                self.context.add_message("assistant", text)
                return text

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _iteration_limit_reached(self) -> bool:
        return self.max_iterations > 0 and self.iteration >= self.max_iterations

    def _token_limit_reached(self) -> bool:
        return self.max_turn_tokens > 0 and self.context.turn_tokens >= self.max_turn_tokens

    def _call_opts(self) -> Dict[str, Any]:
        """Build options for client.call(), including tools filtered by M4+M5."""
        opts: Dict[str, Any] = {}
        if self.max_output_tokens is not None:
            opts["max_output_tokens"] = self.max_output_tokens

        # M5 integration: if registry is GuardedRegistry, extract actor and policy
        # and pass them to to_tools() for permission-based pruning (M5)
        actor, policy = self._get_actor_and_policy()
        if actor is not None and policy is not None:
            # Build tool list with M4 gating + M5 pruning
            tools = self.builder.to_tools(actor=actor, policy=policy)
            opts["tools"] = tools

        return opts

    def _get_actor_and_policy(self) -> tuple[Optional[Any], Optional[Any]]:
        """Extract actor and policy from GuardedRegistry if available.

        Returns:
            Tuple of (actor, policy) if registry is GuardedRegistry, else (None, None)
        """
        if GuardedRegistry is None:
            return None, None

        if isinstance(self.registry, GuardedRegistry):
            return self.registry._actor, self.registry._policy

        return None, None

    # Add this call's input+output to the cumulative turn total (the spend
    # budget) and refresh the known context size from input_tokens (compaction
    # pressure). A direct, unnormalized read of response["usage"] — only
    # populated for Anthropic and the OpenAI Responses API among the shipped
    # backends; see docs/plans/python_port/12_context.md judgment call 1.
    def _record_usage(self, response: Dict[str, Any]) -> None:
        usage = response.get("usage") or {}
        self.context.add_turn_tokens(usage.get("input_tokens"), usage.get("output_tokens"))
        self.context.update_tokens(usage.get("input_tokens"))

    def _compact_if_needed(self) -> None:
        if not self.context.needs_compaction():
            return

        before = self.context.current_tokens
        dropped = self.context.compact_messages()
        self.logger.compaction(
            before=before, dropped=dropped, context_window=self.context.context_window
        )

    # One final, tools-disabled model call so the agent ends the turn in
    # character rather than aborting. Runs *outside* the counted loop: it
    # never re-checks the limits (so it cannot re-trigger) and does not
    # increment self.iteration, though its tokens still count toward the
    # reported turn total. Falls back to a deterministic message if the
    # call fails.
    def _wrap_up(self, reason: str) -> str:
        self.context.add_message("user", self.WRAP_UP_DIRECTIVE)
        try:
            response = self.client.call(
                tools=[],
                max_output_tokens=self.WRAP_UP_OUTPUT_TOKENS,
            )
            parsed_wrap = self.builder.parse_response(response)
            text = self._extract_text(parsed_wrap["content"])
            if not text.strip():
                text = self._fallback_message(reason)
            self._record_usage(response)
            self.logger.response(
                text=text,
                usage=response.get("usage"),
                stop_reason=parsed_wrap["stop_reason"],
                task=None,
                backend=self.builder.backend,
            )
            self.logger.turn_end(
                reason=reason, iterations=self.iteration, tokens=self.context.turn_tokens
            )
            self.context.add_message("assistant", text)
            return text
        except ApiError:
            msg = self._fallback_message(reason)
            self.logger.turn_end(
                reason=reason, iterations=self.iteration, tokens=self.context.turn_tokens
            )
            self.context.add_message("assistant", msg)
            return msg

    def _fallback_message(self, reason: str) -> str:
        return (
            f"I reached my {self.max_iterations}-action limit for this turn before finishing "
            f"({reason}). Ask me to continue and I'll pick up from here."
        )

    @staticmethod
    def _extract_text(content: List[Dict[str, Any]]) -> str:
        return "\n".join(
            block["text"] for block in content if block.get("type") == "text"
        )

    # Emit one `reasoning` event per reasoning block so the viewer can show
    # the model's thinking as a first-class step. Empty, non-redacted blocks
    # are skipped to avoid noise (a redacted/omitted block still renders,
    # since it tells the viewer "the model thought here").
    def _log_reasoning(self, content: List[Dict[str, Any]]) -> None:
        for block in content:
            if block.get("type") != "reasoning":
                continue

            redacted = block.get("redacted") is True
            text = str(block.get("text") or "")
            if not text.strip() and not redacted:
                continue

            self.logger.reasoning(text=text, redacted=redacted)

    def _handle_tool_calls(self, content: List[Dict[str, Any]], response: Dict[str, Any]) -> None:
        """Log any preamble, store the assistant message, then dispatch each tool call."""
        tool_calls = [b for b in content if b.get("type") == "tool_use"]

        # Log any preamble text that accompanied the tool call (carries no
        # usage -- the placeholder below owns the turn's usage chip), then
        # the placeholder.
        preamble = self._extract_text(content)
        if preamble.strip():
            self.logger.plan(text=preamble)
        self.logger.response(
            text=f"(tool use — {len(tool_calls)} call{'s' if len(tool_calls) != 1 else ''})",
            usage=response.get("usage"),
            stop_reason="tool_use",
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
