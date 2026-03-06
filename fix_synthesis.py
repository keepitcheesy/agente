
path = "/home/remvelchio/agent/anchor_cycler.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

old = 'is_synthesis = self.phase == "synthesis"'
new = 'is_synthesis = self.phase in ("synthesis", "roundtable") and anchor.name == "Anchor E"'

if old in content:
    content = content.replace(old, new, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print("OK  synthesis trigger fixed")
    print("check:", new in content)
else:
    print("FAIL: string not found")
