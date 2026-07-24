# Python Port: Boukensha Step 10 — A Standard Tool Library

**Status**: Plan to be reviewed and confirmed before porting.

This plan outlines porting Step 10 from Ruby to Python. Step 10 adds three built-in tool modules that agents can use out-of-the-box.

## Quick Summary

**Step**: 10 (Standard Tool Library)
**Ruby Source**: week1_baseline/ruby/10_standard_tool_library/
**Python Target**: week1_baseline/python/10_standard_tool_library/
**Template**: week1_baseline/python/08_the_repl_loop/ (already ported)

### What's New in Step 10

Step 10 builds on step 08/09 (the global executable) by adding three tool modules:

1. **Boukensha::Tools::FileSystem** - Sandboxed file operations
   - `pwd` - return working directory
   - `list_directory` - list files at path
   - `read_file` - read file contents
   - `write_file` - write/create file
   - `delete_file` - delete file
   - `search_files` - grep pattern across working tree

2. **Boukensha::Tools::Shell** - Sandboxed shell command execution
   - `run_command` - execute shell command in working dir
   - Supports timeout and command allow-listing

3. **Boukensha::Tools::Mud** - CircleMUD gameplay tools
   - Registers tools when `mud_*` config is set
   - Depends on `mud_manager` gem (local path: week0_explore/mud_manager)

### Key Changes from Step 08

**Files to Copy Unchanged** (from step 08):
- All existing lib files remain unchanged
- pyproject.toml (version bump only)
- README.md (minimal updates)

**New Files to Create**:
- `src/boukensha/tools/__init__.py` - Package init
- `src/boukensha/tools/file_system.py` - FileSystem tool module (~150 lines)
- `src/boukensha/tools/shell.py` - Shell tool module (~80 lines)
- `src/boukensha/tools/mud.py` - Mud tool module (~200+ lines)

**Files to Modify**:
- `src/boukensha/__init__.py` - Import and expose tool modules
- `pyproject.toml` - Version bump to 0.10.0

## Porting Tasks

### Phase 1: Create Tool Modules

#### 1.1 FileSystem Tools (`src/boukensha/tools/file_system.py`)

**Purpose**: Register sandboxed file operation tools

**Key Components**:
- `FileSystem` class with `@staticmethod register(registry, working_dir)`
- Path resolution lambda that validates paths don't escape working_dir
- Tool registrations for: pwd, list_directory, read_file, write_file, delete_file, search_files
- Error handling for path traversal and file operation failures

**Translation Notes**:
- Ruby `lambda do |path| ... end` → Python `lambda path: ...` or `def resolve(path): ...`
- Ruby `File.expand_path()` → Python `os.path.abspath(os.path.normpath(...))`
- Ruby `File.readlines()` → Python `open().readlines()` or `pathlib.Path.read_text().splitlines()`
- Ruby regex matching `path.start_with?()` → Python `path.startswith()`
- Ruby `Dir.glob()` → Python `glob.glob()` or `pathlib.Path.glob()`

**Dependencies**:
- `os`, `pathlib`, `glob` (stdlib)
- Uses `registry.tool()` from Registry class

#### 1.2 Shell Tools (`src/boukensha/tools/shell.py`)

**Purpose**: Register sandboxed shell command execution tool

**Key Components**:
- `Shell` class with `@staticmethod register(registry, working_dir, allow_list=None, timeout=30)`
- `run_command` tool that executes shell commands in the working directory
- Timeout handling and command validation
- Process output capture (stdout + stderr)

**Translation Notes**:
- Ruby `Open3.popen3()` → Python `subprocess.run()` or `subprocess.Popen()`
- Ruby timeout handling → Python `subprocess.TimeoutExpired` exception
- Ruby `allow_list` validation → Python list membership check with `in` operator
- Process output handling with `subprocess.run(capture_output=True)`

**Dependencies**:
- `subprocess`, `os` (stdlib)
- Uses `registry.tool()` from Registry class

#### 1.3 Mud Tools (`src/boukensha/tools/mud.py`)

**Purpose**: Register CircleMUD gameplay tools (depends on mud_manager gem)

**Key Components**:
- `Mud` class with `@staticmethod register(registry, host, port, name, password)`
- Session management through MudManager::Session closure pattern
- Tools for: mud_connect, mud_disconnect, mud_status, look, examine, score, inventory, move
- Error handling for connection failures

**Translation Notes**:
- Ruby closure with instance variables → Python uses class variables or local scope
- Ruby MudManager::Session → Python mud_manager.Session (from imported gem)
- Ruby tool registration pattern remains similar
- Error messages match Ruby version

**Dependencies**:
- `mud_manager` gem (installed from week0_explore/mud_manager)
- Uses `registry.tool()` from Registry class

### Phase 2: Update Main Module

#### 2.1 Modify `src/boukensha/__init__.py`

**Changes**:
- Import tool modules: `from . import tools`
- Update version to 0.10.0 (in version.py)
- No changes to run() or repl() signatures needed - tool registration is optional

**Tool Registration Pattern** (existing in Ruby, translate as-is):
- Tools register conditionally: FileSystem/Shell register when `working_dir:` is set
- Mud tools register when `mud_*` config values are present
- Optional: allow tool registration via tools_fn parameter

### Phase 3: Update Metadata

#### 3.1 Modify `pyproject.toml`
- Bump version to 0.10.0
- Update dependencies (add mud_manager path dependency if needed for packaging)

#### 3.2 Update `README.md`
- Document the three tool modules
- Add usage examples for FileSystem, Shell, Mud tools
- Keep most content from Ruby version

## File Structure Checklist

```
week1_baseline/python/10_standard_tool_library/
├── src/boukensha/
│   ├── __init__.py (MODIFY - add tool imports)
│   ├── version.py (MODIFY - bump to 0.10.0)
│   ├── tools/ (NEW DIRECTORY)
│   │   ├── __init__.py (NEW)
│   │   ├── file_system.py (NEW)
│   │   ├── shell.py (NEW)
│   │   └── mud.py (NEW)
│   ├── agent.py (UNCHANGED from step 08)
│   ├── client.py (UNCHANGED)
│   ├── config.py (UNCHANGED)
│   ├── context.py (UNCHANGED)
│   ├── errors.py (UNCHANGED)
│   ├── logger.py (UNCHANGED)
│   ├── message.py (UNCHANGED)
│   ├── prompt_builder.py (UNCHANGED)
│   ├── registry.py (UNCHANGED)
│   ├── repl.py (UNCHANGED)
│   ├── run_dsl.py (UNCHANGED)
│   ├── tool.py (UNCHANGED)
│   ├── tasks/
│   │   ├── __init__.py (UNCHANGED)
│   │   ├── base.py (UNCHANGED)
│   │   └── player.py (UNCHANGED)
│   └── backends/ (UNCHANGED)
├── pyproject.toml (MODIFY - version)
├── README.md (MODIFY - tool docs)
└── examples/
    └── example.py (UNCHANGED or minimal update)
```

## Implementation Order

1. Create `src/boukensha/tools/__init__.py` - empty or with imports
2. Create `src/boukensha/tools/file_system.py` - start with this, most self-contained
3. Create `src/boukensha/tools/shell.py` - similar pattern to FileSystem
4. Create `src/boukensha/tools/mud.py` - depends on mud_manager import
5. Update `src/boukensha/__init__.py` - add tool module imports if needed
6. Update version to 0.10.0 in `src/boukensha/version.py`
7. Update `pyproject.toml` - version bump
8. Update `README.md` - document tools
9. Test with `python examples/example.py` or `./bin/python/10_standard_tool_library`

## Testing Plan

After porting:

1. [ ] All tool modules import cleanly:
   ```python
   from boukensha import tools
   from boukensha.tools import FileSystem, Shell, Mud
   ```

2. [ ] Example runs without errors:
   ```bash
   ./bin/python/10_standard_tool_library
   ```

3. [ ] Tool registration works in Boukensha.run():
   - With `working_dir` parameter, FileSystem/Shell tools auto-register
   - With MUD config, Mud tools auto-register

4. [ ] No deprecation warnings or import errors

## Common Pitfalls for Step 10

- **Path validation**: Ruby `start_with?()` is exact; Python `startswith()` is exact too. Ensure path escaping logic is identical.
- **File operations**: Use `pathlib.Path` for consistency with later Python versions
- **Process handling**: `subprocess.run()` has different defaults than Ruby's Open3; check capture_output and text mode
- **Timeout handling**: Python subprocess timeout raises exception, not returns error string; wrap appropriately
- **Mud_manager import**: Will fail if mud_manager not installed; may need conditional import with graceful fallback
- **Closure patterns**: Ruby uses instance variables in closures; Python lambda has different scoping rules

## Dependency Status

- [x] Step 08 (repl) Python version complete
- [ ] Step 10 tools need to be created
- [ ] mud_manager available locally at week0_explore/mud_manager

## Estimated Timeline

- **FileSystem module**: 30-40 minutes
- **Shell module**: 15-20 minutes
- **Mud module**: 30-40 minutes (more complex, depends on mud_manager)
- **Integration & testing**: 15-20 minutes
- **Total**: ~2-2.5 hours

## Notes

- Step 10 is backward compatible with step 08; all existing code works unchanged
- Tools are optional - if no working_dir or mud config, no tools register
- The same tool registration pattern from step 09 (if it exists) can be reused
- Focus on matching Ruby behavior exactly for path validation and error messages

---

**Next Steps**:
1. Review and approve this plan
2. Port tools modules in order (FileSystem → Shell → Mud)
3. Integrate and test
4. Commit changes with clear messages

