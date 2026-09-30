# `web/` — the browser client (GUI v1)

React 19 + Vite + TypeScript, built ahead of time into static assets that
`auto-reel serve` mounts at `/` (decision **D-8**, HLD §4.10). **No Node process
exists at runtime** — the deployment stays the single Python process, and the
service starts normally when `dist/` is absent.

Two screens so far, both only read. The **event list** (slice B of §4.10) answers
"which events need a render, and why": every event grouped by year, its clip
counts, its staleness verdict with reasons in words, and its latest job. Each
event's title opens its **event page** (slice C) at `#/event/<id>`: its chapters
and clips in play order, each clip's status, size and time, and any clip
`reel.yaml` lists that is missing from disk. Both read on open and on Refresh —
never poll, never cache — and report a failed read by its cause. The list stays
mounted while an event page is open, so Back returns to it without a new read —
unless the client recorded meanwhile that an event changed (`markEventsChanged()`
in `events/changes.ts`, called by the slices that write or render): then the list
reads again when shown, keeping its filter. Every page sits in one shell: a sticky
header with the Events link and a System / Light / Dark theme control, remembered
per browser (see "Design system").

```
src/
├── main.tsx              mounts App; imports styles/index.css first
├── App.tsx               the route switch inside the shell; keeps the list mounted
├── route.ts              hash routes (#/event/<id>) — no router library
├── styles/
│   ├── index.css         the cascade layer order, then the four files below
│   ├── reset.css         box sizing, zeroed margins; [hidden] always wins
│   ├── tokens.css        colors (OKLCH, light-dark()), spacing, radii, type, motion
│   ├── base.css          elements, typographically only
│   └── components.css    buttons, panels, data tables, pills, alerts, dialog, toasts
├── shell/
│   ├── AppShell.tsx      skip control, sticky header, theme control, toast region
│   ├── theme.ts          System / Light / Dark, kept per browser
│   └── shell.css         the header and the page frame
├── ui/
│   ├── Icon.tsx          inline-SVG icons (Lucide paths, ISC; notice in the file)
│   ├── Pill.tsx          a status: icon + words on a tone
│   ├── Alert.tsx         an inline message: tone, title, detail, action
│   ├── Skeleton.tsx      placeholder rows, and the announced read status
│   ├── Dialog.tsx        a modal over the native <dialog>
│   ├── toast.ts          the toast store: toast.success / info / error
│   └── ToastRegion.tsx   where toasts appear (rendered once by the shell)
├── api/
│   ├── schema.d.ts       generated (see below)
│   ├── http.ts           shared response reading and problem parsing
│   ├── events.ts         the list fetch: URL, status codes
│   └── event.ts          the one-event fetch: URL, status codes
└── events/
    ├── EventList.tsx     the list: load/refresh, summary, filter, year panels
    ├── EventDetail.tsx   the event page: status, counts, per-chapter clip panels
    ├── list.css          the list's layout and column widths
    ├── detail.css        the event page's layout and column widths
    ├── common.tsx        helpers both screens share (job cell, sizes, verdict)
    ├── changes.ts        "an event changed": markEventsChanged(), useEventsVersion()
    ├── grouping.ts       groupByYear, needsRender (pure)
    ├── labels.ts         words for reasons, job statuses, failures, clip statuses
    └── tones.ts          the tone and icon of each status (the words stay in labels.ts)
```

`labels.ts` maps each vocabulary through a `Record` over its generated union, so
a reason, job status, failure kind or clip status added, renamed or removed in the engine is a
`tsc --noEmit` error until it is given words.

## The Node toolchain runs in podman

Nothing is installed on the host — the same arrangement as the containerized
Postgres test fixture. Run all four commands from the **repository root**:

```bash
# install dependencies (writes web/node_modules/ and web/package-lock.json)
podman run --rm -v "$PWD/web:/app:Z" -w /app docker.io/library/node:22 npm install

# dev server on http://127.0.0.1:5173, proxying /api (and the WS) to the service;
# --network host is what lets the proxy reach 127.0.0.1:8080
podman run --rm --network host -v "$PWD/web:/app:Z" -w /app docker.io/library/node:22 \
    npx vite --host 127.0.0.1 --port 5173

# production build → web/dist/ (runs `tsc --noEmit` first)
podman run --rm -v "$PWD/web:/app:Z" -w /app docker.io/library/node:22 npm run build

# the frontend gate on its own
podman run --rm -v "$PWD/web:/app:Z" -w /app docker.io/library/node:22 npx tsc --noEmit
```

`npm run dev` expects a running `auto-reel serve` on `127.0.0.1:8080` (its default
bind). To proxy to a service elsewhere, set `AUTO_REEL_API`, for example
`podman run --rm --network host -e AUTO_REEL_API=http://127.0.0.1:8101 …` with the
dev-server command above. Client code addresses the API **by path alone** — never
an absolute base URL — so the same code works behind the dev proxy and when the
service serves the built assets. Same origin either way; the service needs no CORS.

Two things to know when containers run side by side:

- `:Z` gives a mount a private SELinux label. A second container that mounts `web/`
  with `:Z` (for example `npm run build`) relabels it and cuts off a running dev
  server (`EACCES` on `.vite/deps`). Don't build while Vite runs, or mount with `:z`
  in both.
- Screens checked ad hoc in the Playwright container (never committed, see "Checks")
  render `system-ui` in a CJK fallback font with no bold face. For representative
  screenshots, copy the host's Noto Sans files into the mounted scratch directory and
  run with `-e FONTCONFIG_FILE=/work/fonts/fonts.conf`:

  ```xml
  <fontconfig>
    <include ignore_missing="yes">/etc/fonts/fonts.conf</include>
    <dir>/work/fonts</dir>
    <match target="pattern"><test name="family"><string>system-ui</string></test>
      <edit name="family" mode="assign" binding="strong"><string>Noto Sans</string></edit></match>
    <alias binding="strong"><family>sans-serif</family><prefer><family>Noto Sans</family></prefer></alias>
  </fontconfig>
  ```

## A library to develop against

The shared fixture holds one event, which cannot show what the screens must render.
`scripts/make_dev_library.py` builds a small real-footage library from it (the fixture
is only read). It cuts 6 s stream-copied clips and lays out 11 events across 2023 and
2024: 10 that list normally, plus 1 that needs attention. Part of the library is rendered through
the real queue, then disk is edited so the screens show every state:

- fresh, and stale for `editorial`, `output`, `clip_set` and `no_manifest`
- NEW and MISSING clips
- a named chapter, an IGNORED clip and a NEW clip inside a chapter (`2024-08-20 - Två kapitel -
  Tjörn`: a `Main` table and a `Kvällen` table on its event page)
- an event whose folder name (`2024/Blandat`) has no date, dated by its `reel.yaml` (`2024-11-02`)
- a same-name output clash (`2024-07-14 - Kalas` and `2024-07-14 - kalas`, same date, differing
  only in case)
- latest jobs that are `done`, `failed` and `queued`
- an event the list cannot read (`2024-02-30 - Omöjligt datum`, an impossible date), shown as an
  error row under "Needs attention"

The service needs Postgres even to list events (the list carries each event's latest
job). One-time setup, from the repository root:

```bash
# a persistent dev database at the dev-default URL (named volume survives restarts)
podman run -d --name auto-reel-ng-dev-db \
    -e POSTGRES_USER=auto_reel_ng -e POSTGRES_PASSWORD=auto_reel_ng -e POSTGRES_DB=auto_reel_ng \
    -v auto-reel-ng-dev-db:/var/lib/postgresql/data -p 127.0.0.1:5432:5432 \
    docker.io/library/postgres:16-alpine
.venv/bin/python -m alembic upgrade head

# build (or rebuild from scratch) the library beside the fixture
.venv/bin/python scripts/make_dev_library.py ../auto-reel-dev
```

Then run the service against it and the dev server as above, and open
<http://127.0.0.1:5173/>:

```bash
.venv/bin/auto-reel serve ../auto-reel-dev/library   # after a reboot: podman start auto-reel-ng-dev-db
```

## Regenerating the API types

The client's types are **generated, never hand-written**. Two committed artifacts:

```
auto_reel_ng/api response models
        │  app.openapi()
        ▼
   web/openapi.json          ◄── pytest fails when this is stale
        │  openapi-typescript
        ▼
   web/src/api/schema.d.ts   ◄── tsc --noEmit fails when client code reads
        │                        what the types no longer describe
        ▼
      client code
```

After any change to an endpoint's request or response model, run **both**, from the
repository root:

```bash
.venv/bin/python -m auto_reel_ng.api.openapi > web/openapi.json
podman run --rm -v "$PWD/web:/app:Z" -w /app docker.io/library/node:22 npm run generate:types
```

Both files are committed. Hand-editing either is pointless — regenerating
overwrites it — and `tests/test_api_openapi.py` fails, naming the disagreement,
until `web/openapi.json` matches what the application produces.

## Design system

Plain CSS, inline SVG and native HTML, inside the dependency budget below: no CSS
framework, no component library, no icon package, no web font (decision **D-10**,
HLD §7).

- **Layers.** `styles/index.css` declares `@layer reset, tokens, base, components,
  screens;` once, and `main.tsx` imports it first. Every stylesheet wraps all of its
  rules in exactly one of those layers — unlayered CSS would beat every layer. A
  screen's styles live next to it (`events/list.css`), and a later change adds its
  **own** file in `@layer components` or `@layer screens` (`edit/edit.css`,
  `jobs/jobs.css`) rather than editing one of these for its own rules. `base` sets
  no layout on elements; layout lives in classes.
- **Tokens** (`styles/tokens.css`) are the only place a color, size or duration is
  chosen. Every color is one OKLCH `light-dark(<light>, <dark>)` value: neutrals on
  hue 260, one indigo accent on 265, and five status tones (`ok`, `warn`, `err`,
  `info`, `idle`), each with a `-bg`, a `-fg` and a solid. Text pairs meet WCAG AA
  in both schemes; `--fg-subtle` is for icons and borders, never text. The scheme
  follows the OS until the header's theme control sets `data-theme` on `<html>`
  (stored per browser under `auto-reel:theme`, and applied before the first paint
  by the inline script in `index.html`).
- **Status is never color alone.** A status is a `Pill`: an icon and its words, on
  its tone. Tone and icon come from `events/tones.ts`, the words from `labels.ts`.
- **Shared pieces, by fixed name.** `ui/Icon` (`<Icon name="…" />`, decorative unless
  given a `label`), `ui/Pill`, `ui/Alert` (with an `action` slot; `role="alert"` by
  default), `ui/Skeleton` (`SkeletonRows`, `LoadStatus`), `ui/Dialog`, `ui/toast`
  with `ui/ToastRegion`, and `markEventsChanged()`. Classes on native elements:
  `btn` plus `btn-primary`, `btn-secondary`, `btn-ghost` or `btn-danger` (plus
  `btn-icon`); `pill`, `badge` and `alert` with `data-tone`; `panel` (with
  `panel-header` and `panel-meta`); `data-table`; `segmented`; `dialog-actions`;
  `visually-hidden`. The header's `<div className="shell-status">` is the slot for
  status indicators.
- **Busy controls.** A control the operator pressed that now waits for an answer
  gets `aria-disabled="true"` and `aria-busy="true"` and ignores clicks (a ref
  guard) until the answer. It never gets the `disabled` attribute, which drops
  keyboard focus to `<body>`. `.btn[aria-busy="true"]` shows a loader. Other
  controls of a locked form may use `disabled`.
- **Dialogs.** `<Dialog open title onClose initialFocus>`: pass the safe action's
  ref as `initialFocus` — never React's `autoFocus`, which fires while the dialog
  is still closed. Escape calls `onClose`; a close the caller starts does not.
- **Toasts** appear bottom right. A page with a sticky bar at the bottom sets
  `--toast-inset-bottom` on `:root` to the bar's height, so no toast covers it.
- **Motion.** Every `transition` takes its duration from a `--dur-*` token; the
  tokens become `0ms` under `prefers-reduced-motion: reduce`. Every `animation` and
  its `@keyframes` sit inside `@media (prefers-reduced-motion: no-preference)`, with
  a literal loop duration (for example `1.2s`), never a `--dur-*` token. Each change
  runs this gate over its own directory:

  ```bash
  grep -rnE 'transition[^;]*[0-9.]+m?s\b' <dir>            # prints nothing
  grep -rn 'animation[^;]*--dur-' <dir>                    # prints nothing
  grep -rnE '(^|[^-])animation(-name)?:|@keyframes' <dir>  # each hit inside a no-preference block
  ```

- **Support floor.** Evergreen browsers from 2024 on: Chrome and Edge 123, Firefox
  120, Safari 17.5 — the `light-dark()` floor. `vite.config.ts` sets
  `build.cssTarget` to them, so the build keeps native nesting and `light-dark()`.
  An older engine falls back to browser-default colors; nothing stops working.

## Dependency budget

`react`, `react-dom`, `vite`, `@vitejs/plugin-react`, `typescript`, and
`openapi-typescript` (dev). **No component library, no CSS framework, no router,
and no state-management or data-fetching library at GUI v1.** Any addition must be
justified in the proposal of the slice that demonstrably needs it — the
drag-and-drop library arrives with the reorder slice, not here. The design system
adds nothing to it.

## Checks

`tsc --noEmit` is the whole frontend gate for GUI v1. There is deliberately **no
test runner and no browser automation**: the types are generated from the schema,
so drift is a compile error, and the API's behavior is covered by `pytest`. A later
slice with logic worth unit-testing may propose a runner, with its justification.
