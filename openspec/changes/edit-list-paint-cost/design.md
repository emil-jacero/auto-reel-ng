## Context

Edit mode (`web/src/edit/EventEditor.tsx`, ~3,000 lines) mounts, top to bottom: the metadata form, the poster panel,
`TimelineSection` (D-20), the marks line, then `ChapterDrag` → one `ClipOrderList` per chapter → `ClipRow` per clip
(`<li className="clip-item">`), and the sticky save bar (`.save-bar`, `position: sticky; inset-block-end: 0`, its card
with `box-shadow: var(--shadow-lg)`). The rows are already memoised (`ClipRow`, `RowBody`, `MoveButtons`, `MarkBox`,
`ClipOrderList` are `memo`), and `ClipThumb.tsx` already sets `loading="lazy" decoding="async"`.

`timeline-zoom-slider` measured (archived `tasks.md` 3.1 status, quiet host, load 2–5, same 180-move drag, Chrome 154 at
4x): idle 0–0.6 %; thumb alone 1.4–2.1 %; zoom after its review 30–34 % of frames > 25 ms (p95 55–66 ms); the same with
`content-visibility: auto` injected on the rows (via `STYLE=` in `perf_slider.py`) 7.4–7.9 % (p95 30 ms). Firefox
unthrottled 0 %. Scrub gates held (Chrome 55.6 fps / step p90 25.3 ms; Firefox 47.6 fps / p90 33.5 ms). The remaining
~7.5 % after the injection is not yet attributed — this change profiles it before deciding further steps.

The Timeline talks to the editor through `editing: EditBinding` and `cardEditing` (memoised in `EventEditor.tsx`) and
calls back only on edits (`onTrim`, `onPoster`, `onAdd`, `onCardDuration`). Zoom, scrub and play should therefore not
re-render the editor; this is to be proven, not assumed.

## Goals / Non-Goals

**Goals:**
- A Zoom-slider drag on the 400-clip fixture keeps ≤ 2 % of frames over 25 ms in Chrome at 4x, and Firefox stays at
  its current figure, with the scrub and frame-step gates intact.
- Zoom, scrub and play cause 0 clip-row renders.
- No visible change: no scroll jump, no clipped focus ring or drop indicator, drag-and-drop, marks, keyboard reorder,
  rotate, the card dialog and the save bar behave as today.

**Non-Goals:**
- Virtualising the list, touching the Timeline's own rendering, any engine/API change (proposal "Non-goals").

## Decisions

### E1 — Measure first, then change only what the profile names

Before any code, re-run the #140 measurement on `origin/main` in this worktree's dev service (port 8460, DB
`arel_edit_list_paint_cost`, the dev library from `scripts/make_dev_library.py` plus the 400-clip one-chapter event
`2024/2024-07-06 - Fyrahundra` built the way #140's verification built it, `scratchpad/verify/v2/timeline-zoom-slider/`):
`perf_slider.py chrome 4 idle|slider` ×5 and `firefox 1 slider` ×3, copied into this change's SCRATCH, plus a CDP
`Tracing` capture (categories `devtools.timeline`, `disabled-by-default-devtools.timeline.frame`, `blink`, `cc`) of one
drag with and without the injected `content-visibility` style. The breakdown (script, style/layout, paint, layerize /
commit, raster, GPU) per frame, grouped by the DOM subtree that was invalidated, is recorded in the PR body. Every later
decision below that has no line in this breakdown is skipped.

### D1 — `content-visibility: auto` per clip row, with a remembered intrinsic size

```css
/* edit.css */
.clip-list > .clip-item {
  content-visibility: auto;
  contain-intrinsic-size: auto var(--clip-row-h);
}
.edit-page { --clip-row-h: 4.5rem; }                       /* measured, wide layout */
@container (width < 36rem) { .edit-page { --clip-row-h: 7rem; } } /* measured, narrow layout */
```

(Selectors and values illustrative — the implementation uses the list's real class names and the measured heights.)

- Per **row**, not per chapter section: one chapter can hold all 400 clips, and a section-level skip does nothing
  while any of that chapter is in view.
- `contain-intrinsic-size: auto <h>`: the `auto` keyword makes a row that has rendered once keep its last real size
  while skipped, so scrolling back never re-estimates; `<h>` is used only for rows never rendered. `<h>` is the measured
  median height of a collapsed row in each container-query layout (`edit.css` breaks at 36rem / 58rem / 30rem), held in
  one custom property per layout so it cannot drift from the CSS that sets the row's height. The property is static CSS,
  never written at runtime: `web-edit-save-bar-polish` measured that a root custom-property write restyles all 400 rows
  (its PR body: 128.8 ms of a first edit). Inline-size is not
  constrained (`contain-intrinsic-size` gives only the block size; the row keeps the list's width).
- Rows near the viewport render normally (the browser's ~50 % viewport margin), so a row's thumbnail, focus and hover
  are unchanged when seen. Skipped rows stay in the DOM and the accessibility tree, focusable and found by
  find-in-page (`content-visibility: auto`, unlike `hidden`, does not hide content from either).
- Scroll anchoring (`overflow-anchor: auto`, the default) keeps the visible row in place when a row above the view gets
  its real size. No rule in the edit page may set `overflow-anchor: none` on the page scroller; one is checked for.
- As built: `contain-intrinsic-size` sizes the **content box**, so `--clip-row-h` is a row's height less its 17 px of
  padding and border (a first try with whole-row heights grew the page 15 %): 3.1875rem (58-64rem panel), 4.5rem (from
  64rem, the 8rem frame), 3.75rem (under 58rem), 5.125rem (under 30rem). The rule sits in `@container (width >=
  20.25rem)`: under it a row's tools already overflow the row (on `main` too, the page itself below 340 px), and
  containment would cut the Move down button.

### D2 — Paint containment must not clip what a row draws outside itself

`content-visibility: auto` implies `contain: layout style paint` while skipped *and* paint containment while shown, so
anything a row paints outside its border box is clipped. Known cases to check, each in Playwright at 1280 and 390,
light and dark: the row's focus ring (`:focus-visible` outline with an offset), the drop slot indicator and the drag
overlay (`drag.css`, `box-shadow` spread), the mark checkbox's ring, the rotate badge, a toast or tip anchored in a row
(`overflow` of the cut panel), and the inset accent `box-shadow: inset 2px 0 0 var(--accent)` (inside, unaffected).
Fix per case: draw the ring inset (`outline-offset` ≤ 0) or move the outside decoration to an element that is not
inside the contained `li` (dnd-kit's `DragOverlay` already renders in a portal). No visual regression is accepted;
screenshots are compared with `main`'s.

As built: neither — the rule skips the rows that draw outside themselves, `:not(:focus-within, [data-drop-before],
[data-dragging])`, so a focused row, the drop target and the lifted row are drawn exactly as before (pixel-equal
screenshots), and the other rows have nothing outside their box. Toggling containment on one row costs nothing measurable.

### D3 — dnd-kit measures correct rects for rows that were skipped

dnd-kit (sortable, `ChapterDrag.tsx`) reads `getBoundingClientRect` of every droppable at drag start. A skipped row's
box is its intrinsic size, so the rects are right for rendered and `auto`-remembered rows, and approximately right for
never-rendered ones; as auto-scroll brings those into view their real size may differ. The drag MUST keep measuring
while dragging (`MeasuringStrategy.WhileDragging` or `Always` on the `DndContext`, whichever `ChapterDrag` does not
already use — check first) so a drop lands where its indicator was drawn. Verified by a Playwright drag from the first
row of the first chapter to the last chapter's last slot of the 400-clip fixture (auto-scroll across never-rendered
rows), and by the existing drag suites.

### D4 — Zoom, scrub and play render no clip row

Prove with a scratch-only render count: a patch kept in SCRATCH (never in the repo) wraps the chapter list in
`React.Profiler` and counts commits whose tree includes `ClipRow`, exposed as `window.__rowCommits`; a Playwright run
drags the slider, scrubs the playhead across 20 clips and plays 5 s, and asserts the count did not change. If it does,
the offending prop is found with the Profiler's "why did this render" (`changedProps`) and made stable in place
(`useMemo`/`useCallback` in `EventEditor.tsx`, or the state moved into `web/src/timeline/`). No production code path
exists only for the count (Principle VII).

### D5 — Other repaint sources, only if E1 shows them

Candidates, in the order the profile is expected to show them:
- **Sticky save bar**: a `position: sticky` card with a large shadow over a page whose content repaints may be repainted
  with it. Fix: `contain: paint` / its own layer (`will-change: transform` only if the trace shows a raster win, since a
  layer costs memory) — or nothing, if it is not in the trace.
- **Marks line and help toggles**: memoised already; checked in the render count of D4.
- **Thumbnails**: every `<img>` in a row gets `loading="lazy" decoding="async"` (only `ClipThumb` is known to have it).
- **Large layers**: the trace's layer list for the Edit page during a drag; a layer the size of the list is removed by
  removing whatever promotes it.

As built (E1's breakdown): none of the candidates above showed in the trace (the save bar is hidden during a zoom; the
app header's backdrop filter, the sticky chapter header and the thumbnails changed nothing when switched off). The cost
left after D1 was the **layerize of the rows in view** (each icon `<svg>` is its own paint chunk; about 60 ms per drawn
row per drag), so each chapter's played list is given **its own composited layer** (`.edit-chapter > ol.clip-order {
will-change: transform }`): layerize 1.5 s -> 0.5 s per traced drag, and the list's layer is not repainted while the
Timeline zooms. This is the one large layer the page adds, on purpose: it is tiled (only tiles near the view are
rastered), and the trade is a memory cost for the gate. Side effect: the list's content snaps to whole pixels, so glyph
and thumbnail antialiasing differ from `main`'s at sub-pixel level (nothing moves).

## Research & Decisions

### Why `content-visibility`, not virtualisation
**Context**: the paint/layerize of 400 rows dominates a zoom frame.
**Explored**: archived `timeline-zoom-slider/design.md` (Risks) and `tasks.md` 3.1 status: injected
`content-visibility: auto` takes Chrome 4x from 30–34 % to 7.4–7.9 %. Virtualising (e.g. a windowed list) was not
measured; it would add a dependency or a second list model, and would unmount rows dnd-kit, keyboard reorder
(focus stays on the moved row) and find-in-page rely on.
**Decision**: `content-visibility: auto` + `contain-intrinsic-size: auto <measured>` on rows.
**Rationale**: CSS only, no dependency (D-8), keeps every row in the DOM; the measured win is most of the gap.

### The gate's fallback
**Context**: the remaining ~7.5 % after the injection is unattributed; 2 % may be unreachable without touching the
Timeline.
**Decision**: aim for ≤ 2 %; if the best achieved is above it, report it with E1's breakdown and stop (the supervisor
decides whether the requirement takes the achieved figure measured against the page's idle floor). The ADDED
requirement then carries the agreed figure; nothing else in `event-timeline` changes.
**Rationale**: the brief; a gate written to a number never measured would be a fabricated claim.

## Failure behaviour

Pure presentation: no request, file, job or DB row is involved. A browser without `content-visibility` support (none of
the targets) renders every row as today. A wrong estimate only changes the scroll bar's thumb size until rows render;
scroll anchoring keeps the view still.

## Idempotency

No state: reloading, re-entering Edit mode and Save/Refresh show the same page; rows remember their size per page life.

## Risks / Trade-offs

- [Scroll jump when a never-rendered row above the view renders with a different height] → `auto` remembered size,
  measured estimates, scroll anchoring; Playwright measures it (web-app requirement).
- [Keyboard reorder's `scrollIntoView` to a far, never-rendered row] → the row is rendered on arrival (it is in view);
  rows between keep their estimates, the target lands in view; covered by the existing keyboard reorder suite plus a
  far move in the 400-clip fixture.
- [Paint containment clips a ring or indicator] → D2 per-case check against `main`'s screenshots.
- [dnd-kit stale rects during auto-scroll] → D3.
- [Shared host noise] → medians of ≥ 5 Chrome and ≥ 3 Firefox runs with the idle baseline in the same session, load
  average recorded per run.
- Playwright and Node run only in podman (Chrome 154 `localhost/playback-research:chrome`, Firefox ≥ 155
  `localhost/pcm-audio-research:pw163`), scripts in SCRATCH only, locators scoped to `main:not([hidden])`, write
  routes intercepted, every screenshot looked at.
