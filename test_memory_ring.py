import re

def normalize_entity(text: str) -> str:
    text = text.lower()
    text = re.sub(r'[$,]', '', text)
    text = re.sub(r'(\d+)k\b', lambda m: str(int(m.group(1)) * 1000), text)
    text = re.sub(r'(\d+)m\b', lambda m: str(int(m.group(1)) * 1000000), text)
    text = re.sub(r"'s\b", '', text)
    return text.strip()

def extract_core_entities(title: str) -> set:
    stopwords = {"as", "in", "the", "a", "an", "over", "is", "here", "its", "yet", "new", "called", "amid"}
    normalized_title = normalize_entity(title)
    words = normalized_title.split()
    return {w for w in words if w not in stopwords and (len(w) > 3 or w.isdigit())}

def check_semantic_duplicate(title1: str, title2: str) -> float:
    ents1 = extract_core_entities(title1)
    ents2 = extract_core_entities(title2)
    if not ents1 or not ents2: 
        return 0.0
    intersection = ents1.intersection(ents2)
    union = ents1.union(ents2)
    return len(intersection) / len(union)

if __name__ == "__main__":
    titles = [
        "Bitcoin surges past $100,000 as institutional investors pile in",
        "Bitcoin price rockets above $100K amid institutional buying frenzy",
    ]

    print("=== THE BITCOIN TEST ===")
    btc1 = titles[0]
    btc2 = titles[1]
    score = check_semantic_duplicate(btc1, btc2)
    
    print(f"Headline A: {btc1}")
    print(f"Headline B: {btc2}")
    print(f"Entity Match Score: {score:.3f}")
    if score > 0.4:
        print("VERDICT: CATCH - Duplicate Detected.")
    else:
        print("VERDICT: FAIL - Duplicate Missed.")

