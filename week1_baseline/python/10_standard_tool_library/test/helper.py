"""Shared fixtures for the MCP test suite.

The MCP tests need a real MCP server to spawn. The mud-manager daemon in the
sibling week0_explore/mud_manager package is the one we have, so it plays the
role of "some MCP server" — the code under test knows nothing about it beyond
command/args/env.
"""

from __future__ import annotations

import contextlib
import os
import tempfile
import unittest
from pathlib import Path
from typing import Dict, Tuple

MUD_MANAGER_ROOT = Path(__file__).resolve().parents[4] / "week0_explore" / "mud_manager"
MUD_MANAGER_BIN = MUD_MANAGER_ROOT / "bin" / "mud-manager"
MUD_MANAGER_LIB = MUD_MANAGER_ROOT / "lib"


class McpTestHelper:
    def start_fake_mud(self):
        """Spawn a FakeMud for the daemon to talk to, or skip if the sibling
        package isn't checked out."""
        if not MUD_MANAGER_BIN.exists():
            raise unittest.SkipTest(f"mud_manager not found at {MUD_MANAGER_ROOT}")

        import subprocess

        script = (
            f'$LOAD_PATH.unshift({str(MUD_MANAGER_LIB)!r})\n'
            'require "mud_manager/fake_mud"\n'
            "fake = MudManager::FakeMud.new\n"
            "puts fake.port\n"
            "STDOUT.flush\n"
            "STDIN.gets\n"
            "fake.stop\n"
        )
        proc = subprocess.Popen(
            ["ruby", "-e", script],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        port = int(proc.stdout.readline().strip())
        return _FakeMudHandle(proc, port)

    def fake_mud_env(self, fake: "_FakeMudHandle") -> Dict[str, str]:
        """The credentials the daemon needs to reach the fake MUD."""
        return {
            "MUD_HOST": "127.0.0.1",
            "MUD_PORT": str(fake.port),
            "MUD_NAME": "Gandalf",
            "MUD_PASSWORD": "secret",
        }

    # command/args that spawn the daemon as an MCP server.
    mud_manager_command = "ruby"

    @property
    def mud_manager_args(self):
        return [str(MUD_MANAGER_BIN), "--mcp"]

    def new_registry(self):
        from boukensha.context import Context
        from boukensha.registry import Registry
        from boukensha.tasks.player import Player

        ctx = Context(task=Player, system="test")
        return ctx, Registry(ctx)

    @contextlib.contextmanager
    def config_from(self, yaml_text: str):
        """Build a Config from a settings.yaml written into a throwaway
        BOUKENSHA_DIR."""
        from boukensha.config import Config

        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "settings.yaml").write_text(yaml_text)
            old = os.environ.get("BOUKENSHA_DIR")
            os.environ["BOUKENSHA_DIR"] = tmpdir
            try:
                yield Config()
            finally:
                if old is None:
                    os.environ.pop("BOUKENSHA_DIR", None)
                else:
                    os.environ["BOUKENSHA_DIR"] = old


class _FakeMudHandle:
    def __init__(self, proc, port: int) -> None:
        self._proc = proc
        self.port = port

    def stop(self) -> None:
        try:
            self._proc.stdin.close()
        except Exception:
            pass
        self._proc.wait()
