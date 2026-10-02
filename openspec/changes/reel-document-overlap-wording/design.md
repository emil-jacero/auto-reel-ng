## Context

See `proposal.md` for why. The current behaviour, re-checked against `origin/main` (6a7fe16):

- `reel/schema.py` `_parse_trims` rejects only a cut with `out <= in` or a negative or non-numeric time. It does
  not compare cuts with each other, so `trims: [{in: 1, out: 3}, {in: 2, out: 5}]` parses and both cuts are kept
  in the document, in the order written (and are written back unchanged, per the round-trip rule).
- `render/segments.py` `kept_spans` clamps each cut to `[0, duration]`, sorts by start, drops empty cuts,
  merges any cut whose start is `<=` the previous merged end (so overlapping AND touching cuts join), and
  returns the complement. `build_segments` makes one segment per returned span. The input order of the cuts does
  not matter.
- `tests/test_render.py::test_kept_spans_complement` already pins ONE overlap, `(1,3)+(2,4)` on a 10 s clip,
  with the comment "Overlapping cuts merge". It does not pin touching, nested or unsorted cuts, a cut that
  reaches past the end, and nothing pins the rule at the segment-list or the parser level.
- The `reel-document` requirement says "A clip MAY have multiple non-overlapping spans." The triage cited
  `tests/test_render_segments.py`; that file does not exist, the render tests live in `tests/test_render.py`.

## Goals / Non-Goals

**Goals:**
- One stated rule, in the two specs that own it, that matches the engine.
- Tests that fail if someone makes the engine reject, drop, or double-render an overlapping cut.

**Non-Goals:** see the proposal. In particular no behaviour moves in the parser, the writer, the API or the GUI.

## Research & Decisions

### Overlapping cuts on one clip
**Context**: three rules coexist (spec: "non-overlapping", engine: union, GUI: refuse new, show read as union).
**Explored**: `reel/schema.py`, `render/segments.py`, `api/schemas.py` (`TrimBody` and `ClipPropertiesBody` add
no overlap check, so `PUT .../reel` accepts overlap too), HLD D-14, `web-app` Cut editing and Skip cuts
requirements (the latter already says cuts "are joined as the render joins them, overlapping or touching ones
as one").
**Decision**: keep the engine's union. Overlapping or touching cuts are accepted and are one removal. The GUI
keeps refusing only a NEW overlapping cut. (Supervisor decision, 2026-10-02; the strict alternative, rejecting
overlap in the parser and the PUT body, is declined.)
**Rationale**: `reel.yaml` is hand-editable, and nothing ties a cut accepted from analysis to the cuts already
in the file: the analysis pass resolves overlap between its own suggestions (black/white over freeze, D-AN3),
not against the file's existing cuts. Failing a render, or making an existing file unparseable, over a harmless
overlap is worse than merging. Union is also the only reading under which the GUI's Skip cuts playback and the
render agree.

### Where the rule is stated
**Decision**: the document-level statement ("accepted, kept as written, one joined removal") goes in
`reel-document`; the footage-level statement ("kept footage = outside the union, order-independent") goes in
`render-segments`. `web-app` is not modified because it already states the union for read cuts and the refusal
for new ones. A "joined as one removal" statement is in terms of footage kept, so it needs no function names.

### Touching cuts
`(1,3)` and `(3,5)` join. The cut ranges are half-open in effect (`in` inclusive, `out` exclusive), so touching
cuts leave no frame between them, so no zero-length kept span reaches the renderer. `kept_spans` already
guarantees this (the merge uses `start <= merged_end`, and the complement only emits a span when
`start > cursor`); the spec makes it explicit.

## Behaviour on failure and re-run

Nothing raises and nothing new is reported: overlap is not an error at any layer. Rendered output is identical
for identical inputs, so a re-run, a `--force` run and a worker restart mid-render behave exactly as before, and
no manifest or fingerprint changes. There is no CPU-fallback or ffmpeg-argument impact because the segment list
handed to the graph is unchanged.

## Risks / Trade-offs

- [A future change makes the parser strict and silently contradicts the spec] -> the parser test and the spec
  scenario both name the lenient rule, so the change would have to MODIFY the requirement and fail a test.
- [Overlapping cuts stay in `reel.yaml` as written, so a reader may think the cut total is larger than it is]
  -> accepted; the file is the operator's, and normalizing on save would rewrite hand-written content.
- [Documenting the union freezes it] -> acceptable; the render, the staleness reasons and the GUI preview
  already rely on it.

## Migration Plan

None. No schema, fingerprint, database or file change.
