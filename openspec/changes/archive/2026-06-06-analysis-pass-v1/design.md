## Context

This is HLD phase #6 (§4.5, research §8.6). Phases 1–5 shipped the engine as a stack of tested
library layers; analysis fits the same mold — a pure-ish module driven later by the CLI/API, with
no GUI or scheduler in scope yet.

The unusual thing about this slice: its *output* has no consumer in v1. The natural consumer is an
operator approving suggestions (GUI v2, phase #9) or a CLI apply step, neither of which exists. We
deliberately accept that and scope to **detect + cache** (explore decision, Option A), matching §4.5
verbatim ("raw detection output cached in a sidecar, **not** in `reel.yaml`"). The `Trim.reason`
field already reserves `black`/`white`/`freeze` (D-K) and the render pipeline already cuts on
`Trim` spans, so the eventual `Segment → Trim` mapping is a future consumer's job, not this change's.

Detection thresholds are not guesses — experiment 005 calibrated them against synthetic ground
truth and confirmed **zero false positives** on real daytime footage. This change encodes those
findings; it does not re-litigate them.

## Goals / Non-Goals

**Goals:**
- A `Segment{start, end, kind, confidence}` type and a per-clip `analyze` entry point that returns
  overlap-resolved segments.
- Exp-005 thresholds as configurable defaults; two-pass ffmpeg invocation; `black`/`white > freeze`
  overlap precedence.
- A `.auto-reel/cache/` sidecar that persists results and invalidates on clip change.
- Headless, fixture-driven tests (parse recorded ffmpeg logs into segments) plus a `has-ffmpeg`
  integration test.

**Non-Goals:**
- No `reel.yaml` writes, no approve→`Trim` path, no GUI review surface.
- No ML (PySceneDetect / quality models) — Stage 2 behind the same `Segment` interface (§8.7).
- No full §8.14 render fingerprint; the cache key is a minimal clip-change signal only.
- No GPU/accel-profile dependency — detection is CPU-only (exp 005).

## Decisions

**D-AN1 — New `auto_reel_ng/analysis/` module, parser split from runner.**
Keep the impure ffmpeg invocation (build args, run via `FfmpegRuntime`) separate from a **pure log
parser** (`str → list[raw span]`) and a **pure overlap resolver** (`list[Segment] → list[Segment]`).
This is what makes the bulk of the suite run without ffmpeg: parser and resolver are tested against
recorded log text (exp-005 artifacts), mirroring how the accel layer tests golden arg strings.
*Alternative:* one monolithic `analyze()` — rejected; it forces every test through a live decode.

**D-AN2 — White via `negate,blackdetect`, two passes per clip.**
Adopt exp-005's method A. `negate` rewrites the stream, so white detection cannot share the chain
with un-negated black/freeze; we issue **pass 1** = `blackdetect`+`freezedetect`, **pass 2** =
`negate,blackdetect`. *Alternative:* a `signalstats` YAVG threshold for white — rejected by exp 005
(re-derives the same result with a hand-tuned, range-fragile constant). YAVG is kept only as a
possible future confidence signal.

**D-AN3 — Overlap precedence `black`/`white` > `freeze`, applied after parsing.**
A static black/white region is also frozen, so `freezedetect` reports it; emitting both would
double-count. The resolver subtracts black/white spans from freeze spans, so each region carries
exactly one `kind`. This is a spec'd requirement, not a cleanup step.

**D-AN4 — Cache key = clip identity + content-change signal; sidecar is source of truth.**
The `.auto-reel/cache/` entry is keyed by clip identity plus a change signal (size+mtime by default;
allow a content hash as an option). On mismatch the entry is stale and detection re-runs; a missing,
unreadable, or unparseable entry is treated as cold. The sidecar travels with the media and survives
a Postgres rebuild (consistent with D-7). The key shape is chosen to be a **forward-compatible
down-payment** on §8.14 — same family of signals the eventual render fingerprint will hash — without
committing to the fingerprint's composition here. *Alternative:* cache in Postgres — rejected for v1
(no DB in the engine yet, and §4.5 wants detections on disk beside the media).

**D-AN5 — Coarse confidence in v1.**
`blackdetect`/`freezedetect` emit spans, not scores, so v1 sets `confidence` to a coarse fired-value.
The field stays in the type so an ML stage (or a `signalstats` pass) can populate it richly later
without a type change.

**D-AN6 — Explicit pass; fail loud.**
`analyze` is never called from `scan_event` (scanning stays cheap). An ffmpeg non-zero exit or an
undecodable clip raises a typed analysis error naming the clip — never a silent empty result
(engine-wide fail-loud rule; the original auto-reel fake-metadata bug being avoided).

## Risks / Trade-offs

- **Output with no consumer in v1** → Accepted by design (Option A). The cache is the deliverable;
  the approve/apply surface lands with the CLI/GUI. Documented as a non-goal so it is a choice, not a gap.
- **Dark night/indoor footage may approach the black `pix_th`** (exp 005 caveat — sample was daytime)
  → Thresholds are configurable; re-validate on dark footage before any unattended use. Detections
  are suggestions, never auto-applied, which bounds the blast radius.
- **Full-range (PC, 0–255) sources shift luma levels** → Using `negate,blackdetect` rather than a raw
  YAVG constant insulates white detection from the range question (exp 005).
- **`size+mtime` cache key misses in-place edits that preserve both** → Offer an opt-in content hash
  for correctness-sensitive runs; mtime is the cheap default. Same trade-off §8.14 must settle, so
  the key stays compatible with that decision.
- **`freezedetect` `n=0.003` tuned on synthetic static frames** → may need field tuning on real
  "paused camera" footage; it is configurable, defaults are documented as exp-005-validated suggestions.

## Open Questions

- Where do analysis **config defaults** ultimately live — a dedicated analysis block, or folded into
  project `config.yaml` (D-2)? v1 can accept them as call parameters and defer the config-file home
  until the config-layering slice exists.
- Exact on-disk sidecar **format/layout** under `.auto-reel/cache/` (one file per clip vs per event;
  JSON shape) — settle during spec apply; it is private to this module in v1.
