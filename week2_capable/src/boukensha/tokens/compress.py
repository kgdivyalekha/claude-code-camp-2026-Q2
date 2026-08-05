"""Result compression hooks: repeat-visit substitution, banner stripping, error collapsing.

These hooks run at after_tool_call and reduce token usage by replacing verbose,
repetitive MUD output with compact summaries.
"""

import re
import sys
from typing import Any, Dict, Optional

from boukensha.world.db import WorldDB
from boukensha.world.identity import signature


class CompressionHooks:
    """Compression hooks for tool results.

    All hooks are registered to run on after_tool_call with high priority
    (compression runs last, after any hook that might add content).
    """

    def __init__(self, world_db: WorldDB, logger=None):
        self.world_db = world_db
        self.logger = logger

    def compress_repeat_rooms(
        self,
        actor: Any,
        name: str,
        args: Dict[str, Any],
        result: Any,
    ) -> Optional[Dict[str, Any]]:
        """Compress repeat-visit room descriptions.

        First visit to a room: pass full description through.
        Subsequent visits: replace with compact summary from world.db.

        Example: "Temple Square (visited 4x). Exits: n, e, s."
        """
        if name != "look":
            return None

        # Try to parse the result
        try:
            room_name, exits, description = self._parse_look(result)
        except (ValueError, AttributeError, TypeError):
            # Parse failure — return original, log it
            self._log_event("navigation.parse_failed", result=result[:200])
            return None

        # Compute room signature
        try:
            sig = signature(room_name, exits, description)
        except Exception as e:
            self._log_event("signature_failed", error=str(e))
            return None

        # Query world.db for this room
        rooms = self.world_db.get_rooms_by_signature(sig)
        if not rooms:
            # New room; return original
            return None

        room = rooms[0]  # Most recent visit

        # visit_count is 0 on first discovery, increments on each subsequent add_room() call.
        # So: visit_count >= 1 means "we've seen this room before this call"
        if room["visit_count"] < 1:
            # First visit; return original, store summary for future repeats
            self._store_default_summary(room["id"], room_name, exits)
            return None

        # Repeat visit (visit_count >= 1): return compact summary
        summary = room.get("summary")
        if not summary:
            summary = self._generate_summary(room_name, room["visit_count"], exits)

        before_tokens = self._estimate_tokens(result)
        after_tokens = self._estimate_tokens(summary)
        saved = before_tokens - after_tokens

        self._log_event(
            "tokens.compressed",
            tool="look",
            before_tokens=before_tokens,
            after_tokens=after_tokens,
            saved=saved,
            room_id=room["id"],
            visit_count=room["visit_count"],
        )

        return {"content": summary, "ok": True}

    def strip_banners(
        self,
        actor: Any,
        name: str,
        args: Dict[str, Any],
        result: Any,
    ) -> Optional[Dict[str, Any]]:
        """Remove MUD banners, ASCII art, and decorative noise.

        Strips login prompts, title screens, weather spam, and other
        deterministic verbose output that doesn't aid gameplay.
        """
        if isinstance(result, dict) and "content" in result:
            content = result["content"]
        else:
            return None

        original_tokens = self._estimate_tokens(content)
        stripped = content

        # Strip banner lines: rows of repeated symbols
        stripped = re.sub(r"^[=\-]{10,}\s*$", "", stripped, flags=re.MULTILINE)

        # Strip decoration lines: mostly non-alphanumeric characters
        lines = stripped.split("\n")
        filtered = []
        for line in lines:
            # Lines that are mostly stars/equals/dashes with optional text (e.g., "*** Banner ***")
            if re.match(r"^\s*[\*#@=\-]{3,}.*[\*#@=\-]{3,}\s*$", line):
                continue  # Skip pure decoration
            filtered.append(line)

        stripped = "\n".join(filtered)

        # Strip excessive blank lines (3+ becomes 2)
        stripped = re.sub(r"\n{3,}", "\n\n", stripped)

        new_tokens = self._estimate_tokens(stripped)
        if new_tokens < original_tokens:
            saved = original_tokens - new_tokens
            self._log_event(
                "tokens.banner_stripped",
                tool=name,
                before_tokens=original_tokens,
                after_tokens=new_tokens,
                saved=saved,
            )
            result["content"] = stripped
            return result

        return None

    def collapse_failures(
        self,
        actor: Any,
        name: str,
        args: Dict[str, Any],
        result: Any,
    ) -> Optional[Dict[str, Any]]:
        """Collapse repeated identical errors.

        If a tool result is an error and matches the last error seen this turn,
        replace with a note: "(same error, 3rd time)".

        Note: This is a simple implementation. A full version would track
        per-turn error history and collapse across the turn.
        """
        if isinstance(result, dict) and result.get("ok") is True:
            return None  # Not an error

        # Check if this is an error-like result
        content = result.get("content", "") if isinstance(result, dict) else str(result)
        if not content or len(content) < 10:
            return None

        # For now, stub this — we'd need per-turn state tracking to do it properly.
        # Leaving a hook structure for future implementation.
        return None

    @staticmethod
    def _parse_look(text: Any) -> tuple[str, list[str], str]:
        """Parse look output into (name, exits, description).

        Reuses NavigationTracker's parsing logic.
        """
        if isinstance(text, dict):
            text = text.get("content", "")
        if not isinstance(text, str):
            raise ValueError("look result is not a string")

        lines = text.strip().split("\n")
        if not lines:
            raise ValueError("Empty look output")

        name = lines[0].strip()

        exits: list[str] = []
        description_lines: list[str] = []

        for line in lines[1:]:
            match = re.search(r"\[\s*Exits:\s*([^\]]+)\]", line, re.IGNORECASE)
            if match:
                exits_str = match.group(1)
                # Split on comma or space, and strip commas
                raw_exits = re.split(r"[,\s]+", exits_str)
                exits = [d.lower() for d in raw_exits if d.strip() and d.lower() not in ("", ",")]
                continue

            if line.strip():
                description_lines.append(line)

        if not exits:
            raise ValueError("No exits line found in look output")

        description = "\n".join(description_lines[:20])
        if not description:
            raise ValueError("No description text found")

        return name, exits, description

    def _store_default_summary(self, room_id: str, name: str, exits: list[str]) -> None:
        """Store a default summary for a first-visit room."""
        exits_str = ", ".join(exits[:4]) if exits else "none"
        summary = f"{name}. Exits: {exits_str}."
        self.world_db.update_room_summary(room_id, summary)

    def _generate_summary(self, name: str, visit_count: int, exits: list[str]) -> str:
        """Generate a compact repeat-visit summary."""
        exits_str = ", ".join(exits[:4]) if exits else "none"
        return f"{name} (visited {visit_count}x). Exits: {exits_str}. Nothing new."

    @staticmethod
    def _estimate_tokens(text: Any) -> int:
        """Rough token estimate: ~4 chars per token (OpenAI rule of thumb)."""
        if isinstance(text, dict):
            text = text.get("content", "")
        if not isinstance(text, str):
            text = str(text)
        return max(1, len(text) // 4)

    def _log_event(self, phase: str, **kwargs) -> None:
        """Log a compression event."""
        if self.logger:
            self.logger.event(phase, **kwargs)
        else:
            # Fallback: stderr
            print(f"[compress] {phase}: {kwargs}", file=sys.stderr)
