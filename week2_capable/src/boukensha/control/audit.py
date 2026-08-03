"""Audit logging for permission decisions and tool calls."""

import json
import sqlite3
from datetime import datetime
from typing import Any, Dict, Optional

from .actors import Actor
from .permissions import Decision


class AuditLog:
    """Write permission decisions and tool calls to audit trail."""

    def __init__(self, db_path: str = ".boukensha/events.db"):
        self.db_path = db_path
        self._init_schema()

    def _init_schema(self) -> None:
        """Create audit_log table if it doesn't exist."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                at TEXT NOT NULL,
                session_id TEXT NOT NULL,
                actor TEXT NOT NULL,
                action TEXT NOT NULL,
                args TEXT,
                target_actor TEXT,
                target_room TEXT,
                verdict TEXT NOT NULL,
                rule TEXT,
                reason TEXT
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_log(actor, at)"
        )
        conn.commit()
        conn.close()

    def record(
        self,
        actor: Actor,
        tool: str,
        args: Optional[Dict[str, Any]],
        decision: Decision,
        target_actor: Optional[str] = None,
        target_room: Optional[str] = None,
    ) -> None:
        """Record a permission decision for an attempted tool call.

        Args:
            actor: The actor attempting the action
            tool: Tool name (e.g., 'scout__look')
            args: Tool arguments
            decision: The Decision returned by the permission check
            target_actor: If the action targets another actor (e.g., admin commands)
            target_room: If the action targets a room (e.g., zone policy)
        """
        # Redact credentials from args before logging
        redacted_args = self._redact_credentials(args)

        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """
            INSERT INTO audit_log
            (at, session_id, actor, action, args, target_actor, target_room, verdict, rule, reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now().isoformat(),
                actor.session_id,
                actor.id,
                tool,
                json.dumps(redacted_args) if redacted_args else None,
                target_actor,
                target_room,
                decision.verdict,
                decision.rule,
                decision.reason,
            ),
        )
        conn.commit()
        conn.close()

    @staticmethod
    def _redact_credentials(args: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Remove passwords and other sensitive data from args."""
        if not args:
            return args

        redacted = args.copy()
        # Redact common password/credential fields
        for key in ['password', 'passwd', 'pwd', 'token', 'secret', 'api_key']:
            if key in redacted:
                redacted[key] = "[REDACTED]"

        # For send_raw, redact if it contains 'password' command
        if 'command' in redacted and isinstance(redacted['command'], str):
            if 'password' in redacted['command'].lower():
                redacted['command'] = "[REDACTED]"

        return redacted

    def query(
        self,
        session_id: str,
        actor_id: Optional[str] = None,
        verdict: Optional[str] = None,
    ) -> list[Dict[str, Any]]:
        """Query the audit log."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        query = "SELECT * FROM audit_log WHERE session_id = ?"
        params = [session_id]

        if actor_id:
            query += " AND actor = ?"
            params.append(actor_id)

        if verdict:
            query += " AND verdict = ?"
            params.append(verdict)

        query += " ORDER BY at DESC"

        cursor = conn.execute(query, params)
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return rows
