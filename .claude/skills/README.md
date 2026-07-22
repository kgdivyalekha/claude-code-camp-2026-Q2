# Boukensha Porting Skills

This directory contains reusable skills and automation scripts for porting Ruby code to Python.

## Available Skills

### 1. **port-to-python** (Universal Porting Guide)
**File**: `port-to-python.md`

The master guide for porting any Ruby step to Python. Includes:
- Ruby → Python translation patterns
- Step-by-step porting workflow
- File checklist templates
- Common pitfalls & solutions
- Testing strategies
- Dependency chain reference

**Usage in Claude Code**:
```
/port-to-python
```

Then read the comprehensive guide for your specific step.

---

### 2. **port-to-python.sh** (Automated Setup Script with Plan Confirmation)
**File**: `port-to-python.sh`

Automates the setup phase of porting **with plan generation and user confirmation**:
- **Auto-generates** plan if one doesn't exist
- **Shows** plan for your review and approval
- **Gets confirmation** before proceeding
- Validates Ruby source exists
- Validates Python template (prior step) exists
- Copies template to new step
- Generates file checklist from plan
- Checks environment (venv, pip, installations)
- Provides next steps checklist

**Usage**:
```bash
./.claude/skills/port-to-python.sh 04
./.claude/skills/port-to-python.sh 05
```

**Workflow**:
1. ✓ Generates/retrieves plan
2. ✓ Shows plan for review
3. ✓ **Asks for confirmation** (new!)
4. ✓ Validates all prerequisites
5. ✓ Sets up Python target directory
6. ✓ Provides step-by-step next steps

**Output**:
- ✓ Auto-generated plan (if needed)
- ✓ Plan review options (view/edit/confirm/abort)
- ✓ User confirmation requirement
- ✓ Validated prerequisites
- ✓ Ready-to-work Python target
- ✓ Helpful commands and resources

---

## Quick Start: Port Any Step

### One-Minute Setup
```bash
# 1. Run the setup script
./.claude/skills/port-to-python.sh 04

# 2. Follow the printed guidance

# 3. Read the detailed plan
open docs/plans/python_port/04_api_client.md

# 4. Port files following plan examples

# 5. Test
source venv/bin/activate
pip install -e week1_baseline/python/04
./week1_baseline/bin/python/04
```

### Complete Workflow

1. **SETUP** (automated)
   ```bash
   ./.claude/skills/port-to-python.sh <STEP>
   ```
   - Validates Ruby source ✓
   - Copies Python template ✓
   - Creates checklist ✓

2. **PORT** (manual with guidance)
   - Read plan: `docs/plans/python_port/<STEP>.md`
   - Follow file-by-file translation examples
   - Create new files, modify exports
   - Use patterns from `port-to-python.md`

3. **TEST** (automated + manual)
   ```bash
   source venv/bin/activate
   pip install -e week1_baseline/python/<STEP>
   ./week1_baseline/bin/python/<STEP>
   ```
   - Verify imports work
   - Verify example output
   - Verify no warnings

4. **COMMIT**
   ```bash
   git add week1_baseline/python/<STEP>
   git commit -m "Port step <STEP> to Python"
   ```

---

## New: Plan Generation & Confirmation

### ✨ Automatic Plan Generation

Starting now, the script can **auto-generate** a plan if one doesn't exist!

**When you run**:
```bash
./.claude/skills/port-to-python.sh 05
```

**The script**:
1. Checks if `docs/plans/python_port/05_*.md` exists
2. If NOT, generates a template based on Ruby source
3. Shows you the plan for review
4. Offers options: view full plan / edit / confirm / abort
5. **Waits for your confirmation** before proceeding

### Generated Plan Includes

✓ Ruby files to port  
✓ Python files to create/modify  
✓ Dependency analysis  
✓ Porting strategy  
✓ Testing checklist  
✓ Common pitfalls  

### Why This Matters

- Ensures you understand what will be ported
- Catches missing pieces before starting
- Documents the plan automatically
- Prevents surprises during porting
- Makes porting repeatable and auditable

---

## Understanding the Porting Process

### Directory Structure
```
week1_baseline/
  ruby/
    00_config/
    01_struct_skeleton/
    02_the_registry/
    03_prompt_builder/
    04_api_client/       ← Your source step
  
  python/
    00_config/
    01_struct_skeleton/
    02_the_registry/
    03_prompt_builder/   ← Your template
    04_api_client/       ← Your target (to be created)

docs/plans/python_port/
  04_api_client.md       ← Your detailed guide
```

### The Workflow
```
Ruby source (04_api_client)
        ↓ (read & translate)
Template (03_prompt_builder copied to 04_api_client)
        ↓ (modify with new code)
Python port (04_api_client - complete)
        ↓ (test)
Example runs successfully
```

### Key Principle
**Always copy the prior Python step as a template.** This ensures:
- ✓ All dependencies are included
- ✓ Project structure is consistent
- ✓ No file is accidentally omitted
- ✓ Configuration is correct (pyproject.toml, imports, etc.)

---

## Ruby → Python Quick Reference

### Imports
```ruby
require "net/http"
require_relative "../lib/boukensha"
```
→
```python
import urllib.request
from ..lib import boukensha
```

### Symbols & Hashes
```ruby
:symbol
{ key: "value", :other => 1 }
msg.role == :user
hash[:key]
```
→
```python
"symbol"
{"key": "value", "other": 1}
msg.role == "user"
dict.get("key")
```

### Methods & Blocks
```ruby
def method(arg)
  [1,2,3].map { |x| x * 2 }
end
```
→
```python
def method(arg: int) -> List[int]:
    return [x * 2 for x in [1, 2, 3]]
```

### Exceptions
```ruby
begin
  dangerous()
rescue StandardError => e
  handle(e)
end
```
→
```python
try:
    dangerous()
except StandardError as e:
    handle(e)
```

### File I/O
```ruby
File.read(path)
File.exist?(path)
Dir.entries(dir)
```
→
```python
Path(path).read_text()
Path(path).exists()
os.listdir(dir)
```

### Type Hints (Python-specific)
```python
from typing import Dict, List, Optional

def method(name: str, items: List[int]) -> Optional[Dict[str, Any]]:
    pass
```

See `port-to-python.md` for comprehensive pattern list.

---

## Common Porting Tasks

### Task: Add New Exception
**In Ruby** (`lib/boukensha/errors.rb`):
```ruby
class ApiError < StandardError; end
```

**In Python** (`src/boukensha/errors.py`):
```python
class ApiError(Exception):
    """Raised when API request fails."""
    pass
```

Then export it:
```python
# src/boukensha/__init__.py
from .errors import ApiError  # noqa: F401
```

### Task: Add New Class
**Follow plan template**, e.g., for `Client`:

1. Create file: `src/boukensha/client.py`
2. Implement class following Ruby source & plan examples
3. Add type hints
4. Export from `__init__.py`
5. Test: `python -c "from boukensha import Client; print(Client)"`

### Task: Copy Unchanged File
Files from prior steps don't need translation—copy as-is:

```bash
# Copy Registry from 02_the_registry
cp week1_baseline/python/02_the_registry/src/boukensha/registry.py \
   week1_baseline/python/03_prompt_builder/src/boukensha/registry.py
```

### Task: Update Package Version
In `pyproject.toml`:
```toml
[project]
version = "0.4.0"  # was 0.3.0, now 0.4.0
```

### Task: Create Example Script
`examples/example.py` should:
- Import from `boukensha`
- Use Config to load settings
- Create Context with task
- Register tools via Registry
- Use new classes (Client, Agent, etc.)
- Run and print output

---

## Debugging Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `ImportError: cannot import name 'X'` | Not exported from `__init__.py` | Add `from .module import X` |
| `ModuleNotFoundError: boukensha` | Package not installed | `pip install -e week1_baseline/python/<STEP>` |
| `TypeError: method() takes 1 positional argument but 2 were given` | Missing `self` parameter | Add `self` to method signature |
| `NameError: name 'var' is not defined` | Attribute not set in `__init__` | Initialize in `self.__init__()` |
| `AttributeError: 'str' object has no attribute 'foo'` | Type error in translation | Check Ruby→Python type mapping |
| `json.JSONDecodeError` | Invalid JSON response | Check API response format |
| `FileNotFoundError: cert.pem` | Hardcoded cert path | Use `ssl.create_default_context()` |

See `port-to-python.md` for comprehensive debugging guide.

---

## Step-by-Step Example: Port Step 04

### Step 1: Setup
```bash
./.claude/skills/port-to-python.sh 04

# Output:
# ✓ Ruby source found
# ✓ Python template found (03_prompt_builder)
# ✓ Plan document found (04_api_client.md)
# → Next steps listed
```

### Step 2: Read Plan
```bash
cat docs/plans/python_port/04_api_client.md | head -100
```

Key sections:
- Decisions (why this step, design choices)
- Target Python Structure (what to create)
- Porting Plan (Ruby ↔ Python code examples)
- Common Pitfalls (what to watch for)

### Step 3: Copy Template
Done automatically by script. Files from 03_prompt_builder are now in 04_api_client/.

### Step 4: Create New Files
From plan, need to create:
- `src/boukensha/client.py` (main HTTP client)
- `examples/example.py` (updated example)

### Step 5: Modify Existing Files
From plan, need to modify:
- `src/boukensha/errors.py` (add ApiError)
- `src/boukensha/__init__.py` (export Client, ApiError)
- `pyproject.toml` (version 0.3.0 → 0.4.0)
- `README.md` (document Client usage)

### Step 6: Test
```bash
source venv/bin/activate
pip install -e week1_baseline/python/04_api_client
./week1_baseline/bin/python/04_api_client
```

### Step 7: Commit
```bash
git add week1_baseline/python/04_api_client
git add docs/plans/python_port/04_api_client.md
git commit -m "Port step 04 (API Client) to Python"
```

---

## File Reference

### Skills & Docs
| File | Purpose |
|------|---------|
| `port-to-python.md` | Comprehensive porting guide (this skill) |
| `port-to-python.sh` | Automated setup & validation script |
| `README.md` | This file |
| `port-ruby-to-python.md` | Legacy guide (deprecated, use port-to-python.md) |

### Project Structure
| Directory | Purpose |
|-----------|---------|
| `week1_baseline/ruby/` | Ruby source code (reference) |
| `week1_baseline/python/` | Python ports (target) |
| `docs/plans/python_port/` | Detailed porting guides per step |
| `.claude/skills/` | This directory |

### Generated During Porting
- `week1_baseline/python/<STEP>/` — new Python step
- `week1_baseline/bin/python/<STEP>` — executable launcher
- Commit history shows what changed

---

## Tips for Success

### 1. Use the Script for Setup
```bash
./.claude/skills/port-to-python.sh <STEP>
```
Saves time, catches errors, ensures consistency.

### 2. Always Read the Plan First
Every plan has:
- Decisions (WHY this step)
- Examples (HOW to translate)
- Pitfalls (WHAT to avoid)
- Testing (HOW to verify)

### 3. Copy First, Then Modify
**Workflow**:
1. Copy prior Python step → new step
2. Keep all old files as-is
3. Add only new files
4. Modify only exports & config

**Never**: Rewrite existing files or restructure copied code.

### 4. Follow Naming Conventions
- Python files: `snake_case.py`
- Classes: `PascalCase`
- Methods: `snake_case()`
- Private: `_leading_underscore()`
- Constants: `UPPER_CASE`

### 5. Use Type Hints
```python
def method(arg: str, count: int = 1) -> Dict[str, Any]:
    """Do something with arg, repeated count times."""
    pass
```

Helps catch bugs, improves IDE support, serves as documentation.

### 6. Test Before Committing
```bash
source venv/bin/activate
pip install -e week1_baseline/python/<STEP>
python -c "from boukensha import *; print('✓ Imports work')"
./week1_baseline/bin/python/<STEP>  # Must run successfully
```

---

## When to Use Each Resource

### Use `port-to-python.sh` when:
- ✓ Starting a new port
- ✓ Checking prerequisites
- ✓ Generating file checklists
- ✓ Verifying environment setup

### Use `port-to-python.md` when:
- ✓ Learning Ruby→Python patterns
- ✓ Translating a specific idiom
- ✓ Understanding a design decision
- ✓ Debugging common issues
- ✓ Troubleshooting test failures

### Use plan docs (`docs/plans/python_port/*.md`) when:
- ✓ Porting a specific step
- ✓ Need file-by-file guidance
- ✓ Looking at Ruby↔Python code examples
- ✓ Understanding step dependencies
- ✓ Verifying testing approach

---

## Getting Help

### Quick Questions
- Ruby → Python pattern: See `port-to-python.md` Translation Patterns section
- Script not working: Run with `-x` flag: `bash -x port-to-python.sh 04`
- Import errors: Check exports in `src/boukensha/__init__.py`

### Comprehensive Guidance
1. Read `port-to-python.md` (this skill)
2. Read plan for your step: `docs/plans/python_port/<STEP>.md`
3. Compare Ruby source: `week1_baseline/ruby/<STEP>/`
4. Check prior Python step: `week1_baseline/python/<STEP-1>/`

### Still Stuck?
1. Check "Common Pitfalls" in plan document
2. Run tests to narrow down issue
3. Compare working prior step to broken new step
4. Review git diff: `git diff week1_baseline/python/<STEP>`

---

## Future Enhancements

Possible improvements to these tools:
- [ ] Interactive CLI for porting decisions
- [ ] Auto-generation of stub files from plan
- [ ] Diff tool: highlight Ruby↔Python changes
- [ ] Test generator: create unit tests from examples
- [ ] Linter: check for common Python style issues
- [ ] Formatter: auto-format Python code (black)

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-07-22 | Initial release: port-to-python.md, port-to-python.sh, README |
| | | Universal porting guide for steps 00-04+ |
| | | Automated setup & verification |
| | | Comprehensive Ruby→Python patterns |

---

## License & Attribution

Created as part of the Boukensha AI baseline project. Designed to make Ruby→Python porting systematic, repeatable, and well-documented.

For questions or improvements, see project documentation or raise an issue.

---

**Ready to port?** Start with:
```bash
./.claude/skills/port-to-python.sh <STEP_NUMBER>
```
