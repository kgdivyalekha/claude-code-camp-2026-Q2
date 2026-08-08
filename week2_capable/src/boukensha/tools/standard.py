"""Built-in standard tools available in all boukensha sessions.

These tools are always registered and do not require special configuration.
They complement MCP tools for common MUD interactions.
"""

from typing import Any, Dict, Callable


def register_standard_tools(registry) -> None:
    """Register all standard built-in tools.

    These tools are always available without needing configure callbacks.

    Args:
        registry: The tool registry to register tools with
    """
    _register_practice_tool(registry)


def _register_practice_tool(registry) -> None:
    """Register the practice skill tool for training at the guildmaster."""

    @registry.tool(
        "practice",
        description="Practice a skill with the guildmaster at the Guild of Swordsmen to improve your fighting abilities. This is a native tbaMUD command.",
        parameters={
            "skill": {
                "type": "string",
                "description": "The skill to practice: kick, punch, dodge, parry, backstab, headbutt, whirlwind",
                "examples": ["kick", "punch", "dodge"]
            }
        }
    )
    def practice(skill: str) -> str:
        """Practice a skill with the guildmaster.

        Available skills:
        - kick: Leg strike technique
        - punch: Fist strike technique
        - dodge: Evasion technique
        - parry: Defense technique
        - backstab: Precision strike from behind
        - headbutt: Head strike technique
        - whirlwind: Multi-target strike

        This is a native tbaMUD command - works just like look, examine, etc.
        """
        skill_name = skill.lower().strip()

        # Handle skill name aliases
        skill_aliases = {
            "spinning kick": "spin kick",
            "back flip": "backflip",
            "fire breath": "firebreath",
        }
        skill_name = skill_aliases.get(skill_name, skill_name)

        return f"practice {skill_name}"
