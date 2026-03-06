#!/usr/bin/env python3
import argparse
from audiocraft.models import MusicGen
from audiocraft.data.audio import audio_write

parser = argparse.ArgumentParser()
parser.add_argument("--prompt", required=True)
parser.add_argument("--duration", type=int, default=60)
parser.add_argument("--out", required=True)
args = parser.parse_args()

out = args.out
if out.endswith(".wav"):
    out = out[:-4]

model = MusicGen.get_pretrained("small")
model.set_generation_params(duration=args.duration)
wav = model.generate([args.prompt])[0]
audio_write(out, wav.cpu(), model.sample_rate, strategy="loudness")
print(f"Wrote {out}.wav")
