# Player Memory — queen

Last updated: 2026-07-16 (after direct play session — see Event Log)

## Current Goal

- [ ] Reach character level 7 (currently: level 1)
- [ ] Defeat the minotaur (location: not yet found — not encountered anywhere explored so far)

This checklist is the definition of "done." Read it before doing anything
else in a new session; check off a line the moment it's achieved.

## Important: this account may be shared

On reconnecting, the server once greeted with "You take over your own body,
already in use!" and the character had moved to a new room with no movement
command from this skill causing it. Something else (another session, another
person testing the same demo login) may act on `queen` between our sessions.
**Don't assume queen is where this file says she is — always trust a fresh
`init`/`look` over this file, and update this file to match reality, not the
other way around.**

## Class / Build

- Title at level 1: "Queen the Swordpupil" — this is a warrior-type class.
  Confirmed: `skills` and `spells` are both invalid commands ("Huh!?!"); the
  only skill listing works via bare `practice`, which showed exactly one
  entry: `kick` (not yet learned). No spellcasting exists for this build.
- `practice kick` only works inside a guild ("You can only practice skills in
  your guild.") — the guild's location is not yet known. Find it before
  relying on `kick` in combat.

## Last Known Stats (verified via `score`, 2026-07-16)

- Level: 1 (Queen the Swordpupil)
- HP: 23/24, Mana: 100/100, Movement: 85/85
- AC: 100/10, Alignment: 29
- Experience: 124 (need 1876 more to reach level 2 — level 2 threshold is 2000 total)
- Gold: 10
- Quest points: 0
- Status: standing, **hungry**, **thirsty**
- Location: The Dirty Hallway (Newbie Zone — see world.md)

## Inventory / Equipment (verified, 2026-07-16)

- Inventory: empty ("You are carrying: Nothing.")
- Equipment: empty ("You are using: Nothing.") — **no weapon, no armor**
- Only resource: 10 gold coins (just picked up; nothing to spend it on yet —
  no shop location known)

## Event Log

Most recent first. Keep entries short — a diary of what mattered, not a
command transcript.

- 2026-07-16: Played directly as queen to ground this file in reality instead
  of guesses. Found her already in the Newbie Zone (not Midgaard, where she'd
  been left last session) — confirms the shared-account risk above. Picked up
  10 gold in "The Beginning Of The Passage." Learned she's completely
  unequipped (no weapon/armor) and unarmed combat is weak ("tickle" damage
  both ways). Fought "the newbie monster" bare-fisted after standing up first
  (combat silently fails while resting) — HP dropped 24→20 over several
  rounds, but the monster left the fight/room before dying, so no kill and no
  net exp gained. Wandered into "The Dirty Hallway" without issuing a move
  command (further shared-account evidence). Also saw "someone's little pet
  dragon" there — a harmless pet, not a target despite the name. Goal
  unstarted: still level 1, minotaur not found.
- 2026-07-16 (earlier): Fixed the skill's connection/login bug (see SKILL.md)
  and set up this memory system for the first time.

## Strategy Notes

- **Get a weapon before grinding seriously.** Bare-fisted damage is weak in
  both directions; a real weapon would speed up every fight from here on.
- **Address hunger/thirst and low gold** — no food/drink on hand, and no
  known shop yet. Worth resolving before committing to a long unattended grind.
- **Always `stand` before combat.** Resting silently blocks `kill`.
- **The Newbie Zone (see world.md) seems built for exactly this goal** — low
  danger, intended first kills — but treat it as a starting point, not the
  whole plan; level 7 will likely require areas beyond it.
- **Don't hunt the minotaur until it's located and assessed** (via `consider`,
  once found) and current stats/gear look survivable. Minotaurs are typically
  a tougher mid-level CircleMUD mob, not something to fight unarmed at level 1.
