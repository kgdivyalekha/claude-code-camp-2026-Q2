"""Pathfinding and frontier queries over the world graph."""

from collections import deque
from typing import List, Optional, Tuple

from .db import WorldDB


def find_path(
    world_db: WorldDB,
    from_room_id: str,
    to_room_id: str,
) -> Optional[List[str]]:
    """Find a route from one room to another using BFS.

    Returns:
        List of direction strings ['north', 'east'] or None if unreachable.
    """
    if from_room_id == to_room_id:
        return []

    queue: deque[Tuple[str, List[str]]] = deque([(from_room_id, [])])
    visited = {from_room_id}

    while queue:
        current_id, path = queue.popleft()

        # Check all exits from current room
        exits = world_db.get_exits(current_id)
        for direction, target_id in exits.items():
            if not target_id:
                # Exit not yet traversed; skip
                continue

            if target_id in visited:
                # Already explored this branch
                continue

            new_path = path + [direction]

            if target_id == to_room_id:
                return new_path

            visited.add(target_id)
            queue.append((target_id, new_path))

    # No path found
    return None


def nearest_unexplored(
    world_db: WorldDB,
    from_room_id: str,
) -> Optional[Tuple[str, int, List[str], str]]:
    """Find the closest room with an unexplored exit.

    Returns:
        Tuple of (room_id, distance, path, unexplored_direction) or None
    """
    queue: deque[Tuple[str, List[str], int]] = deque([(from_room_id, [], 0)])
    visited = {from_room_id}

    while queue:
        current_id, path, distance = queue.popleft()

        # Check if current room has unexplored exits
        exits = world_db.get_exits(current_id)
        for direction, target_id in exits.items():
            if target_id is None:
                # Found an unexplored exit!
                return (current_id, distance, path, direction)

        # Explore neighbors
        for direction, target_id in exits.items():
            if not target_id or target_id in visited:
                continue

            visited.add(target_id)
            new_path = path + [direction]
            queue.append((target_id, new_path, distance + 1))

    # No unexplored exits found
    return None
