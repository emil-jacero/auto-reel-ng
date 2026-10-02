## Context

See proposal.md, "Why". Code on main f0b6ca3 (after the gates): `web/src/edit/EventEditor.tsx` and `SaveBar.tsx`.

- **The save path.** `submit(pressed, operation)` (`EventEditor.tsx`, near line 1559) is the one function that
  saves. It returns without effect when `ready === null`, a save is in flight (`saving.current`), a Move
  clips is pending (`moving.current`), something is typed but not added (`unfinished(ready)`), or nothing
  changed (`!edited`). Otherwise it dispatches `save-start`, builds the body with `buildWriteBody`, sends
  it with the read etag, and on success toasts "Saved <name>" and calls `onSaved` (which leaves Edit mode);
  on failure it dispatches `save-failed`.
- **What holds Save back lives in the button.** `SaveBar` computes `unsendable = !edited || unfinished` and
  `saveBlocked = unsendable || problem is conflict or gone`, and makes the button `aria-disabled` and inert.
  `submit` knows the first group but NOT the conflict and gone cases: after a conflict, calling
  `submit('save', 'save')` directly would send the save again with the stale etag. A shortcut that only calls
  `submit` would therefore bypass a rule the button enforces. This is the main hazard (Decision 2).
- **Focus after an answer** (`answers` effect): a failure leaves focus where it was unless it fell to
  `<body>`, then goes to the alert; it scrolls the focused control into view above the bar. So a save started
  from a text field keeps the caret in that field. Nothing to add.
- **The live region.** One `<p role="status" class="visually-hidden">` in the editor shows `announcement`;
  `announce(message)` clears it and sets it a frame later so that a repeated message is said again. Success
  is a polite toast ("Saved …", `toast.success`); a failure is the bar's alert.
- **Keyboard users today.** The editor's Tab order is the page's order, so Save is last. Dialogs
  (`ui/Dialog.tsx`, native `<dialog>` + `showModal()`) are modal: `EventEditor` has two (Discard unsaved
  changes, Overwrite the other change), `ChapterDialogs` has two (name, Move clips), and the render panel's
  Render dialog (`jobs/RenderControl.tsx`) can be open in Edit mode as well. dnd-kit's keyboard drag listens
  for Space, Enter, arrows and Escape; none is S.
- **Latest state in a listener.** `latest.current` (a `useRef<Ready | null>` assigned each render,
  `EventEditor.tsx` near line 1216) already exists so that stable callbacks read the current draft.

## Goals / Non-Goals

**Goals:**
- Ctrl/Cmd+S from any focus on the page saves exactly as the button would, or says why it does not.
- One definition of "Save cannot act now", used by the button and the shortcut.
- Independence from how the bar is mounted or shown (`web-edit-save-bar-polish` changes that).

**Non-Goals:**
- A shortcut registry, a help overlay, user-configurable keys (Principle VII).
- Changing `submit`'s own guards, what Save writes, or any failure presentation.
- Skipping the leave-page or Overwrite confirmations; the shortcut reaches neither.

## Decisions

### 1. One `keydown` listener on `document`, registered while the editor is ready

**Context**: focus may be in a text field, on a clip handle, on a thumbnail button, or on `<body>`; a
listener on the editor element would miss `<body>` and the header.
**Explored**: `onKeyDown` on `.event-editor` (misses the header and `<body>`, where focus sits after Reset
or a click on empty space); `window` (same as `document` here); a `<form onSubmit>` (the editor is not a
form, and Enter must not save).
**Decision**: a `useEffect` keyed on `ready !== null` adds `document.addEventListener('keydown', onKey)` and
removes it on cleanup. The handler reads the live state through `latest.current` plus the refs `submit`
already uses, so the effect does not re-register on every keystroke of a field. A key is the shortcut when
`(ctrlKey || metaKey) && !shiftKey && !altKey && !isComposing && key.toLowerCase() === 's'`.
`event.key` (not `event.code`) so that the key labelled S works on Dvorak and AZERTY. `altKey` excluded
because AltGr is Ctrl+Alt on Windows and types characters; Shift excluded because Ctrl+Shift+S is the
browser's and the OS's own ("Save as" in editors).
**Rationale**: it is registered only while there is something to save into. While the document is loading or
its read failed there is no editor, so the browser's behaviour is left alone.

### 2. `saveHold`: one rule for the button and the shortcut

**Context**: `submit` does not know the conflict and gone holds (Context, "What holds Save back lives in the button").
**Explored**: (a) the shortcut clicks the Save button through a ref (inherits `aria-disabled` handling, but
breaks if `web-edit-save-bar-polish` hides or unmounts the bar while clean, and a `.click()` on a hidden
node is not a user press); (b) copy the conditions into the effect (drifts); (c) move the hold into `submit`
(it also serves Retry and Overwrite, and Overwrite with mine is legitimately sent while a conflict holds
Save back).
**Decision**: export from a new pure module `saveShortcut.ts` (imported by `SaveBar.tsx` and `EventEditor.tsx`;
not from the `.tsx` so that `npm test` can load it)

```ts
export type SaveHold = 'nothing' | 'unfinished' | 'conflict' | 'gone'
/** Why Save cannot act now, or null. Pressed-state is a separate rule (`locked`). */
export function saveHold(edited: boolean, unfinished: boolean, problem: { kind: string } | null): SaveHold | null
```

Precedence: `gone`, then `conflict`, then `unfinished`, then `nothing`. A vanished event with no edits is
"gone", not "nothing"; a date typed in part is `unfinished` though `edited` is false. The button's `saveBlocked` becomes `saveHold(...) !== null`; `unsendable`, which also feeds
Retry and Overwrite, is unchanged. The shortcut calls `saveHold(edited, unfinished(ready), ready.problem)`;
`null` means call `submit('save', 'save')`.
**Rationale**: smallest change that makes drift impossible, `submit` untouched, and no DOM dependency.

### 3. What happens in each state

The key is always `preventDefault()`ed once the editor is ready, even when nothing is saved: muscle memory
for Ctrl+S in an editor must not open the browser's file dialog over a half-edited page. In order:

| State when pressed | Write | Live region |
|---|---|---|
| a dialog is open (`document.querySelector('dialog[open]')`) | none | silent |
| key repeat (`event.repeat`) | none | silent |
| a save is in flight (`locked`), or a Move clips is pending (`movingFrom !== null`) | none | silent (the bar already says "Saving…") |
| `saveHold` = `nothing` | none | "Nothing to save." |
| `saveHold` = `unfinished` | none | "Not saved: the date is incomplete." / "Not saved: a cut is typed and not added." / both joined with " and " |
| `saveHold` = `conflict` | none | "Not saved: choose Reload latest or Overwrite with mine first." |
| `saveHold` = `gone` | none | "Not saved: this event no longer exists." |
| otherwise | `submit('save', 'save')` | "Saving…" |

The open-dialog row is checked first and generically (any native `<dialog>` that is open), because the render
panel's dialog is not Edit mode's own state. The in-flight and Move-clips rows reuse the refs `submit`
checks, so that a second press never announces "Saving…" twice.
A failed save started by the shortcut is shown by the bar's alert as for the button, with `pressed: 'save'`
(the Save button shows busy while the field keeps the caret). `Retry` is the failure's own button.

**Wording**: the unfinished and conflict messages repeat words the bar's summary and alert already show
("date incomplete", "cut typed on … not added"; "Reload latest", "Overwrite with mine"), so a screen-reader
user hears the same names.

### 4. Announcing

`announce()` (the editor's existing function) for every row with a message. "Saving…" is spoken at the start
because the shortcut can start from a field far from the bar, where nothing else changes; the success toast
follows (polite), and a failure is the bar's own alert (assertive). A pointer press on Save is left exactly
as it is (the bar's title turns to "Saving…" and the button is `aria-busy`); this change does not add
announcements to the button.

### 5. Telling people it exists

`aria-keyshortcuts="Control+S Meta+S"` on the Save button (the ARIA attribute for exactly this; it is
informative only, it implements nothing) and `title="Save (Ctrl+S, or ⌘S on a Mac)"`. No visible text: the
bar's width budget at 390 and 320 px, and its height budgets, stay as specified. A `title` is not available
to touch or to keyboard-only users, which is why `aria-keyshortcuts` carries the information; `web/README.md`
documents it for everyone.
**Interaction**: when Save is held back and `aria-describedby` points at the summary or the alert, that
description replaces the title for assistive technology; the shortcut's name is still exposed by
`aria-keyshortcuts`.

### Gates

Both gates edit the files this change edits, and neither changes the behaviour it relies on. Re-checked
against their triage entries:

- **`web-edit-save-bar-polish`** (merged) mounts `SaveBar` from the start of Edit mode and hides it while
  clean (`<SaveBar shown={showBar} … />`, stable `barRef`). This change does not
  depend on the bar's presence: the shortcut reads `edited`, `unfinished` and `problem` from the editor's
  state (Decision 2) and never touches the DOM node. When the bar is hidden because the draft is clean, the
  shortcut says "Nothing to save." through the live region, which a hidden bar could not. The edit to the
  Save button (`aria-keyshortcuts`, `title`) is two attributes; if the gate has moved `saveBlocked`, the
  `saveHold` refactor is applied to wherever it lives. Task 1.1 re-reads both.
- **`web-playback-and-notices`** (merged) keeps `MoviePanel` mounted but hidden in Edit mode. Its
  requirement says "the page SHALL add no keyboard shortcut of its own" about the movie section's player
  (the read view); Ctrl/Cmd+S is Edit mode's and exists only while the editor is ready, so the two do not
  meet. A hidden `<video>`
  cannot hold focus, and the player's own keys (Space, arrows, F, M) do not include Ctrl/Cmd+S; the
  document listener sees the press first only if focus is outside the player, and inside it the press
  bubbles to `document` all the same. No interaction. Task 1.1 confirms on the merged code that the player
  does not stop propagation of keydown.
- **`web-edit-verdict-refresh`** (not a gate; same round) refreshes only the render panel's verdict while
  Edit mode is open; it does not touch the draft, so a shortcut save sees the same baseline and etag.

## Risks / Trade-offs

- **[A keyboard drag is lifted when Ctrl+S is pressed]** The lifted clip is not yet an edit (dnd-kit commits
  at drop), so a save writes the draft as it stands and leaves Edit mode, which unmounts the drag. The
  button cannot be pressed mid-lift, so this is new. → Accepted: Escape-then-save would be the tidy order,
  but the edge needs a drag-state signal `EventEditor` does not have, and the effect is "the lift is not
  saved", which is what the operator sees on screen (the clip has not moved yet). Revisit if reported.
- **[A browser or extension owns Ctrl+S]** In a page that calls `preventDefault()` in `keydown`, Chrome and
  Firefox do not open the Save dialog. Some extensions bind it; if they see the event first the page never
  does. → Nothing to do; the button stays.
- **[Intercepting the key when nothing is editable]** An operator who wants the browser's Save page while in
  Edit mode loses it until they leave Edit mode. → Intended: the announcement says "Nothing to save.", and
  the browser's File menu still works.
- **[IME]** A composition ends with keydown events whose `isComposing` is true; they are ignored.
- **[Hidden state drift]** `saveHold` shared by the button and the shortcut stops the two from drifting; the
  Playwright check "conflict holds the shortcut" (task 3.2) is the regression test.

## Verification approach

The pure rules (`saveHold`, `isSaveChord`, `holdWords`) are in `saveShortcut.ts` with a `node --test` file,
like the other pure modules; no framework is added. The keyboard behaviour is tested with
real-browser Playwright scripts run from the scratchpad (never committed), each asserting on the requests
the page sends (a `**/reel` route that records and fulfils or aborts, never a catch-all), `defaultPrevented`
on a `keydown` probe, the live region's text, and focus. They run in light and dark at 1280 and 390 wide,
and the screenshots are looked at.

## Open Questions

None that change the specs, the approach or the tasks.
