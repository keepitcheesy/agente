path = "/home/remvelchio/agent/image_gen.py"
with open(path, "r") as f:
    content = f.read()

old_line = "        ).to(self.device)"
new_lines = "        )\n        # Offload to CPU between generations - frees ~10GB VRAM for Ollama\n        self.pipe.enable_model_cpu_offload()"

if old_line in content:
    content = content.replace(old_line, new_lines, 1)
    with open(path, "w") as f:
        f.write(content)
    print("OK: cpu_offload patch applied")
    # verify
    with open(path) as f:
        for i, line in enumerate(f.readlines(), 1):
            if i <= 20: print(f"{i:3}: {line}", end="")
else:
    print("FAIL: target line not found")
    with open(path) as f:
        for i, line in enumerate(f.readlines(), 1):
            if i <= 20: print(f"{i:3}: {line}", end="")