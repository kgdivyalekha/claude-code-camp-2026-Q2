# Python Port Plan — 12 · Context Management

## Goal

Port the step-12 delta into the already-copied
`week1_baseline/python/12_context` snapshot (an untracked copy of
`11_tui`, confirmed via `diff -rq` to differ only where noted below — this
plan's job is entirely the delta, not the copy itself).

Ruby's own framing (`README.md`): *"When you call an LLM directly you are
responsible for the context window. There is no auto-compacting."* This step
adds real token accounting (`Context.current_tokens` vs `context_window`,
looked up per-model), colour-coded usage display, automatic compaction when
the window gets too full, a `/compact` command, a second per-turn ceiling
(`max_turn_tokens`, alongside the existing `max_iterations`), and
provider-normalized "reasoning" content blocks (Anthropic thinking, Gemini
`thought`, Ollama `message.thinking`) surfaced as their own logged event —
all layered on top of the MCP-host architecture and Textual TUI from prior
steps.

It also completes a smaller, previously-deferred cleanup: task-derived agent
limits (`max_iterations`/`max_output_tokens` sourced from
`tasks.player.*` via `Task.max_iterations(task_settings)`) are replaced by a
new `agent:` settings namespace read directly off `Config`
(`Config.agent_max_iterations` etc.), decoupling per-turn circuit breakers
from the task/prompt-override system. `Task.max_iterations`/
`Task.max_output_tokens` (`src/boukensha/tasks/base.py`) stay defined —
ruby doesn't remove `Tasks::Base`'s equivalents either — they're just no
longer called from `run()`/`repl()`.

## Source of truth and scope

Diffing `11_tui` against `12_context` directly in ruby shows a broad but
contained set of changes — one new file, no removed files:

| Ruby file | What changed |
|---|---|
| `lib/boukensha/version.rb`, `boukensha.gemspec`, `Gemfile.lock` | `0.11.1` → `0.12.0` |
| `lib/boukensha/models.rb` | **new.** `Boukensha::Models` — a static model-id → `context_window` lookup table with a conservative `DEFAULT_CONTEXT_WINDOW` fallback |
| `lib/boukensha/context.rb` | `task:` keyword **removed** (system prompt no longer needs a task object); `system:` now required; adds `context_window:`/`compaction_threshold:` constructor args, `current_tokens`/`turn_tokens` tracking, `update_tokens`, `reset_turn_tokens`, `add_turn_tokens`, `usage_fraction`, `usage_pct`, `needs_compaction?`, `compact_messages!` |
| `lib/boukensha/agent.rb` | drops `task_settings:`; `max_iterations:` now defaults to `MAX_ITERATIONS` directly (no more task-based resolution helpers); adds `max_turn_tokens:` (a second, independent per-turn ceiling) and its `token_limit_reached?` check; calls `context.reset_turn_tokens`/`compact_if_needed` at the top of `run`; every API response updates `context.current_tokens`/`turn_tokens` via `record_usage`; extracts and logs reasoning blocks (`log_reasoning`); tool-call preambles now go through a new `logger.plan` event instead of being folded into the response placeholder text; `log_response`/`normalized_usage` helpers removed |
| `lib/boukensha/logger.rb` | `prompt` gains `context_window:`; new `compaction`, `reasoning`, `plan` event methods |
| `lib/boukensha/config.rb` | new `provider_type`/`model` (display-only), `agent_max_iterations`/`agent_max_output_tokens`/`agent_max_turn_tokens`/`agent_compaction_threshold` (the new `agent:` settings namespace, each with a hardcoded default); `to_s` now shows provider/model instead of the tasks list |
| `lib/boukensha/repl.rb` | drops `task_settings:`, adds `max_turn_tokens:` (both threaded into the `Agent` it constructs); new `/compact` command + help text |
| `lib/boukensha/tui.rb` | drops the two session-token accumulators in favor of reading `context.current_tokens`/`context_window`/`usage_pct` directly; colour-codes the context indicator (grey/yellow/red at 70%/85%); new `"compaction"` event renders a log line |
| `lib/boukensha.rb` | both `run`/`repl`: add `context_window:` keyword (defaults via `Models.context_window(model)`); `Context.new` call sites drop `task:`, add `context_window:`/`compaction_threshold:`; logger snapshot and `Agent.new` now source `max_iterations`/`max_turn_tokens`/`max_output_tokens` from `cfg.agent_*` instead of `task_class.max_iterations(task_settings)`; requires `models.rb` |
| `lib/boukensha/backends/base.rb` | doc-comment only — documents the new normalized `"reasoning"` content-block shape all backends now emit |
| `lib/boukensha/backends/anthropic.rb` | maps native `thinking`/`redacted_thinking` blocks to/from `"reasoning"` blocks (round-tripping `signature`); assistant messages built from block arrays now handled explicitly (`when :assistant` branch) |
| `lib/boukensha/backends/gemini.rb` | `thinkingConfig` added to every request (thinking explicitly disabled for current models); `thought`/`thoughtSignature` parts map to/from `"reasoning"` blocks; `tool_use`/`reasoning` blocks round-trip a `signature` |
| `lib/boukensha/backends/ollama.rb`, `backends/ollama_cloud.rb` | `think: false` added to the request payload; `message["thinking"]` (when present) maps to a `"reasoning"` block; `ollama_cloud.rb`'s `MODELS` entries are also just reordered (no value changes) |
| `lib/boukensha/backends/openai.rb` | **rewritten** from the Chat Completions API to the Responses API (`/v1/responses`): `instructions` replaces a synthetic system message, `input` items replace `messages`, tool defs are flattened (no `function:` wrapper), tool results round-trip via `function_call_output`/`call_id`, `reasoning: {effort: "none"}` is set explicitly, reasoning items are parsed but dropped on the way back in (gpt-5.x doesn't need them echoed at `effort: "none"`); `MODELS` drops `gpt-5.4`, adds `gpt-5.4-nano` |
| `prompts/system.md` | one new paragraph telling the model a `"[context compacted ...]"` notice is system-generated housekeeping, not user input |
| `examples/example.rb` | reverts from step-11's MCP-only text back to a MUD-flavored task string, adds a `BOUKENSHA_DIR` env default and `working_dir: false`; drops the `Servers:` print line — see judgment call 4 below, its header comment is unreliable |
| `examples/mcp_mud_demo.rb` | one line: `Context.new(task: ..., system: "demo")` → `Context.new(system: "demo")` |
| `test/helper.rb` | one line: same `Context.new` signature fix in `new_registry` |
| `README.md` | full rewrite documenting all of the above |
| `lib/boukensha/errors.rb` | cosmetic alignment only (`<` column-padding around the `class X < StandardError` lines) — **no port needed** |
| `lib/boukensha/prompt_builder.rb` | doc-comment only, describing the same normalized content-block contract `backends/base.rb` documents — **no port needed beyond an equivalent comment** |
| `lib/boukensha/tasks/base.rb`, `tasks/player.rb` | **no diff** — `Task.max_iterations`/`max_output_tokens`/`model`/`provider`/`system_prompt` stay exactly as they are; `boukensha.rb` simply stops calling the first two |
| `lib/boukensha/client.rb`, `registry.rb`, `message.rb`, `tool.rb`, `run_dsl.rb`, `mcp/client.rb`, `tools/mcp.rb` | **no diff** |
| `test/*` (besides `helper.rb`) | **no diff** — ruby ships no new automated coverage for compaction/token-limits/reasoning; this plan adds Python-only tests for them (see Verification) |

Seven judgment calls this plan makes, called out so they don't read as
accidental deviations in review:

**1. `response["usage"]` is read raw, matching ruby's step-12 regression
exactly — not "fixed."** Ruby's `record_usage` and every `logger.response`
call in the new `agent.rb` read `response["usage"]` directly off the raw
HTTP JSON body (`Client#call` does no normalization — it's
`JSON.parse(response.body)`, full stop). That key only exists in
Anthropic's and the rewritten OpenAI Responses API's raw response shapes;
Gemini's usage lives under `usageMetadata`, and Ollama/Ollama Cloud report
`prompt_eval_count`/`eval_count` at the top level with no `usage` key at
all. Step 11's ruby agent (and Python's current agent) both had a
`normalized_usage`/`_normalized_usage` helper checking `usage` →
`usageMetadata` → `prompt_eval_count`/`eval_count` in that order
specifically to paper over this cross-backend inconsistency — step 12's
ruby diff **deletes that helper** as part of deleting `log_response`, and
nothing in the diff or README suggests this was anything but an oversight.
The blast radius is larger than just this step's headline feature: it's
not only `current_tokens`/`turn_tokens`/compaction/`max_turn_tokens` that
silently go inert for Gemini/Ollama/OllamaCloud (raw `usage` is `None`,
`add_turn_tokens(None, None)` adds zero, the context bar never leaves
grey), it's also the *pre-existing* cost-estimation logging
(`Logger._execution_metadata`'s `cost_usd`/`input_tokens`/`output_tokens`)
that quietly stops populating for those three backends too, since it now
receives the same raw, ungeneralized value. This plan ports the regression
faithfully — delete Python's `_normalized_usage` (matching ruby's deletion
of `normalized_usage`), read `response.get("usage")` raw everywhere ruby
does — rather than keeping a helper ruby itself removed. `/compact` (the
manual command) still works on every backend regardless, since it doesn't
depend on usage data at all; only the *automatic* triggers and the
usage-derived display/cost figures are affected. Flag this in review as an
inherited limitation of the step-12 ruby source, scoped wider than this
step's own feature set, not a Python defect or a missed fix.

**2. `parsed["stop_reason"]`, not `response.get("stop_reason")`, for the
logged stop reason.** Ruby's new `logger.response` calls in the non-tool
branch and in `wrap_up` pass `stop_reason: parsed[:stop_reason]` /
`parsed_wrap[:stop_reason]` — the *builder-normalized* value (always
`"tool_use"` or `"end_turn"`), not a raw field off the HTTP response (which
doesn't even exist under that key for Gemini/Ollama/OpenAI's Responses API).
Python's pre-step-12 `_log_response` used `response.get("stop_reason")`
directly — worked only by coincidence for Anthropic. This plan switches
both call sites to the parsed value, matching what ruby's own diff actually
does (this is a faithful port, not a divergence — called out here only
because it looks like a one-line typo fix and isn't; it's necessary for
Gemini/Ollama/OpenAI parity to keep working post-port, independent of
judgment call 1's usage-key gap).

**3. Python-only `cancel_event`/`TurnCancelled` cooperative cancellation
(added in the step-11 port; ruby has no equivalent there or here — it uses
`Thread#raise(Interrupt)` inside `Tui`, untouched by this diff) is preserved
unchanged, in its existing position.** Nothing in step 12's `agent.rb` diff
touches cancellation, so there's nothing to port. Concretely: today's
`Agent.run()` checks `_iteration_limit_reached()` first, then
`cancel_event`, then increments `self.iteration`. The new
`_token_limit_reached()` check is inserted **between** those two existing
checks (iteration limit → token limit → cancel_event → increment), not
ahead of both — matching where ruby's own two new/existing limit checks sit
relative to each other, with the Python-only cancel check kept in the slot
step 11 already put it.

**4. `examples/example.py`'s header comment describes reality, not
ruby's stale docstring.** Ruby's step-12 `example.rb` is a near-exact
revert to the *actual* step-10 ruby `example.rb` (task text, `working_dir:
false`, dropped `Servers:` line) — except its new header claims to
"Demonstrate `Boukensha::Tools::Mud`", a class that **does not exist**
anywhere in `12_context/lib/` (confirmed: `find lib -iname '*mud*'` and
`grep Mud lib/boukensha.rb` both come up empty). This reads as a copy-paste
artifact from a different lineage of this exercise, not a real change in
architecture — the file still works purely through `mcp_servers:` (the `mud`
entry in `settings.yaml`), exactly like every step since 10. This plan ports
the *functional* diff (task string, `working_dir=False`, `BOUKENSHA_DIR`
default — already present in Python's `example.py` since it was carried
over from an earlier step, drop the `Servers:` print line) but writes an
accurate header describing the actual MCP-based mechanism, the same way
step 10's plan would have, rather than reproducing a comment that names a
class this codebase never ported. Call this out in review as a deliberate
correction of ruby's own doc bug, not a missed detail.

**5. `Context#compact_messages!`'s `target_fraction:` keyword is accepted
but never read in ruby's body** (`drop_count` hardcodes `0.40` regardless
of what's passed). This is a real but harmless quirk — nobody currently
calls it with a non-default value — and this plan ports it faithfully
(Python's `compact_messages` keeps the same unused-but-accepted parameter)
rather than silently "fixing" call-site behavior ruby itself doesn't
implement. Unlike judgment call 1, this doesn't break a *feature* (manual
and auto compaction both still drop the intended ~40%), so faithfully
porting the quirk is the safer choice.

**6. Ruby's README references
`docs/plans/context_delta/plan.md`** (an open question about
`tasks.player.*` vs `agent.*` settings namespaces) that **does not exist**
anywhere in this repo's `docs/plans/` tree. This plan's rewritten Python
`README.md` keeps the substance of that note (two settings namespaces now
exist for conceptually similar things) as inline prose instead of a link to
a document that was never actually written, rather than inventing content
for a doc nobody asked for.

**7. `PromptBuilder.to_messages()` is left calling `backend.to_messages(...)`
even where a backend no longer has that method — matching a latent bug
present in both languages, not silently patched.** Both ruby's and Python's
`PromptBuilder` ship an unused convenience method —
`to_messages(self) -> self.backend.to_messages(self.context.messages)` —
that nothing in the real request path calls (`to_api_payload`/
`to_payload` is what's actually used; each backend builds its own messages
internally). It already had a latent Python-specific mismatch before this
step: `Ollama`/`OllamaCloud`/`OpenAI`'s `to_messages` take `(system,
messages)`, not the single `messages` arg `PromptBuilder.to_messages()`
passes — calling it against any of those three would already have raised a
`TypeError`, pre-existing and out of scope for this port. Step 12 compounds
it for ruby specifically: `OpenAI#to_messages` is renamed to `#to_input` in
this same diff, so ruby's `PromptBuilder#to_messages` would now raise
`NoMethodError` for the OpenAI backend where it previously (accidentally)
worked. This plan renames the Python method identically
(`to_messages`→`to_input` inside `backends/openai.py`, per step 10 below)
without touching `PromptBuilder.to_messages()` itself — faithfully carrying
the same dead, unreachable-in-practice inconsistency forward in both
languages, rather than quietly fixing a method nothing calls. Flag this in
review as an inherited, harmless dead-code inconsistency, not a missed
rename.

## Python API shape

```python
from boukensha import run, repl, Context, Models

# context_window now resolved from the model id unless overridden
run(task="...", context_window=128_000)   # override for a non-standard model
repl()                                     # unchanged surface, same default context_window lookup

Models.context_window("claude-haiku-4-5")  # -> 200_000
Models.context_window("unknown-model-id")  # -> Models.DEFAULT_CONTEXT_WINDOW (32_000)

ctx = Context(system="...")                # `task=` no longer accepted
ctx.usage_pct                               # 0-100 int
ctx.needs_compaction()                      # bool, threshold from ctx.compaction_threshold
dropped = ctx.compact_messages()            # drop oldest ~40%, reset current_tokens
```

```
boukensha> /compact
(compacted context — 12 messages dropped)
```

## Implementation plan

### 1. Bump the version

- `src/boukensha/run.py`: `__version__ = "0.12.0"`.
- `pyproject.toml`: `version = "0.12.0"`, update `description` to mention
  context management. No new dependencies — everything here is pure
  Python/stdlib on top of what's already installed.

### 2. Add `src/boukensha/models.py`

Direct port of `Boukensha::Models` (`lib/boukensha/models.rb`): a module-level
`TABLE: Dict[str, Dict[str, int]]` (same model ids, same `context_window`
values — Anthropic, OpenAI, Gemini, Ollama, Ollama Cloud), a
`DEFAULT_CONTEXT_WINDOW = 32_000`, and a `context_window(model: str) -> int`
lookup function using `.get(model, {}).get("context_window",
DEFAULT_CONTEXT_WINDOW)`. Mirror ruby's `qwen3:8b` outlier (40,000, smaller
than its siblings) and the commented-out
`gpt-5.4`-removal/`gpt-5.4-nano`-addition already reflected in step 6's
`OpenAI.MODELS` change (keep the two tables' model ids consistent with each
other).

### 3. Rewrite `Context`

`src/boukensha/context.py`:

- Constructor: drop `task` entirely; `system: str` becomes required
  (no default); add `context_window: int = 200_000`,
  `compaction_threshold: float = 0.85`. Add `self.current_tokens = 0`,
  `self.turn_tokens = 0`.
- `update_tokens(self, n) -> None`: `self.current_tokens = int(n or 0)`.
- `reset_turn_tokens(self) -> None`: `self.turn_tokens = 0`.
- `add_turn_tokens(self, input_tokens, output_tokens) -> None`:
  `self.turn_tokens += int(input_tokens or 0) + int(output_tokens or 0)`.
- `usage_fraction(self) -> float`: `self.current_tokens / self.context_window
  if self.context_window > 0 else 0.0`.
- `usage_pct(self) -> int`: `round(self.usage_fraction() * 100)`.
- `needs_compaction(self, threshold: Optional[float] = None) -> bool`:
  defaults `threshold` to `self.compaction_threshold`; returns
  `self.usage_fraction() >= threshold`.
- `compact_messages(self, target_fraction: float = 0.60) -> int`: drop the
  oldest `min(ceil(len(messages) * 0.40), max(len(messages) - 2, 0))`
  messages (judgment call 4 — `target_fraction` accepted, not used, matching
  ruby exactly), reset `current_tokens` to 0, return the drop count.
- `clear_messages(self)`: also reset `current_tokens = 0` (currently only
  clears `self.messages`).
- `__repr__`/`__str__`: drop `task=...`; add `window=self.context_window
  current={self.current_tokens}` — `"<Context turns={} tools={} window={}
  current={}>"`.
- Every other method (`register_tool`, `add_message`, `tool_count`,
  `turn_count`) is unchanged.

### 4. Wire the new `agent:` settings namespace into `Config`

`src/boukensha/config.py`:

- `provider_type` (`@property`): `self.dig("tasks", "player", "provider") or
  "anthropic"`. Not called anywhere else in either language beyond
  `Config.__str__` — ported for parity, not because anything consumes it
  (actual model/provider resolution for `run()`/`repl()` continues to go
  through `Player.provider(task_settings)`/`.model(task_settings)`,
  unchanged).
- `model` (`@property`): `self.dig("tasks", "player", "model") or
  "claude-haiku-4-5"`. Same caveat as `provider_type`.
- `agent_max_iterations` (`@property`, `-> int`): `dig("agent",
  "max_iterations")`, default `25` (matches `Agent.MAX_ITERATIONS` / ruby's
  `Tasks::Base::DEFAULT_MAX_ITERATIONS`).
- `agent_max_output_tokens` (`@property`, `-> int`): `dig("agent",
  "max_output_tokens")`, default `1024`.
- `agent_max_turn_tokens` (`@property`, `-> int`): `dig("agent",
  "max_turn_tokens")`, default `60_000`.
- `agent_compaction_threshold` (`@property`, `-> float`): `dig("agent",
  "compaction_threshold")`, default `0.85`.
- All four `agent_*` readers and `provider_type`/`model` are `@property`
  (no-arg), matching this file's existing convention for `mcp_servers`/
  `user_prompts_dir` rather than the parenthesized-method style `tasks()`
  uses (which takes an optional arg and so can't be a property).
- `__str__`: `f"<Boukensha.Config dir={self.dir} provider={self.provider_type}
  model={self.model}>"` (drops the `tasks=...` listing).

### 5. `Logger`: `context_window` on `prompt`, plus `compaction`/`reasoning`/`plan`

`src/boukensha/logger.py`:

- `prompt(self, messages, tools, context_window: int) -> None`: add the new
  required kwarg to the existing event dict (`"context_window":
  context_window`).
- `compaction(self, before: int, dropped: int, context_window: int) ->
  None`: `_write_log({"phase": "compaction", "before": before, "dropped":
  dropped, "context_window": context_window})`.
- `reasoning(self, text: str, redacted: bool = False) -> None`:
  `_write_log({"phase": "reasoning", "text": str(text), "redacted":
  redacted})`.
- `plan(self, text: str) -> None`: `_write_log({"phase": "plan", "text":
  str(text).strip()})`.
- `response`/`turn_end`/everything else: unchanged (Python's `response`
  already accepts `task`/`backend` and computes `execution_metadata` —
  ruby only caught up to that in *this* step; Python already had it since
  it was ported ahead of ruby's own `log_response` cost-estimation feature
  in an earlier step. Nothing to add here.)

### 6. `Agent`: turn-token ceiling, compaction, reasoning/plan events

`src/boukensha/agent.py`:

- `__init__`: drop `task_settings`; `max_iterations: int = MAX_ITERATIONS`
  (still coerced via `int(max_iterations or self.MAX_ITERATIONS)` — keep
  accepting `None` since `Repl`/`run()`/`repl()` may still pass it through);
  add `max_turn_tokens: Optional[int] = None` stored as `self.max_turn_tokens
  = int(max_turn_tokens or 0)` (`0` = disabled, matching ruby). Delete
  `_resolve_max_iterations`/`_resolve_max_output_tokens` entirely — callers
  now pass explicit, already-resolved values (from `Config.agent_*`).
  **Keep `cancel_event`** — ruby's `Agent` never had this concept in any
  step (ruby cancels via `Thread#raise(Interrupt)` entirely inside `Tui`,
  untouched by this diff); it's a Python-only mechanism established in step
  11's plan (judgment call 2 there) to work around Python's lack of a safe
  async-thread-interrupt primitive, and nothing in this step's ruby diff
  bears on it.
- `run()`: at the very top, call `self.context.reset_turn_tokens()` then a
  new private `self._compact_if_needed()`. Inside the loop, after the
  existing `_iteration_limit_reached()` check/return, add a
  `_token_limit_reached()` check/return (mirroring the iteration check's
  shape exactly: log `limit_reached(kind="max_tokens", n=self.context.turn_tokens,
  max=self.max_turn_tokens)`, `return self._wrap_up("max_tokens")`) —
  **before** the existing `cancel_event` check, matching ruby's ordering
  of "both hard-limit checks first, then the loop body." After computing
  `response`/`parsed` (call `self.builder.parse_response`), call
  `self._record_usage(response)` then `self._log_reasoning(parsed["content"])`
  before branching on `stop_reason`.
  - Non-tool branch: `self.logger.response(text=text,
    usage=response.get("usage"), stop_reason=parsed["stop_reason"],
    task=None, backend=self.builder.backend)` (judgment calls 1 and 2 — raw
    usage read faithfully as ruby now does, parsed stop_reason, `task=None`
    since `Context` has no `task` anymore); `self.logger.turn_end(reason="completed",
    iterations=self.iteration, tokens=self.context.turn_tokens)`.
- `_token_limit_reached(self) -> bool`: `self.max_turn_tokens > 0 and
  self.context.turn_tokens >= self.max_turn_tokens`.
- `_record_usage(self, response) -> None`: `usage = response.get("usage") or
  {}`; call `self.context.add_turn_tokens(usage.get("input_tokens"),
  usage.get("output_tokens"))` and
  `self.context.update_tokens(usage.get("input_tokens"))` — a direct,
  unnormalized read (judgment call 1: this only actually populates for
  Anthropic and the rewritten OpenAI backend, matching ruby's own
  step-12 regression rather than papering over it).
- `_compact_if_needed(self) -> None`: `if not
  self.context.needs_compaction(): return`; else capture `before =
  self.context.current_tokens`, `dropped = self.context.compact_messages()`,
  `self.logger.compaction(before=before, dropped=dropped,
  context_window=self.context.context_window)`.
- `_wrap_up(self, reason)`: after parsing the wind-down response, call
  `self._record_usage(response)` before logging; `self.logger.response(...,
  usage=response.get("usage"), stop_reason=parsed_wrap["stop_reason"],
  task=None, backend=self.builder.backend)`; `self.logger.turn_end(...,
  tokens=self.context.turn_tokens)`. The `except ApiError` fallback branch
  also gains `tokens=self.context.turn_tokens` on its `turn_end` call.
- `_extract_text`: join with `"\n"` instead of `""` (ruby: `.join("\n")`).
- New `_log_reasoning(self, content: List[Dict[str, Any]]) -> None`: for
  each block with `block.get("type") == "reasoning"`, compute `redacted =
  block.get("redacted") is True`, `text = str(block.get("text") or "")`;
  skip if `not text.strip() and not redacted`; else
  `self.logger.reasoning(text=text, redacted=redacted)`.
- `_handle_tool_calls`: replace the current single `_log_response(...)` call
  with: extract `preamble = self._extract_text(content)`; if
  `preamble.strip()`, call `self.logger.plan(text=preamble)`; always call
  `self.logger.response(text=f"(tool use — {len(tool_calls)}
  call{'s' if len(tool_calls) != 1 else ''})",
  usage=response.get("usage"), stop_reason="tool_use")` — no
  `task=`/`backend=` here (they default to `None`, matching ruby's call
  signature exactly omitting them).
- Delete both `_log_response` and `_normalized_usage` entirely (matching
  ruby's removal of `log_response`/`normalized_usage` in this same diff —
  judgment call 1). Every `usage=` argument above reads `response.get("usage")`
  directly; nothing in `Agent` normalizes across providers anymore, on
  either side of this port.

### 7. `Repl`: `/compact`, drop `task_settings`, thread `max_turn_tokens`

`src/boukensha/repl.py`:

- `__init__`: drop `task_settings`; add `max_turn_tokens: Optional[int] =
  None` alongside the existing `max_iterations`/`max_output_tokens`.
- `HELP` and `banner()`: add a `/compact` line each, matching ruby's
  wording (`"drop oldest 40% of messages to free context"` /
  `"free context (drop oldest messages)"`).
- `handle_command`: add an `elif task == "/compact":` branch —
  `dropped = self.context.compact_messages()`; `self._output(f"(compacted
  context — {dropped} messages dropped)")`; `return "command"`.
- `run_turn`: drop `task_settings=self.task_settings` from the `Agent(...)`
  it constructs, add `max_turn_tokens=self.max_turn_tokens`.

### 8. `Tui`: read `Context` directly, colour-code, log compaction

`src/boukensha/tui.py`:

- Delete `self._session_input_tokens`/`self._session_output_tokens` (both
  the `__init__` initializers and the accumulation in `_handle_event`'s
  `"response"` branch — `Context.current_tokens` now owns this).
- Add class-level `CTX_WARN_PCT = 70`, `CTX_ALERT_PCT = 85`, and a
  `_ctx_color(pct: int) -> str` helper returning `"red"` / `"yellow"` /
  `"dim"` (Textual's markup names — see below) at those thresholds.
- CSS: add two colour rules the progress/status Statics can switch into —
  simplest is to keep using Rich markup tags in `update()` calls (`[red]`,
  `[yellow]`, `[dim]`) rather than adding new CSS classes, matching how
  `_render_progress`'s active branch already uses inline `[cyan]...[/cyan]`
  markup instead of a CSS rule.
- `_render_progress`'s idle branch: replace `used = self._fmt_tokens(self._session_input_tokens)`
  with `pct = self._ctx.usage_pct()`, `color = self._ctx_color(pct)`, `used
  = self._fmt_tokens(self._ctx.current_tokens)`, `cap =
  self._fmt_tokens(self._ctx.context_window)`; render
  `f"[{color}]  [ready]   ctx {used} / {cap} ({pct}%)   {self._turn_count}
  turns[/{color}]"`.
- `_render_status`: same `pct`/`used`/`cap` computation; `ctx_indicator = "
  ⚠ " if pct >= self.CTX_ALERT_PCT else " "`; bar text becomes `f" boukensha
  v{ver} · {model}  ·  ctx {used}/{cap} ({pct}%){ctx_indicator}·  {tools}
  tools  ·  {clock} "` (status bar keeps its existing white-on-grey
  background — ruby doesn't recolor the whole bar, just adds the `⚠`).
- `_handle_event`: add an `elif phase == "compaction":` branch — `dropped =
  event.get("dropped")`; write `f"[context compacted — {dropped} messages
  dropped to free space]"` to the `#log` `RichLog`.

### 9. Backends: normalized `"reasoning"` blocks

`src/boukensha/backends/base.py`: add a class-level doc comment above
`BackendBase` documenting the shared content-block contract (reasoning
comes first, `text`/`signature`/`redacted` fields, providers that can't
accept it back drop it on the way in) — mirrors ruby's new `Backends::Base`
doc comment; no behavior change, `estimate_cost`/`model_info` etc. untouched.

`src/boukensha/backends/anthropic.py`:
- `parse_response`: map each raw content block through a new
  `_normalize_block` — `"thinking"` → `{"type": "reasoning", "text":
  block["thinking"], "signature": block.get("signature")}`;
  `"redacted_thinking"` → `{"type": "reasoning", "text": "", "redacted":
  True, "signature": block.get("data")}`; anything else passes through
  unchanged.
- `to_messages`: for `msg.role == "assistant"`, build content via a new
  `_assistant_content(msg.content)` instead of passing `msg.content` raw —
  text-only turns (a bare `str`) pass through unchanged; block-list turns
  map each block through `_denormalize_block` (the inverse: `"reasoning"` +
  `redacted` → `{"type": "redacted_thinking", "data": block["signature"]}`;
  `"reasoning"` (not redacted) → `{"type": "thinking", "thinking":
  block["text"], "signature": block["signature"]}`; everything else passes
  through).

`src/boukensha/backends/gemini.py`:
- `to_payload`: add `"thinkingConfig": self._thinking_config()` inside
  `generationConfig`.
- New `_thinking_config(self) -> dict`: `{"thinkingLevel": "LOW"}` if
  `self.model == "gemini-3.1-pro-preview-customtools"` else
  `{"thinkingBudget": 0}` — dead branch today (that model id isn't in
  `MODELS`) but mirrors ruby's forward-looking `case`/comment verbatim, see
  step 2's note about keeping the two `MODELS` tables' ids in sync.
- `parse_response`: when a part has `part.get("thought")`, append
  `{"type": "reasoning", "text": part.get("text", ""), "signature":
  part.get("thoughtSignature")}`; when a part is a `functionCall`, also
  carry `"signature": part.get("thoughtSignature")` into the emitted
  `tool_use` block.
- `_assistant_parts`: `tool_use` blocks re-add `thoughtSignature` when
  `b.get("signature")` is set; add a `"reasoning"` case emitting `{"text":
  b.get("text", ""), "thought": True}` (+ `thoughtSignature` if present).

`src/boukensha/backends/ollama.py`, `backends/ollama_cloud.py`:
- `to_payload`: add `"think": False`.
- `parse_response`: if `message.get("thinking")`, prepend a `{"type":
  "reasoning", "text": message["thinking"]}` block before the existing
  text/tool_use blocks (matching ruby's insertion order — reasoning first).

### 10. `OpenAI` backend: Responses API rewrite

`src/boukensha/backends/openai.py` — this is the largest single-file change,
a straight structural port of ruby's rewrite (see the ruby-file table above
for the full rationale: gpt-5.x rejects `reasoning_effort` + tools on
`/v1/chat/completions`):

- `BASE_URL = "https://api.openai.com/v1/responses"`.
- `MODELS`: drop `"gpt-5.4"`, add `"gpt-5.4-nano"` (`context_window:
  400_000`, `cost_per_million: {"input": 0.2, "output": 1.25}`,
  `"usage_unit": "tokens"`) — keep `"gpt-5.5"`/`"gpt-5.4-mini"` as-is.
- Rename `to_messages(system, messages)` → `to_input(self, messages) ->
  List[Dict]` (drops the `system` param — it becomes `instructions` at the
  payload level, not an input item). This is the rename judgment call 7
  flags: `PromptBuilder.to_messages()` still calls
  `backend.to_messages(...)`, unreachable in the real request path, and is
  left as-is rather than papered over. `flat_map` semantics — for each
  message, `tool_result` → one `{"type": "function_call_output", "call_id":
  msg.tool_use_id, "output": str(msg.content)}` item; `assistant` → the new
  `_assistant_items(msg.content)` (returns a list, see below); everything
  else → one `{"role": msg.role, "content": msg.content}` item.
- `to_tools`: flatten — drop the `"function": {...}` wrapper, put
  `name`/`description`/`parameters` directly alongside `"type":
  "function"`.
- `to_payload`: `{"model": self.model, "instructions": context.system,
  "input": self.to_input(context.messages), "tools": tools or
  self.to_tools(context.tools), "max_output_tokens": max_output_tokens,
  "reasoning": {"effort": "none"}}`.
- `parse_response`: iterate `response.get("output") or []`; for
  `item["type"] == "reasoning"`, join `item.get("summary", [])`'s `"text"`
  fields into one `"reasoning"` block; for `"message"`, join the
  `"output_text"`-typed entries of `item["content"]` into one `"text"`
  block (skip if empty); for `"function_call"`, stash the raw item and
  after the loop append one `"tool_use"` block per stashed call (`"id":
  call_id`, `"name"`, `"input": json.loads(arguments or "{}")`);
  `stop_reason = "tool_use" if any function_call items else "end_turn"`.
- `_assistant_items(self, content) -> List[Dict]`: text-only turns wrap to
  a single-block list first (existing pattern); join all `"text"`-type
  block text and, if non-empty, emit one `{"role": "assistant", "content":
  text}` item; then for each `"tool_use"` block emit one `{"type":
  "function_call", "call_id": b["id"], "name": b["name"], "arguments":
  json.dumps(b["input"])}` item. Reasoning blocks are dropped here — not
  re-sent (matches ruby's comment: gpt-5.x doesn't need them echoed back at
  `effort: "none"`).

### 11. `boukensha.rb` → `run.py`/`repl.py`: wire it all together

`src/boukensha/run.py` — both `run()` and `repl()` change identically:

- Add `context_window: Optional[int] = None` to the signature.
- After resolving `model`/`backend` (unchanged): `if context_window is
  None: context_window = Models.context_window(model)`.
- `Context(...)` call site: drop `task=task_class`, add
  `context_window=context_window`,
  `compaction_threshold=cfg.agent_compaction_threshold`.
- Replace `effective_max_iterations = task_class.max_iterations(task_settings)`
  / `effective_max_output_tokens = max_output_tokens if ... else
  task_class.max_output_tokens(task_settings)` with:
  ```python
  effective_max_iterations = cfg.agent_max_iterations
  effective_max_turn_tokens = cfg.agent_max_turn_tokens
  effective_max_output_tokens = (
      max_output_tokens if max_output_tokens is not None
      else cfg.agent_max_output_tokens
  )
  ```
- `Logger(...)` snapshot dict: add `"max_turn_tokens":
  effective_max_turn_tokens`, `"context_window": context_window`; drop
  `"task": task_class.task_name()` (ruby's snapshot drops it too — the
  snapshot is a point-in-time record of *this run's* limits, and `task`
  there was always just `"player"`, redundant with `provider`/`model`).
- `Agent(...)` (in `run()`) / the `dict` passed to `Repl(...)` (in
  `repl()`): drop `task_settings=task_settings`, add
  `max_turn_tokens=effective_max_turn_tokens`.
- Imports: add `from .models import Models`.
- `task_settings` itself is still computed and still used for
  `system`/`model`/`backend` resolution via `Player.system_prompt`/`.model`/
  `.provider` — only its use for iteration/token limits goes away.

`src/boukensha/cli.py`: no change — `--no-tui` wiring doesn't touch any of
this.

### 12. `__init__.py`: export `Models`

Add `from .models import Models` and `"Models"` to `__all__`, in the "New in
this step" block alongside the existing `Tui` export (matching the
established convention of noting *which* step introduced each late addition).

### 13. Fix up call sites and prompts

- `examples/example.py`: apply judgment call 4 — change the task string to
  the MUD-connect version, add `working_dir=False`, drop the `Servers:`
  print line, rewrite the header comment to describe the actual MCP
  mechanism (not a nonexistent `Tools::Mud`). Keep the existing
  `BOUKENSHA_DIR` default block (`os.environ.setdefault(...)`) — it already
  matches ruby's newly-added one path-for-path (both resolve to the repo
  root's `.boukensha`), so no change needed there.
- `examples/mcp_mud_demo.py`: `Context(task=Player, system="demo")` →
  `Context(system="demo")`.
- `test/helper.py`: same fix in `new_registry` —
  `Context(task=Player, system="test")` → `Context(system="test")`. If
  `Player` becomes an unused import in this file after the change, drop the
  import (check `test/helper.py` for other `Player` uses first).
- `prompts/system.md`: append ruby's new paragraph about
  `"[context compacted ...]"` notices being system-generated, not user
  input.

### 14. Rewrite the README

Replace the copied step-11 README with step-12 documentation: accurate
context tracking (`current_tokens` vs `context_window`, the old-bug
callout that a prior step conflated the output-token budget with the
context window), colour coding, auto-compaction + `/compact`,
`Logger.compaction`/`.reasoning`/`.plan` events, the `context_window:`
keyword on `run()`/`repl()`, provider reasoning normalization, the two
independent per-turn ceilings and the new `agent:` settings block. Note the
existing cost-estimation logging (already documented in this repo's prior
README, since Python shipped it ahead of ruby) now shares judgment call 1's
scope — call out plainly that automatic context/cost tracking is accurate
for Anthropic and OpenAI, and known-inert for Gemini/Ollama/OllamaCloud,
matching ruby exactly; `/compact` still works everywhere. Fold in judgment
call 6's substance (two settings namespaces, `tasks.player.*` vs `agent.*`)
as prose, not a dead link.

### 15. Add the launcher

Add `week1_baseline/bin/python/12_context`, byte-for-byte the same shape as
the existing `week1_baseline/bin/python/11_tui` (confirmed by reading that
file directly) with only the step directory changed:

```bash
#!/bin/bash
cd "$(dirname "$0")/../../python/12_context" || exit 1
source ../../../venv/bin/activate
pip install -e . > /dev/null 2>&1
boukensha "$@"
```

This invokes the installed `boukensha` console script (`cli.py`'s `main()`),
not `examples/example.py` — `example.py` is still the separate,
non-interactive one-shot `run()` demo established in step 10/11's plans and
untouched by this step; the launcher's job is to reach the interactive
REPL/TUI where `/compact` and the context gauge are actually visible.

## Target files

```text
week1_baseline/python/12_context/            (already copied from 11_tui)
  pyproject.toml                              version 0.12.0, description update
  README.md                                   replace step-11 documentation
  prompts/system.md                           append compaction-notice paragraph
  src/boukensha/
    __init__.py                               export Models
    models.py                                 new: model -> context_window table
    context.py                                drop task=, add context_window/compaction_threshold/current_tokens/turn_tokens + methods
    config.py                                 provider_type, model, agent_max_iterations/max_output_tokens/max_turn_tokens/compaction_threshold
    logger.py                                 prompt() gains context_window; new compaction()/reasoning()/plan()
    agent.py                                  max_turn_tokens, compaction, reasoning/plan events, raw response["usage"] everywhere (judgment calls 1-2), delete _normalized_usage/_log_response
    repl.py                                   /compact command, drop task_settings, thread max_turn_tokens
    tui.py                                    read Context directly, colour-code ctx display, compaction event
    run.py                                    context_window= on run()/repl(), agent_* config wiring, drop task_settings
    backends/base.py                          doc comment only
    backends/anthropic.py                     reasoning block normalize/denormalize
    backends/gemini.py                        thinkingConfig, reasoning block normalize/denormalize, signatures
    backends/ollama.py                        think: false, reasoning block from message.thinking
    backends/ollama_cloud.py                  think: false, reasoning block from message.thinking
    backends/openai.py                        rewritten: Responses API, MODELS table update
  examples/example.py                         task text, working_dir=False, drop Servers: line, honest header comment
  examples/mcp_mud_demo.py                    Context(system="demo") — drop task=
  test/helper.py                              Context(system="test") — drop task=
week1_baseline/bin/python/12_context           new launcher — mirrors 11_tui, invokes installed `boukensha` console script
```

Everything else under `week1_baseline/python/12_context/`
(`tool.py`, `message.py`, `registry.py`, `run_dsl.py`, `client.py`,
`state.py`, `prompt_builder.py`, `cli.py`, `tasks/`, `mcp/`, `tools/`,
`tasks/base.py`, `tasks/player.py`, other `test/*.py`) carries over from
`11_tui` unchanged — there is no ruby diff touching them (confirmed above).

## Dependency Chain

```
12_context (Models, Context token tracking/compaction, Agent max_turn_tokens, reasoning/plan events, agent: settings, OpenAI Responses API)
    ↓ extends/depends on
11_tui (Tui, tui=, on_output, handle_command, public run_turn/banner, cancel_event/TurnCancelled, --no-tui)
    ↓ extends/depends on
10_standard_tool_library (Mcp::Client, Tools::Mcp, working_dir, mcp_servers, tool_names)
    ↓ extends/depends on
08_the_repl_loop (Repl, repl, __version__)
    ↓ extends/depends on
07_the_run_dsl (RunDSL, run)
    ↓ extends/depends on
06_the_logger (Logger, state)
    ↓ extends/depends on
05_agent_loop (Agent)
    ↓ extends/depends on
04_api_client (Client, ApiError)
    ↓ extends/depends on
03_prompt_builder (PromptBuilder, Backends)
    ↓ extends/depends on
02_the_registry (Registry, UnknownToolError)
    ↓ extends/depends on
01_struct_skeleton (Tool, Message, Context)
    ↓ depends on
00_config (Config, Tasks.Base, Tasks.Player)
```

**Action**: Verify `11_tui` is installed/importable (`pip install -e .`
against the repo-root `venv`) before starting this port.

## Verification

Ruby ships no new automated coverage for this step's headline features
(compaction, `max_turn_tokens`, reasoning normalization), so this plan adds
Python-only tests rather than trying to match a ruby reference suite:

1. Compile every changed file; import `Models`, `Context`, `Agent`,
   `Config`, `Logger` from `boukensha`.
2. `Context`: `Context(system="x")` no longer accepts `task=`; default
   `context_window == 200_000`; `usage_pct()` at `current_tokens=170_000,
   context_window=200_000` is `85`; `needs_compaction()` is `True` at
   exactly the default `0.85` threshold and `False` just under it;
   `compact_messages()` on a 10-message context drops 4 (`ceil(10*0.4)`)
   and resets `current_tokens` to `0`; `clear_messages()` also resets
   `current_tokens`.
3. `Models.context_window("claude-haiku-4-5") == 200_000`;
   `Models.context_window("totally-unknown") ==
   Models.DEFAULT_CONTEXT_WINDOW`.
4. `Agent`: with a fake client/backend returning an Anthropic-shaped raw
   response (top-level `"usage"`), assert `context.current_tokens` and
   `context.turn_tokens` are non-zero after `agent.run()`. Then, separately,
   with a fake client/backend returning a Gemini-shaped raw response
   (`usageMetadata`, not `usage`) or an Ollama-shaped one
   (`prompt_eval_count`/`eval_count`, no `usage` key), assert
   `context.current_tokens`/`turn_tokens` stay `0` — this is the
   judgment-call-1 regression test, asserting the *documented, inherited*
   limitation stays stable and doesn't silently start working (which would
   mean the port diverged from ruby) or silently break further (which would
   mean an unrelated bug).
5. `Agent`: construct with `max_turn_tokens=10` and a fake client that
   always reports `usage={"input_tokens": 20, "output_tokens": 0}`; assert
   `run()` stops via `_wrap_up("max_tokens")` rather than looping past the
   iteration limit.
6. `Agent`: seed `context` with `current_tokens` above
   `context_window * compaction_threshold` before calling `run()`; assert
   `context.messages` shrinks and `logger`'s subscribed callback receives a
   `phase == "compaction"` event before the first `phase == "prompt"`
   event of that turn.
7. `Agent`: feed a fake backend `parse_response` that returns a
   `"reasoning"` block (`redacted=False`, non-empty `text`) followed by a
   `"text"` block; assert `logger` receives a `phase == "reasoning"` event
   with the reasoning text, and a `phase == "response"` event with only the
   final text (reasoning text must not leak into the response text).
   Repeat with `redacted=True, text=""` and assert the reasoning event
   still fires (empty+redacted is not filtered) but a plain empty,
   non-redacted block is filtered.
8. `Agent`: feed a tool-call response with reasoning/preamble text before
   the `tool_use` blocks; assert `logger` receives a `phase == "plan"`
   event with the preamble text, then a `phase == "response"` event whose
   text is the `"(tool use — N calls)"` placeholder, not the preamble.
9. `Repl.handle_command("/compact")` returns `"command"`, calls
   `context.compact_messages()`, and routes the drop-count message through
   `on_output` (or `print` when unset) — same pattern as the existing
   `/clear` test.
10. `OpenAI` backend: `to_payload` includes `"instructions"` (not a
    `messages[0] == {"role": "system", ...}` entry), `"input"` (not
    `"messages"`), and `"reasoning": {"effort": "none"}`; a fake `output[]`
    response with one `"reasoning"` item, one `"message"` item, and one
    `"function_call"` item parses to a `content` list in that order with
    the correct `stop_reason`; round-tripping a `"tool_use"` block through
    `_assistant_items` produces a `function_call`-typed input item with
    the same `call_id`/`name`/JSON-encoded `arguments`.
11. `Anthropic`/`Gemini`/`Ollama` backends: a raw response containing a
    `thinking`/`thought`/`message.thinking` field parses to a leading
    `"reasoning"` block; round-tripping an assistant message containing a
    `"reasoning"` block back through `to_messages`/`_assistant_parts`
    reproduces the provider-native shape (`thinking`/`redacted_thinking`
    for Anthropic, `thought: true` for Gemini) including the `signature`.
12. Manually run `week1_baseline/bin/python/12_context` against the repo's
    `.boukensha/settings.yaml` (no `agent:` block present today — confirms
    the new defaults apply): confirm the status bar shows `ctx X/Y (Z%)`
    instead of the old unlabeled "ctx X" session-sum display, the `⚠`
    appears once a long session crosses 85%, `/compact` works from the
    TUI (`ctrl` path not needed — it's an `Input.Submitted` slash command,
    unlike `ctrl+l`/`/clear`), and a compaction notice appears in the
    conversation log. Separately run `week1_baseline/bin/python/12_context
    --no-tui` and confirm `/compact` works in the plain REPL too.

## Acceptance criteria

- `week1_baseline/python/12_context` exists as a copy-plus-delta of
  `11_tui`, with no unrelated files changed.
- `Context` no longer accepts `task=`; requires `system=`; tracks
  `current_tokens` (last-response window pressure) separately from
  `turn_tokens` (cumulative per-turn spend) and exposes `usage_pct`/
  `needs_compaction`/`compact_messages`.
- `Agent` stops a turn at whichever of `max_iterations`/`max_turn_tokens`
  trips first, auto-compacts before starting a turn when the context is
  over threshold, and logs `reasoning`/`plan` events distinct from the
  final `response` event. Automatic token/context tracking (and therefore
  auto-compaction and the token ceiling actually *triggering*) is accurate
  for Anthropic and the rewritten OpenAI backend and inert for
  Gemini/Ollama/OllamaCloud — a faithfully-ported ruby regression, not a
  Python gap (judgment call 1). `/compact` (manual) works identically on
  every backend regardless, since it doesn't read usage data.
- `run()`/`repl()` gain a `context_window:` keyword defaulting to
  `Models.context_window(model)`; `max_iterations`/`max_output_tokens`/
  `max_turn_tokens` are sourced from `Config.agent_*` (a new `agent:`
  settings namespace), not from `tasks.player.*` — `Task.max_iterations`/
  `.max_output_tokens` remain defined but uncalled from these two
  functions.
- The TUI's context indicator reads real window usage
  (`current_tokens`/`context_window`), colour-coded grey/yellow/red at
  70%/85%, replacing the old unbounded session-token-sum display; a
  compaction event renders a log line.
- `OpenAI` backend targets the Responses API (`/v1/responses`); Anthropic,
  Gemini, Ollama, and Ollama Cloud backends normalize provider-native
  reasoning output into a shared `"reasoning"` content-block shape that
  round-trips through `to_messages`/`_assistant_*` unchanged.
- `pyproject.toml` gains no new dependencies — this step is pure
  Python/stdlib on top of what `11_tui` already installs.

## Not Ported (out of scope for this step)

- Ruby's cosmetic `errors.rb` alignment whitespace and `prompt_builder.rb`
  doc-comment-only diff beyond an equivalent Python docstring/comment where
  it's actually informative (`backends/base.py`).
- `Boukensha::Tasks::Base`/`Tasks::Player` changes — there are none; both
  stay exactly as `11_tui` shipped them.
- Any change to `boukensha_loader.rb` / `~/.boukensharc` resolution —
  untouched by ruby's step-12 diff, and Python has no gem-loader analogue
  (excluded since step 10's plan).
- A working link for judgment-call-6's referenced
  `docs/plans/context_delta/plan.md` — that document doesn't exist in this
  repo; its substance is folded into the rewritten README as prose instead.
- Reproducing ruby's dead `gemini-3.1-pro-preview-customtools` `MODELS`
  entry as an *active* table row — ruby itself ships it commented out with
  a "confirm before enabling" TODO; this plan mirrors that (comment, not a
  live entry) rather than activating an unconfirmed preview model.
- Any change to `lib/boukensha/mcp/client.rb` / `src/boukensha/mcp/client.py`
  — confirmed byte-identical between `11_tui` and `12_context`
  (`diff -q` exit 0) and no reference to `Bundler`/`with_unbundled_env`
  anywhere in either ruby tree. An earlier draft of this plan (not this
  one) claimed a Bundler-env-leak fix and a stderr-on-EOF diagnostic landed
  here in this step; neither exists in the actual source, so neither is
  ported.
