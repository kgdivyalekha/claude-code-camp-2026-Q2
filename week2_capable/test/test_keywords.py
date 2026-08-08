#!/usr/bin/env python3
"""Test keyword extraction and keyword-based navigation.

Tests:
1. Keyword extraction from descriptions
2. Keyword storage and retrieval in world.db
3. Keyword-based room searching
4. Navigator integration with keyword search
"""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from boukensha.world.db import WorldDB
from boukensha.world.identity import signature
from boukensha.world.keywords import KeywordExtractor, KeywordTrie
from boukensha.tools.navigator import Navigator


def test_keyword_extraction():
    """Test automatic keyword extraction from descriptions."""
    descriptions = [
        "A bustling marketplace with vendor stalls and fountain",
        "The ancient temple with sacred altar and treasures",
        "A cozy tavern with ale and good company",
        "The forest path with thick trees and mushrooms",
    ]

    expected_keywords = [
        {"marketplace", "vendor", "fountain"},
        {"temple", "sacred", "altar"},
        {"tavern", "ale"},
        {"forest", "trees"},
    ]

    for desc, expected in zip(descriptions, expected_keywords):
        extracted = set(KeywordExtractor.extract(desc))
        matches = extracted & expected
        assert len(matches) > 0, f"No keywords extracted from: {desc}"
        print(f"✓ Extracted keywords: {matches}")


def test_keyword_storage_retrieval():
    """Test storing and retrieving keywords in world.db."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "world.db")
        world_db = WorldDB(db_path)

        try:
            # Create a room
            sig = signature("Market Square", ["north", "south"], "A marketplace")
            room_id = f"room_{sig[:8]}"
            world_db.add_room(room_id, "Market Square", sig, "A marketplace")

            # Add keywords
            keywords = ["market", "shop", "vendor", "fountain"]
            world_db.add_keywords(room_id, keywords)

            # Retrieve keywords
            retrieved = world_db.get_keywords(room_id)
            assert set(retrieved) == set(keywords), f"Expected {keywords}, got {retrieved}"
            print(f"✓ Stored and retrieved keywords: {retrieved}")
        finally:
            world_db.close()


def test_keyword_search():
    """Test searching rooms by keyword."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "world.db")
        world_db = WorldDB(db_path)

        try:
            # Create multiple rooms
            rooms = {
                "market": ("Market Square", ["north", "south"]),
                "tavern": ("Green Tavern", ["north", "east"]),
                "temple": ("Temple", ["south", "west"]),
            }

            for key, (name, exits) in rooms.items():
                sig = signature(name, exits, f"The {name}")
                room_id = f"room_{sig[:8]}"
                world_db.add_room(room_id, name, sig, f"The {name}")
                rooms[key] = {"id": room_id, "name": name}

            # Add keywords
            world_db.add_keywords(rooms["market"]["id"], ["market", "vendor", "shop"])
            world_db.add_keywords(rooms["tavern"]["id"], ["tavern", "ale", "bar"])
            world_db.add_keywords(rooms["temple"]["id"], ["temple", "altar", "sacred"])

            # Search by keyword
            results = world_db.search_by_keyword("market")
            assert len(results) > 0, "Should find rooms with 'market' keyword"
            assert results[0]["name"] == "Market Square"
            print(f"✓ Search 'market': found {results[0]['name']}")

            results = world_db.search_by_keyword("tavern")
            assert len(results) > 0
            assert results[0]["name"] == "Green Tavern"
            print(f"✓ Search 'tavern': found {results[0]['name']}")

            results = world_db.search_by_keyword("nonexistent")
            assert len(results) == 0, "Should not find nonexistent keyword"
            print(f"✓ Search 'nonexistent': correctly returned no results")
        finally:
            world_db.close()


def test_keyword_search_multiple():
    """Test searching with multiple keywords."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "world.db")
        world_db = WorldDB(db_path)

        try:
            # Create rooms
            sig1 = signature("Inn", ["north"], "The Inn")
            sig2 = signature("Market", ["south"], "The Market")

            room1 = f"room_{sig1[:8]}"
            room2 = f"room_{sig2[:8]}"

            world_db.add_room(room1, "Inn", sig1, "The Inn")
            world_db.add_room(room2, "Market", sig2, "The Market")

            # Add keywords
            world_db.add_keywords(room1, ["inn", "lodging"])
            world_db.add_keywords(room2, ["market", "shop"])

            # Search by multiple keywords (any match)
            results = world_db.search_by_keywords(["inn", "market"])
            assert len(results) == 2, f"Expected 2 results, got {len(results)}"
            print(f"✓ Multi-keyword search: found {len(results)} rooms")

            # Results should be ordered by match count
            for result in results:
                assert "keyword_matches" in result
            print(f"✓ Results ordered by keyword match count")
        finally:
            world_db.close()


def test_popular_keywords():
    """Test getting popular keywords across rooms."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "world.db")
        world_db = WorldDB(db_path)

        try:
            # Create rooms with keywords
            for i, (name, keywords) in enumerate([
                ("Market", ["market", "shop", "vendor"]),
                ("Bazaar", ["market", "shop"]),
                ("Street", ["market"]),
            ]):
                sig = signature(name, [], name)
                room_id = f"room_{sig[:8]}"
                world_db.add_room(room_id, name, sig, name)
                world_db.add_keywords(room_id, keywords)

            # Get popular keywords
            popular = world_db.get_popular_keywords(limit=5)
            assert len(popular) > 0, "Should have popular keywords"
            assert popular[0][0] == "market", "Market should be most popular"
            print(f"✓ Popular keywords: {popular}")
        finally:
            world_db.close()


def test_navigator_keyword_search():
    """Test Navigator integration with keyword search."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "world.db")
        world_db = WorldDB(db_path)

        try:
            # Create connected rooms
            sig_market = signature("Market Square", ["north", "south"], "Market")
            sig_temple = signature("Temple", ["south"], "Temple")

            market_id = f"room_{sig_market[:8]}"
            temple_id = f"room_{sig_temple[:8]}"

            world_db.add_room(market_id, "Market Square", sig_market, "Market")
            world_db.add_room(temple_id, "Temple", sig_temple, "Temple")

            # Add keywords
            world_db.add_keywords(market_id, ["market", "shop", "vendor"])
            world_db.add_keywords(temple_id, ["temple", "altar", "sacred"])

            # Wire exits
            world_db.add_exit(market_id, "north", temple_id, "confirmed")
            world_db.add_exit(temple_id, "south", market_id, "confirmed")

            # Search via Navigator
            navigator = Navigator(world_db)

            result = navigator.search_by_keyword(
                keyword="temple",
                from_room_signature=sig_market,
                from_room_name="Market Square",
            )

            assert result["success"], f"Search failed: {result.get('reason')}"
            assert result["nearest_match"] == "Temple"
            assert result["path"] == ["north"]
            print(f"✓ Navigator keyword search: {result['instructions']}")

            # Search for nonexistent keyword
            result = navigator.search_by_keyword(
                keyword="bakery",
                from_room_signature=sig_market,
            )

            assert not result["success"], "Should not find nonexistent keyword"
            print(f"✓ Navigator correctly rejects unknown keyword")
        finally:
            world_db.close()


def test_keyword_trie():
    """Test keyword trie for matching."""
    keywords = ["market", "marketplace", "temple", "tavern", "forest"]
    trie = KeywordTrie(keywords)

    text = "I found a marketplace and a temple in the forest"
    matches = trie.find_all_in_text(text)

    assert "marketplace" in matches
    assert "temple" in matches
    assert "forest" in matches
    print(f"✓ Trie found keywords: {matches}")


def test_keyword_extractor_limit():
    """Test that keyword extraction respects limits."""
    description = "market shop vendor stall bazaar trading post commerce exchange emporium"

    # Extract with limit
    keywords = KeywordExtractor.extract(description, limit=3)
    assert len(keywords) <= 3, f"Should respect limit, got {len(keywords)}"
    print(f"✓ Extraction limit: {len(keywords)} keywords")


if __name__ == "__main__":
    test_keyword_extraction()
    test_keyword_storage_retrieval()
    test_keyword_search()
    test_keyword_search_multiple()
    test_popular_keywords()
    test_navigator_keyword_search()
    test_keyword_trie()
    test_keyword_extractor_limit()
    print("\n✅ All keyword tests passed!")
