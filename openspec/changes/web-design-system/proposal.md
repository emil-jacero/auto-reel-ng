## Why

GUI v1 (HLD **§6 phase 8**, §4.10, stack **D-8**) has two screens so far, the event list and the event page.
Both are styled as a readable minimum: one flat `app.css` (294 lines), hex tokens redefined under
`prefers-color-scheme: dark`, browser-default buttons, no focus styles, and table column widths set by
position (`th:nth-child(n)`, `app.css:97-111` and `:236-254`). That minimum was deliberate. The event-list
design deferred "visual polish beyond readable, theme-aware plain CSS" to a v2 look-and-feel pass
(`archive/2026-09-26-event-list-screen/design.md:31-32`).

The operator has now asked for the rest of GUI v1 (slice D: reorder and metadata, slice E: render and live
progress) **and** a modern visual design for the whole GUI in v1. Doing the design now, before D and E,
has two reasons:

- **D and E are built in parallel on top of it.** Both need the same pieces: icons, buttons, a
  confirmation dialog, toasts, status pills, alerts, and a way to tell the hidden list that an event
  changed. If each slice builds its own, there are two competing implementations and a merge conflict in
  every shared file. Landing them once in this change, with fixed names, avoids both.
- **The current CSS does not survive new columns.** Any column a later slice adds shifts every `nth-child`
  width rule, and those rules are already overridden twice (clip tables, narrow windows). Moving to
  class-based widths is cheapest before E reshapes the list's rows.

The redesign stays inside D-8's budget: plain CSS, inline SVG and native HTML (`<dialog>`), with no new
dependency. Pulling the visual design into v1 is a decision that outlives this change, so it is recorded
as **D-10** in the HLD.

## What Changes

- **One visual system in plain CSS.** `app.css` is replaced by layered stylesheets
  (`@layer reset, tokens, base, components, screens`): OKLCH color tokens resolved per scheme with
  `light-dark()`, a cool-gray neutral ramp, one indigo accent, five status tones (ok, warn, err, info,
  idle), spacing, radius, shadow, type and motion tokens. System fonts, 14px body, tabular numbers. Each
  screen and each later change keeps its own stylesheet.
- **An app shell.** A sticky header on every page shows the product mark and name, the primary navigation
  (Events), an empty slot for later status indicators, and a theme control (System, Light, Dark). The
  choice is kept per browser. A skip control and focus management make the pages keyboard-friendly.
- **The event list, restyled.** A page header with the summary and the scan time, a toolbar with an
  **All / Needs render** segmented control (replacing the checkbox, same behavior and state) and a Refresh
  button, year groups as panels with sticky headings, status pills that pair an icon with words, and the
  "Needs attention" group as a warning panel. Tables stay tables, with class-based column widths. At phone
  width each row reflows instead of scrolling sideways.
- **The event page, restyled.** A back link, a header with the title, facts, verdict and latest job,
  chapters as panels, and the missing-clip warning as an alert.
- **Loading and failure states.** Loading shows placeholder rows plus an announced status message. A
  failure shows an alert with a tone, an icon, the cause and the detail.
- **Shared UI primitives for slices D and E** (`web/src/ui/`): `Icon`, `Pill`, `Alert`, skeleton rows,
  `Dialog` (native `<dialog>`), toasts (`toast.*` and `ToastRegion`), and button classes. Also a small
  "events changed" signal (`web/src/events/changes.ts`). Once an event changes elsewhere in the client, the
  list re-reads the next time it is shown. This change wires the list side; D and E call
  `markEventsChanged()`.
- **Rules the next slices build on**, stated once here so C4 and C5 follow one pattern: a pressed control
  that becomes busy is `aria-disabled` + `aria-busy` and never `disabled`; `Dialog` takes an optional
  `initialFocus` ref for the safe action; the toast region's bottom offset follows
  `--toast-inset-bottom` (default 0) so a sticky bar can lift it; every looping animation is declared
  only under `prefers-reduced-motion: no-preference`, checked by a grep gate each slice runs over its own
  directory. Requirement ownership in `web-app` is fixed in design "Risks": C4 and C5 do not modify the
  three requirements this change modifies, and only C5 modifies one this change adds.
- **Spec text that the next slices would make false is corrected now.** The "read-only / never poll"
  sentences move out of two screen requirements into one new requirement: reading a screen never changes
  state, and changes happen only through a control that names what it does. This change adds no such
  control.
- **Dev convenience.** The Vite dev proxy target can be set with `AUTO_REEL_API` (default unchanged,
  `http://127.0.0.1:8080`), so a dev server can run against a service on another port.

## Non-goals

- **No new behavior on the data side.** Reads, refresh, abort, hash routing, the hidden list, failure causes
  and label maps keep their current behavior. The only new read is the list re-reading after an
  events-changed signal, and nothing in this change sends that signal yet.
- **No editing, no render button, no live progress, no WebSocket** (slices D and E, changes
  `event-edit-screen` and `render-progress-screen`).
- **No web font, no icon package, no CSS framework, no component library, no PostCSS.**
- **No view transitions, no popover or anchor positioning.** None is needed: `<dialog>` and a fixed toast
  region cover every floating layer. View transitions and anchor positioning are also newer than the
  support floor.
- **No jobs page, search, thumbnails or look editor** (v2 or later).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `web-app`:
  - new `Requirement: Every page shares one header and follows the operator's color scheme`
  - new `Requirement: State is never shown by color alone`
  - new `Requirement: The screens are operable by keyboard`
  - new `Requirement: The screens respect reduced motion`
  - new `Requirement: The screens fit a phone-width window`
  - new `Requirement: A read in progress is shown as a placeholder and announced`
  - new `Requirement: Reading a screen never changes state`
  - modified `Requirement: The event list answers what needs rendering, from disk`: the read-only and
    no-poll sentences move to the new requirement, the filter is a two-way choice, and the list re-reads
    after an events-changed signal
  - modified `Requirement: Each event opens on its own page`: the same re-read exception on return
  - modified `Requirement: The event page shows the event's chapters and clips`: the read-only and no-poll
    sentences move to the new requirement

## Impact

- **Packages:** `web/` and `docs/` only.
  - New files:
    - `src/styles/{index,reset,tokens,base,components}.css`
    - `src/ui/{Icon,Pill,Alert,Skeleton,Dialog,ToastRegion}.tsx`, `src/ui/toast.ts`
    - `src/shell/{AppShell.tsx,theme.ts,shell.css}`
    - `src/events/{changes.ts,tones.ts,list.css,detail.css}`
  - Rewritten markup and class names: `src/events/EventList.tsx`, `EventDetail.tsx`, `common.tsx`.
  - Modified: `src/App.tsx` (renders inside the shell, focus on navigation), `src/main.tsx` (imports the
    stylesheets), `index.html` (`color-scheme` and `theme-color` metas, and the stored theme applied before
    first paint), `vite.config.ts` (`AUTO_REEL_API`, `build.cssTarget`).
  - Deleted: `src/app.css`.
  - Docs: `web/README.md` (screens, file tree, a design-system section) and `docs/high-level-design.md`
    (**D-10** in §7, one line in §4.10).
- **CLI vs API (Principle V):** untouched. No endpoint is added, and no response is read differently.
- **Rendered output:** unchanged. **No `RENDER_GRAPH_VERSION` bump.** Fingerprint inputs are unchanged.
- **Schemas:** no `reel.yaml`, `config.yaml` or API change. **No Alembic migration**, no rescan, and no
  `openapi.json` or `schema.d.ts` regeneration.
- **Dependencies:** **gate: none.** This change lands first, and `event-edit-screen` and
  `render-progress-screen` are gated on it. **Packages added: none** (Principle VII). Icon path data is
  adapted from Lucide (ISC, with MIT portions from Feather), with its notice kept in `Icon.tsx`. It is
  copied source, not a package.
- **Size (Principle VIII):** one package (`web/`) plus docs, and one capability delta. It is large for a
  single change, because it restyles two screens and adds primitives that nothing calls yet. The tasks are
  split so each ends in a type-checked, buildable state. See design "Risks" for the split this change
  would fall back to.
