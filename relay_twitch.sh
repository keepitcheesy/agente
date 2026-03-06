#!/bin/bash
HLS="http://127.0.0.1:8080/hls/stream.m3u8"
TW="rtmp://live.twitch.tv/app/live_1450329520_DcFkkTckId23Ea21m8WmlHLhux6f0e"
while true; do
  echo "[$(date)] Starting Twitch relay..."
  ffmpeg -hide_banner -loglevel warning -stats \
    -fflags +genpts -avoid_negative_ts make_zero \
    -re -i "$HLS" \
    -vf "fps=30,format=yuv420p" \
    -c:v libx264 -preset veryfast -tune zerolatency \
    -g 60 -keyint_min 60 -sc_threshold 0 \
    -c:a aac -b:a 128k -ar 44100 -ac 2 \
    -f flv "$TW"
  echo "[$(date)] Relay died, restarting in 5s..."
  sleep 5
done
