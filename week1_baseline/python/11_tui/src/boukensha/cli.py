"""Entry point for the ``boukensha`` console script (see pyproject.toml's
``[project.scripts]``). Mirrors ruby's ``bin/boukensha`` (via
``boukensha_loader.rb``): no configure callback — just start the interactive
REPL with everything coming from config (``BOUKENSHA_DIR`` env var, else
``~/.boukensha``). ``--no-tui`` falls back to the plain terminal REPL, same
as ruby's ``boukensha --no-tui``.
"""

import sys

import boukensha


def main() -> None:
    no_tui = "--no-tui" in sys.argv
    boukensha.repl(tui=not no_tui)


if __name__ == "__main__":
    main()
