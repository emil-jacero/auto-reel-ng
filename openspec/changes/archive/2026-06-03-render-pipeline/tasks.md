## 1. Package & data model

- [x] 1.1 Create `auto_reel_ng/render/` package (`segments.py`, `decorators.py`, `target.py`, `normalize.py`, `concat.py`, `chapters.py`, `verify.py`, `orchestrator.py`) and add a `RenderError` to the error hierarchy.
- [x] 1.2 Define typed, frozen models with `to_dict()`: `TargetSpec` (resolution, fps, video codec + encoder, pix_fmt, SAR, audio sample_rate/channels/codec), `OverlaySpec` (source, position, time range), and `Segment` (source identity + kept-span in/out + rotate, OR synthetic producer ref; `chapter`; `overlays`; `copy_eligible` flag).

## 2. Segment list (render-segments)

- [x] 2.1 Flatten a `RenderPlan` into an ordered `Segment` list: untrimmed clip → one segment; clip with `cut_spans` → one segment per kept span in source-time order; preserve chapter membership and plan order. (spec: Segment list from the render plan)
- [x] 2.2 Model source vs synthetic segments as peers; synthetic segments carry a producer ref and no source identity. (spec: Source vs synthetic segments)
- [x] 2.3 Make `overlays` a first-class `Segment` field; any non-empty overlay list marks the segment copy-ineligible. (spec: Overlays are a first-class segment field)
- [x] 2.4 Tests: untrimmed → 1 segment; one mid-clip cut → 2 segments; two chapters preserve order; deterministic across repeated runs. (spec: Deterministic segment construction)

## 3. Decorator seam (render-segments)

- [x] 3.1 Define the `Decorator` interface — pure `(plan, target, segments) -> segments` — plus the inserter/attacher helpers and a name-keyed registry. (spec: Pluggable segment decorators)
- [x] 3.2 Implement the `none` default decorator (returns segments unchanged) and resolve the decorator list by name from the `look`/config layering (D-2); unknown name fails loud.
- [x] 3.3 Tests: inserter adds a synthetic segment at the chosen position; attacher adds an `OverlaySpec`; `none` is a no-op; unknown decorator name raises. (spec scenarios for decorators)

## 4. Target spec (render-segments)

- [x] 4.1 Derive `TargetSpec` from resolved `look` + first clip probe facts + selected profile `usable_encoders`: resolution from `look.target_resolution`, fps from first clip, codec/pix_fmt from look, SAR 1:1, common audio params; AV1 honored when usable (D-5). (spec: Target spec derivation)
- [x] 4.2 Fail loud when the requested codec has no usable hardware **or** CPU encoder. (spec scenario: Unencodable codec fails loud)
- [x] 4.3 Tests: resolution/fps derivation; AV1 target when profile supports it; unencodable codec raises.

## 5. Per-segment normalize (clip-normalize)

- [x] 5.1 Build the per-segment normalize command by composing `AccelProfile` fragments (decode → normalize → tonemap → overlay → encode) and running them through `insert_transfers()` for hw↔system markers. (spec: Compose the normalize command from profile fragments)
- [x] 5.2 Apply rotation (hardware where available, else CPU transpose) and SAR→1:1 scale+pad with centered letterbox/pillarbox and the configured fill color. (spec: Rotation and aspect normalization)
- [x] 5.3 Tonemap HDR→SDR only when the clip is HDR: hardware when `can_tonemap_hw`, else CPU `zscale,tonemap` with a loud slowness warning; never tonemap SDR. (spec: HDR tonemapping with CPU fallback and slowness warning)
- [x] 5.4 Composite overlays during normalize: hardware overlay when `can_overlay_hw`, else a CPU bridge for that segment only; overlay-free segments stay on the hardware path. (spec: Overlay compositing with CPU bridge fallback)
- [x] 5.5 Normalize audio to target params; synthesize a silent track matching target params + segment duration for video-only clips. (spec: Audio normalization and synthesized silence)
- [x] 5.6 Realize kept spans via in/out seeking so trimmed footage never reaches output. (spec: Trims realized as kept spans)
- [x] 5.7 Raise a typed `RenderError` naming the segment on normalize failure — never drop or substitute. (spec: Fail loud on segment normalization failure)
- [x] 5.8 Golden-command tests (no GPU): AMD VAAPI chain composes `scale_vaapi,pad_vaapi` + VAAPI encode; CPU tonemap/overlay/transpose fallbacks appear with correct transfer markers; HDR path warns.

## 6. Copy eligibility (clip-normalize)

- [x] 6.1 Implement per-segment copy-eligibility: source segment, untrimmed (whole clip), no overlays, no rotation/tonemap need, and ffprobe-equal to `TargetSpec` (video + audio); else normalize. Synthetic segments are always encoded. (spec: Per-segment copy eligibility)
- [x] 6.2 Tests: conforming untouched clip → eligible; trimmed/overlaid/rotated/mismatched → ineligible; synthetic → always encoded.

## 7. Movie assembly (movie-assembly)

- [x] 7.1 Whole-set equivalence pre-flight via `ffprobe` over video (codec/profile/W/H/SAR/pix_fmt/time_base) + audio (codec/sample_rate/channels/layout); only an all-match set is stream-copied; the decision uses probe data, never the ffmpeg exit code. (spec: Equivalence pre-flight before stream-copy concat)
- [x] 7.2 Concatenate the uniform set with the concat demuxer + `-c copy`; when the pre-flight fails, re-encode to a uniform set before joining. (spec scenarios: uniform copy; mismatch forces re-encode)
- [x] 7.3 Generate an `ffmetadata` file with `[CHAPTER]` markers from **measured** intermediate durations and mux it into the output; names from the plan; timeline matches the concat timeline. (spec: Chapter markers from measured durations)
- [x] 7.4 Post-render verification: re-probe the output, assert it matches `TargetSpec` and is a single continuous stream; raise a typed verification error otherwise. (spec: Post-render output verification)
- [x] 7.5 Output naming `<title> - <location>.mp4` (location optional); skip if exists unless overwrite/force; dry-run builds + reports commands without executing or writing. (spec: Output naming and overwrite control)
- [x] 7.6 Tests: uniform set → copy; resolution/SAR mismatch → re-encode; chapters reach the container with measured boundaries; broken-stream output is caught; filename/overwrite/dry-run behaviors.

## 8. Orchestration & wire-up

- [x] 8.1 Implement the render orchestrator: resolve → build segments → apply decorators → derive target → per-segment normalize/copy → assemble → verify, running commands via `ffmpeg-runtime` and forwarding its `-progress` callback; intermediates in an ephemeral per-render temp dir, cleaned up after. (design: pure builder + thin runner)
- [x] 8.2 Per-event failure isolation: one event's failure is caught, reported with cause, and does not abort the batch; no incomplete output is presented as success. (spec: Per-event failure isolation)
- [x] 8.3 Expose the public render API (`render_movie(plan, profile, options)` + batch entry), models, and `RenderError` from the package; integration test behind a "has GPU" marker renders a real two-clip, two-chapter movie end-to-end and verifies chapters + playable output on the AMD host.
- [x] 8.4 Ensure `task lint:check` and `pytest` pass clean.
