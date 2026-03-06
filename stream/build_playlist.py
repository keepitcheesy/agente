#!/usr/bin/env python3
"""
THE INVARIANT PLAYLIST BUILDER
Populates the Playback Deck with the next batch.
Failsafe: Shuffles archive as reruns when backlog is empty.
"""
import os
import glob
import random
import shutil
import subprocess

BATCH_SIZE = 10
BASE_DIR = "/home/remvelchio/agent"
BACKLOG_DIR = os.path.join(BASE_DIR, "tmp/backlog/video")
ARCHIVE_DIR = os.path.join(BASE_DIR, "tmp/archive/video")
PLAYLIST_FILE = os.path.join(BASE_DIR, "tmp/current_batch.txt")

def setup_dirs():
    os.makedirs(BACKLOG_DIR, exist_ok=True)
    os.makedirs(ARCHIVE_DIR, exist_ok=True)

def is_valid_mp4(path):
    """Strict validation: h264 video + 22050Hz audio + valid duration."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=codec_name", "-of", "csv=p=0", path],
            capture_output=True, text=True, timeout=5
        )
        if "h264" not in result.stdout:
            return False
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "a:0",
             "-show_entries", "stream=sample_rate", "-of", "default=nw=1:nk=1", path],
            capture_output=True, text=True, timeout=5
        )
        if result.stdout.strip() != "22050":
            return False
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", path],
            capture_output=True, text=True, timeout=5
        )
        dur = float(result.stdout.strip())
        return dur > 1.0
    except Exception:
        return False

def build_playlist():
    setup_dirs()

    # 1. Check backlog for fresh content
    videos = sorted(glob.glob(os.path.join(BACKLOG_DIR, "*.mp4")), key=os.path.getmtime)

    valid = []
    for v in videos:
        if is_valid_mp4(v):
            valid.append(v)
        else:
            print(f"REJECTED: {os.path.basename(v)}")
            os.remove(v)

    selected = valid[:BATCH_SIZE]

    with open(PLAYLIST_FILE, "w") as f:
        f.write("ffconcat version 1.0\n")

        if selected:
            # FRESH CONTENT — play new stories
            print(f"LIVE: Loading {len(selected)} new videos...")
            for vid in selected:
                f.write(f"file '{vid}'\n")
            # Archive after writing playlist
            for vid in selected:
                dest = os.path.join(ARCHIVE_DIR, os.path.basename(vid))
                shutil.move(vid, dest)
        else:
            # RERUNS — shuffle the archive so it's never the same loop
            archived = glob.glob(os.path.join(ARCHIVE_DIR, "*.mp4"))
            if archived:
                random.shuffle(archived)
                rerun_batch = archived[:BATCH_SIZE]
                print(f"RERUNS: Shuffling {len(rerun_batch)} from archive ({len(archived)} total)")
                for vid in rerun_batch:
                    f.write(f"file '{vid}'\n")
            else:
                print("CRITICAL: No videos anywhere. Master will hold frame.")

if __name__ == "__main__":
    try:
        build_playlist()
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
