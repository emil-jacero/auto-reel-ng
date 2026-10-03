## Context

`render/normalize.py` builds one segment's ffmpeg command from pure inputs (segment, probed clip, target,
profile). Today rotation enters it in two places that do not know about each other: `_canvas_stages` adds a CPU
`transpose` stage when `segment.rotate` is set (`_transpose_filter`: 90 = `transpose=1`, 180 = twice,
270 = `transpose=2`, all clockwise), and `_needs_pad` decides padding from `rotate or clip.rotation`. The clip's own
display rotation is left to ffmpeg's automatic rotation, which the builder neither requests nor disables.
`copy_eligible` never reads `clip.rotation`. `reel/schema.py` stores `rotate` as any integer. The probe's
`rotation` is ffprobe's display-matrix angle (counter-clockwise, normalized to 0..359): a phone clip with matrix
-90 probes as 270. See proposal.md for the two defects this produces.

## Goals / Non-Goals

**Goals:**
- One meaning for `rotate`, the same on the CPU and every hardware profile, that a GUI can show.
- The display rotation applied exactly once, by a stage the golden tests can see.
- A rotated clip never rides the stream-copy path.

**Non-Goals:**
- Anything in `web/`, `api/`, proxies or thumbnails (proposal Non-goals).
- A hardware rotation filter.

## Research & Decisions

### What the engine does today (measured)
**Context**: the supervisor asked that `rotate` become "extra, on top of the display rotation", and for the
before/after of a file that has both.
**Explored**: for the three samples in `auto-reel-media/samples/` that matter (`h264-720p-rotate90-aac.mp4`,
`hevc-mov-rotate90-aac.mov`, `h264-portrait-1080x1920-aac.mp4`) the script `exp.py` built the real normalize
command with `build_normalize_command` for `rotate` in {unset, 90, 180, 270} on the CPU profile and on the host's
AMD VAAPI profile (hardware decode, hardware encode), ran it, took the output's frame at 1 s, and compared it by
SSIM with four references (the same source frame, autorotated by ffmpeg, then turned 0/90/180/270 clockwise,
fitted to the 640x360 canvas). The best-matching reference is the extra clockwise turn the render actually
applied relative to an upright picture:

| clip (display matrix) | `rotate` | CPU: extra turn applied | VAAPI: extra turn applied |
|---|---|---|---|
| 720p H.264 (-90) | unset | 0 | **270** (sideways) |
| | 90 | 90 | 0 |
| | 180 | 180 | 90 |
| | 270 | 270 | 180 |
| HEVC MOV (-90) | unset | 0 | **270** (sideways) |
| | 90 / 180 / 270 | 90 / 180 / 270 | 0 / 90 / 180 |
| portrait (none) | unset / 90 / 180 / 270 | 0 / 90 / 180 / 270 | 0 / 90 / 180 / 270 |

(Best SSIM 0.93 to 0.99 in every cell; the best wrong reference scores at most 0.77.) So the CPU profile already *adds*; the VAAPI profile loses the container's rotation, which is
why it *replaces* for a display-rotated clip and is correct for a clip without one. A second run, `exp2.py`,
sets the total turn `(clockwise display rotation + rotate) mod 360` explicitly, opens the source with
`-noautorotate`, and repeats all 24 renders: every cell gives the extra turn equal to `rotate` (0, 90, 180, 270), on both profiles and on all
three clips, and `ffprobe` on each output shows no display matrix. A third run, `exp3.py`, renders a 1280x720 30 fps AAC 48 kHz stereo clip with a 90 degree display matrix
as an event of one clip with the target 1280x720: it takes the stream-copy path and the finished movie reports
`rotation=90`.
The scripts (`exp.py`, `exp2.py`, `exp3.py`) and their outputs are under the session scratchpad,
`verify/v2/clip-rotate-engine/`; they are not in the repo.
**Decision**: compose in the builder, apply the total turn in the filter chain, and open the clip with
`-noautorotate` whenever it has a display rotation.
**Rationale**: it is the only form that gives both profiles the same answer, and it is what the proxy research
concluded for rotation ("rotation is a CPU path": `research/v2/synthesis.md` §6, `proxies.md` §6; D-21
"never a wrong proxy, silently"). It adds nothing to the fingerprint and no new key.

### Clockwise versus the probe's angle
**Context**: `rotate` is clockwise (`transpose=1` is 90 clockwise, the existing mapping), while the probe stores
the display-matrix angle, which is counter-clockwise: matrix -90 probes as 270 and needs a 90 clockwise turn
(`exp.py` confirms: probed 270 sorts out with `transpose=1`).
**Decision**: one pure function in `render/normalize.py`, `display_turn(clip) -> int`, returns
`(360 - (clip.rotation or 0)) % 360`; a second, `total_turn(clip, rotate) -> int`, returns
`(display_turn(clip) + (rotate or 0)) % 360`. Everything below calls these two; nothing else reads
`clip.rotation` for the render.
**Rationale**: the sign is the one thing that can be wrong in the compose, and a single function with a golden
test (probed 90 = 270 clockwise, probed 270 = 90) pins it. The probe stays as it is (the proxy facts publish it as
the probe reports it, D-21).

### Where the flag goes
**Decision**: `-noautorotate` is emitted as an input option, before `-ss` and `-i` of the source, only when
`display_turn(clip) != 0`. A clip without a display rotation keeps byte-identical arguments, so every existing
golden string stays valid.
**Rationale**: ffmpeg applies a display matrix to the filter graph's first stage by itself; with the flag off the
engine's own stage would apply it a second time on the CPU and not at all on VAAPI frames. The overlay inputs
(`-i overlay.png`) take no flag.

### The emitted chain, per profile
The rotation stage is the existing `_Stage(transpose chain, SYSTEM, SYSTEM)`, now fed the total turn. Examples for
the 1280x720 sample with matrix -90 (probed 270, clockwise 90) to a 640x360 canvas:

```
rotate unset -> total 90      CPU:   -noautorotate -i clip  -vf transpose=1,scale=w=640:h=360:force_original_aspect_ratio=decrease,pad=...,setsar=1
                              VAAPI: -hwaccel vaapi ... -noautorotate -i clip  -vf hwdownload,format=nv12,transpose=1,scale=...,pad=...,setsar=1,format=nv12,hwupload
rotate 90    -> total 180     VAAPI: ... -vf hwdownload,format=nv12,transpose=1,transpose=1,format=nv12,hwupload,scale_vaapi=...
rotate 270   -> total 0       no rotation stage (the flag is still given, there is a matrix)
                              CPU:   -vf scale=w=640:h=360:force_original_aspect_ratio=decrease,pad=...   (stored 16:9 needs no bars: no pad)
                              VAAPI: -vf scale_vaapi=w=640:h=360:force_original_aspect_ratio=decrease
```

(The first two rows are the commands `exp2.py` ran, with the flag inserted by hand; the portrait picture in a
landscape canvas needs bars, and the host's `pad_vaapi` fill is faulty, so the CPU scale-and-pad chain is taken,
acceleration-profile "Clips are padded where the fill is correct". The last row is what the fixed padding
decision gives; `exp2.py` still showed the CPU pad chain there, because the old decision fell back to
`clip.rotation`.) The CPU fallback of every row is the same chain without transfers; the VAAPI retry in
software (`force_software_decode`, D-18) takes the same stage. The total 0 case emits no stage and so no `hwdownload`: a display-rotated phone clip turned back to its
stored orientation stays on the GPU path.
**Cost**: a display-rotated clip now takes the CPU transpose between `hwdownload` and `hwupload` on the GPU
profile; before, the GPU path skipped it and was wrong. An explicit `rotate` already paid it. Home-video phone
clips are minutes, and the stage runs at the decode rate.
**Alternative rejected**: `transpose_vaapi`. The proxy research found wrong geometry on HEVC and a picture with
SSIM 0.47 and no error (D-21, "Never a wrong proxy, silently"); this builder would have the same silent
failure with no post-encode check.
**Alternative rejected**: leave the automatic rotation on and add only `rotate`. It adds on the CPU and loses the
display rotation on VAAPI; the two profiles keep disagreeing, and the GUI could not say what a turn does.

### Padding
`_needs_pad(clip, rotate, target)` becomes `_needs_pad(clip, turn, target)` with `turn = total_turn(...)`, a
quarter turn swapping width and height. The old `rotate or clip.rotation` also mis-judged a total of 0 reached by
cancelling (display 90, `rotate: 270` fell back to `clip.rotation` and padded a clip that needed no bars, which
the run above showed as the CPU pad chain on a 16:9 clip). Exact-ratio comparison and the SAR rule are unchanged.
SAR is not inverted by the turn (as with ffmpeg's own autorotate); a quarter-turned clip with a non-square pixel is
out of scope and unchanged.

### Copy eligibility
`copy_eligible` returns `False` when `display_turn(clip) != 0` or `(segment.rotate or 0) % 360 != 0`, not when
the total is non-zero: a clip with display 90 and `rotate: 270` totals 0 but a stream copy would still carry its
matrix into the movie. The existing `segment.rotate` truth test becomes `% 360`, so `rotate: 0` or `360` does not
cost the fast path. `decide_copy_eligibility` already passes the clip.

### Where `rotate` is validated
**Decision**: `reel/schema.py` gets `_rotate(value, loc)`: `_opt_int`, then `value % 90 != 0` raises
`ReelParseError(f"{loc}: rotate must be a multiple of 90, got {value}")`. The loc already names the clip.
The editorial write goes through `build_document`, so it is refused with the file untouched; the API maps a
`ReelParseError` as it does for any bad document.
**Rationale**: a typo written by a GUI should fail the save, not a render queued an hour later with
`RenderError: unsupported rotation`. Multiples of 90 beyond 0/90/180/270 (-90, 360, 450) are accepted because the
render already normalized them (`rotate % 360`), so no file that renders today stops loading, and the plan
carries the value as written (the fingerprint hashes what is written; `rotate: -90` and `270` are two spellings and
render the same, an accepted cost, the same as any equivalent edit).
`_transpose_filter` keeps its `RenderError` for a total that is not a quarter turn; it is unreachable from a
parsed document and stays as the fail-loud guard for a hand-built `Segment`.

### Fingerprint and migration
**Rendered output changes for identical inputs**, in three cases: a display-rotated clip on a hardware profile
(sideways before, upright now); a display-rotated clip with an explicit `rotate` on a hardware profile (replace
before, add now); a display-rotated clip whose stored shape equals the target (stream-copied with a matrix
before, normalized upright now). `RENDER_GRAPH_VERSION` therefore goes 5 to 6 (history line
`6: clip-rotate-engine (...)`). The fingerprint is probe-free (Principle IV), so it cannot tell which events hold
a rotated clip; every manifest turns stale once and unchanged events re-render to the same bytes (D-C8, the
accepted trade-off the earlier bumps took). No fingerprint input is added: the editorial `rotate` was already one
(`PINNED_EDITORIAL` does not move) and the display rotation belongs to the file (size and mtime).

**A `reel.yaml` that already sets `rotate` on a clip that has a display rotation.**
- On the CPU profile: before, display + `rotate` (stacked); after, the same. No change.
- On a hardware profile: before, `rotate` alone (the display rotation was lost); after, display + `rotate`. A file
  whose `rotate` was written *to fix* a clip that came out sideways (matrix -90, `rotate: 90`) now renders at 180,
  upside down; the fix is to delete the key (the display rotation does it) or to set the turn that is needed
  on top of what a player shows. A `rotate` on a clip without a display rotation renders as before everywhere.
- How likely: the GUI never wrote `rotate`, the legacy import does not produce one (`reel/legacy.py` has no
  rotate), and no `reel.yaml` under `auto-reel-media/` or the dev libraries has the key; the supervisor's
  expectation was "likely rare" and nothing found contradicts it. The info log (spec scenario "Both rotations are
  logged") names the three numbers on the first render after the upgrade, which is the only signal the engine
  can give without a decode.
There is no data migration and no rescan: the key and the file are unchanged.

## Risks / Trade-offs

- [The sign of the display rotation is easy to get backwards] -> `display_turn` is the only reader; golden tests
  on probed 90 and 270, and a real-render test that measures orientation on both rotated samples at all three
  turns, on both profiles.
- [A legacy `rotate` container tag would be read by `_extract_rotation` as a clockwise number where the matrix
  gives a counter-clockwise one] -> not touched here: ffmpeg >= 7.1 (asserted at startup) is expected to hand the
  tag to the display matrix and not to list it, and the two rotated samples carry only the matrix; this was not
  verified on a file that really carries the tag. If one turns up, `display_turn` is the single place to fix.
- [A hardware profile now downloads frames for a display-rotated clip] -> same cost an explicit `rotate` always
  had; the alternative is a silent wrong picture.
- [Every existing render goes stale once] -> accepted (D-C8); `auto-reel scan` states the engine reason.
- [A title card over video] -> the card is its own segment (D-C/D-E) and the overlay path places overlays in canvas
  space after the rotation stage; neither reads `rotate`. Covered by a test that a trimmed, overlaid segment keeps
  its overlay inputs and gets the flag only on the clip's own input.
- [Proxies, thumbnails and filmstrips are keyed by the file] -> unchanged, and a rotate edit must not touch
  them (`clip-proxies`, `clip-thumbnails`); the GUI turns what it shows.

## Open Questions

- None that change the specs or the tasks. (Which D number the HLD entry takes is decided at apply time: D-23 is
  the next free number on `main` today and parallel v2 changes may take it first.)
