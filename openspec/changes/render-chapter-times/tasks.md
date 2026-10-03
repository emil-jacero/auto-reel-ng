## 1. Baseline

- [ ] 1.1 Confirm the code this change was designed against on the current `origin/main`:
  `render/chapters.py` has `aggregate_chapter_durations` and `build_ffmetadata` and no chapter-times helper;
  `staleness/manifest.py` writes `version: 1`, has `superseded` and no `chapters`; the orchestrator calls
  `write_manifest` after `os.replace` with `measured` still in scope; `cli/commands.py` `adopt-renders` calls
  `write_manifest` without a render; `change-detection` and `movie-assembly` have no requirement about chapter
  times. Stop and report if a check fails in a way the design does not cover.

## 2. staleness/ — the manifest record

- [ ] 2.1 Red first, then green. Tests in `tests/test_staleness_manifest.py`: a manifest written with two
  chapters (one with a title-card span) reads back equal; one written without `chapters` has
  `chapters is None` and stores `null`; a hand-written version 1 manifest with no field reads as valid with
  `chapters is None`; each of `"x"`, a list with a bool start, a negative start, `start > end`, a missing
  `name`, a title-card span outside its chapter, and a list whose second entry is bad reads as valid with
  `chapters is None` (not a partial list); a rewritten manifest does not carry the previous chapters over;
  `superseded` and the other fields are unchanged. In `tests/test_cli_adopt_renders.py`: adopting a movie
  writes `chapters` as `None`, also over an event whose previous manifest had chapters, and runs no ffprobe.
  Verify they fail on the unchanged code, then add `TitleCardSpan` and `ChapterTime`, `RenderManifest.chapters`,
  the `chapters` keyword on `write_manifest` and the tolerant parse in `read_manifest`
  (`auto_reel_ng/staleness/manifest.py`, as in the design), and export the two dataclasses from
  `auto_reel_ng/staleness/__init__.py`. Verify the new tests pass and `tests/test_staleness_gate.py`,
  `tests/test_cli_commands.py` and `tests/test_cli_adopt_renders.py` stay green.

## 3. render/ — compute and record

- [ ] 3.1 Red first, then green. Pure tests (no ffmpeg) in a new `tests/test_render_chapters.py`: the specs'
  arithmetic examples (a trimmed chapter of 1.0 s and 0.5 s then a 2.0 s chapter gives 0-1500 and 1500-3500;
  0.967 s measured gives an end of 967; a 3.0 s card then a 1.0 s clip as the second chapter gives 2000-6000
  with the card at 2000-5000; a card after a 1.0 s first clip starts 1000 ms into the chapter; no card gives
  `None`); for awkward durations (0.0004, 0.0005, 1.0005 s) every title-card span lies inside its chapter;
  `START`/`END` parsed from `build_ffmetadata(aggregate_chapter_durations(...))` equal the helper's numbers for
  the same input, and `build_ffmetadata`'s output for the existing inputs is byte-identical (the
  `build_ffmetadata` golden tests in `tests/test_render.py` stay unchanged and green); two title-card segments
  in one chapter raise `RenderError`; mismatched segment/duration lengths raise. Verify they fail on the
  unchanged code, then add `chapter_times` and the shared boundary helper to `auto_reel_ng/render/chapters.py`
  and make `build_ffmetadata` use the helper without changing its output.
- [ ] 3.2 Red first, then green. Real renders, `has_ffmpeg`, in `tests/test_render_manifest.py` (the existing
  `runtime` and `make_clip` fixtures, 320x240 clips of 1 s to 2 s): a two-chapter plan whose first chapter has
  a trimmed clip is rendered and the manifest's chapters equal the `[CHAPTER]` START/END that
  `ffprobe -show_chapters` reads from the finished movie, converted from the 1/1000 timebase; the last end is
  within one frame period of the movie's probed duration; a stream-copy render (uniform clips) and a
  re-encoded one (a mixed-size clip set) both hold; a skipped, dry-run and failed render leave the previous
  manifest and its chapters untouched; the fingerprint is the same before and after and `evaluate` still says
  fresh; two renders of the same inputs, one with a fingerprint and one without, give the same `[CHAPTER]`
  markers and stream durations. In `tests/test_title_card.py` (`has_fonts`): a plan with a title clip in its
  second chapter records a title-card span whose length equals the configured card duration within 1 ms and
  lies inside that chapter, and the first chapter records `None`. Verify they fail on the unchanged
  orchestrator, then compute `chapter_times(segments, measured)` beside `chapter_pairs` in
  `auto_reel_ng/render/orchestrator.py` and pass it to `write_manifest(..., chapters=...)`, touching nothing
  else (not `RENDER_GRAPH_VERSION`, the fingerprint or `adopt-renders`). Verify `tests/test_cli_render.py` and
  `tests/test_cli_render_staleness.py` stay green and `git diff -- auto_reel_ng/staleness/fingerprint.py` is
  empty.

## 4. Docs

- [ ] 4.1 Amend `docs/high-level-design.md` and verify with `grep -n "no chapter times"` that no sentence still
  says the manifest records none: in D-15, replace "the manifest records no chapter times and browsers expose
  none" with the new fact (the render manifest records chapter times and title-card spans, `chapters`, and
  the player does not show them yet); in the §4.10 v2 bullet, mark "chapter times in the render manifest" as
  built by `render-chapter-times` and keep "a chapter list for the movie player" as the open consumer; and in
  the D-C2 / §4.6 sidecar text add one sentence that the manifest also holds the last render's chapter times,
  additively at schema version 1, never a fingerprint input. Do not add a D-20 or D-21 entry and do not edit
  those (the timeline and the proxy contract are other changes').

## 5. Validation gates

- [ ] 5.1 Run `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`,
  `.venv/bin/python -m mypy auto_reel_ng` and `.venv/bin/python -m pylint auto_reel_ng` (clean, the known cairo
  `no-member` noise aside), then `.venv/bin/python -m pytest` green with podman available (or
  `-m "not requires_db"` with a stated reason); the title-card tests either run or skip only for the known
  Cairo/Pango + DejaVu reason.
