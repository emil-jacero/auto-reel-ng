# Experiment 008 — What black/white/freeze analysis costs per minute of footage

- **Date:** 2026-10-05
- **Author:** Claude (agent for change `analysis-job`)
- **Time-box:** ≤ 1.5 h   **Status:** Confirmed (with a heavily loaded host; CPU time is the robust figure)
- **Unblocks:** `analysis-job` tasks 4.2/4.3 (the figure in HLD D-27); informs `analysis-auto-sweep`'s per-sweep
  cap and a later hardware-decode experiment. Decides nothing in `analysis-job`'s specs.

## Hypothesis

We believe the two-pass CPU analysis of an **original** clip (each pass decodes the whole clip in software,
`-an -vf <detectors> -f null -`) costs **well under real time for 1080p50 H.264** (< 0.5 s of wall time per
second of footage) and **around real time or more for 4K50** (≥ 0.5 s per second, H.264 and HEVC), so a
4K-heavy library is what the automatic sweep's cap must be sized for. Secondary: with the yield, a GPU render
queued while an analysis job runs overlaps only the clip in flight, and the next clip waits for the render.

## Why this matters

No figure existed (HLD silent; experiment 005 timed nothing). `analysis-auto-sweep` caps how much it queues per
sweep, and whether hardware decode or a `scale` prefilter deserves an experiment depends on this cost.

## Environment

- Bazzite (Fedora 44 base), kernel 7.2.7; AMD Ryzen AI 7 350 (8 cores / 16 threads), 62 GB RAM.
- GPU: AMD Radeon 860M (integrated, Krackan, `renderD128`), VAAPI. Analysis itself is CPU only.
- ffmpeg 8.1.3 (host build), the worktree's `auto-reel` (branch `feat/analysis-job`), Postgres 16 dev container,
  scratch database `arel_analysis_job`.
- **The host was shared with other agents' test suites and builds: load average 9 to 28 on 16 threads during
  the runs** (`artifacts/load-direct.txt`). ffmpeg's decoders use every thread, so **wall times are inflated and
  noisy**; user+sys CPU time is the figure that transfers. Single host, single vendor; a quiet desktop CPU will
  show lower wall times.

## Method

`run.sh` (entry point; `DEV` = the scratch area, `DATABASE_URL` = the scratch database):

- **Inputs** (read-only originals from `auto-reel-media`, **symlinked** into scratch libraries; nothing written
  under `auto-reel-media`):
  - `samples/h264-1080p50-aac.mp4` — H.264, 1920x1080, 50 fps, 24.96 s;
  - `samples/h264-4k50-aac-119mbps.mp4` — H.264, 3840x2160, 50 fps, 119 Mb/s, 30.24 s;
  - **no 4K HEVC original exists in `auto-reel-media`** (its only HEVC clip is a 1080p rotated phone clip), so a
    4K HEVC original was derived from the 4K H.264 sample with `hevc_vaapi` (HEVC Main, 3840x2160, 50 fps,
    ~70 Mb/s, 30.24 s) into the scratch area. Its decode cost stands for a camera's 4K HEVC; a 10-bit or
    higher-bitrate source would cost more;
  - the render event: the four 1080p50 H.264 clips of `input/2024/2024-06-27 - grillning med grannar`
    (61.4 + 39.8 + 20.6 + 27.8 s = 149.8 s).
- **A — direct**: the exact pass-1 and pass-2 argument vectors of `auto_reel_ng.analysis.filters`
  (`blackdetect=d=2:pic_th=0.98:pix_th=0.1,freezedetect=n=0.003:d=2` and `negate,blackdetect=…`), run with
  `/usr/bin/time -f "%e %U %S"`, two repetitions.
- **B — real worker**: `auto-reel analyze <samples> --enqueue --force`, then `auto-reel worker --device cpu`
  with the `analysis` handler; job wall time = `finished_at - started_at` from the jobs table (one clip per job,
  so it includes the probe and both passes).
- **C — beside a GPU render**: `auto-reel worker` (VAAPI) renders the 4-clip event alone (`enqueue --force`);
  then a forced 4-clip `analysis` job is queued, and 3 s after it starts the same render is queued again. Each
  clip's finish time is its sidecar entry's mtime.

## Results

### A — direct, two passes (seconds)

| sample | footage | run | pass 1 wall / user / sys | pass 2 wall / user / sys |
|---|---|---|---|---|
| H.264 1080p50 | 24.96 s | 1 | 3.24 / 24.20 / 0.85 | 3.79 / 25.75 / 0.89 |
| H.264 1080p50 | 24.96 s | 2 | 3.52 / 24.62 / 0.82 | 3.23 / 25.44 / 0.89 |
| H.264 4K50 119 Mb/s | 30.24 s | 1 | 13.77 / 81.15 / 1.69 | 13.56 / 87.96 / 1.81 |
| H.264 4K50 119 Mb/s | 30.24 s | 2 | 16.00 / 83.78 / 3.01 | 21.96 / 94.99 / 2.35 |
| HEVC 4K50 ~70 Mb/s (derived) | 30.24 s | 1 | 31.06 / 89.80 / 1.33 | 19.11 / 82.85 / 1.12 |
| HEVC 4K50 ~70 Mb/s (derived) | 30.24 s | 2 | 32.01 / 93.06 / 1.92 | 25.25 / 93.34 / 1.41 |

### B — the real `analysis` job per event (wall, claim to done)

| event | footage | job wall |
|---|---|---|
| H.264 1080p50 | 24.96 s | 7.28 s |
| H.264 4K50 | 30.24 s | 28.50 s |
| HEVC 4K50 | 30.24 s | 43.93 s |

### Per minute of footage (both passes)

| source | wall s / min (A runs; B) | CPU s / min (user+sys, A runs) |
|---|---|---|
| H.264 1080p50 | 16.9, 16.2; 17.5 | 124, 124 |
| H.264 4K50 | 54, 75; 57 | 342, 365 |
| HEVC 4K50 | 100, 114; 87 | 347, 376 |

So on this 8-core APU, **about 2 CPU-seconds per second of 1080p50 footage and about 6 per second of 4K50**, both
codecs; with all 16 threads available that is roughly **a quarter of real time for 1080p50 and about real time
for 4K50 H.264**, HEVC 4K slower in wall time (1.5 to 1.9 times real time under this load; its CPU time equals
H.264's, so the difference is how well its decoder threads under contention).

### C — beside a GPU render (`artifacts/beside.txt`, `beside-clip-finish-utc.txt`; times UTC)

- Render alone: **40.98 s**. Render queued 3 s into the running analysis job: **35.16 s** (the host's load fell
  between the two runs, from ~19 to ~9; not a clean A/B, but no slowdown is visible).
- Analysis claimed 07:55:51.35; render claimed 07:55:57.37 and done 07:56:32.53.
- Clip 1 (61.4 s, in flight when the render was queued) finished 07:56:04.96, **overlapping the render by 7.6 s**.
- Clip 2 (39.8 s) finished 07:56:41.03, **8.5 s after the render ended**: it started only after the render (yield
  poll ≤ 1 s, then ~8 s of work, the same 0.2 s/s rate as clips 1, 3, 4). Clips 3 and 4 finished 07:56:45.64 and
  07:56:51.73. The whole job (149.8 s of 1080p50) took 60.4 s including the 35 s it waited.

## Verdict

**Confirmed.** 1080p50 H.264 costs 0.27–0.29 s of wall time per second of footage (< 0.5), and 4K50 costs 0.9 to
1.9 (≥ 0.5) for both codecs; CPU time is ~2.1 CPU-s/s at 1080p50 and ~5.7–6.3 CPU-s/s at 4K50. The secondary claim
holds: the render overlapped only the clip in flight and the next clip waited for it. Not tested: a quiet host,
10-bit HEVC, 4K60/100 Mb/s phone footage, hardware decode, a `scale` prefilter, merging the two passes (each pass
decodes the clip again: half the cost is the second decode), several analysis jobs at once.

## Decision & next action

- Recorded in HLD D-27 (`analysis-job`): **~17 s of wall time and ~2 CPU-min per minute of 1080p50 H.264; ~1 to
  1.9 min of wall time and ~6 CPU-min per minute of 4K50** on this APU.
- For `analysis-auto-sweep`: size the cap in **minutes of footage, not events** (a 4K event costs 3–6x a 1080p
  one); an hour of 4K footage is about an hour of a fully used CPU here, so trickling (lowest priority, one
  slot, yielding to renders and proxy jobs, as built) is the right shape.
- Worth an experiment of its own: **one decode for both passes** (`split` into the two detector chains: the
  dominant cost is decoding, done twice today), then VAAPI decode with `hwdownload` for H.264/HEVC. Either needs
  a check that the detections are unchanged (experiment 005's calibration is on software-decoded frames).

## Open questions / follow-ups

- The figures should be repeated on a quiet host for the HLD's wall numbers; the CPU numbers are stable (two runs
  within 7%).
- Disk read rate was not the limit here (119 Mb/s is ~15 MB/s); a NAS-mounted library could change that.
