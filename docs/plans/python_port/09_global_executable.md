# Python Port: Boukensha Step 09

**Status**: Auto-Generated Plan — Review and confirm before porting.

This plan was auto-generated based on the Ruby source structure.
Review the file structure, verify dependencies, and confirm this plan captures all porting tasks.

## Quick Summary

**Step**: 09
**Ruby Source**: week1_baseline/ruby/09_*/
**Python Target**: week1_baseline/python/09_*/
**Template**: week1_baseline/python/<PRIOR>_*/

This step builds on prior steps by:
- [x] Adding new module: `boukensha_loader.py` (resolves which step version to load)
- [x] Modifying: `pyproject.toml` to add console entry point for `boukensha` command
- [x] No changes to existing classes or exception handling
- [x] All code identical to Step 08 - this is purely a packaging/distribution wrapper

## Key Files for Step 09

**NO file porting needed** — Step 09 reuses Step 08 code unchanged.

**Only New File to Create**:
- [x] `src/boukensha/boukensha_loader.py` — Module that resolves which step version to load based on:
  1. `BOUKENSHA_PATH` environment variable (points to specific step directory)
  2. `~/.boukensharc` file (persistent step selection)
  3. Bundled default (uses the Step 08 version shipped with the package)

## Porting Strategy

### Files to Copy Unchanged (from Step 08)
All Step 08 files are copied verbatim:
- [x] ALL src/boukensha/*.py files
- [x] ALL src/boukensha/backends/*.py files
- [x] ALL src/boukensha/tasks/*.py files

### New Files to Create
- [x] `src/boukensha/boukensha_loader.py` (~80 lines)
  - Function: `resolve()` - determines which step's lib to load
  - Function: `load_and_start_repl()` - loads the resolved step and starts REPL
  - Follows Ruby logic: checks BOUKENSHA_PATH → ~/.boukensharc → bundled default

### Files to Modify
- [x] `pyproject.toml` - Add console script entry point for `boukensha` command
- [x] `bin/boukensha` - Wrapper script that invokes the Python loader
- [x] `README.md` - Document BOUKENSHA_PATH and ~/.boukensharc usage

## Dependency Analysis

**Prior Step Dependencies**:
- Uses all of Step 08 unchanged - no new dependencies

**New in This Step**:
- New module: `boukensha_loader` - handles version resolution
- New public function: `load_and_start_repl()` - entry point for CLI
- No new exceptions or classes

## Estimated Complexity

- **Number of files to create**: 1 (boukensha_loader.py)
- **Number of files to modify**: 3 (pyproject.toml, bin/boukensha, README.md)
- **Number of files to copy**: 20+ (all Step 08 files)
- **Estimated porting time**: 20-30 minutes
- **Complexity level**: LOW (straightforward wrapper; logic is identical to Ruby version)

## Translation Notes

Key patterns for boukensha_loader.py:
- Ruby `ENV.fetch("BOUKENSHA_PATH", nil)` → Python `os.environ.get("BOUKENSHA_PATH")`
- Ruby `File.expand_path()` → Python `os.path.expanduser()` + `os.path.abspath()`
- Ruby `File.exist?()` → Python `os.path.exists()` or `Path.exists()`
- Ruby `File.read()` → Python `Path.read_text()` or `open().read()`
- Ruby `abort()` → Python `sys.exit(1)` with error message to stderr
- Ruby string interpolation → Python f-strings

## Testing Plan

After porting:
1. [x] All imports work: `python -c "from boukensha.boukensha_loader import *"`
2. [x] Loader resolution works with BOUKENSHA_PATH env var
3. [x] Loader reads ~/.boukensharc correctly
4. [x] Bundled default (Step 08) loads when no overrides set
5. [x] CLI entry point works: `boukensha` command available globally
6. [x] REPL starts: `boukensha` without args
7. [x] Respects BOUKENSHA_PATH: `BOUKENSHA_PATH=../step08 boukensha`

## Common Pitfalls for Step 09

- **Path expansion**: Remember `~` expansion needs `os.path.expanduser()` 
- **Module importing**: Dynamically importing the loaded step's lib requires correct sys.path manipulation
- **Entry points**: pyproject.toml entry point must be exact: `[project.scripts] boukensha = "boukensha.boukensha_loader:load_and_start_repl"`
- **Error messages**: Match Ruby version exactly so users see consistent help text
- **File not found**: Both BOUKENSHA_PATH and ~/.boukensharc should fail gracefully with helpful errors

---

## Next Steps

1. Review this plan
2. Analyze Ruby source code structure
3. Map each Ruby file to Python equivalent
4. Document in plan details section
5. Get approval from user
6. Execute porting with confirmed plan

---

**IMPORTANT**: This is an auto-generated plan template.
Before porting, analyze the Ruby code and fill in the specific details about:
- What new classes/functionality is being added
- What files need to be created vs copied
- Any special translation requirements
- Testing considerations

Then confirm with user that the plan is complete and accurate.

