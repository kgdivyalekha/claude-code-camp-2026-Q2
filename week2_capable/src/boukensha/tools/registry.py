"""Tool registry for navigator and other helper tools.

These tools are available to the agent for navigation, exploration, and world interaction.
They complement the MCP tools by providing world-db-aware assistance.
"""

from typing import Dict, Any, Callable, Optional
from dataclasses import dataclass

from boukensha.world.db import WorldDB
from boukensha.logger import Logger
from .navigator import Navigator


@dataclass
class ToolDefinition:
    """Definition of an available tool."""
    name: str
    description: str
    parameters: Dict[str, Any]
    handler: Callable


class HelperToolRegistry:
    """Registry of helper tools that augment MCP tools with world-db awareness."""

    def __init__(self, world_db: Optional[WorldDB] = None, logger: Optional[Logger] = None):
        self.world_db = world_db
        self.logger = logger
        self.navigator = Navigator(world_db, logger)
        self._tools = self._init_tools()

    def _init_tools(self) -> Dict[str, ToolDefinition]:
        """Initialize available helper tools."""
        return {
            "navigate": ToolDefinition(
                name="navigate",
                description="Query the world map for a path to a known location. "
                           "First checks cached world.db paths, then computes via BFS if needed. "
                           "Much cheaper than exploring blindly.",
                parameters={
                    "type": "object",
                    "properties": {
                        "destination": {
                            "type": "string",
                            "description": "Name of destination room (must be already discovered)"
                        },
                        "destination_signature": {
                            "type": "string",
                            "description": "Optional: Exact signature for destination (more reliable than name)"
                        }
                    },
                    "required": ["destination"]
                },
                handler=self.handle_navigate,
            ),
            "explore": ToolDefinition(
                name="explore",
                description="Find the nearest unexplored exit from current location. "
                           "Guides exploration without tokens wasted on wandering.",
                parameters={
                    "type": "object",
                    "properties": {
                        "include_distance": {
                            "type": "boolean",
                            "description": "Include distance in response (default: true)"
                        }
                    },
                    "required": []
                },
                handler=self.handle_explore,
            ),
            "exits": ToolDefinition(
                name="exits",
                description="Get status of exits from current room (explored vs unexplored). "
                           "Helps plan next moves without re-exploring.",
                parameters={
                    "type": "object",
                    "properties": {},
                    "required": []
                },
                handler=self.handle_exits,
            ),
        }

    def get_tools(self) -> Dict[str, ToolDefinition]:
        """Get all available helper tools."""
        return self._tools

    def call_tool(
        self,
        name: str,
        from_room_signature: str,
        from_room_name: Optional[str] = None,
        args: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Call a helper tool.

        Args:
            name: Tool name
            from_room_signature: Current room signature
            from_room_name: Current room name (for logging)
            args: Tool arguments

        Returns:
            Tool result dict
        """
        args = args or {}

        if name not in self._tools:
            return {
                "ok": False,
                "error": f"Unknown tool: {name}"
            }

        tool_def = self._tools[name]

        try:
            return tool_def.handler(
                from_room_signature=from_room_signature,
                from_room_name=from_room_name,
                **args
            )
        except Exception as e:
            return {
                "ok": False,
                "error": str(e)
            }

    # Tool handlers

    def handle_navigate(
        self,
        destination: str,
        from_room_signature: str,
        from_room_name: Optional[str] = None,
        destination_signature: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Handle navigation query."""
        if not self.world_db:
            return {
                "ok": False,
                "error": "World database not available"
            }

        result = self.navigator.navigate_to(
            from_room_signature=from_room_signature,
            to_room_name=destination,
            from_room_name=from_room_name,
            to_room_signature=destination_signature,
        )

        # Format for agent consumption
        if result["success"]:
            return {
                "ok": True,
                "path": result["path"],
                "distance": result["distance"],
                "cached": result["cached"],
                "instructions": result["reason"],
                "compaction_needed": result.get("compaction_needed", False),
            }
        else:
            return {
                "ok": False,
                "error": result["reason"],
                "compaction_needed": result.get("compaction_needed", False),
            }

    def handle_explore(
        self,
        from_room_signature: str,
        from_room_name: Optional[str] = None,
        include_distance: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        """Handle frontier exploration query."""
        if not self.world_db:
            return {
                "ok": False,
                "error": "World database not available"
            }

        result = self.navigator.explore_frontier(
            from_room_signature=from_room_signature,
            from_room_name=from_room_name,
        )

        if result["success"]:
            response = {
                "ok": True,
                "frontier_direction": result["frontier_direction"],
                "frontier_room": result["frontier_room"],
                "instructions": result["reason"],
                "compaction_needed": result.get("compaction_needed", False),
            }
            if include_distance:
                response["distance"] = result["distance"]
                response["path"] = result["path"]
            return response
        else:
            return {
                "ok": False,
                "error": result["reason"],
                "compaction_needed": result.get("compaction_needed", False),
            }

    def handle_exits(
        self,
        from_room_signature: str,
        from_room_name: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Handle exit status query."""
        if not self.world_db:
            return {
                "ok": False,
                "error": "World database not available"
            }

        result = self.navigator.get_exit_status(
            from_room_signature=from_room_signature,
            from_room_name=from_room_name,
        )

        return {
            "ok": True,
            "explored": result["explored_exits"],
            "unexplored": result["unexplored_exits"],
            "compaction_needed": result.get("compaction_needed", False),
        }
