# Implementation Plans

This directory contains detailed plans for major project initiatives and ports.

## Python Port Initiative

### Python Port: Boukensha Configuration (00_config)
**Status**: Implemented — `week1_baseline/python/00_config/`, verified against the Ruby output
**Location**: `python_port/00_config.md`
**Objective**: Port the Ruby Boukensha configuration library to Python with full feature parity.

**Key Deliverables**:
- Python package structure with `pyproject.toml`, installed editable into the shared root `venv`
- `Config` class for YAML/environment-based settings
- Task base class system with prompt management (`is_prompt_override` naming)
- `examples/example.py` smoke test (no pytest suite — matches the Ruby side's smoke-test-only approach)
- `week1_baseline/bin/python/00_config` launcher alongside the fixed `bin/ruby/00_config`

**Key Dependencies**:
- `python-dotenv` - Environment variable management
- `pyyaml` - YAML parsing

---

## How to Use This Directory

1. **Read the plan** before starting implementation
2. **Track progress** against the rollout checklist
3. **Update status** as phases complete
4. **Cross-reference** related documentation and reference files

## Related Documentation

- Ruby source implementation: `week1_baseline/ruby/00_config/`
- Project structure overview: `docs/explore_architectures.md`
- Journal/progress notes: `docs/journal/README.md`
