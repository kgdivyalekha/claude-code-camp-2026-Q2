"""Admin commands for control-plane management of actors and policies."""

from typing import Any, Dict, Optional

from ..logger import Logger
from .actors import Actor, ActorRegistry, Role
from .audit import AuditLog
from .permissions import Policy


class AdminError(Exception):
    """Admin command failed."""
    pass


class AdminCommands:
    """Control-plane tier: actor lifecycle, role management, policy changes.

    All commands work on the local process and are not transmitted to the MUD.
    In-world admin (transfer, goto, force) requires immortal privileges and comes later.
    """

    def __init__(
        self,
        actors: ActorRegistry,
        audit: AuditLog,
        logger: Logger,
    ):
        self.actors = actors
        self.audit = audit
        self.logger = logger

    def _check_admin(self, actor: Actor) -> None:
        """Ensure actor has ADMIN role."""
        if actor.role != Role.ADMIN:
            raise AdminError(f"admin commands require ADMIN role, actor has {actor.role.value}")

    def list_actors(self, actor: Actor) -> list[Dict[str, Any]]:
        """List all active actors in the session."""
        self._check_admin(actor)
        return [
            {
                "id": a.id,
                "character": a.character,
                "role": a.role.value,
                "current_room": a.current_room,
            }
            for a in self.actors.list()
        ]

    def set_role(self, admin: Actor, actor_id: str, new_role: str) -> Dict[str, Any]:
        """Change an actor's role.

        Args:
            admin: The admin performing this action
            actor_id: The actor to modify
            new_role: One of 'observer', 'player', 'admin'

        Returns:
            Updated actor info
        """
        self._check_admin(admin)

        try:
            role = Role(new_role)
        except ValueError:
            raise AdminError(f"invalid role: {new_role}")

        target = self.actors.get(actor_id)
        if not target:
            raise AdminError(f"actor not found: {actor_id}")

        self.actors.update_role(actor_id, role)

        self.logger.event(
            "admin.set_role",
            admin=admin.id,
            actor=actor_id,
            new_role=new_role,
        )

        updated = self.actors.get(actor_id)
        return {
            "id": updated.id,
            "character": updated.character,
            "role": updated.role.value,
            "current_room": updated.current_room,
        }

    def pause_actor(self, admin: Actor, actor_id: str) -> Dict[str, str]:
        """Pause an actor (no-op in this milestone; cancel_event will be wired later).

        Returns:
            Status message
        """
        self._check_admin(admin)

        target = self.actors.get(actor_id)
        if not target:
            raise AdminError(f"actor not found: {actor_id}")

        # TODO: call agent.cancel_event if agent object is available
        self.logger.event("admin.pause", admin=admin.id, actor=actor_id)

        return {"status": f"paused {actor_id}"}

    def resume_actor(self, admin: Actor, actor_id: str) -> Dict[str, str]:
        """Resume a paused actor.

        Returns:
            Status message
        """
        self._check_admin(admin)

        target = self.actors.get(actor_id)
        if not target:
            raise AdminError(f"actor not found: {actor_id}")

        # TODO: clear pause state if actor object is available
        self.logger.event("admin.resume", admin=admin.id, actor=actor_id)

        return {"status": f"resumed {actor_id}"}

    def audit_for_actor(self, admin: Actor, actor_id: str) -> list[Dict[str, Any]]:
        """Retrieve audit trail for a specific actor."""
        self._check_admin(admin)

        target = self.actors.get(actor_id)
        if not target:
            raise AdminError(f"actor not found: {actor_id}")

        records = self.audit.query(target.session_id, actor_id=actor_id)
        return records

    def denied_actions(self, admin: Actor) -> Dict[str, list[str]]:
        """List tools that are statically denied for each actor.

        Useful for understanding what an actor cannot access.
        """
        self._check_admin(admin)

        results = {}
        for actor in self.actors.list():
            # This requires the policy to support statically_denied
            # If policy is a Composite, it collects from all sub-policies
            if hasattr(admin, "_policy") and hasattr(admin._policy, "statically_denied"):
                denied = admin._policy.statically_denied(actor)
                results[actor.id] = sorted(denied)
            else:
                results[actor.id] = []

        return results

    def reset_world(self, admin: Actor, backup_first: bool = True) -> Dict[str, str]:
        """Clear world memory (world.db).

        This is destructive — it forgets all rooms, exits, items.
        Typically not called; world.db persists across sessions.

        Args:
            admin: The admin performing this action
            backup_first: If True, create a backup before clearing

        Returns:
            Status message
        """
        self._check_admin(admin)

        # TODO: implement world DB reset with optional backup
        self.logger.event(
            "admin.reset_world",
            admin=admin.id,
            backup=backup_first,
        )

        return {"status": "world reset"}

    def actor_status(self, admin: Actor) -> Dict[str, Any]:
        """Get detailed status of all actors for dashboard."""
        self._check_admin(admin)

        return {
            "actors": self.list_actors(admin),
            "audit_enabled": True,
            "session": admin.session_id,
        }
