#!/usr/bin/env bash
# THE PLAYBACK DECK
# Reads batches and pushes them to the Master via UDP.
# When a batch ends, this process dies and restarts.
# The Master stays alive — viewers see nothing.

set -uo pipefail

UDP_TARGET="udp://127.0.0.1:10000?pkt_size=1316"
PLAYLIST="/home/remvelchio/agent/tmp/current_batch.txt"
PYTHON="/home/remvelchio/agent/.venv/bin/python"
BUILDER="/home/remvelchio/agent/stream/build_playlist.py"

echo "$(date): PLAYBACK DECK STARTING"

while true; do
    echo "$(date): Building playlist..."
    $PYTHON "$BUILDER"

    if [[ ! -s "$PLAYLIST" ]]; then
        echo "$(date): Empty playlist. Waiting 10 seconds for content..."
        sleep 10
        continue
    fi

    echo "$(date): Feeding batch to transmitter..."
    cat "$PLAYLIST"

    ffmpeg -hide_banner -loglevel warning -re \
        -fflags +genpts+igndts \
        -f concat -safe 0 -i "$PLAYLIST" \
        -c copy \
        -f mpegts "$UDP_TARGET" 2>>/home/remvelchio/agent/tmp/worker.log || true

    echo "$(date): Batch complete. Loading next in 1 second..."
    sleep 1
done
