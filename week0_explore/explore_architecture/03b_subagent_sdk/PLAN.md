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
     (mirrors how the `Agent`/`Task` tool currently invokes it).
   - **Multi-player execution runs in the foreground, never backgrounded.**
     `argv` is parsed as one or more `"login: goal"` assignments (e.g.
     `python3 scripts/run_agent.py "queen: kill rats near temple square" "horseman: explore north of the temple"`).
     Each assignment gets its own `ClaudeSDKClient` session, all driven
     concurrently via `asyncio.gather` in the same process — no
     `nohup`/`&`/detached subprocess, so a Ctrl-C or process exit stops every
     player immediately and nothing keeps running unobserved.
   - Every message from every player's session is printed to stdout as soon
     as it arrives, tagged with that player's login (e.g. `[queen] ...`,
     `[horseman] ...`), so the status of every player is visible live while
     they're playing, not just in a final summary.
   - With no `argv`, fall back to the original single-session interactive
     loop (`python3 scripts/run_agent.py`, one request typed at a time) —
     useful for ad hoc exploration outside a scripted multi-player run.

3. **Retire the filesystem definition**
   - Delete `.claude/agents/mud-player.md` (or move its content, since it's
     now fully represented in `run_agent.py`) so there's a single source of
     truth and no risk of the two definitions drifting apart.
   - Leave `.claude/settings.local.json` alone unless permissions need
     adjusting for the new script.

4. **Update usage docs**
   - `scripts/run_agent.py`'s module docstring documents both entry points:
     multi-player non-interactive (`"login: goal"` args, concurrent,
     foreground, live per-player status) and the single-session interactive
     fallback. `scripts/example_gameplay.sh` is unrelated (it exercises
     `mud_connection.py` directly) and stays as-is.

## Verification

- `python3 -c "import claude_agent_sdk"` succeeds after install.
- Run `python3 scripts/run_agent.py "queen: list known players"` and confirm
  the SDK invokes the `mud-player` subagent (visible via streamed tool-use
  events) rather than any file-based agent lookup, and that it correctly
  calls `scripts/mud_connection.py --action list-players`.
- Run with two assignments at once, e.g.
  `python3 scripts/run_agent.py "queen: check score" "horseman: check score"`,
  and confirm both run concurrently in the foreground (no backgrounding) with
  interleaved, per-player-tagged output appearing live as each session
  progresses, not buffered until the end.
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
- The new driver file that you create must receive the user request from an interactive loop
