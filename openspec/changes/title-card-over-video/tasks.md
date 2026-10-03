## 1. render/ overlay mechanics

- [ ] 1.1 In `render/segments.py` add to `OverlaySpec` the fields `producer`, `producer_config`, `fade_in` and
  `fade_out` (defaults "unused", `source` defaulting to `""`, `to_dict` carrying the new keys); in
  `render/producers.py` add a function that materializes a producer-backed overlay through the registered
  producer (a transient synthetic `Segment` carries the payload) into an overlay with `source`, `start=0`,
  `end` and fades from the `ProducedSegment`; call it from `_build_segment_command` in `render/orchestrator.py`
  for source segments, so run and dry-run plans share it, writing `card_<index>_<n>.png` under the scratch
  dir. Verify with tests in `tests/test_render.py`: the overlay comes back with the PNG path, window and fades
  from a fake registered producer; an unregistered producer raises `RenderError` naming it and the registered
  ones; `_plan_only` with a producer-backed overlay writes the PNG and names it in the planned args; every
  existing `OverlaySpec(...)` call and `to_dict` assertion still passes.
- [ ] 1.2 In `render/normalize.py` build a timed overlay (any overlay with a fade): the extra input
  `-loop 1 -framerate <target fps> -t <window> -i <png>`, the overlay chain
  `format=rgba,fade=t=in:st=0:d=<in>:alpha=1,fade=t=out:st=<window-out>:d=<out>:alpha=1`, composited with the
  `CPUProfile` overlay fragment whatever the selected profile, and clamp the window to `duration` (scaling the
  fades together) with a warning on `NormalizeCommand.warnings` naming the segment, the asked and the shown
  seconds. An overlay with no fades keeps today's graph. Verify with golden-argument tests in
  `tests/test_render.py`: AMD profile (`hwdownload,format=nv12` ... `overlay=x=0:y=0:enable='between(t,0,7)'`
  ... `format=nv12,hwupload`, `-loop 1 ... -t 7`), CPU profile (same, no transfers), an NVENC-style profile with
  `can_overlay_hw=True` (still `overlay`, not `overlay_cuda`), a clip without audio (silence input index follows
  the card input), a 3 s trimmed span under a 7 s card (window 3, fades 1.5 + 1.5, one warning), a full clip
  shorter than the card (window from the probed duration), a 0 s fade side, and the existing
  `test_overlay_uses_cpu_bridge_filter_complex` and copy-eligibility tests unchanged.

## 2. render/title

- [ ] 2.1 In `render/title/render.py` skip the background `paint()` when the card's resolved background is
  `video` (the one renderer, same layout, outline, shadow, position, fail-loud font resolution). Verify with
  `has_fonts` tests in `tests/test_title_card.py`: corner pixels of a `video` card have alpha 0 and glyph pixels
  alpha 255 in the text colour; the `video` card's opaque pixels coincide with the `black` card's text pixels
  for the same title and style; a `black` card is pixel-identical to a render with the new code path absent
  (compared with a render of a config that predates the field); an unresolvable font family still raises
  `FontResolutionError` for `video`.
- [ ] 2.2 In `render/title/decorator.py` have `title_decorator` choose per chapter from its resolved card
  (read the merged `title-card-model` for the field and type names): `black` keeps the inserted segment and the
  `TitleCardRequest` exactly as now; `video` replaces the anchor segment (the existing `_anchor_indexes`) with a
  copy whose `overlays` gain a producer-backed `OverlaySpec(producer="title", producer_config=<same
  TitleCardRequest>, start=0, end=<card duration>, fade_in, fade_out)`. Update the module and function
  docstrings. Verify with decorator tests in `tests/test_title_card.py` (segment lists, no rendering needed):
  a `video` default chapter attaches one overlay and inserts nothing; a `black` plan's segments are unchanged
  from before; a mixed plan; a `video` title clip partially cut (overlay on its first kept span, one overlay
  although it has two kept spans) and wholly cut (overlay on the chapter's first surviving segment); a fully cut
  chapter and a chapter with no title clip (no overlay); a `video` card on a later explicit `title: true` clip;
  the decorator is still a pure function (same input, equal output).
- [ ] 2.3 Pin that an attached card leaves chapter times alone: in `tests/test_render_chapters.py` add
  `chapter_times` cases for segment lists carrying an overlay and no title segment (the chapter's
  `title_card` is `None`, starts and ends equal the same list without the overlay, another chapter's inserted
  card span unaffected) and, if `_title_card_spans` needs it, nothing else changes in `render/chapters.py`.
  Verify with `tests/test_render_chapters.py`.

## 3. Real renders

- [ ] 3.1 Add a `has_ffmpeg` + `has_fonts` test that renders, through `render_movie` on the CPU profile, a
  generated mid-grey clip (lavfi) with a `video` card (7 s, 2 s fades, white text) and the same event without the
  card: the two durations agree within one frame, `RenderResult.warnings` is empty, a frame sampled at the
  window's middle has luma well above the control's in the text band while one sampled after the window matches
  the control (tolerance for lossy encode), the recorded chapter times equal the control's; then repeat with a
  3 s clip and assert the clamp warning, the 3 s length and that text is present. Verify by running the test
  with ffmpeg and fonts present.
- [ ] 3.2 Add the same render as a `gpu` + `has_ffmpeg` + `has_fonts` test on the VAAPI profile (skipped
  without a render node, as the existing GPU tests): same assertions as 3.1, plus the output verifies against
  the target (`verify_output`). Verify by running it on this host's `renderD128`, and record in the PR the
  anchor segment's wall time with and without the card for a clip of a few minutes, so the cost named in the
  design is measured (not asserted).

## 4. Staleness, docs and gates

- [ ] 4.1 `RENDER_GRAPH_VERSION` stays 7 (the merged `title-card-model` fails loud on `background: video`, so no
  prior output exists; see design). Add a test in `tests/test_staleness_fingerprint.py` that changing a chapter's
  card background from `black` to `video` changes the editorial hash only (defaults, clip-set and engine hashes
  equal), so the event is stale for the editorial reason. State in the PR that no event turns stale.
- [ ] 4.2 Update `docs/high-level-design.md`: §4.4 (the card is a segment for `black` and an attached,
  alpha-faded overlay on the anchor segment for `video`; remove the "overlay stays a non-goal" sentence and the
  "✅ Resolved (§8.5)" caveat, keep D-A for the black card, note the CPU-bridge cost against experiment 003's
  advice), the title-card research item in §8.5/§8 list, the §4.10 v2 bullet and the §6 GUI v2 sequencing note
  (the engine half of "text on video" has landed; the editor and preview are `title-card-write-api` and the web
  changes), and the title-card decision the gate `title-card-model` records (extend it, or add the next free
  decision number if it recorded none). Verify by grep that no HLD sentence still calls the title-over-footage
  overlay a non-goal, and that the paragraph cites this change by name.
- [ ] 4.3 Run `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`,
  `.venv/bin/python -m mypy auto_reel_ng` and `.venv/bin/python -m pylint auto_reel_ng` (only the known cairo
  `no-member` noise remains), then `.venv/bin/python -m pytest` (podman available; otherwise
  `-m "not requires_db"` and say so), and verify all are clean and green, including the title-card, render,
  chapters and staleness tests.
