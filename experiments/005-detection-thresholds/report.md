# Experiment 005 — black / white / freeze detection thresholds

- **Date:** 2026-06-05
- **Author:** auto-reel-ng (spike)
- **Time-box:** ≤ 1.5h   **Status:** **Confirmed** — defaults calibrated, white method chosen, zero false positives
- **Unblocks:** HLD §4.5 (analysis pass), §8.6, OpenSpec phase #6 (analysis v1)

## Hypothesis
The three ffmpeg detection filters can drive analysis v1 with **default-ish thresholds** that (a) catch real
black/white/freeze spans and (b) do **not** false-fire on ordinary bright/handheld footage. "White" has no
native filter; we expect either `negate,blackdetect` or a `signalstats` luma-mean threshold to work. We'll
know we're right if a synthetic clip with known spans is detected at the right timestamps while the real BBQ
clips stay clean.

## Why this matters
Analysis (#6) emits suggested cut-ranges that become `reel.yaml` `trims` (the open-string `reason` field from
#3 was designed for exactly `black`/`white`/`freeze`). Thresholds picked blind would either miss real dead
footage or trim good content. §8.6 demanded these be set on evidence before speccing.

## Environment
- Fedora 43, ffmpeg **7.1.3** (CPU only — no GPU needed for detection). Filters present: `blackdetect`,
  `freezedetect`, `signalstats` (+ `blackframe`).
- **Synthetic ground truth** (`artifacts/gt.mp4`, 720p25, 20s): `BLACK[0,3]` · motion[3,8] · `WHITE[8,11]` ·
  motion[11,16] · `FREEZE(static gray)[16,20]`. Motion segments are `testsrc2`.
- **Real footage:** `auto-reel-media/.../2024-06-27 - grillning med grannar/` — 4× 1080p50 daytime BBQ clips
  (20–61s), bright sky and slow handheld pans = the realistic false-positive stressors.

## Results

**Ground truth — every span caught at the right timestamp:**

| Detector | Command | Result on `gt.mp4` | Ground truth | Verdict |
|---|---|---|---|---|
| black  | `blackdetect=d=2:pic_th=0.98` | `black_start:0 black_end:3` | BLACK[0,3] | ✅ exact |
| white  | `negate,blackdetect=d=2:pic_th=0.98` | `black_start:8 black_end:11` | WHITE[8,11] | ✅ exact |
| freeze | `freezedetect=n=0.001:d=2` | starts @ `0, 8, 16` | FREEZE[16,20] (+static black/white) | ✅ (see overlap) |

**Luma envelope (`signalstats` YAVG, 0–255 code space) is cleanly trimodal:** black `YAVG=16`, normal/motion
content `YAVG≈123–126`, white `YAVG=235` (limited/TV range). A YAVG≥~200 cut separates white from content
with huge margin.

**Real footage — ZERO false positives** across all 4 clips (`artifacts/real_falsepos.txt`): no black, no
white, no freeze hits at the above thresholds. Brightest real frame `max_YAVG=124.6` (`artifacts/real_yavg.txt`)
— **110 code-values below** the 235 white level and well under any sane white cutoff. Daytime sky does not
read as white; handheld pans do not read as frozen.

## Decisions / recommendations (feed straight into spec #6)

1. **White = `negate,blackdetect` (method A), not a bespoke YAVG threshold.** It reuses blackdetect's exact
   `d`/`pic_th`/`pix_th` machinery (symmetry: one code path, inverted input), hit the white span exactly, and
   the YAVG approach would just re-derive the same thing with a hand-tuned constant. Keep `signalstats` YAVG
   only as an optional confidence signal.
2. **Default thresholds (validated):** black/white `pic_th=0.98`, `pix_th=0.10` (ffmpeg defaults); freeze
   `n=0.003` (slightly looser than the 0.001 default — same hits here, more tolerant of sensor noise on real
   frozen frames); **minimum duration `d=2.0s` for all three.** Expose all as config; these are the defaults.
3. **Freeze OVERLAPS black/white** — a static black/white span is *also* frozen (freeze fired at 0 and 8, the
   black and white spans). The analysis layer MUST resolve overlap: **precedence black/white > freeze**, so a
   span isn't reported as two kinds. This is a real `Segment` requirement, not an edge case.
4. **`Segment{start, end, kind, confidence}`** confirmed as the output type; detectors emit start/end pairs
   directly parsable from ffmpeg log lines (`black_start/black_end`, `freeze_start/freeze_end`).

## Threats to validity / caveats
- Real sample is **daytime** footage. Very dark night/indoor clips could approach the black `pix_th` — the
  black default should be re-checked on dark footage before trusting it unattended (still safe: detections are
  *suggestions* the operator approves, never auto-applied — HLD §4.5).
- Limited-range (TV) luma assumed (black=16, white=235). Full-range (PC, 0–255) sources shift these; using
  `negate,blackdetect` rather than a raw YAVG constant insulates us from the range question.
- `freezedetect` `n` is a normalized noise tolerance; `0.003` validated on synthetic static frames, may want
  field-tuning against real "paused camera" footage (none in this sample).

## Reproduce
`bash run.sh` — builds `artifacts/gt.mp4`, runs all detectors on it and on the real clips, writes
`artifacts/{black_gt,white_gt,freeze_gt_*,yavg_gt,real_falsepos,real_yavg}.txt`.
