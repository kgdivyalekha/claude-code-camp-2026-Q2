# Step 09 — Global Executable

Package BOUKENSHA as a pip-installable module so the `boukensha` command works from anywhere on your machine.

## What this step adds

- `pyproject.toml` — declares the package: name, version, which files to include, and the `boukensha` console script entry point
- `bin/boukensha` — the shebang script that becomes the global command
- `src/boukensha/loader.py` — resolves *which step folder* to load from, then boots the REPL
- `src/boukensha/` — steps 0-8's modules, bundled as the default

## Install

```bash
cd 09_global_executable
pip install -e .
```

After that, `boukensha` is on your `$PATH` and works from any directory.

## Switching steps with BOUKENSHA_PATH

The loader resolves in this order:

| Priority | Source | Example |
|----------|--------|---------|
| 1 | `BOUKENSHA_PATH` env var | `BOUKENSHA_PATH=~/Sites/boukensha/08_the_repl_loop boukensha` |
| 2 | `~/.boukensharc` file | `echo ~/Sites/boukensha/08_the_repl_loop > ~/.boukensharc` |
| 3 | Bundled default | just run `boukensha` |

`BOUKENSHA_PATH` must point to a step folder that contains `src/boukensha/`.

## Running a specific step

```bash
# step 8 (interactive REPL)
BOUKENSHA_PATH=~/Sites/boukensha/08_the_repl_loop boukensha

# step 7 doesn't have a REPL — loader tells you how to run it
BOUKENSHA_PATH=~/Sites/boukensha/07_the_run_dsl boukensha
# => boukensha: the step at .../07_the_run_dsl does not support the interactive REPL
#    Run its examples directly, e.g.: python .../07_the_run_dsl/examples/*.py
```

## Debug mode

```bash
BOUKENSHA_DEBUG=1 boukensha
# => [boukensha] loading from: /path/to/step
```

## The key idea

The package is just a **wrapper and a default**. All the teaching material stays in the numbered step folders exactly as it was. The package doesn't copy or symlink anything — it just knows where to look.
