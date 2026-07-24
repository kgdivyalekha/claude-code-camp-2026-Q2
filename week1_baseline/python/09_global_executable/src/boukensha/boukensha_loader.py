"""Boukensha loader that resolves which step version to load and starts the REPL."""

import os
import sys
from pathlib import Path


def resolve():
    """Resolve which step's boukensha lib to load.

    Resolution order:
    1. BOUKENSHA_PATH environment variable (selects which step lib to load)
    2. ~/.boukensharc file (persistent step selection)
    3. Bundled default (this step's lib)

    Returns:
        str: Path to boukensha.py file to load
    """
    # 1. Check BOUKENSHA_PATH env var
    if os.environ.get("BOUKENSHA_PATH"):
        custom_path = os.path.expanduser(os.environ["BOUKENSHA_PATH"])
        lib_path = os.path.join(custom_path, "src", "boukensha", "__init__.py")

        if os.path.exists(lib_path):
            return lib_path

        sys.stderr.write(
            f"boukensha: BOUKENSHA_PATH is set but no src/boukensha/__init__.py found at:\n"
            f"       {custom_path}\n"
            f"       Make sure BOUKENSHA_PATH points to a step folder, e.g.:\n"
            f"       BOUKENSHA_PATH=~/Sites/boukensha/08_the_repl_loop boukensha\n"
        )
        sys.exit(1)

    # 2. Check ~/.boukensharc
    rc_path = os.path.expanduser("~/.boukensharc")
    if os.path.exists(rc_path):
        with open(rc_path, "r") as f:
            step_path = f.read().strip()

        if step_path:
            step_path = os.path.expanduser(step_path)
            lib_path = os.path.join(step_path, "src", "boukensha", "__init__.py")

            if os.path.exists(lib_path):
                return lib_path

            sys.stderr.write(
                f"boukensha: ~/.boukensharc points to {step_path}\n"
                f"       but no src/boukensha/__init__.py was found there.\n"
                f"       Update ~/.boukensharc or remove it to use the bundled default.\n"
            )
            sys.exit(1)

    # 3. Bundled default (this step's lib)
    default_lib = os.path.join(
        os.path.dirname(__file__),
        "__init__.py"
    )
    return default_lib


def load_and_start_repl():
    """Load the resolved boukensha step and start the REPL."""
    lib_path = resolve()
    # lib_path is: /path/to/step/src/boukensha/__init__.py
    # We need: step_dir = /path/to/step, src_dir = /path/to/step/src
    src_dir = os.path.dirname(os.path.dirname(lib_path))
    step_dir = os.path.dirname(src_dir)

    if os.environ.get("BOUKENSHA_DEBUG"):
        print(f"[boukensha] loading from: {step_dir}")

    # Add the step's src directory to sys.path so we can import boukensha
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

    # Import and start the REPL
    import boukensha

    if not hasattr(boukensha, "repl"):
        sys.stderr.write(
            f"boukensha: the step at {step_dir}\n"
            f"       does not support the interactive REPL (added in step 08).\n"
            f"       Run its examples directly, e.g.:\n"
            f"         python {step_dir}/examples/*.py\n"
            f"       Or point BOUKENSHA_PATH at step 08 or later.\n"
        )
        sys.exit(1)

    boukensha.repl()


if __name__ == "__main__":
    load_and_start_repl()
