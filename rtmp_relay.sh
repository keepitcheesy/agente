#!/bin/bash

INPUT="rtmp://localhost:1935/live"

ffmpeg -re -i "$INPUT" \
-c:v copy -c:a copy -f flv "rtmp://a.rtmp.youtube.com/live2/YOUTUBE_KEY" \
-c:v copy -c:a copy -f flv "rtmp://live.twitch.tv/app/TWITCH_KEY" \
-c:v copy -c:a copy -f flv "rtmp://live.rumble.com/live/RUMBLE_KEY" \
-c:v copy -c:a copy -f flv "rtmp://fa723fc1b171.global-contribute.live-video.net/app/FACEBOOK_KEY" \
-c:v copy -c:a copy -f flv "rtmp://live.kick.com/app/KICK_KEY" \
-c:v copy -c:a copy -f flv "rtmp://rtmp.trovo.live/live/TROVO_KEY"

