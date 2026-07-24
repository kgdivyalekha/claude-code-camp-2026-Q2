"""``mcp_servers:`` in settings.yaml is what makes boukensha a general MCP
host: plugging in a server is data, not code.
"""

import io
import unittest
from contextlib import redirect_stderr, redirect_stdout

from boukensha.run import _register_mcp_servers
from boukensha.mcp.client import Client
from boukensha.tools import mcp as tools_mcp

from .helper import McpTestHelper


class TestMcpServersConfig(unittest.TestCase, McpTestHelper):
    def setUp(self) -> None:
        self.fake = None

    def tearDown(self) -> None:
        if self.fake is not None:
            self.fake.stop()

    def test_parses_entries_and_applies_defaults(self):
        yaml_text = """
mcp_servers:
  mud:
    command: mud-manager
    args:    [--mcp]
    prefix:  tbamud
    env:
      MUD_HOST: your.mud.host
      MUD_PORT: 4000
  filesystem:
    command: npx
    required: false
"""
        with self.config_from(yaml_text) as cfg:
            mud = cfg.mcp_servers["mud"]
            self.assertEqual("mud-manager", mud["command"])
            self.assertEqual(["--mcp"], mud["args"])
            self.assertEqual("tbamud", mud["prefix"])
            # env values are stringified — YAML would hand us 4000 as an
            # int, and the spawn environment only accepts strings.
            self.assertEqual(
                {"MUD_HOST": "your.mud.host", "MUD_PORT": "4000"}, mud["env"]
            )
            self.assertTrue(mud["required"], "servers are required by default")

            fs = cfg.mcp_servers["filesystem"]
            self.assertEqual([], fs["args"])
            self.assertEqual({}, fs["env"])
            self.assertIsNone(fs["prefix"])
            self.assertFalse(fs["required"])

    def test_absent_block_is_empty(self):
        with self.config_from("tasks: {}") as cfg:
            self.assertEqual({}, cfg.mcp_servers)

    def test_required_server_that_fails_to_spawn_raises(self):
        # A required server that won't start is fatal: you asked for those
        # tools.
        yaml_text = """
mcp_servers:
  broken:
    command: boukensha-no-such-mcp-server-xyz
"""
        with self.config_from(yaml_text) as cfg:
            _ctx, registry = self.new_registry()
            with self.assertRaises(RuntimeError) as cm:
                _register_mcp_servers(registry, cfg)
            self.assertRegex(str(cm.exception), r"'broken' failed to start")

    def test_optional_server_that_fails_to_spawn_warns_and_continues(self):
        # An optional server that won't start is a warning: the agent is
        # still useful without its tools.
        yaml_text = """
mcp_servers:
  decorative:
    command: boukensha-no-such-mcp-server-xyz
    required: false
"""
        with self.config_from(yaml_text) as cfg:
            ctx, registry = self.new_registry()
            out, err = io.StringIO(), io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                _register_mcp_servers(registry, cfg)
            self.assertRegex(
                out.getvalue() + err.getvalue(),
                r"optional MCP server 'decorative' failed to start",
            )
            self.assertEqual(0, len(ctx.tools))

    def test_optional_server_does_not_excuse_a_collision(self):
        # required: false excuses a server that won't START. It does not
        # excuse a name collision — that's a contradiction in the config,
        # and swallowing it would silently drop the whole server's toolset.
        self.fake = self.start_fake_mud()
        yaml_text = self._server_yaml("unprefixed", extra="    required: false")
        with self.config_from(yaml_text) as cfg:
            _ctx, registry = self.new_registry()
            registry.tool("look", description="pre-existing", block=lambda: "local")

            with self.assertRaises(tools_mcp.CollisionError):
                _register_mcp_servers(registry, cfg)

    def test_mud_is_just_another_server(self):
        # `mud` gets no special treatment: it is spawned by the same code
        # path as any other server, and a bad command kills the agent
        # exactly like any other required entry would. The agent has no
        # idea it's a MUD.
        yaml_text = """
mcp_servers:
  mud:
    command: boukensha-no-such-mcp-server-xyz
"""
        with self.config_from(yaml_text) as cfg:
            _ctx, registry = self.new_registry()
            with self.assertRaises(RuntimeError) as cm:
                _register_mcp_servers(registry, cfg)
            self.assertRegex(str(cm.exception), r"'mud' failed to start")

    def test_returns_a_tool_count_per_server(self):
        # The banner needs to tell you what the agent can actually do,
        # since without servers it can do nothing at all.
        self.fake = self.start_fake_mud()
        expected = Client.spawn(
            command=self.mud_manager_command,
            args=self.mud_manager_args,
            env=self.fake_mud_env(self.fake),
        )
        expected_count = len(expected.tools)
        expected.close()

        yaml_text = self._server_yaml("mud", extra="    prefix: tbamud")
        with self.config_from(yaml_text) as cfg:
            _ctx, registry = self.new_registry()
            summary = _register_mcp_servers(registry, cfg)
            self.assertEqual({"mud": expected_count}, summary)

    # ---------- helpers -------------------------------------------------

    def _server_yaml(self, name: str, extra: str = "") -> str:
        return f"""
mcp_servers:
  {name}:
    command: {self.mud_manager_command}
    args:    {self.mud_manager_args}
{extra}
    env:
      MUD_HOST:     127.0.0.1
      MUD_PORT:     {self.fake.port}
      MUD_NAME:     Gandalf
      MUD_PASSWORD: secret
"""


if __name__ == "__main__":
    unittest.main()
