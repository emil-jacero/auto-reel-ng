## Context

See proposal.md, "Why". The state `web/` starts from (main at `541c44c`):

- **One stylesheet.** `src/app.css` (294 lines) is imported at `App.tsx:1`. It has:
  - flat hex tokens on `:root`, redefined under `@media (prefers-color-scheme: dark)` (`:2-33`)
  - element-selector rules for `main`, `header`, `h1`, `button`, `nav`, `a`, `table`, `caption`, `th` and
    `td` (`:35-133`, `:192-198`), so any new `<header>` inherits the flex row
  - positional column widths `th:nth-child(1|2|3|5)` (`:97-111`), overridden for clips (`:236-254`) and
    reset under `max-width: 40rem` (`:279-294`)
  - no focus, hover or motion rules, and no accent color
  - `.table-scroll { overflow-x: auto }` (`:85-88`) around every table
- **Screens.**
  - `EventList.tsx` renders `<main hidden={hidden}>` (`:170`) with an `h1`, a Refresh button that is
    `disabled` while loading (`:173`), a checkbox filter (`:246-253`), an attention table and one table per
    year. The year is a `<caption>` (`:101`).
  - `EventDetail.tsx` renders `<main>` with a `nav` back link (`:110-112`), an `h1`, the same disabled
    Refresh (`:115`), `.failure`/`.warning` blocks with `role="alert"`, and one table per chapter keyed by
    index (`:181-182`).
  - Loading on both screens is a plain `<p className="muted">` (`EventList.tsx:178`, `EventDetail.tsx:120`),
    with no live region.
- **Shared cells.** `common.tsx` has `JobCell` (`:35-47`, `job job-<status>` text plus the time) and
  `StalenessCell` (`:50-63`, `pill pill-stale|pill-fresh` plus reasons).
- **Routing and the kept list.** `route.ts` maps every hash other than `#/event/…` to the list (`:22-38`).
  `App.tsx` keeps the list mounted, saves and restores its scroll, and sets the list's title (`:15-57`).
- **`index.html`** has no `color-scheme` or `theme-color` meta. `vite.config.ts` hard-codes the proxy target
  `http://127.0.0.1:8080` (`:5`).
- **The tsc include covers `vite.config.ts`** (`tsconfig.json` `include`), and `@types/node` is not
  installed. The config therefore cannot reference `process`.
- **Chapter names are unique within an event's detail.** The reel parser raises on a duplicate
  (`auto_reel_ng/reel/schema.py:118-119`), and the detail read appends a disk-only chapter only when no
  chapter of that name exists yet (`auto_reel_ng/api/events_read.py:298-310`). A chapter's name is
  therefore a stable React key.

## Goals / Non-Goals

**Goals:**

- A modern, quiet, data-dense look for the two existing screens in both color schemes, with no change to what
  they read or when, except the events-changed re-read.
- One token set and one set of component classes that slices D and E extend without editing shared
  stylesheets.
- The shared primitives D and E both need, under the names the plan fixed, verified in this change.
- Keyboard, contrast, reduced-motion and phone-width behavior as the spec states.

**Non-Goals:**

- Any change to data reading, failure mapping, labels or routing semantics beyond the spec's deltas.
- A generic component library. Primitives exist only where two or more screens or slices use them.

## Research & Decisions

### Stylesheet architecture

**Context**: One flat file with element selectors and positional widths (see Context) cannot be extended by
two parallel slices without conflicts, and its element rules leak into new markup.

**Explored**:
- Plain CSS with cascade layers and native nesting. Both are Baseline widely available since 2023, and Vite
  bundles `@import`s without PostCSS.
- CSS modules. Vite supports them natively, but they rename every class and add a second styling idiom.
- A utility framework. Ruled out by D-8.

**Decision**:
- `src/styles/index.css` MUST start with the single order statement
  `@layer reset, tokens, base, components, screens;`, followed by `@import`s of `reset.css`, `tokens.css`,
  `base.css` and `components.css`. `main.tsx` imports `./styles/index.css` before `App`, so the order
  statement comes first in the bundle.
- Every stylesheet MUST wrap all of its rules in exactly one of those layers. Unlayered CSS would beat every
  layer.
- Screen styles live next to their screen and are imported by it: `events/list.css`, `events/detail.css`
  and `shell/shell.css`, all in `@layer screens`.
- Later changes MUST add their own files (C4: `edit/edit.css`, C5: `jobs/jobs.css`) in `@layer components`
  or `@layer screens`, and MUST NOT edit this change's files for their own rules.
- `base` styles elements only typographically: font, color, margins and link color. It sets no `display`
  or layout on `main`, `header`, `nav` or `table`. Layout lives in classes.
- `reset` MUST contain `[hidden] { display: none !important; }`. An `!important` declaration in the first
  layer beats all later layers. Without it, any class that sets `display` on the list's `<main>` would
  un-hide the kept list (`EventList.tsx:170`).
- `vite.config.ts` sets `build.cssTarget` to the support floor (`chrome123`, `edge123`, `firefox120`,
  `safari17.5`), so esbuild neither lowers nesting nor rewrites `light-dark()` for older engines.
- `src/app.css` is deleted.

**Rationale**:
- Layers make order explicit, so the last file imported does not win by accident.
- One file per owner is what lets C4 and C5 work in parallel.
- Keeping `base` free of layout removes the element-selector leakage the current file has.

### Tokens and the support floor

**Context**: Two schemes, five status tones and AA contrast have to hold together. The current hex pairs were
never measured.

**Explored**: `light-dark()` (Baseline 2024: Chrome 123, Firefox 120, Safari 17.5) against a duplicated
`@media (prefers-color-scheme)` block; OKLCH against hex. Sources: MDN `light-dark()`, `color-scheme`, and
the web.dev Baseline tables.

**Decision**:
- `tokens.css` defines on `:root`:
  - `color-scheme: light dark`
  - neutrals: `--bg`, `--surface`, `--surface-2`, `--surface-hover`, `--border`, `--border-strong`, `--fg`,
    `--fg-muted`, `--fg-subtle`
  - accent: `--accent`, `--accent-hover`, `--accent-fg`, `--accent-soft`, `--focus-ring`
  - per tone `ok|warn|err|info|idle`: `--<tone>-bg`, `--<tone>-fg` and `--<tone>` (solid)
  - spacing `--s-1..7` (4px base); radii `--r-sm|md|lg|full`; shadows `--shadow-sm|md|lg` (floating layers
    only); type `--font-sans`, `--font-mono`, `--text-xs..xl` (body `--text-base` = 14px), `--lh-*`;
    motion `--dur-fast|med|slow`, `--ease-*`; layout `--header-h`, `--page-max`, `--row-h`
- Every color MUST be one `light-dark(<light>, <dark>)` value in OKLCH: hue 260 for neutrals, 265 for the
  accent. Within a scheme, every tone's `-bg` shares one lightness and every tone's `-fg` shares another,
  so pills read as one family. Chroma may differ by hue, within gamut. A contrast fix moves a lightness
  for all tones together.
- `:root[data-theme="light"] { color-scheme: light }` and `:root[data-theme="dark"] { color-scheme: dark }`
  implement the override. No other rule reads `data-theme`.
- Motion has two kinds, with one rule each:
  - **Transitions** (hover, focus, enter): every `transition` MUST take its duration from a `--dur-*`
    token, never a literal. Under `@media (prefers-reduced-motion: reduce)` the `--dur-*` tokens become
    `0ms`, so transitions stop without any per-rule override.
  - **Animations** (loops: skeleton shimmer, loader spin, and later C5's indeterminate bar and connecting
    spinner): every `animation` declaration, and the `@keyframes` it uses, MUST sit inside
    `@media (prefers-reduced-motion: no-preference)`, so a reduced-motion user gets none and no `reduce`
    override is needed. A loop's duration is a **literal** suited to a loop (for example `1.2s`), never a
    `--dur-*` token: those are at most 320 ms and become `0ms` under reduce.
- **The motion grep gate** (task 2.1 over `web/src/styles`, task 7.1 over `web/src`) checks both rules:
  - `grep -rnE 'transition[^;]*[0-9.]+m?s\b' <dir>` prints nothing (no literal transition duration)
  - `grep -rn 'animation[^;]*--dur-' <dir>` prints nothing (no token-timed loop)
  - every hit of `grep -rnE '(^|[^-])animation(-name)?:|@keyframes' <dir>` lies inside a
    `prefers-reduced-motion: no-preference` block (read the hits)

  `web/README.md` records the gate. Later changes run the same three commands over their own
  directories (C4 over `web/src/edit`, C5 over `web/src/jobs`) in their validation tasks.
- `--fg-subtle` is for icons, borders and placeholders only, never for text: at its starting value it is
  below 4.5:1 on `--bg` in both schemes.
- Starting values (colors):

  ```css
  --bg:            light-dark(oklch(99% 0.003 260), oklch(17% 0.010 260));
  --surface:       light-dark(oklch(100% 0 0),      oklch(21% 0.012 260));
  --surface-2:     light-dark(oklch(97% 0.005 260), oklch(24% 0.014 260));
  --surface-hover: light-dark(oklch(95.5% 0.006 260), oklch(27% 0.016 260));
  --border:        light-dark(oklch(91% 0.008 260), oklch(30% 0.016 260));
  --border-strong: light-dark(oklch(84% 0.010 260), oklch(38% 0.018 260));
  --fg:            light-dark(oklch(22% 0.020 260), oklch(96% 0.006 260));
  --fg-muted:      light-dark(oklch(48% 0.020 260), oklch(72% 0.016 260));
  --fg-subtle:     light-dark(oklch(60% 0.015 260), oklch(58% 0.016 260));
  --accent:        light-dark(oklch(55% 0.19 265),  oklch(70% 0.15 265));
  --accent-hover:  light-dark(oklch(50% 0.20 265),  oklch(76% 0.14 265));
  --accent-fg:     light-dark(oklch(99% 0 0),       oklch(18% 0.02 265));
  --accent-soft:   light-dark(oklch(95% 0.03 265),  oklch(28% 0.06 265));
  --focus-ring:    var(--accent);
  /* tones: -bg L 95% / 29%, -fg L 45% / 82%, solid as listed */
  --ok-bg:   light-dark(oklch(95% 0.04 155),  oklch(29% 0.05 155));
  --ok-fg:   light-dark(oklch(45% 0.11 155),  oklch(82% 0.13 155));
  --ok:      light-dark(oklch(62% 0.15 155),  oklch(72% 0.15 155));
  --warn-bg: light-dark(oklch(95% 0.05 85),   oklch(29% 0.05 85));
  --warn-fg: light-dark(oklch(45% 0.10 70),   oklch(82% 0.13 85));
  --warn:    light-dark(oklch(75% 0.16 80),   oklch(80% 0.15 85));
  --err-bg:  light-dark(oklch(95% 0.03 25),   oklch(29% 0.06 25));
  --err-fg:  light-dark(oklch(45% 0.17 27),   oklch(82% 0.12 25));
  --err:     light-dark(oklch(58% 0.21 27),   oklch(70% 0.17 25));
  --info-bg: light-dark(oklch(95% 0.03 265),  oklch(29% 0.06 265));
  --info-fg: light-dark(oklch(45% 0.16 265),  oklch(82% 0.10 265));
  --idle-bg: light-dark(oklch(95% 0.006 260), oklch(29% 0.014 260));
  --idle-fg: light-dark(oklch(45% 0.02 260),  oklch(82% 0.016 260));
  ```

  Other tokens: `--s-1..7` = 4, 8, 12, 16, 24, 32, 48px; `--r-sm|md|lg|full` = 4, 6, 10, 999px;
  `--text-xs|sm|base|md|lg|xl` = 12, 13, 14, 16, 20, 26px; `--dur-fast|med|slow` = 120, 200, 320ms;
  `--header-h` 3rem, `--row-h` 2.5rem, `--page-max` 72rem.
- These values are chosen by eye and estimated, **not** measured. Task 6.1 measures contrast (axe-core
  `color-contrast`, both schemes), and this change adjusts lightness until every text/background pair
  passes AA.
- The support floor is recorded in `web/README.md`: evergreen browsers from 2024 on (the versions above).

**Rationale**:
- One declaration per token halves the token block and cannot drift between schemes.
- OKLCH makes "equal lightness per tone" a literal property, so pills read as one family.
- The floor is safe for a local, single-operator tool. Below it, colors fall back to browser defaults,
  and nothing stops working.

### Theme choice and persistence

**Context**: The operator wants System, Light and Dark, remembered per browser. A reload must not flash the
wrong scheme, and blocked storage must not break the page.

**Explored**:
- Applying the choice in `main.tsx` alone. Module scripts run after parse, so a dark-OS operator who chose
  Light would see one dark frame.
- An inline `<head>` script.
- Storing the choice server-side. Rejected: it is a per-browser preference, not project state (Principle II
  keeps service state editorial).

**Decision**:
- `src/shell/theme.ts` exports:

  ```ts
  export type ThemeChoice = 'system' | 'light' | 'dark'
  export function readThemeChoice(): ThemeChoice          // 'system' on absence, junk or a throw
  export function applyThemeChoice(choice: ThemeChoice): void // sets/removes <html data-theme>, then stores
  export function useThemeChoice(): [ThemeChoice, (choice: ThemeChoice) => void]
  ```

- The storage key is `auto-reel:theme`, with the value `light` or `dark`. `system` removes the key.
- Every storage access MUST be wrapped in `try/catch`. A failure falls back to `system` on read, and on write
  keeps the choice for the page only.
- `index.html` gets:
  - `<meta name="color-scheme" content="light dark">`
  - two `theme-color` metas scoped by `media="(prefers-color-scheme: …)"`, with hex values (a meta cannot
    read a CSS token)
  - a 3-line inline `<script>` in `<head>` that reads the same key inside `try/catch` and sets
    `document.documentElement.dataset.theme` only when the value is `light` or `dark`

  The key is duplicated in `index.html` and `theme.ts`, each with a comment naming the other.
- The control is a radio group: a `<fieldset>` with a visually hidden legend "Color scheme", and three
  native radios labelled System, Light and Dark. Each shows the `monitor`, `sun` or `moon` icon, with its
  text visually hidden and its `title` set. Native radios give arrow-key selection with no script.

**Rationale**: It is the smallest mechanism that meets the spec's "before the first paint" and "storage
blocked" scenarios. The inline script is the only way to set the attribute before first paint.

### App shell, skip control and focus

**Context**: There is no shared header, no skip link, and no focus handling on navigation. The Refresh
buttons drop keyboard focus, because a disabled button loses focus (`EventList.tsx:173`,
`EventDetail.tsx:115`). And **a fragment skip link would navigate**: `href="#main"` changes the hash, which
`parseRoute` maps to the list (`route.ts:22-25`).

**Explored**:
- An `<a href="#main">` skip link. It breaks routing, as above.
- A skip control that moves focus with a script.
- The View Transitions API for page changes. Not needed, and newer than the support floor (Firefox only
  shipped it in 2025).

**Decision**:
- `src/shell/AppShell.tsx` exports `AppShell({ route, children })`, which renders:
  - a `<button className="skip-link">Skip to content</button>`, visually hidden until focused. It calls
    `focusPageHeading()`.
  - `<header className="app-header">` containing:
    - the brand: an inline-SVG mark and the text "auto-reel". Below 30rem the text is visually hidden, and
      it stays in the accessibility tree.
    - `<nav aria-label="Primary">` with one link, Events (`LIST_HREF`), carrying `aria-current="page"`
      while the route is the list
    - `<div className="shell-status" />`, empty here, for C5's `<JobsIndicator />`
    - the theme control
  - `children`: the screens' own `<main>` elements, unchanged in number
  - `<ToastRegion />`
- `App.tsx` renders its routes inside `<AppShell route={route}>`. `app.css` is no longer imported.
- `focusPageHeading(options?: FocusOptions)` focuses `main:not([hidden]) h1`. Every page `h1` gets
  `tabIndex={-1}`, and has no focus ring when focused by script (`h1:focus:not(:focus-visible)`).
- `App`'s existing route layout effect (`App.tsx:42-49`) calls `focusPageHeading({ preventScroll: true })`
  on every route change after the first render, after the scroll restore, so the two never fight. "A route
  change" MUST be detected by comparing `route` with the previous route kept in a ref (initialised to the
  first route), not with a "first run" flag: StrictMode runs the mount effect twice, and a flag would move
  focus to the `h1` on a fresh load, so the first Tab would skip the skip control.
- Refresh stays focusable while loading: `aria-disabled="true"` plus `aria-busy="true"`, and the click
  handler returns early while loading. It MUST NOT use the `disabled` attribute, which drops focus to
  `<body>` and removes the button from the tab order.
- **The busy-control pattern** is the rule for **every** control that becomes busy after being pressed,
  here and in later changes (the spec's keyboard requirement; C4's Save, Retry and Overwrite, C5's Render,
  Render anyway, Cancel, Cancel render and row Render):
  - the pressed control gets `aria-disabled="true"` and `aria-busy="true"` while its request is in
    flight, and its handler ignores clicks (and Enter/Space) until the answer, through a ref guard, not
    through `disabled`
  - it never gets the `disabled` attribute, so it keeps keyboard focus and stays in the tab order
  - the **other** controls of a locked form or editor (fields, drag handles, Reset) MAY use `disabled`

  ```tsx
  <button type="button" className="btn btn-secondary"
          aria-disabled={busy || undefined} aria-busy={busy || undefined}
          onClick={() => { if (busy) return; start() }}>
  ```

  Each change verifies it the same way: press Enter on the control with the request held by
  `page.route`, and assert that `document.activeElement` is still that control until the answer.
- The sticky header must never cover keyboard focus (WCAG 2.4.11): `html` sets `scroll-padding-top` to
  `--header-h` plus the height of a sticky panel header, so a focused row link scrolls clear of both.
- Headings: year groups, "Needs attention" and chapters become `<h2>`s in panel headers, replacing
  `<caption>`. Tables reference them with `aria-labelledby`, with ids from `useId()` (chapter names hold
  spaces and non-ASCII letters). An event whose only chapter is the default one gets the section heading
  "Clips", because every section has a heading. `Main` stays reserved for the default chapter beside named
  ones, as the spec says.

**Rationale**:
- It matches the spec's keyboard requirement using native elements only.
- `preventScroll` keeps the kept-list scroll restore intact.

### Tables at every width

**Context**: The plan leaves "tables vs grid rows" to this change. Positional widths are brittle. At 390px a
five-column row cannot fit, and today it scrolls sideways inside `.table-scroll`. Those scroll containers
would also break sticky group headers.

**Explored**:
- **A grid of rows with ARIA table roles.** Every role, header association and column relationship has to be
  rebuilt by hand.
- **Semantic `<table>`s** with `<colgroup>` classes and a narrow reflow via container queries.
- **Hiding columns at narrow widths.** Rejected: it drops facts the spec requires at every width.
- **Adrian Roselli, "Tables, CSS Display Properties, and ARIA".** When `display` changes on table elements,
  some engines (WebKit historically) drop the implicit table semantics. The documented fix is explicit roles.

**Decision**:
- Read-only data stays in `<table className="data-table">`, and widths come from `<colgroup>`:
  - list: `col-date`, `col-event`, `col-clips`, `col-render`, `col-job`
  - attention: `col-folder`, `col-problem`, `col-fix`
  - clips: `col-pos`, `col-file`, `col-status`, `col-size`, `col-mtime`
- Widths are set in the screen stylesheet, and `table-layout: fixed` keeps every year's table aligned. No
  `nth-child` selector remains.
- `.panel` has `container-type: inline-size`. Under `@container (width < 40rem)`, each table reflows:
  - `thead` is visually hidden, not `display: none`
  - each `tr` becomes a small grid with named areas
  - each `td` becomes `display: block`

  Because this changes `display`, every table carries explicit `role="table"`, `rowgroup`, `row`,
  `columnheader` and `cell` attributes.
- The only cell whose value is not self-describing at narrow width is Last job. When the event has a job,
  the cell gets `data-label="Last job"`; an event with no job gets no label, so the cell stays empty at
  every width (the spec's "no job status at all"). The label is shown with
  `content: attr(data-label) / ""`, whose empty alternative text keeps assistive technology on the real
  column header.
- That rule is preceded by a plain `content: attr(data-label)` fallback, for engines above the floor that
  lack the alternative-text syntax (Firefox before 128). Those engines show the label, and may announce it
  once more.
- The list's clip count reads "3 clips" (`plural`) at every width, not a bare "3".
- Folder names, file names and failure details carry `overflow-wrap: anywhere`, as today
  (`app.css:183-185`, `:256-258`), and a pill's words may wrap: `.pill` sets no `nowrap`, so a long label
  such as "missing or invalid date or title" never widens the page at 390px.
- `.table-scroll` wrappers are removed. Panels MUST NOT set `overflow`: their corners are clipped by radii on
  the first and last children, so the sticky `h2` panel headers (`top: var(--header-h)`) work against the
  page scroll.
- The chapter key becomes `chapter.name`, which is unique per event (see Context), in place of the index
  (`EventDetail.tsx:182`). C4 relies on this.

**Rationale**:
- Tables keep native row and column navigation for screen readers. They held 380 rows without
  virtualization (event-detail-screen).
- C4's reorder is an edit-mode list it builds itself, so the read-only tables do not constrain the
  drag-and-drop library.

### Status tones and icons

**Context**: The spec requires words plus an icon for every status, with one tone per status across screens.
Today tones are ad hoc per class: `.pill-fresh`, `.pill-stale`, `.job-failed` and `.clip-status-*`.

**Explored**:
- Adding tone and icon fields to the `labels.ts` maps. Rejected: it changes the shape of every label map
  and of every reader of one, and C4 and C5 both plan to leave `labels.ts` untouched.
- A `switch` per component. Rejected: it is not exhaustive by construction, and the tones would drift
  between screens.
- A separate `Record` per vocabulary in its own module.

**Decision**: `src/events/tones.ts` holds exhaustive maps over the generated unions, so `tsc` fails on a
new member, as `labels.ts` does. The words are unchanged, and come from `labels.ts`.

| Vocabulary | Value | Tone | Icon |
|---|---|---|---|
| verdict | up to date / needs render | `ok` / `warn` | `check` / `refresh` |
| `JobStatus` | queued / running / done / failed / canceled | `idle` / `info` / `ok` / `err` / `idle` | `clock` / `loader` / `check` / `alert-triangle` / `x` |
| `ClipStatus` | active / new / missing / ignored | `idle` / `info` / `err` / `idle` | `check` / `info` / `alert-triangle` / `x` |
| `EventFailure` | every kind | `err` | `alert-triangle` |

```ts
export type StatusLook = { tone: Tone; icon: IconName }
export const JOB_STATUS_LOOK: Record<JobStatus, StatusLook>
export const CLIP_STATUS_LOOK: Record<ClipStatus, StatusLook>
```

- `StalenessCell` and `JobCell` (`common.tsx`) render `<Pill>`s. A running job keeps "Rendering 42%".
- An ignored clip's row stays dimmed (`--fg-muted`) as today.
- The list's "N new" and "N missing" badges are `.badge` with `data-tone="info"` or `data-tone="err"`. Their
  words carry the meaning.
- The list's page header keeps the summary's words and splits them into `.stat` chips: "**7** of 10 events
  need rendering", "**1** needs attention" (only when error rows exist), and a muted "Scanned 14:02:11".
  The spec's "states that 6 of 9 events need rendering" and "1 needs attention" stay literally true.

**Rationale**:
- One lookup per status keeps the tone identical on every screen, and `tsc` enforces completeness.
- Words stay in `labels.ts` and looks in `tones.ts`, so neither map's readers change when the other does.

### Shared primitives

**Context**: C4 and C5 are built in parallel, and both need an icon set, a confirm dialog, toasts, pills,
alerts and buttons (plan "Fixed cross-change names"). This change's own screens use `Icon`, `Pill`, `Alert`,
the skeleton and the buttons. `Dialog` and the toasts have no caller here.

**Explored**:
- Native `<dialog>` with `showModal()`: focus trap, Escape and the top layer come for free. Baseline since
  2022.
- The Popover API for toasts. Not needed: a fixed region is enough, and two live regions carry the
  announcements.
- Icon packages. They are a dependency, which D-8 rules out. The Lucide paths are ISC-licensed.

**Decision** (all under `src/ui/`, named exports only):
- **`Icon.tsx`**:

  ```ts
  export type IconName =
    | 'alert-triangle' | 'arrow-down' | 'arrow-up' | 'check' | 'chevron-left' | 'clock' | 'film'
    | 'grip-vertical' | 'info' | 'loader' | 'monitor' | 'moon' | 'pencil' | 'play' | 'refresh'
    | 'rotate-ccw' | 'save' | 'square' | 'sun' | 'x'
  export function Icon(props: { name: IconName; size?: 16 | 20; label?: string }): JSX.Element
  ```

  - It renders a 24×24-viewBox stroke SVG with `stroke="currentColor"`, `strokeWidth={2}` and
    `focusable="false"`.
  - With no `label` it is `aria-hidden="true"`. With a `label` it has `role="img"` and `aria-label`.
  - The paths live in a `Record<IconName, ReactNode>`, so a name without a path fails `tsc`.
  - The paths are copied once, at implementation time, from the `lucide-static` package's
    `icons/<name>.svg` files (some Lucide names differ, for example `triangle-alert` and `refresh-cw`). The
    file header keeps Lucide's license notice: ISC, including its MIT notice for the portions derived from
    Feather.
- **`Pill.tsx`**: `Pill({ tone, icon, children })` renders `<span className="pill" data-tone={tone}>` with
  the icon and the words. `export type Tone = 'ok' | 'warn' | 'err' | 'info' | 'idle'`.
- **`Alert.tsx`**: `Alert({ tone, title, detail?, action?, role? })` renders a block with the tone's icon, a
  strong title, a muted detail and an optional action node. `title` is a `ReactNode`, so the event page's
  failure keeps its failure-kind `Pill` beside the cause, as today (`EventDetail.tsx:125-128`). `detail` is
  `string | null`. `role` defaults to `alert` and replaces the `.failure` and `.warning` blocks.
- **`Skeleton.tsx`**:
  - `SkeletonRows({ rows })` renders `rows` placeholder rows of `--row-h` height, all `aria-hidden`.
  - `LoadStatus({ message })` renders `<p role="status" className="load-status">{message}</p>`, visible
    muted text. Each screen renders it in **every** state, in its page header, with the read's message
    while loading and an empty string otherwise. Screen readers announce a live region whose text changes
    reliably, but often miss one inserted together with its text, so a Refresh's "Scanning events…" must
    land in a region that already exists. A first read's message appears with the page itself; its heading
    is announced by the focus move.
  - Each page header keeps its read time beside the `LoadStatus` region, as today: "Scanned <time>" on the
    list (`EventList.tsx:244`) and "Read <time>" on the event page (`EventDetail.tsx:166`). These two
    spots are where C5 puts its "Updating…" text for an in-place re-read.
- **`Dialog.tsx`**:

  ```ts
  export function Dialog(props: { open: boolean; title: string; onClose: () => void;
                                  initialFocus?: RefObject<HTMLElement | null>;
                                  children: ReactNode }): JSX.Element
  ```

  - It renders `<dialog className="dialog" aria-labelledby=…>` with an `<h2>` title and `children` (the
    body and the action buttons).
  - When `open` becomes true, it records `document.activeElement` and calls `showModal()`. When `open`
    becomes false, or on unmount, the effect's cleanup calls `close()`.
  - **Initial focus.** Right after `showModal()`, in the same effect, the dialog focuses
    `initialFocus.current` when that prop is given and the element is connected. Without it, the first
    focusable element in `children` gets focus (native `showModal()` behavior, which the dialog relies on
    and does not override). Callers pass a ref to their safe action (C4's "Keep editing" and "Cancel",
    C5's "Keep rendering"). React's `autoFocus` MUST NOT be used for this: React calls `focus()` at
    commit, while the `<dialog>` is still closed, so the call does nothing.
  - The prop is typed `RefObject<HTMLElement | null>` (the plan wrote `RefObject<HTMLElement>`): under
    React 19's types, `useRef<HTMLButtonElement>(null)` returns `RefObject<HTMLButtonElement | null>`,
    which strict `tsc` would not accept for `RefObject<HTMLElement>`. The name and meaning are unchanged.
  - A close the component starts itself MUST NOT call `onClose`: the cleanup sets a ref before `close()`,
    and the `close` event handler clears it and returns. Any other close (Escape, or a browser-forced
    close) calls `onClose`, so Escape counts as cancel. This matters under StrictMode: the simulated
    unmount's `close()` queues a `close` event that fires after the remount's `showModal()`, and without
    the ref it would close a dialog that mounted open.
  - After closing, focus returns to the recorded opener if it is still connected.
  - The enter animation uses `@starting-style`, as progressive enhancement.
- **`toast.ts`** is a module store: an array, listeners, and `useSyncExternalStore`:

  ```ts
  export type ToastTone = 'success' | 'info' | 'error'
  export type ToastOptions = { action?: { label: string; href: string } }
  export type Toast = { id: number; tone: ToastTone; message: string } & ToastOptions
  export const toast: Record<ToastTone, (message: string, options?: ToastOptions) => void>
  export function dismissToast(id: number): void
  export function pauseToasts(paused: boolean): void
  export function useToasts(): readonly Toast[]
  ```

  - Success and info toasts dismiss themselves after 5 s. The timer's remaining time is kept while paused.
  - Errors stay until dismissed.
  - At most three toasts are held. A fourth drops the oldest non-error toast, or the oldest toast when all
    three are errors.
- **`ToastRegion.tsx`**, rendered once by the shell:
  - a fixed region, bottom-right, and bottom full-width below 30rem
  - its bottom offset is `calc(var(--toast-inset-bottom, 0px) + var(--s-4))`. `--toast-inset-bottom` is a
    custom property that defaults to `0` and that this change never sets. It exists for C4's sticky save
    bar: C4 sets it on `:root` to the bar's height while the bar shows (the value it already adds to
    `scroll-padding-bottom`), so a toast never covers Save or Reset at phone width
  - two always-present live containers: `role="status"` for success and info, `role="alert"` for errors
  - each toast shows its tone's icon, the message, the optional action link, and a dismiss button
    (`btn btn-ghost btn-icon`, `Icon name="x" label="Dismiss"`)
  - pointer or focus inside the region pauses the timers
- **Buttons** are classes on native `<button>` and `<a>`: `btn` plus one of `btn-primary`, `btn-secondary`,
  `btn-ghost` or `btn-danger`, plus `btn-icon` for icon-only buttons. Styles exist for `:disabled`,
  `[aria-disabled="true"]` and `[aria-busy="true"]` (a spinning `loader` before the label, motion
  permitting). A busy button is `aria-disabled` + `aria-busy` and ignores clicks, never `disabled` (see
  "App shell, skip control and focus"). There is no Button component: one would only forward attributes.
- **Other classes in `components.css`**: `.panel` (with `.panel-header` and `.panel-body`), `.pill`,
  `.badge`, `.alert`, `.data-table`, `.skeleton`, `.load-status`, `.segmented` (the radio-group look shared by the list
  filter and the theme control), `.stats`/`.stat`, `.visually-hidden`, `.dialog`, `.toast`.

**Rationale**:
- Each primitive is small (under about 80 lines) and uses native behavior.
- The fixed names let C4 and C5 import them blind.
- Leaving out a Button component and a toast library keeps D-8's budget meaningful.

### The events-changed signal

**Context**: The list stays mounted and is never re-read on return (`App.tsx:9-14`). After C4 saves an event
or C5 finishes a render, the list would show stale titles and verdicts.

**Explored**:
- Re-reading the list on every return. Rejected: it breaks the no-request Back behavior that the spec keeps
  for the common case.
- Using the WebSocket. Rejected: it only covers renders, not saves, and it does not exist yet.
- A version counter.

**Decision**: `src/events/changes.ts`:

```ts
export function markEventsChanged(): void      // version += 1, notify
export function currentEventsVersion(): number
export function useEventsVersion(): number     // useSyncExternalStore over the counter
```

- `EventList` records `currentEventsVersion()` at the start of every `load()`, in a ref.
- One effect re-reads when the list is shown and the version is newer:
  `if (!hidden && version !== readVersion.current) load()`, with deps `[hidden, version, load]`. It is
  declared **after** the existing mount effect (`EventList.tsx:164-167`), so on mount the ref already holds
  the version and no second read starts. A mark during an in-flight read changes `version`, so the effect
  starts one more read, which aborts the stale one.
- A re-read keeps `onlyStale`. The scroll offset is best-effort, because the loading state is short and
  `App`'s restore clamps to it.
- A mark while the list is visible also re-reads, and the loading state replaces the content. C5 decides
  whether a visible list should refresh in the background, and owns that spec change.
- The signal is per tab and in memory. A reload reads everything anyway.
- The signal says only that *some* event changed, not how the client learned it. C5 also marks when a job
  it did not start finishes (seen on the WebSocket), so the spec says "the client has recorded that an
  event changed", not "changed through this client".
- This change has no caller of `markEventsChanged()`. C4 calls it after a save, and C5 after a `done`.

**Rationale**:
- A counter is the smallest thing that answers "is my last read older than the last change?" and it
  needs no event payload.
- It keeps the common Back path request-free, as the spec requires.

### Verifying what nothing calls yet

**Context**: `Dialog`, the toasts and the events-changed signal have no caller in this change. The built
bundle exposes no modules, and the Vite dev server's proxy is hard-wired to port 8080, where a stale server
lives (`vite.config.ts:5`).

**Explored**:
- A test runner (Vitest with jsdom). Rejected: the `web-app` spec requires a justified proposal for one,
  and jsdom does not implement `showModal()`.
- A temporary caller in a screen, removed before the change ends. Rejected: the verified code would not be
  the code that ships.
- Driving the real modules through the Vite dev server, which serves each source file as its own module.

**Decision**:
- `vite.config.ts` reads `AUTO_REEL_API` through Vite's `loadEnv(mode, '.', '')`, which merges
  `process.env` without referencing `process`, so `tsc` still passes without `@types/node`. It falls back to
  `http://127.0.0.1:8080`.
- Task 6.1 runs Vite on port `5100+N` against the agent's service on `8100+N`. It drives the real module
  instances from Playwright:
  - `import('/src/ui/toast.ts')`
  - `import('/src/events/changes.ts')`, which is the same module instance `EventList` imports, because
    Vite serves both under the same URL
  - a `Dialog` mounted inside `<StrictMode>` with the app's own React, resolved from the import URLs in the
    transformed `/src/ui/Dialog.tsx` (a second React copy would break hooks)
- The harness lives only in the scratchpad.

**Rationale**:
- It verifies the real code with no test-only code in the repo. D-8 and the `web-app` spec forbid committed
  browser automation.
- The override also lets C4 and C5 agents use Vite against their own ports.

## Failure behavior and idempotency

- **Nothing writes.** Every request is still a GET. The only new read is the events-changed re-read, which
  nothing triggers in this change.
- **Storage failures** (a private window, blocked site data, a quota error) are caught. The theme falls back
  to System, or to the choice for this page only. No error is shown or logged as a failure.
- **Failures keep their causes.** Loading and failed reads still replace content. The `Alert` shows the same
  cause and detail strings as before (`describeProblem` is unchanged in both screens).
- **Timers.** A toast timer or a dialog left open by an unmounting component is cleaned up: the store clears
  timers on dismiss, and `Dialog` closes itself on unmount.
- **Re-run, `--force` and worker restart** do not apply: no job, render or engine path is touched.
  Reloading the page re-applies the stored theme and re-reads as before.
- **No `RENDER_GRAPH_VERSION` bump**, and no API, schema or migration change.

## Risks / Trade-offs

- **[The change is large for Principle VIII]** Two screens restyled, a shell, and seven primitives.
  - It stays in one package with one capability delta, because splitting it would make C4 and C5 wait on
    two changes.
  - **Fallback split** if the apply session overruns: stop after task group 3, move the list's
    events-changed effect from 4.1 into it, and ship tokens, shell and primitives as `web-design-system`
    with the old screens still readable. Put the rest of group 4 in a follow-up change,
    `web-screens-restyle`, and move the phone-width, placeholder and keyboard requirements into it. C4 and
    C5 would then gate on both changes (C5 modifies the placeholder requirement).
- **[Primitives with no caller (Principle VII)]** `Dialog`, the toasts and `markEventsChanged` are unused
  here.
  - They are justified only by C4 and C5 being built in parallel.
  - They are verified by the harness in 6.1, so neither slice inherits an untested primitive. They are kept
    minimal, with no options beyond what C4 and C5 name.
- **[Contrast chosen by eye]** The token values are unmeasured. → 6.1 measures every pair with axe in both
  schemes, and this change fixes the tokens before it is done.
- **[Table semantics in the narrow reflow]** Changing `display` can drop implicit roles. → Explicit roles are
  set, and 6.1 checks the accessibility snapshot at 390px in Chromium and in WebKit (the engine with the
  history of dropping them). Both ship in the Playwright image.
- **[Browsers older than the floor]** Before `light-dark()`, colors fall back to browser defaults. →
  Documented in `web/README.md`. The operator's browser is evergreen.
- **[`theme-color` follows the OS, not the override]** It is cosmetic only, and affects browser chrome on
  some platforms.
- **[Focus on the list heading after Back]** The next Tab goes to the toolbar at the top while the page may
  be scrolled deep. → Accepted, as the spec fixes the heading as the target. Focusing the last-opened row is
  a possible later refinement.
- **[Parallel slices and spec text]** A MODIFIED block replaces a requirement's whole text, and C4 and C5
  archive in an order not known in advance. Requirement ownership in `web-app` after this change:
  - This change owns the three requirements it modifies: "The event list answers what needs rendering,
    from disk", "Each event opens on its own page" and "The event page shows the event's chapters and
    clips". C4 and C5 MUST NOT MODIFY any of them. "Each event opens on its own page" is included because
    its "SHALL NOT re-read the list" on return is what the events-changed re-read makes false; C4's
    error-row link is therefore its own ADDED requirement.
  - Of the requirements this change ADDS, only C5 MAY MODIFY one: "A read in progress is shown as a
    placeholder and announced" (its in-place re-read). C4 MUST NOT modify it. No other ADDED requirement
    here is modified by C4 or C5.
  - C4 and C5 otherwise ADD their own requirements, and rebase each MODIFIED block on the then-current
    spec before archiving (plan rule 3). This change archives first, so C5's block has a target.
- **[Busy controls in later slices]** The keyboard requirement covers every busy control, including C4's
  Save and C5's Render. → The design states the busy-control pattern ("App shell, skip control and
  focus"), the button classes style it, and each slice's verification holds the request and checks
  `document.activeElement`.
- **[Toasts over sticky bars]** A toast could cover a sticky bar at the bottom of the page. →
  `--toast-inset-bottom` lifts the region; the page that owns the bar sets it.
- **[Lucide-derived paths]** → Lucide's license notice (ISC, plus Feather's MIT) is kept in `Icon.tsx`.
  Nothing is fetched at build or run time.

## Migration Plan

- Rebuild `web/dist` with the `web/README.md` container command. `serve` mounts it as before.
- There is no data migration. The stored theme key is new, and absent means System.
- Rollback is reverting the change. A leftover `auto-reel:theme` key is harmless, and the old CSS ignores
  `data-theme`.
