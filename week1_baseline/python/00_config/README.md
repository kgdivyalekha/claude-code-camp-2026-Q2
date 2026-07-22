# 00 · Configuration (Python)

Python port of the Ruby `Boukensha::Config` library
(`week1_baseline/ruby/00_config/`). Same behaviour, same config schema —
see the Ruby README for design rationale. This doc covers Python-specific
setup and the small number of naming differences.

## Environment Setup

All Python steps in this repo share **one virtual environment at the
project root** (`<repo-root>/venv`) — don't create a per-step `.venv`.
Future iterations should install into this same environment.

```bash
# from the repo root, once
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# install this step's package into the shared venv
pip install -e week1_baseline/python/00_config
```

`week1_baseline/bin/python/00_config` assumes the venv is already active
(mirrors the Ruby launcher assuming `bundle install` already ran) — it does
not create or activate anything itself.

## Code Changes

| File | Purpose |
|------|---------|
| `src/boukensha/config.py` | `Config` class |
| `src/boukensha/tasks/base.py` | abstract `Base` (provider/model + prompt resolution) |
| `src/boukensha/tasks/player.py` | concrete `Player` (the main loop) |
| `src/boukensha/__init__.py` | package exports |
| `prompts/system.md` | default system prompt shipped with the library |
| `examples/example.py` | runnable smoke-test |

---

## Config directory resolution

The class looks for a `.boukensha/` directory in this order:

1. **`BOUKENSHA_DIR` env var** — set this to point at any directory you like.
2. **`~/.boukensha`** — the default location for a real install.

## Config directory structure

```
.boukensha/
  .env                 # stores credentials eg. LLMs APIs (never committed to repo)
  settings.yaml        # all non-secret settings
  prompts/
    <task>/
      system.md        # per-task override for the default system prompt (optional)
```

---

## Tasks

`Base` is an abstract stateless class. All behaviour is expressed as
classmethods that accept a `settings` dict — no instances are created.
Concrete subclasses define `task_name()`. For now only `Player` exists.

`Config.tasks()` returns the raw dict from `settings.yaml` under `tasks:`.
Pass a name to look up a specific task's settings dict, then pass it to the
stateless class:

```python
Player.provider(config.tasks("player"))
Player.system_prompt(
    config.tasks("player"),
    user_prompts_dir=config.user_prompts_dir,
    default_prompts_dir=Config.PROMPTS_DIR,
)
```

## System prompt resolution

Per task, `Player.system_prompt` is resolved in this order:

1. **`.boukensha/prompts/<task>/system.md`** — used when the task's
   `prompt_override.system` is `true` and the file exists.
2. **`prompts/system.md`** — the default system prompt shipped with the library.

## Naming differences from the Ruby version

Ruby's `?`-suffix predicate convention (`prompt_override?`) has no direct
Python equivalent. The Python port uses `is_prompt_override` — this naming
choice is intentional and should be applied consistently in later ports.

## Configuration Schema

Same schema as the Ruby version:

```yaml
tasks:
  player:
    provider: anthropic        # provider name (string)
    model: claude-haiku-4-5
    prompt_override:
      system: true
mud:
  host: localhost
  port: 4000
  username: dummy
  password: helloworld
```

## Run Example

```bash
./week1_baseline/bin/python/00_config
```

Expected output (values from your `.boukensha/`):

```
=== Boukensha Step 0: Configuration ===

Config dir:     /home/andrew/Sites/Claude-Code-Camp/.boukensha
Tasks:          player

-- player task --
Provider:       anthropic
Model:          claude-haiku-4-5
Prompt override?True
System prompt:  You are a MUD player assistant. Use the tools available to y...

MUD host:       localhost:4000
MUD user:       dummy

API key set?    True

<Boukensha.Config dir=/home/andrew/Sites/Claude-Code-Camp/.boukensha tasks=player>
```
