## Why

GUI v1 (HLD **§6 phase 8**, §4.10) is feature-complete on main (`bca64f2`). Its shared UI layer
(`web/src/ui/`, **D-10**, change `web-design-system`, inside **D-8**'s budget) carries four accessibility
defects that every screen inherits. They were found by the final end-to-end pass and the a11y and
integration critics, and each one was reproduced again for this change, read-only, on the live server
(design, "Findings reproduced"):

- **Dismissing a toast from the keyboard drops focus to `<body>`.** The next Tab restarts at "Skip to
  content". An error toast never dismisses itself, so dismissing it is the only way to clear it, and every
  time a keyboard or screen-reader user does so they lose their place (WCAG 2.4.3).
- **Each new toast re-reads every toast still shown.** Both toast stacks are `role="status"` or
  `role="alert"` containers, which are implicitly `aria-atomic="true"` (the AX tree shows `atomic: true`).
  The same noise comes from the event page's missing-clip warning: it is an assertive `role="alert"`
  inserted on every read and every Refresh, although the page's render status already says it (WCAG 4.1.3).
- **Dialogs have no accessible description.** Focus goes straight to the safe button, so a screen-reader
  user hears only the title and "Cancel, button". The consequence text is never read. For "Overwrite the
  other change?" that text is the only place that says the overwrite also replaces chapters the operator
  did not touch.
- **The browser's UI color follows the OS, not the operator's choice.** With the OS dark and Light chosen,
  the active `theme-color` is `#0b0d11` over a light page, and the reverse also holds. The spec says the
  screens follow the operator's scheme once one is chosen, and the browser's own color is the one place
  that does not.

A fifth defect comes from where the toasts sit, and it is the one `edit-mode-polish` (P1) needs this layer
to fix. The toast region is lifted by `--toast-inset-bottom`, the save bar's height, which is only right
while the bar is stuck to the viewport bottom. At the end of the page the bar rests in flow, and a toast
lands on it. A held error toast then covers the focused Save and blocks pointer clicks on it (WCAG 2.4.11;
spec: "A focused control SHALL NOT be hidden behind anything that stays in place"). A page-side offset
alone cannot fix this: if the toasts simply follow the bar up, they cover the last clip rows at the end of
the page instead, as the probe measured.

## What Changes

- **Toasts keep keyboard focus.**
  - Dismissing a toast whose control has focus moves focus to the next toast's Dismiss, else to the
    previous toast's, else back to the control that had focus before focus entered the toasts, else to the
    page's `h1`. It never falls to `<body>`, and the move never scrolls the page (Chromium also focuses a
    button on a mouse click, so a pointer dismissal must not jump the page to the heading).
  - The same hand-off applies when a newer toast displaces a toast that holds focus.
  - Each Dismiss is described by its toast's message, so landing on one says which toast it clears.
- **Each announcement is made once.**
  - Both toast stacks get `aria-atomic="false"`, so only the added toast is spoken.
  - The event page's "reel.yaml lists clips that are not on disk" warning becomes `role="note"`. This is a
    one-attribute call site in `EventDetail.tsx`.
- **Toasts never cover the save bar, in either of its states.**
  - `ui/toast.ts` gains `keepToastsClearOf(bar)`, which registers the element toasts must avoid.
  - While a bar is registered, the region places itself live, on scroll, on resize and when either element
    resizes. It sits above the bar while the bar is stuck to the viewport bottom, and below the bar when the
    bar rests in flow with room below it (the page's end padding keeps that room for the toasts).
  - While a bar is registered and a toast is shown, the region also publishes `--toast-rise-h` (the toasts'
    height and gap), and `html`'s `scroll-padding-bottom` adds it: one term in `shell.css`. Toasts above a bar
    rise with it as it leaves the bottom edge, and without that term a control focused by Tab near the end of
    the page stops under them (measured in review: the last clip row at 390 px with two toasts).
  - With no bar registered, the region keeps today's `--toast-inset-bottom` rule.
  - `EventEditor` registers its save bar. This is two lines in its existing bar effect (P1's file) and the
    only call site.
  - `--toast-inset-bottom` stays P1's, the bar's height as today, and it still feeds `scroll-padding-bottom`.
  - Limit: when the toasts and the bar do not fit the window twice over (two toasts at 320 × 700, three at
    phone width), the bar stays clear, but a focused control can sit under the toasts while the bar rises.
    A `position: fixed` save bar (P1's layout) has no such limit and needs none of the placement code above.
    The review measured it cleaner in every case, and it is raised to the supervisor (design, "Also
    considered").
- **Every dialog states its consequence.** `Dialog` takes a required `description`. It renders that text
  under the title and names it in `aria-describedby`. The four call sites (two in `EventEditor.tsx`, two in
  `RenderControl.tsx`) move their body paragraph into the prop, with no visible change.
- **The browser's UI color follows the scheme in effect.**
  - `applyThemeChoice` and the `index.html` pre-paint script set both `theme-color` metas to the chosen
    scheme's page background.
  - System restores each meta's own color.
- **Docs:** the Dialogs and Toasts bullets of `web/README.md` ("Design system").

## Non-goals

- **The save bar itself** (its height at phone width, its buttons, the 320 px conflict alert, focus after a
  keyboard drop) is `edit-mode-polish`'s. This change supplies only the region side of the toast contract,
  and the one registration call.
- **Toasts raised while a modal dialog is open.** They sit under the backdrop, are inert, and a success
  toast's 5 s clock runs out unseen. This integration-critic finding was not assigned to any section of
  this round. It needs the region in the top layer (for example as a popover), which is a design decision
  of its own. It is raised as an open question, not fixed here.
- **Touch-target sizes at phone width** (theme control, segmented filter, compact Render, back link). This
  design-critic finding is unassigned, and those rules live in `shell.css`, `components.css` and screen
  CSS owned by other changes.
- **Toast wording** (event titles instead of folders, "Saved" naming its event) and **list-row enqueue
  announcements** belong to `jobs-live-polish` (P2) and `edit-mode-polish` (P1).
- **No change to toast timing, the three-toast cap, the tones, or where toasts appear when no bar is
  registered.** The existing rule that focus inside the toasts pauses their clocks also covers focus that a
  dismissal hands to another toast (design, Risks).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `web-app`: four ADDED requirements and one MODIFIED requirement.
  - added `Requirement: The screens announce each change once`
  - added `Requirement: Dismissing a notification keeps keyboard focus`
  - added `Requirement: Notifications never cover the save bar`
  - added `Requirement: A confirmation dialog states its consequence`
  - modified `Requirement: Every page shares one header and follows the operator's color scheme`: the
    browser's own interface color follows the scheme in effect, from the first paint. The block is re-based
    on the current spec text at the gate (task 1.1).

## Impact

- **Packages:** `web/` only.
  - Owned: `src/ui/ToastRegion.tsx`, `src/ui/toast.ts`, `src/ui/Dialog.tsx`, the toast rules of
    `src/styles/components.css`, `src/shell/theme.ts` and `index.html`.
  - Call sites in other changes' files, localized and declared in design ("Files and parallel changes"):
    - `src/edit/EventEditor.tsx`: two Dialog bodies move into `description`, and two lines register the
      save bar (P1).
    - `src/jobs/RenderControl.tsx`: two Dialog bodies move into `description` (P2).
    - `src/events/EventDetail.tsx`: one `role="note"` (P4).
    - `src/shell/shell.css` (no owner this round): one `--toast-rise-h` term in `scroll-padding-bottom`.
  - `web/README.md`.
- **CLI vs API (Principle V):** neither is touched. This is presentation only.
- **Rendered output:** unchanged. **No `RENDER_GRAPH_VERSION` bump**, and the fingerprint inputs are
  unchanged.
- **Schemas:** no `reel.yaml`, `config.yaml` or API change, **no Alembic migration**, and no rescan.
  `web/openapi.json` and `schema.d.ts` are untouched.
- **Dependencies:**
  - **Gates:** none. The change builds on main `bca64f2`.
  - **Parallel changes:** it runs in parallel with `edit-mode-polish`, `jobs-live-polish`,
    `event-list-polish` and `event-page-polish`. Whichever lands second rebases (design, "Files and parallel
    changes").
  - **New runtime dependencies:** none (D-8's budget is unchanged).
- **Size (Principle VIII):** one package, one capability delta and 9 tasks.
