# Step 12 — Context Management

## Build
gem build boukensha.gemspec
gem install boukensha-0.12.0.gem

When you call an LLM directly you are responsible for the context window. There is no auto-compacting. This step adds proper token tracking, visual warnings, and automatic compaction so the agent never silently blows past the limit — carried on top of the MCP-host architecture and terminal UI introduced in earlier steps.

Boukensha ships **no tools of its own**. It is an MCP *host*: every tool the
agent can call comes from an MCP server declared in `settings.yaml`. Want file
access? Plug in a filesystem server. Want to play a MUD? Plug in
`mud-manager --mcp`. An agent with an empty `mcp_servers:` block can only talk.

## What's new

### Accurate context tracking

`Context` now maintains two distinct token counts:

| Attribute | What it measures |
|-----------|-----------------|
| `context_window` | The model's maximum input token capacity, looked up per-model via `Boukensha::Models.context_window` |
| `current_tokens` | Tokens actually used in the most recent API call (`usage.input_tokens` from the response) |

Previously `token_budget` (8,192) was displayed as the limit — that was the *output* `max_tokens`, not the context window. And the cumulative session token sum was shown as usage, which grew without bound even after `/clear`. Both are fixed.

The Agent updates `current_tokens` after every API response (including mid-turn tool-use calls), so the display always reflects what the next call will actually send.

### Context colour coding

The progress and status lines now colour the context indicator based on how full the window is:

| Usage | Colour | Meaning |
|-------|--------|---------|
| < 70% | Grey | Normal |
| 70–84% | Yellow | Approaching limit |
| ≥ 85% | Red | Compaction imminent |

A `⚠` symbol also appears in the status bar at 85%+.

### Auto-compaction

At the start of each agent turn, if `current_tokens / context_window ≥ 0.85` (configurable via `agent.compaction_threshold` in `settings.yaml`), the Agent automatically compacts the context before making any API call:

```
[context compacted — 12 messages dropped to free space]
```

Compaction drops the oldest 40% of messages (keeping at least 2) and resets `current_tokens` to 0. The first API call after compaction will report the true new size.

### `Context#compact_messages!`

```ruby
dropped = context.compact_messages!(target_fraction: 0.60)
# => 12  (number of messages dropped)
```

### `/compact` command

Manual compaction from the REPL or TUI, alongside `/quiet` and `/loud` for toggling detailed logging:

```
boukensha> /compact
(compacted context — 12 messages dropped)
```

### `Logger#compaction` event

```json
{"phase":"compaction","before":172000,"dropped":12,"context_window":200000}
```

Emitted whenever auto- or manual compaction runs. The TUI subscribes to this event to display the compaction notice in the conversation view.

### `Boukensha.run` / `Boukensha.repl` — `context_window:` keyword

`token_budget:` is replaced by `context_window:` (default: looked up from `Boukensha::Models` for the configured model):

```ruby
Boukensha.repl(context_window: 128_000)  # override for a non-standard model
```

### Reasoning / thinking normalization

Every backend normalizes provider-native "thinking" output into a common content-block shape (see `Boukensha::Backends::Base`'s doc comment for the full contract):

```ruby
{ "type" => "reasoning", "text" => "...", "signature" => "...", "redacted" => false }
```

Anthropic's `thinking`/`redacted_thinking` blocks, Gemini's `thought`/`thoughtSignature`, and Ollama/Ollama Cloud's `message["thinking"]` all map onto this shape. Reasoning blocks are logged via `Logger#reasoning` and surfaced by `Agent#log_reasoning` as their own event, separate from the response text.

### Two independent per-turn ceilings

`Agent` now stops a turn at whichever limit trips first: `max_iterations` (tool-call rounds) or `max_turn_tokens` (cumulative input+output tokens for the turn). Both are configurable under settings.yaml's `agent:` block (`max_iterations`, `max_output_tokens`, `max_turn_tokens`, `compaction_threshold`), read via `Config#agent_*`.

### Cost-estimation logging

`Logger#response` now accepts `task:`/`backend:` and attaches `execution_metadata` (`provider`, `model`, `usage_unit`, `usage_level`, `input_tokens`, `output_tokens`, `cost_usd`) to every response log line, estimated from each backend's `MODELS` cost table.

## MCP host

### `Boukensha::Mcp::Client`

A minimal MCP-over-stdio client: spawn a server, handshake, `tools/list`,
`tools/call`. It is server-agnostic — `command` / `args` / `env` is the standard
stdio transport config, the same triple every MCP host uses.

### `Boukensha::Tools::Mcp`

The only file under `tools/`. Registers a server's discovered tools into a
registry, optionally scoping their names with a `prefix:`.

```ruby
Boukensha::Tools::Mcp.register(
  registry,
  command: "mud-manager", args: ["--mcp"],
  env: { "MUD_HOST" => "localhost" },
  prefix: "tbamud"          # the daemon's `look` registers as `tbamud__look`
)
```

Prefixing is applied **client-side**: the server still sees `look` on the wire.
It exists so two servers can't silently clobber each other's names — a collision
raises and names the fix.

### `mcp_servers:` in `settings.yaml`

Adding a capability is a config edit, not a code change:

```yaml
mcp_servers:
  mud:
    command: mud-manager
    args:    [--mcp]
    prefix:  tbamud
    env:                     # a stdio server's credentials travel by environment
      MUD_HOST:     your.mud.host
      MUD_NAME:     Gandalf
      MUD_PASSWORD: secret

  filesystem:
    command:  npx
    args:     [-y, "@modelcontextprotocol/server-filesystem", /tmp]
    prefix:   fs
    required: false          # can't start? warn and carry on
```

| Key | Default | Meaning |
|-----|---------|---------|
| `command` | — | Executable to spawn. Resolved by the OS, so a relative path depends on your cwd — nothing hunts for a binary for you. |
| `args` | `[]` | Its argv. |
| `env` | `{}` | Extra environment. Servers inherit boukensha's environment; these keys override it. |
| `prefix` | none | Scopes discovered names (`fs` → `fs__read_file`). |
| `required` | `true` | `false` downgrades a failure to start into a warning. |

### What went away

| Gone | Replaced by |
|------|-------------|
| `Tools::FileSystem` (`pwd`, `read_file`, `write_file`, `search_files`, …) | a filesystem MCP server. Trade-off: needs node/npx, and its root is fixed in `args:` instead of tracking `working_dir`. |
| `Tools::Shell` (`run_command`) | a shell MCP server of your choosing (none configured yet). |
| `Tools::Mud` (embedded `MudManager::Session`) | the `mud-manager --mcp` daemon, which already wrapped the same `mud_manager` gem. |
| `Tools::McpMud`, the `mud:` / `working_dir:` / `allowed_commands:` / `shell_timeout:` arguments, `BOUKENSHA_MUD_MODE`, and `mud:` in settings.yaml | one `mcp_servers:` entry. |

The gemspec declares **no tool dependencies at all** — `mud_manager` went
with `Tools::Mud`. Servers are separate processes and bring their own; boukensha
itself needs only `charm`, for the TUI.

`working_dir:` survives on `Boukensha.run` / `.repl`, but only as Context
metadata: it registers nothing.

## Terminal UI

`Boukensha::Tui` wraps a `Repl` instance and replaces its raw `puts`/`gets` I/O with a structured four-zone display:

```
┌──────────────────────────────────────────────┐
│  conversation viewport (scrollable)           │
├──────────────────────────────────────────────┤
│  ⟳ live progress line (hidden when idle)     │
├──────────────────────────────────────────────┤
│  boukensha> input box                         │
├──────────────────────────────────────────────┤
│  status line (always-on)                      │
└──────────────────────────────────────────────┘
```

The **progress line** shows a spinner, current action, iteration counter (`n/MAX`), elapsed seconds, token counts (↑ in / ↓ out), and tool call count while the agent is running. When idle it shows context usage (colour-coded, see above) and turn count.

The **status line** always shows: version · model · context tokens used/max (colour-coded, with a `⚠` at 85%+) · registered tool count · wall-clock time.

**Keyboard shortcuts:**

| Key | Action |
|-----|--------|
| `Enter` | Submit input or slash command |
| `Esc` | Interrupt the running agent turn |
| `Ctrl+L` | Clear conversation history |
| `PgUp` / `PgDn` | Scroll conversation viewport |
| `Ctrl+C` / `Ctrl+D` | Quit |

The agent runs in a background thread so the UI stays responsive during long turns.

### `Boukensha.repl` — `tui:` keyword

```ruby
Boukensha.repl(tui: true)   # default — launches charm TUI
Boukensha.repl(tui: false)  # falls back to plain terminal REPL
```

The `--no-tui` CLI flag sets `tui: false` from the command line.

### `Repl`, composable

`Repl` doesn't hard-code `puts`/`gets`. Three methods are public so `Tui` (or any other front-end) can drive it:

| Method | Purpose |
|--------|---------|
| `on_output(&block)` | Route all REPL output through a callback instead of stdout |
| `handle_command(input)` | Process a slash command; returns `:quit`, `:command`, or `nil` |
| `run_turn(input)` | Run one agent turn and route the result through `on_output` |

`banner`, `logger`, `context`, `model`, and `version` are also exposed as readers.

### `Logger#subscribe`

```ruby
logger.subscribe { |event| ... }
```

Every structured log event (`:iteration`, `:tool_call`, `:tool_result`, `:response`, `:compaction`, `:reasoning`, etc.) is broadcast to all registered subscribers as well as being written to the JSONL file. `Tui` uses this to update the live progress line and conversation view in real time without polling.

## Run the demo

The TUI is interactive, so it's run via the global `boukensha` executable
rather than `examples/example.rb` (that file is the one-shot `Boukensha.run`
demo — it doesn't exercise the TUI).

```sh
# Offline, no API key, no live MUD — uses the daemon's built-in fake MUD:
ruby examples/mcp_mud_demo.rb --dry

# One-shot Boukensha.run demo:
ruby examples/example.rb

# Build and install this step's gem. If a later step's gem is already
# installed, `boukensha` will keep launching that version's loader instead —
# remove it first:
gem uninstall boukensha

gem build boukensha.gemspec
gem install boukensha-0.12.0.gem

# launches the charm TUI:
BOUKENSHA_DIR=/home/system/claude-code-camp-2026-Q2/.boukensha BOUKENSHA_PATH=/home/system/claude-code-camp-2026-Q2/week1_baseline/ruby/12_context boukensha

# plain REPL (no charm dependency required):
BOUKENSHA_PATH=/home/system/claude-code-camp-2026-Q2/week1_baseline/ruby/12_context boukensha --no-tui
```

```sh
bundle exec bin/boukensha
```

## Tests

```sh
rake test
```

## Technical Considerations
This is just observations we dont want to fix these right now just to perserve current future layers.
- It seems like we need more tool work, as there might not be enough tools to accomplish tasks efficently and mostly are mapping the same task to primitives.
- Servers spawn **eagerly** at boot: every entry costs a subprocess and a handshake even if the LLM never calls it. Fine at two servers; revisit past that.
- Non-text MCP content blocks (images, embedded resources) are dropped rather than rendered — they yield an empty string, not an exception. No MUD tool can hit this.
- The backends advertise every listed parameter as required, which is wrong for third-party servers with genuinely optional params. Fixing it means plumbing `inputSchema["required"]` through `Boukensha::Tool`, which touches all tools.
- `~/.boukensharc` YAML support (`boukensha_path:` / `boukensha_dir:` keys, plus bare single-line path backward compat) from step 9 was not carried forward into an earlier rewrite, which silently mis-parsed step-9-era rc files. This step's loader restores that step-9 behavior verbatim — see [`docs/plans/floating_artifacts/bounkensharc.md`](../../../docs/plans/floating_artifacts/bounkensharc.md) for the incident writeup; keep that doc in mind before rewriting `boukensha_loader.rb` in later steps.
- Two settings namespaces now exist for conceptually similar things: `tasks.player.*` (provider/model/prompt overrides) and `agent.*` (per-turn circuit breakers). See `docs/plans/context_delta/plan.md` open question 1 before consolidating.
