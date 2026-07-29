---
name: week2_capable_plan
description: Week 2 plan to build a control layer for multi-user MUD agents with admin capabilities
metadata:
  type: project
---

## Week 2 Capable Agent Plan — Control Layer

**Created**: 2026-07-28  
**Updated**: 2026-07-28 (Clarified Goal)  
**Status**: Planning phase (detailed)  
**Target completion**: 2026-08-04 (7 days)

### Goal: Multi-User Control Plane

Build a **control layer** on top of `week1_baseline/python/12_context` that enables:

1. **User/Admin System** — Different identities with different permissions
2. **Admin Powers** — Teleport players, reset world, manage users
3. **Permission Policies** — Role-based access control (Admin, Player, Observer)
4. **Audit Trail** — Log every action for security/debugging
5. **Persistent World** — SQLite stores rooms, players, actions

### NOT about dashboards or observability visualization

This is about **authorization & control**, not metrics/analytics.

### Core Systems

1. **AuthManager** (`control/auth.py`)
   - Create users (Admin, Player, Observer roles)
   - Track current room per player
   - Manage sessions

2. **PermissionPolicy** (`control/permissions.py`)
   - RoleBasedPolicy: what each role can do
   - ResourceQuotaPolicy: action limits per hour
   - SelfOnlyPolicy: players can't control others
   - CompositePolicy: combine multiple policies

3. **AdminCommands** (`control/admin.py`)
   - `teleport_player(user, room)` — move player to location
   - `reset_world()` — reset game state
   - `create_player(name)` — create new user
   - `grant_admin(player_name)` — promote to admin
   - `list_players()` — show all users

4. **PermissionChecker** (`control/guard.py`)
   - Enforce policies before action
   - Sits between user request and agent
   - Log permission checks (allowed/denied)

5. **AuditLogger** (`control/audit.py`)
   - Track all actions in SQLite
   - Query user history
   - Find permission denials
   - Admin can inspect any user's activity

6. **WorldDB** (`world/db.py`)
   - SQLite world database
   - Rooms, exits, player locations
   - Pathfinding queries
   - Persistent across sessions

### Architecture

```
User Input (Admin or Player)
    ↓
PermissionChecker (guard)
    ↓
PermissionPolicy (RoleBased, Quota, etc)
    ├─ Allowed? → Execute action
    └─ Denied? → Log and return error
    ↓
Admin commands OR Agent task
    ↓
SQLite (world.db, audit_log)
```

### Key Feature: Admin Teleports Player

**Command:**
```
/admin teleport Alice "Market Square"
```

**Flow:**
1. Check: Is user Admin? YES
2. Check: Can admin do "admin_teleport"? YES
3. Find Alice in users DB
4. Update Alice's current_room to "Market Square"
5. Log in audit_log: admin moved Alice
6. Return success message

**Player Tries Same:**
1. Check: Is user Admin? NO
2. Permission denied: "player cannot admin_teleport"
3. Log denial in audit_log
4. Return error

### 7-Phase Implementation

| Phase | Days | What |
|-------|------|------|
| 1 | 2 | WorldDB (SQLite rooms, exits) |
| 2 | 1 | AuthManager (create users, roles) |
| 3 | 1 | PermissionPolicy (RoleBased, Quota) |
| 4 | 1 | AdminCommands (teleport, reset, etc) |
| 5 | 1 | AuditLogger (track all actions) |
| 6 | 1 | PermissionChecker (enforce policies) |
| 7 | 1 | Integration & testing |

### Success Metrics

✅ **Users & Roles**
- Create Admin with full access
- Create Player who can only control self
- Create Observer with read-only access

✅ **Admin Commands**
- `/admin teleport Alice "Market Square"` works
- `/admin reset_world` resets state
- `/admin create_player Bob` creates new user
- `/admin grant_admin Charlie` promotes player

✅ **Permissions Enforced**
- Players cannot execute admin commands
- Quota prevents action spam (50 spells/hour for players)
- Admins have unlimited actions

✅ **Audit Trail**
- Every action logged (permitted/denied)
- Admin can query: "What did Alice do?"
- Admin can query: "Which players tried admin_teleport?"
- Logs stored in SQLite audit_log table

✅ **Integration**
- Control layer wraps agent (no agent code changes)
- Multiple users can run simultaneously
- World state shared/consistent across users

**Full detailed plan**: `docs/plans/week2_control_layer.md`  
**Architecture diagram**: Control Layer Architecture artifact
