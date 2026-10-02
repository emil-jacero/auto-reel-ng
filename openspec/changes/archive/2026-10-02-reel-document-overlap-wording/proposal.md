## Why

Three documents state three different rules for two cuts on one clip that overlap. The `reel-document` spec says a
clip "MAY have multiple non-overlapping spans", which reads as a restriction but names no consequence. The
engine accepts overlapping cuts everywhere (`reel.yaml` parsing checks only `out > in` and non-negative times)
and the render joins them into one removal. The GUI (HLD D-14, `web-app`) refuses to add a cut that overlaps
another, yet shows overlapping cuts read from `reel.yaml` as their union, "joined as the render joins them".
An operator or a tool author cannot tell from the specs whether `trims: [{in: 1, out: 3}, {in: 2, out: 5}]` is
an error, and nothing in the test suite pins the union for that shape.

The supervisor has decided the rule (HLD §6 slice 3 `reel.yaml` schema and slice 4 render pipeline; GUI v1 is
D-14): the engine keeps its tolerant union, because hand-edited cuts, and analysis suggestions accepted next to
existing cuts, can overlap and failing a render over it is worse than merging. The GUI keeps refusing only NEW overlapping cuts, as an editing
aid. This change makes the specs and the tests say so.

## What Changes

- `reel-document`: the trims requirement says that cuts MAY overlap or touch, that the document accepts and
  keeps them as written, and that overlapping or touching cuts are one joined removal.
- `render-segments`: the segment-list requirement says that the footage kept from a clip is what lies outside
  the union of its cuts, whatever order the cuts are listed in and however they overlap, with scenarios for
  overlapping, touching and nested cuts.
- Tests pin the rule at three levels: the kept-span arithmetic, the segment list, and the `reel.yaml` parser.
- HLD D-14 gets one sentence that the refusal of a new overlapping cut is an editing aid and not an engine rule.
- The `kept_spans` docstring says "union" in the same words as the specs.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `reel-document`: "Trims are ordered cut ranges" states the overlap rule (accepted, kept as written, joined).
- `render-segments`: "Segment list from the render plan" states that kept footage is the complement of the
  union of the cuts, with scenarios for overlapping, touching and nested cuts.

## Non-goals

- No rejection of overlapping cuts in `reel.yaml` parsing or in `PUT .../reel`. That would make existing files
  unparseable and needs a migration story nobody has asked for.
- No change to the GUI: it keeps refusing a NEW cut that overlaps another and keeps showing read overlaps as
  their union. `web-app` is not modified.
- No normalization on save: overlapping cuts already in a `reel.yaml` are not rewritten to their union.
- No engine code change beyond a docstring.

## Impact

- Rendered output for identical inputs: **unchanged**. The behaviour being documented is what the engine
  already does. `RENDER_GRAPH_VERSION` is NOT bumped, and the staleness fingerprint inputs do not change.
- `reel.yaml` / `config.yaml` schema: unchanged. No Alembic migration, no rescan.
- Packages: `auto_reel_ng/render` (docstring, tests) and `auto_reel_ng/reel` (a parser test only).
- CLI and API: not touched.
- Specs: `openspec/specs/reel-document/spec.md`, `openspec/specs/render-segments/spec.md`; docs:
  `docs/high-level-design.md` D-14.
