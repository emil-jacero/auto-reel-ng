## Why

The target spec, the canvas every segment of a movie is normalized to (`render-segments`, decision D-E),
takes its **resolution** from the first clip unless `look.target_resolution` is set. Its **frame rate**
comes from the first clip with no override at all. The first clip is an accident of editorial order, not a
choice. The read-only survey of the real archive (2026-09-26) shows what that does to a real library:

- **Events mix clip formats.** They include 720p, 1080p, 4K (3840×2160) and **portrait** phone clips
  (720×1280, 1440×1920), at 25, 30 and 50 fps.
- **An event that opens with a portrait clip renders a portrait movie**, with every landscape clip
  shrunk into a vertical frame.
- **An event that opens with a 25 fps clip drops half of every 50 fps clip's frames.** One that opens
  with a 4K clip renders 4K, upscaling everything else, at several times the size and render time.

Legacy auto-reel defaulted to **1920×1080** (`config/processing.py:73`). Every legacy movie probed on the
archive is 1920×1080, at 25 fps for 25 fps events and 50 fps for 50 fps events. HLD §2 lists carrying
auto-reel's working mechanics forward, and a stable canvas is one of them. The operator decided the
defaults (2026-09-27):

- a fixed 1920×1080 canvas
- the event's highest clip frame rate
- both overridable per library (`config.yaml`) or per event (`reel.yaml`)

This belongs to HLD **§6 phase 4** (render pipeline). It is the last render-shaping fix before the first
real-library render.

The survey also found that the README's own `config.yaml` example sets `look.resolution: 1080p`. That key
does not exist: the engine reads `look.target_resolution`. Because `look` is opaque, the example is
silently ignored, and the operator following it gets first-clip behavior.

## What Changes

- **The default resolution is 1920×1080.** `look.target_resolution: [width, height]` still overrides it,
  via project `config.yaml` or event `reel.yaml` (D-2 layering). A portrait or 4K clip is fitted into the
  canvas by the existing aspect-preserving scale and pad, pillarboxed or downscaled. It never decides the
  canvas.
- **The default frame rate is the highest probed fps among the plan's clips.** A new `look.fps` (a
  positive number) overrides it. Clips below the target are shown at the higher rate by repeating frames,
  so no motion is lost. An event whose clips all match the target keeps the stream-copy fast path.
- **A malformed `look.fps` or `look.target_resolution` fails loud**, naming the key and value, as
  `target_resolution` already does.
- **`RENDER_GRAPH_VERSION` becomes 2.** Rendered bytes change for identical inputs whenever the first clip
  was not already the 1080p, highest-fps clip.
- **The README's `config.yaml` example is corrected** to `target_resolution: [1920, 1080]`, with `fps`
  shown as an optional override.

## Non-goals

- **No validation of other `look` keys.** `look` stays opaque (D-I). Catching unknown keys such as
  `resolution` belongs to a later look-schema change: the v2 look editor will need one anyway.
- **No new frame-rate conversion method.** The existing `-r` output option repeats or drops frames. Motion
  interpolation (`minterpolate`) is out of scope, and it is slow on AMD.
- **No per-chapter canvas.** One movie has one canvas.
- **No change to the target's codec, pixel format or audio parameters.**

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `render-segments`: `Requirement: Target spec derivation`. Resolution and frame rate come from the look or
  from these defaults, never from the first clip.

## Impact

- **Packages:**
  - `render/`: `target.py`'s `derive_target` takes all the plan's clip facts, not the first clip. Also
    `orchestrator.resolve_target`.
  - `staleness/`: `RENDER_GRAPH_VERSION` becomes 2.
  - `scheduler/worker.py` already goes through `resolve_target`, and gets no code change.
- **CLI vs API (Principle V):** neither gains a surface. Both render through `resolve_target`.
- **Rendered output:** **changes** for events whose first clip was not 1920×1080 at the event's highest fps.
  Hence **`RENDER_GRAPH_VERSION` → 2**. Every NG-rendered event reports stale (`engine`) and re-renders
  once. On the real archive no NG render and no real adoption exist yet, so nothing needs re-rendering
  there. Manifests adopted later carry version 2.
- **Staleness fingerprint inputs:** unchanged components. The engine component moves with the version,
  and `look.fps` is part of the resolved look already hashed into `defaults`/`editorial`.
- **Schemas:** `look` gains an optional `fps` key. There is no `reel.yaml` version change, because `look`
  is opaque. No Alembic migration, no rescan.
- **Dependencies:** none.
- **Size (Principle VIII):** one function's inputs and two defaults, one version bump, one capability
  delta.
