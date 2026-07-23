# Python Port: Boukensha Step 06 (The Logger)

**Status**: Planning — This document defines the port plan for `week1_baseline/ruby/06_the_logger/` to Python.

Step 06 adds comprehensive session logging to track agent iterations, API calls, tool execution, and responses. The Logger writes JSONL (JSON Lines) format for easy parsing and analysis. It also introduces module-level configuration access via `Boukensha.config` and debug flags.

## Decisions

These decisions build on 00_config through 05_agent_loop:

- **Logger class writes JSONL**: Each log event is a single JSON line with timestamp and session ID. Logs go to `sessions/{session_id}.jsonl` by default.

- **Session ID auto-generated**: Format is `{YYYYMMDDTHHMMSSZ}-{4-byte-hex}`, e.g., `20260722T213045Z-a1b2c3d4`.

- **Boukensha module singleton**: `Boukensha.config` is a lazy-loaded Config instance; debug and quiet flags are module-level.

- **Agent logging integration**: Agent logs every phase: iteration start, prompt sent, response received, tool calls, tool results, turn end.

- **Error handling in tool dispatch**: Tool call errors are caught and logged with `ok: false` and error message.

- **Usage tracking**: Logger extracts usage data from API responses in a provider-agnostic way.

## Target Python Structure

```
week1_baseline/python/06_the_logger/
├── src/
│   └── boukensha/
│       ├── __init__.py              # Add Boukensha.config, debug/quiet functions
│       ├── logger.py                # Logger class (NEW)
│       ├── agent.py                 # Modify: add logger, logging calls
│       ├── config.py                # Copy from 05
│       └── ... (other files unchanged)
├── examples/
│   └── example.py                   # No changes
├── prompts/
│   └── system.md
├── pyproject.toml                   # Bump to 0.6.0
└── README.md
```

## Key Changes by File

### 1. **logger.py** (NEW)

Full Logger class with:
- `__init__(session_id=None, dir=None, log=None, snapshot={})`
- Methods: `iteration()`, `limit_reached()`, `turn_end()`, `prompt()`, `tool_call()`, `tool_result()`, `response()`, `raw()`, `close()`
- JSONL writing with timestamps and session IDs
- Usage extraction from different provider formats
- Cost estimation support

**Key translations**:
- `SecureRandom.hex(4)` → `secrets.token_hex(4)`
- `Time.now.iso8601` → `datetime.now(timezone.utc).isoformat()`
- `File.open(..., "a")` → `open(..., "a")`
- `FileUtils.mkdir_p()` → `Path(...).mkdir(parents=True, exist_ok=True)`

### 2. **agent.py** (MODIFIED)

- Add `logger: Optional[Logger] = None` parameter to `__init__`
- If logger is None, create `Logger()` instance
- Add logging calls throughout:
  - `self.logger.limit_reached(kind="max_iterations", n=..., max=...)`
  - `self.logger.iteration(n=..., max=...)`
  - `self.logger.prompt(messages=..., tools=...)`
  - `self.logger.raw(data=response)`
  - `self.logger.tool_call(name=..., args=...)`
  - `self.logger.tool_result(name=..., result=..., ok=...)`
  - `self.logger.response(text=..., usage=..., stop_reason=..., task=..., backend=...)`
  - `self.logger.turn_end(reason=..., iterations=...)`
- Wrap tool dispatch in try/except to log errors
- Add `_log_response()` and `_normalized_usage()` helper methods

### 3. **__init__.py** (MODIFIED)

Add module-level state and functions:

```python
_config = None
_debug = False
_quiet = False

def config():
    """Lazy-load Config singleton."""
    global _config
    if _config is None:
        from .config import Config
        _config = Config()
    return _config

def debug_enabled():
    return _debug

def debug_on():
    global _debug
    _debug = True

def debug_off():
    global _debug
    _debug = False

def quiet_enabled():
    return _quiet

def quiet_on():
    global _quiet
    _quiet = True

def loud_on():
    global _quiet
    _quiet = False
```

Export Logger and update `__all__`.

## Copy Unchanged from 05_agent_loop

- All files except `agent.py` and `__init__.py`

## Testing Strategy

1. Logger writes valid JSONL format
2. Session ID has correct format
3. Timestamps are ISO 8601
4. Usage extraction works for all providers
5. Agent logging integration works end-to-end
6. Example runs successfully

## Complexity

- **New classes**: 1 (Logger)
- **Modified classes**: 1 (Agent)
- **Estimated time**: 45 minutes
- **Complexity level**: Medium

