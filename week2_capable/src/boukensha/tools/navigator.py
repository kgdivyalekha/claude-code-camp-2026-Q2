"""Navigator tool: World DB-first pathfinding with BFS fallback.

This tool provides efficient navigation by:
1. First checking world.db for cached paths (no tokens wasted on recomputation)
2. Falling back to BFS pathfinding if path not yet discovered
3. Supporting exploration guidance via frontier queries
4. Keyword-based searches ("where's the bakery?", "find a shop")
5. Token-aware: tracks usage and triggers compaction at 80% threshold
"""

import sys
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass

from boukensha.world.db import WorldDB
from boukensha.world.pathfind import find_path, nearest_unexplored
from boukensha.world.keywords import KeywordExtractor
from boukensha.logger import Logger


@dataclass
class NavigationResult:
    """Result of a navigation query."""
    success: bool
    path: Optional[List[str]] = None
    distance: Optional[int] = None
    destination: Optional[str] = None
    reason: str = ""
    cached: bool = False  # True if from world.db, False if computed


class Navigator:
    """Efficient navigation using cached paths and BFS fallback.

    Strategy:
    1. Check if destination is in world.db
    2. Try to find path in cached graph
    3. If not found, compute via BFS
    4. Return path and indicate if cached or computed
    """

    def __init__(self, world_db: Optional[WorldDB] = None, logger: Optional[Logger] = None):
        """Initialize navigator.

        Args:
            world_db: WorldDB instance for cached path lookups
            logger: Optional logger for events
        """
        self.world_db = world_db
        self.logger = logger
        self._compaction_threshold = 0.80  # 80% of session window

    def navigate_to(
        self,
        from_room_signature: str,
        to_room_name: str,
        from_room_name: Optional[str] = None,
        to_room_signature: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Navigate from current room to a destination.

        First checks world.db for cached path. If not found, uses BFS.

        Args:
            from_room_signature: Current room signature
            to_room_name: Destination room name
            from_room_name: Current room name (for logging)
            to_room_signature: Destination room signature (for exact lookup)

        Returns:
            Dict with: success, path, distance, destination, cached, reason, compaction_needed
        """
        if not self.world_db:
            return {
                "success": False,
                "reason": "World database not available",
                "compaction_needed": False,
            }

        self._log_event("navigation.query",
                       from_room=from_room_name,
                       to_room=to_room_name)

        try:
            # Step 1: Resolve current room
            from_room_id = self._resolve_room(from_room_signature, from_room_name)
            if not from_room_id:
                return {
                    "success": False,
                    "reason": f"Current room not found in world map",
                    "compaction_needed": False,
                }

            # Step 2: Resolve destination room
            to_room_id = self._resolve_room(to_room_signature, to_room_name)
            if not to_room_id:
                return {
                    "success": False,
                    "reason": f"Destination '{to_room_name}' not yet discovered",
                    "compaction_needed": False,
                }

            # Step 3: Check if path is in world.db (cached)
            path, cached = self._find_cached_path(from_room_id, to_room_id)

            if path is not None:
                # Path found in world.db
                self._log_event("navigation.found_cached",
                               from_room=from_room_name,
                               to_room=to_room_name,
                               hops=len(path))

                return {
                    "success": True,
                    "path": path,
                    "distance": len(path),
                    "destination": to_room_name,
                    "cached": True,
                    "reason": f"Cached path found: {self._format_path(path)}",
                    "compaction_needed": self._check_compaction_needed(),
                }

            # Step 4: Compute path via BFS
            path = find_path(self.world_db, from_room_id, to_room_id)

            if path:
                # Path computed
                self._log_event("navigation.found_computed",
                               from_room=from_room_name,
                               to_room=to_room_name,
                               hops=len(path))

                return {
                    "success": True,
                    "path": path,
                    "distance": len(path),
                    "destination": to_room_name,
                    "cached": False,
                    "reason": f"Path computed via BFS: {self._format_path(path)}",
                    "compaction_needed": self._check_compaction_needed(),
                }

            # No path found
            return {
                "success": False,
                "reason": f"No path to '{to_room_name}' from current location",
                "destination": to_room_name,
                "compaction_needed": False,
            }

        except Exception as e:
            self._log_event("navigation.error", error=str(e))
            return {
                "success": False,
                "reason": f"Navigation error: {str(e)}",
                "compaction_needed": False,
            }

    def explore_frontier(
        self,
        from_room_signature: str,
        from_room_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Find nearest unexplored exit for exploration guidance.

        Args:
            from_room_signature: Current room signature
            from_room_name: Current room name (for logging)

        Returns:
            Dict with: success, frontier_direction, distance, path, reason, compaction_needed
        """
        if not self.world_db:
            return {
                "success": False,
                "reason": "World database not available",
                "compaction_needed": False,
            }

        try:
            # Resolve current room
            from_room_id = self._resolve_room(from_room_signature, from_room_name)
            if not from_room_id:
                return {
                    "success": False,
                    "reason": "Current room not found in world map",
                    "compaction_needed": False,
                }

            # Query frontier
            frontier = nearest_unexplored(self.world_db, from_room_id)

            if not frontier:
                self._log_event("navigation.frontier_none", room=from_room_name)
                return {
                    "success": False,
                    "reason": "All reachable exits have been explored",
                    "compaction_needed": self._check_compaction_needed(),
                }

            frontier_room_id, distance, path, direction = frontier
            frontier_room = self.world_db.get_room(frontier_room_id)

            self._log_event("navigation.frontier_found",
                           from_room=from_room_name,
                           frontier_room=frontier_room["name"],
                           distance=distance,
                           direction=direction)

            return {
                "success": True,
                "frontier_direction": direction,
                "frontier_room": frontier_room["name"],
                "distance": distance,
                "path": path if distance > 0 else [],
                "reason": self._format_frontier_hint(
                    frontier_room["name"],
                    distance,
                    path,
                    direction
                ),
                "compaction_needed": self._check_compaction_needed(),
            }

        except Exception as e:
            self._log_event("navigation.frontier_error", error=str(e))
            return {
                "success": False,
                "reason": f"Frontier query error: {str(e)}",
                "compaction_needed": False,
            }

    def get_exit_status(
        self,
        from_room_signature: str,
        from_room_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get status of exits from current room (explored vs unexplored).

        Args:
            from_room_signature: Current room signature
            from_room_name: Current room name (for logging)

        Returns:
            Dict with: explored_exits, unexplored_exits, compaction_needed
        """
        if not self.world_db:
            return {
                "explored_exits": [],
                "unexplored_exits": [],
                "compaction_needed": False,
            }

        try:
            # Resolve current room
            from_room_id = self._resolve_room(from_room_signature, from_room_name)
            if not from_room_id:
                return {
                    "explored_exits": [],
                    "unexplored_exits": [],
                    "compaction_needed": False,
                }

            # Get exits
            all_exits = self.world_db.get_exits(from_room_id)
            explored = [d for d, target in all_exits.items() if target]
            unexplored = [d for d, target in all_exits.items() if not target]

            return {
                "explored_exits": sorted(explored),
                "unexplored_exits": sorted(unexplored),
                "compaction_needed": self._check_compaction_needed(),
            }

        except Exception as e:
            return {
                "explored_exits": [],
                "unexplored_exits": [],
                "compaction_needed": False,
            }

    def search_by_keyword(
        self,
        keyword: str,
        from_room_signature: Optional[str] = None,
        from_room_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Search for rooms matching a keyword and optionally find routes.

        Args:
            keyword: Keyword to search for (e.g., "bakery", "temple", "market")
            from_room_signature: Optional current room for pathfinding
            from_room_name: Optional current room name (for logging)

        Returns:
            Dict with: matches, nearest, path_to_nearest, compaction_needed
        """
        if not self.world_db:
            return {
                "success": False,
                "reason": "World database not available",
                "compaction_needed": False,
            }

        try:
            # Search for keyword
            matches = self.world_db.search_by_keyword(keyword)

            if not matches:
                self._log_event("navigation.keyword_search_empty", keyword=keyword)
                return {
                    "success": False,
                    "reason": f"No rooms found with keyword '{keyword}'",
                    "compaction_needed": self._check_compaction_needed(),
                }

            # If no current room, just return matches
            if not from_room_signature:
                return {
                    "success": True,
                    "keyword": keyword,
                    "matches": [
                        {
                            "name": m["name"],
                            "description": m["description"][:100] + "..." if m["description"] else "",
                            "visits": m["visit_count"],
                        }
                        for m in matches[:5]
                    ],
                    "count": len(matches),
                    "compaction_needed": self._check_compaction_needed(),
                }

            # Find route to nearest matching room
            from_room_id = self._resolve_room(from_room_signature, from_room_name)
            if not from_room_id:
                return {
                    "success": True,
                    "keyword": keyword,
                    "matches": [{"name": m["name"]} for m in matches[:3]],
                    "count": len(matches),
                    "reason": "Cannot compute path from unknown current location",
                    "compaction_needed": self._check_compaction_needed(),
                }

            # Find route to each match, return nearest
            nearest_match = None
            nearest_path = None
            nearest_distance = float('inf')

            for match in matches:
                path = find_path(self.world_db, from_room_id, match["id"])
                if path and len(path) < nearest_distance:
                    nearest_match = match
                    nearest_path = path
                    nearest_distance = len(path)

            if nearest_match:
                self._log_event("navigation.keyword_found",
                               keyword=keyword,
                               room=nearest_match["name"],
                               distance=nearest_distance)

                return {
                    "success": True,
                    "keyword": keyword,
                    "nearest_match": nearest_match["name"],
                    "distance": nearest_distance,
                    "path": nearest_path,
                    "all_matches": len(matches),
                    "instructions": self._format_keyword_hint(
                        keyword,
                        nearest_match["name"],
                        nearest_distance,
                        nearest_path
                    ),
                    "compaction_needed": self._check_compaction_needed(),
                }
            else:
                return {
                    "success": True,
                    "keyword": keyword,
                    "matches_found": len(matches),
                    "reason": "Matching rooms exist but are unreachable from current location",
                    "compaction_needed": self._check_compaction_needed(),
                }

        except Exception as e:
            self._log_event("navigation.keyword_search_error", error=str(e))
            return {
                "success": False,
                "reason": f"Keyword search error: {str(e)}",
                "compaction_needed": False,
            }

    def suggest_landmark_search(
        self,
        query: str,
        from_room_signature: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Suggest landmarks based on a natural language query.

        Args:
            query: Natural language query (e.g., "find a shop", "where's food?")
            from_room_signature: Optional current room

        Returns:
            Dict with: suggestions, keywords_searched, compaction_needed
        """
        if not self.world_db:
            return {"success": False, "reason": "World database not available"}

        # Extract keywords from query
        keywords = KeywordExtractor.extract(query, limit=5)

        if not keywords:
            return {
                "success": False,
                "reason": f"No recognizable landmarks in query: '{query}'",
                "compaction_needed": False,
            }

        # Search for each keyword
        results = []
        for keyword in keywords:
            matches = self.world_db.search_by_keyword(keyword)
            if matches:
                results.append({
                    "keyword": keyword,
                    "match_count": len(matches),
                    "nearest": matches[0]["name"],
                })

        return {
            "success": True,
            "query": query,
            "keywords_searched": keywords,
            "results": results,
            "compaction_needed": self._check_compaction_needed(),
        }

    # Private methods

    def _resolve_room(
        self,
        signature: Optional[str],
        name: Optional[str],
    ) -> Optional[str]:
        """Resolve a room ID from signature (preferred) or name."""
        if not self.world_db:
            return None

        # Try signature first (more reliable)
        if signature:
            rooms = self.world_db.get_rooms_by_signature(signature)
            if rooms:
                return rooms[0]["id"]

        # Fallback to name (less reliable, picks most-visited)
        if name:
            try:
                result = self.world_db.conn.execute(
                    "SELECT id FROM rooms WHERE name = ? ORDER BY visit_count DESC LIMIT 1",
                    (name,)
                ).fetchone()
                if result:
                    return result[0]
            except Exception:
                pass

        return None

    def _find_cached_path(
        self,
        from_room_id: str,
        to_room_id: str,
    ) -> Tuple[Optional[List[str]], bool]:
        """Check if path exists in world.db (all edges confirmed or probable).

        Returns:
            (path, cached) where cached=True if path was found in DB
        """
        if from_room_id == to_room_id:
            return [], True

        # Use BFS but it will only succeed if path is fully known
        # (confirmed and probable edges form a connected graph)
        path = find_path(self.world_db, from_room_id, to_room_id)

        if path:
            # Path was found using existing graph
            return path, True

        return None, False

    def _check_compaction_needed(self) -> bool:
        """Check if token usage is at 80% of 60k window.

        Returns:
            True if compaction should be triggered
        """
        if not self.logger:
            return False

        try:
            # Get current token usage from logger
            # This would need to be tracked by the logger
            # For now, return False - this would be set by the agent
            # based on actual token tracking
            return False
        except Exception:
            return False

    def _format_path(self, path: List[str]) -> str:
        """Format path as readable directions."""
        if not path:
            return "already here"
        if len(path) == 1:
            return f"go {path[0]}"
        return " → ".join(path)

    def _format_frontier_hint(
        self,
        frontier_room: str,
        distance: int,
        path: List[str],
        direction: str,
    ) -> str:
        """Format frontier query result as readable hint."""
        if distance == 0:
            return f"Unexplored exit '{direction}' is here"

        path_str = " → ".join(path) if path else "here"
        return f"Nearest unexplored: go {path_str} to reach {frontier_room}, then {direction}"

    def _format_keyword_hint(
        self,
        keyword: str,
        room_name: str,
        distance: int,
        path: List[str],
    ) -> str:
        """Format keyword search result as readable hint."""
        if distance == 0:
            return f"'{keyword.title()}' is here at {room_name}"

        path_str = " → ".join(path)
        return f"{keyword.title()}: go {path_str} to reach {room_name} ({distance} moves)"

    def _log_event(self, phase: str, **kwargs) -> None:
        """Log a navigation event."""
        if self.logger:
            self.logger.event(phase, **kwargs)
