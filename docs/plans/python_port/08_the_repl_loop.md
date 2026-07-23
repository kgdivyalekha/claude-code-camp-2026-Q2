# Python Port: Boukensha Step 08

**Status**: Auto-Generated Plan — Review and confirm before porting.

This plan was auto-generated based on the Ruby source structure.
Review the file structure, verify dependencies, and confirm this plan captures all porting tasks.

## Quick Summary

**Step**: 08
**Ruby Source**: week1_baseline/ruby/08_*/
**Python Target**: week1_baseline/python/08_*/
**Template**: week1_baseline/python/<PRIOR>_*/

This step builds on prior steps by:
- [x] Adding new classes/modules: `Repl` class for interactive session loop, `VERSION` constant
- [x] Modifying existing classes: `Boukensha` module with new quiet/loud/debug methods and repl() method
- [x] No new exception handling changes
- [x] New public methods: `Boukensha.quiet!`, `Boukensha.loud!`, `Boukensha.quiet?`, `Boukensha.debug!`, `Boukensha.debug?`, `Boukensha.repl()`

## Ruby Files to Port

The following Ruby files need translation to Python:

- [ ] `examples/example.rb` → `src/boukensha/examples/example.py`
- [ ] `lib/boukensha.rb` → `src/boukensha/lib/boukensha.py`
- [ ] `lib/boukensha/agent.rb` → `src/boukensha/lib/boukensha/agent.py`
- [ ] `lib/boukensha/backends/anthropic.rb` → `src/boukensha/lib/boukensha/backends/anthropic.py`
- [ ] `lib/boukensha/backends/base.rb` → `src/boukensha/lib/boukensha/backends/base.py`
- [ ] `lib/boukensha/backends/gemini.rb` → `src/boukensha/lib/boukensha/backends/gemini.py`
- [ ] `lib/boukensha/backends/ollama.rb` → `src/boukensha/lib/boukensha/backends/ollama.py`
- [ ] `lib/boukensha/backends/ollama_cloud.rb` → `src/boukensha/lib/boukensha/backends/ollama_cloud.py`
- [ ] `lib/boukensha/backends/openai.rb` → `src/boukensha/lib/boukensha/backends/openai.py`
- [ ] `lib/boukensha/client.rb` → `src/boukensha/lib/boukensha/client.py`
- [ ] `lib/boukensha/config.rb` → `src/boukensha/lib/boukensha/config.py`
- [ ] `lib/boukensha/context.rb` → `src/boukensha/lib/boukensha/context.py`
- [ ] `lib/boukensha/errors.rb` → `src/boukensha/lib/boukensha/errors.py`
- [ ] `lib/boukensha/logger.rb` → `src/boukensha/lib/boukensha/logger.py`
- [ ] `lib/boukensha/message.rb` → `src/boukensha/lib/boukensha/message.py`
- [ ] `lib/boukensha/prompt_builder.rb` → `src/boukensha/lib/boukensha/prompt_builder.py`
- [ ] `lib/boukensha/registry.rb` → `src/boukensha/lib/boukensha/registry.py`
- [ ] `lib/boukensha/repl.rb` → `src/boukensha/lib/boukensha/repl.py`
- [ ] `lib/boukensha/run_dsl.rb` → `src/boukensha/lib/boukensha/run_dsl.py`
- [ ] `lib/boukensha/tasks/base.rb` → `src/boukensha/lib/boukensha/tasks/base.py`
- [ ] `lib/boukensha/tasks/player.rb` → `src/boukensha/lib/boukensha/tasks/player.py`
- [ ] `lib/boukensha/tool.rb` → `src/boukensha/lib/boukensha/tool.py`
- [ ] `lib/boukensha/version.rb` → `src/boukensha/lib/boukensha/version.py`

## Porting Strategy

### Files to Copy Unchanged (from prior step)
Copy all files from step 07 to step 08 unchanged - the entire previous implementation remains the same:
- [x] All src/boukensha/*.py files
- [x] All src/boukensha/backends/*.py files
- [x] All src/boukensha/tasks/*.py files
- [x] pyproject.toml (will update version only)
- [x] README.md (minimal updates)

### New Files to Create
- [x] `src/boukensha/version.py` - VERSION constant (simple, one line)
- [x] `src/boukensha/repl.py` - Repl class for interactive session loop (~140 lines)
  - `banner()` - Display startup banner with config/provider info
  - `start()` - Main loop that reads input, handles commands, runs agent turns
  - `run_turn()` - Execute one turn of the agent and print result
  - Handles commands: /help, /quiet, /loud, /clear, /exit, /quit

### Files to Modify
- [x] `src/boukensha/__init__.py` - Add version import, quiet/loud/debug methods, repl() method
- [x] `pyproject.toml` - Bump version to 0.8.0
- [x] `README.md` - Minimal update noting REPL capability

## Dependency Analysis

**Prior Step Dependencies**:
- Repl class depends on: Context, Registry, Agent, Logger, PromptBuilder, Client, Config
- All files from step 07 remain unchanged and are re-used
- No changes to exception handling or task system

**New in This Step**:
- New public class: `Repl` - interactive REPL session manager
- New module export: `VERSION` constant
- New module methods: `quiet!()`, `loud!()`, `quiet?()`, `debug!()`, `debug?()`, `repl()`

## Estimated Complexity

- **Number of files to create**: 2 (version.py, repl.py)
- **Number of files to modify**: 2 (boukensha/__init__.py, pyproject.toml)
- **Estimated porting time**: 20-30 minutes
- **Complexity level**: Low-to-Medium
  - Repl class is mostly UI/I/O with straightforward control flow
  - Pattern conversion is simpler than earlier steps (no complex data structures)

## Translation Notes

Key patterns for this step:
- Ruby `loop do` / `break unless` → Python `while True` / `if not ... break`
- Ruby `case input` with string matching → Python `if input == "" elif input == "/exit"`
- Ruby `$stdin.gets` → Python `input()` or `sys.stdin.readline()`
- Ruby `puts string` → Python `print(string)` 
- Ruby `$stdout.flush` → Python `sys.stdout.flush()`
- Ruby string interpolation `"#{var}"` → Python f-strings `f"{var}"`
- Ruby module class variables `@quiet` → Python class variables `Boukensha._quiet`

## Testing Plan

After porting:
1. [ ] All imports work: `python -c "from boukensha import *"`
2. [ ] Example runs: `./week1_baseline/bin/python/08`
3. [ ] Output is correct shape
4. [ ] No deprecation warnings

## Common Pitfalls for This Step

- **Input handling**: In Python, `input()` blocks for user input with no output prefix; use `print(PROMPT, end='', flush=True)` first
- **Module-level state**: Ruby uses instance variables on module; Python needs to use class variables or a singleton pattern
- **Interrupt handling**: Python's `KeyboardInterrupt` (Ctrl-C) needs explicit try/except; Ruby uses `rescue Interrupt`
- **String formatting**: Watch for proper indentation in multi-line strings (HELP and BANNER)
- **EOF handling**: Python's `input()` raises `EOFError` on EOF; Ruby's `gets` returns `nil`
- **Empty string check**: Remember to strip/chomp input before checking if empty

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

