## Context

See proposal.md - Why. Everything here is in `web/`; the toast store (`ui/toast.ts`) is a module-level
store read through `useSyncExternalStore`, `ui/ToastRegion.tsx` renders it once in the shell and places
itself relative to a registered bar (`keepToastsClearOf`, called by `EventEditor`), and `ui/Dialog.tsx` wraps a
native `<dialog>` + `showModal()`. There is no committed web test runner: every earlier web change was
verified with a Playwright script kept in the session scratchpad. Each finding in the triage was re-read
against main (6a7fe16):

| Finding | Re-checked in the code |
|---|---|
| Info evicts an unread error | `toast.ts` `show()`: `held.find((s) => s.tone !== 'error') ?? held[0]` is evaluated before, and without, `tone`. Three errors then an info gives `error:e2, error:e3, info:i4` - e1 is gone. |
| Toast under a modal | Nothing in `ui/`, `styles/` or `shell/` uses `popover`, `showPopover` or `inert`. `.toast-region` is `position: fixed; z-index: 30`; a modal `<dialog>` is in the top layer, above any z-index. `startClock` ignores dialogs, so a success toast expires behind the backdrop. |
| Resting bar | PR #26 already re-places on scroll/resize and observes the bar and region *sizes*, and publishes `--toast-rise-h` (used only by `scroll-padding-bottom` and the page's bottom padding). Remaining: (1) no trigger when layout above the bar moves it without a size change of the bar; (2) no room between the last chapter and a resting bar, so a toast placed above the bar sits on the last row. `README.md` calls this "a known gap". |
| Escape then Save | `Dialog` effect cleanup: `if (opener instanceof HTMLElement && opener.isConnected) opener.focus()` runs for every close, after `dialog.close()`. The spec's wider claim (3-4 ms window) is not hand-reachable; it is a real ordering bug all the same (Escape fires the native `close`, `onClose`, a state update, then the cleanup). |

## Goals / Non-Goals

**Goals:**
- An unread error is only ever displaced by a newer error.
- An error toast is visible above an open modal dialog; success/info toasts do not expire unseen under one.
- With a resting save bar and a toast above it, the last row and every focus stop stay uncovered at
  320 x 256 and 320 x 568.
- A dialog's close never takes focus away from a control the operator already moved to.

**Non-Goals:**
- Making the toast operable (focusable, dismissible) while a modal dialog is open - the platform decides that
  (Risks).
- A toast queue, a toast cap other than three, or per-dialog toast routing.
- Changing the held-vs-resting rule of the save bar (`placeBar`), which `web-edit-save-bar-polish` and
  `web-save-shortcut` build on.

## Research & Decisions

### A full stack never drops an error for a lesser toast
**Context**: `show()` must make room at `MAX_HELD = 3`.
**Explored**: Reproduced with a copy of `toast.ts` under `node --experimental-strip-types` (triage
`repro.mts`): error e1..e3 then info i4 leaves `e2, e3, i4`. Alternatives: (a) refuse the new non-error toast
when nothing non-error can be dropped; (b) allow a fourth transient slot; (c) drop the oldest *info/success*
even when the new one is also info (already the case).
**Decision**: (a). In `show()`: when full, `dropped = held.find(non-error)`; if there is none, a new *error*
drops `held[0]` (unchanged) and any other tone returns without adding anything (no `nextId` consumed, no
clock, no emit). The header comments in `toast.ts` and `ToastRegion.tsx` are rewritten to say "a fourth drops
the oldest non-error toast; when all three are errors, only a new error drops the oldest".
**Rationale**: smallest change; (b) would let the stack exceed the height the page reserves
(`--toast-region-h` is sized for three); the lost info/success toast is a confirmation, the held errors are
failures (Principle I).

### Toasts above a modal dialog: a manual popover, re-promoted on dialog open
**Context**: a modal `<dialog>` is in the top layer, so no z-index lifts the region above it.
**Explored**: (A) make the region `popover="manual"` and `showPopover()` it; re-run `hidePopover()` +
`showPopover()` when a modal dialog opens, because the top layer is ordered by insertion time and a popover
opened *before* the dialog sits under it. (B) Defer: count open dialogs, queue toasts without clocks, flush
on close - errors stay unseen meanwhile. (C) Render the region inside the dialog - couples `ui/Dialog` to a
singleton and duplicates live regions.
**Decision**: (A) for visibility of every toast, plus the cheap half of (B) for the clocks:
- `toast.ts` gains a module counter `modalDepth` and `enterModal(): () => void` (idempotent release) and
  `onModalOpened(listener): () => void`. The effective pause is `isPaused || modalDepth > 0`; a single
  `syncClocks()` stops or starts every running clock when that value changes, and `startClock` checks it, so
  a toast raised under a dialog is created with a stopped clock and keeps its full 5 s until the last dialog
  closes. `pauseToasts` (hover/focus) keeps its meaning and only changes `isPaused`.
- `Dialog` calls `enterModal()` in its open effect immediately after `showModal()` and releases it in the
  cleanup after `dialog.close()`; `enterModal` notifies `onModalOpened` listeners synchronously.
- `ToastRegion` renders `<div popover="manual" className="toast-region">`, calls `showPopover()` in a mount
  effect (hide in its cleanup, so StrictMode's double mount is safe), and re-promotes on `onModalOpened`
  (`hidePopover(); showPopover()`). Both calls are guarded by `typeof region.showPopover === 'function'`, so
  a browser without the API keeps today's plain fixed region (and today's behaviour).
- `.toast-region[popover]` resets the user-agent popover box (`inset: auto` then the existing
  `inset-block-end` / `inset-inline-end`, `margin: 0`, `padding: 0`, `border: 0`, `overflow: visible`,
  `background: transparent`, `color: inherit`), keeping `position: fixed`, the width and `pointer-events:
  none`. The `z-index` is dropped (meaningless in the top layer).
**Rationale**: only (A) shows the error; it needs no knowledge of which dialog opened. Pausing success/info
clocks stops them from expiring unseen; showing them above the dialog as well costs nothing.
**Failure behaviour**: if `showPopover()` throws (a disconnected node, a `popover` already open) the effect
catches it and leaves the region where it is; no toast is ever dropped because of it.
**Idempotency**: a re-promote while the region holds focus is harmless - the dialog has just taken focus
(`showModal()`), and the region's hand-off logic already treats a vanished focus target as "go to the
heading". A second dialog opening on top of the first re-promotes again; two overlapping `enterModal`s keep
the clocks paused until both are released.

### Room above a resting save bar
**Context**: with the bar resting (`data-rests`, in the page after the last chapter) and too little room
below it, `place()` puts the region *above* the bar, over the last row.
**Decision**: `place()` publishes, besides `--toast-rise-h`, `--toast-room-h` on `<html>`: the same value
(`ceil(height + gap)`) **only while the region is placed above the bar** (the room below the bar does not fit
the toasts), removed otherwise. The decision is the fit test itself, not `offset > 0`: the offset is 0 while
the bar is still under the window's bottom edge, and keying the room on it would let the room's own shift
toggle it (found while implementing).
`edit.css` gives `.save-bar[data-rests]` `margin-block-start: var(--toast-room-h, 0px)`, so the room sits
between the last chapter and the bar, exactly where the region lands. A *held* bar has no such margin
(`position: sticky`, not `data-rests`), so the property is harmless there.
Room is reserved only while toasts sit above the bar, so the choice above/below cannot flip-flop: adding the
room moves the bar down the page (less room below it, so "above" stays true); removing it, because the region
moved below, moves the bar up (more room below, so "below" stays true).
The fit test is evaluated on the bar **as it would sit with no room before it**: the bar's bottom minus its
computed `margin-block-start` (the room it carries while it rests; a held bar has none). Without this the
switch had a band about a toast tall: the room already applied pushed the bar down, so scrolling up turned
"below" off at 32 px from the end but scrolling back down turned it on only near the new, taller end (measured
in Chromium at 320 x 568, one toast: the room stayed on all the way to the end). With it the choice depends
on the scroll position alone, so the switch is at one position in both directions. The switch itself still
moves the bar by the room (a toast tall) when it happens: the toast changes sides, and that is accepted.
`place()` gains a second trigger: a `ResizeObserver` on `document.documentElement` and on `bar.parentElement`
(the document grows or shrinks when content above the bar changes), next to the existing bar/region
observers. The callback is idempotent (it writes only when a value changed), so the room it reserves does not
loop through the observer.
**Alternatives**: `margin-block-end` on the editor (the triage sketch) - equivalent in the flex column but puts
page layout in `ui/`'s contract; a bottom padding on `.page` - too coarse (reserves room for every page, and
`.page` already adds `--toast-region-h`). Rejected.
**Rationale**: the bar's `data-rests` state is decided by `placeBar` (edit/); `ui/` only publishes a number
and the page consumes it, as with `--toast-rise-h` today.
**Spec**: the "MAY cover a control just above the bar" sentence is removed; the measured claim (focus-stop
sweep at 320 x 256 and 320 x 568, one and two toasts) becomes the acceptance check.

### Dialog returns focus only when it still owns it
**Context**: cleanup refocuses the opener unconditionally.
**Decision**: pure `mayReturnFocus(active: Element | null, dialog: Element, body: Element): boolean` in
`ui/returnFocus.ts` - true when `active` is null, is `body`, or `dialog.contains(active)`. The effect reads
`document.activeElement` *before* `dialog.close()` (which may itself move focus), then focuses the opener only
when `mayReturnFocus(...)` and the opener is connected.
Escape: the native `close` has already restored focus to the opener (Chromium) or left it on `body`; either
way the rule gives the same result as today. A Cancel/Confirm button inside the dialog: focus is inside, so
the opener is refocused as today. Operator already on Save: focus is outside and not on body, so it stays.
**Rationale**: a file of its own only so the rule has a committed unit test that needs no DOM (the arguments
are structural); `Dialog.tsx` is TSX and cannot be loaded by Node's type stripping.

### How the tests run
`web/package.json` gains `"test": "node --test --experimental-strip-types \"src/**/*.test.ts\""` (the glob
quoted, so Node expands it recursively; unquoted, `sh` would expand it one level only); `tsconfig.json`
excludes `src/**/*.test.ts` from the app program, and `tsconfig.test.json` type-checks them with `@types/node`
(a dev dependency; `check` and `build` run both programs, so the tests meet the strict-typing convention). `toast.test.ts` sets
`globalThis.window = globalThis` and imports `./toast.ts` dynamically afterwards; it drives time with
`node:test`'s `mock.timers` (`setTimeout`, `Date`), which patches the `window.setTimeout` alias too because it
is the same object. Run: `podman run --rm -v $WT/web:/app:Z -w /app docker.io/library/node:22 npm test`
after `npm ci`.

## Risks / Trade-offs

- [A popover outside a modal dialog is inert, and inert content may be hidden from assistive technology] ->
  The visible error is the goal; it stays until dismissed after the dialog closes. While a dialog is open the
  region carries `data-under-modal` and its Dismiss buttons and links are drawn at half opacity, so they do
  not offer a press that does nothing. An error raised under a dialog is not announced then, nor when the
  dialog closes (its text does not change): a recorded limit, not handled here. The Playwright pass records
  what Chromium does (visible above the backdrop; whether `role=alert` is in the accessibility tree while
  inert). If it is hidden from AT, the design stays and the finding is noted in the final report as a known
  limit (the spec asks for visibility, not operability, under a dialog).
- [`showPopover()` while focus is in the region drops focus to `body`] -> The dialog's own focus move follows
  it in the same task; `ToastRegion`'s layout effect also hands focus on if the focused toast vanished.
- [A popover's user-agent styles leaking] -> The reset lists every UA property (`inset`, `margin`, `padding`,
  `border`, `background`, `color`, `overflow`, `width/height: fit-content` replaced by the existing sizing);
  checked in light and dark at 1280 and 390.
- [Reserved room appears when a toast appears and the bar rests: the page grows by a toast's height] ->
  Intended: it is the room the toast would otherwise cover. It collapses on dismissal; a scroll clamp at the
  page's end is expected and not announced.
- [320 x 256 may not hold two stacked toasts and a row] -> The requirement is checked with one toast at
  320 x 256 and 320 x 568, and with two at 320 x 568; if the 256-pixel case cannot hold even one, report it
  rather than weaken the requirement silently.
- [The browser behaviour has no committed test] -> Same as every web change before it; the pure rules (toast
  eviction, clock pausing under a dialog, focus-return) do, and the task list names the Playwright checks.

## Implementation findings

- Chromium treats the popover region as inert while a modal dialog is open (`elementFromPoint` skips it) and
  it is absent from the accessibility tree then: an error is seen above the backdrop, not announced or
  operable until the dialog closes. As designed (Risks); it stays shown until dismissed.
- At 320 x 256 the focus-stop sweep covers the save bar and the clip rows. The metadata form's description
  textarea (88 px) cannot clear a 114 px toast plus the sticky header in a 256 px window; that is outside the
  requirement (bar and clip rows) and is not changed here.
- When the bar's top is above the window's top edge or the stack is taller than the room above a low bar, the
  region extends past the window's top edge, as before this change; no placement fits there.
