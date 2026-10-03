## Context

State of `main` (143f0fc, with `timeline-view`, `timeline-trim` and `timeline-overlay-decisions` merged; read from the
code):

- `cuts/times.ts` `formatTime(seconds)`: `m:ss` or `h:mm:ss`, then the fraction to the millisecond **with trailing
  zeros stripped** (`0:01`, `0:01.5`, `1:02.35`). It is the format of the Cuts panel, of the typed fields (which parse
  it back) and of every spoken string. It is used across `cuts/`, `preview/`, `movie/` and `timeline/`; four uses are visible running times: `PlayheadReadout`
  (`timeline/Playhead.tsx`), `timeWords` (`preview/playback.ts`, shown by `ClipPreview`'s `.preview-time`), the trim
  tip (`TrimHandle.tsx`) and `movieWords` (`timeline/labels.ts`, the `.tl-summary` line).
- The Timeline readout is `<p class="tl-readout">` (`display: flex; flex-wrap: wrap; gap`) holding the clip name
  (`overflow-wrap: anywhere`) and two `.tl-readout-time` spans (`white-space: nowrap`, mono, `tabular-nums`). Its text
  is `{formatTime(at.ms)} / {formatTime(clip duration)}` and `{formatTime(global)} / {formatTime(total)} in all`.
  `at` comes from the playhead store and changes on every `timeupdate`/animation tick while playing.
- The player's header is `.preview-time { min-inline-size: 15ch }` over `timeWords(atMs, lengthMs)`, which writes
  `0:20.476 / 0:20.64` (18 characters) or `0:00 / —` before the length is read.
- `Layout` is `{startsMs, totalMs}` (whole `Ms`); `TrackClip.facts.durationMs` is each clip's length; the playhead
  store holds `{clip, ms}` and `clampPosition` keeps it inside the clips. `timeline-view`'s layer rule: pure files
  import types only, `npm test` runs them under `node --test --experimental-strip-types`.

Two facts found by reading the code shaped this design:

1. **`formatTime` cannot be made fixed-width without breaking its other job.** The Cuts panel and the typed fields
   treat it as the canonical, parseable form of a cut's time (`checkCut`, `formatTime(own.out)` comparisons in
   `cuts/times.ts`), and the spec's scenarios quote it (`0:01.2`, `0:02.607`). A running time is a different thing:
   it is read, never typed back. So the running time gets its own formatter and `formatTime` stays as it is.
2. **A fixed number of characters is not enough on its own.** Even with `0:09.50 → 0:10.00`-safe text, a proportional
   font, a wrapping flex row and a name that wraps all still move the line. The fix has a text part (the formatter)
   and a layout part (cells of reserved width, a name that is cut), and the spec states both as observable behavior.

## Research & Decisions

### Evidence
**Context**: the request is user feedback with screenshots, not a research item (§8 has none open for it).
**Explored**: the two screens' code above; `research/v2/timeline-library.md` line 65 (the prototype had a "movie-length
readout" and no width rule, so there is nothing to reuse); the existing node tests for `timeWords`, `playheadValueText`
and `movieWords` (`playback.test.ts`, `labels.test.ts`), which pin the current wording and must be updated.
**Decision**: measure, in the task that builds it, the readout's and each cell's bounding width every 100 ms across a
playthrough in Chrome 154 and Firefox >= 155, light and dark, 1280 and 390 px. The old behaviour is the control: the
same script run before the change shows the width moving (a failing check first), so the check is known to detect it.
**Rationale**: "never changes width" is only true if it is measured in a browser; a unit test of string length cannot
see a font, a wrap or a flex gap.

### One scale, taken from the longest value
**Context**: "minutes padded to the longest value's width" needs a definition of "longest" that is stable while the clip
plays and while the playhead crosses clips.
**Decision**:
```ts
// web/src/clock.ts: pure, no imports
export type ClockScale = { hourDigits: number; minuteDigits: number; decimals: 2 | 3; longestMs: number }
export function clockScale(longestMs: number, decimals?: 2 | 3): ClockScale   // default 2
export function clockChars(scale: ClockScale): number                          // width in ch
export function formatClock(ms: number | null, scale: ClockScale): string
```
`clockScale(longestMs)`: `hourDigits` is 0 below one hour, else the digits of `floor(longest / 3_600_000)`;
`minuteDigits` is 2 when `hourDigits > 0`, else the digits of `floor(longest / 60_000)` (at least 1). `formatClock`
floors `ms` to the unit of `decimals` (never rounds, so `39.996` is `0:39.99` and a position never reads past its
total), clamps it to `[0, longest]`'s display range, zero-pads minutes to `minuteDigits` and seconds to 2, and always
writes `decimals` fraction digits. `null` is the unknown length: dashes in the same places (`-:--.--`). A value that is
negative or not finite throws a `RangeError` (Principle I: no invented time); callers pass the playhead store's clamped
value, and the player turns an unreadable `currentTime` into `null` itself.
`longestMs` is the longest value cut to the fraction's unit: `formatClock` clamps to it, which is how "a value above the longest is shown as the longest" holds. `clockCell(ms, scale)` returns `{text, ch}` for the screens that reserve the cell (`ui/Clock.tsx`, shared by the Timeline, the player and the trim tip, classes `clock-group`, `clock-key`, `clock-cell`).
The Timeline builds three scales: **clip** from the longest clip in the event, **event** from `lay.totalMs`, **tip**
from the clip's own duration with 3 decimals.
**Rationale**: the scale depends on the clip set, not on the position, so it cannot change during playback. It changes
only when the clip set changes (a Prepare job ends, a clip is removed), which is a page event, not a tick. Zero
padding was chosen over blank padding because a blank is invisible and reads as a layout glitch; `00:09.50 of 12:30.00`
reads as one clock.

### Two decimals for playback, three for a trim
**Context**: the player shows `0:20.476`, the Timeline `0:00.96` or `1:02.4`; the user cannot read either, and a third
digit changes every frame at 60 fps.
**Explored**: frame lengths of the footage: 33 ms (30 fps) and 40 ms (25 fps) are the common ones, 16.7 ms at 60 fps.
**Decision**: playback readouts (Timeline, player, summary) write centiseconds. The trim tip writes milliseconds,
because a cut is stored and typed to the millisecond and the tip is what the edge will become.
**Rationale**: centiseconds are as fine as a person follows while it plays and never alias a frame step. **Trade-off**
stated openly: in the player, "Set From" writes the playhead to the millisecond (`0:02.607`, D-16) while the header
shows `0:02.60`; the value is in the Cuts panel's field the moment it is set, and the header is a where-am-I, not the
cut. If the operator wants the millisecond in the header, the single place to change is the `decimals` argument.

### Layout: fixed cells, one cut-off name
**Context**: text of constant length is still moved by a proportional face, a wrapping row, or a name that wraps.
**Decision**: the readout is a flex row of: the name (`flex: 1 1 6rem; min-inline-size: 0; overflow: hidden;
text-overflow: ellipsis; white-space: nowrap`, whole name in `title`), then one `.tl-readout-group` per pair with
`flex: none`:
```
<span class="tl-readout-group"><span class="tl-readout-key">Clip</span>
  <span class="tl-readout-time" style="--ch: 7">0:00.96</span> of <span class="tl-readout-time" style="--ch: 7">0:39.84</span></span>
```
`.tl-readout-time { display: inline-block; inline-size: calc(var(--ch) * 1ch); font-family: var(--font-mono);
font-variant-numeric: tabular-nums; text-align: end; white-space: nowrap }`, `--ch` set from `clockChars`. Below
the wide breakpoint the row wraps: the name takes its own line and the two groups sit on the next, still fixed. The
name is the only flexible part, so a shorter or longer name never moves a number. The player's header is the same
pattern with one group. The `15ch` is removed.
**Rationale**: `ch` is the width of "0" in the element's font; with the mono face and `tabular-nums` every digit and
colon takes the same cell, so the cell's width is the text's. The inline style only sets a custom property, so no
layout is done in script.

### The words
**Decision**: the key words are "Clip" and "Event" (the summary in the plan: `Clip 0:00.96 of 0:39.84 · Event
1:02.40 of 2:29.76`). "Event" is the whole timeline, the footage as laid out end to end, before cuts; the
existing `Movie 3:12 of 3:45 of footage` line is what remains after cuts and keeps its name. The `·` between groups is
drawn by CSS (`::before`) so a wrap at 390 px leaves no stray separator. The slider's value text becomes
`Harbour, clip 0:12.4 of 0:24.96; event 1:12 of 3:12` in `formatTime` (spoken; padding is for eyes, and "00:09" is
read badly), replacing "... in all", so seen and heard use the same nouns.

### What stays on `formatTime`
Cut times, typed fields, the ruler's ticks, chapter starts, "ready to play, 0:06.02", "From set to 0:01.234" and every
`aria-valuetext`. None changes while playing.

## Goals / Non-Goals

**Goals:** every running time on the Timeline and the clip player says what it is, never changes width during a
playthrough, a scrub or a clip change, and is written by one tested formatter.

**Non-Goals:** as in the proposal: no setting, no timecode toggle, no change to the ruler, chapter list or movie
player, no engine/API/schema work.

## Failure behavior and idempotency

Nothing is written, queued or cached. A value that is not a time throws in `formatClock` (a render error, loud and not a wrong
number) rather than printing `NaN`; the player's unknown length is `null` and prints dashes of the
right width, never `0:00`. A re-render with the same inputs gives the same text (the formatter is pure), and a page
reload, a Refresh and a worker restart change nothing here.

## Risks / Trade-offs

- **Width changes once when the length is read.** The player's scale comes from the clip's length, unknown until the
  browser reads it: the header's width can change once at that moment (if the clip is 10 minutes or more), never
  afterwards. The spec states "never while it plays" and the check opens the player before and after the length.
- **Centiseconds in the player versus milliseconds in Set From** (above).
- **Clamping hides a bad length.** A playhead a hair past a clip's length (float `currentTime`) shows the length. It
  is a display clamp of an artifact, not a stored value; a length that is zero or not finite is `null`, not a clamp.
- **Font fallback.** If `--font-mono` fell back to a face where a `ch` is not a digit's width, the cell would be
  wider or narrower than its text but would still be constant; `tabular-nums` and the mono face are what make the
  text fill it exactly. The browser check looks at the screenshots in both schemes.
- **One more formatter next to `formatTime`.** Justified (Principle VII): the two have different jobs (parsed vs read)
  and different invariants (trailing zeros dropped vs fixed width); merging them with a flag would put an option bag
  in the module the cuts depend on.
- **The slider's spoken value may carry more precision than the screen.** `aria-valuetext` keeps `formatTime` (the raw
  value, trailing zeros dropped) while the visible readout floors to centiseconds: at 12.396 s the eye reads `0:12.39`
  and the ear `0:12.396`. Padding is for eyes; the spoken value stays the more exact of the two.
- **The trim tip is kept inside the track.** Near either end of the track the tip and its snap words would be cut by
  the track's own edge, so they slide back inside it (together, as one box) while the handle itself stays put.
