# Week 2 Capable - Directory Organization

This document describes the organization and purpose of each directory in the week2_capable project.

## Root Level

```
week2_capable/
├── README.md                    # Main project documentation
├── ORGANIZATION.md              # This file
├── pyproject.toml              # Python project configuration
├── event_store.py              # Core event logging module
├── src/                        # Source code
├── test/                       # Tests
├── examples/                   # Example code
├── docs/                       # Documentation
├── dashboard/                  # Token dashboard
├── log_viz/                    # Log visualization web app
├── milestone_docs/             # Milestone tracking
└── .boukensha/                 # Runtime data (databases, sessions)
```

## Core Directories

### `src/boukensha/`
Main application source code organized by capability:

```
src/boukensha/
├── agent.py                    # Main agent loop
├── prompt_builder.py           # Prompt construction
├── api_client.py               # Claude API client
├── session.py                  # Session management
├── run.py                      # Entry point
├── prompt_builder.py           # Tool schema building
├── control/                    # M5: Permissions & hooks
│   ├── permissions.py          # Permission policies
│   ├── hooks.py                # Hook system
│   ├── guarded_registry.py     # Tool gating
│   ├── actors.py               # Actor management
│   ├── audit.py                # Audit logging
│   └── admin.py                # Admin commands
├── tokens/                     # M7: Token compression
│   ├── compress.py             # Compression logic
│   ├── compaction.py           # Context compaction
│   └── __init__.py             # Module exports
├── observability/              # Observability features
│   ├── navigation.py           # Movement tracking
│   └── __init__.py             # Module exports
└── __init__.py                 # Package initialization
```

### `test/`
Test files organized by milestone:

```
test/
├── test_m1_baseline.py         # M1: Token baseline
├── test_m4_token_impact.py     # M4: Tool gating impact
├── test_m5_permissions_hooks.py # M5: Permissions
├── test_m7_compression.py      # M7: Compression
└── __pycache__/                # Python cache
```

### `docs/`
Project documentation:

```
docs/
├── M5_PERMISSIONS_HOOKS.md     # M5 design
├── M5_M4_INTEGRATION.md        # M5-M4 integration
├── M7_DASHBOARD.md             # M7 dashboard design
└── milestones/                 # Individual milestone docs
```

### `examples/`
Example code and demos:

```
examples/
├── m5_permissions_demo.py      # M5 permissions example
└── m5_m4_integration.py        # M5-M4 integration example
```

### `dashboard/`
Token dashboard setup:

```
dashboard/
├── start_dashboard.sh          # Dashboard startup script
└── setup_events_db.rb          # Database initialization
```

### `log_viz/`
Log visualization web application:

```
log_viz/
├── lib/log_viz/
│   ├── app.rb                  # Sinatra web app
│   ├── session.rb              # Session parser
│   ├── analytics.rb            # Token analytics
│   ├── audit_db.rb             # Audit database
│   ├── world_db.rb             # World map database
│   └── ansi.rb                 # ANSI color handling
├── views/                      # ERB templates
│   ├── tokens.erb              # Token dashboard
│   ├── session.erb             # Session transcript
│   ├── permissions.erb         # Permission dashboard
│   ├── map_live.erb            # World map
│   └── ...                     # Other views
└── public/                     # Static assets
    └── style.css               # Styling
```

### `milestone_docs/`
Milestone tracking and scripts:

```
milestone_docs/
├── milestones.md               # Master milestone status
├── scripts/                    # Verification & test scripts
│   ├── README.md               # Scripts documentation
│   ├── verify_m*.py|sh         # Verification scripts
│   ├── test_*.py|rb            # Test scripts
│   └── ...                     # Other utility scripts
└── ...                         # Milestone-specific docs
```

### `.boukensha/`
Runtime data and databases (not committed):

```
.boukensha/
├── events.db                   # Event store database
├── events.db-shm               # SQLite shared memory
├── events.db-wal               # SQLite write-ahead log
├── sessions/                   # Session JSONL files
│   └── <session-id>.jsonl      # Individual session logs
├── world.db                    # World map database
└── ...                         # Other runtime data
```

## Key Features by Milestone

### M1: Token Tracking
- Event logging system (`event_store.py`)
- Token counting and cost calculation
- Analytics queries in `log_viz/lib/log_viz/analytics.rb`

### M4: Tool Gating
- Tool filtering by game phase
- Reduced schema overhead
- Tests in `test/test_m4_token_impact.py`

### M5: Permissions & Hooks
- Permission policies in `src/boukensha/control/permissions.py`
- Hook system in `src/boukensha/control/hooks.py`
- Tool gating via `GuardedRegistry`
- Audit logging in `src/boukensha/control/audit.py`

### M6: World Mapping
- World database in `.boukensha/world.db`
- Map visualization in `log_viz/views/map_live.erb`
- World database module in `log_viz/lib/log_viz/world_db.rb`

### M7: Token Compression
- Context compaction in `src/boukensha/tokens/`
- Compression metrics in dashboard
- Compression details in `log_viz/lib/log_viz/analytics.rb`

## Running Scripts

All scripts in `milestone_docs/scripts/` can be run from any directory:

```bash
# From week2_capable/
bash milestone_docs/scripts/verify_m5.sh

# From project root
bash week2_capable/milestone_docs/scripts/verify_m5.sh

# From anywhere with full path
bash /path/to/week2_capable/milestone_docs/scripts/verify_m5.sh
```

See `milestone_docs/scripts/README.md` for detailed script documentation.

## Database Organization

### events.db
SQLite database with event stream:
- `events` table - All logged events
- Indexed by session_id, phase, actor
- Populated from JSONL session files

### world.db
SQLite database for world mapping:
- `rooms` table - Discovered rooms
- `exits` table - Room connections
- `items` table - Items in rooms
- `npcs` table - NPC data
- `navigation_log` table - Movement history

## Best Practices

1. **Keep root clean** - Only config and core modules at root
2. **Organize by domain** - Source code grouped by capability
3. **Centralize scripts** - All scripts in `milestone_docs/scripts/`
4. **Document structure** - Maintain ORGANIZATION.md as code changes
5. **Use relative paths** - Scripts work from any directory

## Related Documentation

- `README.md` - Project overview and getting started
- `milestone_docs/milestones.md` - Milestone progress tracker
- `milestone_docs/scripts/README.md` - Script documentation
- Individual milestone docs in `docs/`
