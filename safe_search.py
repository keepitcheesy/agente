import json
import os
import re
import time
import urllib.parse
import urllib.request
from typing import List, Optional, Dict, Any

CACHE: Dict[str, Dict[str, Any]] = {}
CACHE_TTL = 3600

SENSITIVE_TERMS = [
    "sexual", "assault", "abuse", "exploitation", "trafficking",
    "violence", "minor", "child", "teen", "rape"
]

REDACTIONS = [
    (r"\brape\b", "sexual violence"),
    (r"\bsexual assault\b", "sexual violence"),
    (r"\bsexual abuse\b", "sexual violence"),
    (r"\bchild\b", "minor"),
    (r"\bteen(ager)?s?\b", "young people"),
]

BANNED_SNIPPET_TERMS = [
    "graphic", "explicit", "porn", "pornography", "gore",
    "beheading", "dismember", "torture", "suicide", "self-harm"
]

def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())

def is_sensitive_topic(text: str) -> bool:
    text = _normalize(text)
    return any(term in text for term in SENSITIVE_TERMS)

def _sanitize(text: str) -> str:
    out = text
    for pattern, repl in REDACTIONS:
        out = re.sub(pattern, repl, out, flags=re.IGNORECASE)
    return out

def _build_query(title: str, sensitive: bool) -> str:
    base = "policy response OR prevention OR intervention OR public safety"
    if sensitive:
        return f"{base} community services oversight program examples"
    return f"{base} recent examples"

def _fetch_serpapi(query: str, api_key: str, num: int = 5) -> Dict[str, Any]:
    params = {
        "engine": "google",
        "q": query,
        "num": num,
        "api_key": api_key
    }
    url = "https://serpapi.com/search.json?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.load(resp)

def _extract_safe_snippets(data: Dict[str, Any]) -> List[str]:
    out = []
    for item in data.get("organic_results", []):
        title = item.get("title") or ""
        snippet = item.get("snippet") or ""
        if not snippet:
            continue
        snippet_lower = snippet.lower()
        if any(bad in snippet_lower for bad in BANNED_SNIPPET_TERMS):
            continue
        text = f"{title}: {snippet}".strip()
        text = _sanitize(text)
        out.append(text)
        if len(out) >= 2:
            break
    return out

def get_policy_context(title: str, summary: Optional[str] = None) -> List[str]:
    api_key = os.environ.get("SERP_API_KEY")
    if not api_key:
        return []

    blob = f"{title} {summary or ''}"
    cache_key = _normalize(blob)[:200]
    now = time.time()
    cached = CACHE.get(cache_key)
    if cached and now - cached["ts"] < CACHE_TTL:
        return cached["data"]

    sensitive = is_sensitive_topic(blob)
    query = _build_query(title, sensitive)
    try:
        data = _fetch_serpapi(query, api_key)
        snippets = _extract_safe_snippets(data)
    except Exception:
        snippets = []

    CACHE[cache_key] = {"ts": now, "data": snippets}
    return snippets
