#!/usr/bin/env python3
"""Keyword-based exploration demo: Find locations by type.

Shows:
1. Automatic keyword extraction from room descriptions
2. Keyword storage in world.db
3. Searching for rooms by keyword (e.g., "find the bakery")
4. Navigating to keyword-matched rooms
5. Natural language landmark queries
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from boukensha.world.db import WorldDB
from boukensha.world.identity import signature
from boukensha.world.keywords import KeywordExtractor
from boukensha.tools.navigator import Navigator


def create_diverse_world() -> tuple[WorldDB, dict]:
    """Create a world with diverse landmark-based locations."""
    db_path = tempfile.mktemp(suffix=".db")
    world_db = WorldDB(db_path)

    # Define rooms with rich descriptions
    locations = [
        {
            "name": "Town Square",
            "description": "A bustling plaza with fountain and market stalls",
            "keywords": ["plaza", "fountain", "market", "center"],
            "exits": ["north", "south", "east", "west"],
        },
        {
            "name": "Baker's Shop",
            "description": "Aroma of fresh bread and pastries, ovens warm the shop",
            "keywords": ["bakery", "shop", "baker", "food"],
            "exits": ["south"],
        },
        {
            "name": "Armorer's Hall",
            "description": "Clanging of hammers, racks of armor and weapons gleam",
            "keywords": ["armory", "armoury", "smithy", "weapons"],
            "exits": ["south"],
        },
        {
            "name": "Temple of Wisdom",
            "description": "Sacred altar with holy candles, marble columns tower",
            "keywords": ["temple", "sacred", "altar", "holy"],
            "exits": ["south", "east"],
        },
        {
            "name": "Green Tavern",
            "description": "Cozy tavern with ale, hearth fire, and friendly folk",
            "keywords": ["tavern", "bar", "ale", "inn"],
            "exits": ["north", "west"],
        },
        {
            "name": "Dark Forest",
            "description": "Ancient trees block sunlight, mushrooms grow wild",
            "keywords": ["forest", "woods", "trees", "nature"],
            "exits": ["north", "east"],
        },
        {
            "name": "Grand Library",
            "description": "Shelves of books, scholars reading, quiet atmosphere",
            "keywords": ["library", "books", "scholar", "knowledge"],
            "exits": ["west"],
        },
        {
            "name": "Apothecary Shop",
            "description": "Bottles of potions, herbs drying, mysterious smells",
            "keywords": ["apothecary", "potion", "herbs", "magic"],
            "exits": ["west"],
        },
    ]

    rooms = {}
    for loc in locations:
        sig = signature(loc["name"], loc["exits"], loc["description"][:80])
        room_id = f"room_{sig[:8]}"
        rooms[loc["name"]] = {"id": room_id, "name": loc["name"]}

        world_db.add_room(room_id, loc["name"], sig, loc["description"])
        world_db.add_keywords(room_id, loc["keywords"])

    # Wire connections: roughly in a star pattern from Town Square
    connections = [
        ("Town Square", "north", "Baker's Shop"),
        ("Baker's Shop", "south", "Town Square"),
        ("Town Square", "north", "Armorer's Hall"),  # Alternative north
        ("Armorer's Hall", "south", "Town Square"),
        ("Town Square", "east", "Temple of Wisdom"),
        ("Temple of Wisdom", "west", "Town Square"),
        ("Temple of Wisdom", "east", "Grand Library"),
        ("Grand Library", "west", "Temple of Wisdom"),
        ("Town Square", "south", "Green Tavern"),
        ("Green Tavern", "north", "Town Square"),
        ("Green Tavern", "west", "Apothecary Shop"),
        ("Apothecary Shop", "east", "Green Tavern"),
        ("Town Square", "west", "Dark Forest"),
        ("Dark Forest", "east", "Town Square"),
    ]

    for from_name, direction, to_name in connections:
        if from_name in rooms and to_name in rooms:
            world_db.add_exit(
                rooms[from_name]["id"],
                direction,
                rooms[to_name]["id"],
                "confirmed"
            )

    print("Created world with 8 landmark locations")
    print("Landmarks: Bakery, Armory, Temple, Tavern, Forest, Library, Apothecary\n")

    return world_db, rooms


def demo_keyword_extraction():
    """Show keyword extraction from descriptions."""
    print("=" * 70)
    print("DEMO 1: Keyword Extraction from Descriptions")
    print("=" * 70 + "\n")

    descriptions = [
        ("Baker's Shop", "Aroma of fresh bread and pastries, ovens warm the shop"),
        ("Armorer's Hall", "Clanging of hammers, racks of armor and weapons gleam"),
        ("Temple", "Sacred altar with holy candles, marble columns tower"),
        ("Tavern", "Cozy tavern with ale, hearth fire, and friendly folk"),
    ]

    for name, desc in descriptions:
        keywords = KeywordExtractor.extract(desc, limit=5)
        print(f"{name:20} → {keywords}")

    print()


def demo_keyword_search(world_db: WorldDB, rooms: dict):
    """Demo searching for landmarks by keyword."""
    print("=" * 70)
    print("DEMO 2: Searching for Landmarks by Keyword")
    print("=" * 70 + "\n")

    navigator = Navigator(world_db)
    current_room = rooms["Town Square"]

    searches = [
        ("bakery", "Looking for fresh bread"),
        ("armory", "Need new armor"),
        ("tavern", "Time for a drink"),
        ("library", "Research some knowledge"),
        ("potion", "Need healing supplies"),
    ]

    for keyword, reason in searches:
        print(f"Query: '{keyword}' ({reason})")

        result = navigator.search_by_keyword(
            keyword=keyword,
            from_room_signature=current_room["sig"],
            from_room_name=current_room["name"],
        )

        if result["success"]:
            if "nearest_match" in result:
                print(f"  ✓ Found: {result['nearest_match']}")
                print(f"    Distance: {result['distance']} moves")
                print(f"    Route: {' → '.join(result['path'])}")
                print(f"    {result['instructions']}")
            elif "matches_found" in result:
                print(f"  ✓ Found {result['matches_found']} matching location(s)")
                print(f"    {result.get('reason', 'Cannot compute exact route')}")
            else:
                print(f"  ✓ Search succeeded: {len(result.get('matches', []))} locations")
        else:
            print(f"  ✗ {result['reason']}")
        print()


def demo_natural_language_queries(world_db: WorldDB, rooms: dict):
    """Demo natural language landmark queries."""
    print("=" * 70)
    print("DEMO 3: Natural Language Landmark Queries")
    print("=" * 70 + "\n")

    navigator = Navigator(world_db)
    current_room = rooms["Town Square"]

    queries = [
        "Where can I get food?",
        "I need weapons and armor",
        "Let's go pray at a sacred place",
        "Need to study some books",
        "What about magical supplies?",
    ]

    for query in queries:
        print(f"Query: \"{query}\"")

        result = navigator.suggest_landmark_search(
            query=query,
            from_room_signature=current_room["sig"],
        )

        if result["success"]:
            print(f"  Keywords identified: {result['keywords_searched']}")
            for res in result["results"]:
                print(f"    • {res['keyword']}: {res['nearest']} ({res['match_count']} matches)")
        else:
            print(f"  {result['reason']}")
        print()


def demo_popular_landmarks(world_db: WorldDB):
    """Show most common landmark types in the world."""
    print("=" * 70)
    print("DEMO 4: Popular Landmark Types")
    print("=" * 70 + "\n")

    popular = world_db.get_popular_keywords(limit=10)

    print("Most common landmarks in the world:\n")
    for i, (keyword, count) in enumerate(popular, 1):
        bar = "█" * count + "░" * (10 - count)
        print(f"  {i:2}. {keyword:15} [{bar}] {count} location(s)")

    print()


def demo_exploration_by_interest(world_db: WorldDB, rooms: dict):
    """Demo exploring the world based on interests."""
    print("=" * 70)
    print("DEMO 5: Exploration by Interest")
    print("=" * 70 + "\n")

    navigator = Navigator(world_db)

    interests = [
        ("Combat focused", ["armory", "weapons", "smithy"]),
        ("Scholarly", ["library", "knowledge", "books"]),
        ("Hedonistic", ["tavern", "ale", "bar"]),
        ("Mystical", ["magic", "potion", "altar"]),
    ]

    for interest_name, keywords in interests:
        print(f"Interest: {interest_name}")
        print(f"  Seeking: {', '.join(keywords)}\n")

        for keyword in keywords:
            matches = world_db.search_by_keyword(keyword)
            if matches:
                print(f"    ✓ {keyword:12} → {matches[0]['name']}")
            else:
                print(f"    ✗ {keyword:12} → not found")
        print()


def main():
    print("\n" + "=" * 70)
    print("KEYWORD-BASED EXPLORATION DEMO")
    print("=" * 70 + "\n")

    world_db, rooms = create_diverse_world()

    # Add signature to each room for navigation
    for room_info in rooms.values():
        room_data = world_db.get_room(room_info["id"])
        room_info["sig"] = room_data["signature"]

    try:
        demo_keyword_extraction()
        demo_keyword_search(world_db, rooms)
        demo_natural_language_queries(world_db, rooms)
        demo_popular_landmarks(world_db)
        demo_exploration_by_interest(world_db, rooms)

        print("=" * 70)
        print("✅ KEYWORD SEARCH DEMONSTRATION COMPLETE")
        print("=" * 70)
        print()
        print("Key features demonstrated:")
        print("  ✓ Automatic keyword extraction from descriptions")
        print("  ✓ Keyword storage in world.db")
        print("  ✓ Searching for rooms by landmark type")
        print("  ✓ Automatic routing to matched landmarks")
        print("  ✓ Natural language query parsing")
        print("  ✓ Interest-based exploration")
        print()
        print("Token savings: Keyword search enables targeted exploration")
        print("  - Agents don't need to describe what they're looking for")
        print("  - No blind wandering searching for specific room types")
        print("  - Direct routing to landmarks")
        print()

    finally:
        world_db.close()


if __name__ == "__main__":
    main()
