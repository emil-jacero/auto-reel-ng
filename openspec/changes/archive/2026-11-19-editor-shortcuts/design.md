## Context

Every Timeline key is an element's own `onKeyDown`:
- **The playhead grip** (`timeline/Playhead.tsx`, `playheadKey` in `timeline/keys.ts`): Space, the arrows, Page Up and
  Page Down, Home and End.
- **The track scroller** `.tl-viewport` (`timeline/Track.tsx`): `+ = - _ 0 \` (`trackZoomKey`), Alt+Left and
  Alt+Right (`clipMoveKey`), and Q, W and S.
- **A clip block** `.tl-clip-press`: Enter and Space select the clip, with `preventDefault`.

On `document`, only Ctrl/Cmd+S (`saveShortcut.ts`), Ctrl/Cmd+Z and Y (`undoShortcut.ts`, workspace only) and Escape
(`useSelection.ts`) are listened for.

Probe of the running app (2026-11-18, Chromium 1440×900, all writes blocked):

| After a click on… | focus is on | Space plays | `+` zooms |
|---|---|---|---|
| a clip block | `.tl-clip-press` | no (it re-selects) | yes (inside the scroller) |
| the picture | `video.tl-video` | no | no |
| the ruler | `.tl-grip` | yes | no |

Ctrl+wheel zoomed Fit → 240 px/s over the track. Over the tool row and over the viewer it did nothing, so in a real
browser it zooms the page there. The wheel listener is attached in a `[]` effect to `.tl-viewport`
(`Timeline.tsx`, "Ctrl+wheel").

## Decisions

### D1. One key table and pure rules (`edit/workspace/shortcuts.ts`)
```ts
export type Command =
  | { kind: 'playhead'; action: KeyAction }   // Space (toggle), Left/Right (frames ±1), Shift+Left/Right (ms ±1000)
  | { kind: 'hold' }                          // a held Space: preventDefault, no toggle
  | { kind: 'zoom'; key: string }             // + = - _ 0 \  (trackZoomKey)
  | { kind: 'edge'; key: 'q' | 'w' | 's' }
  | { kind: 'move'; way: -1 | 1 }             // Alt+Left/Right (clipMoveKey)
  | { kind: 'help' }                          // ?

export type FocusFacts = {
  enabled: boolean      // the single-key switch (D5)
  field: boolean        // isTextTarget (undoShortcut.ts): text inputs, textarea, select, contenteditable
  dialogOpen: boolean   // a dialog[open]
  inPreview: boolean    // inside an open .clip-preview
  dragging: boolean     // the Timeline's drag store holds a drag, or a pointer is held (D2)
  arrowWidget: boolean  // range input or role slider|radio|radiogroup|tab|tablist|listbox|option|menu|menuitem*|spinbutton|grid|gridcell|tree|treeitem
  spaceControl: boolean // button, checkbox, radio, summary, or role button|checkbox|radio|switch|option|menuitem*|tab
  modality: 'keyboard' | 'pointer'
}
export function workspaceCommand(press: Press, focus: FocusFacts): Command | null
export function focusFacts(target: ElementLike | null, env: Env): FocusFacts
export const SHORTCUTS: readonly Shortcut[]   // { group, keys, words, scope: 'workspace' | 'focused' | 'chord' | 'mouse' }
```
The rules apply in this order:
1. Not `enabled`, `defaultPrevented`, `isComposing`, `field`, `dialogOpen`, `inPreview` or `dragging` → `null`.
2. `?` with no Ctrl, Cmd or Alt → `help`.
3. Space with no modifier:
   - a `spaceControl` reached by keyboard → `null`;
   - otherwise, a repeat → `hold`;
   - otherwise → `playhead` toggle.
4. Left and Right:
   - on an `arrowWidget` → `null`;
   - `clipMoveKey` → `move`;
   - any other Ctrl, Cmd or Alt chord → `null`;
   - otherwise frames, or ms with Shift. A repeat steps again, as on the grip.
5. `trackZoomKey` → `zoom`.
6. Bare q, w or s (either case, no modifier) → `edge`.
7. Anything else → `null`.

Up, Down, Page Up, Page Down, Home and End are not workspace keys: they scroll the bin and the inspector, and stay the
grip's. The Help list is `SHORTCUTS`. A test feeds a press for every `workspace` row through `workspaceCommand` and
checks that each gives a command. It also checks that every command a press can give has a row.

### D2. Last input (`edit/workspace/modality.ts`)
- Capture-phase `pointerdown` sets `pointer`, and a capture-phase `keydown` of Tab (with or without Shift) sets
  `keyboard`. The start value is `keyboard`, which keeps native behaviour.
- Arrows do not count: a click on Rotate, then Right, then Space must still play.
- The module also tracks `pointerHeld`: true from `pointerdown` (button 0) to `pointerup`, `pointercancel`,
  `contextmenu` or window `blur`.
- The pure step function `nextModality(was, event)` is tested.
- `Workspace.tsx` installs the listeners while it is mounted; `lastInput()` and `pointerHeld()` read them. Without a
  workspace the value stays `keyboard`, so the stacked editor is unchanged.

### D3. The listener lives in `useTimeline`
- **Where.** `useTimeline` already holds every action: `onKey`, `onTrackKey`, `onEdgeKey`, the drag store, the
  selection and the reorder. It adds one `document` `keydown` listener in the bubble phase, so a focused element's
  handler runs first and its `preventDefault` shows. The listener is active only when `TimelinePanesContext` is
  non-null (the workspace).
- **Dispatch.** `playhead` → `onKey`, `zoom` → `onTrackKey`, `edge` → `onEdgeKey`, `help` → toggle the list (D4).
- **Moving a clip.** `move` uses the Alt+arrow code, lifted out of `Track.tsx` into one `moveSelected(way)` that both
  call. With no selected clip it does nothing and does not `preventDefault`, so the browser's Back still works.
- **`preventDefault`** runs only when the command acted, or for `hold`.
- **The clip block.** Its Space handler returns early when `lastInput() === 'pointer'`, without `preventDefault`, so
  the document listener plays. Enter is unchanged.
- **The playhead grip** keeps its own keys, which run first.

### D4. The shortcuts list is a native popover
- **The button.** `TopBar` gets a "Keyboard shortcuts" button (keyboard icon; `aria-label` and `title` say the words)
  before the theme switch, with `popovertarget="ws-keys"`.
- **The popover.** `<section id="ws-keys" popover="auto" aria-labelledby>` holds a heading, one `<h3>` and `<dl>` per
  group (`<kbd>` keys, words), and the switch (D5).
  - **Placement:** fixed under the bar (`top: var(--ws-top-measured)`, inline-end 16px), `width: min(22rem, 100vw -
    32px)`, scrolling within the window.
  - **Why not modal:** the keys can be tried while it is open, and D-28 already removed modals that hid the workspace.
  - **Closing:** light dismiss and Escape close it natively.
- **Escape guard.** `useSelection`'s Escape listener also yields while `#ws-keys` is `:popover-open`, so Escape closes
  only the list.
- **`?`** calls `togglePopover()`. Focus is not moved on open; the popover follows its button in the reading order.

### D5. The single-key switch
- **Control:** `<input type="checkbox" role="switch">` "Single-key shortcuts", with a description of what it turns off.
- **Storage:** stored as `auto-reel:shortcuts=off` in `localStorage`; absent means on. Every read and write is in
  try/catch, and when the browser keeps nothing it falls back to on, without a note.
- **Sharing:** a tiny module store, read through `useSyncExternalStore`, so the switch and the listener agree.
- **Off:** `enabled: false`. The grip, track, handle and mark handlers are untouched (WCAG 2.1.4 allows shortcuts that
  are active only on focus), and the Ctrl/Cmd chords are another listener.

### D6. Ctrl+wheel over the Timeline's own part
- **Listener.** The non-passive wheel listener moves from `.tl-viewport` to the track part's root (`.tl-track-part`:
  the tool row, the lanes and the track). It is attached through a callback ref kept in state, so it follows a remount
  instead of reading `scroller.current` once.
- **Anchor.** A pointer inside the scroller's rect zooms about the pointer (today's math). Elsewhere in the part it
  calls `zoomTo(target)` with no pointer, so the zoom keeps the playhead or the view's centre.
- **Outside.** The viewer, the bin, the inspector and the clip panels are portaled out of the part, so the browser
  keeps Ctrl+wheel there.

## Research & Decisions

### Global listener vs focus steering
**Context**: the keys are dead after most clicks.
**Explored**:
- Move focus to the grip on any press in the viewer and the track.
- One document listener.

**Decision**: one document listener (D3).
**Rationale**: focus steering still leaves the keys dead after a click in the bin, the inspector or the top bar. Moving
focus on a press also fights the selection's rule that focus never moves across panes (D-28, `editor-selection`).

### Space on a focused button
**Context**: a mouse user's focus rests on the last control they clicked: Rotate, Play, a mark checkbox.
**Explored**:
- Space always activates the control (today: a click then Space presses Rotate again).
- Space always plays (keyboard users lose Space on buttons and checkboxes, where it is the only key).
- `:focus-visible` (the browser's heuristic; it flips once a key is pressed, so the second Space would differ from the
  first).
- Our own last-input record (D2).

**Decision**: the last-input record. The control keeps Space when it was reached by Tab; after a click, Space plays.
**Rationale**: it serves both kinds of operator, is deterministic and is testable as a pure function. Screen readers in
browse mode send a click rather than Space, and the switch (D5) turns the whole layer off.

### The list: popover vs dialog vs Help panel
**Decision**: a non-modal native popover (D4).
**Rationale**: the operator can read it and try the keys at once. `HelpToggle` is an inline panel per section and does
not fit the top bar, and the toasts already use the Popover API (`popover="manual"`).

### WCAG 2.1.4 (Character Key Shortcuts, level A)
**Decision**: a switch that turns the workspace layer off (D5).
**Rationale**: 2.1.4 asks for a way to turn single-character shortcuts off, to remap them, or to keep them active only
on focus. Off returns to exactly today's on-focus keys.

### J/K/L
**Decision**: not added.
**Rationale**: J is play backwards, which a browser `<video>` does not do with a negative rate in Chrome. K and L alone
would duplicate Space.

## Risks / Trade-offs

- **Space on a clicked button.** The click must be suppressed by `preventDefault` on `keydown`. Chromium and Firefox
  activate a button on `keyup`. 3.1 verifies both. If one still clicks, the listener also cancels the matching `keyup`.
- **Alt+Left with nothing selected** stays the browser's Back, as today: the unsaved guard catches it.
- **Gates.** One listener per document has no per-frame cost. The frame-step gate (p90 ≤ 60 ms) is re-measured through
  the layer in 3.1.

## Failure behaviour

Display and input only: nothing is written and nothing is requested. When storage is unavailable, the switch is on and
not remembered.
