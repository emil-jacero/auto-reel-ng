## Context

This is HLD slice #4 — the render pipeline. Its three inputs already exist and are typed:

- `event-resolution` produces a `RenderPlan` (`auto_reel_ng/event/plan.py`): chapters → `ResolvedChapter` →
  `ResolvedClip` with `identity`, `cut_spans`, `rotate`, `is_title`, plus an opaque merged `look`.
- `media-probe` (`auto_reel_ng/probe/`) supplies per-clip facts: codec/profile, w/h, SAR/DAR, pix_fmt,
  rotation, HDR/transfer, fps, audio params — fail-loud, never fabricated.
- `acceleration-profile` (`auto_reel_ng/accel/`) returns per-op `OpFragment`s with `frames_in/out`, plus
  `insert_transfers()`, capability flags (`pad_filter`, `can_overlay_hw`, `can_tonemap_hw`, `usable_encoders`,
  `decode_method`), and best-accelerator selection. Verified on AMD VAAPI; other vendors gated by self-test.

The spikes set hard constraints: stream-copy concat is clean only when codec/profile/W/H/SAR/pix_fmt/time_base
+ audio all match, and resolution/SAR mismatches **mux at exit 0 while breaking players** (exp 001); AMD
normalize is native `scale_vaapi,pad_vaapi` and is the fastest path, but `overlay_vaapi` is unsupported and
every GPU HDR-tonemap path fails (exp 003/004). `ffmpeg-runtime` already provides structured command execution
and `-progress` parsing, so no changes there.

New code lives under `auto_reel_ng/render/`.

## Goals / Non-Goals

**Goals:**
- Turn a `RenderPlan` + selected `AccelProfile` into one verified movie per event with real chapters.
- Make "look" features pluggable from day one via a general decorator seam — titles (#5) are the first user.
- Keep command-building pure and golden-testable without a GPU; isolate the side-effecting runner.
- Default to the safe normalize path; treat stream-copy as a narrow, probe-guarded, output-verified fast path.

**Non-Goals:**
- Rendering title/card/overlay *content* (#5) — we ship the seam + a `none` default decorator only.
- Detecting trims (#6) — `cut_spans` arrive already approved on the plan.
- Scheduling, GPU-aware concurrency, WebSocket progress, Postgres job state (#7) — the orchestrator renders one
  movie when called and exposes a progress callback.
- Deciding *whether* an event is stale (§4.13) — that gates #7; here we render on request with overwrite/force.

## Decisions

### D-A: Segment list is the pipeline's spine; a clip × its trims = N segments
The unit of work is a `Segment`, not a clip. Flattening the plan yields an ordered list where a trimmed clip
becomes one segment per kept span. Concat, chapters, and decorators all operate on this list. **Why:** trims,
synthetic title cards, and future transitions are all naturally "more or fewer segments"; modelling clips
directly would special-case each. **Alternative considered:** keep clips whole and express trims as
filter-graph `select`/`trim` — rejected because a trimmed clip can't stream-copy across its own gap and the
segment model makes that fall out for free.

### D-B: The decorator seam (inserter / attacher), not a "title" feature
A decorator is a pure `(plan, target, segments) -> segments`. Two shapes cover every look feature we foresee:
**inserter** (adds synthetic segments — title card, intro, outro, transition bumper) and **attacher** (adds an
`OverlaySpec` to existing segments — title-over-footage, watermark, lower-third). `Segment.overlays` is a
first-class field so the normalize stage composites overlays generically. Decorators are selected by name from
the resolved `look`/config (D-2) and live in a registry, mirroring the project's pluggable-ingest-layout (D-6)
and vendor-profile patterns. v1 ships only `none`; #5 registers real title decorators. **Why:** the user
requirement is explicitly "configurable, with more options later" — so the pipeline must not know what a
"title" is. **Alternative considered:** a fixed title step with a strategy enum — rejected as not extensible to
transitions/watermarks without reopening the pipeline.

### D-C: Normalize-to-intermediates, then demuxer `-c copy` — not one big filter_complex
Each non-conforming segment is normalized to its own intermediate file; the uniform set is then joined with the
concat demuxer and `-c copy`. **Why:** per-segment commands are independently runnable (the GPU-aware scheduler
in #7 wants per-clip jobs), give clean per-segment progress, and isolate a failure to one segment. The single
giant `filter_complex` graph (all inputs open, one encode) avoids intermediates but kills per-clip parallelism,
makes mixed hw-frame-contexts harder (research §8.3), and turns any one bad clip into a whole-movie failure.
**Audio is normalized hard** in every normalize pass (resample to target params) so the join copies only
video, sidestepping the AAC-priming gap exp 001 saw even between identical clips. **Trade-off:** segments that
already conform still get re-encoded unless they pass copy-eligibility (D-D).

### D-D: Guarded copy fast path, decided from probe data and verified after
A segment skips normalization only if it is a source segment, untrimmed, overlay-free, needs no
rotation/tonemap, and ffprobe-equal to the target spec. The whole-set equivalence pre-flight (codec/profile/
W/H/SAR/pix_fmt/time_base + audio) then decides whether the demuxer `-c copy` join is safe — **never** the
ffmpeg exit code. After assembly, the output is re-probed against the target spec. **Why:** exp 001 proved the
fast path silently ships broken files; the only safe shape is probe-before, verify-after. **Alternative
considered:** normalize-always (no copy) — simpler and was on the table, but the user chose to keep the
optimization, so it ships guarded.

### D-E: Target spec derived from look + first clip + profile
The common canvas = resolution from `look.target_resolution`, fps from the first clip's probed fps (carried
from auto-reel's behavior), codec/pix_fmt from look, SAR 1:1, and common audio params. The codec is validated
against the selected profile's `usable_encoders` (or CPU fallback); an unencodable codec fails loud. AV1 is a
first-class option (D-5). **Why:** deterministic, and grounds the equivalence check in one explicit spec
object every segment is compared against.

### D-F: Rotation/HDR ship on CPU fallbacks (documented, known-slow)
Rotation uses a hardware path where available, else CPU transpose; HDR uses hardware tonemap only when
`can_tonemap_hw`, else CPU `zscale,tonemap` with a loud slowness warning (~0.35× realtime on AMD, exp 004).
**Why:** the user chose "spec with CPU fallbacks" over spiking first; both are correctness-complete now and
optimizable per vendor later. `insert_transfers()` already inserts the hwdownload/hwupload these CPU detours
require.

### D-G: Pure builder + thin runner; golden-string tests
Command construction (segment list, target spec, per-segment arg lists, concat args, ffmetadata) is pure and
unit-tested against **golden ffmpeg command strings** — no GPU needed, matching how the accel layer is tested.
A thin orchestrator runs the commands via `ffmpeg-runtime`, probes intermediates/outputs, and exposes a
progress callback. Integration tests that actually encode sit behind a "has GPU" marker.

## Risks / Trade-offs

- **Real camera files differ from synthetic spike inputs (variable GOP, edit lists, B-frames)** → exp 001
  flagged these aren't probe-visible. Mitigation: audio is always re-encoded; copy-eligibility is conservative
  (untrimmed source only); the post-render verification re-probes the actual output, catching a copy that
  passed pre-flight but produced a broken stream. A follow-up spike on real footage can widen the fast path
  later.
- **Mixed hardware frame contexts in one chain** (e.g. CPU tonemap interrupting a VAAPI graph) → relies on
  `insert_transfers()` correctness; research §8.3 is only partly settled. Mitigation: per-segment commands keep
  each chain small and single-input; golden tests assert the transfer markers land where expected.
- **HDR throughput cliff** (~0.35× realtime, CPU-only on AMD) → a single HDR clip slows a whole movie.
  Mitigation: loud warning now; flagged for the scheduler (#7) to treat HDR segments as heavy. Not blocking.
- **fps taken from the first clip** can be wrong if the first clip is an outlier → carried from auto-reel for
  compatibility; revisit if it bites. The target spec makes the chosen fps explicit and logged.
- **Decorator ordering** (multiple decorators, e.g. title + watermark) must be deterministic → decorators apply
  in a defined order from config; construction is specified deterministic and golden-tested.

## Open Questions

- Where do normalized intermediates live and when are they cleaned up — a temp dir per render vs a reusable
  `.auto-reel/cache/`? (Caching intermediates interacts with #7/§4.13 staleness; v1 can use an ephemeral temp
  dir and revisit.)
- Should copy-eligible source segments still get audio re-encoded for join safety, or is a fully-conforming
  source trusted to stream-copy audio too? **Resolved (v1):** a copy-eligible segment is passed through
  entirely unchanged — no audio re-encode — per `clip-normalize` spec 6.1 ("passed through unchanged"). The
  residual AAC-priming risk is bounded by two guards: copy-eligibility is conservative (untrimmed, conforming
  source only), and the whole-set equivalence pre-flight + re-normalize-to-uniform fallback (`movie-assembly`)
  re-encodes the copied segments if the join would not be clean. Revisit if real footage surfaces a priming gap.
- Exact `OverlaySpec` shape (time-varying alpha for fades vs static) — minimal now, finalized with #5 when real
  overlay content exists.
