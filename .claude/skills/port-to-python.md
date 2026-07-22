---
name: port-to-python
description: Universal guide for porting any Ruby step to Python with automated execution
---

# Universal Ruby-to-Python Porting Skill

This skill automates the process of porting any Ruby step to Python. Use it for any step in the Boukensha baseline (04_api_client, 05_agent_loop, etc.).

## Quick Start

### Usage
```
/port-to-python <step_number>
```

Examples:
```
/port-to-python 04
/port-to-python 05
/port-to-python 06
```

### One Command to Start
```bash
./.claude/skills/port-to-python.sh <step_number>
```

This runs the automated porting workflow with **plan generation and confirmation**:
1. ✅ Validates Ruby source exists
2. ✅ **Checks for existing plan or auto-generates one**
3. ✅ **Shows plan for your review and approval**
4. ✅ **Gets your confirmation before proceeding**
5. ✅ Copies Python template from prior step
6. ✅ Generates file checklist from confirmed plan
7. ✅ Provides step-by-step guidance

---

## Plan Generation & Confirmation Workflow

### ✨ New Feature: Automatic Plan Generation

If a plan document doesn't exist for the step you're porting, the script will:

1. **Analyze** the Ruby source structure
2. **Generate** a plan template automatically
3. **Show** the plan for your review
4. **Allow** you to edit the plan (optional)
5. **Request** your confirmation before proceeding

### How It Works

```bash
# Run the script
./.claude/skills/port-to-python.sh 05

# If plan doesn't exist:
# → Script generates plan/05_agent_loop.md
# → Shows preview of generated plan
# → Offers options to view/edit/confirm/abort
# → Waits for your confirmation

# If plan exists:
# → Shows existing plan for review
# → Offers options to view/edit/confirm/abort
# → Waits for your confirmation
```

### Generated Plan Includes

- **Quick Summary**: What's being added in this step
- **Ruby Files List**: All files to translate
- **Porting Strategy**: Files to copy, create, modify
- **Dependency Analysis**: What this step depends on
- **Estimated Complexity**: Time & effort required
- **Translation Notes**: Key patterns to remember
- **Testing Plan**: Verification checklist
- **Common Pitfalls**: Known issues specific to step

### Confirming the Plan

During the confirmation phase, you can:

```
❓ Do you want to:
  1) View full plan (less command)
  2) Edit plan in editor
  3) Continue with current plan
  4) Abort and fix plan manually

Choice (1-4): _
```

**Option 1**: Read the full plan before confirming  
**Option 2**: Make changes to the plan in your editor  
**Option 3**: Accept the plan and continue with setup  
**Option 4**: Stop and fix the plan manually later  

### Why Plan Confirmation?

This approach ensures:
- ✅ You understand what will be ported
- ✅ You can add step-specific notes
- ✅ You catch missing pieces before starting
- ✅ Documentation is always up-to-date
- ✅ No surprises during porting

---

## Directory Structure

```
week1_baseline/
  ruby/
    00_config/           # Step 0: Config & Tasks
    01_struct_skeleton/  # Step 1: + Tool, Message, Context
    02_the_registry/     # Step 2: + Registry, UnknownToolError
    03_prompt_builder/   # Step 3: + PromptBuilder, Backends
    04_api_client/       # Step 4: + Client (HTTP)
    05_agent_loop/       # Step 5: + Agent (tool calling)
    # More steps...
  
  python/
    00_config/           # Python port of step 0
    01_struct_skeleton/  # Python port of step 1
    02_the_registry/     # Python port of step 2
    03_prompt_builder/   # Python port of step 3
    04_api_client/       # Python port of step 4 (to be ported)
    # More ports follow...

docs/
  plans/
    python_port/
      00_config.md           # Porting plan for step 0
      01_struct_skeleton.md  # Porting plan for step 1
      02_the_registry.md     # Porting plan for step 2
      03_prompt_builder.md   # Porting plan for step 3
      04_api_client.md       # Porting plan for step 4
      05_agent_loop.md       # Porting plan for step 5
      # Plans for all steps
```

---

## The Porting Workflow

### Phase 1: Setup (Automated)
```bash
# 1. Validate Ruby source exists
# 2. Copy latest Python step as template
# 3. Read porting plan
# 4. Generate checklist
```

### Phase 2: Port Files (Manual with Guidance)
For each file in the plan:
1. Read Ruby source file
2. Read Python template (if copying from prior step)
3. Apply porting patterns
4. Update exports and configs

### Phase 3: Test & Verify (Automated)
```bash
# 1. Install package
# 2. Run example
# 3. Verify imports
# 4. Check output shape
```

---

## Ruby → Python Translation Patterns

### Imports & Requires
```ruby
require "lib"
require_relative "../lib/boukensha"
```
→
```python
import lib
from ..lib import boukensha
```

### Symbols vs Strings
```ruby
:symbol
hash[:key]
msg.role == :user
```
→
```python
"symbol"
dict.get("key")
msg.role == "user"
```

### Constants & Class Variables
```ruby
CONSTANT = 42
attr_reader :var

class Foo
  def self.class_method
  end
end
```
→
```python
CONSTANT = 42
@property
def var(self): ...

class Foo:
    @classmethod
    def class_method(cls):
        pass
```

### Methods & Blocks
```ruby
def method(arg)
  arg * 2
end

[1,2,3].map { |x| x * 2 }
[1,2,3].each { |x| puts x }
hash.fetch(:key)
```
→
```python
def method(arg):
    return arg * 2

[x * 2 for x in [1, 2, 3]]
for x in [1, 2, 3]:
    print(x)
dict.get("key")
```

### Exception Handling
```ruby
begin
  dangerous_call
rescue StandardError => e
  handle(e)
rescue *ERRORS => e
  retry
end
```
→
```python
try:
    dangerous_call()
except StandardError as e:
    handle(e)
except tuple(ERRORS) as e:
    retry()
```

### File I/O
```ruby
File.read(path)
File.exist?(path)
File.write(path, content)
Dir.entries(path)
```
→
```python
Path(path).read_text()
Path(path).exists()
Path(path).write_text(content)
os.listdir(path)
```

### Data Structures
```ruby
arr = [1, 2, 3]
hash = { key: "value", :symbol => 1 }
struct = Struct.new(:field)
```
→
```python
arr = [1, 2, 3]
dict = {"key": "value", "symbol": 1}
@dataclass
class Struct:
    field: Any
```

### String Interpolation
```ruby
"Value is #{var}, item #{item.name}"
%w[one two three]
```
→
```python
f"Value is {var}, item {item.name}"
["one", "two", "three"]
```

### Inheritance & Mixins
```ruby
class Child < Parent
  def method
    super
  end
end
```
→
```python
class Child(Parent):
    def method(self):
        return super().method()
```

### Type Hints (Python-specific)
```python
from typing import Dict, List, Optional, Any

def method(arg: str, items: List[int]) -> Optional[Dict[str, Any]]:
    pass
```

---

## Step-by-Step Porting Process

### Step 1: Copy Template
```bash
cp -r week1_baseline/python/<PRIOR_STEP> week1_baseline/python/<NEW_STEP>
cd week1_baseline/python/<NEW_STEP>
```

**Why**: Reuse all prior dependencies (config, structs, registry, builders, backends, etc.)

### Step 2: Read the Plan
```bash
open docs/plans/python_port/<NEW_STEP>.md
```

Key sections:
- **Decisions**: Why this step exists, design choices
- **Target Structure**: What files to create/modify
- **Porting Plan**: File-by-file translation guide with Ruby ↔ Python examples
- **Key Translations**: Language-specific idiom mappings
- **Testing Strategy**: How to verify the port works
- **Common Pitfalls**: Mistakes to avoid

### Step 3: Create New Files
For each new file mentioned in the plan:
1. Create the Python stub: `src/boukensha/path/to/file.py`
2. Follow the plan's code examples
3. Use type hints
4. Add docstrings for classes/methods

### Step 4: Modify Existing Files
For files carried forward from prior steps:
1. Copy them as-is (they're already ported)
2. Only add new exceptions/exports to `errors.py` and `__init__.py`

### Step 5: Update Package Metadata
- Bump version in `pyproject.toml` (0.3.0 → 0.4.0 → 0.5.0 → ...)
- Update `README.md` with new classes/usage
- Ensure `examples/example.py` uses new functionality

### Step 6: Test the Port
```bash
source venv/bin/activate
pip install -e week1_baseline/python/<NEW_STEP>
./week1_baseline/bin/python/<NEW_STEP>
```

Expected: Script runs successfully, produces valid output

### Step 7: Create/Update Executable
Ensure `week1_baseline/bin/python/<NEW_STEP>` exists and is executable:
```bash
#!/bin/bash
cd "$(dirname "$0")/../../python/<NEW_STEP>"
source ../../venv/bin/activate
python examples/example.py
```

---

## Common Ruby Patterns & Python Equivalents

### Handling Nil/None
| Ruby | Python |
|------|--------|
| `value || default` | `value or default` |
| `value&.method` | `value.method if value` or `getattr(value, 'method', None)` |
| `raise if value.nil?` | `if not value: raise ...` |

### Method Definitions
| Ruby | Python |
|------|--------|
| `def method; end` | `def method(): pass` |
| `def method(arg = default)` | `def method(arg=default):` |
| `def method(*args)` | `def method(*args):` |
| `def method(key:)` | `def method(key):` |
| `private def foo` | `def _foo(self):` |

### Iteration & Blocks
| Ruby | Python |
|------|--------|
| `[1,2].map { \|x\| x*2 }` | `[x*2 for x in [1,2]]` |
| `hash.each { \|k,v\| ... }` | `for k, v in dict.items(): ...` |
| `(1..10).each { \|i\| ... }` | `for i in range(1, 11): ...` |
| `loop { break if done }` | `while True: ... ; break` |

### Error Handling
| Ruby | Python |
|------|--------|
| `begin...rescue...end` | `try...except...` |
| `raise ArgumentError, "msg"` | `raise ValueError("msg")` |
| `ensure` | `finally` |

### HTTP/Network
| Ruby | Python |
|------|--------|
| `Net::HTTP` | `urllib.request` (stdlib) |
| `URI(url)` | `urllib.parse.urlparse(url)` |
| `JSON.parse(str)` | `json.loads(str)` |
| `JSON.generate(obj)` | `json.dumps(obj)` |

---

## File-by-File Checklist Template

Use this for every porting task:

```markdown
## Step <N> Porting Checklist

### Setup
- [ ] Copied step <N-1> to step <N>
- [ ] Read plan document: docs/plans/python_port/<N>_*.md

### New Files
- [ ] File 1: `src/boukensha/path/file1.py`
- [ ] File 2: `src/boukensha/path/file2.py`
- [ ] File 3: `examples/example.py`

### Modified Files
- [ ] `src/boukensha/errors.py` — added new exceptions
- [ ] `src/boukensha/__init__.py` — updated exports
- [ ] `pyproject.toml` — version bump
- [ ] `README.md` — new usage examples

### Verification
- [ ] `pip install -e week1_baseline/python/<N>` succeeds
- [ ] All imports work: `python -c "from boukensha import ..."` 
- [ ] Example runs: `./week1_baseline/bin/python/<N>`
- [ ] Output is valid JSON (for API steps) or correct shape
- [ ] No DeprecationWarnings or ImportErrors
- [ ] Code follows project style (type hints, docstrings)

### Commit
- [ ] Changes staged: `git add week1_baseline/python/<N>`
- [ ] Plan added: `git add docs/plans/python_port/<N>_*.md`
- [ ] Commit message: "Port step <N> to Python"
```

---

## Automated Porting Script

The script at `.claude/skills/port-to-python.sh` automates setup and verification:

```bash
./.claude/skills/port-to-python.sh 04
```

What it does:
1. Validates Ruby source: `week1_baseline/ruby/04_*`
2. Validates Python template: `week1_baseline/python/03_*`
3. Creates target: `week1_baseline/python/04_*`
4. Copies all files from step 3
5. Lists files to create (from plan)
6. Lists files to modify (from plan)
7. Tests imports
8. Runs example

---

## Debugging Common Issues

### ImportError: cannot import name 'X'
**Cause**: New class not exported from `__init__.py`
**Fix**: Add to `src/boukensha/__init__.py`:
```python
from .module import ClassName  # noqa: F401
```

### ModuleNotFoundError: No module named 'boukensha'
**Cause**: Package not installed in venv
**Fix**: 
```bash
source venv/bin/activate
pip install -e week1_baseline/python/<STEP>
```

### TypeError: method() takes 1 positional argument but 2 were given
**Cause**: Forgot `self` parameter or called as classmethod
**Fix**: Add `self` parameter, or mark with `@classmethod` if class method

### AttributeError: 'X' object has no attribute 'Y'
**Cause**: Attribute not set in `__init__` or typo
**Fix**: Check `__init__` sets all attributes; use `self.Y` not `@Y`

### SyntaxError on `from __future__ import annotations`
**Cause**: Line not at top of file
**Fix**: Move to line 1 (before all other imports)

---

## Version Bumping Strategy

Each step increments the patch or minor version:

```
Step 0: 0.0.1  (initial config)
Step 1: 0.1.0  (structs added, minor bump)
Step 2: 0.2.0  (registry added, minor bump)
Step 3: 0.3.0  (builder + backends, minor bump)
Step 4: 0.4.0  (client added, minor bump)
Step 5: 0.5.0  (agent loop, minor bump)
```

Update in `pyproject.toml`:
```toml
[project]
version = "0.4.0"  # Bump this
```

---

## Testing Strategy for Each Step

### Unit Tests
- New exceptions are catchable and have descriptive messages
- New classes initialize without errors
- Core methods return expected types
- Edge cases handled (empty lists, None values, etc.)

### Integration Tests
- Example script runs without errors
- Output format is correct (JSON for APIs, dict for agents)
- All imports from `boukensha` work
- Backward compatibility maintained (prior step classes still work)

### Smoke Tests
```bash
source venv/bin/activate
pip install -e week1_baseline/python/<STEP>
python -c "from boukensha import *; print('OK')"
./week1_baseline/bin/python/<STEP>
```

---

## Tips for Success

### 1. Follow the Plan Exactly
The plan documents have been carefully designed. If you deviate, you'll hit the same pitfalls others discovered. Read the "Common Pitfalls" section.

### 2. Copy First, Modify Second
Always copy the prior step first. Don't try to merge Ruby concepts directly—use the template structure as a guide.

### 3. Use Type Hints
Python's type hints are optional but help catch bugs early:
```python
def method(arg: str, count: int) -> Dict[str, Any]:
    pass
```

### 4. Document Why, Not What
Comments should explain WHY a design choice was made, not WHAT the code does:
```python
# Good: Explains a non-obvious decision
# Use string keys instead of symbols—yaml.safe_load() only produces strings

# Bad: Just repeats the code
# Convert role to string
role_str = msg.role.to_s
```

### 5. Test Before Committing
Run the example and verify output before committing. A passing example beats a passing test suite.

### 6. Keep Ruby & Python in Sync
When Ruby code changes (bug fix, new feature), port that change to Python too. Use:
```bash
git diff week1_baseline/ruby/<STEP> | grep "^[+-]"
```

---

## Step Dependency Chain

```
Step 4 (Client) 
  ├─ uses: Step 3 (PromptBuilder, Backends)
  ├─ uses: Step 2 (Registry, UnknownToolError)
  ├─ uses: Step 1 (Tool, Message, Context)
  └─ uses: Step 0 (Config, Tasks)

Step 5 (Agent Loop)
  ├─ uses: Step 4 (Client, ApiError)
  ├─ uses: Step 3 (PromptBuilder, Backends)
  ├─ uses: Step 2 (Registry)
  ├─ uses: Step 1 (Structs)
  └─ uses: Step 0 (Config, Tasks)
```

**Key**: When porting Step N, copy all files from Step N-1 unchanged. Only add new files and modify exports.

---

## Next Steps After Porting

1. **Commit the port**
   ```bash
   git add week1_baseline/python/<STEP>
   git add docs/plans/python_port/<STEP>_*.md
   git commit -m "Port step <STEP> to Python"
   ```

2. **Tag the version** (optional)
   ```bash
   git tag -a v0.<STEP>.0 -m "Step <STEP> complete"
   ```

3. **Update main CLAUDE.md** (if you have one)
   - Add entry: "Step <STEP>: <Description>"
   - Link to plan: `docs/plans/python_port/<STEP>_*.md`

4. **Port next step** (when ready)
   ```bash
   /port-to-python <NEXT_STEP>
   ```

---

## References & Resources

- **Ruby baseline**: `week1_baseline/ruby/`
- **Python ports**: `week1_baseline/python/`
- **Porting plans**: `docs/plans/python_port/`
- **This skill**: `.claude/skills/port-to-python.md`
- **Automation script**: `.claude/skills/port-to-python.sh`
- **Python docs**: https://docs.python.org/3/
- **Ruby docs**: https://docs.ruby-lang.org/en/

---

## When to Use This Skill

Use `/port-to-python <STEP>` when:
- ✅ You have a Ruby step that needs porting
- ✅ The previous Python step is complete
- ✅ You want automated setup and verification
- ✅ You need guidance on language-specific patterns

Use the plan document (`docs/plans/python_port/<STEP>.md`) for:
- ✅ Detailed file-by-file translation
- ✅ Code examples (Ruby ↔ Python)
- ✅ Design decisions and rationale
- ✅ Testing strategy and expected output

Use the script (`.claude/skills/port-to-python.sh`) for:
- ✅ Automated template setup
- ✅ File listing and checklist generation
- ✅ Quick verification tests
- ✅ Dependency validation
