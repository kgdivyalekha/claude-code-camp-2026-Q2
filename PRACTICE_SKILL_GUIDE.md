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

The `practice` tool is **built-in and always available** — no configuration needed!

```python
import boukensha

result = boukensha.run(
    task="Navigate to the guildmaster and practice kick"
)
```

Just use `practice kick` in your task, just like `look`, `examine`, or `drink fountain`.

### Example

Run the practice skill example:

```bash
python3 examples/practice_skill_builtin.py
```

### In Your Code

The practice command works naturally:

```python
import boukensha

result = boukensha.run(
    task="Go to Tournament Yard and practice kick skill"
)
```

No special `configure` callbacks needed anymore! The `practice` tool is a **native command** just like:
- `look` - examine your surroundings
- `examine <object>` - look closely at something
- `drink fountain` - drink from a fountain
- `practice kick` - practice a skill ✅ (now built-in!)

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

### Built-in Tool

The `practice` tool is now **registered as a standard built-in tool** in `src/boukensha/tools/standard.py`.

It's automatically available in all boukensha sessions without requiring:
- Special imports
- Configure callbacks
- Custom setup code

This makes it a **native command** just like the MCP server tools.

### How It Works

1. Agent calls `practice` tool with skill name
2. Tool normalizes the skill name (lowercase, trimmed)
3. Tool returns MUD command format: `practice <skill>`
4. MUD processes the command and improves skill proficiency
5. Guildmaster responds with training feedback

### Technical Details

The tool is defined in `src/boukensha/tools/standard.py::register_standard_tools()`

It automatically:
- Accepts skill names (kick, punch, dodge, etc.)
- Normalizes them to lowercase
- Handles skill aliases (spinning kick → spin kick)
- Returns the correct MUD command format

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
| `src/boukensha/tools/standard.py` | Built-in standard tools (includes practice) |
| `add_practice_tool.py` | Legacy helper (still works for custom configure callbacks) |
| `examples/practice_skill_builtin.py` | Example showing practice as built-in tool (no setup needed) |
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

✅ **Practice tool is now a built-in standard command!**

- No longer requires special configuration
- Always available, just like `look`, `examine`, `drink`
- Works as a native tbaMUD command
- Agent can use it automatically when navigating to the guildmaster

**To use**: Just include "practice kick" (or any skill) in your task description!

Example:
```
"Navigate to Tournament Yard and practice kick with the guildmaster"
```

The agent will automatically use the built-in `practice` tool.
