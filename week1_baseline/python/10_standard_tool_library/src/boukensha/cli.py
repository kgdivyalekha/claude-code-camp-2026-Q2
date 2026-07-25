"""Entry point for the ``boukensha`` console script (see pyproject.toml's
``[project.scripts]``). Mirrors ruby's ``bin/boukensha``: no arguments, no
configure callback — just start the interactive REPL with everything coming
from config (``BOUKENSHA_DIR`` env var, else ``~/.boukensha``).
"""

import boukensha


def main() -> None:
    boukensha.repl()


if __name__ == "__main__":
    main()
