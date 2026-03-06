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


def _escape_drawtext(text: str) -> str:
    return (
        text.replace('\\', '\\\\')
            .replace(':', '\\:')
            .replace("'", "\\'")
            .replace('%', '\\%')
    )


def make_loop(
    image_path: str,
    out_path: str,
    seconds: Optional[int] = 6,
    fps: int = 30,
    audio_path: Optional[str] = None,
    ticker_text: Optional[str] = None,
    show_ticker: bool = True,
    spectrogram_path: Optional[str] = None,
    font_path: str = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ticker_height: int = 60,
    ticker_font_size: int = 28,
    pip_width: int = 320,
    pip_height: int = 90,
    pip_margin: int = 16,
) -> str:
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)

    if audio_path and seconds is None:
        dur = _get_audio_duration(audio_path)
        if dur:
            seconds = int(dur) + 1

    has_audio = bool(audio_path)
    has_spectrogram = bool(spectrogram_path) and Path(spectrogram_path).exists()
    do_ticker = show_ticker and bool(ticker_text)

    # ── inputs ────────────────────────────────────────────────────────────────
    cmd = ["ffmpeg", "-y", "-loop", "1", "-i", image_path]
    if has_audio:
        cmd.extend(["-i", audio_path])
    if has_spectrogram:
        spec_idx = 2 if has_audio else 1
        cmd.extend(["-loop", "1", "-i", spectrogram_path])

    # ── filter graph ──────────────────────────────────────────────────────────
    filters = []

    # Step 1: zoom on main image → [v0]
    filters.append(
        "[0:v]zoompan=z='min(1.05,1+0.0005*on)':d=1:s=1024x576[v0]"
    )

    current = "v0"

    # Step 2: spectrogram PiP (dream block only)
    if has_spectrogram:
        pip_y = f"H-{pip_height}-{pip_margin}"
        if do_ticker:
            pip_y = f"H-{pip_height}-{ticker_height}-{pip_margin}"
        filters.append(
            f"[{spec_idx}:v]scale={pip_width}:{pip_height}[pip]"
        )
        filters.append(
            f"[{current}][pip]overlay=W-{pip_width}-{pip_margin}:{pip_y}[v1]"
        )
        current = "v1"

    # Step 3: ticker (news block only)
    if do_ticker:
        safe_text = _escape_drawtext(ticker_text)
        if not Path(font_path).exists():
            font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        filters.append(
            f"[{current}]drawbox=x=0:y=h-{ticker_height}:w=iw:h={ticker_height}"
            f":color=black@0.55:t=fill[v2]"
        )
        filters.append(
            f"[v2]drawtext=fontfile={font_path}:text='{safe_text}':"
            f"fontcolor=white:fontsize={ticker_font_size}:"
            f"x=w-mod(t*120\\,(w+tw)):y=h-{ticker_height}+14:"
            f"shadowcolor=black@0.6:shadowx=2:shadowy=2[out]"
        )
    else:
        filters.append(f"[{current}]null[out]")

    filter_str = ";".join(filters)

    cmd.extend([
        "-t", str(seconds),
        "-r", str(fps),
        "-filter_complex", filter_str,
        "-map", "[out]",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
    ])

    if has_audio:
        cmd.extend([
            "-map", "1:a",
            "-c:a", "aac",
            "-b:a", "128k",
            "-shortest",
        ])
    else:
        cmd.append("-an")

    cmd.append(out_path)

    subprocess.run(cmd, check=True)
    return out_path
