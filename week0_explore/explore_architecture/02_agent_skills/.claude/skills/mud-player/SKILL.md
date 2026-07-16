---
name: mud-player
description: Play tbaMUD (CircleMUD variant) games running on localhost:4000, as the character queen/password. Use this skill whenever you need to interact with the MUD — movement, combat, inventory, exploring — or to pursue a longer-horizon goal (leveling up, hunting a specific monster, mapping the world) across many commands or multiple separate sessions. The skill manages connection lifecycle (a fresh reconnect+login per interaction, since there's no persistent socket across processes), parses game output into structured state, and maintains persistent memory in data/player.md and data/world.md so a goal can survive across sessions.
compatibility: Python 3.7+ (uses raw sockets — no external netcat dependency)
---

# MUD Player Skill

Plays tbaMUD (a CircleMUD variant) on localhost:4000 as `queen`/`password`,
via `scripts/mud_connection.py`. Read `data/player.md` and `data/world.md`
before doing anything else — see "Persistent Memory" below.

## Actions

All actions go through `python mud_connection.py --action <action> ...` from
the `scripts/` directory. Every action prints one JSON object to stdout.

### `init` — start a session

```
python mud_connection.py --login queen --password password --action init
```

Connects, logs in, sends an extra `look` (login alone doesn't repeat the room
description), and returns a `session_id` plus the starting room. Save the
session ID — every later call needs it. The server treats this as
**reconnecting to the same live character**, not creating a new session, so
whatever queen was doing when you last disconnected (position, HP, an active
fight) is still true. **Read that starting state and reconcile it against
`player.md`/`world.md` before doing anything else** — see "Persistent Memory".

### `execute` — one command

```
python mud_connection.py --session-id <id> --action execute --command "north"
```

Runs a single command. Under the hood this reconnects and re-logs in first
(there's no live socket left over from `init` — each call is a fresh Python
process), then sends your command and returns only its output. Costs a login
round-trip (~2-3s) on top of the command itself.

### `batch` — several commands over one login

```
python mud_connection.py --session-id <id> --action batch --commands score inventory equipment
```

Logs in once, then sends each command in `--commands` in order, returning a
list of per-command results. **Prefer this over repeated `execute` calls**
whenever you're issuing more than one or two commands in a row (checking your
sheet, exploring several rooms, a multi-step fight) — it saves a full
login round-trip per command. Quote multi-word commands individually, e.g.
`--commands 'get gold' 'kill newbie monster' look`.

### `close` — end the session

```
python mud_connection.py --session-id <id> --action close
```

Deletes the local session record. This does **not** make the character quit
the game — it just stops tracking the session locally, and the character
stays connected server-side until it goes link-dead. If you want the
character to actually leave, send a `quit` command first (via `execute` or as
the last command in a `batch`).

### `status` — list local sessions

```
python mud_connection.py --action status
```

## Response shape

```json
{
  "success": true,
  "command": "look",
  "raw_output": "The Bakery\n   You are standing inside...\n[ Exits: s ]\n...",
  "parsed_state": {
    "current_room": {"name": "...", "exits": ["s"], "npcs": [...], "items": [...]},
    "character": {"health": 23, "max_health": 24, "mana": 100, "level": 1, "experience": 124, "gold": 10},
    "inventory": {"items": [...], "weight": null},
    "combat_state": {"in_combat": true, "target": "the newbie monster"}
  },
  "error": null,
  "timestamp": "..."
}
```

`parsed_state` is filled in on a best-effort basis — whatever the heuristics
below actually matched, nothing more. **Treat `raw_output` as the source of
truth and `parsed_state` as a convenience.** The room-description parser in
particular is naive (it takes the first line as the room name, and looks for
"is here"/"lying here" phrasing for NPCs/items) and tbaMUD often writes NPCs
as a full action sentence instead ("The baker looks at you calmly, wiping
flour from his face with one hand.") that it won't catch. When you're
deciding what to write into memory, read the raw text yourself.

## Verified mechanics (learned by actually playing as queen)

These aren't guesses — each one was confirmed live against this server:

- **You can't fight while resting/sitting/sleeping.** `kill <target>` while
  resting silently no-ops ("Nah... You feel too relaxed to do that.."). Send
  `stand` first.
- **Combat is automatic once started.** One `kill <target>` starts the fight;
  it continues on its own each game pulse without repeating the command. Poll
  with `score` or `look` to watch it progress — don't resend `kill`.
- **A fight can end without a kill.** The target can flee or wander off mid-fight
  with no message announcing it — if `combat_state.in_combat` goes false and
  exp/gold didn't change, nothing was actually killed.
- **`practice <skill>` only works inside your guild** ("You can only practice
  skills in your guild.") — check what skills are known/unlearned with bare
  `practice`, but you have to physically be in the guild to learn them.
- **queen started with no weapon and no armor equipped**, and fights bare-fisted
  ("You swing your fist...tickle..."), which does very little damage in either
  direction. Getting even a basic weapon is a real priority, not a nice-to-have.
- **`consider <target>`** gives a relative-difficulty read before you commit to
  a fight (phrases range from an easy win to hopeless). Use it before engaging
  anything you haven't fought before.
- **Hunger/thirst are tracked** (`score` reports "You are hungry"/"You are
  thirsty") and queen currently has no food, drink, or much gold. Address
  this before a long grind, not after it's a problem.
- **This account may be shared.** On one `init`, the server greeted with "You
  take over your own body, already in use!" and the character had moved rooms
  between sessions with no movement command from this skill causing it. Don't
  assume queen is exactly where you left her — always reconcile against the
  live `init`/`look` response, and expect that another party's actions (not
  just time or death) can explain a state that doesn't match memory.

## Verified command list

From the in-game `help` command — this is the actual command set on this
server, not a generic MUD command guess:

| Category | Commands |
|---|---|
| Movement | `north south east west up down`, `look`, `exits`, `enter`, `leave`, `sleep wake rest sit stand` |
| Communication | `say gsay shout holler tell ask whisper`, `mail receive check gossip grats auction` |
| Objects | `get drop junk donate put give wear grab`, `inventory equipment remove`, `examine eat drink taste sip pour` |
| Info | `score help info who news time weather`, `where`, `consider`, `levels wizlist immlist`, `toggle flags` |
| Combat | `kill wield flee assist track`, `kick bash rescue backstab cast` |
| Utility | `quit save brief compact title commands socials` |

`help <keyword>` gives detail on any of these, or on topics like `social`,
`shops`, `inns`, `warrior`, `magic`, `spells`. Run it in-game rather than
guessing when you hit something unfamiliar.

## Persistent Memory

`data/player.md` and `data/world.md` are the only things that outlive a
session — the MUD has no notion of "your conversation," and this skill's own
context will eventually end or reset. Read both **before** connecting, and
write to them **as things happen**, not just before you stop:

- **`player.md`**: the goal checklist, last known stats/inventory, and a short
  event log. This is what makes "reach level 7" or "defeat the minotaur"
  possible to resume across sessions — it's the definition of what "done"
  means and the diary of progress toward it.
- **`world.md`**: the map — rooms seen (name, exits, notable occupants), a
  monster tracker (location + danger read for anything worth remembering), and
  routes between places. Update a room's entry in place if something about it
  changes rather than duplicating it.
- **Reconcile, don't assume.** Right after `init`, compare the server's actual
  report against memory. If they've drifted — because of death, time, or
  (see above) someone/something else acting on this account — trust the live
  server and correct memory, not the other way around.
- Write prose/tables meant to be skimmed in a few seconds, not raw JSON dumps.

## Playing toward a long-horizon goal

For something like "reach level 7 and defeat the minotaur" — far more actions
than fit in one exchange, plausibly spanning several conversations:

1. Read `player.md`'s goal checklist first; it's what "done" means.
2. Loop: assess current state → pick the safest useful next action → act →
   update memory if anything changed → repeat. Don't plan the whole route
   upfront — HP, room contents, and what just attacked you change too fast
   for a fixed plan to stay valid.
3. Checkpoint memory regularly, not only at the end — a long grind is exactly
   what's most likely to get interrupted.
4. Use `consider` (and `world.md`'s Monster Tracker, once populated) before
   any unfamiliar fight. Don't engage the actual named target until it's
   located, assessed, and plausibly survivable given current stats/gear.
5. Fix known gaps before grinding seriously: get a weapon, address hunger/
   thirst, and practice available skills at the guild once you can reach one.

## Troubleshooting

**Login unexpectedly asks you to confirm a password (new-character flow)?**
The username never reached the actual name prompt — almost always because a
read returned before the server finished its banner/negotiation (there's a
~1s gap between the quick "Attempting to Detect Client" message and the rest
of the banner). Disconnect immediately without answering Y/N, or it will
create an unwanted character.

**A command seems to do nothing?**
Check `player.md`/the last `score` — you may be resting/sitting (most
commands, especially combat, need you standing) or already in combat.

**Session ID lost or connection dropped?**
Just re-run `init` — the server reconnects to the same live character rather
than failing or duplicating it.

**Parser missed something?**
Read `raw_output` directly — see "Response shape" above. This is expected for
custom-worded room descriptions, not a bug to chase.
