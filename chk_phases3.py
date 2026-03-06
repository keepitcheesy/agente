
import re
with open("/home/remvelchio/agent/broadcast_pipeline.py", "r") as f:
    lines = f.readlines()
for i, line in enumerate(lines, 1):
    if "phase" in line and (":" in line or "=" in line):
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            print(f"{i:4}: {stripped}")
