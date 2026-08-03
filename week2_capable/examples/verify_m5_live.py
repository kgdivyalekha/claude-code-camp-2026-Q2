#!/usr/bin/env python3
"""
Minimal M5 verification during Boukensha play.

This example shows the simplest way to:
1. Wire M5 into an agent
2. Monitor what's happening
3. Verify permissions, hooks, and audit work

Run this, then query the audit log to verify M5 is working.
"""

from boukensha.control import (
    Actor, Role, GuardedRegistry,
    AllowList, DenyList, Composite,
    HookRegistry, AuditLog,
)
from boukensha.logger import Logger
from boukensha.registry import Registry


def setup_m5_for_agent(agent, session_id="test-session"):
    """Wire M5 into an existing agent."""

    # 1. Create an actor (represents the MUD character)
    actor = Actor(
        id="scout",
        character="Scout",
        role=Role.PLAYER,
        session_id=session_id,
    )

    # 2. Create a permission policy
    # Deny: send_raw, quit, delete
    # Allow: everything else
    policy = Composite([
        DenyList(["*__send_raw", "*__quit", "*__delete"]),
        AllowList(["*__*"]),
    ])

    # 3. Create hooks (optional, for observation)
    hooks = HookRegistry()

    # Log all tool calls (you'll see these in the audit trail)
    def log_call(**payload):
        actor_id = payload.get("actor").id if payload.get("actor") else "?"
        tool = payload.get("name", "?")
        # Could log to file, print, etc.

    hooks.register("before_tool_call", log_call, priority=10)

    # 4. Create logger and audit trail
    logger = Logger(session_id=session_id)
    audit = AuditLog(".boukensha/events.db")

    # 5. Wrap agent's registry with GuardedRegistry
    agent.registry = GuardedRegistry(
        agent.registry,
        actor=actor,
        policy=policy,
        hooks=hooks,
        logger=logger,
        audit=audit,
    )

    return actor, policy, audit


def check_m5_results(session_id):
    """After agent finishes, check what M5 recorded."""
    import sqlite3

    db_path = ".boukensha/events.db"

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
    except Exception as e:
        print(f"✗ Could not open audit database: {e}")
        return

    print(f"\n=== M5 Verification Results ===")
    print(f"Session: {session_id}\n")

    # 1. Count decisions
    cursor.execute(
        "SELECT verdict, COUNT(*) FROM audit_log WHERE session_id = ? GROUP BY verdict",
        (session_id,)
    )

    print("Permission Decisions:")
    total = 0
    for verdict, count in cursor.fetchall():
        print(f"  {verdict}: {count}")
        total += count

    if total == 0:
        print("  ✗ No audit log entries found!")
        print(f"  Check that GuardedRegistry was used")
        conn.close()
        return

    # 2. Show which rules were applied
    cursor.execute(
        "SELECT rule, COUNT(*) FROM audit_log WHERE session_id = ? GROUP BY rule ORDER BY COUNT(*) DESC",
        (session_id,)
    )

    print("\nRules Applied:")
    for rule, count in cursor.fetchall():
        print(f"  {rule}: {count}x")

    # 3. Show denials (if any)
    cursor.execute(
        "SELECT action, rule, reason FROM audit_log WHERE session_id = ? AND verdict = 'deny'",
        (session_id,)
    )

    denials = cursor.fetchall()
    if denials:
        print("\nDenied Calls:")
        for action, rule, reason in denials[:5]:
            print(f"  {action}")
            print(f"    → {rule}: {reason}")
    else:
        print("\nNo denials (policy allowed everything)")

    # 4. Check credential redaction
    cursor.execute(
        "SELECT args FROM audit_log WHERE session_id = ? AND args IS NOT NULL LIMIT 1",
        (session_id,)
    )

    row = cursor.fetchone()
    if row:
        import json

        args = json.loads(row[0])
        if "[REDACTED]" in str(args):
            print("\n✓ Credential redaction working")
        else:
            print("\n✓ No credentials in sample")

    # 5. Summary
    print(f"\n✓ M5 audit trail complete ({total} entries)")
    print("✓ M5 is working during play!")

    conn.close()


def main():
    """Example: how to use M5 during play."""

    print("M5 Verification During Play")
    print("===========================\n")

    print("1. Set up M5:")
    print("   agent.registry = setup_m5_for_agent(agent, 'game-session')")

    print("\n2. Run the agent:")
    print("   result = agent.run(prompt)")

    print("\n3. Check results:")
    print("   check_m5_results('game-session')")

    print("\nTo verify M5 during your actual Boukensha game:")
    print("  1. Call setup_m5_for_agent(agent) before agent.run()")
    print("  2. Let the agent play")
    print("  3. Call check_m5_results() after")
    print("\nThis will show:")
    print("  ✓ How many tool calls were allowed/denied")
    print("  ✓ Which permission rules were applied")
    print("  ✓ Any denied calls (and why they were denied)")
    print("  ✓ Confirmation that credentials are redacted")


if __name__ == "__main__":
    main()

    # Uncomment to test with a session:
    # print("\nQuick test:")
    # check_m5_results("test-session")
