"""World memory subsystem — persistent room database with identity reconciliation.

The world module tracks the MUD map as the agent explores:
- Rooms are identified by signature (name + exits + description), not by name alone
- Room identity is probabilistic: confirmed, probable, or ambiguous
- Exits are reconciled via reciprocity: moving back should return to sender
- Pathfinding uses BFS over confirmed and probable edges
"""

from .db import WorldDB
from .identity import signature
from .pathfind import find_path, nearest_unexplored

__all__ = [
    "WorldDB",
    "signature",
    "find_path",
    "nearest_unexplored",
]
