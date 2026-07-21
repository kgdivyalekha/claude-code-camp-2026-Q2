#!/usr/bin/env python3
"""Driver for the mud-player subagent, defined via the Claude Agent SDK.

Unlike a plain Claude Code session, this script does not rely on Claude Code's
filesystem discovery of `.claude/agents/*.md`. The `mud-player` subagent is
built entirely in code using `claude_agent_sdk.AgentDefinition` (see
`build_agent_definition` below) and registered with `ClaudeAgentOptions(agents=...)`.
`setting_sources=[]` disables filesystem settings/agent discovery outright, so
the only subagent available is the one defined here.

Two ways to run it:

1. Multi-player, non-interactive (foreground, live status per player):
       python3 scripts/run_agent.py "queen: kill rats near temple square" \\
                                     "horseman: explore north of the temple"
   Each `login: goal` argument spawns its own concurrent agent session for
   that character. All sessions run in this process, in the foreground —
   nothing is detached or backgrounded — and every message each one produces
   is printed immediately, tagged with that player's name, as it happens.

2. Interactive, single-session (no CLI args): prompts for one request at a
   time, same as before.
"""

import asyncio
import sys
from pathlib import Path

from claude_agent_sdk import (
    AgentDefinition,
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROMPT_FILE = PROJECT_ROOT / "prompts" / "mud_player_prompt.md"

AGENT_NAME = "mud-player"
AGENT_DESCRIPTION = (
    'Play the tbaMUD (CircleMUD variant) game running on localhost:4000 as any '
    "known character (see data/players/). Delegate to this agent whenever the "
    "user asks to play the MUD, connect to the game, move around, fight "
    "monsters, check inventory or stats, level up, hunt a specific monster, "
    "map the world, or continue a previously started game goal — even if they "
    'just say "keep playing" or "continue the quest". Also use it for any '
    "long-horizon goal that spans many commands or multiple sessions. If the "
    'user names a character (e.g. "play as queen", "log in gandalf"), pass '
    "that login through; otherwise let the agent figure out which character "
    "to use."
)
AGENT_TOOLS = ["Bash", "Read", "Edit", "Write"]

ORCHESTRATOR_SYSTEM_PROMPT = (
    "You are the entry point for a tbaMUD gameplay project. For every user "
    f"request, delegate to the `{AGENT_NAME}` subagent via the Task tool — do "
    "not play the game or run scripts/mud_connection.py directly yourself."
)


def build_agent_definition() -> AgentDefinition:
    prompt_text = PROMPT_FILE.read_text(encoding="utf-8")
    return AgentDefinition(
        description=AGENT_DESCRIPTION,
        prompt=prompt_text,
        tools=AGENT_TOOLS,
    )


def build_options(system_prompt: str = ORCHESTRATOR_SYSTEM_PROMPT) -> ClaudeAgentOptions:
    return ClaudeAgentOptions(
        agents={AGENT_NAME: build_agent_definition()},
        system_prompt=system_prompt,
        cwd=str(PROJECT_ROOT),
        # [] disables loading .claude/settings*.json and .claude/agents/*.md —
        # the mud-player subagent comes solely from the AgentDefinition above.
        setting_sources=[],
        # Only "Task" is exposed at the top level so every request is forced
        # through the mud-player subagent instead of the orchestrator running
        # Bash/Read/Edit/Write itself. The subagent's own tool access is
        # scoped separately via AgentDefinition(tools=AGENT_TOOLS) above.
        allowed_tools=["Task"],
        permission_mode="bypassPermissions",
    )


def render_message(message, prefix: str = "") -> None:
    pad = f"{prefix} " if prefix else ""
    if isinstance(message, AssistantMessage):
        for block in message.content:
            if isinstance(block, TextBlock):
                print(f"{pad}{block.text}")
            elif isinstance(block, ToolUseBlock):
                print(f"{pad}  [tool call] {block.name}({block.input})")
    elif isinstance(message, ResultMessage):
        if message.is_error:
            print(f"{pad}  [error] {message.result}")
        cost = f"${message.total_cost_usd:.4f}" if message.total_cost_usd else "n/a"
        print(f"{pad}  [turn complete: {message.num_turns} turns, cost {cost}]")


def parse_assignments(argv: list[str]) -> list[tuple[str, str]]:
    """Parse `login: goal` CLI arguments into (login, goal) pairs."""
    assignments = []
    for arg in argv:
        if ":" not in arg:
            raise SystemExit(
                f"Invalid assignment {arg!r}; expected the form 'login: goal' "
                "(e.g. \"queen: kill rats near temple square\")"
            )
        login, goal = arg.split(":", 1)
        login, goal = login.strip(), goal.strip()
        if not login or not goal:
            raise SystemExit(f"Invalid assignment {arg!r}; both login and goal are required")
        assignments.append((login, goal))
    return assignments


async def run_player(login: str, goal: str, prefix: str) -> None:
    """Run one character's play session to completion, streaming its status live."""
    system_prompt = (
        "You are the entry point for a tbaMUD gameplay project. For this "
        f"request, delegate to the `{AGENT_NAME}` subagent via the Task tool — "
        "do not play the game or run scripts/mud_connection.py directly "
        f"yourself. Always play as the character '{login}' (read "
        f"data/players/{login}.md for its login/password and current goal) "
        f"and pursue this goal: {goal}"
    )
    print(f"{prefix} starting — goal: {goal}")
    async with ClaudeSDKClient(options=build_options(system_prompt=system_prompt)) as client:
        await client.query(goal)
        async for message in client.receive_response():
            render_message(message, prefix=prefix)
    print(f"{prefix} done")


async def run_players(assignments: list[tuple[str, str]]) -> None:
    """Run every assigned player concurrently in this process (foreground,
    not backgrounded), printing each one's status live as it plays."""
    tag_width = max(len(login) for login, _ in assignments)
    print(
        f"Running {len(assignments)} player(s) concurrently in the foreground — "
        "each line below is tagged with its player and printed as it happens.\n"
    )
    await asyncio.gather(
        *(
            run_player(login, goal, prefix=f"[{login:<{tag_width}}]")
            for login, goal in assignments
        )
    )


async def run_interactive() -> None:
    print(f"mud-player agent ready (prompt loaded from {PROMPT_FILE.relative_to(PROJECT_ROOT)}).")
    print("Type a request (e.g. 'play as queen'). Empty line or 'exit' quits.\n")

    async with ClaudeSDKClient(options=build_options()) as client:
        while True:
            try:
                user_input = await asyncio.to_thread(input, "> ")
            except EOFError:
                break
            user_input = user_input.strip()
            if not user_input or user_input.lower() in {"exit", "quit"}:
                break

            await client.query(user_input)
            async for message in client.receive_response():
                render_message(message)
            print()


async def main() -> None:
    argv = sys.argv[1:]
    if argv:
        await run_players(parse_assignments(argv))
    else:
        await run_interactive()


if __name__ == "__main__":
    asyncio.run(main())
