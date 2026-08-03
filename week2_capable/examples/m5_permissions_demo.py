"""M5 Example: Wiring permissions, hooks, and audit into an agent run.

This shows how to set up a single-actor agent with permission enforcement,
result compression hooks, and audit logging.

Usage:
    python examples/m5_permissions_demo.py
"""

from boukensha.control import (
    Actor,
    ActorRegistry,
    AllowList,
    AuditLog,
    Composite,
    DenyList,
    GuardedRegistry,
    HookRegistry,
    PermissionDenied,
    RateLimit,
    Role,
)
from boukensha.logger import Logger
from boukensha.registry import Registry


def setup_single_actor_with_permissions():
    """Set up a single agent with permissions and hooks."""

    # 1. Create the actor
    scout = Actor("scout", "Scout", Role.PLAYER, session_id="demo-1")

    # 2. Set up permission policy
    # Allow look, move, check. Deny send_raw. Rate limit look to 5/turn.
    policy = Composite([
        DenyList(["*__send_raw"]),  # First rule: deny send_raw
        RateLimit(
            per_turn={"*__look": 5},
            per_session={"*__cast_spell": 50},
        ),
        AllowList(["*__look", "*__move", "*__check", "*__say"]),  # Fallback: only these
    ])

    # 3. Set up hooks
    hooks = HookRegistry()

    # Example hook: log all tool calls
    def log_tool_call(**payload):
        actor_id = payload.get("actor")
        tool_name = payload.get("name")
        print(f"  HOOK: {actor_id} called {tool_name}")

    hooks.register("before_tool_call", log_tool_call, priority=10)

    # Example hook: compress repeated results
    def compress_repeated_results(**payload):
        result = payload.get("result", {})
        # In a real system, check if this exact result was returned recently
        # and replace with a compressed summary
        return result

    hooks.register("after_tool_call", compress_repeated_results, priority=90)

    # 4. Set up logging and audit
    logger = Logger(session_id="demo-1")
    audit = AuditLog(".boukensha/events.db")

    # 5. Create a simple registry with a few tools
    registry = Registry()

    @registry.tool("look")
    def look():
        return {"text": "You are in a dimly lit room. Exits: n, e."}

    @registry.tool("move")
    def move(direction: str = None):
        if not direction:
            return {"error": "move requires direction"}
        return {"text": f"You move {direction}."}

    @registry.tool("say")
    def say(text: str = None):
        if not text:
            return {"error": "say requires text"}
        return {"text": f'You say "{text}"'}

    @registry.tool("send_raw")
    def send_raw(command: str = None):
        if not command:
            return {"error": "send_raw requires command"}
        return {"response": f"MUD: {command}"}

    # 6. Wrap registry with permissions and hooks
    guarded = GuardedRegistry(
        registry,
        actor=scout,
        policy=policy,
        hooks=hooks,
        logger=logger,
        audit=audit,
    )

    return guarded, scout, audit


def run_demo():
    """Run a series of tool calls to demonstrate permissions and hooks."""

    guarded, scout, audit = setup_single_actor_with_permissions()

    test_calls = [
        ("look", {}),
        ("move", {"direction": "north"}),
        ("say", {"text": "hello"}),
        ("send_raw", {"command": "quit"}),  # Should be denied
        ("look", {}),
    ]

    print("\n=== M5 Permissions + Hooks Demo ===\n")
    print(f"Actor: {scout.character} (role: {scout.role.value})\n")

    for tool_name, args in test_calls:
        print(f"Calling: {tool_name} {args}")
        try:
            result = guarded.dispatch(tool_name, args)
            print(f"  Result: {result}\n")
        except PermissionDenied as e:
            print(f"  DENIED: {e}\n")
        except Exception as e:
            print(f"  ERROR: {e}\n")

    # Print audit trail
    print("\n=== Audit Trail ===\n")
    records = audit.query(scout.session_id)
    for record in records[:5]:  # First 5 records
        print(f"{record['action']:15} {record['verdict']:6} {record['rule']}")


def demo_multi_actor_policies():
    """Demonstrate role-based policies with multiple actors."""

    from boukensha.control import RolePolicy

    print("\n=== Multi-Actor Role-Based Policies ===\n")

    # Observer can only look
    observer = Actor("bot", "Bot", Role.OBSERVER, session_id="demo-2")

    # Player can move, communicate
    player = Actor("scout", "Scout", Role.PLAYER, session_id="demo-2")

    # Admin can do anything
    admin = Actor("admin1", "Admin", Role.ADMIN, session_id="demo-2")

    policy = RolePolicy()

    tools_to_check = ["look", "move", "attack", "say"]

    for actor in [observer, player, admin]:
        print(f"\nRole: {actor.role.value}")
        for tool in tools_to_check:
            decision = policy.check(actor, tool, {})
            verdict = "✓" if decision.verdict == "allow" else "✗"
            print(f"  {verdict} {tool}")

    # Show statically denied tools
    print(f"\nStatically denied for observer: {policy.statically_denied(observer)}")


if __name__ == "__main__":
    run_demo()
    demo_multi_actor_policies()
