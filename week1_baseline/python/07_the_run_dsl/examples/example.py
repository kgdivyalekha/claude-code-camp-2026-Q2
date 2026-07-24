import os
from pathlib import Path

import boukensha

os.environ["BOUKENSHA_DIR"] = str(Path(__file__).resolve().parent.parent.parent.parent.parent / ".boukensha")

print("=== BOUKENSHA Step 7: The Boukensha.run DSL ===")
print()
print(f"Config: {boukensha.config()}")
print()

base_dir = Path(__file__).resolve().parent.parent


def register_tools(dsl: boukensha.RunDSL) -> None:
    @dsl.tool(
        "read_file",
        description="Read the contents of a file from disk",
        parameters={"path": {"type": "string", "description": "The file path to read"}},
    )
    def read_file(path: str) -> str:
        return (base_dir / path).read_text()

    @dsl.tool(
        "list_directory",
        description="List the files in a directory",
        parameters={"path": {"type": "string", "description": "The directory path to list"}},
    )
    def list_directory(path: str) -> str:
        return ", ".join(
            f for f in os.listdir(str(base_dir / path)) if not f.startswith(".")
        )


# Task defaults (system prompt, model, provider, credentials) come from the
# Boukensha config directory. Any of run()'s keyword arguments can override
# a specific default without touching the others.
result = boukensha.run(
    task="Read the README.md file and summarise what this MUD player assistant framework can do.",
    configure=register_tools,
)

print()
print("=== FINAL RESPONSE ===")
print(result)
