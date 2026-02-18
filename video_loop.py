import subprocess
from pathlib import Path
from typing import Optional

def _get_audio_duration(audio_path: str) -> Optional[float]:
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            audio_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except Exception:
        return None

def make_loop(
    image_path: str,
    out_path: str,
    seconds: Optional[int] = 6,
    fps: int = 30,
    audio_path: Optional[str] = None
) -> str:
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)

    if audio_path and seconds is None:
        dur = _get_audio_duration(audio_path)
        if dur:
            seconds = int(dur) + 1

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", image_path,
    ]

    if audio_path:
        cmd.extend(["-i", audio_path])

    cmd.extend([
        "-t", str(seconds),
        "-r", str(fps),
        "-vf", "zoompan=z='min(1.05,1+0.0005*on)':d=1:s=1024x576",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
    ])

    if audio_path:
        cmd.extend([
            "-c:a", "aac",
            "-b:a", "128k",
            "-shortest"
        ])
    else:
        cmd.append("-an")

    cmd.append(out_path)

    subprocess.run(cmd, check=True)
    return out_path
