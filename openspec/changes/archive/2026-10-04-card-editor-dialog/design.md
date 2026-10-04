## Context

Today (main 89079d9) `TimelineSection` renders `CardInspectorPanel` after the track (title-card-toggle moved it there) for the
page's one card selection (`useCardSelection`: `selected`, `select`, `clear`, `retain`). `ui/Dialog` already wraps native
`<dialog>` + `showModal()` with focus return (`returnFocus`), toast-clock hold (`enterModal`) and `onClose` for operator dismissals;
`RenderControl` uses it. The inspector panel handles Escape itself and calls `onClose`, which refocuses
`.card-row-select[data-selected]` by DOM query and clears the selection. No media research applies.

## Goals / Non-Goals

**Goals:** edit a card where the operator is; one editor; the draft model, preview and field logic unchanged.
**Non-Goals:** the event-style panel, Timeline block playback (`timeline-plays-cards`), reorder, any API change, the
"Move clips" dialog (see Risks).

## Decisions

1. **Reuse `ui/Dialog`.** `CardInspectorPanel` keeps its fields; its `<section class="ci">` becomes the dialog body, its own
   Escape handler is dropped (native cancel -> `onClose`). The dialog gets a title (`inspectorName`), a Close button in the head and
   a Done button in `.dialog-actions`. `Dialog` may need a wide variant class for the two-column layout; nothing else in it changes.
   Alternative: a new dialog component; rejected (one dialog code path for focus, scroll lock and toasts).
2. **Open state separate from selection.** Selection must survive close (highlight), so `CardsBinding` gains `editing: string | null`,
   `open(chapter)` (selects and opens, also when already selected) and `dismiss()` (closes, keeps selection). `select` stays for the
   handle press. The pure transitions go in `cards.ts` next to `cardSelection` and are `node:test`-tested. The state lives with the
   selection above Edit mode, but the dialog renders only in Edit mode and `retain` ends both when the chapter vanishes.
3. **Focus return via the opener.** `Dialog` records `document.activeElement` at open; row and block are the focused buttons when
   activated, so the DOM-query refocus in `TimelineSection` is deleted. If the row re-mounts (chapter list re-render) the existing
   `isConnected` guard falls through and the selected row's button is focused by `data-selected` as a fallback.
4. **Layout.** `.ci` becomes a grid: single column with the preview first at <= 600 px (the sheet is full viewport, no radius, no
   max-height there), two columns (fields | preview, preview sticky) above it; fields scroll inside the dialog, so no horizontal page
   scroll at 320/390. Background scroll lock is native to the top layer; add `overflow: hidden` on `body` while open only if a
   browser still scrolls under it (verified in Chrome and Firefox).
5. **Escape.** With the dialog open Escape closes it and keeps the selection; the row's existing Escape-clears-selection applies
   only when it has focus and no dialog is open (the dialog is modal, so the two cannot both fire).
6. **Handle press** selects, never opens (a modal under an active pointer drag would cancel it).
7. **No inline slot in Edit mode.** The read view keeps `CardInspector` (words only); the status region still announces the selection.

## Risks / Trade-offs

- A preview request inside a modal can outlive close: the existing debounce/stale-response rule applies; unmount aborts it.
- `timeline-plays-cards` also edits `TimelineSection` and the blocks: this change touches only the inspector slot and the block's
  press handler; whichever lands second merges onto the other.
- Native `<dialog>` in Firefox: focus return and scroll lock are verified in both browsers (Playwright).
- The user's second remark ("it also look like we can remove the old > Move clips...") names a different surface and is not in
  this change's brief; it is reported to the supervisor as a separate candidate change rather than guessed at here.
