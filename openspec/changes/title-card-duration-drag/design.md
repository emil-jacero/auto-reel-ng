## Context

See proposal.md, "Why". Written against `origin/main` at `8554c29`, where `title-card-blocks` has **not** merged: this
design names its parts by role ("the card block", "the shared selection", "the chapter's card row"), and task 1.1
re-reads the merged code and maps each role to its real name before anything is built.

What exists and is reused:
- **Trim handles** (`timeline-trim`): `TrimHandle.tsx` / `ClipHandles` are sliders moved by the distance the pointer
  moves, with a drag store (`dragStore.ts`: one drag at a time, `claim`/`unclaim`, `useSyncExternalStore` so only the
  parts that show the drag re-render), a snap rule (`SNAP_PX = 8`), a press hand-over for overlapping areas, a
  `FINE_PX`/`COARSE_PX` reach, `locked` while a save or Move is pending, Escape to cancel, one live region, and a
  scripted drag gate (80 clips, 4x CPU throttle, <= 2 % of frames over 25 ms). The card handle is the same kind of
  thing on a different value, so it reuses these and adds no second drag machinery.
- **The engine's bounds**: `reel/card.py` has `CARD_MIN_DURATION = 0.5` and `CARD_MAX_DURATION = 60.0`; the loader and
  the write API refuse anything else (`card.duration` 400 naming the field). The detail reports each chapter's
  **resolved** card (`duration`, `background`, ...), which is what a block draws, and `PUT .../reel` takes
  `chapters[].card.duration`.
- **The draft** (`edit/draft.ts`) holds the operator's unsaved editorial state; `unsaved.ts` decides "unsaved changes";
  Reset puts the draft back and bumps `EditBinding.epoch`. There is no multi-step undo today; "Undo" for a card is
  Reset (or dragging it back), exactly as for a trim.
- **Layout**: `layout()` lays clips end to end; `title-card-blocks` puts a black card as its own span before its chapter
  and a video card over the start of the chapter's first clip.

## Roles mapped to the merged code (task 1.1)

Re-read against `origin/main` at `50d5ac7` (`title-card-blocks`, `title-card-write-api`, `title-card-over-video` merged):
- *card block* = `CardBlock` in `timeline/cards.ts`, drawn by `CardLane.tsx` (a button per block, in a lane above the clips);
  *the shared selection* = `useCardSelection` (`CardsBinding`, by the chapter's **saved name**); *the chapter's card
  row* = `edit/CardRow.tsx` fed by `edit/cardRows.ts` from the resolved `CardSpec`s.
- The Timeline derives blocks from `cardPlacements` (resolved specs + clips + `look.decorators`) -> `cardMap` ->
  `trackLayout`. A black card's span is its duration; a video card is held to `Placement.keptMs`.
- **Difference 1: the bound is the first kept span, not the first clip.** The engine attaches a video card to the
  first surviving *segment* ("Segment shorter than the card" clamps it), so a cut in the middle of the clip ends the
  footage. The bound is `Placement.keptMs`, which the blocks already use; `cardLimits` takes it as `keptMs` (null: no
  footage). A chapter with no footage has no block, so no handle; the pure rule still reports it.
- **Difference 2: the draft has no card concept yet.** `Draft` gains `cardDurations` (chapter key -> seconds,
  only values that differ from the resolved duration); `buildWriteBody` merges it into the chapter's read `card`
  (`ChapterBody.card`: absent keeps the card, a present one replaces it, so the read overrides are carried and only
  `duration` changes). The chapter row and the blocks read the resolved specs with the draft's durations laid over them
  (`withDurations`), keyed by the chapter's saved name, which is what the selection uses.
- **Difference 3: no separate `shiftedLayout`.** The Timeline already derives every span from the specs, so the live
  shift of a black card's drag is `cardPlacements -> cardMap -> trackLayout` with the dragged duration laid over the
  specs (`withDurations`), one code path for the drag and for the release. The scenarios of the shift are tests of that
  path. This removes a second layout rule that could disagree.
- **Difference 4: the card lane is a row of its own,** so the card handle and the trim handles never overlap.
- The drag store gets a second slot for the card drag (`getCard`/`setCard`) under the same claim, so one drag at a time
  holds across trims and cards.

## Goals / Non-Goals

**Goals**
- A card's length is changed by dragging its end edge, with the same quality as a trim: precise, snapped, keyboard
  and touch operable, announced, smooth, bounded so a drag cannot produce a value the engine refuses.
- The movie's length stays truthful while a black card is dragged.

**Non-Goals**
- Editing any other card field (`title-card-inspector`), the event-wide style (`title-card-event-style`).
- Dragging the card's start edge, moving a card, or a card that is not at its chapter's head.
- Fades: the engine clamps them to the duration at render; the handle does not show them.
- Any engine or API change, including exposing the bounds over the API.

## Decisions

**1. The end edge is a slider, built from the trim handle's parts.**
A card block's end edge carries `role="slider"` named "Title card length, <chapter>" (the opening card: the event's
opening), `aria-valuemin/max/now` in seconds and `aria-valuetext` "Card 4.0 s", focusable, in Tab order after the
playhead and before the clip handles of the same position. Pointer movement is applied as a delta from where the edge
was (no jump to the pointer), as for a trim. Pressing a handle selects its card (the shared selection).
*Alternative:* a numeric field only - already what the inspector will offer; the request was to *drag*.

**2. Values are tenths of a second; the unit is an integer.**
The model works in integer tenths (`tenths = round(seconds * 10)`) and converts at the edges, so 3.9999999 never
reaches the draft or the file; the draft receives `tenths / 10` exactly (a number with one decimal). A pointer
position maps to the nearest tenth; within 8 screen pixels of a whole second (at the current zoom) it takes that
second. At low zoom 8 px may span more than 1 s; then the nearest whole second to the pointer is taken only if it is
within 8 px, else the nearest tenth, so snapping never moves the edge further than 8 px. A snap the limits would move
the edge off is not shown (the trim rule). At high zoom a tenth is wider than a pixel, so the pointer always lands on
a tenth, never between.
*Alternative:* snapping to the other cards' ends or the playhead as trims do - rejected: a card has no neighbour
edges that mean anything, and a whole second is the operator's unit ("4 s").

**3. Limits always hold the current place; the bound is a pure function.**
`cardLimits({ background, saved, firstClipMs })`: min 0.5 s; max 60 s for a black card; for a video card
`min(60, floor-to-tenth(keptMs))` (see Difference 1). The range then widens to include the card's current value (a video
card whose clip was trimmed shorter after the card was set keeps its value, may be dragged only down, and the track
says "longer than its clip" in words); a bound below 0.5 s (the first clip is trimmed to under half a second) makes
the handle inert with the reason in its accessible description, never a value the engine would refuse. A video card in
a chapter with no clips in the draft is inert for the same reason. "After trims" is the clip's duration less its
`cutSpans` (what the render joins), from the **draft's** cuts, so a trim edited a moment ago is already the bound.
The bound is read when the drag begins and is not recomputed during it (a drag and a trim are never both live: one
drag at a time).
*Why the bound is the clip and not the movie:* the video card draws over the first clip while it plays and adds no
time; past the clip it would overlay a different clip, which the engine's `title-card-over-video` does not do.

**4. The engine's min and max are mirrored as two constants, kept honest by a test.**
The Timeline cannot ask the API for the bounds (not exposed, and this change is web-only). Two constants in the web
model mirror `reel/card.py`; a `node:test` test reads `auto_reel_ng/reel/card.py` as text and fails if either differs,
so a change of the engine's bounds fails the web suite instead of drifting. The server stays the authority: a value
it refuses is a 400 on Save, shown as any save error. The browser makes no other title-card rule.
*Alternatives:* publish the bounds in the OpenAPI schema (a second package, and the Pydantic body deliberately has no
value rules, `title-card-write-api` decision 1); omit the bounds and rely on the 400 (the operator could drag to 90 s
and learn on Save).

**5. A black card's drag translates the later layers and draws the real layout once, on release.**
Measured first with the live relayout of every later block, ruler and band on each move: 9 to 24 % of the frames over
25 ms in Chrome at 4x (the idle page 1 to 3.7 %), so the `--shift` fallback of the first design was built here, with one
change: a `translate` set on each element behind the card (not a custom property inherited by the whole track), and
`will-change: translate` on those so that a move is the compositor's and nothing is painted again (without it the
translate alone still measured 6 to 15 %). The Timeline keeps the committed layout during the drag (`placements`, `lay`, `blocks` and `handles` are
derived from the committed specs only), marks what starts at or after the card's end with `data-after` (clips, trim handles,
chapter bands, card blocks and handles, analysis marks, the playhead if it is behind the card), and a layout effect
subscribed to the drag store writes the translate (`(tenths - tenths at start) x 100 ms` in px) with no React render. The
parts that show a value follow the edge by themselves, each with its own store subscription: the dragged block and
handle, the dragged chapter's band (it grows), the ruler's ticks (their times are those of the new movie) and the
summary line (movie length and card time, from `withDurations` over the committed specs). On release, Escape or a lock,
the effect's cleanup lets go of the translates in the same commit that draws the new layout. The pure rules are
unchanged. The fitted zoom no longer needs holding during the drag; it refits on release as before.
A video card's drag changes only its own block: nothing shifts.
*Known limit:* the window of drawn clips is that of the committed layout, so a drag that shortens a card by more than
one view's width at high zoom can pull in content that was not drawn; it appears on release.

**6. Release is one edit; the draft stores an override.**
`setCardDuration(draft, chapter, seconds)` sets `card.duration` for that chapter (a card with only `duration` set is a
valid override; the engine's other layers still apply) and marks the draft changed; setting it to the resolved value it
already had is **not** an edit (a release where it began makes none), and Reset restores the saved card. Save sends
the draft's chapter cards in the existing `PUT .../reel` body. The chapter-row duration, the block and the
screen-reader name update on release, not per move (the trim rule: the rest of the editor does not change mid-drag).
A black card's change also changes "the movie will be N long", wherever the editor already shows it.

**7. The readout is the clock's, with one decimal.**
"Card 4.0 s" is written with the clock module's rule (a scale taken from the longest value, 60.0, so the text keeps
its character count; tabular figures) by adding a one-decimal case to `clock.ts`, shown beside the handle while it is
dragged and as the handle's value text. It is not `formatTime` (a cut's typed time).

**8. Keyboard.**
Left/Down -0.1 s, Right/Up +0.1 s, with Shift +/-1 s (to the nearest whole second in that direction, so a card at 4.3
goes to 5.0, not 5.3), Home the minimum, End the maximum; keys stop at the limits; a key is one edit, its result is
the value text (not also announced); Escape during a drag cancels it. Keys are handled only on the focused handle,
never inside a field, never scroll the page.

**9. Touch.**
The handle's area is 24 px (fine) / 44 px (coarse) wide, `touch-action: none` on the handle only so a swipe on the
rest of the track still scrolls. The handle lies in the card lane, a row of its own above the clips, so its area
never covers a trim handle's and no press hand-over is needed (difference 4 in the findings above); a mouse press
without pointer events (Firefox under touch emulation) is handed to the handle as for trims.

## Risks / Trade-offs

- [The blocks' structure differs from the roles assumed here] -> task 1.1 maps roles to names and records the
  differences in the design before building; the pure rules do not depend on them.
- [Re-laying out on each move of a black card is slower than a trim] -> built as decision 5 (translate, relayout on
  release); the gate is measured in both browsers against the idle page of the same session, because a shared host's own
  noise (the idle page took up to 3.7 % of frames over 25 ms) is larger than the 2 % first written.
- [Mirrored constants drift] -> the text-reading test (decision 4).
- [Dragging past a video card's clip is blocked silently] -> the bound is in the slider's range, the readout stops, and
  the handle's description says "up to the first clip's length".
- [A black card at the head shifts a playhead the operator was watching] -> it keeps its content, not its time; the
  scrub video does not change.
