## Context

See proposal.md, "Why". The work is in `web/src/edit/` on main at 6a7fe16. Two gates merge first and are
designed around below: `web-toast-and-dialog-layers` (toast placement, `edit.css`) and
`api-excluded-clips-read-model` (`ClipOrderList.tsx`: an "Excluded" pill, Cuts hidden for excluded clips).

How the save bar is wired today (`EventEditor.tsx`):

- `showBar = ready !== null && (dirty || ready.problem?.kind === 'gone')` (line 987), and `<SaveBar>` is
  rendered only `{showBar && …}` (line 1844). `barRef` is a `useRef` passed to `SaveBar`, so it is `null`
  while the bar is not rendered.
- A layout effect keyed on `[showBar]` (1005-1059) returns at once when `!showBar || bar === null`. Otherwise
  it runs `placeBar(bar)` (reads `getComputedStyle(root).fontSize` and `bar.offsetHeight`, toggles
  `data-rests`, writes `--toast-inset-bottom`), registers the bar with `keepToastsClearOf(bar)`, creates a
  `ResizeObserver`, and adds `resize`, `scroll` and `focusin` listeners. Its cleanup removes all of that and
  the property.
- A second layout effect with no dependency list runs `placeBar` on every commit while `showBar`.
- `keepInView(element, barRef.current)` (answers effect, 1090; a field's focus, 1630) treats a null bar as
  "measure against the scroll padding", the same as for any element outside a bar.
- `onReset` (1870): `cutPanels.clear()`, `dispatch({ type: 'reset' })`, `focusPageHeading({ preventScroll:
  true })`. The reducer's `reset` case clears `problem` and `refusal` and increments `resets`.
- `focusPageHeading` (`shell/AppShell.tsx:25`) focuses `main:not([hidden]) h1`; the h1 has `tabIndex={-1}`.

## Findings, re-checked

### 1. The first edit builds the save bar

Confirmed in the code (above). The first edit, in one commit, (a) updates the 400-row list (moved badges,
positions), (b) renders and mounts the `SaveBar` subtree with its two `useId`s and icons, (c) runs the effect
that observes, listens and registers the toast clearance (`ToastRegion` subscribes to it through
`useToastClearance`, so registering renders it), and (d) forces a synchronous layout in `placeBar` right after
the list changed. Every later commit repeats (d) but not (b) and (c).

The triage's 110-200 ms was a hypothesis about (b) and (c). **It was measured at implementation** (400 symlinked
clips in one chapter, Chromium 1280 x 900 in the Playwright image, five fresh Edit modes, a click then two
animation frames; `measure-base.txt`, `measure-after-2.1.txt` in the scratch directory):

| build                                   | first press | second press | difference |
| --------------------------------------- | ----------- | ------------ | ---------- |
| base                                    | 177 ms      | 48 ms        | 129 ms     |
| bar mounted early, hidden (task 2.1 a)  | 185 ms      | 52 ms        | 133 ms     |
| and no custom property write (2.1 b)    | 79 ms       | 47 ms        | 32 ms      |

Mounting early changes nothing measurable. A CPU profile of the first press puts 105 ms of self time in
`placeBar`, which the second press does not pay, and a direct test in the page shows why: on this page, one
write of any custom property on `<html>` (or on `<main>`, or on the chapter's `<ol>`) followed by a style
flush costs 90-100 ms, because custom properties inherit and Chrome restyles the whole subtree; setting the
`scroll-padding-bottom` property inline on `<html>` costs 0.2 ms; the same value written again costs nothing.
`placeBar` wrote `--toast-inset-bottom` on `<html>` on the first edit (and `removeProperty` on Reset), and
that is the first-only cost. Registering the property with `@property { inherits: false }` was tried and was
no better (a write still cost 145 ms), so it is not used.

So the fix has two parts, both in task 2.1: the early mount (the requirement above) and no custom property
written for the bar (see "The bar's height without a custom property").

### 2. Reset focuses a heading out of view

Confirmed. `{ preventScroll: true }` was chosen deliberately by `edit-mode-polish` so that a pointer Reset does
not jump the page; its non-goals recorded the off-screen heading as a follow-up. At the bottom of a long list,
Reset is below the fold of the heading, which is at the top of the page, so focus lands on an element nobody
can see. Moving focus is still right: the bar leaves with its buttons, and focus on `<body>` is worse.

### 3. The empty-chapter hint names a control that is absent

Confirmed. `MOVE_IN`, `NO_CLIPS` and `NO_CLIPS_PLAYED` are module constants (`ClipOrderList.tsx` 485-490), and
`words={empty ? NO_CLIPS : NO_CLIPS_PLAYED}` (756) uses them unconditionally. `ChapterToolsModel.moveClips` is
`null` exactly when the event lists one chapter (`EventEditor.tsx` 1421: `!several ? null : …`), where
`several = listed.length > 1` and `listed` excludes deleted chapters. The spec text that required the hint
("It SHALL also say that clips can be dragged into it…") says nothing about a lone chapter, so the constant
was a spec gap, not a regression.

## Goals / Non-Goals

**Goals**

- The first edit does not build the save bar; the bar is a stable element for the editor's lifetime.
- After Reset, focus is on a heading the operator can see.
- A lone empty chapter gives no instruction that cannot be followed.

**Non-Goals**

- Anything that changes `placeBar`'s rules, the toast region, `ClipOrderList`'s rows, or what is saved.
- Making the multi-chapter hint smarter when every other chapter is empty too.

## Research & Decisions

### Mount the bar early, hide it with the attribute

**Context**: Avoid the first-edit-only work in one commit with the list update (Finding 1).

**Explored**: (a) mount `SaveBar` as soon as the editor is `ready` and set `hidden` while `!showBar`;
(b) keep the conditional mount but wrap the showing state in `startTransition` or render it after the first
paint; (c) memoise the list harder.

**Decision**: (a). `SaveBar` takes `shown: boolean`; the editor passes `hidden={!shown}` through to the root
`div`. `reset.css` already declares `[hidden] { display: none !important }` in the first layer, which beats
every `.save-bar` rule, so no CSS changes. The attribute removes the bar from layout, the focus order and the
accessibility tree, which is what the new requirement states.

**Rationale**: (b) leaves the bar visibly late, and a held bar must be decided in the commit that shows it
(the comment on the layout effect: a move's scroll, a passive effect, must already clear it). (c) is the
`ClipOrderList` memoisation that already exists (`memo`, stable `tools`); the list is not what differs between
the first and second edit. (a) also keeps the `@starting-style` entrance: an element going from `display: none`
to rendered is styled for the first time, so `.save-bar-card` still fades and rises in under
`prefers-reduced-motion: no-preference` (checked in task 2).

### The bar's height without a custom property

**Context**: Finding 1's measured cost: a custom property written on `<html>` restyles every row.

**Explored**: (a) keep `--toast-inset-bottom` and accept ~130 ms (the first edit then fails the spec's bound);
(b) register it with `@property { inherits: false }` (measured, no better); (c) write the property on a
smaller element (every ancestor of the rows costs the same, and `<html>`'s scroll padding needs it on
`<html>`); (d) an inline `scroll-padding-bottom` on `<html>`, a real property, so only `<html>` is restyled.

**Decision**: (d). `shell.css` defines `--scroll-pad-bottom` on `html` as the old formula without the bar
(`var(--toast-region-h, 0px) + var(--toast-rise-h, 0px) + var(--s-4)`) and uses it as the default
`scroll-padding-bottom`. While the bar is held, `placeBar` writes
`scroll-padding-bottom: calc(<bar height>px + var(--scroll-pad-bottom))` inline on `<html>`; while it rests,
and in the effect's cleanup, it removes that inline value. The resulting padding is the same as before in
every state. The toast region's `inset-block-end` drops its `var(--toast-inset-bottom, 0px)` fallback: a bar
that is held is always registered with `keepToastsClearOf`, so the region has `--toast-offset` from the bar and
the fallback was never read with a bar present; with no bar nothing sets it, so it was `0px`.

**Rationale**: the formula stays in the stylesheet that owned it; the page writes only the number it alone
knows. `--toast-region-h`, `--toast-rise-h` and `--toast-room-h` stay custom properties, written by the toast
region when toasts appear (a different cost, paid when a toast is shown, not at the first edit; the toast
contract is otherwise untouched). Cost of the decision: the page's README and four comments say the property
names, and are updated with it.

### What stays conditional on `shown`

**Context**: The triage suggested keeping the toast registration stable too.

**Decision**: Only the element and `barRef` are stable. The layout effect keeps its `[showBar]` key, so the
placement, `ResizeObserver`, listeners, the inline scroll padding and `keepToastsClearOf(bar)` exist only while
the bar is shown, exactly as before.

**Rationale**: A hidden bar has `offsetHeight` 0 and no box. Registering it would have `ToastRegion` place
toasts against a box that is not on the page, and `web-toast-and-dialog-layers` makes the region measure the
registered bar (its resting-bar `margin-block-end`, its `ResizeObserver`). A registration that comes and goes
with the bar is the contract that change is written against. Registration costs one `setClearance` and one
`ToastRegion` render, which task 2.2 shows is or is not the residue.

The summary is computed only while shown: `summary={showBar ? summarize(…) : ''}`. `summarize`, `nameNow` and
`cutChanges` would otherwise run on every render of a clean Edit mode, for a bar nobody sees.

**Failure and edge behaviour**:

- A save answered with `gone` keeps the bar (`showBar` includes it) and its alert; unchanged.
- `problem` is non-null only while the bar is shown, except that undoing every edit by hand after a failed
  save hides a bar whose `problem` stays in state. That was already so: unmounting kept the reducer's
  `problem`, and the next edit showed the same alert. Reset clears it.
- Focus in the bar when it hides (Reset pressed): `display: none` drops focus to `<body>`, as unmounting did;
  Reset moves focus to the heading first (next decision).
- `data-rests` may remain on a hidden bar; the shown effect runs `place()` before paint, which sets it from
  scratch.
- A StrictMode double effect run registers and releases the same element, which `keepToastsClearOf` already
  handles.

### Reset: focus now, scroll after the page settles

**Context**: Focus must move in the click handler (the bar's button is about to go), but the page's height and
scroll position are not final until the reset commit has removed the bar and the edits.

**Explored**: (a) scroll in the handler; (b) focus the first form field in view instead of the heading;
(c) focus in the handler, scroll in a layout effect keyed on `ready.resets`.

**Decision**: (c). The handler keeps `focusPageHeading({ preventScroll: true })`. A `useLayoutEffect` keyed on
`ready?.resets`, skipping the initial value, runs after the reset commit and before paint. When the focused
element is still the page heading (`document.activeElement` equals the `h1`), it calls the existing
`keepInView(heading, null)`: it measures the heading against the page's scroll padding (the sticky header and
more) and calls `scrollIntoView({ block: 'nearest' })` only when part of it is outside. Nothing else triggers
it, so a Reset with the heading in view does not scroll, and a heading focused by the operator in between
(there is none before paint) is not stolen.

**Rationale**: (a) measures the page before the bar and the edits are gone: a 400-row reset shrinks the page,
and the browser clamps the scroll after layout. (b) changes the destination that `edit-mode-polish` and the
toast hand-offs (`pageHeading()` in `ToastRegion`) agree on. `block: 'nearest'` is the minimum scroll the spec
asks for and honours `scroll-padding-top`. No smooth behaviour is requested, and `html` sets no
`scroll-behavior`, so the scroll is instant, with or without reduced motion. `keepInView` measures against
`scroll-padding-top`, which also reserves room for a sticky panel heading the h1 does not sit under; at worst
this scrolls a few pixels more than strictly needed, and at the top of the page the browser cannot scroll
further, so the 'already in view' case stays still.

### The words come from a function of two booleans

**Context**: Finding 3.

**Explored**: (a) a new `multipleChapters` prop on `ClipOrderList`; (b) derive "alone" from the
`tools.moveClips === null` the list already receives; (c) a field `alone` on `ChapterToolsModel`.

**Decision**: (b), with the rule in a new dependency-free module `edit/emptyChapter.ts`:

```ts
export function emptyChapterWords(alone: boolean, wholly: boolean): string
// wholly: nothing listed at all (no removed, no ignored clip), the 'No clips.' form
// alone && wholly   -> 'No clips. A chapter without clips is left out of the movie.'
// alone && !wholly  -> 'It plays no clip. A chapter without clips is left out of the movie.'
// !alone            -> today's texts, unchanged
```

`ClipOrderList` calls it with `tools.moveClips === null` and `empty`. A lone chapter that lists removed or
ignored clips keeps its "It plays no clip." lead; those lists have their own restore control.

**Rationale**: `tools` is already a prop, is cached by `sameTools`, and `moveClips` is one of the fields it
compares, so going from one chapter to two re-renders the chapter once, with no new prop to thread through a
memoised 400-row component (Principle VII). `ChapterTools.tsx:36` documents `moveClips` as "absent when the
chapter is the only one". A pure function in its own file is testable without React. Today's wording for the
several-chapter case is kept character for character, so nothing else changes for the existing scenarios.

**Gate interplay**: `api-excluded-clips-read-model` edits other parts of `ClipOrderList.tsx`. The only lines
here are the three constants, the `words=` prop and one import. After that gate merges, re-read how `empty`,
`plays` and `removed` are defined: if an excluded missing clip becomes part of "wholly empty", the rule above
still holds, because it takes `empty` as given.

## Risks / Trade-offs

- [The mount is not the first-edit cost] → it was not (Finding 1); the bound is measured (task 2.2), and the
  cause, a custom property write, is removed instead.
- [A hidden-but-mounted bar changes the DOM for tests that look for `.save-bar`] → the browser checks use the
  region role and the `hidden` attribute; none of the repo's other code queries `.save-bar` (checked with
  `grep -rn "save-bar" web/src`, which finds only `edit.css` and `SaveBar.tsx`).
- [A scroll after Reset moves a page the operator did not ask to move] → only when the heading is out of
  view, which is where focus would otherwise sit unseen.
- [`web-toast-and-dialog-layers` changes `edit.css` and the bar-registration code] → this change adds no
  `edit.css` rule and keeps the registration inside the same `[showBar]` effect, so a textual conflict is
  limited to the comments.
- [`web-save-shortcut` and `web-edit-verdict-refresh` also edit `EventEditor.tsx`] → they do not touch the
  `showBar` render, the `onReset` handler or the area before the answers effect; whichever lands second
  rebases.
- [Fixture: an event with no clip lists no chapter] → checked in the browser: such an event shows only the
  page-wide "No clips." and no chapter, so the lone empty chapter is reached by Add chapter on it (which also
  covers the multi-chapter return); the lone chapter that holds only an ignored clip is the other form.

## Open Questions

None that change the specs or the tasks.
