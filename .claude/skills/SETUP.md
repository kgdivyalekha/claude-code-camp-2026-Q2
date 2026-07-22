# Boukensha Ruby-to-Python Porting Suite — Setup Complete ✓

You now have a complete, reusable system for porting any Ruby step to Python.

## What Was Created

### 1. **port-to-python.md** (Universal Porting Skill)
The master guide recognized by Claude Code. Use it with:
```
/port-to-python
```

**Contains**:
- Ruby → Python translation patterns (20+ common patterns)
- Step-by-step porting workflow
- File checklist templates
- Common pitfalls & debugging guide
- Testing & verification strategy
- Version bumping guidance
- Dependency chain reference

**~1000 lines** of comprehensive porting guidance.

---

### 2. **port-to-python.sh** (Automated Setup Script)
Automates the tedious setup phase.

**Usage**:
```bash
./.claude/skills/port-to-python.sh 04
./.claude/skills/port-to-python.sh 05
```

**What it does**:
- ✓ Validates Ruby source exists (week1_baseline/ruby/04_*)
- ✓ Validates Python template exists (week1_baseline/python/03_*)
- ✓ Creates Python target directory by copying template
- ✓ Generates file checklist from plan
- ✓ Checks environment (venv, pip, installations)
- ✓ Provides step-by-step next steps
- ✓ Prints helpful commands and resources

**Output**:
```
========================================
Boukensha Ruby → Python Porting Automation
========================================
Step: 04 | Prior: 03

Phase 1: Validation
✓ Ruby source found: /path/to/week1_baseline/ruby/04_api_client
✓ Python template found: /path/to/week1_baseline/python/03_prompt_builder
✓ Plan document found: /path/to/docs/plans/python_port/04_api_client.md

[... more setup phases ...]

Phase 6: Next Steps
1. READ THE PLAN
2. PORT FILES (follow examples)
3. CREATE NEW FILES
4. MODIFY EXISTING FILES
5. TEST THE PORT
6. COMMIT

[Helpful commands, docs references]
```

---

### 3. **README.md** (Skills Directory Guide)
Quick reference for this entire porting system.

**Contains**:
- Overview of all available skills
- Quick start workflow
- Ruby → Python reference table
- Common porting tasks & solutions
- Debugging guide (error table)
- Step-by-step example for step 04
- File reference and when to use each resource

---

### 4. **SETUP.md** (This File)
Summary of everything created and how to use it.

---

### 5. **04_api_client.md** (Step 04 Plan - Already Existed)
Comprehensive porting plan for step 04, now populated with:
- Design decisions
- Target Python structure
- File-by-file porting examples (Ruby ↔ Python code)
- Common pitfalls specific to HTTP/retry logic
- Testing strategy
- Expected output examples

---

## Quick Start: Port Step 04 (or Any Step)

### Minute 1: Generate & Confirm Plan
```bash
./.claude/skills/port-to-python.sh 04
```

The script will:
1. Check for existing plan (or auto-generate if missing)
2. Show the plan for your review
3. Ask you to confirm the plan before proceeding

**You'll see**:
```
❓ Do you want to:
  1) View full plan (less command)
  2) Edit plan in editor
  3) Continue with current plan
  4) Abort and fix plan manually

Choice (1-4): 3
```

Choose **3** to continue with setup, or **1/2** to review/edit first.

### Minutes 2-5: Read the Plan
```bash
cat docs/plans/python_port/04_api_client.md
```
Focus on:
- "Decisions" (understand the WHY)
- "Porting Plan" (see Ruby ↔ Python examples)
- "Common Pitfalls" (know what to watch for)

### Minutes 6-30: Port Files
Follow the plan's file-by-file guidance:
1. Create new files (e.g., `client.py`)
2. Copy old files unchanged (e.g., `registry.py`)
3. Modify exports (add new classes to `__init__.py`)
4. Update metadata (version in `pyproject.toml`)

Use patterns from `port-to-python.md` for language-specific issues.

### Minute 31: Test
```bash
source venv/bin/activate
pip install -e week1_baseline/python/04_api_client
./week1_baseline/bin/python/04_api_client
```

### Minute 32: Commit
```bash
git add week1_baseline/python/04_api_client
git commit -m "Port step 04 (API Client) to Python"
```

**Total time**: ~30 minutes for a typical step.

---

## How It Works: The Three-Tier System

### Tier 1: Automated Setup (Script)
```bash
./.claude/skills/port-to-python.sh <STEP>
```
**Does**: Validate, copy, check environment, provide checklist
**Output**: Ready-to-work directory + next steps

### Tier 2: Guided Porting (Plan Docs)
```
docs/plans/python_port/<STEP>.md
```
**Does**: File-by-file translation with Ruby ↔ Python examples
**Length**: 500-2000 lines depending on step complexity
**What's in it**:
- Decisions (design choices)
- Target structure (what to create)
- Porting plan (Ruby ↔ Python code side-by-side)
- Common pitfalls (what went wrong before)
- Testing strategy (how to verify)

### Tier 3: Pattern Reference (Skill)
```
/port-to-python
```
**Does**: Provides Ruby → Python pattern translations
**Use when**: You need to translate a specific idiom
**Examples**: imports, symbols, blocks, exceptions, file I/O, type hints

---

## File Locations

```
.claude/skills/
├── port-to-python.md          ← Universal porting skill (read by Claude)
├── port-to-python.sh          ← Automated setup script
├── README.md                  ← Skills guide & quick reference
├── SETUP.md                   ← This file
└── port-ruby-to-python.md     ← Legacy (use port-to-python.md instead)

docs/plans/python_port/
├── 00_config.md               ← Plan for step 0
├── 01_struct_skeleton.md      ← Plan for step 1
├── 02_the_registry.md         ← Plan for step 2
├── 03_prompt_builder.md       ← Plan for step 3
└── 04_api_client.md           ← Plan for step 4 (comprehensive!)

week1_baseline/
├── ruby/                      ← Ruby reference code
│   └── 04_api_client/
├── python/                    ← Python ports
│   ├── 03_prompt_builder/     ← Template to copy from
│   └── 04_api_client/         ← Target (created by script)
└── bin/
    └── python/04_api_client   ← Executable to test
```

---

## Typical Porting Flow

```
User runs:
  ./.claude/skills/port-to-python.sh 04

Script:
  1. Validates prerequisites ✓
  2. Copies template (03 → 04) ✓
  3. Shows checklist ✓
  4. Lists next steps ✓

User:
  1. Reads plan doc
  2. Creates new files (client.py)
  3. Modifies exports (__init__.py)
  4. Tests (pip install, ./bin/python/04)

User:
  1. Tests pass ✓
  2. Runs example ✓
  3. Output is correct ✓

User:
  git commit -m "Port step 04 to Python"

Next port:
  ./.claude/skills/port-to-python.sh 05
  (repeat)
```

---

## Key Features

### ✓ Systematic
- Same workflow for every step
- Consistent file structure
- Predictable patterns

### ✓ Guided
- Plan documents with examples
- Ruby ↔ Python patterns
- Debugging tips

### ✓ Automated
- Setup script validates & copies
- Environment checks
- Verification commands

### ✓ Documented
- 2000+ lines of documentation
- Real Ruby ↔ Python code examples
- Tested patterns from prior steps

### ✓ Reusable
- Works for steps 04, 05, 06, ...
- Same patterns apply
- Templates improve over time

---

## Using the Skills in Claude Code

### Option 1: Invoke Skill
```
/port-to-python
```
Opens this comprehensive guide in Claude.

### Option 2: Run Script Directly
```bash
./.claude/skills/port-to-python.sh 04
```
Gets immediate setup & validation output.

### Option 3: Read Plan Doc
```bash
cat docs/plans/python_port/04_api_client.md
```
Deep dive into step-specific guidance.

### Option 4: Browse Skills Directory
```bash
ls -la ./.claude/skills/
cat ./.claude/skills/README.md
```
Overview of all available resources.

---

## Example: Porting Step 04 (API Client)

### Before (No System)
- Manual copy: `cp -r python/03 python/04`
- Search Ruby: `cat ruby/04_api_client/lib/boukensha/client.rb`
- Manual translation: `vim python/04/src/boukensha/client.py`
- Manual testing: `pip install -e python/04` (hope it works)
- Repeat for 5+ files
- **Time**: 2-3 hours, many mistakes

### After (With System)
```bash
# 1. Run setup (2 min)
./.claude/skills/port-to-python.sh 04

# 2. Read plan (5 min)
open docs/plans/python_port/04_api_client.md

# 3. Port files following examples (15 min)
# - client.py (copy Ruby code, translate)
# - errors.py (add ApiError)
# - __init__.py (export new classes)
# - examples/example.py (update usage)

# 4. Test (3 min)
source venv/bin/activate
pip install -e week1_baseline/python/04_api_client
./week1_baseline/bin/python/04_api_client

# 5. Commit (1 min)
git add week1_baseline/python/04_api_client
git commit -m "Port step 04 to Python"

# Total: ~30 minutes
```

**Improvements**:
- ✓ Script validates everything upfront
- ✓ Plan has Ruby ↔ Python examples
- ✓ Pattern reference reduces translation errors
- ✓ Systematic approach = fewer mistakes
- ✓ Reusable for all future ports

---

## Next Ports: Using the System

### Port Step 05 (Agent Loop)
```bash
./.claude/skills/port-to-python.sh 05
open docs/plans/python_port/05_agent_loop.md
# Follow same pattern...
```

### Port Step 06, 07, etc.
```bash
./.claude/skills/port-to-python.sh <N>
open docs/plans/python_port/<N>_*.md
# Same workflow...
```

---

## What if Something Goes Wrong?

### Script Fails
```bash
bash -x ./.claude/skills/port-to-python.sh 04
```
Shows every step (helps debug).

### Can't Find Plan Document
```bash
ls docs/plans/python_port/
```
If missing, create one following the structure of `04_api_client.md`.

### Import Errors
Check `src/boukensha/__init__.py` exports:
```python
from .client import Client  # noqa: F401
```

### Test Fails
Compare to prior working step:
```bash
diff -u week1_baseline/python/03_prompt_builder/src/boukensha/__init__.py \
         week1_baseline/python/04_api_client/src/boukensha/__init__.py
```

### Still Stuck?
1. Re-read plan document's "Common Pitfalls" section
2. Check plan examples match your code
3. Inspect `git diff` to see what changed
4. Test a working prior step to confirm environment

---

## Documentation Roadmap

### For Quick Answers
1. **Script errors**: Run with `bash -x`
2. **Language patterns**: See `port-to-python.md`
3. **Specific step**: Read `docs/plans/python_port/<STEP>.md`

### For Deep Understanding
1. Read `port-to-python.md` (learn patterns)
2. Read step plan (see examples)
3. Compare Ruby & Python sources side-by-side
4. Check prior working step for patterns

### For Troubleshooting
1. `.claude/skills/README.md` — error table
2. Plan document — common pitfalls section
3. Test with simpler step (00, 01)
4. Use `git diff` to find what changed

---

## Summary

You now have:

| Resource | Purpose | Use When |
|----------|---------|----------|
| `port-to-python.md` | Universal porting guide | Learning patterns, translating idioms |
| `port-to-python.sh` | Automated setup | Starting a new port |
| `README.md` | Skills guide | Need quick reference |
| `docs/plans/python_port/<STEP>.md` | Step-specific guidance | Porting a specific step |
| Prior Python steps | Working examples | Comparing structure/patterns |

**To port any step**:
```bash
./.claude/skills/port-to-python.sh <STEP>  # Setup (2 min)
cat docs/plans/python_port/<STEP>.md        # Read plan (5 min)
# Port files (15 min)
pip install -e week1_baseline/python/<STEP> && ./week1_baseline/bin/python/<STEP>  # Test (3 min)
git commit -m "Port step <STEP> to Python"  # Commit (1 min)
```

**Total**: ~30 minutes per step, repeatable, well-documented, proven patterns.

---

## Ready to Port?

Start with:
```bash
./.claude/skills/port-to-python.sh 04
```

Then follow the guidance printed to your terminal! 🚀
