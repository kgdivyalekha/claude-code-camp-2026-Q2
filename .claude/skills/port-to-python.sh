#!/bin/bash
#
# port-to-python.sh
# Automated Ruby-to-Python porting script for Boukensha baseline
# Includes plan generation, review, and user confirmation workflow
#
# Usage: ./port-to-python.sh <STEP_NUMBER>
# Example: ./port-to-python.sh 04
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"
RUBY_BASE="$PROJECT_ROOT/week1_baseline/ruby"
PYTHON_BASE="$PROJECT_ROOT/week1_baseline/python"
PLANS_DIR="$PROJECT_ROOT/docs/plans/python_port"
VENV_DIR="$PROJECT_ROOT/venv"

# Helper functions
print_header() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

print_question() {
    echo -e "${CYAN}❓ $1${NC}"
}

print_step() {
    echo -e "${MAGENTA}➜ $1${NC}"
}

# User confirmation function
confirm() {
    local prompt="$1"
    local response

    while true; do
        read -p "$(echo -e ${CYAN}$prompt${NC}) (y/n): " -n 1 -r response
        echo
        case $response in
            [Yy]) return 0 ;;
            [Nn]) return 1 ;;
            *) print_warning "Please answer y or n" ;;
        esac
    done
}

# Generate plan if missing
generate_plan() {
    local step="$1"
    local ruby_dir="$2"
    local plan_file="$3"

    print_header "Generating Porting Plan"

    # List Ruby files to be ported
    print_info "Analyzing Ruby source files..."

    local ruby_files=$(find "$ruby_dir" -type f -name "*.rb" | sed "s|^$ruby_dir/||" | sort)
    local file_count=$(echo "$ruby_files" | wc -l)

    print_success "Found $file_count Ruby files"
    echo ""

    # Generate plan content
    cat > "$plan_file" << 'EOF'
# Python Port: Boukensha Step <STEP>

**Status**: Auto-Generated Plan — Review and confirm before porting.

This plan was auto-generated based on the Ruby source structure.
Review the file structure, verify dependencies, and confirm this plan captures all porting tasks.

## Quick Summary

**Step**: <STEP>
**Ruby Source**: week1_baseline/ruby/<STEP>_*/
**Python Target**: week1_baseline/python/<STEP>_*/
**Template**: week1_baseline/python/<PRIOR>_*/

This step builds on prior steps by:
- [ ] Adding new classes/modules (list them)
- [ ] Modifying existing classes (which ones?)
- [ ] Changing exception handling (what new exceptions?)
- [ ] Updating API/contract (new public methods?)

## Ruby Files to Port

The following Ruby files need translation to Python:

EOF

    # Add file listing
    echo "$ruby_files" | while read file; do
        echo "- [ ] \`$file\` → \`src/boukensha/${file%.rb}.py\`" >> "$plan_file"
    done

    cat >> "$plan_file" << 'EOF'

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
2. [ ] Example runs: `./week1_baseline/bin/python/<STEP>`
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

EOF

    # Replace placeholders
    sed -i "s|<STEP>|$step|g" "$plan_file"

    print_success "Plan template generated: $plan_file"
    print_info "Please review and update the plan with specific details"
}

# Review and confirm plan
review_plan() {
    local plan_file="$1"

    print_header "Review Porting Plan"

    print_info "Plan file: $plan_file"
    echo ""
    print_info "Opening plan for review..."
    echo ""

    # Display the plan (first 50 lines for preview)
    head -50 "$plan_file"

    echo ""
    echo -e "${YELLOW}[... plan continues, showing first 50 lines ...]${NC}"
    echo ""

    print_question "Do you want to:"
    echo "  1) View full plan (less command)"
    echo "  2) Edit plan in editor"
    echo "  3) Continue with current plan"
    echo "  4) Abort and fix plan manually"

    read -p "Choice (1-4): " choice

    case $choice in
        1)
            less "$plan_file"
            print_info "Back to confirmation..."
            ;;
        2)
            if command -v nano &> /dev/null; then
                nano "$plan_file"
            elif command -v vi &> /dev/null; then
                vi "$plan_file"
            else
                print_warning "No editor found. Please edit manually:"
                echo "$plan_file"
            fi
            print_success "Plan updated"
            ;;
        3)
            print_info "Continuing with current plan"
            ;;
        4)
            print_error "Aborting. Edit plan manually at: $plan_file"
            exit 0
            ;;
        *)
            print_warning "Invalid choice. Continuing..."
            ;;
    esac
}

# Main script
main() {
    local step="$1"

    # Validate input
    if [ -z "$step" ]; then
        print_error "Step number required"
        echo "Usage: $0 <STEP_NUMBER>"
        echo "Example: $0 04"
        exit 1
    fi

    # Normalize step
    local step_num=$(echo "$step" | sed 's/^0*//')
    if [ -z "$step_num" ]; then
        step_num="0"
    fi

    # Calculate prior step
    local prior_step_num=$((step_num - 1))
    local prior_step=$(printf "%02d" "$prior_step_num")

    print_header "Boukensha Ruby → Python Porting Automation"
    echo "Step: $step | Prior: $prior_step"
    echo ""

    # Phase 1: Validation
    print_header "Phase 1: Validation"

    # Check Ruby source exists
    local ruby_dir=$(find "$RUBY_BASE" -maxdepth 1 -type d -name "${step}*" | head -1)
    if [ -z "$ruby_dir" ]; then
        print_error "Ruby source not found: $RUBY_BASE/${step}*"
        exit 1
    fi
    print_success "Ruby source found: $ruby_dir"

    # Check Python template exists (if not step 0)
    local python_template=""
    if [ "$step_num" -gt 0 ]; then
        python_template=$(find "$PYTHON_BASE" -maxdepth 1 -type d -name "${prior_step}*" | head -1)
        if [ -z "$python_template" ]; then
            print_error "Python template not found: $PYTHON_BASE/${prior_step}*"
            echo "You must port step $prior_step before step $step"
            exit 1
        fi
        print_success "Python template found: $python_template"
    fi

    echo ""

    # Phase 2: Plan Check/Generation
    print_header "Phase 2: Plan Generation & Review"

    local plan_doc=$(find "$PLANS_DIR" -maxdepth 1 -type f -name "${step}*.md" | head -1)

    if [ -z "$plan_doc" ]; then
        print_warning "Plan document not found: $PLANS_DIR/${step}*.md"
        print_info "Generating plan template..."
        echo ""

        # Create plan filename
        local step_name=$(basename "$ruby_dir" | cut -d_ -f2-)
        plan_doc="$PLANS_DIR/${step}_${step_name}.md"

        # Generate the plan
        generate_plan "$step" "$ruby_dir" "$plan_doc"

        echo ""
        print_warning "Auto-generated plan requires review!"
        echo ""

        # Review the generated plan
        review_plan "$plan_doc"

    else
        print_success "Plan document found: $plan_doc"

        # Review existing plan
        print_info "Reviewing existing plan..."
        echo ""
        review_plan "$plan_doc"
    fi

    echo ""

    # Phase 3: Plan Confirmation
    print_header "Phase 3: Plan Confirmation"

    echo ""
    print_step "Summary of porting plan:"
    echo "  Step: $step"
    echo "  Ruby Source: $ruby_dir"
    echo "  Python Target: ${python_template%/*}/${step}_*"
    echo "  Plan Location: $plan_doc"
    echo ""

    if ! confirm "Do you want to proceed with this porting plan?"; then
        print_warning "Porting cancelled by user"
        echo "You can:"
        echo "  1. Edit the plan: $plan_doc"
        echo "  2. Run setup again when ready: $0 $step"
        exit 0
    fi

    print_success "Plan confirmed! Proceeding with setup..."
    echo ""

    # Phase 4: Setup
    print_header "Phase 4: Setup"

    # Find or create Python target directory
    local python_target=$(find "$PYTHON_BASE" -maxdepth 1 -type d -name "${step}*" | head -1)

    if [ -n "$python_target" ]; then
        print_warning "Python target already exists: $python_target"
        if ! confirm "Do you want to continue and overwrite?"; then
            print_info "Aborted by user"
            exit 0
        fi
    else
        # Create target by copying template
        if [ "$step_num" -eq 0 ]; then
            print_info "Step 0 - creating baseline structure"
            mkdir -p "$PYTHON_BASE/00_config"
            python_target="$PYTHON_BASE/00_config"
        else
            python_target="${python_template%/*}/${step}_$(basename "$ruby_dir" | cut -d_ -f2-)"
            print_step "Copying template: $python_template → $python_target"
            cp -r "$python_template" "$python_target"
            print_success "Template copied to: $python_target"
        fi
    fi

    echo ""

    # Phase 5: Environment Check
    print_header "Phase 5: Environment Check"

    if [ -d "$VENV_DIR" ]; then
        print_success "Virtual environment found: $VENV_DIR"
    else
        print_warning "Virtual environment not found: $VENV_DIR"
        print_info "Run: python3 -m venv $VENV_DIR"
    fi

    if [ -d "$VENV_DIR" ] && [ -f "$VENV_DIR/bin/pip" ]; then
        print_success "pip is available"
    fi

    echo ""

    # Phase 6: Next Steps
    print_header "Phase 6: Ready to Port!"

    cat << EOF

✓ Plan reviewed and confirmed
✓ Python target directory ready
✓ Environment verified

NEXT STEPS
==========

1. REVIEW DETAILED PLAN (if needed)
   Open: $plan_doc

2. PORT FILES (follow plan guide)
   Ruby source:  $ruby_dir
   Python target: $python_target

   For each file in the plan:
   - Read Ruby source
   - Follow plan's translation examples
   - Create/modify Python files
   - Use patterns from: ./.claude/skills/port-to-python.md

3. UPDATE METADATA
   - Bump version in pyproject.toml
   - Update exports in __init__.py
   - Document new functionality in README.md

4. TEST THE PORT
   source $VENV_DIR/bin/activate
   pip install -e $python_target
   ./week1_baseline/bin/python/$step

5. COMMIT
   git add week1_baseline/python/$step
   git commit -m "Port step $step to Python"

HELPFUL COMMANDS
================
# View the plan
cat $plan_doc

# View Ruby file
cat $ruby_dir/lib/boukensha/file.rb

# Check Python structure
find $python_target -type f -name "*.py" | head -20

# Validate imports
python -c "from boukensha import *; print('OK')"

# Run example
./week1_baseline/bin/python/$step

# Check what changed
git diff $python_target

DOCUMENTATION
==============
- Porting skill: ./.claude/skills/port-to-python.md
- This plan: $plan_doc
- Ruby source: $ruby_dir
- Python target: $python_target

Questions? Check:
- ./.claude/skills/README.md (quick reference)
- ./.claude/skills/SETUP.md (getting started)
- ./.claude/skills/port-to-python.md (language patterns)

EOF

    echo ""
    print_success "Setup complete and confirmed. Ready to port!"
    echo ""
}

# Run main function
main "$@"
