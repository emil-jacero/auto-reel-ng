## Why

The user, looking at the Timeline and the clip player in a browser (2026-10-03, with screenshots), said: "The numbers
are hard to interpret and they jump when it plays. When it goes to single digit it gets shorter which affects the rest
of the line. And I don't know what they do. Same with the numbers in the top left corner" of the clip player. Two
screens are named: the Timeline's readout under the video (`s1710002.mp4 0:00.96 / 0:39.84 1:02.4 / 2:29.76 in all`)
and the clip player's header (`0:20.476 / 0:20.64`).

Reading the code finds three causes, all on the client (HLD §4.10, §6 phase 9 GUI v2; D-20 for the Timeline, D-16 for
the clip player; no research item is open, and `research/v2/timeline-library.md` has no finding on readouts, so the
evidence is the user's report and the code):

1. **The number changes width as it plays.** Every readout is written by `formatTime` (`web/src/cuts/times.ts`), which
   is right for a *cut's time* (it is typed back and parsed, so it drops a trailing zero: `1:02.4`, `1:02.35`,
   `0:01`) and wrong for a *running time*: the text is 4 to 8 characters long and changes length several times a
   second. `tl-readout` is a wrapping flex line, so a shorter number moves everything after it, or wraps it.
2. **The number says nothing about what it is.** `a / b` and `c / d in all` do not say which is the clip, which the
   whole timeline, which the position and which the length.
3. **The reserved width is a guess.** The player's `.preview-time` reserves `15ch` for the longest text it writes,
   `0:20.476 / 0:20.64`, which is 18; and the Timeline's clip name has `overflow-wrap: anywhere`, so a long name wraps
   and pushes the numbers instead of being cut.

## What Changes

- **One formatter for running times** (`web/src/clock.ts`, a pure module with no imports, like `format.ts`): a scale
  taken from the longest value a readout can show, then every value written to that scale. Minutes are zero-padded to
  the longest value's width (hours appear only when the longest has them), the fraction has a fixed number of digits
  (2 for playback readouts, 3 for the trim tip, which shows a cut's own millisecond), the value is floored so a
  position never reads past its total, and an unknown length is dashes of the same width. `formatTime` is untouched:
  cut times, typed fields and spoken words keep it.
- **The Timeline's readout says what each number is, and holds still**: `Clip 0:00.96 of 0:39.84 · Event 1:02.40 of
  2:29.76`. The clip's scale is the event's longest clip, the event's the whole timeline, so crossing a clip boundary
  changes no width. The time cells have a reserved width in `ch` on a monospace face with `tabular-nums`; the clip's
  name is one line, cut with an ellipsis, with the whole name as its tooltip. The slider's value text uses the same
  words ("Harbour, clip 0:12.4 of 0:24.96; event 1:12 of 3:12") so what is seen and what is heard agree.
- **The clip player's header** (Edit mode's preview and the event page's Watch, the same component) says
  `Clip 0:20.48 of 0:20.64` the same way, replacing the `15ch` guess.
- **The trim handle's tip** and the Timeline's `Movie 3:12 of 3:45 of footage` line are written by the same formatter,
  so no running time on the Timeline has the old behaviour. The tip's snap words stop moving its time.
- **Record**: D-20 and D-16 in `docs/high-level-design.md` gain the readout rule; §4.10 and §6 name the change.

Non-goals:

- No change to `formatTime`, to a cut's typed form, to a field's parse, to `reel.yaml`, or to what is announced to
  assistive technology other than the slider's value text and the "Movie … of footage" words.
- The ruler's tick labels and the chapter list's start times are not running times (they do not change while
  playing; ticks sit at positions of their own) and keep `formatTime`. The movie player has no running readout: it
  uses the browser's own controls.
- No new control (no frame/timecode toggle), no setting for the number of decimals, no change to the playhead's
  precision or step, no change to how often a readout is repainted.
- No engine, API, job, schema or fingerprint change: **rendered output is unchanged for identical inputs, so no
  `RENDER_GRAPH_VERSION` bump**, the staleness fingerprint's inputs are unchanged, no `reel.yaml` or `config.yaml`
  change, no Alembic migration, no rescan.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `web-app`: ADDED "Running times are written to a fixed width and say what they are" (the formatter's rules, the
  Timeline readout, the player's readout, the trim tip, the summary line); MODIFIED "Edit mode previews a clip on
  request", whose sentence "The preview SHALL show the time and the clip's length in that same format" (the Cuts
  panel's, `0:01.234`) is replaced by the new rule. The slider's value text keeps the Cuts panel's format.
- `event-timeline`: MODIFIED "The playhead scrubs one video": the readout below the video is labelled, and the
  slider's value text uses the same words.

## Impact

- Package `web/` only; the CLI and the API are untouched (Principle V holds: nothing new is reachable only from the
  browser). New: `web/src/clock.ts` and `clock.test.ts`. Changed: `timeline/Playhead.tsx`, `timeline/labels.ts`,
  `timeline/TrimHandle.tsx`, `timeline/Timeline.tsx`, `timeline/timeline.css`, `preview/playback.ts`,
  `preview/ClipPreview.tsx`, `preview/preview.css`, and their tests.
- No new dependency (Principle VII; D-8's list is unchanged): the formatter is about forty lines and the layout is CSS.
- `docs/high-level-design.md`: D-20, D-16, §4.10, §6.
