
path = "/home/remvelchio/agent/anchor_cycler.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Find what's actually around 'return text' and 'LLM commentary'
import re
for m in re.finditer(r'return text', content):
    start = max(0, m.start() - 60)
    end = min(len(content), m.end() + 120)
    print("FOUND:", repr(content[start:end]))
    print()
