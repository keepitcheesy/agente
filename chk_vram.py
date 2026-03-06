
import urllib.request, json

host = "http://localhost:11434"
with urllib.request.urlopen(host + "/api/ps", timeout=5) as r:
    ps = json.load(r)

for m in ps.get("models", []):
    name = m.get("name")
    size_vram = m.get("size_vram", 0)
    size_total = m.get("size", 0)
    details = m.get("details", {})
    print(f"model      : {name}")
    print(f"size_vram  : {size_vram / 1e9:.2f} GB  (in GPU)")
    print(f"size_total : {size_total / 1e9:.2f} GB  (total)")
    pct = (size_vram / size_total * 100) if size_total else 0
    print(f"gpu pct    : {pct:.1f}%")
    print(f"details    : {details}")
    print()

# also check nvidia-smi
import subprocess as sp
r = sp.run(["nvidia-smi", "--query-gpu=name,memory.total,memory.used,memory.free", "--format=csv,noheader"],
           capture_output=True, text=True)
print("=== nvidia-smi ===")
print(r.stdout or r.stderr or "nvidia-smi not available")
