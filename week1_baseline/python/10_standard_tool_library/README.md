# Step 10 — A Standard Tool Library

Boukensha now ships with two built-in tool modules. Instead of manually registering tools, a real coding harness gives the agent a standard library of capabilities out of the box.

## What's New

### `boukensha.tools.FileSystem`

Sandboxed file operation tools. Registers automatically when `working_dir` is set:

| Tool | Description |
|------|-------------|
| `pwd` | Return the working directory |
| `list_directory` | List files at a path (default `.`) |
| `read_file` | Read a file's contents |
| `write_file` | Write (or create) a file |
| `delete_file` | Delete a file |
| `search_files` | **New** — grep for a regex pattern across the working tree, returns `path:line:content` matches |

All paths are **relative to the working directory**. Absolute paths and `..` traversals that escape the root are rejected with an error string.

### `boukensha.tools.Shell`

New module. Registers automatically when `working_dir` is set:

| Tool | Description |
|------|-------------|
| `run_command` | Run a shell command inside the working directory |

Commands run with a configurable timeout and an optional allow-list of permitted executables.

### New Keyword Arguments

```python
boukensha(
    task="player",
    working_dir="/my/project",      # Enable FileSystem + Shell
    allowed_commands=["ruby", "git"], # Restrict commands (nil = allow all)
    shell_timeout=30                 # Timeout in seconds
)
```

`allowed_commands=None` permits any executable. Pass an explicit list to lock the agent down:

```python
# Only allow ruby and git — rm, curl, etc. will be rejected
boukensha(
    task="player",
    working_dir="/my/project",
    allowed_commands=["ruby", "git"]
)
```

### Direct Registration

Both modules can be registered manually if you need finer control:

```python
from boukensha.tools import FileSystem, Shell

FileSystem.register(registry, working_dir="/my/project")
Shell.register(registry, working_dir="/my/project",
              timeout=10, allowed_commands=["ruby"])
```

## Run the Demo

```sh
python examples/example.py

# or via the global executable with working directory:
boukensha
```

Set `BOUKENSHA_PATH` to point to this step:

```sh
BOUKENSHA_PATH=~/Sites/boukensha/10_standard_tool_library boukensha
```
