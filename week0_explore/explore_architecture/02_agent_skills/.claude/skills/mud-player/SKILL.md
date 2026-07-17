---
name: mud-player
description: Play the tbaMUD (CircleMUD variant) game running on localhost:4000 as the character queen/password. Use this skill whenever the user asks to play the MUD, connect to the game, move around, fight monsters, check inventory or stats, level up, hunt a specific monster (like the minotaur), map the world, or continue a previously started game goal — even if they just say "keep playing" or "continue the quest". Also use it for any long-horizon goal that spans many commands or multiple sessions.
allowed-tools: Bash(python3 *mud_connection.py*), Bash(python *mud_connection.py*), Read, Edit, Write
---

# MUD Player

Play tbaMUD purely over the network as the character `queen` (password `password`). Never read or modify the game server's own files, world data, or process — everything you learn about the world must come from playing it, the same way a human player would. The only tool is `scripts/mud_connection.py`.

## Current campaign

The standing goal (tracked in `data/player.md`) is: **reach level 7, then find and kill the minotaur.** Whenever this skill triggers without a more specific instruction, resume that goal from wherever `data/player.md` says you left off.

## Connection lifecycle

There is no persistent socket across Bash calls — each script invocation reconnects and logs in fresh. tbaMUD treats this as reconnecting to the same live character, so game state (position, HP, inventory) carries over server-side. This means:

**Start of any play session:**
```bash
python3 scripts/mud_connection.py --action init --login queen --password password
```
Note the `session_id` in the JSON output; every later call needs it.

**Prefer batch over single execute.** Every invocation pays a reconnect+login round-trip, so bundle your next several commands into one call:
```bash
python3 scripts/mud_connection.py --session-id <ID> --action batch --commands score look inventory
```
Multi-word commands work as single quoted arguments: `--commands "kill rabbit" look score`. Use `--action execute --command "..."` only when the next command genuinely depends on output you don't have yet.

**Batch sizing judgment:** batch aggressively for safe activities (walking known routes, checking stats, shopping), but keep batches short (1–3 commands) during combat or in unexplored territory — if command 2 walks you into a fight, commands 3–5 fire blind into it.

All output comes back as JSON with `raw_output` (source of truth — always read it) and `parsed_state` (best-effort extraction; can miss NPCs or mislabel room names, so never trust it over the raw text).

**Close when done:** `--action close --session-id <ID>` (deletes the local session file only; the character stays alive in-game).

## The play loop

Each turn of play is: **observe → consult memory → decide → act → record.**

1. **Observe**: `look`, `score`, and the prompt line (`24H 100M 85V` = current hit/mana/movement points). After `init`, always check `score` first — another session may have moved or changed the character since you last played (the queen account can be shared; the server has shown "You take over your own body, already in use!").
2. **Consult memory**: read `data/player.md` (goal, progress, known dangers) and `data/world.md` (map, where mobs and shops are) before deciding where to go. Don't re-explore what's already mapped.
3. **Decide** using the strategy section below.
4. **Act** via batch commands.
5. **Record**: update the memory files whenever you learn something durable (new room, new mob, a death, a level-up). Do this as you go, not just at session end — the session may be interrupted at any time, and unrecorded knowledge is lost.

## Combat and leveling strategy

The goal of leveling is steady exp with near-zero risk of death. Death in tbaMUD costs exp and drops your equipment at the death spot — one death can undo an hour of grinding, so fight conservatively.

- **`consider <mob>` before every new fight.** Only engage when it answers "easy", "fairly easy", or "a perfect match". Anything the game hedges on ("you would need some luck", "laughs at you") — walk away and note it in world.md as too dangerous for the current level.
- **Watch HP every round.** Combat output arrives between prompt lines; if HP falls below ~40% of max, `flee`, then `rest` until healed. Resting is free; dying is not.
- **Rest to full between fights** (`rest`, then `stand` when done). Check the prompt line to confirm recovery.
- **Level-appropriate hunting grounds**: at low levels, the newbie areas near the starting town (small animals, janitors, beggars-tier mobs). As `consider` starts calling old targets trivial, push one area further out. `data/world.md` should grow a "hunting grounds by level" section from experience.
- **After each level-up**: visit the guildmaster to `practice` skills (warriors get kick/bash/rescue), and check whether shops sell better armor/weapons you can now afford. `wield` a weapon and `wear all` — fighting bare-handed wastes exp-per-minute.
- **Track exp**: `score` reports "You need N exp to reach your next level." Log the number in player.md each session so progress across sessions is visible.

## Hunting a specific monster (the minotaur)

- First locate it: `where minotaur` (works if it's in your zone) and asking around via exploration. Record every clue in world.md.
- Do not engage until `consider minotaur` says the fight is winnable — that's the whole reason the level-7 milestone comes first.
- Before the fight: full HP, best equipment worn and wielded, skills practiced, and know your escape route (the direction you'll `flee` toward).
- Open with your strongest move (`kick`/`bash` if practiced, else `kill minotaur`), watch HP per round, and flee if it goes badly — you can heal and return; the minotaur isn't going anywhere.
- When it dies: `get all corpse`, confirm with `score`, and mark the campaign goal complete in player.md.

## Persistent memory

Two files in `data/` carry knowledge across sessions. They are the skill's long-term memory — treat keeping them accurate as part of playing well.

**`data/player.md`** — character sheet and campaign state: level, HP/mana/move maxes, exp to next level, gold, equipment, practiced skills, the current goal with a short progress log (dated entries, most recent first), and standing warnings (e.g., the shared-account issue, mobs that nearly killed you).

**`data/world.md`** — the map: rooms as a list/tree with exits, plus sections for shops & services (bakery, weapon shop, guildmaster, healer — with directions from the starting room), mobs seen (name, location, `consider` verdict at what level), and hunting grounds by level.

Reconcile memory with reality at each `init`: if `score`/`look` disagree with player.md (different room, different level), trust the server and correct the file.

## Server-specific lessons (learned by playing, 2026-07-17)

- **The take-over prompt eats commands.** Reconnecting while the character
  is live often hits "Please type Yes or No:" during login. If a batch's
  results all say that, resend the batch with `yes` prepended. Never send
  `look` blind into it — the login flow once interpreted it as a new
  character name. If results look like character creation ("Invalid name",
  "Did I get that right ... (Y/N)?"), just reconnect; the half-created
  character dies with that socket.
- **Finish every fight inside one batch.** Disconnecting mid-combat makes
  the character auto-flee on the next reconnect: lost exp (~8–35 each time)
  and a random room change. Shape combat batches as:
  `'kill <mob>' look look look look look look 'get all corpse' score` —
  the looks let combat rounds resolve; extend with more looks for tougher
  mobs rather than splitting the fight.
- **City gates never open** (game clock appears frozen at 6am). The only
  known exit from Midgaard is the temple back door: Temple Square → n → n
  (By the Temple Altar) → n. This leads to the Great Field and the Newbie
  Zone (see world.md for the full map).
- **Hunger/thirst block regeneration.** `score` shows "You are hungry."
  Fido corpses drop meat (`get all corpse`, `eat meat`); the Temple Square
  fountain fixes thirst (`drink fountain`); the Bakery sells food.
- **Exp is granted per hit, not just per kill** — and lost on flee, so
  interrupted fights actively cost progress.
- **Mobs flee when badly hurt** and return confused; corpses can be looted
  by anyone, so `get all corpse` promptly.

## Troubleshooting

- **Timeout / no response on init**: the server may be down — report that to the user rather than retrying endlessly. Check with one retry after a few seconds.
- **"Session not found"**: run `--action init` again to mint a new session; nothing in-game is lost.
- **Output looks truncated**: long room descriptions or fast combat can span reads; send `look` again to resync rather than guessing.
- **Character in an unexpected place**: someone else used the account. Re-orient with `look` + world.md; don't assume your map is wrong.
