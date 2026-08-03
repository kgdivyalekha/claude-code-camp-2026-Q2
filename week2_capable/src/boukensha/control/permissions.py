"""Permission policies: declarative tool access control."""

import re
import sqlite3
from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol, Set

from .actors import Actor, Role


@dataclass(frozen=True)
class Decision:
    """Result of a permission check."""
    verdict: str          # "allow" | "deny" | "ask"
    rule: str             # which rule decided this — audit trail
    reason: str = ""


class Policy(Protocol):
    """Permission check interface."""

    def check(self, actor: Actor, tool: str, args: Optional[Dict[str, Any]] = None) -> Decision:
        """Check if actor can call tool with args.

        Returns Decision with verdict: "allow", "deny", or "ask" (defer to operator).
        """
        ...

    def statically_denied(self, actor: Actor) -> Set[str]:
        """Tools that can never be allowed for this actor, regardless of arguments.

        Used by ToolGate (M4) to exclude them from the schema payload entirely.
        """
        ...


class AllowList:
    """Name-level allow-list with glob patterns."""

    def __init__(self, patterns: list[str]):
        """patterns: list of tool name globs, e.g., ['scout__*', '*__look']"""
        self.patterns = patterns
        self._compiled = [self._compile_glob(p) for p in patterns]

    @staticmethod
    def _compile_glob(pattern: str) -> re.Pattern:
        """Convert glob to regex."""
        escaped = re.escape(pattern)
        escaped = escaped.replace(r"\*", ".*")
        return re.compile(f"^{escaped}$")

    def check(self, actor: Actor, tool: str, args: Optional[Dict[str, Any]] = None) -> Decision:
        for regex in self._compiled:
            if regex.match(tool):
                return Decision("allow", "allow_list")
        return Decision("deny", "allow_list", f"{tool} not in allow-list")

    def statically_denied(self, actor: Actor) -> Set[str]:
        return set()


class DenyList:
    """Name-level deny-list with glob patterns."""

    def __init__(self, patterns: list[str]):
        self.patterns = patterns
        self._compiled = [self._compile_glob(p) for p in patterns]

    @staticmethod
    def _compile_glob(pattern: str) -> re.Pattern:
        escaped = re.escape(pattern)
        escaped = escaped.replace(r"\*", ".*")
        return re.compile(f"^{escaped}$")

    def check(self, actor: Actor, tool: str, args: Optional[Dict[str, Any]] = None) -> Decision:
        for regex in self._compiled:
            if regex.match(tool):
                return Decision("deny", "deny_list", f"{tool} in deny-list")
        return Decision("allow", "deny_list")

    def statically_denied(self, actor: Actor) -> Set[str]:
        # Collect all tools matching deny patterns
        # This is approximate — we don't know the full tool registry here
        denied = set()
        for pattern in self.patterns:
            if "*" not in pattern:  # Only concrete names
                denied.add(pattern)
        return denied


class ArgumentPolicy:
    """Match argument values; deny if pattern matches."""

    def __init__(self, rules: Dict[str, str]):
        """rules: { 'send_raw': { 'command': '^(quit|delete)' }, ... }

        Format: tool → { arg_name: regex_pattern }
        """
        self.rules = {tool: {k: re.compile(v) for k, v in args.items()}
                     for tool, args in rules.items()}

    def check(self, actor: Actor, tool: str, args: Optional[Dict[str, Any]] = None) -> Decision:
        if tool not in self.rules:
            return Decision("allow", "argument_policy")

        args = args or {}
        for arg_name, pattern in self.rules[tool].items():
            value = args.get(arg_name, "")
            if isinstance(value, str) and pattern.search(value):
                return Decision("deny", "argument_policy",
                              f"{tool}.{arg_name} matches blocked pattern")
        return Decision("allow", "argument_policy")

    def statically_denied(self, actor: Actor) -> Set[str]:
        return set()  # Argument-level, not tool-level


class RolePolicy:
    """Role → permitted tool categories."""

    # Role → visible categories (matches ToolGate)
    ROLE_CATEGORIES = {
        Role.OBSERVER: {"perception"},
        Role.PLAYER: {"perception", "movement", "communication", "inventory"},
        Role.ADMIN: {"perception", "movement", "combat", "communication", "inventory", "magic", "utility"},
    }

    # Tool → category
    TOOL_CATEGORIES = {
        "look": "perception", "examine": "perception", "check": "perception",
        "move": "movement", "flee": "movement", "set_position": "movement", "track": "movement",
        "attack": "combat", "skill_strike": "combat", "consider": "combat",
        "say": "communication", "tell": "communication", "channel_say": "communication",
        "get_item": "inventory", "drop_item": "inventory", "put_item": "inventory",
        "equip_item": "inventory", "consume_item": "inventory",
        "cast_spell": "magic", "use_magic_item": "magic",
        "shop": "utility", "practice": "utility", "save_character": "utility",
        "send_raw": "utility", "poll": "utility", "mud_status": "utility",
    }

    def check(self, actor: Actor, tool: str, args: Optional[Dict[str, Any]] = None) -> Decision:
        category = self.TOOL_CATEGORIES.get(tool)
        if not category:
            return Decision("allow", "role_policy")  # Unknown tool, allow (other policies handle it)

        allowed_categories = self.ROLE_CATEGORIES.get(actor.role, set())
        if category in allowed_categories:
            return Decision("allow", "role_policy")

        return Decision("deny", "role_policy",
                       f"role {actor.role.value} cannot access {category} tools")

    def statically_denied(self, actor: Actor) -> Set[str]:
        """Tools this role can never access."""
        allowed_categories = self.ROLE_CATEGORIES.get(actor.role, set())
        denied = set()
        for tool, category in self.TOOL_CATEGORIES.items():
            if category not in allowed_categories:
                denied.add(tool)
        return denied


class RateLimit:
    """Limit calls per turn and per session."""

    def __init__(self, per_turn: Optional[Dict[str, int]] = None,
                 per_session: Optional[Dict[str, int]] = None):
        """per_turn: { 'scout__look': 5 }
        per_session: { 'warden__cast_spell': 50 }
        """
        self.per_turn = per_turn or {}
        self.per_session = per_session or {}
        # Track call counts: (session_id, actor_id, turn) → { tool: count }
        self._turn_counts: Dict[tuple, Dict[str, int]] = {}
        # Track session totals: (session_id, actor_id) → { tool: count }
        self._session_counts: Dict[tuple, Dict[str, int]] = {}

    def check(self, actor: Actor, tool: str, args: Optional[Dict[str, Any]] = None) -> Decision:
        # Check per-turn limit
        turn_key = (actor.session_id, actor.id, getattr(actor, '_current_turn', 0))
        turn_counts = self._turn_counts.setdefault(turn_key, {})
        turn_count = turn_counts.get(tool, 0)

        if tool in self.per_turn and turn_count >= self.per_turn[tool]:
            return Decision("deny", "rate_limit",
                          f"{tool}: {turn_count} calls this turn, limit {self.per_turn[tool]}")

        # Check per-session limit
        session_key = (actor.session_id, actor.id)
        session_counts = self._session_counts.setdefault(session_key, {})
        session_count = session_counts.get(tool, 0)

        if tool in self.per_session and session_count >= self.per_session[tool]:
            return Decision("deny", "rate_limit",
                          f"{tool}: {session_count} calls this session, limit {self.per_session[tool]}")

        return Decision("allow", "rate_limit")

    def record(self, actor: Actor, tool: str, turn: int) -> None:
        """Call this after a successful tool call to update counts."""
        turn_key = (actor.session_id, actor.id, turn)
        turn_counts = self._turn_counts.setdefault(turn_key, {})
        turn_counts[tool] = turn_counts.get(tool, 0) + 1

        session_key = (actor.session_id, actor.id)
        session_counts = self._session_counts.setdefault(session_key, {})
        session_counts[tool] = session_counts.get(tool, 0) + 1

    def statically_denied(self, actor: Actor) -> Set[str]:
        return set()  # Rate limits never categorically deny


class Budget:
    """Deny once session cost or tokens exceed ceiling.

    Reads live from events.db.
    """

    def __init__(self, max_cost_usd: Optional[float] = None, max_tokens: Optional[int] = None,
                 events_db_path: Optional[str] = None):
        self.max_cost_usd = max_cost_usd
        self.max_tokens = max_tokens
        self.events_db_path = events_db_path or ".boukensha/events.db"

    def check(self, actor: Actor, tool: str, args: Optional[Dict[str, Any]] = None) -> Decision:
        if not (self.max_cost_usd or self.max_tokens):
            return Decision("allow", "budget")

        try:
            conn = sqlite3.connect(self.events_db_path)
            cursor = conn.cursor()

            if self.max_cost_usd:
                cursor.execute(
                    "SELECT COALESCE(SUM(cost_usd), 0) FROM events WHERE session_id = ? AND actor = ?",
                    (actor.session_id, actor.id)
                )
                total_cost = cursor.fetchone()[0]
                if total_cost >= self.max_cost_usd:
                    conn.close()
                    return Decision("deny", "budget",
                                  f"session cost ${total_cost:.2f} >= ${self.max_cost_usd:.2f}")

            if self.max_tokens:
                cursor.execute(
                    "SELECT COALESCE(SUM(input_tokens + output_tokens), 0) FROM events "
                    "WHERE session_id = ? AND actor = ? AND phase = 'response'",
                    (actor.session_id, actor.id)
                )
                total_tokens = cursor.fetchone()[0]
                if total_tokens >= self.max_tokens:
                    conn.close()
                    return Decision("deny", "budget",
                                  f"session tokens {total_tokens} >= {self.max_tokens}")

            conn.close()
        except sqlite3.Error as e:
            # If DB is missing or broken, don't block — log the error elsewhere
            pass

        return Decision("allow", "budget")

    def statically_denied(self, actor: Actor) -> Set[str]:
        return set()


class Composite:
    """Ordered, first-match-wins composition of policies.

    Policies are checked in order; first Decision with a non-default verdict wins.
    Default is "deny" unless specified otherwise.
    """

    def __init__(self, policies: list[Policy], default: str = "deny"):
        self.policies = policies
        self.default = default

    def check(self, actor: Actor, tool: str, args: Optional[Dict[str, Any]] = None) -> Decision:
        for policy in self.policies:
            decision = policy.check(actor, tool, args)
            if decision.verdict != "allow":  # First match: deny or ask
                return decision
        return Decision(self.default, "composite_default")

    def statically_denied(self, actor: Actor) -> Set[str]:
        """Collect all tools statically denied by any policy."""
        denied = set()
        for policy in self.policies:
            denied.update(policy.statically_denied(actor))
        return denied
