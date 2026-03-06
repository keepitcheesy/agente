
path = "/home/remvelchio/agent/anchor_cycler.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

old = '            return text.strip()\n        except Exception as exc:\n            self.logger.warning("LLM commentary failed: %s", exc)'
new = '            if EIGENTRACE_AVAILABLE and anchor.name == "Anchor A":\n                self.last_vance_text = text.strip()\n            return text.strip()\n        except Exception as exc:\n            self.logger.warning("LLM commentary failed: %s", exc)'

if old in content:
    content = content.replace(old, new, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print("OK  vance text storage fixed")
    print("last_vance_text = text" in content or "last_vance_text = text.strip()" in content)
else:
    print("FAIL: string not found")
