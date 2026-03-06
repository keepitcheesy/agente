"""
Dream Broadcast Pipeline — 12AM to 4AM block

Each dream cycle produces one ~5 minute "set":
  pass_1: music forward         — clean
  pass_2: music reversed        — clean
  pass_3: music forward         — clean
  pass_4: music reversed        — clean
  pass_5: music + opening narration (voice over ducked music)
  pass_6: music reversed        — clean
  pass_7: music forward         — clean
  pass_8: music reversed        — clean
  pass_9: music + closing narration (voice over ducked music)

Then next dream cycle fires.
Outside 12AM-4AM: standby image loops silently.
"""

import sys
sys.path.insert(0, '/mnt/c/Users/M4ISI/eigentrace')
sys.path.insert(0, '/home/remvelchio/agent')

import os
import time
import signal
import logging
import subprocess
from datetime import datetime
from pathlib import Path

from video_loop import make_loop
from tts_local import LocalTTS
import dream_engine

# ── config ────────────────────────────────────────────────────────────────────

DREAM_START_HOUR   = 0
DREAM_END_HOUR     = 4
VIDEO_OUT_DIR      = '/home/remvelchio/agent/tmp/video'
AUDIO_DIR          = '/home/remvelchio/agent/tmp/audio'
STANDBY_IMAGE      = '/home/remvelchio/agent/assets/standby_background.png'
TTS_MODEL          = '/home/remvelchio/agent/models/piper/en_US-lessac-medium.onnx'
TTS_CONFIG         = '/home/remvelchio/agent/models/piper/en_US-lessac-medium.onnx.json'
OWNCAST_RTMP       = 'rtmp://localhost:1935/live/hCet25N^wsaXpSH8X$^jW3P9Y7EaZk'
FONT_PATH          = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
MUSIC_VOLUME       = 0.25   # ducked under narration
VOICE_VOLUME       = 1.0

# ── logging ───────────────────────────────────────────────────────────────────

os.makedirs('/home/remvelchio/agent/logs', exist_ok=True)
os.makedirs(VIDEO_OUT_DIR, exist_ok=True)
os.makedirs(AUDIO_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/home/remvelchio/agent/logs/dream_broadcast.log'),
    ]
)
log = logging.getLogger('dream_broadcast')

tts = LocalTTS(
    model_path=TTS_MODEL,
    config_path=TTS_CONFIG,
    cache_dir=AUDIO_DIR,
)

running = True

def handle_signal(sig, frame):
    global running
    log.info('Shutdown signal received')
    running = False

signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)

# ── audio helpers ─────────────────────────────────────────────────────────────

def reverse_audio(src: str) -> str:
    """Return path to reversed WAV, generating if needed."""
    rev = src.replace('.wav', '_rev.wav')
    if Path(rev).exists():
        return rev
    subprocess.run([
        'ffmpeg', '-y',
        '-i', src,
        '-af', 'areverse',
        rev
    ], check=True)
    log.info(f'Reversed audio: {rev}')
    return rev


def mix_narration(music_path: str, voice_path: str, out_path: str) -> str:
    """Mix voice over looped music, ducked to MUSIC_VOLUME. Duration = voice length."""
    dur = _get_audio_duration(voice_path)
    subprocess.run([
        'ffmpeg', '-y',
        '-stream_loop', '-1', '-i', music_path,
        '-i', voice_path,
        '-filter_complex',
        f'[0:a]volume={MUSIC_VOLUME}[music];'
        f'[1:a]volume={VOICE_VOLUME}[voice];'
        f'[music][voice]amix=inputs=2:duration=shortest[out]',
        '-map', '[out]',
        '-t', str(int(dur) + 1),
        out_path
    ], check=True)
    log.info(f'Narration mix ready: {out_path}')
    return out_path


def _get_audio_duration(path: str) -> float:
    result = subprocess.run([
        'ffprobe', '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        path
    ], capture_output=True, text=True, check=True)
    return float(result.stdout.strip())

# ── video helpers ─────────────────────────────────────────────────────────────

def make_dream_segment(
    image_path: str,
    audio_path: str,
    spectrogram_path: str,
    label: str,
    seconds: int = None,
) -> str:
    ts = datetime.now().strftime('%Y%m%d-%H%M%S%f')
    out = os.path.join(VIDEO_OUT_DIR, f'dream_{ts}_{label}.mp4')
    make_loop(
        image_path=image_path,
        out_path=out,
        seconds=seconds,
        fps=30,
        audio_path=audio_path,
        show_ticker=False,
        spectrogram_path=spectrogram_path,
        font_path=FONT_PATH,
    )
    return out


def push(video_path: str):
    log.info(f'→ Owncast: {Path(video_path).name}')
    try:
        subprocess.run([
            'ffmpeg', '-re', '-y',
            '-i', video_path,
            '-c:v', 'copy',
            '-c:a', 'aac', '-b:a', '128k',
            '-f', 'flv',
            OWNCAST_RTMP,
        ], check=True)
    except subprocess.CalledProcessError as e:
        log.error(f'Push failed: {e}')

# ── dream set ─────────────────────────────────────────────────────────────────

def run_dream_set(entry):
    """
    Build and push one full dream set (~5 min) for a FREE or WORLD entry.
    Structure: 4 clean passes → opening narration → 3 clean passes → closing narration
    """
    image     = entry.image_path or STANDBY_IMAGE
    music     = entry.music_path
    spec      = entry.spectrogram_path
    rev_music = reverse_audio(music)

    # TTS — opening and closing narration
    content = (entry.content or '').strip()
    sentences = [s.strip() for s in content.replace('\n', ' ').split('.') if s.strip()]

    mid = max(1, len(sentences) // 2)
    opening_text = '. '.join(sentences[:mid]) + '.'
    closing_text = '. '.join(sentences[mid:]) + '.'

    ts = datetime.now().strftime('%Y%m%d-%H%M%S')

    opening_voice = tts.synthesize(opening_text[:800], pitch=1.0)
    closing_voice = tts.synthesize(closing_text[:800], pitch=1.0)

    opening_mix = os.path.join(AUDIO_DIR, f'opening_mix_{ts}.wav')
    closing_mix = os.path.join(AUDIO_DIR, f'closing_mix_{ts}.wav')

    mix_narration(music, opening_voice, opening_mix)
    mix_narration(music, closing_voice, closing_mix)

    # pass sequence: (audio, label)
    passes = [
        (music,        'fwd_1'),
        (rev_music,    'rev_1'),
        (music,        'fwd_2'),
        (rev_music,    'rev_2'),
        (opening_mix,  'narration_open'),
        (rev_music,    'rev_3'),
        (music,        'fwd_3'),
        (rev_music,    'rev_4'),
        (closing_mix,  'narration_close'),
    ]

    log.info(f'Dream set starting: {entry.dream_type} | {len(passes)} passes')

    for audio, label in passes:
        if not running:
            break
        seg = make_dream_segment(image, audio, spec, label)
        push(seg)
        # clean up segment after push to save disk
        try:
            os.remove(seg)
        except Exception:
            pass

    log.info(f'Dream set complete: {entry.dream_type}')

# ── standby ───────────────────────────────────────────────────────────────────

def push_standby():
    if not Path(STANDBY_IMAGE).exists():
        log.warning('No standby image — sleeping')
        time.sleep(60)
        return
    ts = datetime.now().strftime('%Y%m%d-%H%M%S')
    out = os.path.join(VIDEO_OUT_DIR, f'standby_{ts}.mp4')
    make_loop(
        image_path=STANDBY_IMAGE,
        out_path=out,
        seconds=60,
        fps=30,
        show_ticker=False,
        spectrogram_path=None,
    )
    push(out)
    try:
        os.remove(out)
    except Exception:
        pass

# ── main ──────────────────────────────────────────────────────────────────────

def is_dream_time():
    h = datetime.now().hour
    return DREAM_START_HOUR <= h < DREAM_END_HOUR


def main():
    log.info('=' * 60)
    log.info('EIGENTRACE DREAM BROADCAST STARTING')
    log.info(f'Dream block: {DREAM_START_HOUR:02d}:00 – {DREAM_END_HOUR:02d}:00')
    log.info('=' * 60)

    selector = dream_engine.PhiSelector()

    while running:
        if not is_dream_time():
            log.info('Outside dream hours — standby')
            push_standby()
            continue

        log.info('Dream time — running cycle...')
        try:
            entry = dream_engine.run_dream_cycle(selector)
            log.info(f'Cycle: type={entry.dream_type}')

            if entry.dream_type in ('FREE', 'WORLD'):
                run_dream_set(entry)
            else:
                # IDENTITY dream — single 60s segment, no narration
                seg = make_dream_segment(
                    image_path=STANDBY_IMAGE,
                    audio_path=None,
                    spectrogram_path=None,
                    label='identity',
                    seconds=60,
                )
                push(seg)
                try:
                    os.remove(seg)
                except Exception:
                    pass

        except Exception as e:
            log.error(f'Dream cycle error: {e}', exc_info=True)
            time.sleep(10)


if __name__ == '__main__':
    main()
