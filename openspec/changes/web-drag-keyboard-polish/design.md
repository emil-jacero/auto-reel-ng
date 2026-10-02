## Context

See proposal.md, "Why". Everything here is inside `web/src/edit/`; the engine, the API and `draft.ts`
are untouched. State on main `6a7fe16` (re-checked against the code, not only the triage):

- `ChapterDrag.tsx` `coordinateGetter` (the keyboard sensor's getter): `delta` is 1 for `KeyboardCode.Down`,
  -1 for `Up`, else 0, and `delta === 0` returns `undefined` **without** `preventDefault`. So Page Up,
  Page Down, Home and End scroll the page while a clip is lifted (the sensor itself calls
  `preventDefault` only when a getter returns coordinates; Space, Enter and Tab end the drag and Escape
  cancels it, in the sensor).
- `dragSlots.ts` has `slotsOf` and `stepSlot` (one slot at a time, crossing a chapter edge by one slot),
  `overIdOf`, `slotOf` and `pointerTarget`. Nothing jumps by chapter. `slotCount` is `n` for the clip's own
  chapter (positions) and `m + 1` for any other (gaps), so every reachable chapter has at least one slot;
  a deleted chapter is not in `model.listed` and is therefore passed over.
- `INSTRUCTIONS` / `ACROSS` are the keyboard drag's screen-reader instructions; `ACROSS` is appended only
  while `listed.length > 1`.
- `AUTO_SCROLL = { acceleration: 25, threshold: { x: 0.2, y: 0.2 } }`; `interval` is left at dnd-kit's
  default. Read in `@dnd-kit/core@6.3.1` (`getScrollDirectionAndSpeed`, `useAutoScroller`):
  `speed = acceleration × |zone depth ÷ zone size|` per tick, and a tick is a `setInterval(…, interval)`
  with `interval = 5`. **The ratio is not clamped**: it is exactly 1 with the pointer on the window's edge
  and grows beyond it (a mouse drag keeps reporting coordinates outside the window while the button is
  held). The triage item said the ratio "clamps above 1"; it does not. With the timer free the speed at
  the edge is `25 × (1000 ÷ 5)` = 5,000 px/s nominal, and more with the pointer past the edge: the same
  order as the triage's "about 6,700" (not re-measured; task 3.1 records the old constant's number). When
  the rows re-render on every new target the timer is starved to about one tick per frame, which is why
  the earlier change (per the comment above `AUTO_SCROLL`) saw the default (10) take about 40 s over a
  400-clip chapter and raised the constant to 25. The speed therefore swings with page load, by an
  estimated factor of three or more (25 px × 60 ticks/s = 1,500 px/s starved, 5,000 px/s free): the
  constant alone cannot bound it.
- **The keyboard sensor scrolls the page only for Up and Down.** In `KeyboardSensor.handleKeyDown`,
  the scroll branch compares `event.code` with `KeyboardCode.Down` / `Up` / `Left` / `Right`
  (`canScrollY = direction === Down && !isBottom || direction === Up && !isTop`). For any other code it
  skips the scroll and calls `handleMove` with the getter's coordinates (read in the source; task 2.1
  confirms it in the browser). A getter that returned the first
  slot of a chapter 20,000 px away for Page Down would therefore place the copy outside the window and
  leave the page where it was. The getter has to do the scrolling itself for the Page keys.
- There is no JS test runner in `web/` (`web/README.md`, "Checks": "a later slice with logic worth
  unit-testing may propose a runner, with its justification"). `dragSlots.ts` is written with no runtime
  imports so that "a scratch script runs it under Node", which is how `cross-chapter-drag` verified it.

## Goals / Non-Goals

**Goals:**

- Page Down / Page Up jump a lifted clip to the first position of the next / previous chapter, with the
  result in view, announced through the existing announcements and described in the instructions.
- The pointer's edge auto-scroll has a speed floor and ceiling that do not depend on page load.
- The one new pure function has a committed test.

**Non-Goals:**

- Home and End (first / last position of the whole event) and any change to the arrows' behaviour. They
  still scroll the page while a clip is lifted, as today. Consuming them is a one-line change that this
  change does not ask for.
- Capping the speed of a pointer held outside the window (the ratio grows). dnd-kit offers no cap; one
  would need an own scroller (VII). The bound is defined at the window's edge (spec).
- A runner such as Vitest, a DOM test of `ChapterDrag`, or committed browser automation (VII; the README's
  stance on browser automation stands). The two Playwright checks run from the scratchpad, never committed.
- Any change to the pointer drag's targets, `pointerTarget`, announcements' wording, or Move clips.

## Decisions

### `stepChapter` in `dragSlots.ts`

**Context**: Page keys need "the first slot of the next / previous chapter the clip may reach".
**Explored**: reusing `stepSlot` in a loop until the chapter changes (O(n) calls over a 400-slot chapter,
and the cursor lands at the near edge of the next chapter for Up, i.e. its last slot, not its first);
computing from `slotsOf` (builds every slot of every chapter, 400 objects, per key press).
**Decision**: one pure function next to `stepSlot`, same arguments and the same `null` convention:

```ts
/** The first slot of the listed chapter after (1) or before (-1) `from`'s; null at either end. */
export function stepChapter(
  model: DragModel, identity: string, staysHome: boolean, from: Slot, delta: -1 | 1,
): Slot | null
```

It takes `reachable(model, identity, staysHome)`, finds `from.chapter` in it (null if absent), walks
`delta` chapters on to the first one with `slotCount > 0` and returns `{ chapter, index: 0 }`. Because
`reachable` is the clip's own chapter alone for a missing clip, and a lone chapter when one is listed,
both give `null` with no special case. The own chapter's slot 0 is position 1; any other chapter's slot 0
is the gap before its first clip (or its empty area), the same slots `stepSlot` already produces.
**Rationale**: O(chapters), no allocation beyond the result, and exactly the vocabulary `ChapterDrag`
already speaks (`Slot`, `overIdOf`, `slot.current`).
**Alternative rejected**: "Page Up goes to the start of the current chapter first, then to the one before"
(Home-like). It makes the key stateful and asymmetric with Page Down for little gain: Up and Down already
reach every slot, and from the middle of chapter 3 one press to the first slot of chapter 2 is the jump the
operator asked for. A later change can add it if wanted.

### The getter: one shared path for the arrows and the Page keys

**Decision**: `coordinateGetter` maps `event.code` to a step: `Down` → `stepSlot(…, 1)`, `Up` →
`stepSlot(…, -1)`, `PageDown` → `stepChapter(…, 1)`, `PageUp` → `stepChapter(…, -1)`; any other code still
returns `undefined` untouched. (`KeyboardCode` has no Page members: compare with the strings
`'PageDown'` and `'PageUp'`.) The Page codes call `event.preventDefault()` **before** the lookup, so the
page does not scroll when the key moves nothing (last chapter, missing clip, one chapter, no `own`). The
rest of the getter (the `y` computation for own chapter, empty chapter and gap; `slot.current = next`) is
unchanged and shared. Collision detection, announcements, the line, the drop and Escape need no change:
they read `slot.current`, so `onDragOver` says "x is over “Kvällen”, position 1 of 4" and a drop is one
`clip-drop` edit exactly as after Down.

### Getting the target into view for the Page keys

**Context**: see Context, last sensor bullet. For Up and Down the sensor, when the new `y` lies outside
the window region it allows, scrolls the scroll container by the difference
(`scrollTo({ top: scrollTop + (newY - currentY), behavior })`) and returns without moving the copy: as
read in the source, the copy stays where it is in the window and the content moves under it, so that the
target arrives at the copy. That is why a one-slot step is visible.
**Decision**: for the Page codes the getter does that itself. When the computed `y` lies within the window
(`0 ≤ y ≤ innerHeight − height`), it returns `{ x, y }` as before. Otherwise it scrolls the document's scrolling element by `y − currentY`
(`behavior` from the same `reducedMotion ? 'auto' : 'smooth'` the sensor options use) and returns
`undefined`, which is the sensor's own scroll-only path. `slot.current` is set in both cases, so the
collision detection (which reads the ref) follows the scroll.
**Fallback if that is not exact** (the implementation must measure, task 2.1): `scrollBy` limited by
`maxScroll` leaves the copy short of the target; then scroll the target's line into view after the commit
(an effect keyed on `slot.current`, the way `firstLineIntoView` already does after a drop) and return the
coordinates. The acceptance is observable and is the same either way: after each Page key the target's
line (or area) and the copy are both inside the window (spec, scenario "Page Down and Page Up cross a long
chapter in one press").
**Rationale**: reuse of the sensor's own rule keeps one scrolling behaviour for both key families; the
fallback costs one effect.

### Instructions

`ACROSS` gains one sentence: ` Page Down and Page Up move it to the first position of the next or the
previous chapter.` It stays appended only while more than one chapter is listed, so a single-chapter event's
instructions do not mention keys that do nothing. The announcement text is unchanged.

### Auto-scroll: a frame-rate interval and a lower acceleration

**Context**: see Context. Speed at the edge = `acceleration × ticks per second`, and the tick rate is the
variable. Lowering `acceleration` alone (the triage sketch, 8-10) fixes the ceiling but, with the 5 ms
timer starved to one tick per frame under load, brings back the 40 s crossing the earlier change removed.
**Decision**: set `interval` to 16 (one tick per frame) and `acceleration` to 24:

```ts
const AUTO_SCROLL = { acceleration: 24, interval: 16, threshold: { x: 0.2, y: 0.2 } } as const
```

At the edge: `24 × 62.5` = 1,500 px/s with a tick on every frame, and fewer if a frame is dropped; the
unclamped ratio takes it past 2,000 only when the pointer is more than about a third of the zone (60 px of
a 900 px window) outside the window. The ramp from nothing at the zone's inner edge, the 20 % threshold and the
single constant object (a new object per render would restart dnd-kit's interval) stay. A 400-clip chapter
(a row is roughly 55 px: about 22,000 px, to be measured) crosses in about 15-25 s with the pointer in the
outer half of the zone.
**Rationale**: it makes the tick rate a constant of the page instead of the machine's timer, which is the
real source of the swing, using two options dnd-kit exposes.
**Alternatives rejected**: acceleration alone (above); an own scroller with a hard cap (VII, new surface
to maintain); `requestAnimationFrame` instead of `interval` (not an option of dnd-kit).
**Tuning**: the two numbers are starting values. Task 3.1 measures `scrollY` at the edge and at a tenth of
the window and may change them to meet the spec's bounds; the bounds, not the numbers, are the contract.

### A test for the pure part

**Context**: the README says there is no runner and a slice may propose one with justification.
**Decision**: no dependency. `web/src/edit/dragSlots.test.ts` uses Node's built-in `node:test` and
`node:assert/strict`, and runs in the `node:22` image already used for the toolchain, behind `npm test`
(one `scripts` entry in `package.json`, no change to `package-lock.json`). **The same bug round's
`web-toast-and-dialog-layers` adds this very runner** (task 1.1 there: the script
`node --test --experimental-strip-types src/**/*.test.ts` and the `exclude` below), with no gate between the two
changes. Whichever lands second adds nothing of it: task 1.1 here checks `web/package.json` and
`web/tsconfig.json` first, adds the script and the `exclude` only if they are absent, and then uses the
text that is on main, character for character, so the two never conflict. (`src/**` in that script reaches
`src/edit/` and `src/ui/` through the shell's one-level expansion; a test deeper than one directory would
need the quoted form.) It imports `./dragSlots.ts` (`allowImportingTsExtensions` is already on;
the file's only import is `import type`, which Node erases). `tsconfig.json` gains
`"exclude": ["src/**/*.test.ts"]` so the app's `tsc --noEmit` and `vite build` neither need `@types/node`
nor ship the test. The price is that the test file is not type-checked; it is a few `assert.deepEqual`
lines over `Slot` values, and a wrong shape fails the assertion.
**Alternatives rejected**: Vitest (a dependency tree for one file; VII); a pytest that shells out to
podman (slow, hides the failure behind a second toolchain); a scratch script as before (not a test).
`web/README.md`, "Checks", is brought up to date once, by whichever change lands first (task 4.1 checks
the text on main): `tsc --noEmit` is the type gate, `npm test` runs the pure functions under Node's own
runner, and browser automation is still not committed.

## Research & Decisions summary

| Question | Answer | Where it came from |
|---|---|---|
| Does the sensor scroll for Page keys? | No, only Up / Down / Left / Right | `@dnd-kit/core@6.3.1` `KeyboardSensor.handleKeyDown` |
| Is the auto-scroll ratio capped? | No | `getScrollDirectionAndSpeed` |
| What is the tick? | `setInterval(autoScroll, interval)`, `interval` default 5 | `useAutoScroller` |
| Why not just lower `acceleration`? | The earlier change raised it because the starved timer made the default too slow | `ChapterDrag.tsx` comment above `AUTO_SCROLL` |

## Failure behavior & idempotency

- Nothing is written, probed or rendered. A Page key changes `slot.current` and the copy's place, never the
  draft; the draft changes only on the existing drop, which is one `clip-drop` edit as before.
- A Page key that finds no chapter returns `undefined` after `preventDefault`: nothing moves, nothing is
  announced, and the page does not scroll. Pressing it again does the same (idempotent).
- Escape, a lock (a save in flight, a Move clips pending) and a missing clip behave as with the arrows:
  Escape cancels from any slot; a lock refuses the lift and the drop; a missing clip's `reachable` is its
  own chapter, so the Page keys find no other chapter.
- A restart of the page mid-drag cancels the drag (dnd-kit); there is no state to recover.
- The auto-scroll change has no failure path: the constants are read once per render of `DndContext`.

## Risks / Trade-offs

- [The scroll-only path for Page keys is the sensor's own rule, reimplemented] → The acceptance is observable
  (target and copy both in the window after the key, 20,000 px jump included) and the fallback is named.
- [`interval: 16` makes the page scroll in 16 ms steps, with up to 24 px per step, which can look stepped on
  a 120 Hz display] → The step is under 3 % of the window; the alternative (5 ms) is what produced the
  swing. Task 3.1 looks at it in the browser.
- [A pointer held outside the window scrolls faster than at the edge] → Left as is (Non-Goals); at 100 px
  beyond a 900 px window the speed is about 1.5 × the edge speed, inside the "can still steer" range.
- [The test file is not type-checked] → It is tiny, and the assertions would fail on a wrong shape.
- [A first JS test sets a precedent] → It adds no dependency and no config beyond one script and one
  `exclude`; a runner with DOM support stays a decision for a slice that needs one.
