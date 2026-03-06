
import urllib.request, json, time

host = "http://localhost:11434"

# 1. Check which models are loaded/running
try:
    with urllib.request.urlopen(host + "/api/ps", timeout=5) as r:
        ps = json.load(r)
    print("=== running models ===")
    for m in ps.get("models", []):
        print(" ", m.get("name"), "| size_vram:", m.get("size_vram"), "| expires:", m.get("expires_at"))
except Exception as e:
    print("ps error:", e)

# 2. Check available models
try:
    with urllib.request.urlopen(host + "/api/tags", timeout=5) as r:
        tags = json.load(r)
    print("\n=== available models ===")
    for m in tags.get("models", []):
        print(" ", m.get("name"), "| size:", m.get("size"))
except Exception as e:
    print("tags error:", e)

# 3. Quick ping with tiny prompt
print("\n=== ping test ===")
import os
model = os.environ.get("OLLAMA_MODEL", "mistral:latest")
payload = {"model": model, "prompt": "Say OK.", "stream": False, "options": {"num_predict": 5}}
try:
    t0 = time.time()
    req = urllib.request.Request(
        host + "/api/generate",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    print(f"response: {data.get('response','').strip()} [{time.time()-t0:.1f}s]")
except Exception as e:
    print("ping error:", e)
