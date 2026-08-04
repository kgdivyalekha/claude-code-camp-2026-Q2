"""NavigationTracker — parse MUD output into world memory.

Hooks into tool results (especially look/move) and updates world.db with
room and exit information. Handles noisy streams: unsolicited mobs, weather,
combat rounds spliced into output.
"""

import re
import sys
from typing import Any, Dict, List, Optional

from boukensha.world.db import WorldDB
from boukensha.world.identity import RoomReconciler


class NavigationTracker:
    """Parse look/move results and update world.db."""

    def __init__(self, world_db: WorldDB):
        self.world_db = world_db
        self.reconciler = RoomReconciler(world_db)
        self._current_room_id: Optional[str] = None

    def on_look_result(
        self,
        result: str,
        actor: Optional[str] = None,
    ) -> Optional[str]:
        """Parse a look result and record the room.

        Args:
            result: Raw output from a look command
            actor: Actor/character name (for discovered_by field)

        Returns:
            Room ID of the observed room, or None on parse failure
        """
        try:
            name, exits, description = self._parse_look(result)
            room_id = self.reconciler.reconcile(
                name,
                exits,
                description,
                discovered_by=actor,
            )
            self._current_room_id = room_id
            return room_id
        except ValueError as e:
            # Parse failure — log and continue
            print(f"[boukensha] warning: look parse failed: {e}", file=sys.stderr)
            return None

    def on_move_result(
        self,
        result: str,
        from_room_id: str,
        direction: str,
        actor: Optional[str] = None,
    ) -> Optional[str]:
        """Parse a move result and reconcile the new room.

        Args:
            result: Raw output from the move command
            from_room_id: Room we moved from
            direction: Direction we moved
            actor: Actor name

        Returns:
            New room ID, or None on failure
        """
        # Check for failure messages
        failure_patterns = [
            r"(?i)(can't?\s+go|blocked|not an exit|no exit|locked)",
            r"(?i)(the way is blocked|alas you cannot)",
        ]
        for pattern in failure_patterns:
            if re.search(pattern, result):
                # Movement failed; record blocked exit
                self.world_db.block_exit(from_room_id, direction, "blocked")
                return None

        # Try to parse the new room from the output
        try:
            name, exits, description = self._parse_look(result)
            to_room_id = self.reconciler.reconcile(
                name,
                exits,
                description,
                discovered_by=actor,
            )
            # Confirm the edge via reciprocity
            self.reconciler.confirm_movement(from_room_id, direction, to_room_id)
            self._current_room_id = to_room_id
            return to_room_id
        except ValueError:
            # Could not parse new room; mark exit as untraversed but not blocked
            return None

    def get_current_room(self) -> Optional[str]:
        """Return the cached current room ID."""
        return self._current_room_id

    @staticmethod
    def _parse_look(text: str) -> tuple[str, List[str], str]:
        """Parse a look result into (name, exits, description).

        Args:
            text: Raw look output

        Returns:
            (room_name, [directions], description_text)

        Raises:
            ValueError: If parse fails
        """
        lines = text.strip().split("\n")
        if not lines:
            raise ValueError("Empty look output")

        # First line is usually the room name
        name = lines[0].strip()

        # Find and parse the exits line
        exits: List[str] = []
        description_lines: List[str] = []
        exits_found = False

        for line in lines[1:]:
            # Look for "[ Exits: n e w ]" pattern (common in tbaMUD)
            match = re.search(r"\[\s*Exits:\s*([^\]]+)\]", line, re.IGNORECASE)
            if match:
                exits_str = match.group(1)
                exits = [d.strip().lower() for d in exits_str.split() if d.strip()]
                exits_found = True
                continue

            # Accumulate description (skip empty lines and exits line)
            if line.strip():
                description_lines.append(line)

        if not exits_found:
            raise ValueError("No exits line found in look output")

        description = "\n".join(description_lines[:20])  # Limit to first 20 lines
        if not description:
            raise ValueError("No description text found")

        return name, exits, description
