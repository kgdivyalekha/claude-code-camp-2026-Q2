"""Test M5 permissions + hooks + audit."""

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from boukensha.control import (
    Actor,
    ActorRegistry,
    AdminCommands,
    AllowList,
    AuditLog,
    Composite,
    Decision,
    DenyList,
    GuardedRegistry,
    HookRegistry,
    PermissionDenied,
    RateLimit,
    Role,
    ToolBlocked,
)
from boukensha.logger import Logger
from boukensha.registry import Registry


class TestPermissions(unittest.TestCase):
    def setUp(self):
        self.actor = Actor("scout", "Scout", Role.PLAYER, "session-1")

    def test_allowlist(self):
        policy = AllowList(["*__look", "*__move"])

        allow_result = policy.check(self.actor, "scout__look", {})
        self.assertEqual(allow_result.verdict, "allow")

        deny_result = policy.check(self.actor, "scout__attack", {})
        self.assertEqual(deny_result.verdict, "deny")

    def test_denylist(self):
        policy = DenyList(["*__send_raw"])

        allow_result = policy.check(self.actor, "scout__look", {})
        self.assertEqual(allow_result.verdict, "allow")

        deny_result = policy.check(self.actor, "scout__send_raw", {})
        self.assertEqual(deny_result.verdict, "deny")

    def test_ratelimit(self):
        policy = RateLimit(per_turn={"scout__look": 2})

        # First two calls allowed
        self.assertEqual(policy.check(self.actor, "scout__look", {}).verdict, "allow")
        policy.record(self.actor, "scout__look", turn=1)

        self.assertEqual(policy.check(self.actor, "scout__look", {}).verdict, "allow")
        policy.record(self.actor, "scout__look", turn=1)

        # Third call denied
        self.assertEqual(policy.check(self.actor, "scout__look", {}).verdict, "deny")

    def test_composite_firstmatch(self):
        p1 = DenyList(["*__send_raw"])
        p2 = AllowList(["*__*"])
        policy = Composite([p1, p2])

        # send_raw denied by p1, stops there
        self.assertEqual(policy.check(self.actor, "scout__send_raw", {}).verdict, "deny")

        # look allowed by p1 (doesn't deny), passes to p2 which allows
        self.assertEqual(policy.check(self.actor, "scout__look", {}).verdict, "allow")

    def test_statically_denied(self):
        policy = DenyList(["*__send_raw", "*__quit"])
        denied = policy.statically_denied(self.actor)
        self.assertIn("scout__send_raw", denied)


class TestHooks(unittest.TestCase):
    def setUp(self):
        self.hooks = HookRegistry()
        self.fired = []

    def test_sync_hook(self):
        def on_call(**payload):
            self.fired.append(("call", payload))

        self.hooks.register("before_tool_call", on_call)
        self.hooks.trigger("before_tool_call", actor="scout", name="look", args={})

        self.assertEqual(len(self.fired), 1)
        self.assertEqual(self.fired[0][0], "call")

    def test_hook_result_rewriting(self):
        def compress(**payload):
            result = payload.get("result", {})
            result["compressed"] = True
            return result

        self.hooks.register("after_tool_call", compress)
        result = self.hooks.trigger(
            "after_tool_call",
            actor="scout",
            name="look",
            args={},
            result={"text": "room description"},
        )

        self.assertTrue(result["compressed"])

    def test_hook_priority_order(self):
        order = []

        def first(**payload):
            order.append("first")

        def second(**payload):
            order.append("second")

        self.hooks.register("test", first, priority=10)
        self.hooks.register("test", second, priority=90)
        self.hooks.trigger("test")

        self.assertEqual(order, ["second", "first"])  # 90 priority first

    def test_hook_blocking(self):
        def block(**payload):
            raise ToolBlocked("blocked")

        self.hooks.register("before_tool_call", block)

        with self.assertRaises(ToolBlocked):
            self.hooks.trigger("before_tool_call", actor="scout", name="look")


class TestGuardedRegistry(unittest.TestCase):
    def setUp(self):
        self.actor = Actor("scout", "Scout", Role.PLAYER, "session-1")
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")

        # Set up minimal registries and policies
        self.inner_registry = Registry()
        self.inner_registry.tool("look")(lambda: {"text": "You are here."})

        self.policy = AllowList(["*__look"])
        self.hooks = HookRegistry()
        self.logger = Logger(session_id="session-1")
        self.audit = AuditLog(self.db_path)

        self.guarded = GuardedRegistry(
            self.inner_registry,
            actor=self.actor,
            policy=self.policy,
            hooks=self.hooks,
            logger=self.logger,
            audit=self.audit,
        )

    def tearDown(self):
        import os
        try:
            os.close(self.db_fd)
            os.unlink(self.db_path)
        except:
            pass

    def test_allowed_tool_succeeds(self):
        result = self.guarded.dispatch("look")
        self.assertEqual(result, {"text": "You are here."})

    def test_denied_tool_raises(self):
        policy = DenyList(["*__look"])
        guarded = GuardedRegistry(
            self.inner_registry,
            actor=self.actor,
            policy=policy,
            hooks=self.hooks,
            logger=self.logger,
            audit=self.audit,
        )

        with self.assertRaises(PermissionDenied):
            guarded.dispatch("look")

    def test_audit_records_decision(self):
        self.guarded.dispatch("look")

        # Query audit log
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            "SELECT verdict, rule FROM audit_log WHERE actor = ?", ("scout",)
        )
        row = cursor.fetchone()
        conn.close()

        self.assertIsNotNone(row)
        self.assertEqual(row[0], "allow")
        self.assertEqual(row[1], "allow_list")

    def test_hook_rewriting(self):
        def add_marker(**payload):
            result = payload.get("result", {})
            result["marker"] = "compressed"
            return result

        self.hooks.register("after_tool_call", add_marker)
        result = self.guarded.dispatch("look")

        self.assertEqual(result["marker"], "compressed")


class TestAuditLog(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        self.audit = AuditLog(self.db_path)

    def tearDown(self):
        import os
        try:
            os.close(self.db_fd)
            os.unlink(self.db_path)
        except:
            pass

    def test_record_and_query(self):
        actor = Actor("scout", "Scout", Role.PLAYER, "session-1")
        decision = Decision("allow", "test_rule", "test reason")

        self.audit.record(actor, "look", {"arg": "value"}, decision)

        records = self.audit.query("session-1", actor_id="scout")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["action"], "look")
        self.assertEqual(records[0]["verdict"], "allow")

    def test_credential_redaction(self):
        actor = Actor("scout", "Scout", Role.PLAYER, "session-1")
        decision = Decision("deny", "test_rule")

        self.audit.record(
            actor,
            "send_raw",
            {"command": "password newpass123", "other": "data"},
            decision,
        )

        records = self.audit.query("session-1")
        args = json.loads(records[0]["args"])
        self.assertEqual(args["command"], "[REDACTED]")
        self.assertEqual(args["other"], "data")


class TestAdminCommands(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        self.admin = Actor("admin1", "Admin", Role.ADMIN, "session-1")
        self.player = Actor("scout", "Scout", Role.PLAYER, "session-1")

        self.actors = ActorRegistry()
        self.actors.register(self.admin)
        self.actors.register(self.player)

        self.audit = AuditLog(self.db_path)
        self.logger = Logger(session_id="session-1")

        self.admin_cmd = AdminCommands(self.actors, self.audit, self.logger)

    def tearDown(self):
        import os
        try:
            os.close(self.db_fd)
            os.unlink(self.db_path)
        except:
            pass

    def test_list_actors(self):
        actors = self.admin_cmd.list_actors(self.admin)
        self.assertEqual(len(actors), 2)
        self.assertEqual(actors[0]["id"], "admin1")

    def test_set_role(self):
        result = self.admin_cmd.set_role(self.admin, "scout", "observer")
        self.assertEqual(result["role"], "observer")

        # Verify change persisted
        updated = self.actors.get("scout")
        self.assertEqual(updated.role, Role.OBSERVER)

    def test_non_admin_cannot_execute(self):
        from boukensha.control import AdminError

        with self.assertRaises(AdminError):
            self.admin_cmd.list_actors(self.player)


if __name__ == "__main__":
    unittest.main()
