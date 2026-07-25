"""boukensha.mcp.client.Client is boukensha's own MCP-over-stdio client. It is
server-agnostic: it takes a command, args, and env, and speaks the protocol.
We point it at the mud-manager daemon because that is the MCP server this
repo ships — nothing in the client knows that.
"""

import unittest

from boukensha.mcp.client import Client

from .helper import McpTestHelper


class TestMcpClient(unittest.TestCase, McpTestHelper):
    def setUp(self) -> None:
        self.fake = self.start_fake_mud()
        self.client = None

    def tearDown(self) -> None:
        if self.client is not None:
            self.client.close()
        if self.fake is not None:
            self.fake.stop()

    def spawn_client(self) -> Client:
        self.client = Client.spawn(
            command=self.mud_manager_command,
            args=self.mud_manager_args,
            env=self.fake_mud_env(self.fake),
        )
        return self.client

    def test_handshake_reports_server_info(self):
        client = self.spawn_client()
        self.assertEqual("mud-manager", client.server_info["name"])
        self.assertIsNotNone(client.server_info["version"])

    def test_tools_list_is_discovered(self):
        client = self.spawn_client()
        names = [t["name"] for t in client.tools]
        self.assertIn("look", names)
        self.assertIn("attack", names)
        # Discovery is the server's word, not ours — the client invents nothing.
        self.assertGreater(len(client.tools), 1)
        self.assertTrue(all("inputSchema" in t for t in client.tools))

    def test_call_tool_reaches_the_mud(self):
        client = self.spawn_client()
        self.assertRegex(client.call_tool("look")["text"], r"You do: look")
        self.assertRegex(
            client.call_tool("attack", {"target": "dragon"})["text"],
            r"You do: kill dragon",
        )

    def test_tool_error_comes_back_as_data(self):
        # A tool-level failure is data (error), not an exception — the agent
        # loop must be able to keep going.
        client = self.spawn_client()
        result = client.call_tool("move", {"direction": "sideways"})
        self.assertTrue(result["error"], "expected isError to be set")
        self.assertRegex(result["text"], r"argument_error")

    def test_spawning_a_nonexistent_command_raises(self):
        with self.assertRaises(FileNotFoundError):
            Client.spawn(command="boukensha-no-such-mcp-server-xyz")


if __name__ == "__main__":
    unittest.main()
