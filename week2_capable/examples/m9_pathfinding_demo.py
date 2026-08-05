#!/usr/bin/env python3
"""M9 Pathfinding and frontier queries — demonstration.

This example shows:
1. Building a world map with rooms and exits
2. Using find_path() to navigate the map
3. Using nearest_unexplored() to find exploration frontiers
4. Integration with compression hook to enhance repeat-visit summaries
"""

import sys
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from boukensha.world.db import WorldDB
from boukensha.world.pathfind import find_path, nearest_unexplored
from boukensha.world.identity import signature
from boukensha.tokens.compress import CompressionHooks


def create_sample_world() -> tuple[WorldDB, dict]:
    """Create a small world with interconnected rooms."""
    db_path = tempfile.mktemp(suffix=".db")
    world_db = WorldDB(db_path)

    # Define rooms
    rooms_data = {
        "market": ("Market Square", "The bustling center of town"),
        "temple": ("Sacred Temple", "An ancient place of worship"),
        "forest": ("Dark Forest", "Trees block out the sun"),
        "river": ("Crystal River", "Water flows peacefully"),
        "tavern": ("The Green Griffin", "A cozy watering hole"),
    }

    # Create rooms in world.db
    rooms = {}
    for key, (name, desc) in rooms_data.items():
        exits = ["north", "south", "east", "west"]  # Placeholder
        sig = signature(name, exits, desc)
        room_id = f"room_{sig[:8]}"
        world_db.add_room(room_id, name, sig, desc)
        rooms[key] = room_id
        print(f"  Created: {name}")

    # Wire exits: create a connected graph
    # Market (center) connects to all others
    world_db.add_exit(rooms["market"], "north", rooms["temple"], "confirmed")
    world_db.add_exit(rooms["temple"], "south", rooms["market"], "confirmed")

    world_db.add_exit(rooms["market"], "south", rooms["tavern"], "confirmed")
    world_db.add_exit(rooms["tavern"], "north", rooms["market"], "confirmed")

    world_db.add_exit(rooms["market"], "east", rooms["river"], "confirmed")
    world_db.add_exit(rooms["river"], "west", rooms["market"], "confirmed")

    world_db.add_exit(rooms["market"], "west", rooms["forest"], "confirmed")
    world_db.add_exit(rooms["forest"], "east", rooms["market"], "confirmed")

    # Add some unexplored exits for frontier queries
    world_db.add_exit(rooms["temple"], "east", None, "probable")  # Unexplored
    world_db.add_exit(rooms["forest"], "north", None, "probable")  # Unexplored
    world_db.add_exit(rooms["river"], "south", None, "probable")  # Unexplored

    print(f"\n✓ Created {len(rooms)} rooms with interconnected exits\n")
    return world_db, rooms


def demo_pathfinding(world_db: WorldDB, rooms: dict) -> None:
    """Demonstrate pathfinding from market to each location."""
    print("=" * 60)
    print("PATHFINDING DEMO: Finding routes from Market Square")
    print("=" * 60)

    start = rooms["market"]

    for dest_key in ["temple", "forest", "river", "tavern"]:
        dest = rooms[dest_key]
        path = find_path(world_db, start, dest)

        if path:
            route = " → ".join(path)
            print(f"  Market → {dest_key.title():10} : {route}")
        else:
            print(f"  Market → {dest_key.title():10} : UNREACHABLE")

    print()


def demo_frontier(world_db: WorldDB, rooms: dict) -> None:
    """Demonstrate frontier queries from each location."""
    print("=" * 60)
    print("FRONTIER DEMO: Finding unexplored exits")
    print("=" * 60)

    for room_key in ["market", "temple", "forest", "river", "tavern"]:
        room_id = rooms[room_key]
        frontier = nearest_unexplored(world_db, room_id)

        if frontier:
            target_id, distance, path, unexplored_dir = frontier
            path_str = " → ".join(path) if path else "0 hops"
            print(f"  From {room_key.title():10}: {distance} moves ({path_str}) to explore {unexplored_dir}")
        else:
            print(f"  From {room_key.title():10}: All exits explored")

    print()


def demo_compression(world_db: WorldDB, rooms: dict) -> None:
    """Demonstrate frontier info in repeat-visit compression."""
    print("=" * 60)
    print("COMPRESSION DEMO: Repeat-visit summaries with frontier info")
    print("=" * 60)

    compression = CompressionHooks(world_db)

    # Simulate a repeat visit to Temple
    temple_id = rooms["temple"]
    world_db.conn.execute(
        "UPDATE rooms SET visit_count = visit_count + 1 WHERE id = ?",
        (temple_id,),
    )
    world_db.conn.commit()

    # Create a realistic look output
    look_output = """Sacred Temple

An ancient place of worship. Stone columns rise toward a vaulted ceiling.
Sunlight filters through high windows, illuminating dusty motes. The air
smells of incense and age. A sense of peace permeates the place.

[ Exits: south east ]
"""

    result = {"content": look_output, "ok": True}

    # Compress
    compressed = compression.compress_repeat_rooms(None, "look", {}, result)

    if compressed:
        summary = compressed["content"]
        original_tokens = compression._estimate_tokens(look_output)
        compressed_tokens = compression._estimate_tokens(summary)
        savings = (1 - compressed_tokens / original_tokens) * 100

        print(f"  Original:  {original_tokens} tokens")
        print(f"  Compressed: {compressed_tokens} tokens (saved {savings:.0f}%)")
        print(f"\n  Summary: {summary}")
    else:
        print("  (No compression)")

    print()


def demo_route_walking(world_db: WorldDB, rooms: dict) -> None:
    """Demonstrate end-to-end route walking (M9 success criterion)."""
    print("=" * 60)
    print("ROUTE WALKING DEMO: Agent walks a queried path")
    print("=" * 60)

    start = rooms["market"]
    goal = rooms["forest"]

    # Query the route
    route = find_path(world_db, start, goal)
    print(f"\n  Queried route from Market → Forest: {route}\n")

    if route:
        # Walk the route step by step
        current_room_id = start
        current_name = world_db.get_room(start)["name"]

        print(f"  START: {current_name}")

        for i, direction in enumerate(route):
            next_room_id = world_db.get_exit_by_direction(current_room_id, direction)
            if next_room_id:
                next_room = world_db.get_room(next_room_id)
                current_room_id = next_room_id
                print(f"  STEP {i + 1}: Move {direction:5} → {next_room['name']}")
            else:
                print(f"  STEP {i + 1}: Move {direction:5} → ERROR: no exit")
                return

        final_room = world_db.get_room(current_room_id)
        print(f"\n  GOAL REACHED: {final_room['name']}")
        print(f"  ✓ Successfully walked {len(route)}-hop route end-to-end")
    else:
        print("  ERROR: No route found")

    print()


def main():
    print("\n" + "=" * 60)
    print("M9: PATHFINDING & FRONTIER QUERIES")
    print("=" * 60 + "\n")

    world_db, rooms = create_sample_world()

    demo_pathfinding(world_db, rooms)
    demo_frontier(world_db, rooms)
    demo_compression(world_db, rooms)
    demo_route_walking(world_db, rooms)

    print("=" * 60)
    print("✅ M9 Demonstration Complete")
    print("=" * 60 + "\n")
    print("M9 delivers:")
    print("  ✓ BFS pathfinding (find_path) for navigation")
    print("  ✓ Frontier queries (nearest_unexplored) for exploration")
    print("  ✓ Integration into repeat-visit summaries with route hints")
    print("  ✓ Agent can walk queried routes end-to-end")
    print()


if __name__ == "__main__":
    main()
