"""M6 demo: World memory with identity reconciliation.

This example shows how to:
1. Create a WorldDB instance
2. Use NavigationTracker to parse look output
3. Perform pathfinding
4. Recognize same-named rooms as distinct
"""

import tempfile
from pathlib import Path

from boukensha.observability.navigation import NavigationTracker
from boukensha.world.db import WorldDB
from boukensha.world.pathfind import find_path, nearest_unexplored


def demo_basic_world_memory():
    """Demo 1: Basic room creation and exit tracking."""
    print("=" * 60)
    print("Demo 1: Basic Room Creation and Exit Tracking")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        world_db = WorldDB(str(Path(tmpdir) / "world.db"))

        # Create two rooms
        world_db.add_room(
            "room_001",
            "Market Square",
            "market_sig_001",
            "A bustling marketplace with merchants.",
            discovered_by="scout",
        )

        world_db.add_room(
            "room_002",
            "Temple",
            "temple_sig_001",
            "A sacred temple with high ceilings.",
            discovered_by="scout",
        )

        # Connect them
        world_db.add_exit("room_001", "north", "room_002", "confirmed")
        world_db.add_exit("room_002", "south", "room_001", "confirmed")

        print(f"\nCreated {world_db.room_count()} rooms")
        print(f"Market exits: {world_db.get_exits('room_001')}")
        print(f"Temple exits: {world_db.get_exits('room_002')}")

        # Show current state
        for room in world_db.all_rooms():
            print(f"\n  Room {room['id']}: {room['name']}")
            print(f"    Signature: {room['signature']}")
            print(f"    Confidence: {room['confidence']}")
            print(f"    Discovered by: {room['discovered_by']}")


def demo_same_named_rooms():
    """Demo 2: Same-named rooms in different locations are distinct."""
    print("\n" + "=" * 60)
    print("Demo 2: Same-Named Rooms Are Distinct")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        world_db = WorldDB(str(Path(tmpdir) / "world.db"))
        tracker = NavigationTracker(world_db)

        # First "Dark Alley" (exits north and east)
        look1 = """Dark Alley
You stand in a narrow alley shrouded in shadow. The walls are close.
[ Exits: north east ]"""

        room_id_1 = tracker.on_look_result(look1, "scout")
        print(f"\nFirst Dark Alley: {room_id_1}")

        # Second "Dark Alley" (exits north and south) — different location
        look2 = """Dark Alley
You stand in a gloomy passage with moss-covered walls. A foul stench lingers.
[ Exits: north south ]"""

        room_id_2 = tracker.on_look_result(look2, "scout")
        print(f"Second Dark Alley: {room_id_2}")

        print(f"\nRooms are distinct: {room_id_1 != room_id_2}")

        # Verify signatures are different
        room1_obj = world_db.get_room(room_id_1)
        room2_obj = world_db.get_room(room_id_2)
        print(f"First signature:  {room1_obj['signature']}")
        print(f"Second signature: {room2_obj['signature']}")
        print(f"Signatures differ: {room1_obj['signature'] != room2_obj['signature']}")


def demo_pathfinding():
    """Demo 3: Find routes through the world."""
    print("\n" + "=" * 60)
    print("Demo 3: Pathfinding")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        world_db = WorldDB(str(Path(tmpdir) / "world.db"))

        # Build a simple graph:
        #   Square --[N]--> Temple
        #   Square --[E]--> Market
        #   Market --[N]--> Tower

        for room_id, name, sig in [
            ("room_1", "Square", "sig_1"),
            ("room_2", "Temple", "sig_2"),
            ("room_3", "Market", "sig_3"),
            ("room_4", "Tower", "sig_4"),
        ]:
            world_db.add_room(room_id, name, sig, "A room")

        # Connect rooms
        world_db.add_exit("room_1", "north", "room_2", "confirmed")
        world_db.add_exit("room_1", "east", "room_3", "confirmed")
        world_db.add_exit("room_3", "north", "room_4", "confirmed")

        print("\nWorld map created:")
        print("  Square --N--> Temple")
        print("  Square --E--> Market")
        print("  Market --N--> Tower")

        # Find paths
        path1 = find_path(world_db, "room_1", "room_2")
        print(f"\nPath from Square to Temple: {path1}")

        path2 = find_path(world_db, "room_1", "room_4")
        print(f"Path from Square to Tower: {path2}")

        # Find unexplored frontier
        world_db.add_exit("room_2", "west", None, "probable")  # Untraversed
        result = nearest_unexplored(world_db, "room_1")
        if result:
            room_id, distance, path, direction = result
            print(f"\nNearest unexplored from Square:")
            print(f"  Room: {world_db.get_room(room_id)['name']}")
            print(f"  Distance: {distance} moves")
            print(f"  Direction to explore: {direction}")


def demo_navigation_tracker():
    """Demo 4: Parse MUD output and build world memory."""
    print("\n" + "=" * 60)
    print("Demo 4: NavigationTracker — Parse Look Output")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        world_db = WorldDB(str(Path(tmpdir) / "world.db"))
        tracker = NavigationTracker(world_db)

        # Simulate exploring: look at room 1, move north, look at room 2
        look1 = """Market Square
You stand in a bustling marketplace filled with merchants hawking their wares.
[ Exits: north south east west ]"""

        room_1 = tracker.on_look_result(look1, "scout")
        print(f"\n1. Looked at Market Square: {room_1}")
        print(f"   Known rooms: {world_db.room_count()}")

        # Move north (simulate success)
        look2 = """Temple
A sacred temple with high vaulted ceilings and colored light.
[ Exits: south ]"""

        room_2 = tracker.on_move_result(look2, room_1, "north", "scout")
        print(f"\n2. Moved north, arrived at Temple: {room_2}")
        print(f"   Known rooms: {world_db.room_count()}")

        # Check exits are reciprocal
        exits_2 = world_db.get_exits(room_2)
        print(f"   Temple exits: {exits_2}")
        print(f"   Has south exit back to Square: {'south' in exits_2}")

        # Move back south (should be recognized as same room)
        look_back = """Market Square
You stand in a bustling marketplace filled with merchants hawking their wares.
[ Exits: north south east west ]"""

        room_back = tracker.on_move_result(look_back, room_2, "south", "scout")
        print(f"\n3. Moved south, arrived at: {room_back}")
        print(f"   Same as original Market Square: {room_back == room_1}")
        print(f"   Total rooms discovered: {world_db.room_count()}")

        # Show world state
        print("\nWorld state:")
        for room in world_db.all_rooms():
            exits = world_db.get_exits(room["id"])
            print(f"  {room['name']} {exits}")


if __name__ == "__main__":
    demo_basic_world_memory()
    demo_same_named_rooms()
    demo_pathfinding()
    demo_navigation_tracker()

    print("\n" + "=" * 60)
    print("All demos completed!")
    print("=" * 60)
