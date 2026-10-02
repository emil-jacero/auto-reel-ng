## Why

GUI v1 (HLD **§6 phase 8**, §4.10) puts the Save control after the whole editor: `SaveBar` is the last child
of `.event-editor` (`web/src/edit/EventEditor.tsx`), so a keyboard user who has edited the title and wants
to save tabs through every control of every clip row first. The triage measured 56 Tab stops on a 16-clip
event. That figure was not re-counted, and this change does not rely on it: the structure is enough. Each
row has its own stops (handle, Move up, Move down, Cuts, Watch, and more), the editor's only `tabIndex` is
`-1` on four headings and the save bar's alert, and no key handler for Save exists. Re-checked on main
f0b6ca3 (after both gates merged): `grep -rnE "ctrlKey|metaKey|KeyS|aria-keyshortcuts" web/src` finds only a modifier guard in
`EventList.tsx:101` (a link click), and the Dialog and cut-bar handlers do not touch S.

The supervisor decided on 2026-10-02 (bug round, item `save-is-56-tab-stops-from-title`): **Ctrl/Cmd+S in
Edit mode runs the same Save as the button, respecting the busy and aria-disabled rules, and is announced.**
The other options (a roving tabindex in the clip list, a "Skip to Save" link) are not taken: the shortcut is
additive and leaves each row's tab stops unchanged.

## What Changes

- **Ctrl+S (Cmd+S on a Mac) saves from anywhere on the page** while the editor holds the event's document
  (`web/src/edit/EventEditor.tsx`). One `keydown` listener on `document`, registered while the editor is
  ready, ignores Shift, Alt, key repeat and IME composition, and always calls `preventDefault()` for the
  key, so the browser's "Save page as" never opens over an editor.
- **It runs the same Save as the button**: the same `submit('save', 'save')`, so the same write body, the
  same etag, the same success toast and the same failure bar. It never clicks a DOM node, so it works when
  the bar is hidden or placed any way the `web-edit-save-bar-polish` gate chooses.
- **It respects what holds Save back.** The button's rule (`saveBlocked` in `SaveBar.tsx`: nothing to send,
  a date typed in part, a cut typed and not added, a conflict, a vanished event) moves into one exported
  function that the button and the shortcut both call, so they cannot drift. A save already in flight, a
  Move clips still pending, and an open dialog also stop it, silently.
- **It is announced.** Through the editor's one live region: "Saving…" when it saves, and the reason when it
  does not ("Nothing to save.", "Not saved: the date is incomplete.", and so on). A pointer press on Save
  announces nothing at its start today; the shortcut can start from a text field far from the bar, so it
  must say that it did something.
- **Save advertises it**: `aria-keyshortcuts="Control+S Meta+S"` and a tooltip "Save (Ctrl+S, or ⌘S on a
  Mac)". No visible text is added, so the bar's compact budget (web-app, "Edit mode's save bar stays
  compact and fits the window") is unchanged.
- **Spec and docs**: one ADDED web-app requirement with scenarios; a paragraph in `web/README.md`.

## Non-goals

- **No roving tabindex, no "Skip to Save" link** (supervisor decision). Each row's tab stops stay as they are.
- **No other shortcuts**, no shortcut help screen, and no shortcut outside Edit mode (the read view has
  nothing to save).
- **No change to what Save writes**, to the write API, to `reel.yaml` or to any failure's wording or choices.
  Overwrite with mine keeps its confirmation dialog; the shortcut never reaches it.
- **No new dependency, no web test framework.** `web/` has none (`package.json` has only `dev`, `build`,
  `check`); verification is `tsc`, the production build and Playwright in a real browser, from the
  scratchpad and never in the repo (the project's rule).
- **Not re-ordering the save bar in the DOM** (it would move it before the clip lists; not what was decided).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `web-app`:
  - ADDED `Requirement: Edit mode saves with Ctrl+S or Cmd+S`. It is an addition, not a rewrite: no existing
    requirement's text changes ("Saving an edit writes only what the operator changed" and "Edit mode's save
    bar stays compact and fits the window" already say what Save writes and when it is held back, and the new
    requirement points at them instead of restating).

## Impact

- **Packages:** `web/` only, plus `web/README.md`.
  - `src/edit/SaveBar.tsx`: an exported pure `saveHold(...)` (why Save cannot act now, or null); the button
    uses it, and gets `aria-keyshortcuts` and a `title`.
  - `src/edit/EventEditor.tsx`: the `keydown` effect, one announce per outcome. About 50 lines.
- **CLI vs API (Principle V):** untouched. This is client input handling; nothing moves into `api/`.
- **Rendered output:** unchanged. No `RENDER_GRAPH_VERSION` bump, and the staleness fingerprint inputs are
  unchanged.
- **Schemas:** no `reel.yaml`, `config.yaml` or API change, no Alembic migration, no rescan. `web/openapi.json`
  and `schema.d.ts` are untouched.
- **HLD:** no edit. A key binding is client behaviour inside D-10's visual system and lives in the web-app
  spec and `web/README.md`; no other decision depends on it. §6 phase 8's status is unchanged.
- **Dependencies:** none new (Principle VII).
- **Gates (both merged to main before this was implemented):**
  - `web-edit-save-bar-polish` mounts `SaveBar` from the start of Edit mode and hides it while clean (`shown`,
    stable `barRef`); it also changed `SaveBar.tsx`, `EventEditor.tsx` and `ClipOrderList.tsx`.
  - `web-playback-and-notices` keeps `MoviePanel` mounted (hidden) while Edit mode is open.
  - This change is built to be independent of both (design, "Gates"). Task 1.1 re-checked the names on main f0b6ca3.
- **Size (Principle VIII):** one package, one capability delta (one ADDED requirement), 8 tasks.
