## Context

- **No menu exists.** `web/src` has no menu, no `onContextMenu` and no anchored popup. `ui/Dialog.tsx` is modal, and
  the toasts sit in a `popover="manual"` region. `contextmenu` is heard only to end a gesture (`ZoomSlider.tsx`, the
  undo guard in `EventEditor.tsx`).
- **Every item's edit exists.** Each one is guarded by `idle()`, announced, and is one Undo step (`history.ts`,
  `describeEdit`). The Timeline reaches them through `EditBinding`:
  - `onRotate`
  - `onAdd` (after `cutAtPlayhead`, in the Clip tab's `ClipCuts.add`)
  - `onPoster` (through the Timeline's `usePoster` / `posterWhyFor`)
  - `onMove` (through `reorder.onDrop`; a drop at a chapter's end is `clip-drop`)
  - `onIgnore`
- **The track's tools layer.**
  - A clip's body is `.tl-clip-press` (`role=button`, `aria-pressed`).
  - The edge tools carry `data-identity`; the cut handles sit in `.tl-trims`.
  - The scroller `.tl-viewport` (`tabIndex=-1`) takes zoom, Alt+arrows and Q/W/S in its own `onKeyDown`.
- **Right-button presses already start nothing.** `ClipDrag.onDown`, `EdgeHandles` and `TrimHandle` return early
  unless the button is 0. Nothing listens for `contextmenu` during a drag.
- **From `editor-shortcuts`:**
  - a `document` key layer that skips `defaultPrevented` events, fields, dialogs, previews and drags;
  - `modality.ts`;
  - the `SHORTCUTS` table.

## Goals / Non-Goals

**Goals:** one menu with one set of key, focus and dismiss rules whoever opens it, and no edit of its own: every item
is an existing guarded edit.

**Non-Goals:**
- Submenus, checkable items, type-ahead.
- Exposing the opener beyond the track. That is `plain-clip-bin`'s job.

## Decisions

### D1. One clip menu, owned by `useTimeline`
```ts
type ClipMenuOpen = {
  identity: string
  at: { x: number; y: number } | { box: DOMRectReadOnly } // the pointer, or the block's visible part
  invoker: HTMLElement                                    // focus goes back here
}
openClipMenu(open: ClipMenuOpen): void                    // replaces an open one
```
- **Why the Timeline.** Its items need `editing`, `playhead`, `usePoster` / `posterWhyFor`, `reorder` and the
  selection, which are all there.
- **Where it renders.** In a portal into `document.body`: outside `.tl-viewport`, so the track's `onKeyDown` never
  sees its keys, and clipped by no pane.
- **Later.** `plain-clip-bin` hands `openClipMenu` to its rows.

### D2. The items are pure (`timeline/clipMenu.ts`)
```ts
export type ClipAction =
  | { kind: 'rotate'; way: Way } | { kind: 'cut' } | { kind: 'poster' }
  | { kind: 'move'; chapter: ChapterKey; name: string } | { kind: 'ignore' }
export type ClipMenuItem = { action: ClipAction; label: string; group: 0 | 1 | 2 | 3; why: string | null }
export type ClipMenuFacts = {
  locked: boolean                                        // EditBinding.locked
  cutWhy: string | null                                  // cutAtPlayhead's refusal now
  posterWhy: string | null                               // posterWhyFor(clip) now
  others: readonly { key: ChapterKey; name: string }[]   // reorder.chapters but the clip's own
}
export const MENU_LOCKED = 'Clip edits wait for the save or the move of marked clips to finish.'
export function clipMenu(facts: ClipMenuFacts): { note: string | null; items: ClipMenuItem[] }
export function menuSelects(selection: Selection, identity: string): boolean // false: it or a cut of it is selected
export function focusAfter(drawn: readonly string[], identity: string): string | null // next, else previous
```

| Item | The existing edit it makes | Reason when not locked | Undo label |
|---|---|---|---|
| Rotate left / right | `editing.onRotate(identity, way)` | none (a drawn clip is on disk) | rotation of X |
| Cut at playhead | `addCutAtPlayhead`, lifted out of `ClipCuts.add` and shared | `cutAtPlayhead`'s refusal | cut added |
| Use frame as poster | `usePoster('-menu', clip)` | `posterWhyFor(clip)` | poster |
| Move to «chapter» | `reorder.onDrop(identity, { chapter, index, beforeIdentity: null, words: slotWords(null, name) })` | none | move of X |
| Ignore clip | `editing.onIgnore(identity)` | none | ignore of X |

- **The lock.** While locked, `note` is `MENU_LOCKED` and every `why` is that note. `locked` is a prop, so the menu
  follows a save that starts while it is open.
- **The playhead's reasons.** Cut's and poster's reasons depend on the playhead, a store that does not re-render the
  Timeline. They are taken when the menu opens and again on a choice. If the item has become unavailable, the choice
  says the new reason and the menu stays open.
- **Announcements.** Each edit says what it says today ("Moved s1710003.mp4. At the end of Main."). Choosing an
  unavailable item announces its `why`.

### D3. The menu (`ui/Menu.tsx`; pure `placeMenu` and `menuKey` in `ui/menu.ts`)
- **Markup.** A `<div class="menu" popover="manual">` holds:
  - a title `<p id>` with the clip's name;
  - the lock note while locked;
  - `<div role="menu" aria-labelledby>` with `div role=menuitem tabindex=-1` items, each with an `aria-label`, plus
    `aria-disabled` and `aria-describedby` pointing to its visible reason line, and `role=separator` between the
    groups.

  The items are not `<button>`s: a button presses itself when Space comes up, which a keydown `preventDefault` does
  not reliably stop (`editor-shortcuts`' risk).
- **Keys** (`menuKey(press, count, at)`):

  | Result | Keys | What the menu does |
  |---|---|---|
  | `focus(i)` | Up and Down (wrapping), Home, End | `preventDefault`, `stopPropagation` |
  | `choose` | Enter, Space | `preventDefault`, `stopPropagation` |
  | `close` | Escape, Tab, Shift+Tab | `preventDefault`, `stopPropagation` |
  | `pass` | any Ctrl or Cmd chord | nothing |
  | `keep` | anything else | `stopPropagation`, and `preventDefault` except for F1–F12 (so Alt+Left cannot go back behind the menu) |
- **Placement** (`placeMenu(anchor: Point | Box, size, view) → { left, top, maxHeight }`):
  - At a point, the menu's corner is at the point. It flips left or up where it would come within 8 px of the
    window's edge, and is clamped to 8 px.
  - At a box, it goes under the box, start-aligned with a 4 px gap, or above it when it does not fit under and there is
    more room above, and is clamped the same way.
  - The box is the block's rect intersected with the track scroller's, since a long block can start out of view.
  - It is placed in a layout effect after `showPopover()`, before the first paint
    (`position: fixed; inset: auto; margin: 0`).
- **Dismiss**, its own, since a manual popover has none:
  - a capture-phase `pointerdown` outside the menu closes it, and the press goes on to its target;
  - so do a capture-phase `scroll` from outside the menu, a window `resize` or `blur`, and its clip leaving `clips`;
  - a `contextmenu` inside the menu is `preventDefault`ed and does nothing else.
- **Focus.**
  - On open, focus goes to the first item. Unavailable items stay focusable, as in the WAI-ARIA menu pattern.
  - Hover focuses an item.
  - Escape, Tab or a choice hand focus to D5's target.
  - An outside press hands it back to the invoker only when `mayReturnFocus(activeElement, menu, body)` says it was
    left nowhere (`ui/returnFocus.ts`).

### D4. Opening on the track (`Track.tsx`, `ClipDrag.tsx`)
- **One delegated `onContextMenu` on `.tl-viewport`.** The target's `closest('[data-identity]')` names the clip;
  `.tl-clip-press` and `.tl-trims` gain `data-identity`.
  - **No match** (the empty ground, the ruler, a card, a suggestion mark): no `preventDefault`, so the browser's menu
    shows.
  - **A drag is on:** the event is already `defaultPrevented` (a drag cancelled itself, below) or `held(drag)` is
    true. It is `preventDefault`ed and no menu opens.
  - **Otherwise:** `preventDefault`, select the clip if `menuSelects` says so, and open at the event's point. A point
    outside the target's rect is a key-made request the keydown below missed, and opens the menu at the block.
- **The block's `onKeyDown`.** Shift+F10 (no Ctrl, Alt or Cmd) or `key === 'ContextMenu'` selects the clip as above
  and opens the menu at the block. The block gets `aria-keyshortcuts="Shift+F10 ContextMenu"`.
- **`ClipDrag`.** While a press is held, it adds a capture-phase `contextmenu` listener on `window` beside its Escape
  one. That listener runs before React's root listener.
  - An unstarted press ends quietly and frees the drag store, so the request opens the menu (a Ctrl+click on macOS
    presses button 0 first).
  - A started drag is cancelled as Escape does, and the event is `preventDefault`ed, so neither our menu nor the
    browser's opens.

### D5. Focus after a choice
- **Rotate, Cut, Poster:** the clip's block.
- **Move to:** the clip's block at its new place. The selection is set again, which scrolls the track to the clip (as
  in "Bin press again"). If the block is not drawn at that commit, focus goes to the track.
- **Ignore:** `focusAfter(drawn, identity)`, taken before the edit, else the track.
- **Timing.** Focus moves in a layout effect after the commit, never onto a node that is about to unmount ("Edit mode
  keeps keyboard focus in view and never drops it").

### D6. The workspace's key layer (`editor-shortcuts`)
- **Keys pressed in the menu.** The menu stops every key but Ctrl/Cmd chords (D3), so the layer's document listener
  and `useSelection`'s Escape never see them. That is the spec's "the focused control took the key itself", and
  `focusFacts` already counts `menuitem` as an arrow widget and a Space control.
- **Chords that pass.**
  - Ctrl/Cmd+S locks the items through the note.
  - Ctrl/Cmd+Z can take the clip off the track, which closes the menu.
- **Modality.** A right-click sets `pointer`, and Tab out of the menu sets `keyboard`. After the menu closes, Space
  on the block follows `editor-shortcuts`' rule unchanged.
- **`SHORTCUTS` gains two rows:**
  - `{ group: 'Editing', keys: 'Shift+F10 or Menu key on a clip', words: 'Open its menu', scope: 'focused' }`
  - `{ group: 'Mouse', keys: 'Right-click a clip', words: 'Open its menu', scope: 'mouse' }`

  Neither is a `workspace` row, so the layer's row↔command test is unchanged.

### D7. Styles (`styles/components.css`)
- **The surface.** `.menu` uses the toasts' surface, border and shadow tokens: `min-inline-size: 12rem`,
  `max-inline-size: calc(100vw - 16px)`, `overflow-y: auto`.
- **Items.** At least 28 px tall with a fine pointer and 44 px with a coarse one: an icon, the label, and the reason
  under it in muted text at 4.5:1 or more.
- **States.** The focused item has the focus ring and a tint. An unavailable item has a muted label and its reason in
  words, not colour alone.
- **Theme.** Light and dark come from the existing tokens.

## Research & Decisions

### Popover: manual, auto, or a dialog
**Context**: the menu must sit above the panes, open from a right-click, and close on a press outside it.
**Explored**:
- `popover="auto"`, with its light dismiss;
- `popover="manual"` with our own dismiss;
- a non-modal `<dialog>`;
- a fixed `div`.

**Decision**: manual (D3).
**Rationale**:
- On Linux and macOS, `contextmenu` fires on the button's press. HTML's light dismiss then hides every auto popover
  on the release, because the press came while no popover was open. An `auto` menu would close as the button comes
  up. Task 3.1 checks the manual one in both browsers.
- Manual also leaves `editor-shortcuts`' `#ws-keys` list open.
- A dialog has the wrong role.
- A fixed `div` stays under the toasts' top-layer region.

### Where the menu opens in this change
**Decision**: on the track only, not on today's chapter-list rows.
**Rationale**: `plain-clip-bin` replaces those rows next. Its rows also need the items an ignored or a missing clip
needs (Include, Remove), which no track block shows. Meanwhile the Clip tab and the bin's buttons keep every action.

### Cut and poster when the playhead is in another clip
**Explored**:
- (a) unavailable, with the Clip tab's reason;
- (b) a right-click moves the playhead to the pointer;
- (c) the items act at the pointer's time, seeking before the poster snapshot.

**Decision**: (a).
**Rationale**: (b) changes the picture just to show a menu. (c) is a second seek-then-snapshot path for one item
(`posterFrame.ts` reads the live `<video>`). A double-click already places the playhead, and the reason says so.

### Move to: flat items, a submenu, or none
**Decision**: flat items, each the existing end-of-chapter drop (`clip-drop`).
**Rationale**: it needs no new reducer action, undo label or announcement. A submenu would double the keyboard model
for events of two to four chapters. A long list scrolls inside the menu.

### Touch: the browser's long press or our own timer
**Decision**: the browser's `contextmenu` only.
**Rationale**: a timer of our own must tell a hold from a swipe that scrolls the track and from the trim handles'
touch drags, which makes a second gesture recogniser. Chrome on Android and Windows touch send `contextmenu` on a long
press. iOS Safari does not, and there the Clip tab keeps every item.

### Smaller choices
- **No `aria-haspopup` on the block.** It is a toggle button whose Enter and Space select the clip, and `aria-haspopup`
  would promise that pressing it opens a menu. It gets `aria-keyshortcuts` instead.
- **One lock note, not each control's words.** The Clip tab words a pending save four ways (`MOVE_LOCKED`,
  `UNAVAILABLE`, `WHY_LOCKED`, nothing for Rotate). Six items would say one thing four times.
- **No menu library.** Radix or Floating UI would be the first runtime dependency besides React and dnd-kit ("The
  dependency budget is explicit and small"), for one level and about 150 lines.

## Risks / Trade-offs

- **The Menu key on Windows fires `contextmenu` on keyup,** after the keydown has opened the menu. → It targets the
  focused item, and the menu swallows it.
- **Firefox always shows its own menu on Shift+right-click.** → Accepted: a page cannot override that.
- **A toast shown after the menu stacks above it** (both are manual popovers). → Accepted: toasts sit at the top of
  the viewer, and a press on one closes the menu.
- **Play moves the playhead while the menu is open.** → Reasons are taken again on a choice (D2).
- **`.tl-trims` takes pointer events only on its handles.** → `closest` from a handle still finds the clip. Task 2.1
  checks a right-click on a cut handle.

## Failure behaviour

Until an item is chosen, the menu is display and input only. A choice is a draft edit, the same as the Clip tab's,
and nothing is written or requested until Save. A refused choice changes nothing and says why. Nothing is rendered or
queued, so there is no partial file, re-run or restart to consider. Opening the menu again recomputes it from the
draft.
