import sys
sys.path.insert(0, '/home/system/claude-code-camp-2026-Q2/week0_explore/circlemud-world-parser')
from circlemud_world_parser.room import Room
import re
from collections import deque

DIR_NAMES = {0: 'north', 1: 'east', 2: 'south', 3: 'west', 4: 'up', 5: 'down'}

rooms = {}
for fname in ['30.wld', '186.wld']:
    with open(f'/home/system/claude-code-camp-2026-Q2/week0_explore/circlemud-world-parser/assets/wld/{fname}') as f:
        text = f.read()
    if not text.startswith('\n'):
        text = '\n' + text  # first room has no leading blank line before its "#vnum" marker
    chunks = re.split(r'\n#(\d+)\n', text)
    for i in range(1, len(chunks), 2):
        vnum = chunks[i]
        body = chunks[i + 1]
        room_text = f"{vnum}\n{body}"
        try:
            room = Room.from_text(room_text)
            rooms[room.id] = room
        except Exception as e:
            print(f"parse fail {vnum}: {e}", file=sys.stderr)

print(f"parsed {len(rooms)} rooms")

for check in [3013, 3061, 18600, 18601, 18629]:
    r = rooms.get(check)
    if r:
        print(f"{check}: {r.name!r} exits={[(e.dir, e.room_linked) for e in r.exits]}")
    else:
        print(f"{check}: MISSING")

start = 18602  # confirmed live location: The Dirty Hallway
goal = 18629  # The Red Room

# BFS
prev = {start: None}
q = deque([start])
while q:
    cur = q.popleft()
    if cur == goal:
        break
    room = rooms.get(cur)
    if not room:
        continue
    for ex in room.exits:
        nxt = ex.room_linked
        if nxt not in prev and nxt in rooms:
            prev[nxt] = (cur, ex.dir)
            q.append(nxt)

if goal not in prev:
    print("NO PATH FOUND")
else:
    path = []
    node = goal
    while prev[node] is not None:
        pnode, d = prev[node]
        path.append((pnode, DIR_NAMES.get(d, d), node))
        node = pnode
    path.reverse()
    print(f"Path from {start} ({rooms[start].name}) to {goal} ({rooms[goal].name}):")
    for pnode, d, nxt in path:
        exit_obj = next(e for e in rooms[pnode].exits if DIR_NAMES.get(e.dir, e.dir) == d and e.room_linked == nxt)
        print(f"  {pnode} [{rooms[pnode].name}] --{d}--> {nxt} [{rooms[nxt].name}]  door_flag={exit_obj.door_flag}")
    print()
    print("Command sequence:", ' '.join(d for _, d, _ in path))
