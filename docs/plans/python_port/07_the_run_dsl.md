# Python Port: Boukensha Step 07

**Status**: Auto-Generated Plan — Review and confirm before porting.

This plan was auto-generated based on the Ruby source structure.
Review the file structure, verify dependencies, and confirm this plan captures all porting tasks.

## Quick Summary

**Step**: 07
**Ruby Source**: week1_baseline/ruby/07_*/
**Python Target**: week1_baseline/python/07_*/
**Template**: week1_baseline/python/<PRIOR>_*/

This step builds on prior steps by:
- [ ] Adding new classes/modules (list them)
- [ ] Modifying existing classes (which ones?)
- [ ] Changing exception handling (what new exceptions?)
- [ ] Updating API/contract (new public methods?)

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
- [ ] `lib/boukensha/run_dsl.rb` → `src/boukensha/lib/boukensha/run_dsl.py`
- [ ] `lib/boukensha/tasks/base.rb` → `src/boukensha/lib/boukensha/tasks/base.py`
- [ ] `lib/boukensha/tasks/player.rb` → `src/boukensha/lib/boukensha/tasks/player.py`
- [ ] `lib/boukensha/tool.rb` → `src/boukensha/lib/boukensha/tool.py`

## Porting Strategy

### Files to Copy Unchanged (from prior step)
List any files that should be copied as-is from the previous Python step:
- [ ] src/boukensha/config.py
- [ ] src/boukensha/registry.py
- [ ] (add more)

### New Files to Create
- [ ] File 1: Description
- [ ] File 2: Description
- [ ] examples/example.py: Updated example

### Files to Modify
- [ ] src/boukensha/errors.py: Add new exceptions
- [ ] src/boukensha/__init__.py: Export new classes
- [ ] pyproject.toml: Bump version
- [ ] README.md: Document new functionality

## Dependency Analysis

**Prior Step Dependencies**:
- Depends on prior step for: (config, registry, backends, etc.)

**New in This Step**:
- New public classes: (list them)
- New exceptions: (list them)
- New modules: (list them)

## Estimated Complexity

- **Number of files to create**: ?
- **Number of files to modify**: ?
- **Estimated porting time**: 30 minutes
- **Complexity level**: Medium / High / Low

## Translation Notes

Key patterns to remember:
- Ruby symbols → Python strings
- Ruby blocks → Python functions/lambdas
- Net::HTTP → urllib.request
- rescue → except

## Testing Plan

After porting:
1. [ ] All imports work: `python -c "from boukensha import *"`
2. [ ] Example runs: `./week1_baseline/bin/python/07`
3. [ ] Output is correct shape
4. [ ] No deprecation warnings

## Common Pitfalls for This Step

(Add any known issues specific to this step)
- Watch for: ?
- Be careful with: ?
- Remember to: ?

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

