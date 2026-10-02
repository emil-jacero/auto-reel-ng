## Why

Two small defects remain in the cross-chapter drag (`cross-chapter-drag`, archived 2026-10-01), both
found by the bug triage of main at `6a7fe16` and re-checked against the code for this change (design,
"Context"). Both are in `web/src/edit/ChapterDrag.tsx`, and neither loses data:

- **A keyboard drag has no way to jump to another chapter.** With a clip lifted, only Up and Down do
  anything (`coordinateGetter` returns nothing for every other key). Reaching the third chapter of a
  long event takes one press per clip in between, and Page Up / Page Down, which the sensor does not
  handle, scroll the page under the lifted clip instead of doing nothing or something useful.
- **Auto-scroll while a pointer holds a clip near the window's edge is too fast to steer.** The
  constant `acceleration: 25` is scaled by the pointer's depth in the 20 % edge zone on a 5 ms timer
  (dnd-kit's default `interval`), and the depth ratio is not capped, so the page crosses thousands of
  CSS pixels per second at the very edge. A short push toward a chapter overshoots it by
  several screens, and the operator cannot stop on the clip they wanted. The earlier change raised `acceleration`
  from 10 to 25 because the default crossed a 400-clip chapter too slowly (about 40 s) when the rows
  re-rendered, so the fix must keep a floor as well as add a ceiling.

## What Changes

- **Page Down / Page Up in a keyboard drag** take the lifted clip to the first position of the next /
  previous listed chapter. At the last / first chapter, for a missing clip (it never leaves its
  chapter), and while one chapter is listed, they move nothing. Both keys are always consumed while a
  clip is lifted, so the page no longer scrolls under it. The drag's instructions (read out at the
  lift, only while more than one chapter is listed) say so.
- **The pointer auto-scroll has a bounded speed.** At the window's very edge it is between 600 and
  2,000 CSS pixels per second, and it still ramps from nothing at the zone's inner edge. Two constants
  change (`acceleration`, and an explicit `interval` of one frame), so the speed no longer depends on
  how fast the browser's timer fires.
- No engine, API, schema or dependency change. A zero-dependency unit test of the new pure function
  runs under Node's built-in `node:test` (design, "A test for the pure part"). The same round's
  `web-toast-and-dialog-layers` adds the identical runner (script and tsconfig `exclude`); this change
  adds it only if it is not yet on main, and in either case brings the README's "no test runner"
  sentence up to date if it is still there.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `web-app`: "Edit mode drags clips between chapters" gains the Page Up / Page Down keys, the speed
  bounds of the edge auto-scroll, three scenarios for the keys and one for the speed, and one added
  sentence in the instructions requirement.

## Impact

- `web/src/edit/dragSlots.ts` (one new pure function), `web/src/edit/ChapterDrag.tsx` (the
  coordinate getter, the instructions text, one constant object), a new `web/src/edit/dragSlots.test.ts`,
  and, unless `web-toast-and-dialog-layers` has already landed them, `web/package.json` (a `test` script) and
  `web/tsconfig.json` (the test file is not part of the app's type-check); `web/README.md` (the keyboard
  sentence, and the Checks paragraph if it still denies a runner).
- Same-round neighbours, none a gate: `web-toast-and-dialog-layers` (the runner; `README.md`). No other
  planned change touches `ChapterDrag.tsx` or `dragSlots.ts`.
- One package (`web/`), one capability delta. No new dependency, no `RENDER_GRAPH_VERSION` bump (no
  rendered output changes), no Alembic migration, no OpenAPI change.
