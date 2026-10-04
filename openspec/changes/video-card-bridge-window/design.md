## Context

`Segment` (render/segments.py) is a frozen dataclass: `identity`, `source_path`, `start`/`end` (kept span in source
seconds; `None` when `is_full_clip`), `overlays`, `copy_eligible`. The `title` attacher puts one timed
`OverlaySpec` (producer `title`, `start == 0`) on the chapter's anchor. `_build_segment_command` materializes it
(the producer returns the PNG, window `end` and fades), and `_clamp_timed_overlays` in `render/normalize.py` clamps
the window to the segment's length. `_build_video_graph` then switches to `-filter_complex` whenever the segment has
an overlay, and a timed overlay forces the CPU `overlay`; on VAAPI that wraps the whole segment in
`hwdownload,format=nv12 ... hwupload`. `_execute` and `_plan_only` iterate the plan's segments; concat then joins the
intermediates, chapter times come from the measured intermediate durations (`aggregate_chapter_durations`,
`chapter_times`), and progress weights come from `_segment_weight`.

## Research & Decisions

### Where the split happens
**Context**: the card's window is only known after the producer is asked (`materialize_overlay`), and the
segment's real length for a full clip only from probed facts (`options.clip_facts`). The plan-level decorator has
neither.
**Explored**: `render/decorators.py` (attacher sees plan, target, segment, but not the window), `render/orchestrator.py`
`_build_segment_command` (materializes per segment, index-keyed scratch names `seg_NNN.mp4`, `card_NNN_n.png`), and
a split inside one ffmpeg (a `split`/`trim` graph with a `concat` filter, head via CPU bridge, tail via GPU): rejected,
since `concat` on VAAPI hardware frames is not a verified recipe on Mesa (exp 003/006 cover overlay and pad, not
concat) and the hybrid graph would still need a second recipe per vendor.
**Decision**: a new step `split_card_windows(segments, target, clip_facts, scratch)` in `render/segments.py`'s
neighbour module (a pure function plus the producer call), run once at the top of both `_execute` and
`_plan_only`, before progress is planned. It replaces each qualifying segment with `(head, tail)` and leaves every
other segment untouched; later indices shift by one, so intermediates are named from the expanded list.
**Rationale**: both paths see the same expanded list (a dry-run lists the same commands a run executes), progress
weights and chapter aggregation work on real segments, and the normalize layer keeps taking one segment at a time
with no new concept in it. Materialized overlays are carried on the head, so `_build_segment_command` does not
materialize twice (the head's overlay already has `source`).

### The split rule (frame-exact)
**Context**: head and tail are separate ffmpeg encodes joined by the concat demuxer; a boundary off the target
frame grid would drop or duplicate a frame (the `fps` filter rounds each piece's ticks from its own start).
**Decision**: with `fps = target.fps`, `s0` the segment's start (0 for a full clip), `D` its length (kept span, or the
probed duration for a full clip), `W` the clamped window (`min(overlay.end, D)`):
```
N    = ceil(W * fps - 1e-6)        # whole target frames covering the window
H    = N / fps                     # head length; a multiple of the frame period
split iff D - H >= 1.0 s           # else: segment stays whole, exactly as today
head = Segment(..., start=s0,     end=s0 + H, is_full_clip=False, overlays=(overlay,))
tail = Segment(..., start=s0 + H, end=s0 + D, is_full_clip=False, overlays=())
```
Because `H` is a whole number of frame periods, tail tick `k` falls on source time `s0 + H + k/fps`, the same instant
the unsplit segment's tick `N + k` had, so the same source frame is picked for every output frame; the head is exactly
`N` frames and the tail `round((D - H) * fps)` frames. The head's own length exceeds `W` by under one frame period; the
overlay's window and fades stay the clamped `W` (the last partial frame shows the footage alone, as the unsplit
`enable=between(t,0,W)` did). `is_full_clip=False` on both makes each a trimmed segment, so neither is copy-eligible
(`Per-segment copy eligibility`: trimmed or overlaid), and the tail is never stream-copied at a non-keyframe cut.
**Rationale**: no keyframe dependence because both pieces are re-encoded; the 1.0 s floor stops a 7.5 s clip being
split for a 0.5 s saving. A clamped window (`W < asked`) keeps its warning, emitted once for the head.

### Audio continuity
**Context**: each piece encodes its own AAC stream; the existing joins between segments already rely on the concat
demuxer, but a join inside continuous footage is audible if it gaps or clicks.
**Decision**: both pieces cut audio with the same instants as the video (`-ss`/`-t` on the same input arguments, the
existing normalize chain), and the head's audio is limited to exactly `round(H * rate)` samples (`atrim=end_sample`
with `asetpts=N/SR/TB`) so head+tail sample counts equal the unsplit segment's. The join test (task 3) measures a
continuous 440 Hz tone rendered split and unsplit: total audio length within 1024 samples (one AAC frame) of the
unsplit render, and no sample step at the seam larger than the tone's own maximum step times 2. A clip with no audio
track keeps the synthesized silence on both pieces, each sized to its video length.
**Rationale**: the encoder's priming/padding is the only unavoidable error and is bounded by one AAC frame; if the test
shows more, the fix is in the trim (decide at implementation, fail the task, never loosen the bound).

### Emitted ffmpeg (VAAPI/AMD, 1080p30, 7 s card on a 180 s clip, W = 7)
Head (N = 210, H = 7.0): today's overlay chain on a 7 s span:
`-ss 0 -t 7 -i clip ... -loop 1 -framerate 30 -t 7 -i card.png -filter_complex "[0:v]<canvas>,hwdownload,format=nv12[vbase];
[1:v]format=rgba,fade=...[ov0];[vbase][ov0]overlay=x=0:y=0:format=auto:enable='between(t,0,7)'[vo0];
[vo0]format=nv12,hwupload[vout]" -map [vout] ...`.
Tail: the ordinary linear chain, no card input: `-ss 7 -t 173 -i clip -vf "scale_vaapi=...,pad_vaapi=..." ...`. On CPU
and software profiles both pieces are CPU chains with no transfers; the head differs only by its overlay. The CPU
fallback is unchanged (Principle III).

### RENDER_GRAPH_VERSION
**Decision**: bump 8 -> 9 with the history line `9: video-card-bridge-window (an anchor segment under a video card
is encoded as a card-window head and a tail, so its bytes change for the same inputs)`.
**Rationale**: Principle IV, "any change that alters rendered bytes for identical inputs MUST bump". The anchor now
has an extra encoder start (different GOP/AAC alignment); the over-bump cost on events without a video card is one
re-render each, accepted by D-C8. The fingerprint's inputs are unchanged (engine id only).

### Measurement
**Decision**: the implementation measures wall-clock encode time of the anchor segment, before (the pre-change
revision, `git stash`-free: run the same fixture on origin/main's worktree) and after, on a 180 s first clip with a
7 s video card, on the VAAPI profile (this host, AMD RX 9070 XT) and the CPU profile, three runs each, median, and
records the numbers (and the clip's codec/resolution/fps) in the HLD D-24 paragraph. The expected result is the
VAAPI anchor going from the bridge-bound rate to roughly the GPU-only rate (about 2x, the figure PR #115 recorded);
the CPU profile is expected to be within noise. The numbers, not this expectation, go into the HLD.

## Failure, idempotency
- A segment with no clip facts, an unregistered producer or an unreadable card font fails loud exactly as today
  (`RenderError` naming segment and cause), at the split step, before any encode starts.
- A failed head or tail encode fails the render with that segment's index and label; no `.part` is finalized
  (atomic finalize is unchanged). The software-decode retry applies per piece and is reported as today.
- Re-run, `--force` and worker restart mid-render: the split is a pure function of plan + target + facts +
  producer output, so each yields the same expanded list and the same commands; scratch intermediates are per-run.
