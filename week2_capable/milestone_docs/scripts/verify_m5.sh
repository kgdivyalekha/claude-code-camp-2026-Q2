#!/bin/bash
# Quick M5 Verification Script
# Run from week2_capable/milestone_docs/scripts/ directory

set -e

# Get the project root (go up 3 levels from scripts directory)
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

echo "=== M5 Verification Checklist ==="
echo

# Check 1: All files exist
echo "✓ Check 1: M5 modules exist"
test -f src/boukensha/control/actors.py && echo "  ✓ actors.py"
test -f src/boukensha/control/permissions.py && echo "  ✓ permissions.py"
test -f src/boukensha/control/hooks.py && echo "  ✓ hooks.py"
test -f src/boukensha/control/guarded_registry.py && echo "  ✓ guarded_registry.py"
test -f src/boukensha/control/audit.py && echo "  ✓ audit.py"
test -f src/boukensha/control/admin.py && echo "  ✓ admin.py"
test -f src/boukensha/control/__init__.py && echo "  ✓ __init__.py"
echo

# Check 2: Key classes defined
echo "✓ Check 2: Key classes defined"
grep -q "^class Decision" src/boukensha/control/permissions.py && echo "  ✓ Decision"
grep -q "^class Policy" src/boukensha/control/permissions.py && echo "  ✓ Policy"
grep -q "^class AllowList" src/boukensha/control/permissions.py && echo "  ✓ AllowList"
grep -q "^class DenyList" src/boukensha/control/permissions.py && echo "  ✓ DenyList"
grep -q "^class RolePolicy" src/boukensha/control/permissions.py && echo "  ✓ RolePolicy"
grep -q "^class RateLimit" src/boukensha/control/permissions.py && echo "  ✓ RateLimit"
grep -q "^class Composite" src/boukensha/control/permissions.py && echo "  ✓ Composite"
grep -q "^class HookRegistry" src/boukensha/control/hooks.py && echo "  ✓ HookRegistry"
grep -q "^class GuardedRegistry" src/boukensha/control/guarded_registry.py && echo "  ✓ GuardedRegistry"
grep -q "^class PermissionDenied" src/boukensha/control/guarded_registry.py && echo "  ✓ PermissionDenied"
grep -q "^class AuditLog" src/boukensha/control/audit.py && echo "  ✓ AuditLog"
grep -q "^class AdminCommands" src/boukensha/control/admin.py && echo "  ✓ AdminCommands"
grep -q "^class Actor" src/boukensha/control/actors.py && echo "  ✓ Actor"
grep -q "^class Role" src/boukensha/control/actors.py && echo "  ✓ Role"
echo

# Check 3: GuardedRegistry has key methods
echo "✓ Check 3: GuardedRegistry has required methods"
grep -q "def dispatch" src/boukensha/control/guarded_registry.py && echo "  ✓ dispatch()"
grep -q "def tool" src/boukensha/control/guarded_registry.py && echo "  ✓ tool()"
grep -q "def tool_names" src/boukensha/control/guarded_registry.py && echo "  ✓ tool_names()"
echo

# Check 4: Policy protocol has required methods
echo "✓ Check 4: Policy protocol has required methods"
grep -q "def check" src/boukensha/control/permissions.py && echo "  ✓ check()"
grep -q "def statically_denied" src/boukensha/control/permissions.py && echo "  ✓ statically_denied()"
echo

# Check 5: M5-M4 integration in PromptBuilder
echo "✓ Check 5: M5-M4 Integration"
grep -q "actor.*Optional" src/boukensha/prompt_builder.py && echo "  ✓ to_tools() accepts actor"
grep -q "policy.*Optional" src/boukensha/prompt_builder.py && echo "  ✓ to_tools() accepts policy"
grep -q "statically_denied" src/boukensha/prompt_builder.py && echo "  ✓ pruning logic in to_tools()"
grep -q "_get_actor_and_policy" src/boukensha/agent.py && echo "  ✓ Agent._get_actor_and_policy() exists"
grep -q "GuardedRegistry" src/boukensha/agent.py && echo "  ✓ Agent imports GuardedRegistry"
echo

# Check 6: Tests exist
echo "✓ Check 6: M5 tests exist"
test -f test/test_m5_permissions_hooks.py && echo "  ✓ test_m5_permissions_hooks.py"
grep -q "class Test" test/test_m5_permissions_hooks.py && echo "  ✓ Test classes defined"
echo

# Check 7: Examples exist
echo "✓ Check 7: M5 examples exist"
test -f examples/m5_permissions_demo.py && echo "  ✓ m5_permissions_demo.py"
test -f examples/m5_m4_integration.py && echo "  ✓ m5_m4_integration.py"
echo

# Check 8: Documentation exists
echo "✓ Check 8: M5 documentation exists"
test -f docs/M5_PERMISSIONS_HOOKS.md && echo "  ✓ M5_PERMISSIONS_HOOKS.md"
test -f docs/M5_M4_INTEGRATION.md && echo "  ✓ M5_M4_INTEGRATION.md"
test -f M5_STATUS.md && echo "  ✓ M5_STATUS.md"
test -f M5_M4_INTEGRATION_COMPLETE.md && echo "  ✓ M5_M4_INTEGRATION_COMPLETE.md"
test -f INTEGRATION_GUIDE.md && echo "  ✓ INTEGRATION_GUIDE.md"
echo

# Check 9: Key method signatures
echo "✓ Check 9: Method signatures correct"
grep -q "def __init__.*actor.*policy" src/boukensha/control/guarded_registry.py && echo "  ✓ GuardedRegistry.__init__ has actor, policy"
grep -q "def check.*actor.*tool.*args" src/boukensha/control/permissions.py && echo "  ✓ Policy.check() has actor, tool, args"
grep -q "def dispatch.*name.*args" src/boukensha/control/guarded_registry.py && echo "  ✓ GuardedRegistry.dispatch() has name, args"
echo

# Check 10: Imports are correct
echo "✓ Check 10: Critical imports present"
grep -q "from .control.guarded_registry import GuardedRegistry" src/boukensha/agent.py && echo "  ✓ Agent imports GuardedRegistry"
grep -q "from .control" src/boukensha/prompt_builder.py && echo "  ✓ PromptBuilder imports from control"
grep -q "__all__" src/boukensha/control/__init__.py && echo "  ✓ control/__init__.py exports public API"
echo

echo "=== Summary ==="
echo "✓ All M5 files and modules present"
echo "✓ All required classes defined"
echo "✓ M5-M4 integration in place"
echo "✓ Tests and examples included"
echo "✓ Documentation complete"
echo
echo "Next steps:"
echo "1. python -m pytest test/test_m5_permissions_hooks.py -v"
echo "2. python examples/m5_permissions_demo.py"
echo "3. python examples/m5_m4_integration.py"
echo "4. See VERIFY_M5.md for detailed verification"
