import time
from pathlib import Path
import torch
from diffusers import AutoPipelineForText2Image

class ImageGenerator:
    def __init__(self, out_dir: str = "/home/remvelchio/agent/tmp/images", device: str = "cuda"):
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.device = device
        self.pipe = AutoPipelineForText2Image.from_pretrained(
            "stabilityai/sdxl-turbo",
            torch_dtype=torch.float16,
            variant="fp16",
        ).to(self.device)

    def generate(self, prompt: str, width: int = 1024, height: int = 576, steps: int = 4) -> str:
        ts = time.strftime("%Y%m%d-%H%M%S")
        out_path = self.out_dir / f"story_{ts}.png"
        image = self.pipe(
            prompt=prompt,
            num_inference_steps=steps,
            guidance_scale=0.0,
            width=width,
            height=height,
        ).images[0]
        image.save(out_path)
        return str(out_path)
