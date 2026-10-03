# Experiment 007 — Is a GPU render slower while a proxy job runs beside it?

- **Date:** 2026-10-03
- **Author:** auto-reel-ng (`proxy-job` change)
- **Time-box:** ≤ 2h   **Status:** **Refuted** (on this host, which was loaded by other work throughout)
- **Unblocks:** `proxy-job` task 7.1 (design decision 9); HLD D-21 "proxy job" rules. Proposes a follow-up change.

## Hypothesis
With a GPU-classified render of one event running, a proxy job on other events running throughout makes the
render's wall time **at most 1.15x** its solo time (median of three, warm page cache).

## Why this matters
A proxy job holds a CPU token and no GPU token, so the worker lets a GPU render start beside it. That is only
a good rule if the render does not pay for it: the user's renders are the product, proxies are preparation.

## Environment
- Host `mrFrame`: AMD Ryzen AI 7 350 (16 CPUs), Fedora (Bazzite) kernel 7.2.4, ffmpeg 8.1.2, Mesa 26.2.2 radeonsi;
  `vainfo` names the VAAPI device on `renderD128` as **Radeon 860M** (an APU: the GPU shares system memory with the
  CPU); worker profile `amd`, `render_node=/dev/dri/renderD128`. AMD VAAPI only; Intel and NVIDIA untested.
- **The host was not idle.** Other agents ran builds and test suites on it the whole time: load average 6 to 19
  on 16 CPUs (`artifacts*/host.txt`). Solo render times alone vary from 43 to 79 s between runs. The arms
  alternate (A, B, A, B, ...) so a drift hits both, but this is a noisy measurement and it says so.
- Sources are symlinks to the read-only `auto-reel-media` fixture and samples; the library, output and proxy
  cache are scratch directories under the change's dev directory.

## Method
`run.sh` builds a scratch project and starts a **real** `auto-reel worker` (default `proxy_slots` 1, `cpu_slots`
1, one GPU session). `measure.py` drives it through the job queue:
- Render event R: the 4 conformant fixture clips (s1710001-4) plus a 1080p50 clip, a portrait clip and a 720p25
  clip (about 3.5 minutes of footage). The mixed frame rates and shapes force most clips through the GPU
  normalize path. The render is enqueued with `--force` so it always renders.
- **Arm A** (alone): the render only. **Arm B** (beside): the proxy cache is emptied; three proxy jobs are queued
  (ProxyA: 4K50 + Sony 4K25; ProxyB: legacy MPEG-4 + 1080p25; ProxyC: Sony 1080p25 PCM + HEVC rotated + 720p
  rotated; about 10 minutes of footage, all from different files than R's); when the first is running, the render is
  queued. The render's time is `finished_at - started_at` of its row. The proxy jobs covered 89 to 100 % of the
  render's window in every run (`overlap_s`).
- 1 warm-up render, then 3 pairs of (A, B), then one cold pair (sources evicted from the page cache with
  `posix_fadvise(DONTNEED)`; no root needed).
- The lever (`capped_worker.py`, disposable): the same worker with the proxy x264 encode capped by `-threads N`.
  A diagnostic variant also forces the CPU decode path (no VAAPI use by proxies at all).

Run 1 used only the four conformant clips: the render took 5 s (a near stream-copy, no real GPU work), so it
measured nothing (alone 5.2 s, beside 5.6 s; kept in `artifacts/results-run1-conformant.txt`). The library was
changed to the mixed event above.

```
DEV=<scratch> REPS=3 experiments/007-proxy-job-concurrent-render/run.sh                      # artifacts/
PROXY_X264_THREADS=4 OUT_SUFFIX=-threads4 DEV=<scratch> REPS=3 .../run.sh                    # artifacts-threads4/
PROXY_X264_THREADS=2 OUT_SUFFIX=-threads2 DEV=<scratch> REPS=3 .../run.sh                    # artifacts-threads2/
PROXY_FORCE_CPU=1 PROXY_X264_THREADS=4 OUT_SUFFIX=-cpupath-threads4 DEV=<scratch> REPS=3 .../run.sh
```

## Results
Render wall time in seconds (warm runs 1 to 3, then the median), and the ratio of medians; "pairs" is
beside/alone for each adjacent pair.

| Proxy job configuration | Alone | Beside a proxy job | Median ratio | Pairs | Cold pair (alone / beside) |
|---|---|---|---|---|---|
| as built (hybrid path, x264 default threads) | 60.5, 47.9, 47.5 (47.9) | 73.8, 63.8, 72.7 (72.7) | **1.52** | 1.22, 1.33, 1.53 | 55.2 / 74.4 (1.35) |
| x264 `-threads 4` | 49.3, 43.7, 43.4 (43.7) | 67.9, 68.3, 65.4 (67.9) | **1.56** | 1.38, 1.56, 1.51 | 45.7 / 70.7 (1.55) |
| x264 `-threads 2` | 63.4, 78.6, 54.5 (63.4) | 81.3, 85.4, 66.3 (81.3) | **1.28** | 1.28, 1.09, 1.22 | 44.5 / 65.9 (1.48) |
| CPU decode path, `-threads 4` | 48.1, 49.3, 64.7 (49.3) | 72.2, 71.7, 71.1 (71.7) | **1.45** | 1.50, 1.45, 1.10 | 50.4 / 65.8 (1.31) |

The proxy jobs themselves took 52 to 84 s for the three events (`proxy_total_s` in `results.txt`), i.e. they ran
at full speed throughout, and all three always finished with `done`.

## Verdict
**Refuted.** In 16 of 16 adjacent pairs (warm and cold) the render was slower beside the proxy job, in 14 of
16 by more than 20 %; the medians are 1.28 to 1.56 times the solo time, against a bound of 1.15. The noise of the
host is large (solo runs spread by up to 1.8x), so the exact factor is not known, but 1.15 is far below every
measured pair except two (1.09 and 1.10, in the noisiest sets).

The lever did not rescue it: capping the proxy's x264 to 4 or 2 threads, and removing the proxy's VAAPI use
altogether (CPU decode path), left the render 1.3 to 1.6 times slower. So the cost is not x264's threads and not the
GPU decode of the proxies. What remains, not separated by this experiment: memory bandwidth (the GPU is an APU
and shares system memory with the CPU), the one disk that both read, and the CPU parts of the render (demux, the
copy/concat, audio, which x264 on a few threads still contends with on a host already at a load of 6 to 19).
Not tested: a discrete GPU, Intel or NVIDIA, an idle host, and a library on its own disk.

## Decision & next action
- The `proxy-job` change ships as specified: the job is correct, cancelable and behind renders **in the claim
  order**. It does **not** claim that a render beside a proxy job is unaffected; the README and HLD say a
  render beside a running proxy job can take about 1.3 to 1.5 times as long on this host, and where the claim order and
  `proxy_slots` stop.
- **Follow-up (not built here): `proxy-yield`.** A proxy job should not *start its next clip* while a render is
  running (the proxy handler checks `list_by_status(RUNNING, kind=render)` between clips, which costs nothing and
  needs no preemption); a clip already encoding finishes. This cuts the overlap from minutes to one clip's
  encode (seconds). It is a small change in `scheduler/proxy_job.py`, deliberately left to its own change
  because it changes when a proxy job finishes, which the timeline's Prepare state shows.
- A thread cap is not worth a setting: it did not help here.

## Open questions / follow-ups
- Repeat on an idle host (this one was shared) and with the library on a separate disk to see how much of the 1.3
  to 1.5 is I/O.
- Is the APU's shared memory the cause? A discrete GPU would tell (the project's own host lists an RX 9070 XT
  on `renderD128` in `CLAUDE.md`; `vainfo` here reported the 860M, so the render node order may differ between boots).
