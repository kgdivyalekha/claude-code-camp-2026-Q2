#!/usr/bin/env python3
"""Populate world.db with test data to verify map arrows rendering."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from boukensha.world.db import WorldDB
from datetime import datetime, timedelta

def populate_test_world():
    """Create a test world with rooms, exits, and movement history."""

    db = WorldDB(".boukensha/world.db")

    # Define rooms
    rooms_data = [
        {
            "id": "market",
            "name": "Market Square",
            "signature": "market_sig",
            "description": "A bustling market with merchants and crowds",
            "discovered_by": "test"
        },
        {
            "id": "temple",
            "name": "Sacred Temple",
            "signature": "temple_sig",
            "description": "An ancient temple with towering columns",
            "discovered_by": "test"
        },
        {
            "id": "forest",
            "name": "Dark Forest",
            "signature": "forest_sig",
            "description": "Dense trees block out the sunlight",
            "discovered_by": "test"
        },
        {
            "id": "tavern",
            "name": "The Friendly Tavern",
            "signature": "tavern_sig",
            "description": "A warm tavern with good ale and company",
            "discovered_by": "test"
        },
        {
            "id": "river",
            "name": "Crystal River",
            "signature": "river_sig",
            "description": "Clear water flows peacefully northward",
            "discovered_by": "test"
        }
    ]

    print("📍 Creating rooms...")
    for room in rooms_data:
        db.add_room(
            room["id"],
            room["name"],
            room["signature"],
            room["description"],
            confidence="probable",
            discovered_by=room["discovered_by"]
        )
        # Increment visit count to show repeat visits
        db.conn.execute("UPDATE rooms SET visit_count = visit_count + 3 WHERE id = ?", (room["id"],))
        db.conn.commit()
        print(f"  ✓ {room['name']}")

    # Define exits (bidirectional connections)
    exits_data = [
        ("market", "north", "temple", "confirmed"),
        ("temple", "south", "market", "confirmed"),
        ("market", "south", "tavern", "confirmed"),
        ("tavern", "north", "market", "confirmed"),
        ("market", "east", "river", "confirmed"),
        ("river", "west", "market", "confirmed"),
        ("market", "west", "forest", "confirmed"),
        ("forest", "east", "market", "confirmed"),
        ("temple", "east", None, "probable"),  # Unexplored exit
        ("forest", "north", None, "probable"),  # Unexplored exit
        ("river", "north", None, "probable"),   # Unexplored exit
    ]

    print("\n🚪 Creating exits...")
    for from_room, direction, to_room, confidence in exits_data:
        db.add_exit(from_room, direction, to_room, confidence)
        if to_room:
            print(f"  ✓ {from_room}: {direction} → {to_room}")
        else:
            print(f"  ✓ {from_room}: {direction} → (unexplored)")

    # Add navigation log entries to set current room
    print("\n📝 Creating navigation history...")
    session_id = "test_session_001"
    current_time = datetime.now().astimezone()

    movements = [
        ("market", "market", "look", True),   # Start at market
        ("market", "temple", "north", True),  # Move north
        ("temple", "market", "south", True),  # Move back
        ("market", "river", "east", True),    # Move east to river
        ("river", "market", "west", True),    # Move back to market
    ]

    for i, (from_room, to_room, direction, success) in enumerate(movements):
        timestamp = (current_time - timedelta(minutes=len(movements)-i)).isoformat()
        db.log_movement(
            session_id=session_id,
            actor="scout",
            turn=i+1,
            from_room_id=from_room,
            direction=direction,
            to_room_id=to_room,
            success=success,
        )
        print(f"  ✓ Move {i+1}: {from_room} → {to_room} ({direction})")

    print("\n✅ Test world populated!")
    print(f"   Rooms: 5")
    print(f"   Exits: 11 (9 confirmed, 3 unexplored)")
    print(f"   Session: {session_id}")
    print(f"   Current location: market")
    print("\n🗺️  Open map at:")
    print("   http://localhost:4567/sessions/test_session_001/map")

    db.close()

if __name__ == "__main__":
    try:
        populate_test_world()
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)
