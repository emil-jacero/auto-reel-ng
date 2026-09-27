## Context

See proposal.md — Why. The code facts that shape the approach:

- **`render/target.py`:**
  - `derive_target(plan_look, first_clip, profile)` builds the `TargetSpec`.
  - `_resolution(look, first_clip)` reads `look.target_resolution` (validated as a pair) or falls back to
    `first_clip.width/height`.
  - `fps=first_clip.fps`, with no look key.
- **`render/orchestrator.py`:** `resolve_target(plan, profile, clip_facts)` calls
  `derive_target(plan.look, _first_clip_facts(plan, clip_facts), profile)`. `render_movie` and the worker's
  capacity classification both go through `resolve_target`, so every caller shares the derivation.
- **`clip_facts`** already holds probe facts for every clip in the plan, because the CLI and the worker
  probe all clips before building the job. `_first_clip_facts` only picks the first.
- **Copy eligibility** (`render/normalize.py:437-442`) compares width, height and fps (`abs(Δ) <= 1e-3`)
  plus the codec and audio parameters against the target. A default canvas equal to the uniform clips'
  own format keeps the fast path.
- **Normalize** emits `-r <target.fps>` as an output option, so ffmpeg repeats frames when a clip is below
  the target and drops them when it is above.
- **`RENDER_GRAPH_VERSION = 1`** (`staleness/fingerprint.py:33`). No test pins the literal.

## Goals / Non-Goals

**Goals:**

- The canvas is chosen by the look or by fixed, clip-order-independent defaults.
- An event whose clips already match the defaults renders exactly as fast as before, via stream copy.

**Non-Goals:**

- Look-key validation beyond the two keys this change reads (proposal: Non-goals).
- Interpolated frame-rate conversion.

## Research & Decisions

### Defaults, and where they are applied

**Decision**:

```python
DEFAULT_TARGET_RESOLUTION = (1920, 1080)

def derive_target(
    plan_look: Mapping[str, Any],
    clips: Sequence[ClipMetadata],
    profile: AccelProfile,
) -> TargetSpec: ...

def _resolution(look: Mapping[str, Any]) -> tuple[int, int]:
    """``look.target_resolution`` (a pair of positive ints) or 1920x1080."""

def _fps(look: Mapping[str, Any], clips: Sequence[ClipMetadata]) -> float:
    """``look.fps`` (a positive number) or the highest probed fps among ``clips``."""
```

- `resolve_target` passes `[clip_facts[c.identity] for chapter in plan.chapters for c in chapter.clips]`,
  failing loud (as `_first_clip_facts` does today) when any plan clip lacks facts.
- An empty plan cannot reach `derive_target`, because `render_movie` rejects a plan with no segments
  first, but `_fps` still raises a `RenderError` on an empty sequence rather than calling `max()` on it.
- `_first_clip_facts` is removed. It has no other use.

**Rationale**:
- These are the operator's decisions (2026-09-27): fixed 1080p, highest fps.
- Taking all clip facts instead of the first clip is the smallest signature change that makes "highest"
  computable. Resolution no longer needs clip facts at all, and fps is the only property that reads them.

**Alternative rejected**: computing the highest fps in `event/resolution.py` and putting it into
`plan.look`. The plan is probe-free by design ("the plan derives from the document alone"), and the fps is
a probe fact. `render/` is where probe facts already meet the look.

### Validation

**Decision**:
- `look.target_resolution` must be a two-element list or tuple of integers, each `> 0`.
- `look.fps` must be an `int` or `float` (not `bool`) `> 0`. A string is rejected rather than parsed:
  `"25"` fails loud, naming `look.fps`, so the look stays unambiguous.

Both raise a `RenderError`, which already reaches the operator per event, as the CLI's `ERROR` line or the
worker's job error.

**Rationale**: This is the existing `target_resolution` validation, extended to positivity and to the new
key. Refusing strings avoids a second, lenient parsing path (Principle VII).

### The version bump

**Decision**: `RENDER_GRAPH_VERSION = 2`, with its comment line naming this change.

**Rationale**: Principle IV requires a bump whenever rendered bytes change for identical inputs. They do
here for any event whose first clip was not 1920×1080 at the event's highest fps. Over-bumping costs one
re-render of NG-rendered events: only dev libraries today, since the real archive has no NG renders and
no real adoption yet. Under-bumping would leave portrait or low-fps movies marked fresh.

## Failure behavior and idempotency

- **Malformed look keys** raise a `RenderError` before any segment is built, so nothing is written, and
  the atomic finalize is untouched.
- **A plan clip without probe facts** raises, as before, but now for any clip rather than only the first.
- **Re-runs** are deterministic: the same look and the same clip set give the same target, whatever the
  clip order.
- **`--force`** re-renders with the new target.
- **Worker restart:** a requeued job derives the same target.
- **After deploy:** every NG-rendered event reports `stale: engine` once, then is fresh again after its
  re-render.

## Risks / Trade-offs

- **[50 fps output from a mostly-25 fps event]** One 50 fps clip makes the whole movie 50 fps, so the file
  grows by roughly the frame-rate ratio for the re-encoded 25 fps clips. → This is the operator's
  explicit choice. `look.fps: 25` per event or library restores 25.
- **[Variable-frame-rate phone clips]** The probed fps is an average, and a VFR clip's average (such as
  29.87) could become the canvas if it is the highest. → On the archive, phone clips are 30 fps, below
  the 50 fps camera clips they are mixed with. When a VFR clip does win, `look.fps` pins a round value.
- **[Upscaling 720p clips to 1080p]** It softens them. → Legacy did the same with its fixed 1080p, and
  the alternative (a 720p canvas) degrades every other clip.
- **[The first real re-render after the bump]** → There are no NG renders on the archive. Dev libraries
  re-render in seconds (stream copy).

## Migration Plan

Deploy, then render as usual. Dev libraries re-render once (engine stale). The README's `config.yaml`
example is corrected in the same change, so an operator copying it gets the keys the engine reads.
Rollback means reverting the two defaults and the version (outputs rendered at version 2 would then
report stale again).
