#!/bin/bash
HLS="http://127.0.0.1:8080/hls/stream.m3u8"
YT="rtmp://a.rtmp.youtube.com/live2/t0eu-shj4-9sr2-24h9-9uma"
while true; do
  echo "[$(date)] Starting YouTube relay..."
  ffmpeg -hide_banner -loglevel warning -stats \
    -fflags +genpts -avoid_negative_ts make_zero \
    -re -i "$HLS" \
    -vf "fps=30,format=yuv420p" \
    -c:v libx264 -preset veryfast -tune zerolatency \
    -b:v 3500k -maxrate 3500k -bufsize 7000k \
    -g 60 -keyint_min 60 -sc_threshold 0 \
    -c:a aac -b:a 128k -ar 44100 -ac 2 \
    -f flv "$YT"
  echo "[$(date)] Relay died, restarting in 5s..."
  sleep 5
done
