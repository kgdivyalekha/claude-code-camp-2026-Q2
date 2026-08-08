# Milestone Verification and Testing Scripts

This directory contains scripts for verifying milestone implementations and testing system components.

## Verification Scripts

### `verify_m0.py`
Verifies M0 (baseline setup) implementation.
- Checks project structure
- Validates configuration
- Confirms dependencies are installed

```bash
python verify_m0.py
```

### `verify_m1.py`
Verifies M1 (token tracking) implementation.
- Validates token counting
- Checks event store integration
- Confirms cost calculation

```bash
python verify_m1.py
```

### `verify_m3.py`
Verifies M3 (context management) implementation.
- Tests context window tracking
- Validates memory constraints
- Checks cleanup logic

```bash
python verify_m3.py
```

### `verify_m4.py`
Verifies M4 (tool gating) implementation.
- Validates tool filtering by phase
- Checks schema overhead reduction
- Confirms dispatch logic

```bash
python verify_m4.py
```

### `verify_m5.sh`
Verifies M5 (permissions and hooks) implementation.
- Checks all M5 modules exist
- Validates key classes and methods
- Confirms M5-M4 integration

```bash
./verify_m5.sh
# Or from any directory:
bash milestone_docs/scripts/verify_m5.sh
```

### `verify_m8.py`
Verifies M8 (prompt caching) implementation.
- Validates cache control markers on system message
- Checks cache control on tool definitions
- Confirms enable_cache parameter flows through stack
- Verifies analytics integration

```bash
python verify_m8.py
```

## Utility Scripts

### `measure_baseline.py`
Measures baseline metrics for a session.
- Calculates token usage
- Determines cost baseline
- Generates comparison data

```bash
python measure_baseline.py <session_id>
```

## Running from Different Directories

All scripts detect the project root automatically, so you can run them from:
- The script directory: `./verify_m5.sh`
- The week2_capable directory: `bash milestone_docs/scripts/verify_m5.sh`
- The project root: `bash week2_capable/milestone_docs/scripts/verify_m5.sh`

## Script Organization

Scripts are organized by purpose:
- **Verification** (`verify_*.py`, `verify_*.sh`) - Check milestone implementations
- **Testing** (`test_*.py`, `test_*.rb`) - Test functionality
- **Utility** (others) - Support and maintenance tasks

## Adding New Scripts

When adding new scripts:
1. Place them in this directory
2. Update this README with description
3. Use consistent naming: `<purpose>_<component>.py|sh|rb`
4. Include path detection for running from any location
5. Add help/usage information at the top

## Notes

- Python scripts require the project venv to be activated
- Ruby scripts require Ruby and bundled gems
- All scripts should be idempotent when possible
- Use relative paths from PROJECT_ROOT for portability
