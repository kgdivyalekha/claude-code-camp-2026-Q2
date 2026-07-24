# Python Port: Boukensha Step 10 — A Standard Tool Library

**Status**: Plan to be reviewed and confirmed before porting.

This plan outlines porting Step 10 from Ruby to Python. Step 10 adds three built-in tool modules that agents can use out-of-the-box.

## Quick Summary

**Step**: 10 (Standard Tool Library)
**Ruby Source**: week1_baseline/ruby/10_standard_tool_library/
**Python Target**: week1_baseline/python/10_standard_tool_library/
**Template**: week1_baseline/python/08_the_repl_loop/ (already ported)

### What's New in Step 10

Step 10 builds on step 09 (the global executable) by adding two built-in tool modules:

1. **`boukensha.tools.FileSystem`** - Sandboxed file operations (6 tools)
   - `pwd` - return working directory
   - `list_directory` - list files at path (default: current)
   - `read_file` - read file contents
   - `write_file` - write/create file
   - `delete_file` - delete file
   - `search_files` - grep pattern across working tree

2. **`boukensha.tools.Shell`** - Sandboxed shell command execution (1 tool)
   - `run_command` - execute shell command in working directory
   - Supports timeout and command allow-listing for security

### Key Changes from Step 08

**Files to Copy Unchanged** (from step 08):
- All existing lib files remain unchanged
- pyproject.toml (version bump only)
- README.md (minimal updates)

**New Files to Create**:
- `src/boukensha/tools/__init__.py` - Package init with exports
- `src/boukensha/tools/file_system.py` - FileSystem tool module (6 tools)
- `src/boukensha/tools/shell.py` - Shell tool module (1 tool)

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
│   │   ├── __init__.py (NEW - exports FileSystem, Shell)
│   │   ├── file_system.py (NEW - 6 file operation tools)
│   │   └── shell.py (NEW - shell command execution)
│   ├── agent.py (UNCHANGED from step 09)
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
│   ├── tasks/ (UNCHANGED)
│   ├── backends/ (UNCHANGED)
│   └── boukensha_loader.py (UNCHANGED)
├── pyproject.toml (MODIFY - version to 0.10.0)
├── README.md (MODIFY - document tool modules)
├── examples/
│   └── example.py (MODIFY - show working_dir usage)
└── prompts/ (UNCHANGED)
```

## Implementation Order

1. Create `src/boukensha/tools/__init__.py` - package init with FileSystem, Shell exports
2. Create `src/boukensha/tools/file_system.py` - 6 file operation tools
3. Create `src/boukensha/tools/shell.py` - shell command execution tool
4. Update `src/boukensha/__init__.py` - import and expose tool modules
5. Update version to 0.10.0 in `src/boukensha/version.py`
6. Update `pyproject.toml` - version bump
7. Update `README.md` - document new tool modules and keyword arguments
8. Update `examples/example.py` - show tool usage with `working_dir` parameter
9. Test with `python examples/example.py` or global executable

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

- **Path validation**: Use `Path.resolve()` to get absolute path, then check if it's within working_dir using `is_relative_to()` or string prefix check
- **Path sandboxing**: Test edge cases: `/..`, `../../`, symlinks pointing outside, etc.
- **File operations**: Use `pathlib.Path` for all file I/O; handle UnicodeDecodeError for `read_file`
- **Regex search**: Use `re.compile()` and catch invalid regex patterns; handle large files gracefully
- **Process handling**: `subprocess.run()` with `shell=True` vs list of args; use `shell=True` for piped commands like `ls | grep`
- **Timeout handling**: `subprocess.TimeoutExpired` exception must be caught and return error string
- **Allow-list**: Parse command with `shlex.split()`, not regex; check first token (executable name)
- **Closure patterns**: Store `working_dir` etc. as instance variables on the class, not in lambda closures

## Dependency Status

- [x] Step 09 (Global Executable) copied as template
- [x] Step 08 (REPL Loop) infrastructure available
- [x] Registry and Tool classes from prior steps
- [x] All stdlib dependencies available (subprocess, pathlib, re, shlex)

## Estimated Timeline

- **FileSystem module**: 30-40 minutes (6 tools, path sandboxing logic)
- **Shell module**: 15-20 minutes (1 tool, timeout + allow-list)
- **Integration & testing**: 15-20 minutes
- **Total**: ~60-80 minutes (1-1.5 hours)

## Notes

- Step 10 is backward compatible with step 09; all existing code works unchanged
- Tools are **optional** — if no `working_dir` parameter, no tools register
- Tool modules follow the same pattern: `@staticmethod register(registry, **options)`
- Focus on matching Ruby behavior exactly for:
  - Path sandboxing and error messages
  - Process output and timeout handling
  - Allow-list validation

---

**Next Steps**:
1. Review and approve this plan
2. Port tools modules in order (FileSystem → Shell → Mud)
3. Integrate and test
4. Commit changes with clear messages

