#!/usr/bin/env bash
# Experiment 005 — black / white / freeze detection thresholds (HLD §8.6)
# Builds a synthetic ground-truth clip with KNOWN spans, runs the ffmpeg detectors
# at candidate thresholds, then runs the same detectors on real footage to gauge
# false positives. CPU-only; no GPU needed.
set -euo pipefail
cd "$(dirname "$0")"
A=artifacts
mkdir -p "$A"
FF="ffmpeg -hide_banner -y"
MEDIA="../../../auto-reel-media/input/2024/2024-06-27 - grillning med grannar"

# ---------------------------------------------------------------------------
# 1. Build synthetic ground-truth segments (720p25), then concat.
#    Ground truth:  BLACK [0,3]   WHITE [8,11]   FREEZE(gray static) [16,20]
#    (the black and white spans are also static => freezedetect should also flag them)
# ---------------------------------------------------------------------------
$FF -f lavfi -i "color=black:s=1280x720:r=25:d=3"            -pix_fmt yuv420p "$A/seg1_black.mp4"  2>/dev/null
$FF -f lavfi -i "testsrc2=s=1280x720:r=25:d=5"              -pix_fmt yuv420p "$A/seg2_motion.mp4" 2>/dev/null
$FF -f lavfi -i "color=white:s=1280x720:r=25:d=3"          -pix_fmt yuv420p "$A/seg3_white.mp4"  2>/dev/null
$FF -f lavfi -i "testsrc2=s=1280x720:r=25:d=5"             -pix_fmt yuv420p "$A/seg4_motion.mp4" 2>/dev/null
$FF -f lavfi -i "color=gray:s=1280x720:r=25:d=4"           -pix_fmt yuv420p "$A/seg5_freeze.mp4" 2>/dev/null
printf "file '%s'\n" seg1_black.mp4 seg2_motion.mp4 seg3_white.mp4 seg4_motion.mp4 seg5_freeze.mp4 > "$A/concat.txt"
(cd "$A" && ffmpeg -hide_banner -y -f concat -safe 0 -i concat.txt -c copy gt.mp4 2>/dev/null)
echo "== ground truth built: BLACK[0,3] WHITE[8,11] FREEZE[16,20] =="

# ---------------------------------------------------------------------------
# 2. BLACK detection on ground truth — default vs stricter
# ---------------------------------------------------------------------------
echo "### blackdetect d=2:pic_th=0.98 (defaults) on gt"      | tee "$A/black_gt.txt"
$FF -i "$A/gt.mp4" -vf "blackdetect=d=2:pic_th=0.98" -an -f null - 2>&1 | grep -i black_start | tee -a "$A/black_gt.txt" || true

# ---------------------------------------------------------------------------
# 3. WHITE detection — method A: negate then blackdetect (white -> black)
# ---------------------------------------------------------------------------
echo "### WHITE via negate,blackdetect d=2:pic_th=0.98 on gt" | tee "$A/white_gt.txt"
$FF -i "$A/gt.mp4" -vf "negate,blackdetect=d=2:pic_th=0.98" -an -f null - 2>&1 | grep -i black_start | tee -a "$A/white_gt.txt" || true

# 3b. WHITE method B: per-frame luma mean (YAVG) via signalstats, sample @5fps
echo "### YAVG (luma mean) histogram on gt @5fps"            | tee "$A/yavg_gt.txt"
$FF -i "$A/gt.mp4" -vf "fps=5,signalstats,metadata=print:key=lavfi.signalstats.YAVG" -an -f null - 2>&1 \
  | grep -oE "YAVG=[0-9.]+" | sort | uniq -c | tee -a "$A/yavg_gt.txt" || true

# ---------------------------------------------------------------------------
# 4. FREEZE detection on ground truth — default vs looser noise
# ---------------------------------------------------------------------------
for N in 0.001 0.003; do
  echo "### freezedetect n=$N:d=2 on gt"                     | tee "$A/freeze_gt_n$N.txt"
  $FF -i "$A/gt.mp4" -vf "freezedetect=n=$N:d=2" -an -f null - 2>&1 | grep -i freeze_start | tee -a "$A/freeze_gt_n$N.txt" || true
done

# ---------------------------------------------------------------------------
# 5. FALSE-POSITIVE check on real footage (bright sky, slow pans).
#    Run all three detectors; ANY hit on normal content is a false positive.
# ---------------------------------------------------------------------------
: > "$A/real_falsepos.txt"
for f in "$MEDIA"/s171000*.mp4; do
  b=$(basename "$f")
  echo "== $b ==" | tee -a "$A/real_falsepos.txt"
  echo "-- black (d=2:pic_th=0.98):"  | tee -a "$A/real_falsepos.txt"
  $FF -i "$f" -vf "blackdetect=d=2:pic_th=0.98" -an -f null - 2>&1 | grep -i black_start | tee -a "$A/real_falsepos.txt" || echo "   (none)" | tee -a "$A/real_falsepos.txt"
  echo "-- white (negate,blackdetect d=2:pic_th=0.98):" | tee -a "$A/real_falsepos.txt"
  $FF -i "$f" -vf "negate,blackdetect=d=2:pic_th=0.98" -an -f null - 2>&1 | grep -i black_start | tee -a "$A/real_falsepos.txt" || echo "   (none)" | tee -a "$A/real_falsepos.txt"
  echo "-- freeze (n=0.003:d=2):" | tee -a "$A/real_falsepos.txt"
  $FF -i "$f" -vf "freezedetect=n=0.003:d=2" -an -f null - 2>&1 | grep -i freeze_start | tee -a "$A/real_falsepos.txt" || echo "   (none)" | tee -a "$A/real_falsepos.txt"
done

# 5b. Real-footage brightness envelope: max per-frame YAVG (how close do bright
#     scenes get to a white threshold?) sampled @2fps.
echo "== real YAVG max per clip @2fps ==" | tee "$A/real_yavg.txt"
for f in "$MEDIA"/s171000*.mp4; do
  b=$(basename "$f")
  mx=$($FF -i "$f" -vf "fps=2,signalstats,metadata=print:key=lavfi.signalstats.YAVG" -an -f null - 2>&1 \
       | grep -oE "YAVG=[0-9.]+" | cut -d= -f2 | sort -n | tail -1)
  echo "$b  max_YAVG=$mx" | tee -a "$A/real_yavg.txt"
done

echo "DONE"
