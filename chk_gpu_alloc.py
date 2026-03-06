
import subprocess, os

# 1. GPU libs mapped in main.py
r1 = subprocess.run(
    "cat /proc/16598/maps 2>/dev/null | grep -i 'cuda\\|nvidia\\|torch' | awk '{print }' | sort -u",
    shell=True, capture_output=True, text=True
)
print("=== GPU libs in main.py (PID 16598) ===")
print(r1.stdout or "none")

# 2. GPU-touching code in agent .py files
r2 = subprocess.run(
    "grep -rn 'import torch\\|import cv2\\|from diffus\\|cuda\\|image_gen\\|visual_renderer' /home/remvelchio/agent/*.py | grep -v '.venv'",
    shell=True, capture_output=True, text=True
)
print("\n=== GPU-touching imports in agent ===")
print(r2.stdout or "none")

# 3. Headers of visual_renderer and image_gen
r3 = subprocess.run(
    "head -50 /home/remvelchio/agent/visual_renderer.py",
    shell=True, capture_output=True, text=True
)
print("\n=== visual_renderer.py top 50 ===")
print(r3.stdout or "none")

r4 = subprocess.run(
    "head -50 /home/remvelchio/agent/image_gen.py",
    shell=True, capture_output=True, text=True
)
print("\n=== image_gen.py top 50 ===")
print(r4.stdout or "none")
