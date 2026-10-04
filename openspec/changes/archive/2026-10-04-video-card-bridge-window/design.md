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
`_build_segment_command` (materializes per segment, index-keyed scratch names), a split inside one ffmpeg (a
`split`/`trim` graph with a `concat` filter, head via CPU bridge, tail via GPU): rejected, since `concat` on VAAPI
hardware frames is not a verified recipe on Mesa; and an **expanded segment list** (replace the anchor by head and
tail in `_execute`/`_plan_only`, so progress, chapters and concat see two segments): tried first and dropped, see
"Audio continuity" (two audio streams cannot be joined without a gap).
**Decision**: the split is internal to one segment's normalize step. A new `render/card_window.py` holds the pure
`split_segment(segment, fps, length) -> (head, tail) | (segment,)` and the join command builder; the orchestrator's
`_plan_encodes` materializes the segment's overlays, asks `split_segment`, and returns either one encode or a head
encode, a tail encode and a join command. `_normalize_segment` runs them; `_plan_only` lists them. The segment stays
**one entry** in the segment list: indices, `seg_NNN.mp4` naming, progress weights, copy eligibility, the measured
intermediate durations and the chapter aggregation are unchanged.
**Rationale**: no consumer of the segment list needs to learn about pieces, and a dry-run lists the very commands a
run executes because both go through `_plan_encodes`. Materialized overlays are carried on the head, so the card is
rendered once.

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

**Mixed rates**: when the source rate is below the target rate (25 fps into 30), the `fps` filter holds the source frame
that precedes a tick; a tail that starts cold at the boundary has no such predecessor and picks the next frame for its
first tick. The tail therefore starts `L = min(N, ceil(0.5 * fps)) / fps` early (`-ss s0 + H - L`), converts the rate with
`fps=<fps>:start_time=0` (the same tick grid as the unsplit render, shifted by a whole number of ticks) and drops its
first `L * fps` ticks by count with `trim=start_frame`, `setpts=PTS-STARTPTS`. The tail's output length is unchanged.

### Audio continuity
**Context**: each piece encoded with its own AAC stream and joined by a stream copy leaves the second stream's
encoder delay in the middle of continuous footage. Measured on a 20 s clip with a continuous 440 Hz tone split at
7 s: the joined movie decoded 2048 samples (two AAC frames) longer than the unsplit render, with about 1000 samples
of near-silence at the seam (peak 76 against 2900 for the tone). Cutting the head to exactly `round(H * rate)`
samples (the first plan) cannot fix this: the gap is the tail's priming, not the head's length.
**Decision**: the head and the tail are **video-only** (`-an`). A third command, the join, reads the pair through the
concat demuxer with `-c:v copy` and encodes the audio **once** from the source over the whole segment (`-ss start -t
duration` on the clip, the arguments the unsplit audio would have had), writing `seg_NNN.mp4`. A clip with no audio
track gets the same `anullsrc` silence as before, sized to the segment. The tone test (task 3.1) measures the movie's
audio length within 1024 samples of the unsplit render and no sample step at the seam above twice the tone's own
largest step.
**Rationale**: one AAC stream has no seam, so the bound is the unsplit render's own audio. The cost is one cheap
audio-only encode per split segment.

### Emitted ffmpeg (VAAPI/AMD, 1080p30, 7 s card on a 180 s clip, W = 7)
Head (N = 210, H = 7.0): today's overlay chain on a 7 s span, video only:
`-ss 0 -i clip ... -loop 1 -framerate 30 -t 7 -i card.png -filter_complex "[0:v]<canvas>,hwdownload,format=nv12[vbase];
[1:v]format=rgba,fade=...[ov0];[vbase][ov0]overlay=x=0:y=0:format=auto:enable='between(t,0,7)'[vo0];
[vo0]format=nv12,hwupload[vout]" -map [vout] -r 30 ... -t 7 -an seg_000_head.mp4`.
Tail: the ordinary linear chain, no card input: `-ss 7 -i clip -vf "scale_vaapi=...,pad_vaapi=..." -map 0:v:0 ... -t 173
-an seg_000_tail.mp4`. Join: `-f concat -safe 0 -i seg_000_join.txt -t 180 -i clip -map 0:v:0 -map 1:a:0 -c:v copy
-c:a aac -ar 48000 -ac 2 seg_000.mp4` (with `-ss` for a trimmed segment). On CPU and software profiles both pieces are
CPU chains with no transfers; the head differs only by its overlay. The CPU fallback is unchanged (Principle III).

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
  (`RenderError` naming segment and cause), before that segment's first encode starts.
- A failed head, tail or join fails the render with that segment's index and label; no `.part` is finalized
  (atomic finalize is unchanged). The software-decode retry applies per piece and is reported as today. A cancel
  is polled between the pieces and the join as between segments.
- Re-run, `--force` and worker restart mid-render: the split is a pure function of plan + target + facts +
  producer output, so each yields the same commands; scratch intermediates are per-run.
