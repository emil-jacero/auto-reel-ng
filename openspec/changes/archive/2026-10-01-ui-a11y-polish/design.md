## Context

See proposal.md for the problem. The code this change edits, on main `bca64f2`:

- **`web/src/ui/ToastRegion.tsx` (145 lines).**
  - The region renders two always-present stacks: `<div role="alert" className="toast-stack">` for errors and
    `<div role="status" className="toast-stack">` for the rest.
  - `ToastItem`'s Dismiss (`btn btn-ghost btn-icon toast-dismiss`, named by `<Icon name="x" label="Dismiss" />`)
    calls `dismissToast(id)` and does nothing with focus. The comment at lines 86-87 says that the focused
    button leaves with its toast and that no blur fires. The second half is wrong in current Chromium: the
    review measured `blur` and `focusout` (null `relatedTarget`) on removal ("Keyboard dismiss"). Task 2.1
    corrects the comment; the effect it explains stays.
  - The region's `onFocus`/`onBlur` and a document `pointerover`/`pointerout` pair drive `pauseToasts`.
  - A `ResizeObserver` publishes the region's height as `--toast-region-h` on `<html>`.
- **`web/src/ui/toast.ts`.** A module store with `toast.success|info|error`, `dismissToast`, `pauseToasts` and
  `useToasts` (`useSyncExternalStore`). At most three toasts are held: a fourth drops the oldest non-error
  toast, or the oldest when all three are errors.
- **`web/src/styles/components.css:738-827`, the toast rules.** `.toast-region` is fixed at
  `inset-block-end: calc(var(--toast-inset-bottom, 0px) + var(--s-4))`.
- **The P1 side of today's contract** (read, not owned):
  - `EventEditor.tsx:521-535` publishes `--toast-inset-bottom = bar.offsetHeight` on `<html>` while the save
    bar shows. The bar is `.save-bar`: sticky at `inset-block-end: 0`, transparent, with the card at its top
    and a `--s-4` bottom padding.
  - `shell.css` puts `scroll-padding-bottom: calc(var(--toast-inset-bottom, 0px) + var(--toast-region-h, 0px) + var(--s-4))`
    on `html`, and bottom padding `calc(var(--s-7) + var(--toast-region-h, 0px))` on `.page`.
- **`web/src/ui/Dialog.tsx`.**
  - `<dialog aria-labelledby={titleId}>`, then an `h2` title, then `children`.
  - There are four call sites, each passing `<p>consequence</p>` and then a `.dialog-actions` row:
    `EventEditor.tsx:811` ("Discard unsaved changes?") and `:834` ("Overwrite the other change?"), and
    `RenderControl.tsx:420` ("Render anyway?") and `:450` ("Cancel this render?").
  - `.dialog p` is already styled muted (`components.css`), so a paragraph the component renders itself looks
    the same.
- **`web/src/shell/theme.ts` and `web/index.html`.**
  - `applyThemeChoice` sets or removes `data-theme` and stores the choice.
  - `index.html` holds `<meta name="theme-color" media="(prefers-color-scheme: light)" content="#f9fafc">`, a
    dark twin `#0b0d11`, and an inline pre-paint script that applies the stored `data-theme`.
  - The two hex values are exactly `--bg`'s sRGB: `oklch(98.5% 0.003 260)` → `#f9fafc` and
    `oklch(16% 0.008 260)` → `#0b0d11`, computed for this design.
- **`web/src/ui/Alert.tsx`** takes `role?: 'alert' | 'status' | 'note'`, with `alert` as the default.
  `EventDetail.tsx:376` renders the missing-clip warning with the default.

## Goals / Non-Goals

**Goals:**

- Fix the five P5 findings inside the owned files (proposal, Impact), and the touch-target finding the
  supervisor added.
- Keep every other change's files at call-site edits only.
- Give P1 a toast placement contract that holds whichever change lands first.

**Non-Goals:**

- No new component, no dependency, and no visual change except where the toasts sit relative to the save bar,
  and, under a coarse pointer only, the segmented options' width and the back link's height. Dialogs, toasts
  and the missing-clip warning look exactly as before.
- No change to toast lifetime, the cap, pause-on-hover/focus, or the busy-control rule.

## Research & Decisions

### Supervisor decisions (before implementation)

These bind the implementation and supersede the sections below where they differ. Each section they touch
says so.

- **Polish round context.** The brief is `plan/brief-polish.md`, file ownership included. Five sibling changes
  run in parallel: `edit-mode-polish` (P1), `jobs-live-polish` (P2), `event-list-polish` (P3),
  `event-page-polish` (P4) and `serve-clean-exit` (P6). This change (P5) stays in its own files plus the call
  sites named in "Files and parallel changes". README hunks: whichever change lands second rebases and keeps
  every side.
- **The save bar stays sticky. No `position: fixed`.** The "fixed bar" alternative ("Also considered") is
  rejected. Toast placement is this change's "switch sides" rule plus the rise term. `edit-mode-polish` lands
  **after** this change. It keeps publishing `--toast-inset-bottom` as the bar's height (not a live band), and
  it keeps the two registration lines this change adds to its bar effect. The contract is written out in full
  in "The contract with `edit-mode-polish`, as decided".
- **The one-term `shell.css` edit is accepted:** `+ var(--toast-rise-h, 0px)` in `html`'s
  `scroll-padding-bottom`.
- **Dialog descriptions: no required prop.** `Dialog` describes itself. Its body gets a wrapper with a
  generated id, and `aria-describedby` points at that wrapper. Callers stay unchanged, so every existing and
  future dialog has its consequence read. This replaces "Dialog description: a required prop" (see "Dialog
  description: the body describes the dialog").
- **Touch targets at phone width are taken here.** One `@media (pointer: coarse)` rule set across `shell.css`
  and `components.css`, with `detail.css`'s `.back-link` as a one-line exception, brings the interactive
  targets to hit areas of at least 44 × 44 px. Density under a fine pointer does not change. The finding
  leaves "Unassigned findings" (see "Touch targets under a coarse pointer").
- **Toasts under an open modal dialog** (inert, unseen) stay a follow-up, not this change.

### Supervisor decisions (after implementation)

These answer the questions the implementation report raised. None of them changes code.

- **The theme options at 28 × 44 px below 24rem are accepted.** A 320 px header has no width to give them
  (measured). From 384 px up they are 44 × 44 ("Touch targets under a coarse pointer"). (Changed in review:
  below 26rem, so 44 × 44 from 416 px up. See "Changed during review".)
- **The spec's focus sentence keeps its scope:** one toast, or two in a window at least 844 px tall. Two
  toasts at 320 × 700 and three at phone widths stay known limits ("Known limit: a stack too tall for the
  window", Risks).
- **Two comments in `edit-mode-polish`'s files are left to it.** The `edit.css` save-bar block and the comment
  above `EventEditor`'s bar effect still say that the toast region reads `--toast-inset-bottom` to sit above
  the bar. With the bar registered, the region sets its own `--toast-offset` instead, and the property only
  feeds the scroll padding. P1 lands after this change and updates both comments with its own edits to
  those lines.
- **The proposal commit's message is fixed on the PR branch.** On the feat branch, its body runs into its
  subject. The PR branch cherry-picks it with an edited message, as a new commit. No history is rewritten.

### Findings reproduced

**Context**: The brief requires every finding to be reproduced before its fix is designed. The minor ones
(atomic stacks, dialog description, theme-color) had not been adversarially verified.

**Explored**: This change's own probe, read-only against `http://127.0.0.1:8114/` (main `bca64f2`).
Chromium was run from `mcr.microsoft.com/playwright/python:v1.49.0-noble` with `--network host`.
- Every non-GET request was intercepted: `POST /api/v1/jobs` got a mocked 409 `output_collision`, to raise
  error toasts, and everything else was aborted. The log shows only those 10 mocked POSTs.
- One GET detail was patched in the browser to add a missing clip.
- Script, log and shots are in `<scratchpad>/polish-spec/ui-a11y-polish/` (`probe.py`, `logs/probe.log`,
  `shots/`).

| Finding | Result |
|---|---|
| Keyboard dismiss drops focus | **Reproduced.** At 1280 and 390 with one toast, after Enter on Dismiss `activeElement` is `BODY`, and the next Tab lands on "Skip to content". With two toasts it is also `BODY`. |
| Toast stacks are atomic | **Reproduced.** The CDP AX tree gives the alert stack `live: assertive, atomic: true` and the status stack `live: polite, atomic: true`. No `aria-atomic` attribute is set. After two toasts the alert stack's text is both messages plus "Open" twice. |
| Missing-clip warning is an alert (same finding) | **Reproduced.** `2024-08-20 - Två kapitel - Tjörn` was used, with `gammal.mp4` added as missing through the patched GET, because the live library no longer has Sommarlov's missing clip. A `role="alert"` node carrying "reel.yaml lists clips that are not on disk gammal.mp4" is inserted when the page opens, and inserted again on Refresh. The page's `role="status"` render status already says "gammal.mp4 is missing from disk. Restore it, or remove it in Edit mode." |
| Dialogs have no description | **Reproduced.** "Render anyway?" (Midsommar 2023) and "Discard unsaved changes?" (Grillning) have an AX name and a null description, with no `aria-describedby`. Focus is on Cancel and Keep editing. |
| theme-color follows the OS | **Reproduced.** With OS light and Dark chosen, the matching meta is `#f9fafc` over a body of `oklch(0.16 …)`. With OS dark and Light chosen, it is `#0b0d11` over `oklch(0.985 …)`. All four System and matching cases are correct. |
| Toasts cover the save bar (P1's finding, P5's side) | **Reproduced.** With one error toast at the page end, the toast overlaps the save-bar card and covers Reset and Save: Grillning at 1280×900 and 390×844, and the Omöjligt datum fix form at 390×844 and 320×700. With the page at its top (bar stuck), nothing overlaps. |

**Decision**: None of the five P5 findings is dropped. Two details in the critics' reports were wrong and
change nothing:
- the cited `ToastRegion.tsx` line numbers (the Dismiss is at 26-32)
- the claim that `components.css:23-24` is a general "never drop focus to body" rule (it is the busy-control
  rule)

**Rationale**: Each finding reproduced on current main with the critic's own mechanism.

An adversarial review then probed the proposed fixes the same way, read-only (only mocked `POST /jobs`
answers; no other write left the browser), with scripts and logs in
`<scratchpad>/polish-spec/ui-a11y-polish/review/`. It found two defects in the first draft, both fixed below:
the "switch sides" placement left a keyboard-focused control under the toasts while the bar rises ("Where
toasts sit", review table), and the focus hand-off would scroll the page on a mouse dismissal in Chromium
("Keyboard dismiss").

### Keyboard dismiss: where focus goes

**Context**: Removing the focused Dismiss leaves focus on `<body>`. Error toasts never time out, so a keyboard
user has to dismiss them.

**Explored**:
- Returning focus straight to the page control the user came from.
- Focusing the page `h1` every time.
- The pattern React Aria's toast region uses (Adobe's `useToastRegion`): after a close, focus moves to
  another toast when one remains, else it is restored to the element that had focus before the region.
- Removing an item from a list, where focus goes to the next item, else the previous one.

**Decision**: When a toast is dismissed while focus is inside the region, focus MUST move to the first
candidate that actually takes it, in this order:
1. the next toast's Dismiss, in DOM order across both stacks
2. the previous toast's Dismiss
3. `returnTo`, the element that lost focus when focus entered the region, if it is still connected and outside
   the region
4. `main:not([hidden]) h1`, the selector `AppShell`'s `focusPageHeading` uses. It is repeated here because
   `ui/` must not import `shell/`: `AppShell` imports `ToastRegion`.

"Takes it" means that after `.focus({ preventScroll: true })`, `document.activeElement` is that element. That
skips an element in a hidden `<main>`, or one that became `disabled`. Focus moves before `dismissToast(id)`, so
it is never on a removed node.

Every candidate is focused with **`preventScroll: true`**, as EventEditor's Reset already focuses the heading
"in place". This matters because the trigger is "focus is inside the region", and Chromium focuses a button on
a mouse click (review probe: a mouse click on a button reports `detail: 1` with that button already
`activeElement`; Enter and Space report `detail: 0`). A pointer dismissal in Chromium or Firefox therefore runs
the hand-off too. A plain `focus()` on `returnTo` or the `h1` would then scroll the page to a control far above,
or to its top, on a mouse click. With `preventScroll` the hand-off is invisible to a pointer user: no scroll,
and normally no focus ring, because a script focus that follows a mouse click does not match
`:focus-visible`. The trigger stays "focus inside the region", not "keyboard only" (`detail === 0`), so
assistive technology that activates the button with a synthesized pointer click is covered as well.

A toast removed for another reason while it holds focus is handled by one `useLayoutEffect` on `toasts`. In
practice the reason is a fourth toast displacing it. The region remembers `lastFocused`, the last element
inside it to receive focus. When that element is disconnected and `activeElement` is `<body>` or null, focus
moves to the first remaining `.toast-dismiss`, else `returnTo`, else the `h1`, by the same `focusFirst`.

The record has to tell "focus was in the region when the toast went" from "the operator clicked elsewhere
since". A `focusout` cannot: the review probe measured that Chromium **does** fire `blur` and `focusout` when a
focused button is removed, with a null `relatedTarget` and the target still connected while the event runs.
That is the same signature as a click on the page background. So:
- `lastFocused` is cleared by a `focusin` outside the region (a document listener) and by a `pointerdown`
  outside it (the existing document pointer listeners are the place). It is never cleared by a `focusout`.
  (Changed in review: a `pointerdown` no longer clears it, because a touch scroll fires one without moving
  focus. A `focusout` from inside the region does, decided in a microtask: only when its node is still
  connected and focus is outside the region. See "Changed during review".)
- `returnTo` is set on every entry into the region from outside it: to the `relatedTarget` when that is an
  element outside the region, and to `null` when focus came from nowhere (`relatedTarget` null). A stale
  control from an earlier visit is never restored.

Each Dismiss gets `aria-describedby` pointing at its message (`useId` in `ToastItem`). A screen-reader user who
lands on the next toast's Dismiss then hears which toast it clears, not only "Dismiss, button".

```tsx
// ToastRegion.tsx (sketch)
const returnTo = useRef<HTMLElement | null>(null)
const lastFocused = useRef<HTMLElement | null>(null)

function focusFirst(candidates: readonly (HTMLElement | null | undefined)[]): void {
  for (const target of candidates) {
    if (target == null || !target.isConnected) continue
    target.focus({ preventScroll: true })
    if (document.activeElement === target) return
  }
}
const pageHeading = () => document.querySelector<HTMLElement>('main:not([hidden]) h1')

const dismiss = (id: number, button: HTMLElement) => {
  const region = regionRef.current
  if (region !== null && region.contains(document.activeElement)) {
    const buttons = [...region.querySelectorAll<HTMLElement>('.toast-dismiss')]
    const at = buttons.indexOf(button)
    const back = returnTo.current !== null && !region.contains(returnTo.current) ? returnTo.current : null
    focusFirst([buttons[at + 1], buttons[at - 1], back, pageHeading()])
  }
  dismissToast(id)
}
// onFocus (focusin): lastFocused = target. Entering from outside the region:
//   returnTo = relatedTarget instanceof HTMLElement && !region.contains(relatedTarget) ? relatedTarget : null
// document focusin outside the region, or pointerdown outside it: lastFocused = null.
// No focusout clears lastFocused (Chromium fires one, relatedTarget null, when the focused node is removed).
```

**Rationale**:
- Focus stays in the place the user was working, which is the toasts, while there are more to clear. It goes
  back to where they came from once there are none.
- A pointer dismissal with focus elsewhere (Safari, which does not focus buttons on click) does not steal
  focus, because the region does not contain `activeElement`. A pointer dismissal in Chromium moves focus
  without scrolling, so nothing visible changes.
- The "takes it" check makes the order robust without special cases.
- The review spiked the order on the live list with a capture-phase emulation of `dismiss`
  (`review/handoff.py`): Enter on the first of two Dismiss buttons landed on the second; Enter again landed on
  the list's last event link, where focus had come from; from `<body>` it landed on the `h1` "Events". A mouse
  dismissal from halfway down the 390 px list kept `scrollY` at 705 with `preventScroll`, and jumped to 0
  without it.

### Announce once

**Context**: `role="status"` and `role="alert"` imply `aria-atomic="true"` (WAI-ARIA 1.2), so each addition
re-speaks the whole stack.

**Explored**:
- `aria-atomic="false"` on each stack.
- Swapping the roles for bare `aria-live` containers, as Sonner does (`aria-live="polite"` plus
  `aria-atomic="false"` on its container).
- A separate announcer that speaks each toast once (Radix).

**Decision**: Keep the stacks and their roles, as C1's design sets them. Both stacks MUST carry
`aria-atomic="false"`. `aria-relevant` stays at its default, `additions text`, so a removal is silent.

The missing-clip warning at `EventDetail.tsx:376` gets `role="note"`. `Alert` already offers that role, and
`RenderControl` uses it for "Why the render failed". It is one attribute at P4's call site. `Alert`'s default
stays `alert`, which is right for a failure that replaces the content.

**Rationale**: An explicit `aria-atomic` overrides the implied value (the AX tree shows it), with no change
to C1's roles or the "always present" rule that makes the first toast announce. The render status
(`role="status"`, announced when it changes) already carries the missing-clip fact, so the warning is
redundant as a live region.

### Where toasts sit relative to the save bar (the contract with `edit-mode-polish`)

**Context**: The region's offset is the save bar's height, which is correct only while the bar is stuck to
the viewport's bottom edge. When the page is scrolled to its end, the sticky bar rests in flow above
`.page`'s bottom padding (`--s-7 + --toast-region-h`). That lifts it by 48 px plus the toasts' height, and
puts it right under the toasts. Where `B` is the bar's height and `R` the region's, toasts and bar overlap
whenever `B > 32 px`.

**Explored**: Three placement rules, prototyped by injecting each into the live page (probe, "F"). Each was
measured with one error toast, at the page's top (bar stuck) and at its end (bar in flow). "Covered" counts
the focusable controls in `main:not([hidden])` that intersect a toast.

| Rule | Grillning 1280×900, end | Grillning 390×844, end | Fix form 390 / 320, end | Any case, top |
|---|---|---|---|---|
| current: offset = `B` | overlaps the card; Reset and Save covered | overlaps; Reset and Save covered | overlaps; Reset and Save covered | above the bar, no overlap |
| follow: offset = `H - bar.top` | clear of the card, but 4 Move buttons covered | Reorder and Move of the last clip covered | the description textarea covered | same as current |
| **switch sides** | toast below the bar (787-884 vs card 671-739), nothing covered | below (731-828 vs card 571-683), nothing covered | below, nothing covered | same as current |

The chosen rule, implemented as sketched below (the region's own live offset, the gap read back rather than
hard-coded), was also swept from scroll 0 to the end in 8 px steps (`sweep.py`, `logs/sweep.log`).
- Cases: Grillning at 1280×900 and 390×844, and the fix form at 390×844 and 320×700, each with one and with
  two error toasts. That is 570 scroll positions.
- Overlaps between a toast and the save-bar card: **0**.
- The read-back gap: 16 px (`--s-4`) in every case.

"Follow" is the critics' first suggestion. It clears the bar but moves the problem: at the end of the page
the toasts are glued to the bar, and the bar is glued to the last content, so the last clip rows sit under the
toasts and cannot be scrolled clear. That breaks the spec's focused-control rule in another place.

**Review: keyboard focus while the bar rises.** The sweep above checked toasts against the card only, and
controls only at the page end. Between "stuck" and "room below", "switch sides" behaves like "follow": the
toasts ride up with the bar. `html`'s `scroll-padding-bottom` (`--toast-inset-bottom + --toast-region-h +
--s-4`) assumes the toasts sit at the stuck height, so a Tab that scrolls a control near the end into view can
stop in that band with the control under a toast. That would break an existing requirement ("A focused control
SHALL NOT be hidden behind anything that stays in place"). The review probe (`review/tabcover*.py`,
`review/tabstress.py`, `review/fixedbar.py`, logs in `review/logs/`) walked Tab from Title to Save with the
rule injected, and counted focused controls that a toast overlaps by more than 1 px. The same script also
swept every scroll position in 8 px steps (toast over the save-bar card; a toast past the window's top) and
checked the controls at the page end. Cases: Grillning at 1280×900 (1–3 toasts), 768×1024 (2), 390×844 (1–3)
and 320×700 (2–3); the fix form at 390×844 (1–2) and 320×700 (1–3). That is 13 cases per variant
(`review/matrix.py`, `logs/matrix.log`; four more for the chosen rule in `logs/matrix_extra.log`).

| Variant | Toast over the card | Toasts past the window top | Focused controls under a toast in the Tab walk |
|---|---|---|---|
| main today (offset `B`) | every case | none | Reset and Save in every case; the description textarea in 5 cases |
| switch sides alone | none | 3 toasts at 320×700 | 1 toast: the fix form's textarea (390, 320). 2 toasts: the last clip row's Reorder and Move (390, 320), the fix form's date and textarea (390, 320). 3 toasts: 6–9 controls, also at 1280 |
| switch + P1's live inset (`H - bar.top`) | none | 3 toasts at 320×700 | 1 toast: the fix form's textarea at 390. 2 toasts: one row at 320, the fix form's date at 320. 3 toasts at 390/320: 3–7 |
| **switch + rise term (chosen)** | none | 3 toasts at 320×700 | 1 toast: none (also 768 and 320). 2 toasts: none at 1280, 768 and 390; the fix form's date at 320×700. 3 toasts: none at 1280; 3–6 at 390/320 |
| fixed bar, today's offset `B` (alternative) | none | none | the description textarea in the same 5 cases as main, nothing else |

In the textarea cases of main and the fixed bar, the focus scroll leaves part of the 88 px description field
under the toast. They happen on main today, in the same five cases, and are not this change's.

The geometry explains it. While the toasts sit above a bar that has left the bottom edge, a control less than
`R + gap` above the bar is under them at every scroll position of that band; only scrolling on into "below"
uncovers it. The browser's focus scroll computes once, from the padding in force before it scrolls, so the
padding has to reach that far from the start: one more `R + gap` while a bar is registered.

**Decision (amended by the review)**: The region MUST also publish `--toast-rise-h` on `<html>`: `R + gap` in
px while a bar is registered and the region holds a toast, removed otherwise. `shell.css` adds it to `html`'s
`scroll-padding-bottom`, one term, a call site declared below:

```css
/* shell.css: the toasts above a registered bar rise with it as it leaves the bottom edge (ToastRegion) */
scroll-padding-bottom: calc(
  var(--toast-inset-bottom, 0px) + var(--toast-region-h, 0px) + var(--toast-rise-h, 0px) + var(--s-4)
);
```

It is static, not live: a live padding (P1's proposed `H - bar.top` inset) is right only after the scroll it
is meant to steer. It leaves a clip row covered at 320 × 700 with two toasts, and the fix form's textarea at
390 with one, where the static term leaves none. The cost is a focused control kept `R + gap` higher than
strictly needed while the bar is stuck and toasts are shown.

**Known limit: a stack too tall for the window.** The rule needs `B + 2 (R + gap)` plus the focused control
to fit below the header. With two toasts at 320 × 700 (the fix form's date field), and with three toasts at
390 or 320 wide, it does not: the bar stays clear (no card overlap in any case), but while the bar rises a
focused control can sit under the stack, and with three toasts at 320 × 700 the stack passes the window's top.
Scrolling on to the end, or dismissing a toast, resolves it. The spec's focus sentence is scoped to what was
measured clean: one toast, or two in a window at least 844 px tall. A fixed bar has no such limit (last row of
the table).

Also considered:
- **Make the bar `position: fixed`, so it never rests in flow** (measured by the review, `review/fixedbar.py`
  and `matrix.py`: `.save-bar` fixed to the window's bottom in the page column, and `.page`'s end padding
  adding `--toast-inset-bottom`). Today's offset `B` is then right everywhere: no card overlap, nothing past
  the window's top, no control covered at the end, and Tab walks as clean as main's apart from the save bar,
  in all 13 cases up to three toasts at 320 × 700. It needs no registration, scroll listener or rise term, so it
  is the simpler contract (Principle VII), and the more robust one. It is P1's layout decision (`edit.css`,
  plus the end padding), and it changes the look on a short page: the bar sits at the window's bottom rather
  than under the form. Raised to the supervisor, who **rejected it**: the bar stays sticky (Supervisor
  decisions). Task 2.2's placement code and the rise term stay.
- **Move toasts to the top while a bar shows.** They would cover the page heading and the Edit or Stop
  editing controls, and jump across the screen on entering Edit mode.

**Decision**: The "switch sides" rule, owned by the region, plus the rise term above. A page registers the one
element toasts must stay clear of:

```ts
// ui/toast.ts
/**
 * Keep toasts clear of `bar`, an element held at the viewport's bottom edge
 * (position: sticky; inset-block-end: 0) whose box top is where its visible part
 * starts, until the returned function is called. One bar at a time: a later call
 * replaces an earlier one, and a release clears only its own registration.
 */
export function keepToastsClearOf(bar: HTMLElement): () => void
// internal, for ToastRegion: useToastClearance(): HTMLElement | null  (useSyncExternalStore)
```

While a bar is registered, `ToastRegion` places itself in a `useLayoutEffect` keyed on the bar. It
listens to window `scroll` (passive), window `resize`, and a `ResizeObserver` on both the bar and the region.
It sets `--toast-offset` inline on the region, and `--toast-rise-h` on `<html>`:

- `viewport = document.documentElement.clientHeight`; `box = bar.getBoundingClientRect()`
- `gap` is the region's own base gap, `--s-4`. It is read back as
  `viewport - region.getBoundingClientRect().bottom - appliedOffset`, so TS holds no px literal. The effect
  sets `--toast-offset: 0px` before its first measurement, so `appliedOffset` is always known.
- **Below:** when `viewport - box.bottom >= region.offsetHeight + gap`, the offset is 0. The bar has moved up
  far enough that the toasts fit in the room under it. At the page end, `.page`'s bottom padding
  (`--s-7 + --toast-region-h`) always leaves that room.
- **Above:** otherwise the offset is `max(0, ceil(viewport - box.top))`, so the toasts' bottom is one gap
  above the bar's top. While the bar is stuck, this equals `B`, which is today's value.
- **Rise:** `--toast-rise-h` is `region.offsetHeight + gap` px while the region is not empty, and is removed
  when it is empty. Both properties are written only when their value changes, and removed on cleanup.

```css
/* components.css, the toast rules (P5) */
.toast-region {
  /* A registered bar (keepToastsClearOf): the region's own live offset. Otherwise the page's inset. */
  inset-block-end: calc(var(--toast-offset, var(--toast-inset-bottom, 0px)) + var(--s-4));
}
```

The contract with `edit-mode-polish` (P1). It is stated here because the two changes are written in parallel.

| | This change (P5, `ui/`) | `edit-mode-polish` (P1, `edit/`) |
|---|---|---|
| Toast placement | Owns it: the rule above, the CSS, and the fallback to `--toast-inset-bottom` when nothing is registered | MUST NOT position toasts |
| Registration | Adds two lines in EventEditor's existing bar layout effect (`const release = keepToastsClearOf(bar)` after `publish()`, and `release()` in its cleanup). This is the only call site, declared here as a call-site edit in P1's file. | Owns the effect, and keeps the call if it restructures the effect |
| `--toast-inset-bottom` | Stops reading it for placement while a bar is registered, and keeps it as the fallback | Owns what it publishes: the bar's height, as today. It feeds `html`'s `scroll-padding-bottom`, so a focused row scrolls clear of the stuck bar. A live `H - bar.top` band, as P1's proposal plans, is not needed with the rise term (and alone it is "follow"; see the table). |
| Scroll padding | Publishes `--toast-rise-h` and adds that one term to `shell.css`'s `scroll-padding-bottom` | Keeps the inset term; does not add a toast term |
| Bar element | Needs the element whose box top is the bar's visible top edge, and which is held at the viewport bottom while stuck | `.save-bar` today (transparent, card at its top). If P1 moves the alert out of the bar or makes the bar `position: fixed`, the rule still holds: a fixed bar never has room below it, so the toasts stay above it. |
| Spec | Owns "Notifications never cover the save bar" | Does not restate it. P1's own requirements (bar size, alert fit, drop focus) are separate. |

Merge order does not matter:
- If P5 lands first, the region reads the fallback until the registration is there. P5 adds the registration
  itself.
- If P1 lands first with a different publish, for example the live `H - bar.top` its proposal describes, the
  region ignores it for placement once the bar is registered, and P5's rebase re-applies the two lines in
  P1's reshaped effect. The scroll padding then holds both terms, which only adds margin.

**The contract with `edit-mode-polish`, as decided.** The supervisor fixed the order: P5 lands first, P1
second, on top of it. The table above holds with these exact terms, which P1's implementation MUST keep:

1. **Placement is P5's.** `ToastRegion`, `ui/toast.ts` and the `.toast-region` rules in `components.css`
   decide where toasts sit. P1 MUST NOT position toasts, add a margin for them above the bar, or set
   `--toast-offset` or `--toast-rise-h`.
2. **`--toast-inset-bottom` is P1's, and it is the bar's height.** EventEditor's bar layout effect publishes
   `${bar.offsetHeight}px` on `<html>` while the bar shows (the card plus its `--s-4` foot), follows it with a
   `ResizeObserver`, and removes it in the cleanup. This is exactly what `bca64f2` does. It is **not** the live
   band `max(0, ceil(clientHeight - bar.top))` that P1's design proposes. With the rise term the band is not
   needed, and the static height keeps `scroll-padding-bottom` steady while the page scrolls.
3. **The registration lines stay in that effect.** After `publish()` comes
   `const release = keepToastsClearOf(bar)`, and the cleanup calls `release()` (with the import from
   `../ui/toast`). The element passed is the `.save-bar` element (`barRef.current`): sticky,
   `inset-block-end: 0`, with the card at its top, so its box top is the bar's visible top edge. If P1
   restructures the effect, the two lines move with it. They run in the same commit that shows the bar, and
   release in the cleanup that hides it or unmounts the editor.
4. **What the region does with them.** While the bar is registered, the region ignores
   `--toast-inset-bottom` for placement and uses its own `--toast-offset`, which is "above" or "below" by the
   rule above. It publishes `--toast-rise-h` while it holds a toast. With nothing registered (no bar, or
   another page), `--toast-inset-bottom` (default 0) places the region as on `bca64f2`.
5. **Scroll padding is shared.** `shell.css` sets `html`'s `scroll-padding-bottom` to
   `--toast-inset-bottom + --toast-region-h + --toast-rise-h + --s-4`. P1 MUST NOT override it in `edit.css`
   (none does today, and `edit.css` says so), and adds no toast term of its own.
6. **The requirement is P5's.** "Notifications never cover the save bar" lives in this change's spec delta.
   P1 does not restate it. P1's integration check (its tasks, "If `ui-a11y-polish` is on main") runs against
   this contract.

**Rationale**:
- Of the rules the region can apply on its own, it is the only one measured to keep the bar, the page's last
  controls and the focused control uncovered with one toast at every width, and two in a window at least
  844 px tall.
- It keeps today's placement exactly while the bar is stuck, which is the common case.
- It owns toast geometry in the one layer that knows the region's height.
- It survives the layout decisions P1 might make about the bar, including a fixed bar.

### Dialog description: the body describes the dialog

**Context**: The consequence paragraph is a free child, so `Dialog` cannot know which child describes it.

**Explored**:
- An optional `describedBy` id, where each caller calls `useId`: three lines per call site, and easy to forget.
- Describing the dialog by a wrapper around all children: the description would then include the action
  buttons' names ("Cancel Render anyway").
- Finding the first `<p>` in the DOM: implicit and fragile.
- An explicit, required `description` prop. This was this design's first decision: `tsc` would enforce it
  for every future dialog, at the cost of one moved line per call site in two other changes' files
  (`EventEditor.tsx`, `RenderControl.tsx`), both of which P1 and P2 rewrite this round.

**Decision (supervisor)**: No new prop. `Dialog` describes itself, and its callers stay unchanged:

- `Dialog` renders a body wrapper, `<div id={bodyId} className="dialog-body">`, after the title, and sets
  `aria-describedby={bodyId}` on the `<dialog>`. `bodyId` comes from `useId`.
- The body is every child **except the actions row**: a child element whose `className` includes
  `dialog-actions`, the design system's own class for that row (`components.css`). The actions render after
  the body, in their order. So the description is the consequence alone, not "… Cancel Render anyway", and
  the spec's scenarios ("described as …") hold exactly.
- A dialog with no body content sets no `aria-describedby`.
- No CSS changes. The wrapper is a plain block with no margin, and `.dialog p` still styles the paragraph,
  so every dialog looks as before.

```tsx
// ui/Dialog.tsx (sketch)
const parts = Children.toArray(children)
const body = parts.filter((part) => !isActionsRow(part))
const actions = parts.filter(isActionsRow)
<dialog aria-labelledby={titleId} aria-describedby={body.length > 0 ? bodyId : undefined}>
  <h2 id={titleId} className="dialog-title">{title}</h2>
  <div id={bodyId} className="dialog-body">{body}</div>
  {actions}
</dialog>
```

**Rationale**:
- Every existing and future dialog gets its consequence read, with no call-site edit. That also removes
  this change's dialog lines from P1's and P2's files, which both rewrite those dialogs this round (P2's
  cancel dialog gains a conditional lead sentence; it is still the body).
- Leaving out the `.dialog-actions` row keeps the button names out of the description. The class is the one
  every dialog already uses for its actions, so the rule adds no new convention.
- If a future caller wraps its actions in a component of its own, the row lands in the body. The
  description then also reads the button names. That is noisier, but the consequence is still read. The
  verification checks the four dialogs on main.

### Browser UI color

**Context**: The metas are keyed on `prefers-color-scheme`, so an explicit choice cannot reach them.

**Explored**:
- The critic's option: drop the `media` attribute and keep one meta for an explicit choice, then restore two
  metas for System. That means adding and removing nodes.
- Setting the `content` of both metas.
- Reading the color from computed CSS. That gives an `oklch()` string, whose support in `theme-color` varies
  by browser.

**Decision**:
- **Set both metas' `content`.** For Light or Dark, both metas MUST carry that scheme's color, so whichever
  `media` matches, the browser gets the chosen one. For System, each meta gets back its own scheme's color.
  A meta's own scheme is read from its `media` (`meta[name="theme-color"][media*="dark"]` is the dark one).
- **`theme.ts` holds the colors.** It gets
  `const THEME_COLOR: Record<'light' | 'dark', string> = { light: '#f9fafc', dark: '#0b0d11' }` with an
  `applyThemeColor(choice)` helper, which `applyThemeChoice` calls. The comment says to keep the values in
  step with `index.html` and `--bg`, as `STORAGE_KEY` already does.
- **The pre-paint script applies the same rule for a stored choice.** The inline script in `index.html` reads
  the two colors from the metas themselves, which are unmodified at that point, so the script holds no second
  copy of the hex values.

**Rationale**:
- The markup stays the same, and System behaves exactly as now.
- A dynamic `content` change is picked up by mobile Chrome and Safari.
- `<meta name="color-scheme" content="light dark">` is left as is: the built stylesheet is render-blocking, and
  `:root[data-theme]` sets `color-scheme` before the first paint, so it cannot flash.

### Touch targets under a coarse pointer

**Context**: The design critic measured the phone-width targets at 24-28 px: the theme options 28 × 26, the
list's compact Render 81 × 26, the filter options 26 px tall and the back link 71 × 24. That meets WCAG 2.2's
24 px minimum (2.5.8) but not the 44 px that phone interfaces use (WCAG 2.5.5). The supervisor gave the
finding to this change: one `@media (pointer: coarse)` rule set across `shell.css` and `components.css`, with
`detail.css`'s `.back-link` as a one-line exception, with no change in density under a fine pointer.

**Explored**: This change's own probe (`<scratchpad>/verify/ui-a11y-polish/touch_probe.py`,
`header_probe.py`), read-only on the agent's server of `bca64f2`, in Chromium with touch emulation
(`has_touch`, `is_mobile`: `(pointer: coarse)` matches). For every control of the list, Grillning's page and
its Edit mode at 390, 320 and 768 px, it measured the box, and every other control that meets the 44 × 44
box centred on it.
- **Below 44 px:** every `.btn` (32 px tall; the compact Render and Edit's Remove and Undo 26), every icon
  button (32 × 32), the segmented options (26 tall; theme options 28 wide, "All" 40), the header's Events
  link (30 tall) and the back link (24 tall).
- **Neighbours inside the 44 px box:** only the two segmented groups (their options are 2 px apart) and
  Edit's move up / move down pair (4 px apart). No other control comes within reach of another's box.
  (Changed in review: the probe never reached the save bar's conflict state, where two buttons wrap 8 px
  apart. See "Changed during review".)
- **Header room:** the header has 57 px to spare at 390, 27 at 360 and **none at 320**, where the jobs
  status already shrinks from 84 to 71 px. (Changed in review: measured with the jobs pill reading "Live".
  "Connecting…" and "Reconnecting…" are wider. See "Changed during review".)
- Growing the boxes instead was ruled out where the box sits in a track another change sized for the fine
  pointer: Edit's handle sits in a 2rem grid column and the move pair in a 4.25rem one (`edit.css`, P1's),
  and every row would grow. The header has no height to give a 44 px option inside its 2 px track (50 > 48).

**Decision**: Under `@media (pointer: coarse)` only:
- **A hit area, not a bigger box, for buttons and links** (`components.css`): `.btn` (every variant),
  `.segmented label` and `.toast-action` become `position: relative` with an `::after` that is the control's
  border box grown evenly to 2.75rem each way where it is smaller. It is invisible, takes no layout, and a
  tap on it is a tap on its element. Nothing moves, and nothing looks different. The area is set by insets,
  `min(-1px, calc(50% - 1.375rem))`: they count from the padding box, whose size is `100%`, and `-1px` takes
  in the 1px border. (A first version sized the area `max(100%, 2.75rem)` and centred it with `translate`.
  The probe found that it missed the border's 1px columns where the area reaches past the box, because
  `100%` is the padding box.)
- **Two icon buttons side by side** (`.btn-icon` followed by `.btn-icon`, Edit's move pair) extend their
  areas away from each other: the first toward its start, the second toward its end. Each keeps 44 × 44 of
  its own, and neither area reaches into the other button.
- **Segmented options grow to 2.75rem wide** (`components.css`), so their areas never overlap the next
  option; only their height needs the hit area. That is the one visible change: the filter's "All" grows by
  4 px, and the theme options from 28 to 44 px.
- **The theme control keeps 1.75rem below 24rem** (`shell.css`). Its options would need 48 px more than a
  320 px header has. There they stay 28 px wide, with a 44 px tall area of their own width, so the three never
  overlap. 24rem (384 px) is the narrowest window with room: 390 and wider phones get 44 × 44. (Changed in
  review: 26rem, and under a coarse pointer the brand name stays hidden up to 34rem. See "Changed during
  review".)
- **The header's Events link** (`shell.css`) gets the same hit area, inside the 48 px header.
- **The back link** (`detail.css`, one rule) grows to `min-block-size: 2.75rem`. It is alone on its line,
  so growing it moves nothing beside it.

```css
/* components.css, @layer components */
@media (pointer: coarse) {
  .btn,
  .segmented label,
  .toast-action {
    position: relative;

    &::after {
      content: '';
      position: absolute;
      inset: min(-1px, calc(50% - 1.375rem));
    }
  }
  .btn-icon:has(+ .btn-icon)::after { inset-inline: min(-1px, calc(100% + 1px - 2.75rem)) -1px; }
  .btn-icon + .btn-icon::after { inset-inline: -1px min(-1px, calc(100% + 1px - 2.75rem)); }
  .segmented label { min-inline-size: 2.75rem; }
}
/* shell.css: the same area for `.app-nav a`; below 24rem the theme options keep 1.75rem and
   their area its width (`inset-inline: -1px`). detail.css: `.back-link { min-block-size: 2.75rem }`. */
```

**Rationale**:
- Under a fine pointer nothing changes: the rule set is inside the media query, and the probe found no
  rect that differs from `bca64f2`.
- A hit area fits every layout the parallel changes are reshaping (the save bar, Edit's rows, the list's
  rows), because it changes no box.
- `.btn`'s `::before` is the busy loader, so the hit area uses `::after`, which no `.btn` uses. The skip
  link's `position: fixed` (`shell.css`, a later layer) still wins over `position: relative`.

Not covered, and why (raised to the supervisor):
- **Text inputs in Edit mode** are 36 px tall. `.field-input` is in `edit.css` (P1's).
- **The list's event title links** are 17 px tall text. `event-list-polish` (P3) is making the whole row a hit
  area for its link, which supersedes a per-link rule.
- **The theme options below 24rem** stay 28 px wide (above). The supervisor accepted this ("Supervisor
  decisions (after implementation)"). (Changed in review: below 26rem.)

### Files and parallel changes

**Context**: P1-P4 are implemented in parallel worktrees from `bca64f2` (brief, "File ownership").

**Decision**: This change's edits outside its owned files are call sites only:

- **`web/src/edit/EventEditor.tsx`** (P1): two lines in the bar layout effect register the bar, plus the
  import. P1 lands after this change and keeps them ("The contract with `edit-mode-polish`, as decided").
  The dialogs are untouched: `Dialog` describes itself.
- **`web/src/jobs/RenderControl.tsx`** (P2): untouched.
- **`web/src/events/EventDetail.tsx`** (P4): `role="note"` on the missing-clip `Alert`. That is one attribute.
- **`web/src/shell/shell.css`** (no owner this round): one term, `var(--toast-rise-h, 0px)`, in `html`'s
  `scroll-padding-bottom`, and its comment; and the coarse-pointer rules for the header's Events link and the
  theme control below 24rem. No other change of this round lists `shell.css`. (After review: the theme
  control below 26rem, the brand name up to 34rem, and the row gap of `.page-actions` and `.toolbar`.)
- **`web/src/styles/components.css`**: the toast rules (owned) and the coarse-pointer block (supervisor).
- **`web/src/events/detail.css`** (P4): one coarse-pointer rule for `.back-link`.
- **`web/README.md`**: only the "Dialogs" and "Toasts" bullets, the theme sentence and a touch-target
  sentence of "Design system".

The spec delta ADDs five requirements and MODIFIES only the color-scheme requirement. No other P-change of
this round is expected to touch that requirement. The gate task re-bases it anyway.

**Rationale**: This keeps merge conflicts to a few known lines.

### Unassigned findings in this layer (not fixed here)

**Context**: Two minor findings touch `ui/` or the shell but are in no section of this round's brief.

**Decision**: Recorded, not fixed. They are raised to the supervisor.
- **Toasts under a modal dialog** (integration critic, not verified here). A toast raised while a `<dialog>`
  is open sits under the backdrop, is inert, and a success toast's clock runs out unseen. The fix needs the
  region in the top layer (`popover="manual"`, shown after the dialog), or deferred emission. That is a design
  choice of its own, with a WebKit support question. The supervisor kept it a follow-up.
- **Touch targets of 24-28 px at phone width** (design critic): no longer unassigned. The supervisor gave it
  to this change ("Touch targets under a coarse pointer").

**Rationale**: Principle VIII, and the brief's ownership table.

### Changed during review

The supervisor's review (two Opus lenses, then skeptics) found one major and three minor defects. Two of them,
the major one included, share one cause in the header. All four were fixed on `pr/ui-a11y-polish` in new
commits. The scripts named below are in `<scratchpad>/verify/ui-a11y-polish/rf/`.

1. **Under a coarse pointer, the jobs status ran into the theme control** (one major and one minor finding).
   The 44 px theme options take 48 px more from 24rem up. The jobs stylesheet hides the pill's words only
   below 23.5rem, a step sized for 28 px options. The "Header room" figure above was measured with the pill
   reading "Live". `header_sweep.py` measured this branch's first build under a coarse pointer, at 1 px steps
   from 320 to 600 px:
   - "Connecting…" ran past its pill at 384–392 px, by up to 9.1 px.
   - "Reconnecting…" ran past its pill at 384–405 px and at 480–487 px, by up to 21.3 px. At 384–393 px it
     ran into the theme control, by up to 9.3 px.
   - Live, with 3 jobs rendering and 12 queued, the indicator took two lines at 384–414 px, where main keeps
     one. At 480–519 px, where the brand name returns, it took three lines: 61 px high, from y −7.1 to 54.1,
     in the 48 px header.
   - Main, and this branch under a fine pointer, showed none of this at any width.

   The fix keeps the words and gives the header its room back where it has none, in `shell.css` only:
   - Under a coarse pointer the theme options keep 1.75rem below **26rem**, not 24rem. Their area stays as
     wide as the option and 44 px tall. "Reconnecting…" needs 116.5 px, and with the wide options the slot
     beside it is the window minus 296.8 px, so the words fit from 414 px. That leaves 2.7 px to spare at
     416 px and 14–16 px at 428–430 px, the large iPhones.
   - Under a coarse pointer the brand name stays visually hidden up to **34rem**:
     `(width < 30rem), (pointer: coarse) and (width < 34rem)`. With the name and the wide options, the counts
     in words fit in two lines from 520 px. The last rem is for wider fonts: 33rem, tried first, still stacked
     the counts in three lines at 528–537 px with Liberation Sans.
   - So, under a coarse pointer:
     - below 26rem the header is the fine pointer's at the same width
     - from 26rem the wide options take 48 px, which the words have room for
     - from 30rem to 34rem the hidden brand name gives back more than the options take
     - from 34rem the header is the fine pointer's at a window 48 px narrower, which main's sweep shows clean
       from 480 px

   After the fix, `header_sweep.py` covered connecting, reconnecting, live with counts and plain live, from
   320 to 600 px at 1 px steps, under both pointers, on main and on this branch. Nothing ran past its pill,
   into the theme control or out of the header, and nothing scrolled sideways, at any width. The fine
   pointer's rects are still identical to main's (324/324).

   Chromium in the container resolves `system-ui` to WenQuanYi Zen Hei, so the sweep was run again with the
   whole page forced to Liberation Sans (Arial's metrics) and to FreeSans (Helvetica's):
   - **Coarse pointer:** clean in both fonts.
   - **Fine pointer, Liberation Sans:** the counts take three lines at 480–485 px, on main and on this branch
     alike. That is the fine pointer's own 30rem step, not this change's; it is listed as a follow-up.

   Rejected:
   - **Hiding the pill's words under a coarse pointer up to about 26rem** (the minor finding's second option).
     This hides "Reconnecting…" on the most common phones (390–412 px) exactly while the service is down. The
     jobs requirement says the header shows the connection's state in words, and Connecting and Reconnecting
     would then differ by tone alone.
   - **A container query on the status slot** (the major finding's robust option). It has the same effect at
     those widths. It also needs `.shell-status` to become a size container that fills the header, a layout
     change under the fine pointer, and it still needs a fixed width threshold.
   - **One cycling theme button.** It changes the control for a mouse too, which is out of scope for a review
     fix.
2. **A touch scroll cancelled the displaced-toast hand-off** (minor). Any `pointerdown` outside the region
   cleared `lastFocused`, and a touch scroll fires one without moving focus. A newer toast that then displaced
   the focused toast left focus on `<body>`. The record is now cleared only when focus leaves:
   - A document `focusout` from inside the region is decided in a microtask. It clears the record only when
     its node is still connected and `document.activeElement` is outside the region.
   - The focusout Chromium fires for a removed node is not a leave. By the time the microtask runs, the node is
     disconnected and the layout effect has already handed focus on. A browser that fires no focusout there
     keeps the record anyway. Only Chromium was measured.
   - The `focusin` rule stays.

   `focus_record.py` passed 9/9:
   - **Focus handed on to a remaining Dismiss:** with no gesture, after a touch scroll of the page or one
     starting on a toast, after a wheel scroll, and after Tab between Dismiss buttons.
   - **Focus left alone:** after a tap or a mouse click on the page background (`<body>` stays focused), Tab
     out to the `h1`, and a tap on Refresh.

   The reviewer's `displace_after_tap.py` and `displace_after_scroll.py` now end on a remaining Dismiss after
   the touch scroll.
3. **Two stacked buttons less than 12 px apart shared their areas** (minor). Each 32 px button's area reaches
   6 px past its box. In the save bar's 412 conflict alert at phone width, "Reload latest (discard my changes)"
   wraps 8 px above "Overwrite with mine". Overwrite's area, painted later, took 7 of the 8 gap rows, so a tap
   just below Reload opened Overwrite (its confirmation dialog still caught it). The probe behind "Neighbours
   inside the 44 px box" never reached the conflict state.
   - Under a coarse pointer, the shared rows that can wrap buttons onto a second line now keep `row-gap:
     var(--s-4)` (1rem): `.alert-action` and `.dialog-actions` in `components.css`, and `.page-actions` and
     `.toolbar` in `shell.css`, after their base rule. Each area reaches 6 px into the gap and 4 px stay free.
   - 0.75rem, where the areas meet exactly halfway, was tried first. With the bar at a half-pixel offset,
     Chromium's hit test still gave the boundary row to the later button.
   - A fine pointer keeps the 8 px gap.

   `touch_rf.py` passed 98/98: every v52 touch check, plus the conflict state on Grillning and on the
   Omöjligt datum fix form at 320, 360, 390 and 768 px. Every point of Reload's and Overwrite's areas reaches
   that button, the stacked pair is 16 px apart, and under a fine pointer the gap is still 8 px. The header at
   412, 414, 416 and 430 px gives the theme options 28, 28, 44 and 44 px. The reviewer's `conflict_touch.py`
   no longer reports Reload losing points to Overwrite.

**Spec.** The touch requirement now:
- reads 416 pixels for the color-scheme exception, not 384
- says that no area reaches into another control stacked above or below it, and that making room for the
  areas pushes no text out of its box and nothing out of the header
- has a "list on a phone" scenario that gives the color-scheme options their option-wide area at 390
- adds two scenarios: the header keeping the connection's state in words, and the conflict alert's stacked
  buttons

**Found while verifying, not fixed here:**
- **At 320 px, the conflict alert scrolls the page 20 px sideways** (`conflict_hscroll_ab.py`). Its 241 px
  `nowrap` "Reload latest (discard my changes)" is wider than the save-bar card. Main does the same under
  both pointers. This is `edit-mode-polish`'s alert, which it is reshaping.
- **The fine pointer's 30rem step depends on the font.** With Liberation Sans the live counts stack in three
  lines at 480–485 px, on main as well. That step is the jobs indicator's and the shell's.

## Failure behavior and idempotency

- This change makes no request, writes no file, and neither enqueues nor cancels anything. Rendered output,
  fingerprints and the DB are untouched, so re-runs, `--force` and worker restarts are unaffected.
- Storage failures stay as today. `applyThemeColor` runs before the `try` around storage, so a blocked storage
  still switches the meta for the current page. The pre-paint script's `try` already swallows a throwing
  `localStorage`, and then the metas stay OS-keyed.
- Registration is idempotent under StrictMode. The effect registers, releases and registers again. Each call
  returns a release bound to its own registration (a token, not the element: the same element is registered
  twice), so a stale release after a later registration does nothing and the second registration holds. A bar
  removed without release (unmount) runs the effect cleanup, which releases it. `--toast-offset` and
  `--toast-rise-h` are removed with the registration, so the region and the scroll padding fall back
  cleanly to today's values.
- A focus hand-off that finds no candidate that takes focus leaves focus where the browser puts it. The `h1`
  (`tabIndex -1`) always exists on a shown page, so this does not happen in practice.
- With no toast shown, the placement effect still runs on scroll, but it only reads two rects and writes a
  custom property only when its value changes.

## Risks / Trade-offs

- **[Screen readers differ on `role="alert"` with `aria-atomic="false"`]** → Chromium exposes
  `atomic: false`, which the verification checks. No real screen reader is available in this environment, so
  this remains a residual risk. The status stack, where most toasts land, is the well-supported case.
- **[Toasts jump from above the bar to below it during the last scroll pixels]** → The jump happens at one
  threshold per scroll to the end, and has no animation, which suits reduced motion. It is preferred over
  covering the last clip rows (measured).
- **[A scroll listener]** → While a bar is registered: one `getBoundingClientRect` per scroll event (at most
  once per frame) and a style write only when the value changes.
- **[A dialog whose actions are not a `.dialog-actions` child]** → Its description also reads the button
  names. Every dialog on main uses the row, and the consequence is still read. A parallel change that adds a
  dialog needs no edit for this change.
- **[A touch hit area reaches past its box]** → A tap up to 6 px beside a 32 px button (9 px beside a 26 px
  one) is that button's. The probe found no other control within reach on the screens of `bca64f2`. A later
  layout that puts a control that close to a button shares the overlap, and the later element in the page
  wins it. `event-list-polish`'s row-wide link is the case to recheck when it lands: a button's area must stay
  above the row's link. (Changed in review: the shared rows that wrap buttons keep 1rem between lines under
  a coarse pointer. See "Changed during review".)
- **[The theme options below 24rem]** → 28 × 44 px, not 44 × 44: the header has no width to give (measured).
  Accepted by the supervisor. (Changed in review: below 26rem, which keeps the jobs status in words. See
  "Changed during review".)
- **[The hex colors are duplicated between `index.html` and `theme.ts`]** → The verification compares each
  against the rendered `--bg`. The pre-paint script reads the metas instead of holding a third copy.
- **[P1 restructures the save bar]** → The rule depends only on the registered element's box. The table above
  covers sticky, fixed and moved-alert variants.
- **[Three toasts at phone height]** → With three toasts held at 390 × 844 or 320 × 700, the bar stays clear,
  but while it rises the stack can pass the window's top and a focused row can sit under it (review table).
  Scrolling on, or dismissing a toast, ends it. Three held toasts while editing on a phone is rare (errors
  only stay when nobody dismisses them). A fixed bar (Also considered) has no such limit.
- **[The rise term pads more than needed while the bar is stuck]** → With toasts shown, a focused control
  scrolls into view `R + gap` higher than the stuck bar strictly requires. It applies only while a bar is
  registered and a toast is shown.
- **[A pointer dismissal in Chromium moves focus]** → Chromium focuses a clicked button, so the hand-off runs
  (without scrolling). When it lands on another toast's Dismiss, the region stays paused while focus is there,
  so a success toast left after a mouse dismissal waits until the operator clicks elsewhere instead of timing
  out. That errs toward more reading time (WCAG 2.2.1), and is accepted.
- **[Mobile browsers with a collapsing address bar]** → The rule reads `clientHeight` and rects, measured in
  desktop Chromium only. The read-back gap absorbs a constant difference between the fixed-position box and
  `clientHeight`; a residual misplacement on a phone browser would be by the toolbar's height, and is not
  measured here.

## Migration Plan

None. It ships with the static build. Rollback is a revert, with no data, schema or storage key involved.
