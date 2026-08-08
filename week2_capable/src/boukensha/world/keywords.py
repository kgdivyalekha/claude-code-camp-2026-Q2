"""Keyword extraction from room descriptions.

Extracts meaningful keywords from MUD room descriptions to enable
targeted exploration ("find the bakery", "where's the armoury?").
"""

import re
from typing import List, Set, Optional


class KeywordExtractor:
    """Extract keywords from room descriptions."""

    # Common MUD location keywords to look for
    LOCATION_KEYWORDS = {
        # Commerce & trade
        "bakery", "brewery", "market", "shop", "store", "vendor", "merchant",
        "stall", "counter", "alchemist", "apothecary", "blacksmith", "smith",
        "armory", "armoury", "weaponsmith", "leatherworker", "tailor",
        "jeweler", "goldsmith", "silversmith", "tinker", "pawnbroker",

        # Government & authority
        "palace", "castle", "tower", "keep", "fort", "fortress", "garrison",
        "courthouse", "jail", "prison", "barracks", "guard", "guard house",
        "gatehouse", "watchtower",

        # Religious
        "temple", "shrine", "altar", "cathedral", "chapel", "monastery",
        "church", "abbey", "cloister", "sanctum", "holy", "sacred",

        # Recreation & lodging
        "tavern", "bar", "inn", "hotel", "inn", "lodge", "hostel", "pub",
        "ale house", "alehouse", "saloon", "brothel", "gambling", "casino",
        "bath", "bathhouse", "spa",

        # Learning & culture
        "library", "university", "college", "academy", "school", "teacher",
        "scholar", "sage", "scribe", "bookshop", "archives", "museum",
        "theatre", "theater", "hall",

        # Nature & outdoors
        "forest", "woods", "meadow", "field", "plains", "grassland",
        "desert", "mountain", "hill", "valley", "river", "stream", "lake",
        "sea", "ocean", "beach", "shore", "coast", "cave", "cavern",
        "garden", "park", "grove", "thicket", "swamp", "marsh", "bog",

        # Urban & infrastructure
        "plaza", "square", "street", "road", "avenue", "alley", "lane",
        "bridge", "gate", "wall", "fountain", "well", "monument", "statue",
        "dock", "port", "wharf", "harbor", "harbour", "pier", "warehouse",
        "stable", "stables", "inn", "roadhouse", "way station",

        # Dangerous/mystical
        "crypt", "tomb", "grave", "graveyard", "cemetery", "catacombs",
        "dungeon", "lair", "ruin", "ruins", "ancient", "cursed", "evil",
        "dark", "shadow", "haunted", "spectral",

        # Other
        "entrance", "exit", "center", "centre", "corner", "room", "chamber",
        "hall", "corridor", "passage", "tunnel", "underground", "building",
    }

    # Words to ignore (too generic)
    IGNORE_WORDS = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "from",
        "is", "are", "be", "been", "have", "has", "do", "does", "did",
        "you", "i", "he", "she", "it", "we", "they", "what", "which",
        "this", "that", "these", "those", "of", "for", "with", "by",
        "about", "as", "if", "so", "out", "up", "down", "over", "under",
        "here", "there", "where", "when", "why", "how", "not", "no", "yes",
        "all", "each", "every", "both", "some", "any", "many", "much",
        "more", "most", "less", "least", "very", "too", "so", "just",
        "only", "also", "still", "even", "well", "good", "bad",
    }

    @classmethod
    def extract(
        cls,
        description: str,
        room_name: str = "",
        limit: int = 10,
        min_length: int = 3,
    ) -> List[str]:
        """Extract keywords from a room description.

        Args:
            description: Full room description text
            room_name: Room name (checked first)
            limit: Maximum keywords to extract
            min_length: Minimum keyword length

        Returns:
            List of extracted keywords (lowercase)
        """
        if not description and not room_name:
            return []

        text = (room_name + " " + description).lower()

        # Extract words
        words = re.findall(r"\b[a-z]{3,}\b", text)

        # Filter for known keywords and ignore list
        keywords = set()
        for word in words:
            if (
                word in cls.LOCATION_KEYWORDS
                and word not in cls.IGNORE_WORDS
                and len(word) >= min_length
            ):
                keywords.add(word)

        return sorted(list(keywords))[:limit]

    @classmethod
    def extract_custom(
        cls,
        description: str,
        custom_keywords: Set[str],
        room_name: str = "",
    ) -> List[str]:
        """Extract keywords using custom keyword set.

        Args:
            description: Room description
            custom_keywords: Set of keywords to look for
            room_name: Room name

        Returns:
            List of found keywords
        """
        text = (room_name + " " + description).lower()
        words = re.findall(r"\b[a-z]{3,}\b", text)

        found = set()
        for word in words:
            if word in custom_keywords:
                found.add(word)

        return sorted(list(found))

    @classmethod
    def extract_noun_phrases(
        cls,
        description: str,
        limit: int = 5,
    ) -> List[str]:
        """Extract potential noun phrases (experimental).

        Looks for common patterns like "the <adj>* <noun>".

        Args:
            description: Room description
            limit: Maximum phrases

        Returns:
            List of noun phrases
        """
        phrases = []

        # Pattern: "the [adjective]* noun" or "a/an [adjective]* noun"
        pattern = r"\b(?:the|a|an)\s+(?:[a-z]+\s+)*([a-z]+)"
        matches = re.findall(pattern, description.lower())

        # Filter for reasonable lengths
        phrases = [m for m in matches if 3 <= len(m) <= 20]

        return phrases[:limit]


class KeywordTrie:
    """Simple trie for keyword matching (for faster lookups)."""

    def __init__(self, keywords: List[str]):
        """Initialize trie with keywords."""
        self.root = {}
        for keyword in keywords:
            self._insert(keyword)

    def _insert(self, word: str) -> None:
        """Insert word into trie."""
        node = self.root
        for char in word.lower():
            if char not in node:
                node[char] = {}
            node = node[char]
        node["$"] = True  # End marker

    def find_all_in_text(self, text: str) -> List[str]:
        """Find all keywords in text."""
        found = set()
        text_lower = text.lower()

        for i in range(len(text_lower)):
            node = self.root
            for j in range(i, len(text_lower)):
                char = text_lower[j]
                if char not in node:
                    break
                node = node[char]
                if "$" in node:
                    found.add(text_lower[i:j+1])

        return sorted(list(found))
