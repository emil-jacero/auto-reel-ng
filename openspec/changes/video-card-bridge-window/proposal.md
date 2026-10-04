## Why

`title-card-over-video` (D-24) attaches a `background: video` card to the chapter's first segment as a timed
overlay, composited with the CPU `overlay` on every profile (D-C8 note in HLD 4.4: "only the title segment pays CPU
cost" was experiment 003's advice, and an over-video card gave it up). Today the whole anchor segment goes through
that CPU bridge: on VAAPI the chain is `hwdownload,format=nv12 ... overlay ... format=nv12,hwupload` for every frame
of the segment, although the card covers only its first `duration` seconds (default 7 s, `OverlaySpec.end`). For a
180 s first clip that is 173 s of frames downloaded, overlaid with nothing (`enable=between(t,0,7)` is false) and
uploaded again: about 2x slower than the GPU-only path, for no visible effect. PR #115 (`title-card-over-video`)
review recorded this as a follow-up.

This change restricts the CPU bridge to the card window. The anchor segment is split at the end of the card's
window into a head (carries the overlay, CPU bridge) and a tail (no overlay, normal GPU path). Both are re-encoded
anyway (an overlay-carrying segment is never stream-copied), so the split needs no keyframe at the boundary.

HLD: section 4.4 (the sentence that says the anchor is re-encoded through the bridge "for its whole length"),
section 6 (phase status unchanged), decision D-24 (title cards); no new D-number.

## What Changes

- The renderer splits a source segment that carries a timed overlay into two segments over the same clip, at the
  first target-frame boundary at or after the overlay's (clamped) window end. The head keeps the overlay and is
  composited as today; the tail has no overlay and uses the profile's ordinary linear chain (no `filter_complex`,
  no download or upload on VAAPI).
- The split is **frame-exact on the target frame grid**: the head is a whole number of target frames, the tail starts
  at the head's end, so the joined result has exactly the frames the unsplit segment had (none dropped or
  duplicated) and the movie's duration and chapter times are unchanged within one frame.
- The audio is cut at the same instant (sample-exact for the head's length) and joins without a gap or overlap of
  more than one AAC frame.
- A tail shorter than 1 s is not split off (the saving is smaller than a second and costs an extra ffmpeg start
  and audio seam): the segment stays whole, as today.
- `RENDER_GRAPH_VERSION` 8 -> 9 (see Impact).

## Non-goals

- Not a hardware overlay (`overlay_vaapi` stays unsupported on Mesa, exp 003) and not a change to how the card is
  rendered, faded or positioned.
- No change to `black` cards (inserted synthetic segments) or to segments without overlays.
- No change to `reel.yaml`, the project `config.yaml`, the API, the CLI surface, or the database (no Alembic
  migration, no rescan).
- No splitting of any other overlay kind (an untimed overlay still composites over the whole segment).
- Not a change to the staleness fingerprint's inputs (still probe-free: editorial + defaults + clip signals +
  engine id); only the hand-bumped constant inside the engine id changes.

## Impact

- **Rendered output changes for identical inputs** (Principle IV): an event with a video card now has an extra
  segment boundary (a new encode start, a different GOP/audio-frame alignment after the split). So
  `RENDER_GRAPH_VERSION` MUST bump, 8 -> 9, with a history line. The bump makes every event stale once (engine id
  is part of the fingerprint), including events without a video card whose bytes are unchanged; that is the accepted
  over-bump trade-off of D-C8 (one archive re-render, bypassable only by `adopt-renders`, which re-adopts under
  the new id). Not bumping would leave rendered movies whose bytes differ from what `render --force` produces
  while the gate calls them fresh, which Principle IV forbids. If another in-flight change has already taken 9,
  take the next free number at implementation time.
- Fingerprint inputs: unchanged. `reel.yaml` / `config.yaml` schema: unchanged. Alembic migration and rescan: none.
- Packages: `render/` (split, command building, progress weights), `staleness/` (the constant and its history
  line only). CLI and API: both unchanged; `auto-reel render`, the worker and a dry-run (`_plan_only`) all go
  through the same render path, so the plan lists the head and tail commands.
- Capabilities: `clip-normalize` (MODIFIED: the bridge covers the card window), `render-segments` (ADDED: the
  window split).
- Docs: HLD 4.4 and D-24 updated (task 5).
