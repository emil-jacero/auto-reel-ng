## Context

`render/title/decorator.py` `title_decorator` runs after `build_segments`. It maps each chapter name to its
title clip's identity, walks the segment list, and inserts one synthetic segment (a `TitleCardRequest` built by
`compose_content`) immediately before the first segment whose identity matches, remembering inserted chapters so
a clip with several kept spans gets one card. `build_segments` yields one segment per kept span and none for a
clip whose cuts cover its whole duration (`kept_spans` returns `[]`; documented). So a wholly cut title clip
never matches and the chapter loses its card. See proposal.md "Why" for the repro and motivation.

Chapter boundaries (`render/chapters.py:aggregate_chapter_durations`) are derived from the segments' chapter
names in first-seen order, so a chapter with no segments is already absent from the movie and from the
container chapters. Nothing downstream needs to change.

## Goals / Non-Goals

**Goals:**
- A chapter that still has footage keeps exactly one card, opening that chapter.
- A chapter with no footage gets no card and stays absent (current behaviour, now pinned by a test).
- Partially cut title clips, no-title-clip chapters and decorator-off plans render exactly as before.

**Non-Goals:**
- Re-resolving the title clip after cuts (see Decisions); changing `build_segments`; any GUI text.

## Research & Decisions

### Where to re-anchor
**Context**: the title clip is chosen from the editorial model before probed durations are known, because
resolution is probe-free and cuts only become kept spans in `build_segments`, which needs probe facts.
**Explored**: (a) re-resolve the title clip in `resolution.py` skipping fully-cut clips; (b) make
`build_segments` emit a zero-length placeholder segment for a fully cut clip; (c) fix it in the decorator,
which already sees the final segment list.
**Decision**: (c). The decorator computes, per chapter, the title clip's identity and, in one pass over the
segments, the first non-synthetic segment of each chapter. If the title identity has a segment, the anchor is
the first such segment (today's behaviour). Otherwise the anchor is the chapter's first non-synthetic segment.
If the chapter has no non-synthetic segment, no card is inserted.
**Rationale**: (a) would need durations at resolution time, breaking its probe-free contract and the
fingerprint's reuse of the resolved plan; (b) pollutes the segment spine with a fake zero-length segment that
every later stage would have to special-case (Principle VII). (c) is a local change in the one place that owns
card placement and needs no new state.

### Which surviving segment is "next"
**Context**: a fully cut title clip may be the first clip of its chapter (the usual case: the baseline title is
the first included clip) or a later one (explicit `title: true` on, say, the third clip).
**Decision**: anchor before the chapter's **first surviving source segment**, not the first one after the title
clip's original position.
**Rationale**: a card is a chapter opener (HLD §4.4); a title placed mid-chapter only because the chosen clip
happened to be third is a property of that clip, which no longer exists. Opening the chapter is the
unsurprising result and keeps the chapter's segments contiguous with the card first.

### Order and idempotency
**Decision**: the result list is built in a single forward pass; the card for a chapter is inserted once, at its
anchor, tracked with the existing `inserted` set. The function stays pure over `(plan, segments)`, so a re-run,
a `--force` run and a worker restart mid-render all re-derive the same segments and the same card position:
nothing is stored and nothing is left partial. Failure behaviour is unchanged: a malformed `look.title_card`
still raises `TitleCardError` before any segment is touched; a missing anchor is not an error (a fully cut
chapter is legitimate editing), so nothing is swallowed or defaulted.

### `RENDER_GRAPH_VERSION`
**Decision**: bump 3 → 4 in `staleness/fingerprint.py` with a history line
`4: title-card-whole-clip-cut (a chapter whose title clip is wholly cut keeps its title card).`
**Rationale**: rendered output changes for identical inputs (events with a wholly cut title clip), so
Principle IV requires it. Events without such a cut render identical bytes but re-render once as stale, the
accepted over-bump trade-off (D-C8); `--force` is unaffected. The fingerprint components and inputs are
unchanged. No HLD D-n entry is needed: this restores the intent of D-E ("one card per chapter's title clip")
rather than adding a decision that outlives the change.

### Graph and CPU fallback
No ffmpeg argument changes: the synthetic card is encoded by the existing synthetic-segment path on every
profile and on the CPU fallback; only its position in the segment list differs.

## Risks / Trade-offs

- [A chapter whose title clip is `title: true` mid-chapter now has its card move to the chapter start when that
  clip is cut away] -> intended and specified; the alternative leaves the card in an arbitrary position.
- [Over-bump re-renders every existing archive once] -> accepted trade-off D-C8; `render-manifest.json`
  adoption and the staleness gate already handle it.
- [Two decorators both inserting before the same segment] -> out of scope; the title decorator is the only
  inserter today and its output order is unchanged for every plan that rendered correctly before.
