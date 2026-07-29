# Step 10 x mud-manager (MCP path).
#
# boukensha has no MUD code at all. This points its generic MCP client at the
# `mud-manager` daemon and registers whatever tools the daemon advertises —
# exactly what the Ruby / Go / Rust / Java tracks do with their own SDKs.
# Nothing in boukensha.tools.mcp knows what a MUD is; the daemon is just a
# server, and this file is just a host.
#
# Note the names: the daemon advertises `look`, but we pass prefix="tbamud",
# so the agent sees `tbamud__look`. Prefixing is applied agent-side; the
# daemon never hears about it. In a real run that prefix comes from config.
#
#   # Self-contained smoke test — no API key, no live MUD (built-in fake MUD):
#   python3 examples/mcp_mud_demo.py --dry
#
#   # Full agent run — needs ANTHROPIC_API_KEY and a reachable MUD via
#   # mcp_servers: mud: in ~/.boukensha/settings.yaml:
#   python3 examples/mcp_mud_demo.py
#
# `mud-manager` is a ruby script (week0_explore/mud_manager) — there is no
# Python mud_manager package. The Python MCP client only cares that the
# daemon speaks stdio JSON-RPC, so it is spawned with `ruby <path> --mcp`
# exactly like every other language track would spawn it. For --dry mode,
# since there's no Python FakeMud either, a tiny ruby subprocess boots
# MudManager::FakeMud and reports its port back over stdout; this bit of
# process management is isolated here so it can be deleted without touching
# the MCP demo path if a Python mud_manager port ever exists.

import os
import subprocess
import sys
from pathlib import Path

import boukensha
from boukensha import tools as boukensha_tools

MUD_MANAGER_DIR = Path(__file__).resolve().parents[4] / "week0_explore" / "mud_manager"
DAEMON = MUD_MANAGER_DIR / "bin" / "mud-manager"

_FAKE_MUD_SCRIPT = """
$LOAD_PATH.unshift(ARGV[0])
require "mud_manager/fake_mud"
fake = MudManager::FakeMud.new
puts fake.port
STDOUT.flush
STDIN.gets  # blocks until the parent closes our stdin
fake.stop
"""


def _start_fake_mud() -> tuple[subprocess.Popen, int]:
    proc = subprocess.Popen(
        ["ruby", "-e", _FAKE_MUD_SCRIPT, str(MUD_MANAGER_DIR / "lib")],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    port = int(proc.stdout.readline().strip())
    return proc, port


def _stop_fake_mud(proc: subprocess.Popen) -> None:
    try:
        proc.stdin.close()
    except Exception:
        pass
    proc.wait()


def main() -> None:
    dry = "--dry" in sys.argv[1:]

    # --- credentials (env / boukensha config), or a fake MUD for --dry -----
    creds = {
        k: os.environ[k]
        for k in ("MUD_HOST", "MUD_PORT", "MUD_NAME", "MUD_PASSWORD")
        if k in os.environ
    }

    fake_proc = None
    if dry:
        fake_proc, port = _start_fake_mud()
        creds = {
            "MUD_HOST": "127.0.0.1",
            "MUD_PORT": str(port),
            "MUD_NAME": "Gandalf",
            "MUD_PASSWORD": "secret",
        }

    if dry:
        # Register the daemon's tools into a real boukensha Registry through
        # the generic MCP layer, then dispatch through it — the full agent
        # path, minus the LLM.
        from boukensha.context import Context
        from boukensha.registry import Registry

        ctx = Context(system="demo")
        registry = Registry(ctx)

        client = boukensha_tools.mcp.register(
            registry,
            command="ruby",
            args=[str(DAEMON), "--mcp"],
            env=creds,
            prefix="tbamud",
        )

        print(f"daemon: {client.server_info!r}")
        print(f"tools:  {len(ctx.tools)} — {', '.join(ctx.tools.keys())}")
        print()

        print(f"tbamud__look       => {registry.dispatch('tbamud__look', {})!r}")
        print(f"tbamud__attack orc => {registry.dispatch('tbamud__attack', {'target': 'orc'})!r}")
        print(f"bad cast           => {registry.dispatch('tbamud__cast_spell', {'spell': ''})!r}")

        client.close()
        if fake_proc is not None:
            _stop_fake_mud(fake_proc)
        print("\n[dry run OK — daemon + step 10 generic MCP layer working]")
        return

    # --- full agent run -----------------------------------------------------
    # Nothing to wire up: boukensha.run spawns whatever is in `mcp_servers:`
    # and registers its tools. There is no mode to select and no MUD
    # argument to pass, because the agent has no concept of a MUD. See
    # examples/example.py — at this point the two demos are the same
    # program.
    boukensha.run(
        task=(
            "Look at your surroundings, check your score, then look at the "
            "exits and tell me what you see."
        )
    )


if __name__ == "__main__":
    main()
