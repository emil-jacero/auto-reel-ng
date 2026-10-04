## Why

The operator asked to "drag to edit the length" of a title card. `title-card-blocks` makes every chapter's card a
visible block on the Edit-mode Timeline and selectable, but read-only. Nothing yet changes a card's length without
typing a number, and a black card's length changes the movie's length, which the Timeline is the one place that can
show while it happens.

## What Changes

- The **end edge** of a card block on the Edit-mode Timeline becomes a handle (a slider): dragged with a mouse, a pen
  or a finger, it sets that card's `duration` in the draft, in 0.1 s steps that snap to whole seconds within 8 px,
  between the engine's minimum (0.5 s) and maximum (60 s).
- A **video** card (text over the start of the chapter's first clip, adding no time) is bounded above by that clip's
  length after the draft's trims. A **black** card (its own span, adding time) moves everything after it while it is
  dragged, and the movie's length follows.
- A live readout in the Timeline's fixed-width clock style, "Card 4.0 s", while dragging and in the handle's value text.
- Keyboard with slider semantics: arrows 0.1 s, Shift+arrows 1 s, Home/End the limits; Escape cancels a drag.
- Release is one edit of the draft; Reset and Save treat it like any other edit. Pointer and touch, Chrome and Firefox.
- The pure rules (limits, steps, snapping, the shifted layout) join the timeline model and its `node:test` suite.
- No dependency, no API or engine change: the write path and the 0.5-60 s validation are `title-card-model`'s and
  `title-card-write-api`'s.

## Capabilities

### New Capabilities

### Modified Capabilities

- `timeline`: the pure model gains a title card's duration limits, step and snap rules, and the layout shift a
  black card's length makes.
- `event-timeline`: Edit mode's card blocks gain the duration handle: drag, keyboard, readout, bounds, locking,
  accessibility, touch and the performance gate.

## Impact

- `web/src/timeline/` (a card handle beside `TrimHandle.tsx`, `model.ts` rules, `dragStore.ts`, the clock readout),
  `web/src/edit/draft.ts` (the card duration edit and its dirty state), `docs/high-level-design.md` (D-20, §4.10, §6).
- Depends on `title-card-blocks` (the card blocks, the shared selection) and on what it builds on (`title-card-write-api`:
  the resolved cards; `title-card-over-video`: the video card). Not on `title-card-inspector`; the two may merge in
  either order, a typed duration in the inspector and this handle being two ways to the same draft value.
