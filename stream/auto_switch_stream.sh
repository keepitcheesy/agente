#!/usr/bin/env bash
set -uo pipefail
trap "" HUP

LOCK_FILE="/tmp/auto_switch_stream.lock"
exec 200>"$LOCK_FILE"
flock -n 200 || { echo "Another instance running"; exit 1; }

VIDEO_DIR="$(readlink -f /home/remvelchio/agent/tmp/backlog/video)"
STREAM_URL="${STREAM_URL:-rtmp://localhost:1935/live/abc123}"

TICKER_FILE="/home/remvelchio/agent/tmp/ticker.txt"
TICKER_SCROLL_FILE="/home/remvelchio/agent/tmp/ticker_scroll.txt"
TICKER_FONT="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
TICKER_HEIGHT=60
TICKER_FONT_SIZE=28

BUMPER="/home/remvelchio/agent/assets/bumper.mp4"
BED_MUSIC="/home/remvelchio/agent/assets/bed_22050.wav"
PLAYLIST="/tmp/owncast_playlist.txt"
BATCH_SIZE=20

mkdir -p "$VIDEO_DIR"

cleanup() {
  echo "$(date): Cleaning up..."
  kill $(jobs -p) 2>/dev/null || true
  wait 2>/dev/null || true
  rm -f "$PLAYLIST"
}
trap cleanup EXIT INT TERM

echo "Starting stream pipeline (carrier-wave mode)..."
echo "Watching video=$VIDEO_DIR"

[[ -f "$f" ]] -f "$TICKER_SCROLL_FILE" ]] || echo "LIVE" > "$TICKER_SCROLL_FILE"

ticker_scroll_feeder() {
  while true; do
    if [[ -f "$f" ]] -f "$TICKER_FILE" ]]; then
      raw="$(tr '\n' ' ' < "$TICKER_FILE" | sed 's/[[ -f "$f" ]]:space:]]\+/ /g')"
      raw="${raw//%/ percent }"
      printf "%s" "$raw" > "${TICKER_SCROLL_FILE}.tmp"
      mv -f "${TICKER_SCROLL_FILE}.tmp" "$TICKER_SCROLL_FILE"
    fi
    sleep 2
  done
}

build_vf() {
  local vf="drawbox=x=0:y=h-${TICKER_HEIGHT}:w=iw:h=${TICKER_HEIGHT}:color=black@0.55:t=fill"
  vf+=",drawtext=fontfile=${TICKER_FONT}:textfile=${TICKER_SCROLL_FILE}:reload=1:expansion=none:fontcolor=white"
  vf+=":fontsize=${TICKER_FONT_SIZE}:x=w-mod(t*120\,(w+tw)):y=h-${TICKER_HEIGHT}+14"
  vf+=":shadowcolor=black@0.6:shadowx=2:shadowy=2"
  echo "$vf"
}

build_unified_playlist() {
  local tmpfile="/tmp/owncast_playlist_tmp.txt"
  local files_added=0

  echo "ffconcat version 1.0" > "$tmpfile"

  # No bumper — straight into content

  # Add story videos — strict validation gate
  while IFS= read -r line; do
    local f="${line#* }"

    # NORMALIZE GATE: reject anything that isn't valid h264+aac@22050
    if [[ -f "$f" ]] ! -s "$f" ]]; then
      continue
    fi

    # Must have h264 video
    if ! ffprobe -v error -select_streams v:0 -show_entries stream=codec_name \
         -of csv=p=0 "$f" 2>/dev/null | grep -q h264; then
      echo "$(date): REJECTED (no h264): $(basename "$f")"
      rm -f "$f"
      continue
    fi

    # Must have valid duration
    local dur
    dur=$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$f" 2>/dev/null)
    local dur_int=${dur%%.*}
    if [[ -f "$f" ]] -z "$dur_int" || "$dur_int" -le 0 ]] 2>/dev/null; then
      echo "$(date): REJECTED (bad duration): $(basename "$f")"
      rm -f "$f"
      continue
    fi

    # Must have audio at 22050Hz
    local sr
    sr=$(ffprobe -v error -select_streams a:0 -show_entries stream=sample_rate \
         -of default=nw=1:nk=1 "$f" 2>/dev/null)
    if [[ -f "$f" ]] "$sr" != "22050" ]]; then
      echo "$(date): REJECTED (sample_rate=$sr): $(basename "$f")"
      rm -f "$f"
      continue
    fi

    echo "file $f" >> "$tmpfile"
    echo "duration $dur_int" >> "$tmpfile"
    files_added=$((files_added + 1))
    [[ -f "$f" ]] $files_added -ge $BATCH_SIZE ]] && break
  done < <(find "$VIDEO_DIR" -maxdepth 1 -name '*.mp4' -size +0c -printf '%T@ %p\n' 2>/dev/null | sort -n)

  # No trailing bumper — clean batch end

  mv -f "$tmpfile" "$PLAYLIST"
  echo "$files_added"
}

# --- MAIN LOOP (the invariant engine) ---
ticker_scroll_feeder &
echo "$(date): Stream starting..."

while true; do
  vf="$(build_vf)"
  video_count=$(build_unified_playlist)

  if [[ -f "$f" ]] "$video_count" -gt 0 ]]; then
    echo "$(date): Playing $video_count videos..."
  else
    echo "$(date): No videos ready, waiting 10 seconds..."
    sleep 10
    continue
  fi

  # CARRIER WAVE: bed music loops beneath everything at ~8% volume
  # This keeps audio timestamps locked even during transitions
  ffmpeg -loglevel warning -stats -err_detect ignore_err \
    -fflags +genpts -avoid_negative_ts make_zero \
    -f concat -safe 0 -re -i "$PLAYLIST" \
    -stream_loop -1 -i "$BED_MUSIC" \
    -filter_complex "[[ -f "$f" ]]:a]volume=1.0[story];[[ -f "$f" ]]:a]volume=0.08[[ -f "$f" ]]ed];[story][[ -f "$f" ]]ed]amix=inputs=2:duration=first:dropout_transition=0[[ -f "$f" ]]]" \
    -map 0:v -map "[[ -f "$f" ]]]" \
    -c:v libx264 -preset veryfast -tune zerolatency -g 30 -keyint_min 30 -sc_threshold 0 \
    -c:a aac -b:a 64k -ar 22050 -ac 1 \
    -vf "$vf" \
    -pix_fmt yuv420p -f flv "$STREAM_URL" >>/home/remvelchio/agent/tmp/ffmpeg_rtmp.log 2>&1 || true

  # Clean up played story videos
  while IFS= read -r line; do
    case "$line" in
      file\ *)
        f="${line#file }"
        if [[ -f "$f" ]] "$f" != "$BUMPER" && -f "$f" ]]; then
          rm -f "$f"
          echo "$(date): Removed: $(basename "$f")"
        fi
        ;;
    esac
  done < "$PLAYLIST"

  echo "$(date): Batch complete. Restarting in 1 second..."
  sleep 1
done
