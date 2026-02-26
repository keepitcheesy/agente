"""
Memory Ring — Persistent Story Deduplication

Two-layer dedup to prevent the broadcast from becoming a macro-loop:

Layer 1 (GUID Cache):
    Persistent JSON file mapping story GUIDs → timestamp.
    Survives restarts. 48-hour TTL auto-eviction.

Layer 2 (Semantic Dedup):
    Character trigram Jaccard similarity on titles.
    Catches "same event, different source" without needing
    an embedding model or API call.

    "OpenAI releases new model" vs "Sam Altman unveils new AI"
    → trigram overlap catches the shared structure.

Threshold: Jaccard > 0.45 on trigrams = same event.
"""

import json
import os
import re
import time
import logging
from typing import Optional, Dict, Tuple

logger = logging.getLogger(__name__)

CACHE_PATH = "/home/remvelchio/agent/tmp/seen_stories.json"
TTL_SECONDS = 48 * 3600  # 48 hours


def _load_cache() -> Dict:
    """Load the persistent cache from disk."""
    if not os.path.exists(CACHE_PATH):
        return {"guids": {}, "titles": {}}
    try:
        with open(CACHE_PATH, "r") as f:
            data = json.load(f)
        # Ensure both keys exist
        if "guids" not in data:
            data["guids"] = {}
        if "titles" not in data:
            data["titles"] = {}
        return data
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"Memory Ring: corrupt cache, resetting: {e}")
        return {"guids": {}, "titles": {}}


def _save_cache(cache: Dict) -> None:
    """Save cache to disk atomically."""
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    tmp_path = CACHE_PATH + ".tmp"
    try:
        with open(tmp_path, "w") as f:
            json.dump(cache, f, indent=1)
        os.replace(tmp_path, CACHE_PATH)
    except IOError as e:
        logger.error(f"Memory Ring: failed to save cache: {e}")


def _evict_expired(cache: Dict) -> int:
    """Remove entries older than TTL. Returns count evicted."""
    now = time.time()
    evicted = 0

    for section in ("guids", "titles"):
        expired = [
            key for key, ts in cache[section].items()
            if now - ts > TTL_SECONDS
        ]
        for key in expired:
            del cache[section][key]
            evicted += 1

    return evicted


def _normalize_title(title: str) -> str:
    """
    Normalize a headline for comparison:
    lowercase, strip punctuation, collapse whitespace.
    """
    title = title.lower().strip()
    title = re.sub(r"[^a-z0-9\s]", "", title)
    title = re.sub(r"\s+", " ", title)
    return title


def _trigrams(text: str) -> set:
    """Extract character trigrams from text."""
    if len(text) < 3:
        return {text}
    return {text[i:i+3] for i in range(len(text) - 2)}


def _trigram_jaccard(a: str, b: str) -> float:
    """
    Jaccard similarity of character trigrams between two strings.
    Returns 0.0 (completely different) to 1.0 (identical).
    """
    tri_a = _trigrams(a)
    tri_b = _trigrams(b)
    if not tri_a or not tri_b:
        return 0.0
    intersection = tri_a & tri_b
    union = tri_a | tri_b
    return len(intersection) / len(union)


# ---------------------------------------------------------------------------
# Semantic Similarity — Three-Signal Fusion
# ---------------------------------------------------------------------------
# Signal 1: Character trigrams (catches shared substrings)
# Signal 2: Word-level Jaccard (catches shared vocabulary)
# Signal 3: Entity overlap (catches shared proper nouns + numbers)
#
# A story is a duplicate if ANY signal exceeds its threshold,
# OR if the combined score exceeds the fusion threshold.
# ---------------------------------------------------------------------------

TRIGRAM_THRESHOLD = 0.42       # Slightly relaxed from 0.45
WORD_THRESHOLD = 0.50          # Half the words match
ENTITY_THRESHOLD = 0.60        # Core entities overlap
FUSION_THRESHOLD = 0.38        # Weighted average of all three

# Stop words to ignore in word comparison
_STOP_WORDS = frozenset([
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "can", "shall", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "about", "between",
    "through", "after", "before", "above", "below", "and", "but", "or",
    "not", "no", "if", "then", "than", "so", "its", "it", "this", "that",
    "new", "says", "said", "how", "what", "why", "who", "when", "where",
])


def _extract_keywords(title: str) -> set:
    """Extract meaningful words: strip stop words, keep entities and numbers."""
    norm = _normalize_title(title)
    words = set(norm.split())
    return words - _STOP_WORDS


def _extract_entities(title: str) -> set:
    """
    Extract likely named entities and numbers from a title.
    Heuristic: words that start with uppercase in the original,
    plus any numbers/dollar amounts.
    """
    entities = set()
    # Numbers and dollar amounts
    for m in re.finditer(r"\$?[\d][\d,\.]*[kKmMbB]?", title):
        entities.add(m.group().lower().replace(",", ""))
    # Capitalized words from original (before normalization)
    words = re.findall(r"[A-Z][a-zA-Z]{2,}", title)
    for w in words:
        if w.lower() not in _STOP_WORDS:
            entities.add(w.lower())
    return entities


def _word_jaccard(a: str, b: str) -> float:
    """Jaccard similarity of keyword sets."""
    kw_a = _extract_keywords(a)
    kw_b = _extract_keywords(b)
    if not kw_a or not kw_b:
        return 0.0
    intersection = kw_a & kw_b
    union = kw_a | kw_b
    return len(intersection) / len(union)


def _entity_overlap(title_a: str, title_b: str) -> float:
    """Overlap of named entities between two titles."""
    ent_a = _extract_entities(title_a)
    ent_b = _extract_entities(title_b)
    if not ent_a or not ent_b:
        return 0.0
    intersection = ent_a & ent_b
    union = ent_a | ent_b
    return len(intersection) / len(union)


def _compute_similarity(title_a: str, title_b: str, raw_a: str = "", raw_b: str = "") -> Tuple[float, float, float, float]:
    """
    Compute all three similarity signals and the fused score.
    Returns: (trigram_sim, word_sim, entity_sim, fused_score)
    """
    tri = _trigram_jaccard(_normalize_title(title_a), _normalize_title(title_b))
    word = _word_jaccard(title_a, title_b)
    ent = _entity_overlap(raw_a or title_a, raw_b or title_b)
    # Fusion: weighted average (entities matter most)
    fused = 0.25 * tri + 0.30 * word + 0.45 * ent
    return tri, word, ent, fused


def is_duplicate(guid: str, title: str) -> Tuple[bool, str]:
    """
    Check if a story is a duplicate using three-signal fusion.

    Args:
        guid: The story's unique identifier (URL or RSS id)
        title: The story's headline

    Returns:
        (is_dup, reason) — True + reason string if duplicate
    """
    cache = _load_cache()
    evicted = _evict_expired(cache)
    if evicted > 0:
        logger.debug(f"Memory Ring: evicted {evicted} expired entries")

    now = time.time()

    # Layer 1: Exact GUID match
    if guid in cache["guids"]:
        age_hours = (now - cache["guids"][guid]) / 3600
        return True, f"guid_seen_{age_hours:.1f}h_ago"

    # Layer 2: Three-signal semantic dedup
    norm_title = _normalize_title(title)
    if len(norm_title) > 10:
        best_fused = 0.0
        best_title = ""
        best_detail = ""

        for cached_title, ts in cache["titles"].items():
            tri, word, ent, fused = _compute_similarity(norm_title, cached_title, title, "")

            # Any single signal above threshold = duplicate
            if tri > TRIGRAM_THRESHOLD:
                age_hours = (now - ts) / 3600
                return True, f"trigram_dup_{tri:.2f}_vs_'{cached_title[:50]}' ({age_hours:.1f}h)"
            if word > WORD_THRESHOLD:
                age_hours = (now - ts) / 3600
                return True, f"word_dup_{word:.2f}_vs_'{cached_title[:50]}' ({age_hours:.1f}h)"
            if ent > ENTITY_THRESHOLD:
                age_hours = (now - ts) / 3600
                return True, f"entity_dup_{ent:.2f}_vs_'{cached_title[:50]}' ({age_hours:.1f}h)"

            if fused > best_fused:
                best_fused = fused
                best_title = cached_title
                best_detail = f"tri={tri:.2f} word={word:.2f} ent={ent:.2f}"

        # Fusion threshold
        if best_fused > FUSION_THRESHOLD:
            age_hours = (now - cache["titles"][best_title]) / 3600
            return True, f"fused_dup_{best_fused:.2f}[{best_detail}]_vs_'{best_title[:50]}' ({age_hours:.1f}h)"

    return False, "new"


def mark_seen(guid: str, title: str) -> None:
    """
    Mark a story as seen in the persistent cache.
    Call this AFTER the story has been accepted for broadcast.
    """
    cache = _load_cache()
    _evict_expired(cache)

    now = time.time()
    cache["guids"][guid] = now

    norm_title = _normalize_title(title)
    if len(norm_title) > 10:
        cache["titles"][norm_title] = now

    _save_cache(cache)
    logger.debug(f"Memory Ring: marked seen — guid={guid[:60]} title='{norm_title[:60]}'")


def get_stats() -> Dict:
    """Get cache statistics."""
    cache = _load_cache()
    _evict_expired(cache)
    return {
        "guids_cached": len(cache["guids"]),
        "titles_cached": len(cache["titles"]),
        "cache_path": CACHE_PATH,
        "ttl_hours": TTL_SECONDS / 3600,
    }


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("Memory Ring Self-Test")
    print("=" * 60)

    # Test Layer 1: GUID dedup
    print("\n--- Layer 1: GUID Dedup ---")
    dup, reason = is_duplicate("test-guid-001", "Test Story Alpha")
    print(f"First check:  dup={dup} reason={reason}")
    mark_seen("test-guid-001", "Test Story Alpha")
    dup, reason = is_duplicate("test-guid-001", "Test Story Alpha")
    print(f"Second check: dup={dup} reason={reason}")

    # Test Layer 2: Semantic dedup
    print("\n--- Layer 2: Semantic Dedup ---")
    titles = [
        ("guid-nyt", "OpenAI releases powerful new AI model called GPT-5"),
        ("guid-bbc", "Sam Altman unveils OpenAIs new GPT-5 artificial intelligence model"),
        ("guid-verge", "GPT-5 is here: OpenAI releases its most powerful AI model yet"),
        ("guid-different", "Tesla recalls 500,000 vehicles over autopilot safety concerns"),
        ("guid-crypto", "Bitcoin surges past $100,000 as institutional investors pile in"),
        ("guid-crypto2", "Bitcoin price rockets above $100K amid institutional buying frenzy"),
    ]

    # Mark first story as seen
    mark_seen(titles[0][0], titles[0][1])
    print(f"\nMarked as seen: '{titles[0][1]}'")
    print()

    for guid, title in titles[1:]:
        dup, reason = is_duplicate(guid, title)
        status = "DUPLICATE" if dup else "NEW"
        print(f"  {status:10s} | '{title[:65]}...'")
        if dup:
            print(f"  {'':10s} | Reason: {reason}")
        print()

    # Show trigram similarity matrix for the titles
    print("--- Trigram Similarity Matrix ---")
    norm_titles = [_normalize_title(t) for _, t in titles]
    short = [t[:40] for t in norm_titles]
    for i in range(len(norm_titles)):
        for j in range(i+1, len(norm_titles)):
            sim = _trigram_jaccard(norm_titles[i], norm_titles[j])
            flag = " <<<DUP" if sim > SIMILARITY_THRESHOLD else ""
            print(f"  {sim:.3f}{flag}  '{short[i]}' vs '{short[j]}'")

    # Show stats
    print(f"\n--- Cache Stats ---")
    stats = get_stats()
    for k, v in stats.items():
        print(f"  {k}: {v}")

    # Clean up test data
    if os.path.exists(CACHE_PATH):
        os.remove(CACHE_PATH)
        print("\nTest cache cleaned up.")
