# Plan Generation & Confirmation Feature

## Overview

The enhanced `port-to-python.sh` script now includes **automatic plan generation and user confirmation** before executing any port. This ensures you understand exactly what will be ported before the process begins.

## How It Works

### Workflow

```
1. User runs script
   ↓
2. Script checks for existing plan
   ↓
3a. Plan exists → Show for review
    ↓
3b. Plan missing → Auto-generate template
    ↓
4. Show plan to user with review options
   ↓
5. User chooses: view / edit / confirm / abort
   ↓
6. If confirmed → Proceed with setup
   If abort → Exit (user can fix plan manually)
```

### Interactive Options During Plan Review

When the script shows you a plan, you have these options:

```
❓ Do you want to:
  1) View full plan (less command)
  2) Edit plan in editor
  3) Continue with current plan
  4) Abort and fix plan manually

Choice (1-4): _
```

| Option | What Happens |
|--------|--------------|
| **1** | Opens full plan in `less` for detailed review |
| **2** | Opens plan in default editor (nano/vi) for editing |
| **3** | Confirms plan and proceeds with setup |
| **4** | Stops script - you can fix plan manually and run again |

## Plan Auto-Generation

### When It Happens

Plans are auto-generated when:
- Plan file doesn't exist in `docs/plans/python_port/`
- You're porting a new step (e.g., step 05+)
- Script analyzes Ruby source structure

### What Gets Generated

The auto-generated plan template includes:

```markdown
# Python Port: Boukensha Step <STEP>

**Status**: Auto-Generated Plan

## Quick Summary
- Step number
- Ruby source location
- Python target location
- What's being added

## Ruby Files to Port
- Lists all .rb files found
- Maps to Python equivalents

## Porting Strategy
- Files to copy unchanged
- Files to create
- Files to modify

## Dependency Analysis
- Prior step dependencies
- New public classes
- New exceptions
- New modules

## Estimated Complexity
- Number of files
- Time estimate
- Complexity level

## Testing Plan
- Import verification
- Example execution
- Output validation

## Common Pitfalls
- Known issues
- Things to watch for
- Special considerations
```

### Customizing Generated Plans

After generation, you can:

1. **Review** the template structure
2. **Edit** to add step-specific details:
   - Actual descriptions of new classes
   - Specific translation patterns
   - Known challenges
   - Testing requirements

3. **Confirm** when complete

### Example: Generated Plan for Step 05

```bash
./.claude/skills/port-to-python.sh 05
```

Output:
```
========================================
Phase 2: Plan Generation & Review
========================================

⚠ Plan document not found: docs/plans/python_port/05*.md
ℹ Generating plan template...

✓ Plan template generated: docs/plans/python_port/05_agent_loop.md
ℹ Please review and update the plan with specific details

========================================
Phase 3: Plan Confirmation
========================================

ℹ Plan file: docs/plans/python_port/05_agent_loop.md

ℹ Opening plan for review...

# Python Port: Boukensha Step 05

[50 lines of plan content...]

❓ Do you want to:
  1) View full plan (less command)
  2) Edit plan in editor
  3) Continue with current plan
  4) Abort and fix plan manually

Choice (1-4): 2
```

After editing, choose **3** to confirm and proceed.

## Plan Confirmation Requirements

Before porting, the script requires confirmation that:

✓ **Plan exists** (generated or pre-existing)  
✓ **Plan is reviewed** (shown to user)  
✓ **Plan is acceptable** (user confirms)  
✓ **Ruby source verified** (script validates)  
✓ **Python template ready** (prior step exists)  
✓ **Environment okay** (venv, pip available)  

Only after ALL these are met does porting proceed.

## Benefits of Plan Confirmation

### For You
- Know exactly what will be ported
- Add notes/comments to the plan
- Catch missing pieces before starting
- Reference the plan while porting

### For Documentation
- Plans are always up-to-date
- Future porters understand decisions
- Porting becomes repeatable
- No surprises or forgotten steps

### For Quality
- Planned porting = fewer errors
- Confirmation prevents mistakes
- Plans serve as checklists
- Testing strategy is clear upfront

## Typical Workflow with Plan Confirmation

### Scenario 1: Existing Plan

```bash
./.claude/skills/port-to-python.sh 04
```

```
✓ Plan document found: docs/plans/python_port/04_api_client.md
ℹ Reviewing existing plan...

[Plan preview...]

❓ Do you want to:
  1) View full plan
  2) Edit plan in editor
  3) Continue with current plan
  4) Abort and fix plan manually

Choice (1-4): 3

✓ Plan confirmed! Proceeding with setup...
```

### Scenario 2: Missing Plan (Auto-Generated)

```bash
./.claude/skills/port-to-python.sh 05
```

```
⚠ Plan document not found
ℹ Generating plan template...

✓ Plan template generated
ℹ Please review and update the plan

[Plan preview...]

❓ Do you want to:
  1) View full plan
  2) Edit plan in editor
  3) Continue with current plan
  4) Abort and fix plan manually

Choice (1-4): 2

[Opens editor for customization...]

✓ Plan updated
ℹ Back to confirmation...

❓ Do you want to proceed with this porting plan?
Choice (y/n): y

✓ Plan confirmed! Proceeding with setup...
```

### Scenario 3: Needs Changes

```bash
./.claude/skills/port-to-python.sh 06
```

```
⚠ Plan document not found
ℹ Generating plan template...

✓ Plan template generated

[Plan preview...]

❓ Do you want to:
  1) View full plan
  2) Edit plan in editor
  3) Continue with current plan
  4) Abort and fix plan manually

Choice (1-4): 4

✗ Aborting. Edit plan manually at: docs/plans/python_port/06_*.md

You can:
  1. Edit the plan manually
  2. Run setup again when ready: ./port-to-python.sh 06

[User edits plan file...]

./.claude/skills/port-to-python.sh 06

✓ Plan document found
ℹ Reviewing existing plan...

❓ Continue with current plan? (y/n): y

✓ Plan confirmed! Proceeding with setup...
```

## Plan Checklist

When reviewing/confirming a plan, verify it includes:

- [ ] **Identification**
  - [ ] Step number
  - [ ] Step name/purpose
  - [ ] Status (auto-generated or pre-existing)

- [ ] **File Mapping**
  - [ ] List of Ruby files to translate
  - [ ] Corresponding Python file locations
  - [ ] Files to copy vs create vs modify

- [ ] **Strategy**
  - [ ] What's new in this step
  - [ ] Dependencies from prior steps
  - [ ] New public API (classes, exceptions, modules)

- [ ] **Implementation Details**
  - [ ] Key translation patterns
  - [ ] Any special handling needed
  - [ ] Known pitfalls

- [ ] **Testing**
  - [ ] How to verify imports work
  - [ ] How to run example
  - [ ] Expected output shape

- [ ] **Effort Estimate**
  - [ ] Number of files
  - [ ] Estimated time
  - [ ] Complexity level

## Troubleshooting Plan Generation

### Plan Won't Generate

**Problem**: Script says plan can't be generated  
**Check**: Ruby source directory exists and is readable  
**Fix**: Ensure `week1_baseline/ruby/<STEP>*/` exists

### Generated Plan is Incomplete

**Problem**: Auto-generated template is missing details  
**Solution**: This is expected! Auto-generation creates a template. You should:
1. Review the structure
2. Edit to add step-specific details
3. Confirm when complete

**Command**: Choose option 2 (Edit) to customize

### Can't Edit Plan (No Editor Found)

**Problem**: Script can't find nano or vi  
**Solution**: Manually edit the plan file:
```bash
# Find and edit directly
vim docs/plans/python_port/<STEP>.md
# or
nano docs/plans/python_port/<STEP>.md
# or your preferred editor
```

Then run script again - it will find the existing plan and show it for confirmation.

### Want to Regenerate Plan

**Problem**: Want to start over with a fresh plan  
**Solution**:
```bash
# Delete the old plan
rm docs/plans/python_port/<STEP>*.md

# Run script again - it will regenerate
./.claude/skills/port-to-python.sh <STEP>
```

## Plan Structure Reference

### Minimal Plan
Required sections for a valid plan:
```markdown
# Python Port: Boukensha Step <STEP>

**Status**: [Auto-Generated / Planning / In Progress]

## Quick Summary
[What's being added]

## Ruby Files to Port
- [ ] file1.rb
- [ ] file2.rb

## Porting Strategy
### New Files to Create
- [ ] src/boukensha/file1.py

### Files to Modify
- [ ] src/boukensha/__init__.py

## Testing Plan
- [ ] Import verification
- [ ] Example runs
```

### Complete Plan
Comprehensive sections for detailed planning:
```markdown
# Python Port: Boukensha Step <STEP>

**Status**: [Status]

## Quick Summary
[Purpose and scope]

## Ruby Files to Port
[Detailed list with mappings]

## Porting Strategy
[Detailed breakdown]

## Dependency Analysis
[What this step depends on]

## Implementation Details
[Key patterns and considerations]

## Estimated Complexity
[Time, effort, difficulty]

## Testing Plan
[Verification checklist]

## Common Pitfalls
[Known issues]

## Additional Notes
[Any step-specific information]
```

## Next Steps After Confirming Plan

Once plan is confirmed:

1. **Setup completes** automatically
2. **You proceed to port files** following plan guidance
3. **Use plan as checklist** during porting
4. **Refer back to plan** for testing and verification
5. **Commit plan with your port** to document what was done

## FAQ

### Q: Can I skip plan confirmation?
**A**: No. Plan confirmation is required. This ensures you understand what will be ported before starting.

### Q: What if the plan is wrong?
**A**: You can:
1. Choose option 4 (Abort) during confirmation
2. Edit the plan manually
3. Run script again with fixed plan

### Q: Do I need a plan for every step?
**A**: Yes. Either a pre-existing plan or auto-generated template. This ensures documentation and prevents mistakes.

### Q: Can I modify the plan after confirming?
**A**: Yes. The plan is a regular Markdown file. You can:
```bash
vim docs/plans/python_port/<STEP>.md
```
Edit anytime, but confirm it before running the script.

### Q: What happens if I choose to abort?
**A**: Script exits cleanly. You can:
1. Edit the plan manually
2. Run script again
3. Confirm the improved plan

---

## Summary

The plan generation and confirmation feature ensures:

✓ **Visibility**: You know exactly what will be ported  
✓ **Control**: You can review/edit before proceeding  
✓ **Documentation**: Plans are automatically captured  
✓ **Quality**: Planned porting = fewer mistakes  
✓ **Auditability**: Clear record of what was planned vs executed  

**Every port requires a confirmed plan.** This simple requirement catches errors early and makes porting repeatable, auditable, and well-documented.
