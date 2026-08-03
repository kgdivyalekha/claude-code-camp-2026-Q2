"""Permission, hooks, and audit control plane for multi-actor agent system."""

from .actors import Actor, ActorRegistry, Role
from .admin import AdminCommands, AdminError
from .audit import AuditLog
from .guarded_registry import GuardedRegistry, PermissionDenied
from .hooks import HookRegistry, ToolBlocked
from .permissions import (
    AllowList,
    ArgumentPolicy,
    Budget,
    Composite,
    Decision,
    DenyList,
    Policy,
    RateLimit,
    RolePolicy,
)

__all__ = [
    "Actor",
    "ActorRegistry",
    "Role",
    "AdminCommands",
    "AdminError",
    "AuditLog",
    "GuardedRegistry",
    "PermissionDenied",
    "HookRegistry",
    "ToolBlocked",
    "AllowList",
    "ArgumentPolicy",
    "Budget",
    "Composite",
    "Decision",
    "DenyList",
    "Policy",
    "RateLimit",
    "RolePolicy",
]
