## Why

A chapter's title card is anchored to its **title clip**. When the user cuts the *whole* of that clip (one cut
span that covers its full duration, which the GUI's cut editor allows), the clip contributes no segment, so the
card has nothing to sit before and is silently dropped: the chapter plays on from its next clip with no title
card at all. Reproduced on `main` 6a7fe16 with a plan `Ch1 = [a.mp4 (title, 10 s), b.mp4]`: with no cuts the
segments are `title, a.mp4, b.mp4`; with `Trim(0, 10.0)` on `a.mp4` they are `b.mp4` only. The cause is in two
places that agree with each other: `render/segments.py` yields no segment for a clip whose kept spans are empty
(documented behaviour of `kept_spans`), and `render/title/decorator.py` inserts the card only immediately
before a segment whose identity equals the chapter's title clip. The title clip is picked in
`event/resolution.py` before cuts are considered, so nothing re-anchors it.

This is the exact legacy failure mode HLD §2 row 4 and Principle I exist to prevent in spirit: output that
silently lacks something the editorial model asked for (a titled chapter), with no error and no signal. The
user's `reel.yaml` still says "this chapter has a title clip"; the render must honour the chapter, not only
the clip. It belongs to HLD §6 phase 8's v1 polish round, depends on no open §8 research item, and touches only
the already-shipped `title-card` capability (HLD §4.4, decisions D-C/D-E).

## What Changes

- **A chapter whose title clip is entirely cut still gets its title card.** The card moves to the chapter's
  first surviving source segment, so it still opens the chapter and the chapter timeline stays contiguous.
- **A chapter with no surviving segment at all gets no card** and, as today, does not appear in the movie or in
  its container chapters (no empty card chapter, no card floating before the next chapter).
- **A title clip with partial cuts is unchanged**: the card stays immediately before that clip's first kept
  span. A chapter with no title clip still gets no card; a plan without the `title` decorator is untouched.
- **Rendered output changes for identical inputs** (a fully-cut title clip used to render without a card and
  now renders with one), so `RENDER_GRAPH_VERSION` is bumped from 3 to 4 (Principle IV). Existing archives
  re-render once as stale; only events with a fully-cut title clip actually change bytes, the rest re-render to
  the same output (accepted trade-off, D-C8). The fingerprint's inputs and components do not change.
- **Spec:** the "Title decorator inserts a synthetic title segment" requirement states the anchor rule for a
  fully-cut title clip and for a fully-cut chapter, with scenarios for each.
- **Tests** in `tests/test_title_card.py`: title clip fully cut, whole chapter fully cut, partial cut
  unchanged; plus the version-bump pin.

## Non-goals

- No change to which clip is the title clip (`event/resolution.py` keeps picking it before cuts apply), to
  `build_segments`, or to the cut model: a clip with no kept span still contributes no segment.
- No GUI change here. The cut editor's whole-clip-cut warning wording is owned by the web notices change
  (`web-playback-and-notices`); this change only makes the engine behaviour that text describes true.
- No new config key, no `reel.yaml` or `config.yaml` schema change, no Alembic migration or rescan.
- No change to the title-card text content, duration, fades, or rendering.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `title-card`: "Title decorator inserts a synthetic title segment" gains the re-anchoring rule for a title
  clip or a whole chapter that cuts remove entirely.

## Impact

- **Packages:** `auto_reel_ng/render` (`title/decorator.py`) and `auto_reel_ng/staleness`
  (`fingerprint.py`, one constant plus its history comment). Engine only: the CLI and the API need no change
  and gain the behaviour through the shared render path (Principle V).
- **Rendered output:** changes for identical inputs only when a chapter's title clip is wholly cut; the
  `RENDER_GRAPH_VERSION` bump is therefore required. Staleness fingerprint inputs are unchanged (still
  probe-free); the bump changes the `engine` component, making every existing manifest stale once.
- **Schema/DB:** none.
