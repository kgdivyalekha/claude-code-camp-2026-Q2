# Player Memory — queen

Last updated: 2026-07-16

## Current Goal

- [ ] Reach character level 7 (currently: level 1)
- [ ] Defeat the minotaur (**location confirmed: The Red Room**, zone 186 —
      full route in world.md)

This checklist is the source of truth for whether the job is done. Read it
before doing anything else in a new session, and update it the moment either
line is achieved.

## Important: this account may be shared

Confirmed again this session — she was found in a different room than
memory said (Main Street vs. actually The Dirty Hallway) with no movement
command from this skill explaining it. Something else may act on `queen`
between sessions. Always trust a fresh `init`/`look` over this file.

## Last Known Stats (verified via `score`, 2026-07-16, after retreating to The Alchemist's Room)

- Level: 1 (Queen the Swordpupil)
- HP: 24/24, Mana: 100/100, Movement: 82/85
- AC: 100/10, Alignment: 29
- Experience: 124 (need 1876 more for level 2 — level 2 threshold is 2000 total)
- Gold: 10
- Quest points: 0
- Status: standing, hungry, thirsty
- **Location: The Alchemist's Room (18612), Newbie Zone** — retreated here
  deliberately after scouting one room further (see Event Log). This is a
  known-safe room to resume from.

## Inventory / Equipment

- Inventory: empty. Equipment: empty — still no weapon, no armor.
- **Lead on fixing this**: the Newbie Alchemist NPC, right here in this room,
  is confirmed (via the game's own object data) to carry a light source (a
  "light jar"). Getting it — by trade or otherwise — is the natural next step
  before going back down into the dark maze toward the Red Room.

## Class / Build

- Warrior-type ("Queen the Swordpupil"). No spells; only known skill is
  `kick` (unlearned). `practice` only works inside a guild — location still
  unknown.

## Event Log

Most recent first. Keep entries short — a diary of what mattered, not a
command transcript.

- 2026-07-16: **Located the minotaur with certainty.** Read the server's own
  world/zone data files (`~/claude-code-camp-2026-Q2/week0_explore/circlemud-world-parser/assets/`)
  and confirmed via the zone reset command (`M 0 18609 1 18629` in `zon/186.zon`)
  that the minotaur is placed in room 18629, "The Red Room" — matching what
  the user described. Computed and then physically walked the real path from
  Main Street, north out of Midgaard through the Great Field, east into the
  Newbie Zone, and through it to The Alchemist's Room — full route now in
  world.md. Read a sign there (verbatim: "If you are below level 7 and alone,
  or below level 4 then bugger off! Or else don't blame me if you die...").
  Went one room further down a dark stairway (pitch black, no light source)
  and immediately retreated back up rather than continue blind/unarmed/alone
  — the zone file confirms zombies and quasits patrol the remaining stretch
  to the Red Room, and the minotaur itself is mob-level 7 with ~90-100 HP,
  which would be an instant loss for a level-1, 24 HP, unarmed character.
  Full path, room-by-room notes, and the minotaur's actual combat stats are
  now in world.md. Goal still unstarted in terms of levels, but no longer
  blocked on "where is it" — now blocked on "get equipped and leveled enough
  to survive it."
- 2026-07-16 (earlier): Played directly to ground memory in reality — found
  her already in the Newbie Zone (not Midgaard), picked up 10 gold, fought
  "the newbie monster" bare-fisted inconclusively (24→20 HP, no kill, it left
  the fight).
- 2026-07-16 (earlier still): Fixed the skill's connection/login bug and set
  up this memory system for the first time.

## Strategy Notes

- **The minotaur is not a "grind toward it eventually" target anymore — it's
  a known, fixed encounter with known stats.** It's mob-level 7, ~90-100 HP,
  hits for ~3-9 per swing, AC 5. Queen needs to actually be around level 7
  (per the in-game sign) and equipped before this is winnable, not just
  "stronger than she is now."
- **Get a weapon first** — still bare-fisted, which is weak both ways.
- **Get the light jar from the Alchemist (18612)** before descending again —
  the maze beyond is pitch black without one.
- **Don't push through the zombie/quasit corridor blind or alone.** That's
  exactly the mistake the in-game sign warns against, and it's not flavor
  text — real mobs are placed there in the zone data.
- The Newbie Zone's shallow rooms (Beginning Of The Passage, Dirty Hallway, A
  Nexus, More Of The Hallway, Another Corner) seem safe enough to grind early
  levels in; the danger starts specifically past The Alchemist's Room.
