import subprocess
import shlex
from pathlib import Path
from typing import Optional, List


class Shell:
    """Shell command execution with timeout and allow-list."""

    @staticmethod
    def register(registry, working_dir: str,
                 timeout: int = 30, allowed_commands: Optional[List[str]] = None) -> None:
        """Register Shell tools into the registry."""
        shell = Shell(working_dir, timeout, allowed_commands)

        registry.tool(
            name="run_command",
            description="Run a shell command in the working directory",
            parameters={
                "command": {
                    "type": "string",
                    "description": "Command to run (e.g., 'ls -la', 'git status')"
                }
            },
            block=shell.run_command
        )

    def __init__(self, working_dir: str, timeout: int = 30,
                 allowed_commands: Optional[List[str]] = None):
        self.working_dir = Path(working_dir).resolve()
        self.timeout = timeout
        self.allowed_commands = set(allowed_commands) if allowed_commands else None

    def run_command(self, command: str) -> str:
        """Run a shell command."""
        if not command or not command.strip():
            return "Error: Empty command"

        # Parse command and check allow-list
        try:
            parts = shlex.split(command)
        except ValueError as e:
            return f"Error: Invalid command syntax: {e}"

        if not parts:
            return "Error: Empty command"

        executable = parts[0]

        # Check allow-list if it exists
        if self.allowed_commands and executable not in self.allowed_commands:
            return f"Error: '{executable}' not in allow-list: {', '.join(sorted(self.allowed_commands))}"

        # Execute the command
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=str(self.working_dir),
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            output = result.stdout if result.stdout else result.stderr
            return output if output else "(no output)"
        except subprocess.TimeoutExpired:
            return f"Error: Command timed out after {self.timeout}s"
        except Exception as e:
            return f"Error: {e}"
