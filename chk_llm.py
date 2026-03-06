
import sys, os
sys.path.insert(0, "/home/remvelchio/agent")
os.chdir("/home/remvelchio/agent")

from anchor_cycler import AnchorCycler
import yaml

with open("config.yaml") as f:
    config = yaml.safe_load(f)

anchors = config["anchors"]["cycle_order"]
cycler = AnchorCycler(anchors)

# Print LLM config
print("LLM url  :", getattr(cycler, "llm_url", None) or getattr(cycler, "_llm_url", None))
print("LLM model:", getattr(cycler, "model", None) or getattr(cycler, "_model", None))
print("timeout  :", getattr(cycler, "timeout", None) or getattr(cycler, "_timeout", None))
print("LLM attrs:", [a for a in dir(cycler) if "llm" in a.lower() or "model" in a.lower() or "url" in a.lower() or "timeout" in a.lower() or "host" in a.lower()])
