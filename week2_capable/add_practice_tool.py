#!/usr/bin/env python3
"""Add practice skill tool to boukensha.

This script adds a 'practice' tool that allows practicing skills with the guildmaster.
Call this to enable: practice <skill_name>

Usage:
    from add_practice_tool import add_practice_tool

    def setup_tools(dsl):
        add_practice_tool(dsl)

    boukensha.run("explore", configure=setup_tools)
"""

def add_practice_tool(dsl):
    """Add practice skill tool to the RunDSL.

    Args:
        dsl: RunDSL object from boukensha.run(..., configure=...)

    Usage:
        practice kick
        practice punch
        practice dodge
    """

    @dsl.tool(
        "practice",
        description="Practice a skill with the guildmaster to improve your fighting abilities",
        parameters={
            "skill": {
                "type": "string",
                "description": "The skill to practice (e.g., kick, punch, dodge, parry, backstab)"
            }
        }
    )
    def practice(skill: str) -> str:
        """Practice a skill with the guildmaster.

        This tool sends a 'practice' command to the MUD guildmaster.
        Use this when you're at the Guild of Swordsmen with the guildmaster
        to learn or improve fighting skills.

        Available skills to practice:
        - kick: Leg strike technique
        - punch: Fist strike technique
        - dodge: Evasion technique
        - parry: Defense technique
        - backstab: Precision strike from behind
        - headbutt: Head strike technique
        - whirlwind: Multi-target strike
        """
        # Normalize skill name
        skill_name = skill.lower().strip()

        # Common skill name variations
        skill_aliases = {
            "spinning kick": "spin kick",
            "back flip": "backflip",
            "fire breath": "firebreath",
        }
        skill_name = skill_aliases.get(skill_name, skill_name)

        # The practice command format is: practice <skill>
        return f"practice {skill_name}"


if __name__ == "__main__":
    import sys
    sys.path.insert(0, "src")

    from boukensha import run

    def configure_with_practice(dsl):
        add_practice_tool(dsl)

    task = input("Enter your task: ").strip()
    if not task:
        task = "practice kick"

    result = run(task, configure=configure_with_practice)
    print(result)
