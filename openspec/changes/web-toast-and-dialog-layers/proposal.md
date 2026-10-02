## Why

The toast layer (`web/src/ui/toast.ts`, `ToastRegion.tsx`) and the shared `Dialog` came out of
`web-design-system` and were hardened by the jobs/edit-mode rounds, and a bug triage of main (6a7fe16) found
four places where the layers still disagree with each other or with the spec:

- **An unread error can be lost to a lesser toast.** With three errors held, a fourth *info* toast drops the
  oldest error, so the operator never reads it. `show()` picks `held.find(non-error) ?? held[0]` and never
  looks at the new toast's tone (Principle I: a failure must not vanish silently).
- **A toast raised under a modal dialog is unseen and runs out.** `Dialog` uses `showModal()` (top layer,
  backdrop, everything else inert); `ToastRegion` is a plain `position: fixed` element below the backdrop. A
  job ending while "Render anyway?" or "Cancel this render?" is open raises a toast the operator cannot see,
  and a success/info toast's 5 s clock runs out behind the dialog.
- **A resting save bar leaves the toast on top of the last row.** The spec's "Notifications never cover the
  save bar" requirement concedes that, while the bar rests in the page (320 × 256 at 400 % zoom, 320 × 568), a
  notification MAY cover the controls just above it. Two gaps cause it: nothing reserves room between the
  last chapter and a resting bar, and `place()` only reruns on scroll, resize and the size of the bar or the
  region, not when content above the bar shifts it.
- **Escape then Save can pull focus back to the dialog's opener.** `Dialog`'s cleanup refocuses the opener
  unconditionally, so focus the operator has already moved (to Save) is yanked back within the same frame.

This is HLD §6 phase 8 (GUI v1) polish, bug-round follow-up. It depends on no open §8 research item and on
no other change: `web-shell-and-css-polish` and `web-edit-save-bar-polish` touch `shell.css` / `edit.css`
too, and are implemented after this one.

## What Changes

- **A toast never evicts a more important one.** At three held toasts, a new success or info toast is dropped
  when no non-error toast can make room; only a new error may displace the oldest error. The `ToastRegion`
  and `toast.ts` header comments say so.
- **Toasts stay on top of a modal dialog.** The region becomes a manual popover promoted into the top layer,
  and is promoted again each time a modal dialog opens, so it sits above the dialog and its backdrop. While a
  modal dialog is open, the success/info clocks are paused (and resume with the time they had left when the
  last dialog closes); an error stays until dismissed as always.
- **Toasts keep room above a resting save bar.** While toasts sit above the bar, the page reserves their
  height between the last chapter and a *resting* bar, and `place()` reruns when the layout above the bar
  moves it. The requirement's "MAY cover a control just above the bar" exception is removed.
- **Closing a dialog returns focus to its opener only when focus is still the dialog's.** Focus the operator
  has put elsewhere is left there.
- **Tests.** The pure parts get committed `node:test` unit tests (`toast.ts` store rules; the dialog's
  focus-return rule), run by a new `npm test` script under Node 22 with no new dependency. The browser
  behaviour (top layer, reserved room, Escape-then-Save) is checked with a Playwright pass from the session
  scratchpad, as for every earlier web change (never committed).
- **Spec:** `web-app` — "Notifications never cover the save bar" (MODIFIED) plus two ADDED requirements
  (what a full stack keeps; notifications under a dialog) and one ADDED requirement for a dialog's focus
  return.
- **Docs:** `web/README.md`'s Toasts paragraph (drops "a known gap … follow-up in `ui/`") and its `ui/` file
  list.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `web-app`: the toast stack's eviction rule, toasts over a modal dialog, toasts versus a resting save bar,
  and a dialog's focus return.

## Non-goals

- **No change to the Python service, `reel.yaml`, `config.yaml`, the API or `web/openapi.json`.** No Alembic
  migration, no rescan. Rendered output is unchanged for identical inputs, so `RENDER_GRAPH_VERSION` stays and
  the staleness fingerprint inputs are unchanged. Neither the CLI nor the API is touched (Principle V is not
  engaged).
- **No toast queue.** A dropped info/success toast is lost, as an evicted one already is; there is no
  backlog to replay.
- **Toasts are not made operable under a modal dialog** beyond what the platform gives (see design, Risks):
  the aim is that an error is *seen* while the dialog is open, and dismissible once it closes.
- **No change to the save bar's held/resting rule** (`placeBar`), to `--toast-inset-bottom`, or to the Save
  shortcut and the edit-verdict refresh (their own changes).
- **No new test framework** (no vitest, no jsdom, no committed Playwright).

## Impact

- Package: `web/` only (`src/ui/toast.ts`, `ui/ToastRegion.tsx`, `ui/Dialog.tsx`, a small new
  `ui/returnFocus.ts`, `styles/components.css`, `edit/edit.css`, `shell/shell.css` comment, `web/package.json`
  `test` script, `web/tsconfig.json` excludes `*.test.ts`, `web/README.md`).
- New dependencies: none (Node's built-in `node:test`; `--experimental-strip-types` on the `node:22` image).
- Browser support: the manual popover API (`popover="manual"`, `showPopover()`) is in every current browser;
  where absent the region stays the plain fixed element it is today.
