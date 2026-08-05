"""Room identity — signature-based reconciliation with confidence levels.

tbaMUD reuses room names heavily. A signature combines name + exits + description
to separate same-named rooms. Reconciliation builds a graph where identity is
probabilistic — confirmed, probable, or ambiguous — updated by traversal.
"""

import re
from hashlib import sha256
from typing import List, Optional

from .db import WorldDB


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text."""
    ansi_pattern = re.compile(r'\x1b\[[0-9;]*m|\[[0-9;]*m')
    return ansi_pattern.sub('', text)


def signature(name: str, exits: List[str], desc_head: str) -> str:
    """Generate a room signature from observable features.

    Args:
        name: Room name from the title line
        exits: List of exit directions, e.g. ['north', 'east']
        desc_head: First line (or first 80 chars) of room description

    Returns:
        16-character hex hash uniquely identifying this room (to high confidence)
    """
    # Normalize: strip ANSI codes and whitespace for consistent matching
    clean_name = _strip_ansi(name).strip()
    clean_desc = _strip_ansi(desc_head).strip()
    exit_str = ",".join(sorted(exits))

    combined = f"{clean_name}|{exit_str}|{clean_desc[:80]}"
    return sha256(combined.encode()).hexdigest()[:16]


class RoomReconciler:
    """Reconcile observed rooms against the graph.

    When the agent moves, check if the arrival signature matches a known room.
    Confidence levels:
    - confirmed: moved to a known room and signature matches
    - probable: signature matches exactly one known room
    - ambiguous: signature matches multiple rooms (need more data)
    - new: no match; create new node
    """

    def __init__(self, world_db: WorldDB):
        self.world_db = world_db

    def reconcile(
        self,
        name: str,
        exits: List[str],
        description: str,
        discovered_by: Optional[str] = None,
    ) -> str:
        """Reconcile an observed room, returning its ID.

        Args:
            name: Room name
            exits: Exit directions
            description: Full room description
            discovered_by: Actor/character name discovering this room

        Returns:
            Room ID (existing or newly created)
        """
        sig = signature(name, exits, description)
        candidates = self.world_db.get_rooms_by_signature(sig)

        if not candidates:
            # No match: create new room
            room_id = self._new_room_id(sig)
            self.world_db.add_room(
                room_id,
                name,
                sig,
                description,
                confidence="probable",
                discovered_by=discovered_by,
            )
            # Record exits as untraversed
            for direction in exits:
                self.world_db.add_exit(room_id, direction, None, "probable")
            return room_id

        if len(candidates) == 1:
            # Exactly one match: link provisionally
            room_id = candidates[0]["id"]
            self.world_db.add_room(
                room_id,
                name,
                sig,
                description,
                confidence=candidates[0]["confidence"],
                discovered_by=discovered_by,
            )
            self._reconcile_exits(room_id, exits)
            return room_id

        # Multiple matches: ambiguous. Create new node for now; resolv later via reciprocity
        room_id = self._new_room_id(sig)
        self.world_db.add_room(
            room_id,
            name,
            sig,
            description,
            confidence="ambiguous",
            discovered_by=discovered_by,
        )
        for direction in exits:
            self.world_db.add_exit(room_id, direction, None, "ambiguous")
        return room_id

    def confirm_movement(
        self,
        from_room_id: str,
        direction: str,
        to_room_id: str,
    ) -> None:
        """Confirm an exit by reciprocity test.

        After moving `direction` and arriving at `to_room`, check the reverse direction.
        If moving back lands on `from_room`, confirm the edge.
        """
        # Mark the forward exit as confirmed
        self.world_db.confirm_exit(from_room_id, direction, to_room_id)

        # Check if the reverse exists in the destination
        reverse_dir = self._reverse_direction(direction)
        back_exit = self.world_db.get_exit_by_direction(to_room_id, reverse_dir)

        # If reverse exit exists and points back, reciprocity is satisfied
        if back_exit == from_room_id:
            self.world_db.confirm_exit(to_room_id, reverse_dir, from_room_id)

    def _reconcile_exits(self, room_id: str, observed_exits: List[str]) -> None:
        """Update exits for a room based on observed directions."""
        known_exits = self.world_db.get_exits(room_id)

        # Add any new exits not yet in the database
        for direction in observed_exits:
            if direction not in known_exits:
                self.world_db.add_exit(room_id, direction, None, "probable")

    @staticmethod
    def _reverse_direction(direction: str) -> str:
        """Map a direction to its reverse."""
        reverses = {
            "north": "south",
            "n": "s",
            "south": "north",
            "s": "n",
            "east": "west",
            "e": "w",
            "west": "east",
            "w": "e",
            "up": "down",
            "u": "d",
            "down": "up",
            "d": "u",
            "northeast": "southwest",
            "ne": "sw",
            "northwest": "southeast",
            "nw": "se",
            "southeast": "northwest",
            "se": "nw",
            "southwest": "northeast",
            "sw": "ne",
        }
        return reverses.get(direction.lower(), direction)

    @staticmethod
    def _new_room_id(sig: str) -> str:
        """Generate a unique room ID from a signature."""
        return f"room_{sig}"
