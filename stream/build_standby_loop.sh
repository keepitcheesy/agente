#!/usr/bin/env bash
set -euo pipefail

LOCK_FILE="/tmp/standby_loop.lock"
exec 200>"$LOCK_FILE"
flock -n 200 || { echo "Another standby loop instance is running"; exit 1; }


BASE_DIR="/home/remvelchio/agent"
VIDEO_DIR="$BASE_DIR/tmp/video"
ASSETS_DIR="$BASE_DIR/assets"
TICKER_FILE="$BASE_DIR/tmp/ticker_standby.txt"
BG_IMAGE="$ASSETS_DIR/standby_background.png"
WIDTH=1024
HEIGHT=576
DURATION=600   # 10 minutes
FPS=30

mkdir -p "$VIDEO_DIR"

if [[ ! -f "$BG_IMAGE" ]]; then
  echo "Missing background image: $BG_IMAGE"
  exit 1
fi

FONT=""
for f in \
  "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" \
  "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" \
  "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"; do
  if [[ -f "$f" ]]; then
    FONT="$f"
    break
  fi
done

if [[ -z "$FONT" ]]; then
  echo "No font found. Install fonts-dejavu-core or fonts-liberation."
  exit 1
fi

PYTHON="$BASE_DIR/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON="python3"
fi

"$PYTHON" - <<'PYIN'
import yaml, feedparser

cfg = yaml.safe_load(open("/home/remvelchio/agent/config.yaml"))
urls = cfg.get("rss", [])
if isinstance(urls, dict):
  urls = urls.get("urls") or urls.get("url") or []
if isinstance(urls, str):
  urls = [urls]

titles = []
for url in urls:
  if not url: continue
  feed = feedparser.parse(url)
  for entry in feed.entries[:5]:
    title = (entry.get("title") or "").strip()
    if len(title) > 90:
      title = title[:87].rstrip() + "…"
    if title and title not in titles:
      titles.append(title)

if not titles:
  titles = ["Breaking news coverage continues 24/7", "Stay tuned for updates"]

ticker = "  •  ".join(titles)

# repeat ticker so it keeps scrolling without hitting the end
min_len = 800
if len(ticker) < min_len:
  repeats = (min_len // (len(ticker) + 3)) + 1
  ticker = ("  •  ".join(titles) + "  •  ") * repeats

open("/home/remvelchio/agent/tmp/ticker_standby.txt", "w").write(ticker)
print("Ticker length:", len(ticker))
PYIN

TS="$(date +%Y%m%d-%H%M%S)"
OUT="$VIDEO_DIR/loop_${TS}_standby.mp4"

ffmpeg -y -loop 1 -i "$BG_IMAGE" -t "$DURATION" -r "$FPS" \
  -vf "scale=${WIDTH}:${HEIGHT},format=yuv420p,\
drawbox=x=0:y=h-70:w=iw:h=70:color=0x001a33@0.92:t=fill,\
drawtext=fontfile=${FONT}:textfile=${TICKER_FILE}:reload=1:fontsize=28:fontcolor=white:expansion=none:x=w-mod(t*120\,(w+tw)):y=h-52,\
drawbox=x=0:y=0:w=iw:h=60:color=0x001a33@0.65:t=fill,\
drawtext=fontfile=${FONT}:text='OFFICIAL NEWS STANDBY':fontsize=30:fontcolor=white:x=20:y=12" \
  -c:v libx264 -pix_fmt yuv420p -an "$OUT"

echo "Wrote $OUT"
