# `web/` — the browser client (GUI v1)

React 19 + Vite + TypeScript, built ahead of time into static assets that
`auto-reel serve` mounts at `/` (decision **D-8**, HLD §4.10). **No Node process
exists at runtime** — the deployment stays the single Python process, and the
service starts normally when `dist/` is absent.

Two screens so far. The **event list** (slice B of §4.10) answers
"which events need a render, and why": every event grouped by year, its clip
counts, its staleness verdict with reasons in words, and its latest job. A click
anywhere on an event's row (not on its controls, and not one that selects text)
opens its **event page** (slice C) at `#/event/<id>`, as its title does; the title
link stays the row's one keyboard stop. Two events that would read the same (the
same date, title and location, ignoring case) also show their folder's path, for
example `2024/2024-07-14 - Kalas`, and say that they read the same as another
event; the title link is described by both, the note first, since two paths can
differ only in a letter's case, which screen readers do not voice. An empty
library says so and how to add an event; when the Needs render choice hides every
event, the list says nothing needs rendering and offers **Show all events**, which
hands focus back to the All choice.
Each finished read and each filter change is announced with the counts. The event
page shows the event's facts, with the folder name beside a title that differs from
it; one render region holding the verdict and the latest job (when the verdict says
"movie name changed", because the title, date or location changed since the last
render, it adds on a line of its own that the next render saves the movie under its
new name and that the movie under its old name stays on disk); then its chapters,
each listing the clips it plays, numbered in play order, and then its ignored clips,
unnumbered. Each clip shows its status (an included clip's quietly, so the
exceptions stand out), size and time; a clip from another folder is named by its
path in the event folder; and any clip `reel.yaml` lists that is missing from disk
is named. A clip with **cuts** (`reel.yaml`'s `trims`: spans the movie leaves out, D-D)
shows, under its name, how many and the time they cut out ("2 cuts · −4.5 s"), a
disclosure (`<details>`) that lists them; the page reads them with `GET …/reel` after
each event read, writes nothing, and if that read fails shows the clips without cuts and
a note that says why. Both read on open and on Refresh — no timer polling (job state arrives
over the jobs WebSocket), never a cache — and report a failed read by its cause,
telling a service that did not answer ("not reachable", with what to check) from
one that sent an answer its route does not publish ("an unexpected answer", with
the request, its path decoded, the status, and where to look). Each clip row, on
the event page and in Edit mode, shows a frame from its clip (the service's
thumbnail, D-11; 80 × 45, and 128 × 72 in the chapter tables at desktop width):
requested only
as its row nears the view and behind the page's own requests, in a box sized before
it arrives, and kept by the browser while the clip is unchanged. A frame the service
cannot give shows "No preview"; a missing clip asks for none and shows an empty
outline. The list stays mounted while an event page is
open, so Back returns to it without a new read —
unless the client recorded meanwhile that an event changed (`markEventsChanged()`
in `events/changes.ts`, called by the slices that write or render): then the list
reads again when shown, in place, keeping its rows, filter and scroll until the new
read answers. Every page sits in one shell: a sticky header with the Events link,
the jobs connection (Live, Connecting… or Reconnecting…, and while live how many
jobs render and wait) and a System / Light / Dark theme control, remembered per
browser (see "Design system").

**Rendering** (slice E). An event's page offers **Render** when it needs a render,
or **Render anyway** (confirmed) when it is up to date, and follows the job live:
waiting for a worker, a progress bar with its percentage and a time-left estimate,
cancelling, and how it ended — a failure with the service's error text. Every job
shown is dated by its state — when it finished (rendered) or ended (failed or
canceled), started or was queued — whether it came from the connection or a read. **Cancel**
stops a queued job at once and asks first for a running one, and for any job while the
connection is down. Each list row shows its
event's job live and offers a compact Render; a finished render re-reads the list and
the page in place, keeping what is shown until the new read answers. One WebSocket
per tab (`src/jobs/store.ts`) carries every job, reconnects by itself, and reads once any
job that ended while it was down. A row's Render is confirmed to assistive technology
only, since the row shows its job and a toast would cover the rows below; toasts, naming
each event by its title and date, tell how renders started in the tab ended.
Jobs progress only while an `auto-reel worker` runs against the same database; with
none, a job shows "Waiting for a worker". While an event's `reel.yaml` lists a clip
missing from disk, its render would fail, so neither the page nor the row offers one:
the page says which clip (or how many) and to restore it or remove it in Edit mode,
and the row says "Blocked by missing clips". A job already queued keeps its Cancel.

The event page's **Edit mode** (slice D) is the client's first write. **Edit** reads the
event's `reel.yaml` (`GET …/reel` and its `ETag`) and turns the page into an editor: the
title, date, location and description as `reel.yaml` itself says them (an empty field
inherits from the folder name, and says so), and each chapter's clips as a list to
reorder — drag a clip's handle (mouse, pen or touch), lift it from the keyboard (Space
or Enter, the arrows, Space or Enter; Escape cancels), or press its Move up / Move down.
The rows keep the table's columns (`--clip-*`), so entering Edit mode moves nothing but
the position number, and they name each clip as the table does (`clipNames`), a folder
part included where a chapter lists a clip from another folder. A drag or a Move up /
Move down never takes a clip into another chapter; ignored clips are listed but never
move. Each chapter's own tools row, under its heading, edits the chapters themselves
(**D-13**): **Rename…** (every chapter but the event's own, which keeps no name: its
title card is the event's), **Move up** / **Move down**, **Delete** (only once the
chapter plays no clip, and for the event's own chapter only once it lists no ignored
clip; until Save it stays in its place with **Undo**), and **Move clips…**, a dialog
that moves the picked clips (on disk only, checkboxes, Enter moves) to the end of
another chapter, a clip moved back returning to its place. **Add chapter** follows the
last chapter. A name is trimmed, must not be empty, and must differ, ignoring case,
from every other chapter's name and from `Main`. Wherever an edit changes what a name
means for clips added to a folder later (D-12: they join the chapter named exactly
after their folder, else the event's own), the name dialog and the chapter say so. A
save that changes the chapter list writes every chapter as shown, so every NEW clip
joins `reel.yaml` where the page shows it. A clip moved in shows where it came from;
a chapter saved without clips reads "No clips" on the event page. A chapter's heading counts the clips
it plays; its removed and ignored lists count their own. A missing clip (listed in
`reel.yaml`, not on disk) has a **Remove**, under its name (after its facts on a narrow
panel), that takes it out of the play order into a list captioned, for example, "1 clip
removed from reel.yaml when you save", with **Undo** until Save; Save then drops only
its `reel.yaml` entry and its own per-clip properties, and no file on disk is touched.
Every clip on disk that a chapter plays has a **Cuts** control after its move buttons
(under its name on a wide panel; under the handle, with the count only, on a narrow one)
that shows a panel under the row (**D-14**): the clip's cuts (start → end, length, the
reason in words; `manual` reads "Cut by hand") and two typed times, as seconds (`75.5`),
`m:ss` (`1:15.5`) or `h:mm:ss` (`1:01:15.5`), with up to three decimals after `.` or `,`.
**Add cut** refuses, at the field and in words, a time it cannot read, an end that is not
after the start, and an overlap with another cut; it cannot refuse a cut past the clip's
end (no read gives a clip's length), so the panel says the render stops it there and that
a cut over the whole clip leaves the clip out. A cut made here is saved with the reason
`manual`. **Remove** keeps a cut read from `reel.yaml` listed, struck through, with
**Undo** (refused, in words, when another cut now overlaps it); a cut added in this Edit
mode just goes. A time typed but not added counts as unsaved, is named in the save bar
("Cut typed on s1710001.mp4, not added") and holds Save back, as a date typed in part
does; it survives hiding the panel and Move clips, since the editor, not the row, holds
the panel's state. A save writes only the changed clips' `trims` (their title-clip choice,
rotation and exclusion as read; no empty entry), and a cut on a NEW clip writes its
chapter, since `reel.yaml` refuses properties for a clip no chapter lists. A missing
clip shows how many cuts it has, and offers no Cuts control. A
save bar says what changed, with one primary action: **Save**, or a failure's way
on while it holds Save back (Reload latest after a conflict, Back to the event list for
a vanished event). It is held at the window's bottom while it takes at most two fifths
of the window and the window is at least 28rem (448px) tall, which leaves room for the
sticky header, a chapter heading and a whole clip row; otherwise (a failed save in a
short window, any bar at 400 % zoom) it rests in the page after the last chapter. A
save's answer, and every zoom or resize while the bar rests, keeps its focused control
in the window, unless the operator scrolled it away (a `resize` that changes no size,
as a phone's URL bar fires, is ignored). Keyboard focus that lands partly hidden
(outside the window, or under the sticky header, a chapter heading or the held bar;
the description field, whose caret alone the browser would scroll to) is brought into
view whole; focus from a pointer press never scrolls, so the press lands where made.
Save sends one whole-document `PUT` under `If-Match` with only the
operator's edits applied (`edit/draft.ts`); a failure keeps the edits and says why, in a
compact alert inside the bar that fits a 320px window (a third of a phone's height for a
conflict, two fifths with the service's full detail), and a conflict offers Reload
latest or Overwrite with mine. A save that gets no answer says the service is not
reachable, without the browser's error text, and an error in the page itself says so,
never "not reachable". A successful save is confirmed by a toast that names the event by
its title and date. When the `reel.yaml` read fails, **Try again** keeps the failure and
its focus while it reads, then moves focus to the fields' heading. A save never enqueues
a render. The list's "Needs attention" folder names open their event's page; when an
event's date or title is unusable, that page shows the failure and a form to fix them.

Unsaved edits are never discarded silently: closing or reloading the tab gets the
browser's own prompt, and Back, Forward, a link, a typed address, Refresh and Stop
editing ask "Discard unsaved changes?" first. Each history entry the client accepts
carries its index in `history.state` (`route.ts` stamps the entry shown when the app
loads, and each new one), so a refused Back or Forward is undone by going back the
other way and the history stays as it was; Discard redoes the move. A refused link or
typed address stays behind as a Forward entry. While a save is in flight nothing
leaves: Refresh and Stop editing wait, and a navigation is undone with a note that
the save is still running.

```
src/
├── main.tsx              mounts App; imports styles/index.css first
├── App.tsx               the route switch inside the shell; keeps the list mounted
├── route.ts              hash routes (#/event/<id>) and the unsaved-edit navigation guard — no router library
├── format.ts             formatInstant: the one way every time is written (see "Design system")
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
│   ├── toast.ts          the toast store: toast.success / info / error, keepToastsClearOf
│   └── ToastRegion.tsx   where toasts appear (rendered once by the shell)
├── api/
│   ├── schema.d.ts       generated (see below)
│   ├── http.ts           shared response reading and problem parsing; no answer vs an unpublished one
│   ├── events.ts         the list fetch: URL, status codes
│   ├── event.ts          the one-event fetch: URL, status codes
│   ├── jobs.ts           enqueue, one job, cancel: URLs, status codes; the jobs WebSocket URL
│   ├── reel.ts           the editorial read and write: ETag in, If-Match out
│   └── thumbnail.ts      a clip's thumbnail URL, typed from the schema (no fetch: an <img> asks)
├── edit/
│   ├── EventEditor.tsx   Edit mode: the reel read, chapter edits, the save bar, saves and failures
│   ├── ClipOrderList.tsx one chapter's clips to reorder: drag, keyboard, buttons; Remove / Undo
│   ├── ChapterTools.tsx  a chapter's tools row, a deleted chapter's placeholder, Add chapter
│   ├── ChapterDialogs.tsx the name dialog (Add chapter, Rename…) and Move clips
│   ├── chapterNames.ts   chapter name rules and what a name means for later clips (pure)
│   ├── MetadataForm.tsx  title, date, location, description, and inherited values
│   ├── SaveBar.tsx       the save bar and a failed save's alert
│   ├── draft.ts          the edit model: chapters, write body, moved and removed clips, dirty (pure)
│   ├── unsaved.ts        the unsaved-changes guard and its question
│   ├── chapters.css      the chapter tools, the deleted placeholder and the chapter dialogs
│   └── edit.css          Edit mode's fields, rows and save bar
├── cuts/
│   ├── times.ts          typed times read and written, a cut's checks, the cut words and reasons (pure)
│   ├── CutsPanel.tsx     Edit mode's Cuts control and panel, and the cut list both views share
│   ├── ReadCuts.tsx      the event page's cut indicator and list, and the read of its cuts
│   └── cuts.css          the control, the panel and the event page's indicator
├── jobs/
│   ├── store.ts          the one jobs WebSocket: live jobs, reconnect, endings (toasts, re-reads)
│   ├── useJob.ts         which job an event shows (live or last read); the connection's counts
│   ├── eta.ts            the time-left estimate (pure)
│   ├── labels.ts         words for cancel outcomes, the connection and a held-back render
│   ├── JobsIndicator.tsx the header's connection state and counts
│   ├── announce.ts       what the slice tells assistive technology only (a row's Render)
│   ├── JobProgress.tsx   a job's status words, bar and figures
│   ├── RenderControl.tsx the event page's Render, Render anyway and Cancel region
│   ├── LiveJobCell.tsx   a list row's live job cell and compact Render
│   └── jobs.css          this slice's styles
└── events/
    ├── EventList.tsx     the list: load/refresh, summary, filter, year panels
    ├── EventDetail.tsx   the event page: status, counts, clip panels, the Edit toggle and the needs-attention form
    ├── ClipThumb.tsx     a clip row's thumbnail: lazy, loading, "No preview", missing
    ├── list.css          the list's layout and column widths
    ├── detail.css        the event page's layout, render region and clip column properties
    ├── thumbs.css        the thumbnail's 16:9 box and its states
    ├── common.tsx        helpers both screens share (file names, sizes, verdict, failure sentences) and clip names
    ├── changes.ts        "an event changed": markEventsChanged(), useEventsVersion()
    ├── grouping.ts       groupByYear, needsRender, lookAlikes (pure)
    ├── labels.ts         words for reasons, job statuses, failures, clip statuses, unanswered requests
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
With the service down, Vite's proxy answers each request itself with a bare 500, so
under `npm run dev` the screens say the service sent an unexpected answer, where the
built client served by `auto-reel serve` says it is not reachable.

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

- fresh, and stale for `editorial`, `output_renamed` (`2024-06-27 - Grillning med grannar`,
  retitled after its render, so its movie is still on disk under the old name), `clip_set`
  and `no_manifest`; no event is stale for `output` until its movie is removed by hand
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

Renders scheduled from the GUI run only while a worker runs against the same database
(`--device cpu` renders without a GPU):

```bash
.venv/bin/auto-reel worker ../auto-reel-dev/library --device cpu
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
  by the inline script in `index.html`). The control and that script also set both
  `theme-color` metas, so the browser's own interface color is the chosen scheme's
  page background; System gives each meta its OS scheme's color back.
- **Status is never color alone.** A status is a `Pill`: an icon and its words, on
  its tone. Tone and icon come from `events/tones.ts`, the words from `labels.ts`.
  The usual state of a clip row, included, keeps its words and icon without the
  pill's fill and edge (`events/detail.css`, in both views), so the exceptions stand out.
- **Clip columns.** The clip tables publish their widths as `--clip-col-pos`,
  `--clip-thumb-w`, `--clip-col-status`, `--clip-col-size` and `--clip-col-mtime` on
  `.event-detail` (`events/detail.css`; an 8rem frame in a panel of 64rem or more,
  else 5rem), for Edit mode's grid to line up with them.
- **Times.** Every time a screen shows is written by `src/format.ts`
  (`formatInstant`): short month and day, hour and minute, the year only when it is
  not the current one, never seconds, in the browser's locale; the exact instant
  stays in `<time dateTime>`. Event dates are calendar dates and stay `YYYY-MM-DD`,
  as the folders write them.
- **Hover means a target.** Only table rows that open something take a hover fill
  (the list's event rows), and only for a pointer that hovers (`@media (hover:
  hover)`), since a touch screen keeps `:hover` on the last row tapped; "Needs
  attention" rows and the event page's clip table take none. Edit mode's clip rows
  keep their own hover, which brings out their drag handle and move buttons.
- **Shared pieces, by fixed name.** `ui/Icon` (`<Icon name="…" />`, decorative unless
  given a `label`), `ui/Pill`, `ui/Alert` (with an `action` slot; `role="alert"` by
  default), `ui/Skeleton` (`SkeletonRows`, `LoadStatus`), `ui/Dialog`, `ui/toast`
  with `ui/ToastRegion`, and `markEventsChanged()`. Classes on native elements:
  `btn` plus `btn-primary`, `btn-secondary`, `btn-ghost` or `btn-danger` (plus
  `btn-icon`, or `btn-compact` for a control inside a row); `pill`, `badge` and
  `alert` with `data-tone`; `panel` (with `panel-header` and `panel-meta`);
  `data-table`; `segmented`; `dialog-fields`, `dialog-actions`; `visually-hidden`. The header's
  `<div className="shell-status">` is the slot for status indicators.
- **Busy controls.** A control the operator pressed that now waits for an answer
  gets `aria-disabled="true"` and `aria-busy="true"` and ignores clicks (a ref
  guard) until the answer. It never gets the `disabled` attribute, which drops
  keyboard focus to `<body>`. `.btn[aria-busy="true"]` shows a loader. Other
  controls of a locked form may use `disabled`.
- **Dialogs.** `<Dialog open title onClose initialFocus>`: pass the safe action's
  ref as `initialFocus` — never React's `autoFocus`, which fires while the dialog
  is still closed. Escape calls `onClose`; a close the caller starts does not. The
  children are the consequence, then a `dialog-actions` row: everything but that row
  becomes the dialog's description (`aria-describedby`), so the consequence is read
  when the dialog opens. A dialog that asks for input puts its fields in a direct
  child with class `dialog-fields` (a `<form>`; its submit button may sit in the
  actions row with `form=`): it is left out of the description too, and rendered
  between the body and the actions, so a long list of choices is never read out
  when the dialog opens (Edit mode's Move clips). No prop to pass.
- **Toasts** appear bottom right. A page with a bar held at the bottom of the window
  registers it with `keepToastsClearOf(bar)` (and releases it in the same effect's
  cleanup): the region then sits above the bar while it is stuck, and below it at the
  page's end, so no toast covers it. The page also sets `--toast-inset-bottom` on
  `:root` to the bar's height while the bar is held, and removes it while the bar
  rests (in the page after the editor, it holds no room at the window's
  bottom): `html`'s scroll padding uses it, and so does the region when no bar is
  registered. The region publishes its own height as
  `--toast-region-h` on `:root` (absent when empty), and, while a bar is registered,
  its height plus the gap as `--toast-rise-h`, for the toasts that rise with the bar;
  `html`'s `scroll-padding-bottom` and the page's bottom padding add them, so a
  sticky error toast never covers keyboard focus or the end of the page — except,
  while the bar rests, the controls just above it, which a toast may
  cover until dismissed (a known gap; keeping room above a resting bar is a
  follow-up in `ui/`). The stacks
  announce each toast once (`aria-atomic="false"`), each Dismiss is described by its
  message, and dismissing the focused toast hands focus to the next toast, else the
  previous one, else the control it came from, else the page's `h1`, without
  scrolling.
- **Touch.** Under `@media (pointer: coarse)` every `btn`, `segmented` option, toast
  link, the header's Events link and the back link take a tap in at least 44 × 44 px:
  an invisible `::after` around the control, so no box moves (segmented options grow
  to 44 px wide, the theme options only from a 26rem window, and the back link to
  44 px tall, with the folder beside it padded down to keep its first line on the
  link's). The shared action rows (an alert's, a dialog's, `page-actions`,
  `toolbar`) keep 1rem between wrapped lines, so two stacked areas never meet; a
  new row that can stack buttons does the same. The brand name waits for a 34rem
  window, so the jobs status keeps its words beside the wider theme options. A fine
  pointer sees none of it. A new control class that is smaller than 44 px joins
  that rule.
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

`react`, `react-dom`, the one drag-and-drop library — `@dnd-kit/core`,
`@dnd-kit/sortable` and `@dnd-kit/utilities`, the legacy line, added by the reorder
slice (D-8) — `vite`, `@vitejs/plugin-react`, `typescript`, and `openapi-typescript`
(dev). **No component library, no CSS framework, no router, and no state-management
or data-fetching library at GUI v1.** Any addition must be justified in the proposal
of the slice that demonstrably needs it. The design system adds nothing to it.

## Checks

`tsc --noEmit` is the whole frontend gate for GUI v1. There is deliberately **no
test runner and no browser automation**: the types are generated from the schema,
so drift is a compile error, and the API's behavior is covered by `pytest`. A later
slice with logic worth unit-testing may propose a runner, with its justification.
