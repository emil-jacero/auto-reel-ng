#!/usr/bin/env bash
# Experiment 001 — stream-copy concat constraints. Synthetic clips, no real media.
set -euo pipefail
cd "$(dirname "$0")/artifacts"

gen() { # name WxH fps extra_vf
  ffmpeg -hide_banner -loglevel error -y \
    -f lavfi -i "testsrc2=size=$2:rate=$3:duration=2" \
    -f lavfi -i "sine=frequency=440:duration=2" \
    -c:v libx264 -profile:v high -pix_fmt yuv420p ${4:+-vf "$4"} \
    -c:a aac -ar 48000 -ac 2 "$1"
}
gen A.mp4 1920x1080 30          # baseline
gen B.mp4 1920x1080 30          # identical params, different content
gen C.mp4 1280x720  30          # resolution mismatch
gen D.mp4 1920x1080 25          # framerate/timebase mismatch
gen E.mp4 1920x1080 30 "setsar=4:3"   # SAR mismatch (same pixel dims)

probe() { ffprobe -v error -select_streams v:0 \
  -show_entries stream=codec_name,profile,width,height,sample_aspect_ratio,r_frame_rate,time_base,pix_fmt \
  -of default=noprint_wrappers=1 "$1"; }

echo "### Per-clip video params"
for f in A B C D E; do echo "-- $f.mp4"; probe $f.mp4; done

concat_copy() { # out in1 in2
  printf "file '%s'\nfile '%s'\n" "$2" "$3" > list.txt
  echo "## concat -c copy: $2 + $3 -> $1"
  ffmpeg -hide_banner -loglevel warning -y -f concat -safe 0 -i list.txt -c copy "$1" 2>&1 | sed 's/^/   [ffmpeg] /' || echo "   [EXIT $?]"
  if [ -f "$1" ]; then
    echo -n "   result duration/frames: "
    ffprobe -v error -select_streams v:0 -count_frames \
      -show_entries stream=nb_read_frames -show_entries format=duration \
      -of default=noprint_wrappers=1:nokey=1 "$1" | tr '\n' ' '; echo
  fi
}
echo; echo "### Stream-copy concat matrix (each pair = 2x 2s clips, expect ~4s / ~120 frames if clean)"
concat_copy out_AB.mp4 A.mp4 B.mp4   # identical -> expect clean
concat_copy out_AC.mp4 A.mp4 C.mp4   # res mismatch
concat_copy out_AD.mp4 A.mp4 D.mp4   # fps mismatch
concat_copy out_AE.mp4 A.mp4 E.mp4   # SAR mismatch

echo; echo "### Fallback: concat FILTER (re-encode) on the mismatched pair A+C"
ffmpeg -hide_banner -loglevel error -y -i A.mp4 -i C.mp4 \
  -filter_complex "[0:v]scale=1920:1080,setsar=1[v0];[1:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:-1:-1,setsar=1[v1];[v0][v1]concat=n=2:v=1:a=0[v];[0:a][1:a]concat=n=2:v=0:a=1[a]" \
  -map "[v]" -map "[a]" -c:v libx264 -c:a aac out_AC_filter.mp4 \
  && echo "   filter concat OK -> $(ffprobe -v error -show_entries format=duration -of default=nk=1:nw=1 out_AC_filter.mp4)s"
