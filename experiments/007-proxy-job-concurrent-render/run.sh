#!/usr/bin/env bash
# Experiment 007 (proxy-job): a GPU render beside a proxy job. Run from the repo root:
#   DEV=/path/to/scratch REPS=3 experiments/007-proxy-job-concurrent-render/run.sh
# Needs: .venv, a migrated DATABASE_URL (an empty scratch database), ../auto-reel-media (read only).
set -euo pipefail
MEDIA="${MEDIA:-../auto-reel-media}"
DEV="${DEV:?set DEV to a scratch directory}"
REPS="${REPS:-3}"
OUT="$(dirname "$0")/artifacts${OUT_SUFFIX:-}"
LIB="$DEV/library"
CACHE="$DEV/cache/proxies"
mkdir -p "$OUT"
rm -rf "$LIB" "$DEV/library-output" "$DEV/cache"
mkdir -p "$LIB/2024"
link() { # link <event dir> <files...>: symlinks over the read-only media
  local event="$LIB/2024/$1"; shift; mkdir -p "$event"
  for f in "$@"; do ln -s "$(realpath "$f")" "$event/$(basename "$f")"; done
}
# The render event mixes frame rates and shapes (a 50 fps clip and a portrait clip among the 30 fps
# ones), so most clips are normalized on the GPU; four conformant clips alone are nearly a stream copy.
link "2024-06-27 - Render" "$MEDIA"/input/2024/*/s17100*.mp4 "$MEDIA/samples/h264-1080p50-aac.mp4" \
  "$MEDIA/samples/h264-portrait-1080x1920-aac.mp4" "$MEDIA/samples/h264-720p25-aac-msnv.mp4"
link "2024-07-01 - ProxyA" "$MEDIA/samples/h264-4k50-aac-119mbps.mp4" "$MEDIA/samples/sony-xavc-4k25-pcm.mp4"
link "2024-07-02 - ProxyB" "$MEDIA/samples/legacy-render-mpeg4-mp3.mp4" "$MEDIA/samples/h264-1080p25-aac.mp4"
link "2024-07-03 - ProxyC" "$MEDIA/samples/sony-xavc-1080p25-pcm.mp4" \
  "$MEDIA/samples/hevc-mov-rotate90-aac.mov" "$MEDIA/samples/h264-720p-rotate90-aac.mp4"
printf 'proxies:\n  cache_dir: %s\n' "$CACHE" > "$LIB/config.yaml"

{ date -u; uname -r; ffmpeg -version | head -1; lscpu | grep -E 'Model name|^CPU\(s\)'; \
  vainfo 2>&1 | grep -E 'Driver version'; uptime; } > "$OUT/host.txt" 2>&1

# PROXY_X264_THREADS=N runs the worker with the proxy encode capped to N threads (the lever);
# PROXY_FORCE_CPU=1 makes every proxy use the CPU decode path (a diagnostic of where the contention is).
# PROXY_NO_YIELD=1 switches the proxy job's yield to running renders off (the control).
if [ -n "${PROXY_X264_THREADS:-}${PROXY_FORCE_CPU:-}${PROXY_NO_YIELD:-}" ]; then WORKER_CMD=(.venv/bin/python "$(dirname "$0")/capped_worker.py")
else WORKER_CMD=(.venv/bin/auto-reel); fi
"${WORKER_CMD[@]}" worker -v --poll-interval 0.2 "$LIB" > "$OUT/worker.log" 2>&1 &
WORKER=$!
trap 'kill -TERM $WORKER 2>/dev/null || true; wait $WORKER 2>/dev/null || true' EXIT
sleep 3
.venv/bin/python "$(dirname "$0")/measure.py" "$LIB" "$CACHE" "$REPS" | tee "$OUT/results.txt"
uptime >> "$OUT/host.txt"
