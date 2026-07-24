import re
from pathlib import Path
from typing import Optional


class FileSystem:
    """File system tools for reading, writing, and searching files.

    All paths are relative to working_dir and cannot escape it.
    """

    @staticmethod
    def register(registry, working_dir: str) -> None:
        """Register FileSystem tools into the registry."""
        fs = FileSystem(working_dir)

        registry.tool(
            name="pwd",
            description="Return the current working directory",
            block=fs.pwd
        )
        registry.tool(
            name="list_directory",
            description="List files and directories at a path (default: current)",
            parameters={
                "path": {
                    "type": "string",
                    "description": "Path to list (default: '.')"
                }
            },
            block=fs.list_directory
        )
        registry.tool(
            name="read_file",
            description="Read a file's contents",
            parameters={
                "path": {"type": "string", "description": "File path to read"}
            },
            block=fs.read_file
        )
        registry.tool(
            name="write_file",
            description="Write (or create) a file",
            parameters={
                "path": {"type": "string", "description": "File path"},
                "content": {"type": "string", "description": "File content"}
            },
            block=fs.write_file
        )
        registry.tool(
            name="delete_file",
            description="Delete a file",
            parameters={
                "path": {"type": "string", "description": "File path to delete"}
            },
            block=fs.delete_file
        )
        registry.tool(
            name="search_files",
            description="Search files for a regex pattern (returns path:line:content matches)",
            parameters={
                "pattern": {"type": "string", "description": "Regex pattern to search"},
                "path": {
                    "type": "string",
                    "description": "Start directory (default: '.')"
                }
            },
            block=fs.search_files
        )

    def __init__(self, working_dir: str):
        self.working_dir = Path(working_dir).resolve()

    def _safe_path(self, path: str) -> Path:
        """Resolve path safely and reject escapes."""
        target = (self.working_dir / path).resolve()
        if not str(target).startswith(str(self.working_dir)):
            raise ValueError(f"Path escape detected: {path}")
        return target

    def pwd(self) -> str:
        """Return the working directory."""
        return str(self.working_dir)

    def list_directory(self, path: str = ".") -> str:
        """List files and directories."""
        try:
            target = self._safe_path(path)
            if not target.is_dir():
                return f"Not a directory: {path}"
            return "\n".join(sorted([item.name for item in target.iterdir()]))
        except ValueError as e:
            return f"Error: {e}"

    def read_file(self, path: str) -> str:
        """Read a file's contents."""
        try:
            target = self._safe_path(path)
            if not target.exists():
                return f"File not found: {path}"
            return target.read_text()
        except ValueError as e:
            return f"Error: {e}"
        except UnicodeDecodeError:
            return f"Error: File is not text: {path}"

    def write_file(self, path: str, content: str) -> str:
        """Write (or create) a file."""
        try:
            target = self._safe_path(path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
            return f"Written {len(content)} bytes to {path}"
        except ValueError as e:
            return f"Error: {e}"

    def delete_file(self, path: str) -> str:
        """Delete a file."""
        try:
            target = self._safe_path(path)
            if not target.exists():
                return f"File not found: {path}"
            target.unlink()
            return f"Deleted {path}"
        except ValueError as e:
            return f"Error: {e}"

    def search_files(self, pattern: str, path: str = ".") -> str:
        """Search files for a regex pattern."""
        try:
            target = self._safe_path(path)
            if not target.is_dir():
                return f"Not a directory: {path}"

            results = []
            regex = re.compile(pattern)

            for file_path in target.rglob("*"):
                if not file_path.is_file():
                    continue
                try:
                    content = file_path.read_text()
                    for line_num, line in enumerate(content.split("\n"), 1):
                        if regex.search(line):
                            rel_path = file_path.relative_to(self.working_dir)
                            results.append(f"{rel_path}:{line_num}:{line}")
                except (UnicodeDecodeError, PermissionError):
                    pass

            return "\n".join(results) if results else "No matches found"
        except ValueError as e:
            return f"Error: {e}"
        except re.error as e:
            return f"Error: Invalid regex: {e}"
