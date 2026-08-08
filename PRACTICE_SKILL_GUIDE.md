# Practice Skill Tool Guide

## Overview

The `practice` tool enables your agent to train and improve fighting skills with the guildmaster at the Guild of Swordsmen. This tool allows you to use commands like:

```
practice kick
practice punch
practice dodge
```

## Location

The Guild of Swordsmen is located at:

1. From Temple Square, go **south** to Market Square
2. From Market Square, go **east** to Main Street
3. From Main Street, go **east** to Guild of Swordsmen entrance
4. From Guild entrance, go **east** to Bar of Swordsmen
5. From Bar, go **south** to Tournament and Practice Yard

The **guildmaster** is in the Tournament and Practice Yard.

## Available Skills to Practice

| Skill | Description |
|-------|-------------|
| **kick** | Leg strike technique - powerful kick attack |
| **punch** | Fist strike technique - quick melee attack |
| **dodge** | Evasion technique - defensive movement |
| **parry** | Defense technique - block incoming attacks |
| **backstab** | Precision strike - attack from behind |
| **headbutt** | Head strike technique - close-range attack |
| **whirlwind** | Multi-target strike - hit multiple enemies |

## How to Use

### Quick Start

The `practice` tool is a **native MCP tool from mud_manager** — just like `look`, `examine`, `drink`. 

Simply include it in your task:

```python
import boukensha

result = boukensha.run(
    task="Navigate to the guildmaster and practice kick"
)
```

The agent will automatically use: `practice kick`

### Requirements

The `practice` tool must be enabled in your settings:

```yaml
# .boukensha/settings.yaml
tokens:
  always_visible:
    - "*__practice"  # Enable practice command

permissions:
  rules:
    - allow: ["*__practice"]  # Allow practice skill training
```

### In Your Code

Just use it like any other MUD command:

```python
import boukensha

result = boukensha.run(
    task="Go to Tournament Yard and practice kick with the guildmaster"
)
```

The `practice` tool is a **native mud_manager command** just like:
- `look` - examine your surroundings
- `examine <object>` - look closely at something
- `drink fountain` - drink from a fountain
- `practice kick` - practice a skill ✅ (native MCP tool!)

## Skill Progression

When you practice a skill:

1. **First practice**: Skill starts at 1% proficiency
2. **Repeated practice**: Gradually increases skill level
3. **Success**: Skill reaches 100% (master level)

Each practice session takes time in the MUD and may consume movement or action points, depending on the MUD rules.

## Strategy

### Best Skills to Start With

- **kick** - Core martial arts technique, high damage
- **punch** - Quick attack that doesn't require special equipment
- **dodge** - Defensive skill that saves HP

### Skill Synergies

- **Combat path**: kick → backstab → whirlwind
- **Defense path**: dodge → parry → counterattack
- **Balanced path**: kick → dodge → punch

## Implementation Details

### Native MCP Tool

The `practice` tool is provided **natively by mud_manager** as an MCP tool.

It's defined in `mud_manager/primitives.json`:
```json
"practice": {
  "category": "utility",
  "description": "List your known skills at a guildmaster, or practice a specific skill.",
  "args": {
    "skill": {
      "type": "string",
      "required": false,
      "description": "Skill name to practice (omit to list all)"
    }
  }
}
```

### Enabling the Tool

To make `practice` available to agents, ensure it's **not filtered out** by token gates:

1. **Add to `always_visible`** in settings.yaml (so it's never filtered)
2. **Add to permission allow-list** (so it's not denied)
3. **Add to phase tools** if using phase-based gating (or use always_visible)

### How It Works

1. Agent calls `practice` tool with optional skill name
2. mud_manager sends `practice <skill>` to the MUD
3. MUD's guildmaster processes the command
4. Skill improves based on current proficiency
5. Response returned to agent

### Command Variations

```
practice              # Lists all known skills
practice kick         # Practice the kick skill
practice dodge        # Practice the dodge skill
practice punch        # Practice the punch skill
```

All skill names are case-insensitive.

## Troubleshooting

### "Command not recognized"

- Ensure you're in the Tournament and Practice Yard
- Ensure the guildmaster is present
- Check skill name spelling (case-insensitive, but must be valid)

### Skill not improving

- You may need to practice multiple times to see improvement
- Some skills require minimum base stats
- Practice in short sessions for better results

### Wrong location

If you get lost, use:
- `look` - See current location
- `examine <direction>` - Check what's in each direction
- Navigate step-by-step back to Guild of Swordsmen

## Files

| File | Purpose |
|------|---------|
| `.boukensha/settings.yaml` | Configuration - enables practice in always_visible and permissions |
| `week0_explore/mud_manager/primitives.json` | Native tool definitions (includes practice) |
| `add_practice_tool.py` | Legacy helper (for custom configure callbacks, no longer needed) |
| `PRACTICE_SKILL_GUIDE.md` | This guide |

## Example Session

```
Agent: "I'm at the Tournament and Practice Yard with the guildmaster"
Agent calls: practice("kick")
System: Sends "practice kick" to MUD
MUD: "The guildmaster shows you a powerful kick technique."
Agent: "My kick skill improved! I should continue practicing."
Agent calls: practice("kick")
...continue until skill maxes out
```

## Next Steps

After mastering skills at the guildmaster:

1. **Combat training**: Use your skills in actual fights
2. **Boss fights**: Test new skills against tougher enemies
3. **Skill combinations**: Chain multiple skills together
4. **Tournament participation**: Compete in guild tournaments

---

## Status

✅ **Practice tool is a native mud_manager MCP tool!**

mud_manager provides `practice` natively in its primitives. The tool was just being filtered out by token gates in settings.yaml.

**Solution**: Enable in your settings:
```yaml
tokens:
  always_visible:
    - "*__practice"

permissions:
  rules:
    - allow: ["*__practice"]
```

**To use**: Include "practice kick" in your task:
```
"Navigate to Tournament Yard and practice kick with the guildmaster"
```

The agent will automatically recognize and use the `practice` command, just like `look`, `examine`, `move`, and `drink fountain`.
