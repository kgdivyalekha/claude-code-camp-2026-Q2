"""Test smart navigation using world.db (M9 feature).

Smart navigation saves tokens by:
1. Avoiding blind exploration of known areas
2. Using cached directions to reach known rooms
3. Providing navigation hints to the agent
"""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from boukensha.navigation import NavigationAssistant
from boukensha.world.db import WorldDB


class TestNavigationAssistant:
    """Test NavigationAssistant for smart pathfinding."""

    @pytest.fixture
    def world_db_with_rooms(self):
        """Create a test world.db with some rooms and exits."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "world.db"
            world_db = WorldDB(str(db_path))

            # Create a small test world:
            # Market Square -> north -> Temple
            # Market Square -> east -> Garden
            # Temple -> south -> Market Square
            # Garden -> west -> Market Square

            market = world_db.add_room(
                name="Market Square",
                signature="market_001",
                description="A bustling marketplace."
            )
            temple = world_db.add_room(
                name="Temple",
                signature="temple_001",
                description="A sacred temple."
            )
            garden = world_db.add_room(
                name="Garden",
                signature="garden_001",
                description="A beautiful garden."
            )

            # Add exits
            world_db.add_exit(market, "north", temple)
            world_db.add_exit(temple, "south", market)
            world_db.add_exit(market, "east", garden)
            world_db.add_exit(garden, "west", market)

            yield world_db

    def test_get_navigation_hint_direct_path(self, world_db_with_rooms):
        """Should return navigation hint for directly connected rooms."""
        nav = NavigationAssistant(world_db=world_db_with_rooms)

        # Market to Temple (north)
        hint = nav.get_navigation_hint(
            current_room_name="Market Square",
            destination_room_name="Temple",
            current_room_signature="market_001",
            destination_room_signature="temple_001"
        )

        assert hint is not None
        assert "north" in hint.lower()

    def test_get_navigation_hint_multi_hop(self, world_db_with_rooms):
        """Should return path through multiple rooms."""
        nav = NavigationAssistant(world_db=world_db_with_rooms)

        # Garden to Temple (west to Market, then north to Temple)
        hint = nav.get_navigation_hint(
            current_room_name="Garden",
            destination_room_name="Temple",
            current_room_signature="garden_001",
            destination_room_signature="temple_001"
        )

        assert hint is not None
        assert "west" in hint.lower()
        assert "north" in hint.lower()

    def test_get_navigation_hint_same_room(self, world_db_with_rooms):
        """Should return empty path for same room."""
        nav = NavigationAssistant(world_db=world_db_with_rooms)

        hint = nav.get_navigation_hint(
            current_room_name="Market Square",
            destination_room_name="Market Square",
            current_room_signature="market_001",
            destination_room_signature="market_001"
        )

        # Empty path returns None or empty hint
        assert hint is None or hint == "Go"

    def test_get_navigation_hint_unreachable(self, world_db_with_rooms):
        """Should return None for unreachable rooms."""
        nav = NavigationAssistant(world_db=world_db_with_rooms)

        # Add an isolated room with no exits
        isolated = world_db_with_rooms.add_room(
            name="Isolated Room",
            signature="isolated_001",
            description="Unreachable."
        )

        hint = nav.get_navigation_hint(
            current_room_name="Market Square",
            destination_room_name="Isolated Room",
            current_room_signature="market_001",
            destination_room_signature="isolated_001"
        )

        # Should return None (no path)
        assert hint is None

    def test_format_navigation_context(self, world_db_with_rooms):
        """Should provide formatted context about current location."""
        nav = NavigationAssistant(world_db=world_db_with_rooms)

        context = nav.format_navigation_context(
            current_room_name="Market Square",
            current_room_signature="market_001"
        )

        assert context is not None
        assert "Market Square" in context
        assert "north" in context.lower()
        assert "east" in context.lower()

    def test_get_all_known_rooms(self, world_db_with_rooms):
        """Should return all known rooms from world.db."""
        nav = NavigationAssistant(world_db=world_db_with_rooms)

        rooms = nav.get_all_known_rooms()

        assert len(rooms) == 3
        assert "market_001" in rooms
        assert "temple_001" in rooms
        assert "garden_001" in rooms
        assert rooms["market_001"]["name"] == "Market Square"

    def test_suggest_exploration_path(self, world_db_with_rooms):
        """Should suggest nearest unexplored exit."""
        nav = NavigationAssistant(world_db=world_db_with_rooms)

        # Add an unexplored exit from Market Square
        market_id = world_db_with_rooms.conn.execute(
            "SELECT id FROM rooms WHERE signature = ?",
            ("market_001",)
        ).fetchone()[0]

        # Add exit without target (unexplored)
        world_db_with_rooms.conn.execute(
            "INSERT INTO exits (room_id, direction) VALUES (?, ?)",
            (market_id, "south")
        )
        world_db_with_rooms.conn.commit()

        suggestion = nav.suggest_exploration_path(
            current_room_signature="market_001"
        )

        assert suggestion is not None
        assert "south" in suggestion.lower()

    def test_graceful_error_handling(self):
        """Should handle missing world.db gracefully."""
        nav = NavigationAssistant(world_db=None)

        # All methods should return None without crashing
        assert nav.get_navigation_hint("A", "B") is None
        assert nav.format_navigation_context("A") is None
        assert nav.get_all_known_rooms() == {}
        assert nav.suggest_exploration_path() is None

    def test_navigation_saves_tokens(self, world_db_with_rooms):
        """Verify smart navigation provides efficient paths."""
        nav = NavigationAssistant(world_db=world_db_with_rooms)

        # Direct path (1 move)
        hint1 = nav.get_navigation_hint(
            current_room_name="Market Square",
            destination_room_name="Temple",
            current_room_signature="market_001",
            destination_room_signature="temple_001"
        )

        # Multi-hop path (2 moves)
        hint2 = nav.get_navigation_hint(
            current_room_name="Garden",
            destination_room_name="Temple",
            current_room_signature="garden_001",
            destination_room_signature="temple_001"
        )

        # Both should provide hints
        assert hint1 is not None
        assert hint2 is not None

        # Hint2 should be longer (more directions)
        assert len(hint2) > len(hint1)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
