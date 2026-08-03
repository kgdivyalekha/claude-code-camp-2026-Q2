"""Actor definitions: MUD characters + their policy context."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional


class Role(Enum):
    """Role restricts tool access and token exposure."""
    OBSERVER = "observer"    # perception only
    PLAYER = "player"        # perception, movement, communication, inventory
    ADMIN = "admin"          # all tools + control-plane commands


@dataclass(frozen=True)
class Actor:
    """An actor is a MUD character + policy context."""
    id: str                  # 'scout', 'warden' — matches mcp_servers key and tool prefix
    character: str           # MUD character name
    role: Role
    session_id: str
    current_room: Optional[str] = None


class ActorRegistry:
    """Track active actors in a session."""

    def __init__(self):
        self._actors: Dict[str, Actor] = {}

    def register(self, actor: Actor) -> None:
        """Register an actor for this session."""
        if actor.id in self._actors:
            raise ValueError(f"Actor {actor.id} already registered")
        self._actors[actor.id] = actor

    def unregister(self, actor_id: str) -> None:
        """Unregister an actor."""
        self._actors.pop(actor_id, None)

    def get(self, actor_id: str) -> Optional[Actor]:
        """Retrieve an actor by ID."""
        return self._actors.get(actor_id)

    def list(self) -> list[Actor]:
        """List all registered actors."""
        return list(self._actors.values())

    def update_room(self, actor_id: str, room_id: str) -> None:
        """Update actor's current room."""
        actor = self._actors.get(actor_id)
        if actor:
            self._actors[actor_id] = Actor(
                id=actor.id,
                character=actor.character,
                role=actor.role,
                session_id=actor.session_id,
                current_room=room_id,
            )

    def update_role(self, actor_id: str, role: Role) -> None:
        """Change actor's role."""
        actor = self._actors.get(actor_id)
        if actor:
            self._actors[actor_id] = Actor(
                id=actor.id,
                character=actor.character,
                role=role,
                session_id=actor.session_id,
                current_room=actor.current_room,
            )
