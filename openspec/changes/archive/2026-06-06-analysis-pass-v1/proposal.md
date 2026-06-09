## Why

auto-reel had no way to find dead footage — long black/white/frozen spans stayed in the
final movie, or had to be cut by hand. HLD §4.5 calls for an analysis pass that *suggests*
cut ranges. Experiment 005 already resolved the hard part — detection thresholds calibrated
against synthetic ground truth with **zero false positives** on real daytime footage (§8.6),
so this is now spec-ready. The render pipeline (phase #4) already consumes `Trim` spans, and
the `Trim.reason` field was deliberately designed (D-K) for the values `black`/`white`/`freeze`,
so analysis output has a clean place to land later.

## What Changes

- Add an engine-only **analysis pass**: per clip, run ffmpeg detection filters and parse the
  log into a list of `Segment{start, end, kind, confidence}` (`kind ∈ {black, white, freeze}`).
- Detect with the **exp-005 thresholds** as defaults, all configurable: black/white via
  `blackdetect` (`pic_th=0.98`, `pix_th=0.10`); **white = `negate,blackdetect`** (reuses the
  same machinery, range-robust); freeze via `freezedetect` (`n=0.003`); min-duration `d=2.0s`.
- Run **two ffmpeg passes per clip**: pass 1 = `blackdetect`+`freezedetect` together; pass 2 =
  `negate,blackdetect` for white (`negate` rewrites the stream, so it cannot share pass 1).
- **Resolve overlap with precedence `black`/`white` > `freeze`** — a static black/white span is
  also frozen; the layer must not double-report it (a hard requirement from exp 005, not an edge case).
- Cache raw detections to a **sidecar under `.auto-reel/cache/`** (HLD §4.5), keyed by clip
  identity + content signal (mtime/size or hash) so stale results re-run when a clip changes.
- Detections are **suggestions, never auto-applied**. Because no approver surface exists yet
  (CLI/GUI are later phases), v1 **stops at detect + cache**: it does **not** write to `reel.yaml`.
- Analysis is a **separate explicit pass**, never auto-run inside `scan_event` (keeps scan cheap).

## Capabilities

### New Capabilities
- `media-analysis`: Detect black/white/freeze spans in a clip via ffmpeg filters and return
  overlap-resolved `Segment`s with calibrated default thresholds (exp 005). Suggestion-only;
  no editorial mutation.
- `analysis-cache`: Persist and retrieve detection results in a `.auto-reel/cache/` sidecar,
  invalidated when the source clip changes — a lightweight, forward-compatible down-payment on
  the §8.14 render-fingerprint question.

### Modified Capabilities
<!-- None. The Segment→Trim mapping (writing approved trims into reel.yaml) belongs to the
     future CLI/GUI consumer, not this change, so reel-document requirements are unchanged. -->

## Impact

- **New module** `auto_reel_ng/analysis/` (detection runner, parser, overlap resolver, Segment
  type, sidecar cache). New tests in the phases-1-5 style.
- **Reuses** `FfmpegRuntime` (`ffmpeg/runtime.py`) to run filters and read log output, and
  `ClipMetadata` (`probe/media.py`) for duration/identity. No changes to either.
- **No change** to `reel/document.py`, the render pipeline, or `scan_event`. The
  `Segment → Trim` consumer is explicitly deferred to a future CLI/GUI phase.
- ffmpeg detection is CPU-only (exp 005) — no GPU/accel-profile dependency. Unit tests fixture
  from recorded ffmpeg log output (exp 005 artifacts); a live integration test sits behind a
  `has-ffmpeg` marker.

## Non-goals

- **No `reel.yaml` writes and no approve→`Trim` path.** Suggestions are produced and cached only;
  applying them is a later phase's job (its consumer maps `Segment → Trim{reason=…}`).
- **No ML** (PySceneDetect, blur/quality models) — Stage 2, behind this same `Segment` interface (§8.7).
- **No full §8.14 render fingerprint.** The cache key is a minimal clip-change signal, designed to
  stay compatible with §8.14, not to solve it.
- **No GUI review surface** — that is GUI v2 (phase #9).
- **No richer `confidence` signal.** v1 populates `confidence` coarsely (filter-fired); `signalstats`
  YAVG-derived confidence is left as future work, with the field reserved in the type.
