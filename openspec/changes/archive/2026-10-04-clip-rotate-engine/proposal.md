## Why

Some home videos are sideways. The user wants a way to turn a clip until it is upright, and the turn must be
remembered in the event's `reel.yaml` (user request 2026-10-03: "Some videos are rotated 90 degrees. I want a
feature to rotate them so they are correct. We need to remember this in the config as well."). `reel.yaml` is the
source of truth (Principle II, HLD §4.6), and `clips.<identity>.rotate` already exists: it is parsed, resolved,
carried into the plan and applied by the normalize step, and the editorial write accepts it. What is missing is
a meaning that a person can use, and the engine does not give it one. The next change (`clip-rotate-gui`) adds the control and
turns the previews; this one makes the stored value mean "turn this clip N x 90 degrees clockwise from how it
plays now" (supervisor decision: what you see is what you fix).

Measured on `main` 143f0fc with the two rotated samples (`h264-720p-rotate90-aac.mp4`,
`hevc-mov-rotate90-aac.mov`, both display matrix -90, i.e. a phone held upright) and the portrait sample, by
normalizing each with `rotate` unset, 90, 180 and 270 and comparing the output's first frame with the
autorotated source turned by the same amount (SSIM, 24 renders, scratch `verify/v2/clip-rotate-engine/exp.py`):

- **Today the same `reel.yaml` renders two different ways.** On the CPU profile the engine's explicit `transpose`
  runs *after* ffmpeg has autorotated the clip, so `rotate` **adds** to the display rotation. On the AMD VAAPI
  profile the hardware decode delivers frames that ffmpeg does not autorotate (the proxy research found the same
  loss, `research/v2/synthesis.md` §6), so a display-rotated clip with `rotate` unset **renders sideways**
  (SSIM 0.98 against "stored orientation", 0.12 against upright) and `rotate: 90` happens to fix it. The
  documented rule "explicit `rotate` wins over the clip's own rotation metadata" (`_needs_pad`) is only true on
  the GPU, and only by accident.
- **A display-rotated clip that already matches the target is stream-copied with its display matrix.** A
  1280x720, 30 fps, AAC 48 kHz stereo clip with a 90 degree display matrix is copy-eligible (the check never
  looks at the clip's rotation), and the finished movie then carries `rotation=90` on its one video stream,
  although the movie is a concatenation of other clips too.

Both are the legacy failure mode HLD §2 row 6 exists to prevent (rotation handled by luck, silently), in the
engine this change sits in: HLD §6 phase 9 (GUI v2), after `timeline-view`. It depends on no open §8 research item.

## What Changes

- **`rotate` is an extra clockwise turn on top of the clip's display rotation.** The turn the engine applies is
  `(display rotation + rotate) mod 360`, clockwise, where the display rotation is the container's (the probe's
  `rotation` is ffprobe's counter-clockwise display-matrix angle, so the clockwise turn is `(360 - rotation) mod 360`).
- **The display rotation is applied by the engine, explicitly, on every profile.** The source is opened with
  `-noautorotate` when the clip has a display rotation, and the composed turn is one `transpose` stage in the
  filter chain (the CPU stage the explicit `rotate` already used, between `hwdownload` and `hwupload` on the
  hardware path). The output carries no display matrix. CPU and VAAPI therefore agree, and a phone clip no longer
  renders sideways on the GPU.
- **Padding is decided from the composed turn**, not from `rotate or clip.rotation`, so a clip that is turned
  back to its stored orientation (display 90 plus `rotate: 270`) is not padded as if it were portrait.
- **A clip with any display rotation or `rotate` is never stream-copied.** It is normalized, which is what the
  `clip-normalize` spec already says ("requires no rotation").
- **`rotate` is checked when `reel.yaml` is read**: an integer that is a multiple of 90 (0, 90, 180, 270, and
  also -90 or 360, which the engine already normalized) is accepted; any other integer fails the load naming the
  clip and the key, instead of failing the render later.
- **Rendered output changes for identical inputs**, so `RENDER_GRAPH_VERSION` goes from 4 to 5 (Principle IV, see
  design "Fingerprint and migration").
- **Spec:** `reel-document` gains the meaning and the accepted values; `clip-normalize` restates "Rotation and
  aspect normalization" and "Per-segment copy eligibility".
- **Docs:** HLD §4.2/§4.3/§4.6 and §4.10/§6 notes, and a new D entry for the meaning (task 4.1).
- **Tests:** golden argument tests per profile, the copy-eligibility rule, a real-render orientation test with
  the rotated samples at 90/180/270 on the CPU and (marker `gpu`) the VAAPI profile, a parse test, and the
  version pin.

## Non-goals

- No GUI. The control, the rotated previews and the Timeline are `clip-rotate-gui`. Proxies, thumbnails and
  filmstrips stay keyed by the file and are **not** rotated by the editorial value (`clip-proxies` and
  `clip-thumbnails` already say so); the GUI turns the picture it shows.
- No new `reel.yaml` key and no `config.yaml` key: `clips.<identity>.rotate` is the existing key. No Alembic
  migration and no rescan.
- No change to the editorial write (it already accepts `rotate`), to the API schema (`ClipPropertiesBody.rotate`
  and `ClipOut` are untouched, so no regenerated web types), to the CLI, or to the job kinds.
- No mirror/flip, no free angles, no auto-detection of a sideways clip.
- The legacy `rotate` container tag branch of `probe/media.py` `_extract_rotation` is left alone (see design
  Risks); no sample in the archive carries one.
- No `transpose_vaapi` and no GPU rotation (`research/v2/synthesis.md` §6: wrong geometry on HEVC, SSIM 0.47
  with no error).

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `reel-document`: a clip's `rotate` has a defined meaning (an extra clockwise turn on top of the display
  rotation) and a checked value (a multiple of 90).
- `clip-normalize`: "Rotation and aspect normalization" composes the display rotation with `rotate` on every
  profile; "Per-segment copy eligibility" excludes a clip with a display rotation.

## Impact

- **Packages:** `auto_reel_ng/render` (`normalize.py`) and `auto_reel_ng/reel` (`schema.py`). The version bump is
  the one-line constant (and its history comment) in `auto_reel_ng/staleness/fingerprint.py`, which Principle IV
  requires in the same change; no other `staleness/` code changes. Engine only: the CLI and the API gain the
  behaviour through the shared render path (Principle V).
- **Rendered output:** changes for identical inputs, so the `RENDER_GRAPH_VERSION` bump is required. The
  fingerprint's inputs and components do not change (editorial `rotate` was already in; the clip's display
  rotation is a property of the file, covered by its size and mtime); the bump changes the `engine` component,
  making every existing manifest stale once.
- **`reel.yaml` schema:** same key, now validated; a `rotate` that is not a multiple of 90 stops loading.
- **Schema/DB, API, web types:** none.
