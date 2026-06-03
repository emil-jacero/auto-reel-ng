## Why

auto-reel's render path re-encoded every clip 2–3 times (convert → scale-pad → concat), ran scale/pad/overlay
on the CPU even with NVENC, wrote **chapters that never reached the container**, and let moviepy spawn its own
hardcoded-codec ffmpeg for title cards. The three foundations are now in place — `media-probe` (typed clip
facts), `acceleration-profile` (per-op ffmpeg fragments + frame-location tracking), and `event-resolution`
(a fully-explicit `RenderPlan`) — so this change builds the thing they exist for: turn a `RenderPlan` into one
polished movie per event. The strategy is the HLD's **normalize-on-GPU + guarded stream-copy concat** (§4.3),
grounded in the spikes: copy is safe only when a strict ffprobe equivalence check passes (exp 001), AMD
normalize is native `scale_vaapi,pad_vaapi` (exp 003), and overlay/tonemap fall back to CPU (exp 003/004).

A second goal shapes the architecture: the "look" features layered onto a movie (title cards now; intros,
outros, transitions, watermarks, lower-thirds later) must be **pluggable, not hardcoded**. So the pipeline is
built around a general **segment-decorator seam** rather than around "titles" — the title (#5) becomes the
first decorator, and future look features slot in without touching the pipeline core.

## What Changes

- **Segment model + decorator seam:** flatten a `RenderPlan` into a deterministic, fully-explicit **segment
  list** (each `ResolvedClip` × its `cut_spans` → one or more `Segment`s; chapter boundaries preserved), and
  expose a pluggable, ordered **decorator** transform with two general shapes — an **inserter** (adds a
  synthetic segment) and an **attacher** (adds an `OverlaySpec` to a segment). A `Segment` carries
  `overlays` as a first-class field. Ships a `none` default decorator; real title decorators arrive in #5.
- **Target spec derivation:** compute the common canvas (resolution from `look.target_resolution`, fps from
  the first clip, codec/pix_fmt/SAR, and common audio sample-rate/channels/codec) from the resolved `look`
  plus the first clip's probe facts plus the selected profile's **usable** encoders (AV1 a first-class
  target, D-5).
- **Per-segment normalize:** compose one ffmpeg command per non-conforming segment from `acceleration-profile`
  fragments — decode → rotation fix → SAR fix → `scale+pad` → tonemap → overlays → audio resample → encode —
  using `insert_transfers()` for hw↔system round-trips, with **guaranteed CPU fallbacks** (CPU transpose for
  rotation, `zscale,tonemap` + a loud HDR-slowness warning, a CPU overlay bridge when `can_overlay_hw=false`,
  and a synthesized silent track for video-only clips so concat stays A/V-aligned).
- **Guarded copy fast path:** a per-segment **copy-eligibility** check (plain source clip, untrimmed,
  undecorated, and ffprobe-equal to the target) skips re-encode; everything else normalizes. Normalize is the
  default, copy is the narrow optimization (exp 001).
- **Movie assembly:** a strict ffprobe **equivalence pre-flight** over the whole segment set
  (codec/profile/W/H/SAR/pix_fmt/time_base + audio) decides copy vs forced re-encode — **never** trusting the
  ffmpeg exit code (exp 001's silent-failure finding); **stream-copy concat** via the demuxer; **real
  `ffmetadata` `[CHAPTER]` markers** derived from measured segment durations and muxed in; and a **post-render
  output verification** that re-probes the result against the target spec.
- **Failure isolation:** fail loud on any clip/segment error (never fabricate, never silently drop a clip);
  one bad event does not abort the batch — it is reported and the rest proceed.

## Capabilities

### New Capabilities
- `render-segments`: build the deterministic segment list from a `RenderPlan` (clips × trims, chapter
  boundaries), derive the target spec from look + first clip + profile, and apply the pluggable
  inserter/attacher **decorator** seam (with `OverlaySpec` and a `none` default).
- `clip-normalize`: compose the per-segment normalize ffmpeg command from profile fragments with frame-location
  transfers and guaranteed CPU fallbacks (rotation, HDR tonemap, overlay, audio), and decide per-segment
  copy-eligibility.
- `movie-assembly`: equivalence-guarded stream-copy concat (never trusting exit code), `ffmetadata` chapter
  markers from measured durations, post-render output verification, and per-event failure isolation.

### Modified Capabilities
<!-- None. `ffmpeg-runtime` already provides structured command execution AND `-progress` parsing; `acceleration-profile`, `media-probe`, and `event-resolution` are consumed as-is. -->

## Impact

- **New code:** `auto_reel_ng/render/` (segments + decorators, target spec, normalize command builder, concat
  + chapters + verification, the render orchestrator). Golden-command-string tests (assert emitted ffmpeg args
  per profile without a GPU) plus integration tests behind a "has GPU" marker.
- **Consumes:** `event-resolution` (`RenderPlan`/`ResolvedClip`), `media-probe` (clip facts + equivalence
  fields), `acceleration-profile` (`AccelProfile.fragment`, `insert_transfers`, capability flags),
  `ffmpeg-runtime` (command execution + `-progress` callback).
- **Consumed by:** the title/overlay change (#5, registers real decorators), the analysis change (#6, supplies
  approved trims already carried as `cut_spans`), and the job scheduler (#7, drives the orchestrator and reads
  its progress events).
- **No new Python runtime dependencies** — all work is ffmpeg/ffprobe subprocesses via `ffmpeg-runtime`.

## Non-goals

- **Title/overlay content rendering (#5):** this change ships the decorator *seam* and a `none` default; it
  does not render text, cards, or images. No Pillow/Cairo text rendering here.
- **Analysis/detection (#6):** trims are consumed as already-approved `cut_spans` on the plan; detecting
  black/white/freeze is out of scope.
- **Job scheduling, GPU-aware concurrency, WebSocket progress, Postgres job state (#7):** the orchestrator
  renders one movie when called and exposes a progress callback; queueing and multi-GPU balancing are #7.
- **Change detection / render staleness (§4.13):** deciding *whether* an event needs rendering gates the
  scheduler (#7); this change renders when asked and supports an explicit overwrite/force.
- **GPU rotation/HDR optimization:** rotation and HDR tonemap ship on documented CPU fallbacks (a known-slow
  ~0.35× path for HDR on AMD); proving hardware rotation/tonemap per vendor is deferred.
