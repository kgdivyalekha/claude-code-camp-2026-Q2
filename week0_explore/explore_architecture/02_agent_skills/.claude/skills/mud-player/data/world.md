# World Memory

Last updated: 2026-07-16

The route from Midgaard to the Newbie Zone, and the Newbie Zone's full layout
down to the Red Room, is now known with certainty — partly from walking it
live, partly from the server's own world/zone data files (found under
`~/claude-code-camp-2026-Q2/week0_explore/circlemud-world-parser/assets/`,
parsed with that repo's `circlemud_world_parser` library: `wld/30.wld` for
Midgaard, `wld/186.wld` + `zon/186.zon` + `mob/186.mob` + `obj/186.obj` for
the Newbie Zone). Where a room below is marked **(live-confirmed)** it's been
walked and its text matches; **(file-confirmed only)** means it's known from
the data files but hasn't been physically walked this session.

## Full Route: Main Street → The Red Room

```
Main Street (3013)
  --east--> Market Square (3014)
  --north--> The Temple Square (3005)
  --north--> The Temple Of Midgaard (3001)
  --north--> By The Temple Altar (3054)
  --north--> Behind The Temple Altar (3059)
  --north--> The Great Field Of Midgaard (3060)
  --north--> The Great Field Of Midgaard (3061)   [2nd segment, same room name]
  --east---> The Entrance To The Newbie Zone (18600)
  --north--> The Beginning Of The Passage (18601)
  --east---> The Dirty Hallway (18602)
  --east---> A Nexus (18603)
  --south--> More Of The Hallway (18607)
  --south--> Another Corner (18611)
  --[open door, then east]--> The Alchemist's Room (18612)
  --down---> The Entrance [dark maze] (18632)        <- deepest point reached live
  --north--> A Crossing Of Corridors (18627)          } file-confirmed only
  --north--> A Corner In The Hallway (18623)          } from here down —
  --east---> Another Turn (18624)                     } see "Not Yet Walked"
  --south--> A Branching Passage (18630)              } below
  --west---> THE RED ROOM (18629) — Minotaur here
```

This whole route was cross-checked against the actual game live as far as The
Alchemist's Room and one step into the dark maze beyond it; the segment from
"A Crossing Of Corridors" to the Red Room is confirmed by the zone file's
mob-placement data (see Monster Tracker) but not yet physically walked — see
"Not Yet Walked / Next Steps" below for why we turned back before finishing it.

## Midgaard (starting town)

### The Bakery
- Exits: s
- Small bakery. Sweet smell of danish and bread; shelves stocked with bread/danish; a sign on the counter.
- Occupants seen: a cityguard, an oozing green gelatinous blob, the baker (shopkeeper, seemed passive)

### Main Street (Midgaard)
- Exits: n, e, s, w
- Main street through Midgaard. North → Bakery. South → Armory (unvisited). East → Market Square. West unexplored.

### Market Square → Temple Square → Temple Of Midgaard → By/Behind The Temple Altar → The Great Field Of Midgaard
- File-confirmed chain leading out of the city to the north; the Great Field is open countryside ("you can see to the horizon... busy city of Midgaard lies to the south") with a side path east into "a strange structure" — that structure is the Newbie Zone entrance.

## Newbie Zone (dungeon, zone 186)

Explicitly built for low-level play — flavor text literally says "Kill him!
Kill him!" about its starter mob, and a sign deeper in gives an exact level
gate (see below).

### The Entrance To The Newbie Zone (18600) — file-confirmed
- Exits: n (into the zone), w (back to the Great Field)
- "Ahhh... the entrance to the newbie zone! ... when you've readied yourself you can enter to the north."

### The Beginning Of The Passage (18601) — live-confirmed
- Exits: e, s
- "A long corridor... you can hear the sound of creatures roaming about, but can't tell where."
- Seen here: a tiny pile of gold coins (picked up, 10gp), "the newbie monster"

### The Dirty Hallway (18602) — live-confirmed
- Exits: e, (s) [closed/special door], w
- "Continue wandering down the hallway... walls a bit slimy and moldy."
- Seen here: "the newbie monster", "someone's little pet dragon" (this is mob
  "Dragon", zone-file-confirmed as a placed mob here — but its own flavor
  text and behavior so far is a harmless loose pet, not hostile)

### A Nexus (18603) — live-confirmed
- Exits: (n) [closed], (e) [closed], s, w
- "An intersection of two passages... the passage brightens" to the north/east; darker hallway continues south.
- Seen here: the newbie monster (roams between rooms in this zone)

### More Of The Hallway (18607) — live-confirmed
- Exits: n, s, (w) [door, unexplored beyond it]
- "More of this annoying passage."

### Another Corner (18611) — live-confirmed
- Exits: n, (e) [door — keyword is literally **"door"**, e.g. `open door`, not `open east`], w
- "There is a door to the east though... wonder where that leads?"
- Seen here: "a creepy little crawling thing" (a Crawler, zone-confirmed, did not aggro)

### The Alchemist's Room (18612) — live-confirmed
- Exits: (n) [door, unexplored], w, d (down — dark stairway)
- "Lots of bottles and flasks... a lot of formulae and spells written on the walls... a dark stairway in the corner leading down, with a large sign next to it that you probably should read."
- **The sign says (read live, verbatim): "If you are below level 7 and alone, or below level 4 then bugger off! Or else don't blame me if you die..."** This is the game itself telling you the intended level for what's beyond this point — treat it as authoritative, not flavor text.
- Occupants: "The Newbie Alchemist" (a mob, didn't aggro when queen entered) and
  a "funny little imp-like thing (a quasit perhaps?)". **The Alchemist is
  confirmed by the object data file to be carrying a "light jar" (a brightly
  glowing jar) — a light source.** Getting this (by trade, or as a kill drop)
  solves the "pitch black" problem below, and this room is already known safe
  to reach.

### The Entrance [dark maze] (18632) — live-confirmed (briefly)
- Reached via `down` from The Alchemist's Room. **It is pitch black here** —
  no room description renders without a light source. Queen retreated
  immediately (`up`, back to The Alchemist's Room) rather than push forward
  blind, unarmed, and alone. HP was unaffected (24/24 both before and after —
  nothing attacked during the brief visit).

### Beyond here: A Crossing Of Corridors → A Corner In The Hallway → Another Turn → A Branching Passage → The Red Room
File-confirmed only (not yet walked): `north, north, east, south, west` from
The Entrance. This stretch is where the zone file places its zombies and
quasits (see Monster Tracker) — i.e. the sign's warning maps directly onto
real mob placements, not just flavor text.

### The Red Room (18629) — file-confirmed only
- Exits: n (18620), e (18630, the way in), d (a portal — "You could go down
  into it, but you can't be sure where you'll end up, or if you can get back,"
  drops into 3061, the Great Field — one-way, don't use it by accident)
- "It takes you a moment to realize that the red glow here is coming from a
  round portal on the floor. It looks almost as if someone had painted a
  picture of a dirt [path] running through a field on the floor of this
  room... you can feel the wind in the field coming out of the picture."
- **This is where the minotaur is placed** (zone file: `M 0 18609 1 18629`,
  max count 1) — see Monster Tracker for its actual combat stats.

## Monster Tracker

| Monster | Location | Danger | Status |
|---|---|---|---|
| **Minotaur** | **The Red Room (18629)** | Mob level **7** (this is exactly the sign's "below level 7 and alone" threshold — it's not a coincidence). Stats from the mob file: AC 5, ~88-100 HP (3d5+85), hits for roughly 3-9 dmg per swing (2d4+1), alignment -1000 (evil). Flavor text: "The Great Minotaur is wondering just what you'll taste like." Kill reward: 1000 gold, 3000 exp (huge — likely several levels' worth). **Not remotely survivable at queen's current level 1 / 24 HP / unarmed.** | **Located — primary goal target.** Do not engage until queen is level 7 (per the sign) or has a group, and has a real weapon. |
| Zombies | 18620, 18624, 18637, 18633 (up to 5 per room) | Not yet fought; zombies are typically slow but tough for their level. Directly on the path from The Entrance to the Red Room. | Guarding the approach — avoid or fight only once properly equipped |
| Quasits | 18627, 18636, 18638, 18621 (up to 5 per room) | Not yet fought; quasits are small demons, usually fast/tricky rather than high-damage. Also directly on the path (A Crossing Of Corridors is a Quasit spawn room). | Guarding the approach |
| The newbie monster | Beginning Of The Passage, Dirty Hallway, A Nexus (roams) | `consider` said "You would need some luck!" — fair fight. Engaged once bare-fisted: 24→20 HP over several rounds, no kill (it left before dying). | Confirmed fightable; worth a rematch once queen has a weapon |
| The Newbie Alchemist | The Alchemist's Room (18612) | Didn't aggro on entry. Carries a light jar (see room notes) — a real reason to interact rather than avoid | Not yet fought; possible source of a light source |
| A funny little imp-like thing (quasit) | The Alchemist's Room (18612) | Didn't aggro | Unconfirmed hostile |
| A creepy little crawling thing (Crawler) | Another Corner (18611) | Didn't aggro | Unconfirmed hostile |
| Someone's little pet dragon | The Dirty Hallway | Explicitly a pet, not hostile | Not a target — don't attack |
| Oozing green gelatinous blob | The Bakery | Unknown, seemed passive last seen | Unconfirmed hostile |
| Cityguard | The Bakery | Guard NPC | Avoid — guards typically retaliate hard if attacked |

## Points of Interest

- **Light source lead**: the Newbie Alchemist (18612) is confirmed to carry a
  "light jar." Solving the pitch-black problem beyond The Entrance likely
  starts here, and this room is already known safe to reach.
- **Warrior guild** — location still unknown. Needed to `practice kick`.
- **A shop/vendor** — location still unknown. queen has 10 gold and no gear.
- Armory — south of Main Street (mentioned, not yet visited)

## Not Yet Walked / Next Steps

Queen physically reached The Entrance (18632, the dark maze start) and
retreated immediately rather than continue **blind** (no light), **unarmed**
(no weapon or armor), and **alone at level 1** through a corridor the zone
data confirms is patrolled by zombies and quasits, straight into a level-7
mob's room. The sign at 18612 says this outright. This matches the strategy
already recorded in `player.md`: locate and assess before engaging, don't
fight blind just to move faster. Reasonable next steps, in order:
1. Get a weapon (still none equipped).
2. Get a light source — try the Alchemist at 18612 first.
3. Grind safer kills (the newbie monster, once armed) toward level 4+ before
   even considering re-entering the dark maze, and toward level 7 before the
   Red Room itself.
4. When ready, the walked route above (down from 18612, then
   north/north/east/south/west) is the confirmed path in.
