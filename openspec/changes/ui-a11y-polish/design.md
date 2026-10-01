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

- Fix the five P5 findings inside the owned files (proposal, Impact).
- Keep every other change's files at call-site edits only.
- Give P1 a toast placement contract that holds whichever change lands first.

**Non-Goals:**

- No new component, no dependency, and no visual change except where the toasts sit relative to the save bar.
  Dialogs, toasts and the missing-clip warning look exactly as before.
- No change to toast lifetime, the cap, pause-on-hover/focus, or the busy-control rule.

## Research & Decisions

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
  than under the form. Raised to the supervisor. If P1 adopts it, this change drops task 2.2's placement code
  and keeps only the documented contract ("a page that publishes `--toast-inset-bottom` holds the measured
  bar at the window's bottom edge"); the requirement then holds by P1's bar and today's region.
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

**Rationale**:
- Of the rules the region can apply on its own, it is the only one measured to keep the bar, the page's last
  controls and the focused control uncovered with one toast at every width, and two in a window at least
  844 px tall.
- It keeps today's placement exactly while the bar is stuck, which is the common case.
- It owns toast geometry in the one layer that knows the region's height.
- It survives the layout decisions P1 might make about the bar, including a fixed bar.

### Dialog description: a required prop

**Context**: The consequence paragraph is a free child, so `Dialog` cannot know which child describes it.

**Explored**:
- An optional `describedBy` id, where each caller calls `useId`: three lines per call site, and easy to forget.
- Describing the dialog by a wrapper around all children: the description would then include the action
  buttons' names ("Cancel Render anyway").
- Finding the first `<p>` in the DOM: implicit and fragile.
- An explicit prop.

**Decision**: `Dialog` gains a **required** (MUST) `description: ReactNode`, rendered as
`<p id={descriptionId} className="dialog-description">` right after the title, with
`aria-describedby={descriptionId}` on the `<dialog>`. `children` becomes only the actions (and any extra
content). The four call sites move their paragraph's text into `description=`. Callers pass inline content
(it sits inside a `<p>`). The existing `.dialog p` rule styles it, so no CSS changes.

**Rationale**: Required means `tsc`, the frontend gate (D-8), enforces the new requirement for every future
dialog, as the exhaustive label maps do. The change is one moved line per call site.

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

### Files and parallel changes

**Context**: P1-P4 are implemented in parallel worktrees from `bca64f2` (brief, "File ownership").

**Decision**: This change's edits outside its owned files are call sites only:

- **`web/src/edit/EventEditor.tsx`** (P1):
  - Two lines in the bar layout effect register the bar.
  - The Discard and Overwrite dialogs each move their `<p>` into `description`.
  - P1 is expected to edit this file heavily: save-bar publish, focus and Try again. Whichever lands second
    re-applies the other side's lines.
- **`web/src/jobs/RenderControl.tsx`** (P2): the Render anyway and Cancel dialogs move their `<p>` into
  `description`. P2 changes the cancel dialog's lifetime and the hand-off after Render anyway, so the text of
  these two blocks may move. The rebase keeps P2's text inside `description`.
- **`web/src/events/EventDetail.tsx`** (P4): `role="note"` on the missing-clip `Alert`. That is one attribute.
- **`web/src/shell/shell.css`** (no owner this round): one term, `var(--toast-rise-h, 0px)`, in `html`'s
  `scroll-padding-bottom`, and its comment. No other change of this round lists `shell.css`.
- **`web/README.md`**: only the "Dialogs" and "Toasts" bullets and the theme sentence of "Design system".

The spec delta ADDs four requirements and MODIFIES only the color-scheme requirement. No other P-change of
this round is expected to touch that requirement. The gate task re-bases it anyway.

**Rationale**: This keeps merge conflicts to a few known lines.

### Unassigned findings in this layer (not fixed here)

**Context**: Two minor findings touch `ui/` or the shell but are in no section of this round's brief.

**Decision**: Recorded, not fixed. They are raised to the supervisor.
- **Toasts under a modal dialog** (integration critic, not verified here). A toast raised while a `<dialog>`
  is open sits under the backdrop, is inert, and a success toast's clock runs out unseen. The fix needs the
  region in the top layer (`popover="manual"`, shown after the dialog), or deferred emission. That is a design
  choice of its own, with a WebKit support question.
- **Touch targets of 24-28 px at phone width** (design critic). They are in `shell.css`, `components.css`
  (`.btn-compact`, `.segmented`) and `detail.css`, which are not this change's files.

**Rationale**: Principle VIII, and the brief's ownership table.

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
- **[A required `description` breaks a parallel change that adds a dialog]** → `tsc` reports it at rebase,
  and the fix is to pass the text. This is intended.
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
