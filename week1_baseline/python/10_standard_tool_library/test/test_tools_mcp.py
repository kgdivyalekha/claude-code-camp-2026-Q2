"""boukensha.tools.mcp is the generic MCP host layer: point it at any MCP
server and that server's tools become boukensha tools. These tests use the
mud-manager daemon as "some MCP server" and deliberately never rely on it
being a MUD.
"""

import unittest

from boukensha.tools import mcp as tools_mcp

from .helper import McpTestHelper


class TestToolsMcp(unittest.TestCase, McpTestHelper):
    def setUp(self) -> None:
        self.fake = self.start_fake_mud()
        self.client = None

    def tearDown(self) -> None:
        if self.client is not None:
            self.client.close()
        if self.fake is not None:
            self.fake.stop()

    def register(self, registry, prefix=None):
        self.client = tools_mcp.register(
            registry,
            command=self.mud_manager_command,
            args=self.mud_manager_args,
            env=self.fake_mud_env(self.fake),
            prefix=prefix,
        )
        return self.client

    def test_register_populates_the_registry_from_discovery(self):
        # Registration with an explicit command: no MUD knowledge anywhere.
        ctx, registry = self.new_registry()
        client = self.register(registry)

        self.assertEqual(len(client.tools), len(ctx.tools))
        self.assertIn("look", ctx.tools)
        self.assertRegex(registry.dispatch("look", {}), r"You do: look")

    def test_prefix_is_applied_locally_and_the_server_still_sees_bare_names(self):
        # Prefixing is a policy applied agent-side. The server keeps its own
        # names.
        ctx, registry = self.new_registry()
        self.register(registry, prefix="tbamud")

        self.assertIn("tbamud__look", ctx.tools)
        self.assertNotIn("look", ctx.tools)

        # If the prefix leaked onto the wire the daemon would reject this as
        # an unknown tool; getting the MUD's response back proves it didn't.
        self.assertRegex(registry.dispatch("tbamud__look", {}), r"You do: look")
        self.assertRegex(
            registry.dispatch("tbamud__attack", {"target": "dragon"}),
            r"You do: kill dragon",
        )

    def test_none_prefix_yields_bare_names(self):
        # Proves prefixing is opt-in policy, not baked into the mechanism.
        ctx, registry = self.new_registry()
        self.register(registry, prefix=None)
        self.assertIn("look", ctx.tools)
        self.assertNotIn("tbamud__look", ctx.tools)

    def test_schema_enum_is_surfaced_in_the_parameter_description(self):
        ctx, registry = self.new_registry()
        self.register(registry)
        self.assertRegex(
            ctx.tools["move"].parameters["direction"]["description"], r"one of:.*north"
        )

    def test_colliding_tool_names_raise(self):
        # Silent clobbering would be maddening to debug, so a collision is a
        # hard error naming the fix. Two servers sharing a prefix is the
        # realistic case.
        _ctx, registry = self.new_registry()
        self.register(registry, prefix="tbamud")

        second = None
        try:
            with self.assertRaises(tools_mcp.CollisionError) as cm:
                second = tools_mcp.register(
                    registry,
                    command=self.mud_manager_command,
                    args=self.mud_manager_args,
                    env=self.fake_mud_env(self.fake),
                    prefix="tbamud",
                )
            self.assertRegex(str(cm.exception), r"collision on 'tbamud__look'")
            self.assertRegex(str(cm.exception), r"prefix")
        finally:
            if second is not None:
                second.close()

    def test_collision_with_an_existing_non_mcp_tool_raises(self):
        # A collision against a tool boukensha registered itself (not another
        # MCP server) must be caught too — a filesystem server advertising
        # `read_file` is the obvious one.
        _ctx, registry = self.new_registry()
        registry.tool("look", description="pre-existing", block=lambda: "local")

        with self.assertRaises(tools_mcp.CollisionError) as cm:
            self.register(registry)
        self.assertRegex(str(cm.exception), r"collision on 'look'")


if __name__ == "__main__":
    unittest.main()
