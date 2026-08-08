"""WorldDB — persistent map database with safe concurrent access."""

import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from boukensha.db import open_db


class WorldDB:
    """Persistent MUD world map backed by SQLite.

    Rooms are identified by signature hash, not by name (tbaMUD reuses names).
    Exits are reconciled through reciprocity: moving back validates edge identity.
    Coordinates are NOT stored — they are computed at render time via BFS layering.
    """

    def __init__(self, db_path: str = ".boukensha/world.db"):
        self.db_path = db_path
        self.conn = open_db(db_path)
        self._init_schema()

    def _init_schema(self) -> None:
        """Create tables if they don't exist."""
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS rooms (
                id              TEXT PRIMARY KEY,
                name            TEXT NOT NULL,
                signature       TEXT NOT NULL,
                description     TEXT,
                summary         TEXT,
                keywords        TEXT,
                zone_guess      TEXT,
                confidence      TEXT NOT NULL DEFAULT 'probable',
                is_safe         INTEGER,
                first_seen      TEXT,
                last_seen       TEXT,
                visit_count     INTEGER DEFAULT 0,
                discovered_by   TEXT,
                notes           TEXT
            );""")

        # Add keywords column if it doesn't exist (migration for existing DBs)
        cursor = self.conn.execute("PRAGMA table_info(rooms)")
        columns = {row[1] for row in cursor.fetchall()}
        if 'keywords' not in columns:
            self.conn.execute("ALTER TABLE rooms ADD COLUMN keywords TEXT")
            self.conn.commit()

        # Continue with remaining tables
        self.conn.executescript("""

            CREATE TABLE IF NOT EXISTS keywords (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword         TEXT NOT NULL,
                room_id         TEXT NOT NULL REFERENCES rooms(id),
                extracted_from  TEXT,
                confidence      TEXT DEFAULT 'auto',
                added_at        TEXT
            );

            CREATE TABLE IF NOT EXISTS exits (
                room_id         TEXT NOT NULL REFERENCES rooms(id),
                direction       TEXT NOT NULL,
                target_room_id  TEXT REFERENCES rooms(id),
                confidence      TEXT NOT NULL DEFAULT 'probable',
                is_one_way      INTEGER DEFAULT 0,
                blocked_reason  TEXT,
                last_seen       TEXT,
                PRIMARY KEY (room_id, direction)
            );

            CREATE TABLE IF NOT EXISTS items (
                id              TEXT PRIMARY KEY,
                room_id         TEXT REFERENCES rooms(id),
                name            TEXT,
                item_type       TEXT,
                properties      TEXT,
                last_seen       TEXT
            );

            CREATE TABLE IF NOT EXISTS npcs (
                id              TEXT PRIMARY KEY,
                room_id         TEXT REFERENCES rooms(id),
                name            TEXT,
                level_guess     INTEGER,
                is_hostile      INTEGER,
                dialogue        TEXT,
                last_seen       TEXT
            );

            CREATE TABLE IF NOT EXISTS navigation_log (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id      TEXT,
                actor           TEXT,
                turn            INTEGER,
                from_room       TEXT REFERENCES rooms(id),
                direction       TEXT,
                to_room         TEXT REFERENCES rooms(id),
                success         INTEGER,
                reason          TEXT,
                at              TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_rooms_signature ON rooms(signature);
            CREATE INDEX IF NOT EXISTS idx_rooms_name ON rooms(name);
            CREATE INDEX IF NOT EXISTS idx_keywords_keyword ON keywords(keyword);
            CREATE INDEX IF NOT EXISTS idx_keywords_room ON keywords(room_id);
            CREATE INDEX IF NOT EXISTS idx_exits_target ON exits(target_room_id);
            CREATE INDEX IF NOT EXISTS idx_items_room ON items(room_id);
            CREATE INDEX IF NOT EXISTS idx_npcs_room ON npcs(room_id);
            CREATE INDEX IF NOT EXISTS idx_nav_log_session ON navigation_log(session_id);
            CREATE INDEX IF NOT EXISTS idx_nav_log_from_room ON navigation_log(from_room);
        """)
        self.conn.commit()

    # Room operations
    def add_room(
        self,
        room_id: str,
        name: str,
        signature: str,
        description: Optional[str] = None,
        confidence: str = "probable",
        discovered_by: Optional[str] = None,
    ) -> None:
        """Add or update a room."""
        now = datetime.now().astimezone().isoformat()
        self.conn.execute(
            """
            INSERT INTO rooms
            (id, name, signature, description, confidence, first_seen, last_seen, discovered_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                last_seen = ?, visit_count = visit_count + 1
            """,
            (room_id, name, signature, description, confidence, now, now, discovered_by, now),
        )
        self.conn.commit()

    def get_room(self, room_id: str) -> Optional[Dict[str, Any]]:
        """Get room by ID."""
        cursor = self.conn.execute(
            "SELECT id, name, signature, description, summary, zone_guess, confidence, "
            "is_safe, first_seen, last_seen, visit_count, discovered_by, notes "
            "FROM rooms WHERE id = ?",
            (room_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "name": row[1],
            "signature": row[2],
            "description": row[3],
            "summary": row[4],
            "zone_guess": row[5],
            "confidence": row[6],
            "is_safe": row[7],
            "first_seen": row[8],
            "last_seen": row[9],
            "visit_count": row[10],
            "discovered_by": row[11],
            "notes": row[12],
        }

    def get_rooms_by_signature(self, signature: str) -> List[Dict[str, Any]]:
        """Find all rooms matching a signature."""
        cursor = self.conn.execute(
            "SELECT id, name, signature, description, summary, zone_guess, confidence, "
            "is_safe, first_seen, last_seen, visit_count, discovered_by, notes "
            "FROM rooms WHERE signature = ? ORDER BY last_seen DESC",
            (signature,),
        )
        rooms = []
        for row in cursor.fetchall():
            rooms.append(
                {
                    "id": row[0],
                    "name": row[1],
                    "signature": row[2],
                    "description": row[3],
                    "summary": row[4],
                    "zone_guess": row[5],
                    "confidence": row[6],
                    "is_safe": row[7],
                    "first_seen": row[8],
                    "last_seen": row[9],
                    "visit_count": row[10],
                    "discovered_by": row[11],
                    "notes": row[12],
                }
            )
        return rooms

    def update_room_summary(self, room_id: str, summary: str) -> None:
        """Store a compressed summary for repeat visits."""
        self.conn.execute("UPDATE rooms SET summary = ? WHERE id = ?", (summary, room_id))
        self.conn.commit()

    # Exit operations
    def add_exit(
        self,
        from_room_id: str,
        direction: str,
        to_room_id: Optional[str] = None,
        confidence: str = "probable",
    ) -> None:
        """Add or update an exit."""
        now = datetime.now().astimezone().isoformat()
        self.conn.execute(
            """
            INSERT INTO exits
            (room_id, direction, target_room_id, confidence, last_seen)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(room_id, direction) DO UPDATE SET
                target_room_id = COALESCE(?, target_room_id),
                confidence = ?,
                last_seen = ?
            """,
            (from_room_id, direction, to_room_id, confidence, now, to_room_id, confidence, now),
        )
        self.conn.commit()

    def get_exits(self, room_id: str) -> Dict[str, Optional[str]]:
        """Get all exits from a room as {direction: target_room_id or None}."""
        cursor = self.conn.execute(
            "SELECT direction, target_room_id FROM exits WHERE room_id = ?",
            (room_id,),
        )
        return {row[0]: row[1] for row in cursor.fetchall()}

    def get_exit_by_direction(self, from_room_id: str, direction: str) -> Optional[str]:
        """Get target room ID for a specific direction, or None if not yet traversed."""
        cursor = self.conn.execute(
            "SELECT target_room_id FROM exits WHERE room_id = ? AND direction = ?",
            (from_room_id, direction),
        )
        row = cursor.fetchone()
        return row[0] if row else None

    def confirm_exit(self, from_room_id: str, direction: str, to_room_id: str) -> None:
        """Mark an exit as confirmed (moved successfully).

        Updates both target_room_id (in case it was NULL) and confidence.
        """
        self.conn.execute(
            "UPDATE exits SET target_room_id = ?, confidence = 'confirmed' "
            "WHERE room_id = ? AND direction = ?",
            (to_room_id, from_room_id, direction),
        )
        self.conn.commit()

    def block_exit(self, from_room_id: str, direction: str, reason: str) -> None:
        """Mark an exit as blocked (e.g., 'locked', 'not an exit')."""
        now = datetime.now().astimezone().isoformat()
        self.conn.execute(
            "UPDATE exits SET blocked_reason = ?, last_seen = ? "
            "WHERE room_id = ? AND direction = ?",
            (reason, now, from_room_id, direction),
        )
        self.conn.commit()

    # Navigation log
    def log_movement(
        self,
        session_id: str,
        actor: str,
        turn: int,
        from_room_id: str,
        direction: str,
        to_room_id: str,
        success: bool,
        reason: Optional[str] = None,
    ) -> None:
        """Record a movement attempt."""
        now = datetime.now().astimezone().isoformat()
        self.conn.execute(
            """
            INSERT INTO navigation_log
            (session_id, actor, turn, from_room, direction, to_room, success, reason, at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (session_id, actor, turn, from_room_id, direction, to_room_id, int(success), reason, now),
        )
        self.conn.commit()

    # Utility
    def room_count(self) -> int:
        """Total rooms discovered."""
        cursor = self.conn.execute("SELECT COUNT(*) FROM rooms")
        return cursor.fetchone()[0]

    def all_rooms(self) -> List[Dict[str, Any]]:
        """Get all rooms (for rendering, analytics)."""
        cursor = self.conn.execute(
            "SELECT id, name, signature, description, summary, zone_guess, confidence, "
            "is_safe, first_seen, last_seen, visit_count, discovered_by, notes FROM rooms "
            "ORDER BY last_seen DESC"
        )
        rooms = []
        for row in cursor.fetchall():
            rooms.append(
                {
                    "id": row[0],
                    "name": row[1],
                    "signature": row[2],
                    "description": row[3],
                    "summary": row[4],
                    "zone_guess": row[5],
                    "confidence": row[6],
                    "is_safe": row[7],
                    "first_seen": row[8],
                    "last_seen": row[9],
                    "visit_count": row[10],
                    "discovered_by": row[11],
                    "notes": row[12],
                }
            )
        return rooms

    # Keyword operations
    def add_keywords(
        self,
        room_id: str,
        keywords: List[str],
        extracted_from: str = "description",
        confidence: str = "auto",
    ) -> None:
        """Add keywords to a room.

        Args:
            room_id: Room ID
            keywords: List of keywords (e.g., ["fountain", "plaza", "market"])
            extracted_from: Source of keywords ("description", "name", "manual")
            confidence: Confidence level ("auto", "manual")
        """
        now = datetime.now().astimezone().isoformat()

        for keyword in keywords:
            keyword_lower = keyword.lower().strip()
            if keyword_lower:
                self.conn.execute(
                    """
                    INSERT INTO keywords
                    (keyword, room_id, extracted_from, confidence, added_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (keyword_lower, room_id, extracted_from, confidence, now),
                )

        # Store comma-separated keywords in room
        keywords_str = ", ".join(keywords)
        self.conn.execute(
            "UPDATE rooms SET keywords = ? WHERE id = ?",
            (keywords_str, room_id),
        )
        self.conn.commit()

    def get_keywords(self, room_id: str) -> List[str]:
        """Get all keywords for a room."""
        cursor = self.conn.execute(
            "SELECT keyword FROM keywords WHERE room_id = ? ORDER BY keyword",
            (room_id,),
        )
        return [row[0] for row in cursor.fetchall()]

    def search_by_keyword(self, keyword: str) -> List[Dict[str, Any]]:
        """Find all rooms matching a keyword.

        Args:
            keyword: Keyword to search for (case-insensitive)

        Returns:
            List of room dicts matching the keyword
        """
        keyword_lower = keyword.lower()
        cursor = self.conn.execute(
            """
            SELECT DISTINCT r.id, r.name, r.signature, r.description,
                   r.summary, r.zone_guess, r.confidence,
                   r.is_safe, r.first_seen, r.last_seen, r.visit_count,
                   r.discovered_by, r.notes
            FROM rooms r
            JOIN keywords k ON r.id = k.room_id
            WHERE k.keyword LIKE ?
            ORDER BY r.visit_count DESC
            """,
            (f"%{keyword_lower}%",),
        )

        rooms = []
        for row in cursor.fetchall():
            rooms.append({
                "id": row[0],
                "name": row[1],
                "signature": row[2],
                "description": row[3],
                "summary": row[4],
                "zone_guess": row[5],
                "confidence": row[6],
                "is_safe": row[7],
                "first_seen": row[8],
                "last_seen": row[9],
                "visit_count": row[10],
                "discovered_by": row[11],
                "notes": row[12],
            })
        return rooms

    def search_by_keywords(self, keywords: List[str]) -> List[Dict[str, Any]]:
        """Find rooms matching any of the given keywords.

        Args:
            keywords: List of keywords to search for

        Returns:
            List of room dicts, grouped by match count
        """
        if not keywords:
            return []

        placeholders = ",".join("?" * len(keywords))
        keywords_lower = [k.lower() for k in keywords]

        cursor = self.conn.execute(
            f"""
            SELECT r.id, r.name, r.signature, r.description,
                   r.summary, r.zone_guess, r.confidence,
                   r.is_safe, r.first_seen, r.last_seen, r.visit_count,
                   r.discovered_by, r.notes, COUNT(k.keyword) as match_count
            FROM rooms r
            JOIN keywords k ON r.id = k.room_id
            WHERE k.keyword IN ({placeholders})
            GROUP BY r.id
            ORDER BY match_count DESC, r.visit_count DESC
            """,
            keywords_lower,
        )

        rooms = []
        for row in cursor.fetchall():
            room_dict = {
                "id": row[0],
                "name": row[1],
                "signature": row[2],
                "description": row[3],
                "summary": row[4],
                "zone_guess": row[5],
                "confidence": row[6],
                "is_safe": row[7],
                "first_seen": row[8],
                "last_seen": row[9],
                "visit_count": row[10],
                "discovered_by": row[11],
                "notes": row[12],
                "keyword_matches": row[13],
            }
            rooms.append(room_dict)
        return rooms

    def get_popular_keywords(self, limit: int = 20) -> List[Tuple[str, int]]:
        """Get most common keywords across all rooms.

        Args:
            limit: Maximum keywords to return

        Returns:
            List of (keyword, room_count) tuples
        """
        cursor = self.conn.execute(
            """
            SELECT keyword, COUNT(DISTINCT room_id) as room_count
            FROM keywords
            GROUP BY keyword
            ORDER BY room_count DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [(row[0], row[1]) for row in cursor.fetchall()]

    def close(self) -> None:
        """Close the database connection."""
        if self.conn:
            self.conn.close()

    def __enter__(self) -> "WorldDB":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
