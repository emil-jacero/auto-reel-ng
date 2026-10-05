#!/usr/bin/env bash
# Experiment 008 — what black/white/freeze analysis costs per minute of footage (analysis-job).
# Read-only originals from auto-reel-media are SYMLINKED into a scratch library; nothing is
# written under auto-reel-media. Needs: the worktree venv, ffmpeg >= 7.1, VAAPI (for the derived
# HEVC sample and the GPU render), and DATABASE_URL pointing at a migrated scratch database.
#
#   source ../../../dev-analysis-job.env   # DATABASE_URL=…/arel_analysis_job
#   DEV=/path/to/scratch ./run.sh [direct|worker|beside|all]
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(cd "$HERE/../.." && pwd)
AR=$(cd "$REPO/.." && pwd)
MEDIA=${MEDIA:-$AR/auto-reel-media}
DEV=${DEV:-$AR/dev-analysis-job}
SAMPLES=$DEV/lib-samples   # one event per sample
RENDER=$DEV/lib-render     # one 4-clip event to render and analyze
OUT=$HERE/artifacts
PY=$REPO/.venv/bin/python
AR_CLI=$REPO/.venv/bin/auto-reel
: "${DATABASE_URL:?source the dev env file first}"
DB=${DATABASE_URL##*/}
psql_q() { podman exec auto-reel-ng-dev-db psql -U auto_reel_ng -d "$DB" -At -F ' ' -c "$1"; }

declare -A SAMPLE=(
  [h264-1080p50]="$MEDIA/samples/h264-1080p50-aac.mp4"
  [h264-4k50]="$MEDIA/samples/h264-4k50-aac-119mbps.mp4"
  [hevc-4k50]="$DEV/gen/hevc-4k50-aac.mp4"
)

setup() {
  mkdir -p "$DEV/gen" "$OUT"
  # No 4K HEVC original exists in auto-reel-media: derive one from the 4K H.264 original (VAAPI
  # HEVC Main, ~70 Mb/s, same 30.24 s, 3840x2160, 50 fps) into the scratch area.
  [ -f "${SAMPLE[hevc-4k50]}" ] || ffmpeg -hide_banner -loglevel error -y \
    -vaapi_device /dev/dri/renderD128 -i "${SAMPLE[h264-4k50]}" \
    -vf 'format=nv12,hwupload' -c:v hevc_vaapi -b:v 60M -c:a copy "${SAMPLE[hevc-4k50]}"
  for name in "${!SAMPLE[@]}"; do
    mkdir -p "$SAMPLES/2024/2024-10-05 - $name"
    ln -sfn "${SAMPLE[$name]}" "$SAMPLES/2024/2024-10-05 - $name/clip.mp4"
  done
  # The render event: four 1080p50 H.264 originals (150 s) from the grillning fixture.
  mkdir -p "$RENDER/2024/2024-06-27 - render"
  for f in "$MEDIA/input/2024/2024-06-27 - grillning med grannar"/s171000[1-4].mp4; do
    ln -sfn "$f" "$RENDER/2024/2024-06-27 - render/$(basename "$f")"
  done
}

duration() { ffprobe -v error -show_entries format=duration -of csv=p=0 "$1"; }

# Phase A: the two detection passes, exactly as the job runs them, timed with /usr/bin/time.
direct() {
  echo "sample duration_s pass wall_s user_s sys_s" > "$OUT/direct.txt"
  for name in h264-1080p50 h264-4k50 hevc-4k50; do
    clip=${SAMPLE[$name]}
    for pass in 1 2; do
      mapfile -t args < <("$PY" -c "
import sys
from auto_reel_ng.analysis.filters import pass1_args, pass2_args
from auto_reel_ng.analysis.models import AnalysisConfig
print('\n'.join((pass1_args if sys.argv[2] == '1' else pass2_args)(sys.argv[1], AnalysisConfig())))
" "$clip" "$pass")
      /usr/bin/time -f "%e %U %S" -o "$OUT/time.tmp" ffmpeg "${args[@]}" 2>/dev/null
      echo "$name $(duration "$clip") $pass $(cat "$OUT/time.tmp")" >> "$OUT/direct.txt"
    done
  done
  cat "$OUT/direct.txt"
}

start_worker() { root=$1; shift; "$AR_CLI" worker "$root" "$@" >> "$OUT/worker.log" 2>&1 & echo $!; }
stop_worker() { kill -TERM "$1"; while kill -0 "$1" 2>/dev/null; do sleep 0.2; done; }
wait_jobs_done() {  # until no queued/running job is left
  while [ "$(psql_q "SELECT count(*) FROM jobs WHERE status IN ('queued','running')")" != 0 ]; do
    sleep 1
  done
}
job_times() {  # kind event wall_s (claim to finish) status
  psql_q "SELECT kind, split_part(event_dir, ' - ', 2),
                 round(extract(epoch FROM finished_at - started_at)::numeric, 2), status
          FROM jobs WHERE created_at > now() - interval '2 hours' AND id::text = ANY('{$1}')
          ORDER BY started_at"
}
ids_since() { psql_q "SELECT string_agg(id::text, ',') FROM jobs WHERE created_at >= '$1'"; }

# Phase B: the real worker running one analysis job per sample event, idle otherwise.
worker() {
  psql_q "DELETE FROM jobs" >/dev/null
  t0=$(psql_q "SELECT now()")
  "$AR_CLI" analyze "$SAMPLES" --enqueue --force > /dev/null
  pid=$(start_worker "$SAMPLES" --device cpu)
  wait_jobs_done
  stop_worker "$pid"
  job_times "$(ids_since "$t0")" | tee "$OUT/worker.txt"
}

# Phase C: a GPU render solo, then the same render queued into a running 4-clip analysis job.
beside() {
  psql_q "DELETE FROM jobs" >/dev/null
  pid=$(start_worker "$RENDER")
  t0=$(psql_q "SELECT now()")
  "$AR_CLI" enqueue "$RENDER" --force > /dev/null
  wait_jobs_done
  echo "# solo" | tee "$OUT/beside.txt"
  job_times "$(ids_since "$t0")" | tee -a "$OUT/beside.txt"

  t1=$(psql_q "SELECT now()")
  "$AR_CLI" analyze "$RENDER" --enqueue --force > /dev/null
  while [ "$(psql_q "SELECT count(*) FROM jobs WHERE kind='analysis' AND status='running'")" = 0 ]; do
    sleep 0.2
  done
  sleep 3  # the first clip is being analyzed
  "$AR_CLI" enqueue "$RENDER" --force > /dev/null
  wait_jobs_done
  stop_worker "$pid"
  echo "# render queued 3 s into a running 4-clip analysis job" | tee -a "$OUT/beside.txt"
  job_times "$(ids_since "$t1")" | tee -a "$OUT/beside.txt"
  psql_q "SELECT kind, to_char(started_at, 'HH24:MI:SS.MS'), to_char(finished_at, 'HH24:MI:SS.MS')
          FROM jobs WHERE created_at >= '$t1' ORDER BY started_at" | tee -a "$OUT/beside.txt"
}

setup
case "${1:-all}" in
  direct) direct ;;
  worker) worker ;;
  beside) beside ;;
  all) direct; worker; beside ;;
esac
