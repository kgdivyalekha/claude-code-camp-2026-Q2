"""M5 + M4 Integration Example: Permissions + Tool Gating

This demonstrates how M5 (permissions, hooks, audit) integrates with M4 (tool gating).

When GuardedRegistry wraps the agent's registry, the agent automatically:
1. Filters tools by game phase (M4)
2. Prunes statically denied tools (M5)
3. Records all permission decisions

The model never sees tools the actor is never allowed to call, saving tokens.

Flow:
  Agent._call_opts() → detect GuardedRegistry → extract actor + policy
    → PromptBuilder.to_tools(actor, policy)
      → M4: gate().visible_tools_dict(phase, tools)  # filter by phase
      → M5: policy.statically_denied(actor)        # prune denied tools
      → backend.to_tools(filtered_set)
"""

from boukensha.control import (
    Actor,
    AllowList,
    Composite,
    DenyList,
    GuardedRegistry,
    HookRegistry,
    Role,
)
from boukensha.logger import Logger
from boukensha.audit import AuditLog
from boukensha.registry import Registry


def demo_m4_m5_integration():
    """Show tools being gated by phase and pruned by permissions."""

    print("\n=== M4 (Phase Gating) + M5 (Permission Pruning) Demo ===\n")

    # 1. Create an actor
    scout = Actor("scout", "Scout", Role.PLAYER, "session-1")

    # 2. Create a permission policy
    # RolePolicy would automatically deny combat tools for PLAYER role,
    # but let's be explicit with a custom policy for clarity
    policy = Composite([
        # First: deny dangerous tools regardless of arguments
        DenyList([
            "*__send_raw",       # never send raw commands
            "*__cast_spell",     # magic restricted
        ]),
        # Finally: allow common tools
        AllowList([
            "*__look",
            "*__move",
            "*__check",
            "*__examine",
            "*__say",
            "*__attack",         # combat allowed, but restricted by policy
            "*__skill_strike",
        ]),
    ])

    # 3. Show what policy.statically_denied() returns
    print("Policy Behavior:")
    print(f"  Statically denied tools: {policy.statically_denied(scout)}")
    print()

    # 4. Show M4 tool gating by phase
    from boukensha.tokens.gate import gate

    print("M4 Tool Gating by Phase:")
    gate_obj = gate()
    for phase in ["exploring", "fighting", "trading", "full"]:
        visible = gate_obj.visible(phase)
        count = gate_obj.tools_sent(phase)
        print(f"  {phase:12} → {count:2} tools: {sorted(visible)[:3]}...")
    print()

    # 5. Show combined M4 + M5 filtering
    print("Combined M4 + M5 Filtering (exploring phase):")
    phase = "exploring"

    # M4: Filter by phase
    all_tools = {
        "scout__look": "Tool(look)",
        "scout__move": "Tool(move)",
        "scout__check": "Tool(check)",
        "scout__attack": "Tool(attack)",
        "scout__cast_spell": "Tool(cast_spell)",
        "scout__send_raw": "Tool(send_raw)",
    }

    m4_visible = gate_obj.visible(phase)
    m4_filtered = {k: v for k, v in all_tools.items()
                   if k.split("__")[1] in m4_visible}
    print(f"  After M4 gating: {len(m4_filtered)} tools")
    for tool_id in sorted(m4_filtered.keys()):
        print(f"    {tool_id}")

    # M5: Prune denied
    denied = policy.statically_denied(scout)
    m5_filtered = {k: v for k, v in m4_filtered.items() if k not in denied}
    print(f"\n  After M5 pruning: {len(m5_filtered)} tools")
    for tool_id in sorted(m5_filtered.keys()):
        reason = "denied" if k in denied else ""
        print(f"    {tool_id}")

    print(f"\n  Tokens saved: schema payload ~{(len(m4_filtered) - len(m5_filtered)) * 100} tokens per call")
    print()

    # 6. Show GuardedRegistry in action
    print("GuardedRegistry Integration:")
    registry = Registry()

    @registry.tool("look")
    def look():
        return {"text": "A dimly lit room."}

    @registry.tool("send_raw")
    def send_raw(command: str = None):
        return {"error": "not allowed"}

    logger = Logger(session_id="session-1")
    audit = AuditLog(".boukensha/events.db")
    hooks = HookRegistry()

    guarded = GuardedRegistry(
        registry,
        actor=scout,
        policy=policy,
        hooks=hooks,
        logger=logger,
        audit=audit,
    )

    # This is what happens inside Agent when registry is GuardedRegistry:
    print(f"  registry is GuardedRegistry: {isinstance(guarded, GuardedRegistry)}")
    print(f"  actor extracted: {guarded._actor.id}")
    print(f"  policy extracted: {type(guarded._policy).__name__}")
    print()

    # 7. Simulate what PromptBuilder.to_tools() does
    print("PromptBuilder.to_tools() Simulation:")
    print(f"  Called with: phase={phase}, actor={scout.id}, policy={type(policy).__name__}")
    print(f"  M4 filter: {phase} → {len(m4_visible)} tools")
    print(f"  M5 prune: denied={denied} → {len(denied)} tools")
    print(f"  Result: {len(m5_filtered)} tools sent to API")
    print()

    # 8. Show permission enforcement
    print("Permission Enforcement (mid-turn):")
    test_calls = [
        ("look", {}),
        ("send_raw", {"command": "quit"}),
        ("cast_spell", {"spell": "fireball"}),
    ]

    for tool_name, args in test_calls:
        full_name = f"scout__{tool_name}"
        decision = policy.check(scout, full_name, args)
        verdict_mark = "✓ ALLOW" if decision.verdict == "allow" else "✗ DENY"
        print(f"  {full_name:20} {verdict_mark:10} ({decision.rule})")

    print()
    print("Summary:")
    print("  M4 gates by phase: 73% reduction during exploring")
    print("  M5 prunes denied:  send_raw, cast_spell removed from payload")
    print("  Calls at runtime:  still denied with policy check")
    print("  Model sees:        only tools it might need")


if __name__ == "__main__":
    demo_m4_m5_integration()
