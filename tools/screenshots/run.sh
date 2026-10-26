#!/usr/bin/env bash
# Take the README screenshots: a real Home Assistant with this integration,
# connected to a made-up Blue Iris (tools/screenshots/fake_blue_iris.py), driven
# by Playwright (tools/screenshots/capture.mjs). Writes screenshots/*.png.
#
#   PYTHON=/path/to/venv/bin/python tools/screenshots/run.sh
#
# PYTHON needs: homeassistant, home-assistant-frontend, pillow, PyTurboJPEG, av, numpy.
# Node needs playwright-core and its Chromium (set PLAYWRIGHT_CORE to its index.mjs
# if it isn't installed in this folder).
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
PYTHON="${PYTHON:-python3}"
export HA_PORT="${HA_PORT:-8124}"
export BI_PORT="${BI_PORT:-8181}"
export HA_URL="http://127.0.0.1:${HA_PORT}"
CONFIG="$(mktemp -d)"
LOGS="$CONFIG/logs"
mkdir -p "$LOGS"

cleanup() {
  [ -n "${HA_PID:-}" ] && kill "$HA_PID" 2>/dev/null || true
  [ -n "${BI_PID:-}" ] && kill "$BI_PID" 2>/dev/null || true
  wait 2>/dev/null || true
  rm -rf "$CONFIG"
}
trap cleanup EXIT

"$PYTHON" "$HERE/setup_demo.py" "$CONFIG" "$REPO"
"$PYTHON" -m homeassistant --script auth -c "$CONFIG" add demo demo >/dev/null

"$PYTHON" "$HERE/fake_blue_iris.py" "$BI_PORT" >"$LOGS/fake_blue_iris.log" 2>&1 &
BI_PID=$!
"$PYTHON" -m homeassistant -c "$CONFIG" >"$LOGS/home-assistant.log" 2>&1 &
HA_PID=$!

for _ in $(seq 1 100); do
  curl -s -m 2 -o /dev/null "$HA_URL/" && break
  sleep 2
done

rm -f "$REPO"/screenshots/0*.png
node "$HERE/capture.mjs" || { tail -40 "$LOGS/home-assistant.log"; exit 1; }
