"""Smart navigation using world.db to reduce exploration tokens.

Provides navigation hints based on previously discovered rooms, allowing the agent
to navigate efficiently without blind exploration.
"""

from typing import Optional, List, Dict, Any
from .world.db import WorldDB
from .world.pathfind import find_path


class NavigationAssistant:
    """Provides smart navigation hints using world map data."""

    def __init__(self, world_db: Optional[WorldDB] = None):
        """Initialize navigation assistant.

        Args:
            world_db: WorldDB instance. If None, navigation assistance disabled.
        """
        self.world_db = world_db

    def get_navigation_hint(
        self,
        current_room_name: str,
        destination_room_name: str,
        current_room_signature: Optional[str] = None,
        destination_room_signature: Optional[str] = None,
    ) -> Optional[str]:
        """Get navigation hint to reach a known destination room.

        Args:
            current_room_name: Name of current room
            destination_room_name: Name of destination room to reach
            current_room_signature: Optional signature of current room (for exact lookup)
            destination_room_signature: Optional signature of destination room (for exact lookup)

        Returns:
            Navigation hint string (e.g., "north, then west, then north") or None if no path found.
        """
        if not self.world_db:
            return None

        try:
            # Try to find rooms by signature if provided
            from_room_id = None
            to_room_id = None

            if current_room_signature:
                rooms = self.world_db.get_rooms_by_signature(current_room_signature)
                if rooms:
                    from_room_id = rooms[0]["id"]

            if destination_room_signature:
                rooms = self.world_db.get_rooms_by_signature(destination_room_signature)
                if rooms:
                    to_room_id = rooms[0]["id"]

            # Fallback to name search
            if not from_room_id:
                # Try to find current room by name (less reliable but works)
                all_rooms = self.world_db.conn.execute(
                    "SELECT id FROM rooms WHERE name = ? ORDER BY visit_count DESC LIMIT 1",
                    (current_room_name,)
                ).fetchall()
                if all_rooms:
                    from_room_id = all_rooms[0][0]

            if not to_room_id:
                all_rooms = self.world_db.conn.execute(
                    "SELECT id FROM rooms WHERE name = ? ORDER BY visit_count DESC LIMIT 1",
                    (destination_room_name,)
                ).fetchall()
                if all_rooms:
                    to_room_id = all_rooms[0][0]

            if not from_room_id or not to_room_id:
                return None

            # Find path between rooms
            path = find_path(self.world_db, from_room_id, to_room_id)
            if not path:
                return None

            # Format as readable hint
            if len(path) == 1:
                return f"Go {path[0]}"
            else:
                directions = ", ".join(path[:-1]) + f", then {path[-1]}"
                return f"Go {directions}"

        except Exception as e:
            # Navigation hints are optional; don't break agent on errors
            return None

    def format_navigation_context(
        self,
        current_room_name: str,
        current_room_signature: Optional[str] = None,
    ) -> Optional[str]:
        """Get formatted context about current location and nearby unexplored areas.

        Returns:
            Context string about current room and exploration opportunities.
        """
        if not self.world_db or not current_room_signature:
            return None

        try:
            # Find current room
            rooms = self.world_db.get_rooms_by_signature(current_room_signature)
            if not rooms:
                return None

            room = rooms[0]
            room_id = room["id"]

            # Get exit status
            exits = self.world_db.get_exits(room_id)
            explored_exits = [d for d, target in exits.items() if target]
            unexplored_exits = [d for d, target in exits.items() if not target]

            if not unexplored_exits:
                return f"You are at {room['name']}. All exits ({', '.join(explored_exits)}) have been explored."

            context = f"You are at {room['name']}. "
            if explored_exits:
                context += f"Known exits: {', '.join(explored_exits)}. "
            context += f"Unexplored exits: {', '.join(unexplored_exits)}."

            return context

        except Exception:
            return None

    def get_all_known_rooms(self) -> Dict[str, Dict[str, Any]]:
        """Get all known rooms from world.db.

        Returns:
            Dict mapping room signatures to room data.
        """
        if not self.world_db:
            return {}

        try:
            rooms = self.world_db.conn.execute(
                "SELECT id, name, signature, visit_count, confidence FROM rooms ORDER BY visit_count DESC"
            ).fetchall()

            return {
                room[2]: {  # signature as key
                    "id": room[0],
                    "name": room[1],
                    "visits": room[3],
                    "confidence": room[4],
                }
                for room in rooms
            }
        except Exception:
            return {}

    def suggest_exploration_path(
        self,
        current_room_signature: Optional[str] = None,
    ) -> Optional[str]:
        """Suggest the nearest unexplored area.

        Returns:
            Suggestion string like "Nearest unexplored exit: north from Market Square (2 moves away)"
        """
        if not self.world_db or not current_room_signature:
            return None

        try:
            from .world.pathfind import nearest_unexplored

            rooms = self.world_db.get_rooms_by_signature(current_room_signature)
            if not rooms:
                return None

            room_id = rooms[0]["id"]
            result = nearest_unexplored(self.world_db, room_id)

            if not result:
                return "No unexplored exits found in the known map."

            room_id, distance, path, direction = result
            room = self.world_db.get_room(room_id)

            if distance == 0:
                return f"Unexplored exit '{direction}' is here at {room['name']}."
            else:
                path_str = " → ".join(path) if path else "here"
                return f"Nearest unexplored exit '{direction}' at {room['name']} ({distance} moves: {path_str})."

        except Exception:
            return None
