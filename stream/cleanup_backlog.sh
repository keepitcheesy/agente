#!/usr/bin/env bash
# INVARIANT CLEANUP — runs every 2 minutes via cron
# Keeps disk lean, preserves narration logs for 7 days

VIDEO_DIR="/home/remvelchio/agent/tmp/backlog/video"
AUDIO_DIR="/home/remvelchio/agent/tmp/backlog/audio"
IMAGE_DIR="/home/remvelchio/agent/tmp/images"
ARCHIVE_DIR="/home/remvelchio/agent/tmp/archive/video"
OLD_VIDEO_DIR="/home/remvelchio/agent/tmp/video"
LOG_DIR="/home/remvelchio/agent/logs"
SCRIPT_DIR="/home/remvelchio/agent/tmp/scripts"
TMP_DIR="/home/remvelchio/agent/tmp"

MAX_VIDEOS=30
MAX_AUDIO=30

# --- Cap video backlog ---
video_count=$(find "$VIDEO_DIR" -maxdepth 1 -name '*.mp4' -type f 2>/dev/null | wc -l)
if [[ $video_count -gt $MAX_VIDEOS ]]; then
  delete_count=$((video_count - MAX_VIDEOS))
  echo "$(date): Videos: $video_count, deleting $delete_count oldest..."
  find "$VIDEO_DIR" -maxdepth 1 -name '*.mp4' -type f -printf '%T@ %p\n' \
    | sort -n | head -n "$delete_count" | cut -d' ' -f2- | xargs rm -f
fi

# --- Cap audio backlog ---
audio_count=$(find "$AUDIO_DIR" -maxdepth 1 -name '*.wav' -type f 2>/dev/null | wc -l)
if [[ $audio_count -gt $MAX_AUDIO ]]; then
  delete_count=$((audio_count - MAX_AUDIO))
  echo "$(date): Audio: $audio_count, deleting $delete_count oldest..."
  find "$AUDIO_DIR" -maxdepth 1 -name '*.wav' -type f -printf '%T@ %p\n' \
    | sort -n | head -n "$delete_count" | cut -d' ' -f2- | xargs rm -f
fi

# --- Delete images older than 10 minutes ---
img_deleted=$(find "$IMAGE_DIR" -maxdepth 1 -name '*.png' -type f -mmin +10 -delete -print 2>/dev/null | wc -l)
[[ $img_deleted -gt 0 ]] && echo "$(date): Deleted $img_deleted old images"

# --- Purge archive older than 24 hours (already aired) ---
archive_deleted=$(find "$ARCHIVE_DIR" -maxdepth 1 -name '*.mp4' -type f -mmin +1440 -delete -print 2>/dev/null | wc -l)
[[ $archive_deleted -gt 0 ]] && echo "$(date): Purged $archive_deleted archived videos (>24h)"

# --- Nuke legacy tmp/video (old render dir) ---
legacy_deleted=$(find "$OLD_VIDEO_DIR" -maxdepth 1 -name '*.mp4' -type f -mmin +30 -delete -print 2>/dev/null | wc -l)
[[ $legacy_deleted -gt 0 ]] && echo "$(date): Purged $legacy_deleted legacy renders"

# --- Delete stale WAVs in tmp root (orphaned renders) ---
stale_wav=$(find "$TMP_DIR" -maxdepth 1 -name '*.wav' -type f -mmin +30 -delete -print 2>/dev/null | wc -l)
[[ $stale_wav -gt 0 ]] && echo "$(date): Deleted $stale_wav stale WAVs"

# --- Purge corrupt MP4s from backlog ---
for f in "$VIDEO_DIR"/*.mp4; do
  [[ -f "$f" ]] || continue
  if ! ffprobe -v error -show_entries format=duration "$f" >/dev/null 2>&1; then
    echo "$(date): Removing corrupt: $(basename "$f")"
    rm -f "$f"
  fi
done

# --- Narration log: rotate daily, keep 7 days ---
NARRATION_LOG="$SCRIPT_DIR/narration.log"
if [[ -f "$NARRATION_LOG" ]]; then
  today=$(date +%Y-%m-%d)
  daily_archive="$SCRIPT_DIR/narration_${today}.log"
  # If we haven't archived today yet, rotate
  if [[ ! -f "$daily_archive" ]]; then
    cp "$NARRATION_LOG" "$daily_archive"
    > "$NARRATION_LOG"
    echo "$(date): Rotated narration log -> $(basename "$daily_archive")"
  fi
  # Delete narration archives older than 7 days
  find "$SCRIPT_DIR" -name 'narration_*.log' -type f -mtime +7 -delete -print 2>/dev/null \
    | while read f; do echo "$(date): Expired narration archive: $(basename "$f")"; done
fi

# --- Truncate all large logs (>10MB) ---
for logfile in \
  "$TMP_DIR/ffmpeg_rtmp.log" \
  "$TMP_DIR/master.log" \
  "$TMP_DIR/worker.log" \
  "$TMP_DIR/master_console.log" \
  "$TMP_DIR/worker_console.log" \
  "$TMP_DIR/stream.log" \
  "$TMP_DIR/cleanup.log" \
  "$LOG_DIR/agente.log"; do
  if [[ -f "$logfile" ]]; then
    size=$(stat -c%s "$logfile" 2>/dev/null || echo 0)
    if [[ $size -gt 10485760 ]]; then
      echo "$(date): Truncating $(basename "$logfile") ($((size/1024/1024))MB)"
      tail -1000 "$logfile" > "${logfile}.tmp" && mv "${logfile}.tmp" "$logfile"
    fi
  fi
done

# --- Report ---
echo "$(date): Backlog: $(find "$VIDEO_DIR" -maxdepth 1 -name '*.mp4' 2>/dev/null | wc -l)v $(find "$AUDIO_DIR" -maxdepth 1 -name '*.wav' 2>/dev/null | wc -l)a $(find "$IMAGE_DIR" -maxdepth 1 -name '*.png' 2>/dev/null | wc -l)i | Archive: $(find "$ARCHIVE_DIR" -maxdepth 1 -name '*.mp4' 2>/dev/null | wc -l)v | Narrations: $(find "$SCRIPT_DIR" -name 'narration_*.log' 2>/dev/null | wc -l) days | Disk: $(du -sh "$TMP_DIR" 2>/dev/null | cut -f1)"
