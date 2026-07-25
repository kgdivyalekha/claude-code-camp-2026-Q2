# Step 10 — A Standard Tool Library

The standard tool library is **MCP**.

Boukensha ships **no tools of its own**. It is an MCP *host*: every tool the
agent can call comes from an MCP server declared in `settings.yaml`. Want
file access? Plug in a filesystem server. Want to play a MUD? Plug in
`mud-manager --mcp`. An agent with an empty `mcp_servers:` block can only
talk.

Python has no step-9 port (`09_global_executable` is gem/bin packaging with
no Python equivalent), so this step's package is a direct continuation of
`08_the_repl_loop`, absorbing the ruby history from steps 8 through 10 in one
increment — including *removing* two step-8 Python features that ruby itself
reverted in step 9 (see "What went away" below).

## What's new

### `boukensha.mcp.client.Client`

A minimal MCP-over-stdio client: spawn a server, handshake, `tools/list`,
`tools/call`. It is server-agnostic — `command` / `args` / `env` is the
standard stdio transport config, the same triple every MCP host uses.

### `boukensha.tools.mcp`

The only module left under `tools/`. Registers a server's discovered tools
into a registry, optionally scoping their names with a `prefix`.

```python
from boukensha import tools

tools.mcp.register(
    registry,
    command="mud-manager", args=["--mcp"],
    env={"MUD_HOST": "localhost"},
    prefix="tbamud",          # the daemon's `look` registers as `tbamud__look`
)
```

Prefixing is applied **client-side**: the server still sees `look` on the
wire. It exists so two servers can't silently clobber each other's names — a
collision raises `tools.mcp.CollisionError` and names the fix.

### `mcp_servers:` in `settings.yaml`

Adding a capability is a config edit, not a code change:

```yaml
mcp_servers:
  mud:
    command: mud-manager
    args:    [--mcp]
    prefix:  tbamud
    env:                     # a stdio server's credentials travel by environment
      MUD_HOST:     your.mud.host
      MUD_NAME:     Gandalf
      MUD_PASSWORD: secret

  filesystem:
    command:  npx
    args:     [-y, "@modelcontextprotocol/server-filesystem", /tmp]
    prefix:   fs
    required: false          # can't start? warn and carry on
```

| Key | Default | Meaning |
|-----|---------|---------|
| `command` | — | Executable to spawn. Resolved by the OS, so a relative path depends on your cwd — nothing hunts for a binary for you. |
| `args` | `[]` | Its argv. |
| `env` | `{}` | Extra environment. Servers inherit boukensha's environment; these keys override it. |
| `prefix` | none | Scopes discovered names (`fs` → `fs__read_file`). |
| `required` | `true` | `false` downgrades a failure to start into a warning. |

`Config.mcp_servers` parses this block into
`{name: {"command":, "args":, "env":, "prefix":, "required":}}` with those
defaults applied.

### `working_dir`

`run()` and `repl()` gain a `working_dir` keyword (defaults to
`os.getcwd()`), recorded on `Context.working_dir`. It is metadata only — it
registers nothing. An MCP server that touches the filesystem is rooted by its
own spawn `args`, not by this value.

### `Registry.tool_names()` / `RunDSL.tool_names()`

Return the names of every currently-registered tool. Used internally by
`tools.mcp.register_client` to detect name collisions before they happen.

### The REPL banner reports connected servers

`repl()`'s banner gained a `servers:` line, built from the
`{name: tool_count}` summary `_register_mcp_servers` returns — e.g.
`servers:   mud (6)`. Every tool the agent has came from one of these, so
this line doubles as "what can I actually do?".

## What went away

Two Python `08_the_repl_loop` features were **removed** in this step, because
ruby's own `09_global_executable` step removed them first and step 10 never
brought them back:

| Removed | Why |
|---|---|
| `Client.call()`'s friendly HTTP 401 message | A 401 now falls through to the generic non-2xx failure message like any other status. Retry behavior (401 was never retryable) is unchanged. |
| `Config._resolve_dir()`'s cwd-`.boukensha` fallback tier | Directory resolution is back to two tiers: `BOUKENSHA_DIR` env var, then `~/.boukensha`. |

Neither removal is a Python-side regression — both features were ported
faithfully from ruby step 8, then un-ported to match ruby step 9, which is
the state ruby step 10 (and this port) builds on.

Ruby's step 10 also documents removing several *ruby-only* built-in tools
(`Tools::FileSystem`, `Tools::Shell`, `Tools::Mud`) that never had a Python
port to begin with — there is nothing to remove here, since the Python track
never shipped built-in tools in the first place.

## Run the demo

```sh
# Offline, no API key, no live MUD — uses a fake MUD (via a small ruby
# subprocess; mud-manager itself is a ruby daemon in every language track):
python3 examples/mcp_mud_demo.py --dry

# Full run — needs ANTHROPIC_API_KEY and an mcp_servers: mud entry.
# Launch from the repo root so the example config's relative command path
# resolves, or use the launcher below:
BOUKENSHA_DIR=.boukensha python3 week1_baseline/python/10_standard_tool_library/examples/example.py

# or via the launcher script:
./week1_baseline/bin/python/10_standard_tool_library
```

## The `boukensha` command

`pip install -e .` also installs a `boukensha` console script into the active
venv (`[project.scripts]` in `pyproject.toml`, entry point
`boukensha.cli:main`) — the Python analogue of ruby's gem-installed
`bin/boukensha`. It takes no arguments and just calls `boukensha.repl()`, so
config resolution is the same as everywhere else in this step
(`BOUKENSHA_DIR` env var, else `~/.boukensha`):

```sh
source venv/bin/activate      # from repo root
pip install -e week1_baseline/python/10_standard_tool_library
BOUKENSHA_DIR=.boukensha boukensha
```

This is a Python venv script, unrelated to (and non-conflicting with) any
Ruby `boukensha` gem executable on your `PATH` — it only exists while the
venv is active. There is no Python equivalent of ruby's `~/.boukensharc` /
`boukensha_loader.rb` step-switching mechanism (see "Technical
Considerations" below) — which Python step runs is determined by which
package you `pip install -e`, not by an rc file.

## Tests

```sh
python3 -m unittest discover -s test -t .
```

The `-t .` matters: without an explicit top-level directory, `unittest`
discover imports `test/*.py` as top-level modules instead of as the `test`
package, and `from .helper import McpTestHelper`'s relative import fails.

MCP client/tool-registration tests spawn the real `mud-manager` daemon from
the sibling `week0_explore/mud_manager` checkout against its own built-in
fake MUD; they are skipped automatically if that checkout is absent. No test
in this suite requires a paid provider API call.

## Technical Considerations

These are observations, not bugs to fix in this step — preserving them here
so later layers don't have to rediscover them:

- Servers spawn **eagerly** at boot: every `mcp_servers:` entry costs a
  subprocess and a handshake even if the LLM never calls one of its tools.
  Fine at a couple of servers; revisit past that.
- Non-text MCP content blocks (images, embedded resources) are dropped
  rather than rendered — they yield an empty string, not an exception. No
  MUD tool can hit this.
- Every backend still advertises every listed parameter as required, which
  is wrong for third-party servers with genuinely optional params. Fixing it
  means plumbing `inputSchema["required"]` through `boukensha.tool.Tool`,
  which touches every backend's payload builder.
- There is no Python equivalent of ruby's `~/.boukensharc` /
  `boukensha_loader.rb` — Python steps are selected by which package is
  `pip install -e`'d, not by an rc file pointing a shared executable at a
  step directory. This step (and Python generally) has no
  `09_global_executable` concept to reconcile with.
