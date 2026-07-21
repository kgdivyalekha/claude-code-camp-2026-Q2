# Plan: Replace filesystem subagent loading with SDK `AgentDefinition`

## Current state

This directory currently has **no custom driver code** — it's a plain Claude
Code project. The "filesystem loading" is Claude Code's own built-in
mechanism: it discovers `.claude/agents/mud-player.md` automatically and
exposes it as a `mud-player` subagent to the `Agent`/`Task` tool. Nothing in
this repo reads that file explicitly; the CLI does it implicitly by scanning
`.claude/agents/*.md`.

Relevant files today:
- `.claude/agents/mud-player.md` — YAML frontmatter (`name`, `description`,
  `tools`) + a markdown system prompt body. This is the thing being replaced.
- `scripts/mud_connection.py` — the actual game-interaction tool (netcat-style
  MUD client). Not part of the subagent-loading mechanism; stays as-is.
- `data/players/*.md`, `data/world.md` — persistent memory the subagent
  reads/writes. Stays as-is.
- `evals/evals.json`, `scripts/example_gameplay.sh` — stay as-is (they
  exercise `mud_connection.py` directly, not the agent).

## Goal

Stop relying on Claude Code's filesystem discovery of `.claude/agents/*.md`.
Instead, define the `mud-player` subagent **in code**, using the Claude Agent
SDK's `AgentDefinition` type, and drive it from a Python script using the SDK
client rather than the interactive CLI.

## Changes

1. **Add the SDK dependency**
   - Add `claude-agent-sdk` to the project's Python dependencies (installed
     into `../../../venv`). Requires Node.js on PATH (the SDK shells out to
     the Claude Code CLI under the hood) — verify this as a prerequisite
     before writing the script.

2. **New driver script: `scripts/run_agent.py`**
   - Import `ClaudeAgentOptions`, `AgentDefinition`, and `ClaudeSDKClient`
     (or the `query()` helper) from `claude_agent_sdk`.
   - Port the contents of `.claude/agents/mud-player.md` into code:
     - frontmatter `description` → `AgentDefinition(description=...)`
     - frontmatter `tools: Bash, Read, Edit, Write` → `AgentDefinition(tools=[...])`
     - the markdown body (play loop, combat strategy, memory conventions,
       server-specific lessons, troubleshooting) → `AgentDefinition(prompt=...)`
     - frontmatter `name: mud-player` → the dict key under `agents={}`
   - Build `ClaudeAgentOptions(agents={"mud-player": AgentDefinition(...)}, cwd=<project root>, allowed_tools=[...])`
     so the subagent is registered programmatically instead of via file
     discovery.
   - Top-level orchestrator prompt delegates to the `mud-player` subagent
     (mirrors how the `Agent`/`Task` tool currently invokes it), taking a
     user instruction from `argv` (e.g. `python3 scripts/run_agent.py "play as queen"`).
   - Stream and print the SDK's response messages to stdout so behavior is
     observable the same way the CLI's subagent output is today.

3. **Retire the filesystem definition**
   - Delete `.claude/agents/mud-player.md` (or move its content, since it's
     now fully represented in `run_agent.py`) so there's a single source of
     truth and no risk of the two definitions drifting apart.
   - Leave `.claude/settings.local.json` alone unless permissions need
     adjusting for the new script.

4. **Update usage docs**
   - Adjust `scripts/example_gameplay.sh` comments or add a short usage note
     (e.g. in a new `scripts/README.md` or inline comment) pointing at
     `python3 scripts/run_agent.py "<instruction>"` as the new entry point
     for playing via the agent, distinct from calling `mud_connection.py`
     directly.

## Verification

- `python3 -c "import claude_agent_sdk"` succeeds after install.
- Run `python3 scripts/run_agent.py "list known players"` and confirm the
  SDK invokes the `mud-player` subagent (visible via streamed tool-use
  events) rather than any file-based agent lookup, and that it correctly
  calls `scripts/mud_connection.py --action list-players`.
- Confirm `.claude/agents/` no longer influences behavior (e.g. temporarily
  rename/remove it and see the script still works, since it no longer reads
  from there).
- If a MUD server is reachable at `localhost:4000`, run a short session
  (`init` + `look`) end-to-end through the new script to confirm parity with
  the old filesystem-driven subagent.

## Open questions for the user

- Is `claude-agent-sdk` allowed to be installed into the shared `venv` at
  the repo root, or should this get its own virtualenv?
  A: Yes. you are allowed to install venv at repo root
- Should `.claude/agents/mud-player.md` be deleted outright, or kept (unused)
  for reference/comparison against `03a_subagent_sdk`?
  A: Yes, you can delete it from 03b_subagent_sdk
- Prompt text: to be loaded from markdown file
- The new driver file that you create must receive the user request from an interactive inline loop and not to throw new line while a prompt is being executed.
