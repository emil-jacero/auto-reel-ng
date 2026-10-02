## Why

GUI v1 (HLD **§6 phase 8**, §4.10) promises a quiet Edit mode that works by keyboard and gives no wrong
instruction (**D-10**, the visual system). Three small defects in Edit mode's save bar and its
empty-chapter hint break that promise. They were triaged on main at 6a7fe16 and re-checked against the
code before this proposal (design, "Findings, re-checked"):

- **The first edit costs more than the next ones.** The save bar is built when the first edit makes the
  page dirty: `showBar` mounts `<SaveBar>`, runs its placement and registration effect, and registers the
  toast clearance in the same commit as a 400-row list update. The triage measured 110-200 ms for that first
  edit on a 400-clip chapter. The page is idle until then, so the first thing the operator does in Edit mode
  is the slowest.
- **Reset focuses a heading the operator cannot see.** Reset sits on the save bar, at the bottom of a long
  list. It removes the bar, so focus has to go somewhere, and it goes to the page's `<h1>` with
  `preventScroll`. The heading is at the top of the page, so a keyboard or screen-reader user lands on an
  element that is scrolled out of view. This is the follow-up that `edit-mode-polish` recorded in its
  non-goals ("Focus after Reset is unchanged").
- **An empty chapter on a one-chapter event points at a control that does not exist.** A chapter that plays
  no clip says "Drag clips here, or move them here with another chapter’s Move clips." The sentence is a
  constant. On an event that lists one chapter there is no other chapter to drag from, and the page offers no
  Move clips on a lone chapter ("Edit mode adds, renames, reorders and deletes chapters").

All three are in `web/src/edit/`. None changes what is saved, the API or the engine.

## What Changes

- **The save bar is part of the page from the moment Edit mode is ready.** It is mounted while the editor
  has read the document, and carries the `hidden` attribute while there is nothing to save and no vanished
  event to explain. The first edit removes the attribute instead of building the bar. Its placement, its
  height property and its toast registration still run only while it is shown, so a hidden bar holds no room,
  hides nothing and is not in the accessibility tree. The editor stops computing the bar's summary while it is
  hidden.
- **The first edit costs what the second one does.** Measured with a 400-clip chapter in a real browser, the
  first edit is handled within 50 ms of the second of the same kind. If hiding the mount does not reach that,
  the cause is somewhere else; the implementation stops and reports that, rather than weakening the bound.
- **Reset scrolls the heading into view when it is out of view.** After Reset the heading still takes focus
  at once. Once the page has settled, the page scrolls the least distance that brings the heading fully
  into view below the sticky header, and does not scroll when it is already there.
- **The empty-chapter hint is built from the chapter count.** With another chapter listed, the words are
  today's. A lone chapter says only that it has no clips and is left out of the movie, or that it plays no
  clip.

## Non-goals

- **No change to what a save writes**, to Reset's meaning (it restores what was read), or to where the bar
  rests or is held (`placeBar` and its rules).
- **No change to the toast contract.** `web-toast-and-dialog-layers` owns the toast region, its placement
  and its `--toast-rise-h`. This change keeps registering the bar with `keepToastsClearOf(bar)` only while the
  bar is shown, as that contract assumes.
- **No unit-test framework is introduced here.** The empty-chapter words are a pure function so that they
  can be tested with whatever runner `web-toast-and-dialog-layers` sets up for `toast.test.ts`; the browser
  behaviour is verified in a real browser.
- **The read-only event page and the multi-chapter hint are unchanged.** Pointing at "another chapter’s
  Move clips" when every other chapter is itself empty (Move clips is then offered but disabled) is a
  separate wording question.
- **No new dependency, token, API, engine or schema change** (Principle VII).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `web-app`: two ADDED requirements and two MODIFIED ones, all Edit mode's own.
  - ADDED `Requirement: Edit mode's save bar is in the page before the first edit`
  - ADDED `Requirement: Reset leaves keyboard focus on a heading that can be seen`
  - MODIFIED `Requirement: Edit mode adds, renames, reorders and deletes chapters` (the empty-chapter
    sentence)
  - MODIFIED `Requirement: Edit mode drags clips between chapters` (the area an empty chapter shows)

## Impact

- **Packages:** `web/` only.
  - `src/edit/EventEditor.tsx`: the bar is rendered while the editor is ready and hidden while clean; its
    summary is computed only while shown; a layout effect keyed on the reset counter brings the heading into
    view.
  - `src/edit/SaveBar.tsx`: a `shown` prop; the doc comment.
  - `src/edit/ClipOrderList.tsx`: the empty-chapter words come from a function of "is this the only chapter"
    and "is it wholly empty".
  - `src/edit/emptyChapter.ts` (new) and its test: that function.
  - `src/edit/edit.css`: no rule changes (`[hidden]` already wins in `reset.css`); at most a comment, if the
    gate `web-toast-and-dialog-layers` leaves one that says the bar is mounted conditionally.
- **CLI vs API (Principle V):** untouched.
- **Rendered output:** unchanged. No `RENDER_GRAPH_VERSION` bump; the staleness fingerprint inputs are
  unchanged.
- **Schemas:** no `reel.yaml`, `config.yaml` or API change, no Alembic migration, no rescan.
  `web/openapi.json` and `schema.d.ts` are untouched.
- **Dependencies:**
  - **New runtime dependencies:** none.
  - **Gates, merged before implementation:**
    - `web-toast-and-dialog-layers`: edits `edit.css` and the toast files; its resting-bar `margin-block-end`
      and its `ResizeObserver` assume the bar is registered only while shown, which this change keeps
    - `api-excluded-clips-read-model`: edits `ClipOrderList.tsx` (an "Excluded" pill, Cuts hidden for excluded
      clips); this change touches only the empty-chapter constants and the `words` prop there
  - Parallel changes `web-save-shortcut` and `web-edit-verdict-refresh` also edit `EventEditor.tsx`; the
    lines this change touches (the `showBar` render, the Reset handler and one new effect) are separate from
    theirs, and the later to land rebases onto the earlier.
- **Size (Principle VIII):** one package, one capability delta, 6 tasks.
