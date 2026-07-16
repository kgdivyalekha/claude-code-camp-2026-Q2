# MUD Player Skill

A Claude skill for playing tbaMUD games with persistent connections, structured output parsing, and error handling.

## Files

- **SKILL.md** — Main skill definition with usage instructions
- **scripts/mud_connection.py** — Python script managing the connection (raw sockets, not netcat), parsing, and session state
- **data/player.md, data/world.md** — Persistent memory: character state/goals and the map, surviving across sessions
- **evals/evals.json** — Test cases for skill evaluation

## Quick Start

### 1. Initialize a session

```bash
cd .claude/skills/mud-player/scripts
python mud_connection.py --login queen --password password --action init
```

Response (real example, captured live against this server):
```json
{
  "success": true,
  "session_id": "a1b2c3d4",
  "character": "queen",
  "raw_output": "Reconnecting.\r\n\r\n24H 100M 85V (news) (motd) > \nThe Bakery\r\n   You are standing inside the small bakery...\r\n[ Exits: s ]\r\n...",
  "parsed_state": {
    "current_room": {
      "name": "Reconnecting.",
      "exits": ["s"]
    }
  }
}
```

Save the `session_id` for subsequent commands. Note `parsed_state` is a
best-effort extraction, not guaranteed complete — see "Structured Output
Parsing" below and SKILL.md's "Response shape" section.

### 2. Execute a single command

```bash
python mud_connection.py --session-id a1b2c3d4 --action execute --command "north"
```

Reconnects and re-logs in before sending the command (see Architecture below
for why), so it costs a login round-trip on top of the command itself.

### 3. Run several commands over one login (batch)

```bash
python mud_connection.py --session-id a1b2c3d4 --action batch --commands score inventory equipment
```

Logs in once and runs each command in sequence, returning a list of results.
Use this instead of several `execute` calls in a row — it saves a login
round-trip per command, which matters when exploring or checking several
things at once.

### 4. Close the session

```bash
python mud_connection.py --session-id a1b2c3d4 --action close
```

### 5. Check active sessions

```bash
python mud_connection.py --action status
```

## Features

### Connection Model
- No persistent socket across processes — `execute`/`batch` reconnect and
  log back in each time they run. tbaMUD treats this as reconnecting to the
  same live character (confirmed live: game state like position and HP
  persists server-side across these reconnects)
- Sessions (character/password/host/port) stored in `$TEMP/mud_sessions/`
- Login uses a quiet-period read (waits for a gap in server output) rather
  than a fixed prompt character, because tbaMUD's login prompts don't all end
  in the same character — see SKILL.md's Troubleshooting section for why this
  matters

### Structured Output Parsing
Returns both raw output and parsed game state, extracted from two real,
verified formats (the prompt line `24H 100M 85V` and `score` output like
"You have 24(24) hit, 100(100) mana..."):
- **Character stats**: health/max, mana/max, movement/max, level, experience, gold, exp to next level
- **Room info**: name, exits, NPCs, items (naive heuristics — see Limitations)
- **Inventory**: items and weight
- **Combat state**: in_combat flag and target

### Error Handling
- Read timeout: 8s total, treating ~1.5s of server silence as "response complete"
- Invalid commands (returns structured error)
- Unexpected disconnects (detected and reported)
- Malformed responses (raw output logged)

## Command Categories

Verified against this server's own `help` output (see SKILL.md for the full table):

| Category | Examples |
|----------|----------|
| Movement | north, south, east, west, up, down, look, exits, enter, leave, sleep/wake/rest/sit/stand |
| Combat | kill, wield, flee, assist, track, kick, bash, rescue, backstab, cast |
| Objects | get, drop, wear, inventory, equipment, remove, examine, eat, drink |
| Info | score, help, consider, where, who, news, time, weather |

## Testing

Run the evaluation suite with:
```bash
# From the skill-creator directory
python -m scripts.run_evals ../../mud-player --prompt init
```

## Architecture

```
mud-player/
├── SKILL.md                  # Skill definition
├── README.md                 # This file
├── evals/
│   └── evals.json           # Test cases
└── scripts/
    └── mud_connection.py    # Main implementation
        ├── MUDConnection      # Socket handling
        ├── MUDParser          # Output parsing
        └── SessionManager     # Session persistence
```

## Limitations & Future Improvements

**Current:**
- Each `execute` reconnects and re-logs in from scratch (no persistent socket
  across Python process boundaries). tbaMUD treats this as a reconnect to the
  same live character rather than a duplicate login, so it works, but every
  command pays a login round-trip.
- Parser is heuristic-based and tuned loosely for CircleMUD/tbaMUD; it can
  mis-extract room names or miss NPCs described in custom sentences rather
  than a fixed pattern. `raw_output` is always the source of truth.
- Character state (level/goal progress/map) persists across sessions via
  `data/player.md` and `data/world.md`, but the skill doesn't verify those
  files stay in sync automatically — reconciliation against live server state
  happens each time `init` runs (see SKILL.md's Persistent Memory section).

- **The `queen` account may be shared.** Confirmed live: a reconnect once
  returned "You take over your own body, already in use!" and the character
  had moved rooms with no movement command from this skill. Something else
  (another session, another person on the same demo login) can act on this
  character between runs — see `data/player.md`'s warning about this.

**Future:**
- True persistent socket via a background server process (would remove the
  per-command login overhead)
- Advanced parsing for more MUD variants (in particular, detecting NPCs
  written as custom action sentences rather than "X is here" phrasing)
- Combat automation helpers
