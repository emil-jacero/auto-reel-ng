## Context

See proposal.md, "Why". This change starts from `main` once its three gates are archived:
`clip-thumbnail-endpoint` (which brings `clip-thumbnails`), `event-edit-screen` (C4) and
`render-progress-screen` (C5). The line references below are to `main` at `47e46f4` and to C4's and C5's
worktrees at the time of writing. Task 1.1 re-checks every one of them against the landed code.

**The read view** (`web/src/events/EventDetail.tsx`, `detail.css`)
- `ChapterPanel({ chapter, heading })` renders one `data-table clip-table` per chapter with five columns
  (`col-pos`, `col-file`, `col-status`, `col-size`, `col-mtime`). Rows are keyed by `clip.identity`, carry
  `data-status`, and the file cell shows `fileName(identity)` (a private helper in `EventDetail.tsx`).
  Every `<th>` and `<td>` carries an explicit role, because the card layout's `display: block` drops the
  implicit ones in some engines (`components.css`). `ChapterPanel` is not given the event id today.
- `detail.css` fixes the widths of four columns at 34rem, with a comment that the file column keeps about
  16rem at the 50rem card breakpoint. `components.css` asks every screen to size its fixed columns so that
  its flexible column keeps at least ~11rem at 50rem. Below 50rem (a container query on the panel) each row
  is a grid: `'pos file status' / 'pos size mtime'`, and below 30rem `'pos file file' / 'pos status status'
  / 'pos size mtime'`.
- `components.css` sets `vertical-align: baseline` on every `data-table` cell, so that a pill and the text
  beside it share a baseline. `.skeleton` shimmers with the `skeleton-shimmer` keyframes, and both are
  declared only under `prefers-reduced-motion: no-preference`, with the literal duration `1.6s`.
- C5 adds `load({ quiet: true })`, an in-place re-read after a render finishes that keeps the rows mounted.
  A plain Refresh still replaces the content with placeholders, so the rows remount.

**Edit mode** (C4, `web/src/edit/ClipOrderList.tsx`, `edit.css`)
- Each row is a `<li class="clip-item">` grid with seven columns: handle, position, file, status, size,
  time, and move buttons (`2rem 2rem minmax(0, 1fr) 12rem 5.5rem 10.5rem 4.25rem`, `column-gap:
  var(--s-3)`). The grid is mirrored by an `aria-hidden` header strip, `.clip-order-head`, with seven
  `<span>`s.
- `RowBody({ clip, position, was })` (memoised) returns the position, the `.clip-file` span (name plus the
  "was N" badge), and `ClipFacts`, whose `.clip-facts` is `display: contents` when wide. `IgnoredRow` reuses
  `RowBody`.
- Below 54rem the row becomes `'handle pos file moves' / '. . facts facts'`
  (`2rem 1.5rem minmax(0, 1fr) auto`). At 54rem the wide grid leaves the file column 11.25rem.
- `ClipOrderList` is rendered by `EventEditor`, which has `eventId`. `ClipOrderList` does not receive it.
  It keeps its own copy of `fileName`.
- Listeners sit on the handle only. `touch-action: none` is on the handle only.

**The endpoint** (`clip-thumbnail-endpoint`, fixed names from the plan)
- `GET /api/v1/events/{event_id}/thumbnail?clip=<identity>` takes an optional, published `v` query
  parameter that the server ignores (a cache-busting version), and answers:
  - 200 `image/jpeg`, with a strong `ETag` and `Cache-Control: private, max-age=86400`
  - 304 on `If-None-Match`
  - 404 problem for an unknown event, or a clip not in the event's disk listing (including MISSING)
  - 502 problem with the field `thumbnail_failure: thumbnail_failed` when extraction fails
  - 502 problem without that field when the event folder cannot be listed (`failure: unreadable_disk`),
    `config.yaml` is invalid, or the cache directory cannot be written
  - no 503: the route needs no database
  - problem responses carry no caching headers
- It runs at most two extractions at once per process, and shares one extraction between concurrent
  requests for the same key.
- The frame is taken at `thumbnails.position × duration` (default 0.25), scaled to fit 320×180 with its
  aspect kept and the container's display rotation applied. A clip displayed in portrait therefore yields a
  portrait JPEG (101×180). The event list and detail gain no field. The OpenAPI path drops the `:path`
  converter, as for `/reel` (`/api/v1/events/{event_id}/reel` in `web/openapi.json`).

**The dev library** (`scripts/make_dev_library.py`)
- Clips are symlinks into `<dev>/clips/`: four 6 s stream-copied fixture clips (1920×1080p50, keyframe
  every 0.48 s), plus the zero-byte `trasig.mp4`. The cache key hashes the *resolved* path, so events
  share keys: Två kapitel's IGNORED root `s1710004.mp4` and its NEW `Kvällen/s1710004.mp4` are two URLs for
  one key and one image.
- The events this change names:
  - `2024-06-27 - Grillning med grannar`: four clips
  - `2024-08-20 - Två kapitel - Tjörn`: root `s1710001.mp4`, the IGNORED root `s1710004.mp4`, and
    `Kvällen/` with two clips plus the NEW `Kvällen/s1710004.mp4`
  - `2024-09-01 - Sommarlov`: the MISSING `borttagen.mp4`
  - `2024-10-05 - Trasig`: the zero-byte `trasig.mp4`

## Goals / Non-Goals

**Goals:**
- One small component that the read view and Edit mode both mount, and that decides its own states.
  Each screen decides only where the component sits and how wide it is.
- No layout shift, no page-level failure, and no request for a clip that is not there.
- Keep the edits to C1's, C4's and C5's files to a few named lines.

**Non-Goals:**
- A request scheduler, retries, prefetching, or `IntersectionObserver` code (see "Loading").
- Any change to the endpoint's caching or failure contract. Where it limits the page, this is recorded
  (Risks).

## Research & Decisions

### Supervisor decisions (before implementation)

- **The placement is accepted:** after the position number and before the file name, in reading order
  ("Where the thumbnail sits"). So are moving `edit.css`' narrow breakpoint from 54rem to 58rem and the
  image's `fetchPriority="low"`.
- **The URL's `v` is the clip's `mtime` exactly as the event detail gives it** ("The URL, typed from the
  schema").
- **If `missing-clips-screen` or `job-summary-times` lands first,** task 1.1's facts are re-checked against
  the current `main` (`edit.css`' grid values, `ClipOrderList`'s rows) and adapted. If a value the widths
  here were measured against differs, the implementer stops and reports. At implementation
  `job-summary-times` was archived on `main` and `missing-clips-screen` was not; every value this design
  cites matched.
- **After `missing-clips-screen` landed (main `446ac7a`)** this change was cherry-picked onto it. That change
  left `edit.css`' grid values as they were, so the widths here still hold. It added a Remove control at the
  end of a MISSING row's `.clip-file`, and a per-chapter list of the clips the operator removed, whose
  `RemovedRow` reuses `RowBody`. The one conflict, `RowBody`'s props, keeps both sides: `RowBody` takes
  `eventId` and `action`, `RemovedRow` takes `eventId` and passes it on, and `ClipOrderList` passes it to
  `RemovedRow`. A removed row is a MISSING clip, so it shows the empty dashed box and requests nothing. The
  requirement names the removed rows among Edit mode's lists.

### Where the thumbnail sits

**Context**: The plan asks for the thumbnail "at the start of each clip row" in the tables, their phone-width
cards, and C4's drag rows.

**Explored**:
- Two placements:
  - **Inside the file cell**, as a flex item before the name. It needs no column, but in the card layouts
    the box and the name share one grid area. The name then wraps under the box whenever it is longer than
    the space beside it. The box also occupies only the first line of a two-line card.
  - **Its own column (table) or grid item (drag row).** This needs a column in each screen's grid, but the
    box can span every line of a card, and the name keeps its own area.
- Widths, measured rather than estimated. A static mock of the real stylesheets was rendered in the
  Playwright container's Chromium, with Noto Sans and Noto Sans Mono, at window widths from 1280 down to
  360px. It used `components.css` and `detail.css` from `main` and C4's `edit.css`, and it was kept in the
  session scratchpad only. At 14px a monospace character is 8.4px wide, so a 12-character camera name
  (`s1710001.mp4`) needs 101px and the archive's 18-character `YYYYMMDDhhmmss.mp4` names need 152px. A
  first cut with a 6.5rem table column and C4's breakpoints unchanged failed three ways:
  - At the 50rem breakpoint the read table's file column kept 9.5rem, which is 128px of text. That is below
    `components.css`' ~11rem, and an 18-character name wrapped.
  - The phone-width card `'pos thumb size mtime'` left the size about 29px at 390px, and "32.2 MiB"
    overlapped the time in every row.
  - Edit mode's file column was 100px at 390px, and about 100px in the wide grid at the 54rem breakpoint.
    Every camera name broke inside the word (`s1710001.mp` / `4`).

**Decision**: Its own column, after the position and before the file name, in both screens. The box is 5rem
(80×45 CSS px) wide in every layout.
- **Read table:**
  - `<col className="col-thumb" />`, 5rem wide
  - `.clip-table .cell-thumb { padding-inline: 0 }`, because the neighbouring cells' padding already
    spaces the box. The fixed columns total 39rem, so the file column keeps 11rem at the 50rem breakpoint:
    152px of text, measured, which fits an 18-character name.
  - a header cell `<th role="columnheader" scope="col"><span className="visually-hidden">Preview</span></th>`
  - a `<td role="cell" className="cell-thumb">` holding `<ClipThumb …/>`
  - card areas from 30rem: `'pos thumb file status' / 'pos thumb size mtime'`, with
    `grid-template-columns: 2rem 5rem minmax(0, 1fr) auto`
  - below 30rem: `'pos thumb file file' / 'pos thumb status status' / 'pos size size mtime'`. The size and
    time line starts under the box, so the size is never squeezed. Measured: no overlap at 390 or 360px.
    (Changed in review: the phone layout starts at 33rem, the time takes the rest of its line, and below
    22rem the status starts under the box. See "Changed during review".)
- **Drag rows:**
  - `RowBody` renders `<ClipThumb …/>` between the position and `.clip-file`, as a grid item of the row
  - `.clip-order-head` gains one empty `<span />` in the same place
  - wide: `2rem 2rem 5rem minmax(0, 1fr) 12rem 5.5rem 10.5rem 4.25rem`. The fixed part, with gaps and
    padding, grows to 47.75rem, so the narrow breakpoint MUST move from 54rem to **58rem**. At 58rem the file
    column keeps 10.25rem: 166px measured in a 58.1rem panel (a 996px window). At 54rem it would keep
    100px.
  - below 58rem: `grid-template-columns: 2rem 1.5rem 5rem minmax(0, 1fr) auto`, with areas
    `'handle pos thumb file moves' / '. . thumb facts facts'` and `column-gap: var(--s-2)`
  - below 30rem: areas `'handle pos file file moves' / '. . thumb facts facts'`. The name takes the box's
    column on the first line, and the box sits beside the facts on the second. The name keeps 188px at
    390px (158px at 360px) instead of 100px. Two layouts that keep the box first on the line were
    measured and rejected:
    - a 4rem box gave the name 116px at 390px but 86px at 360px, which breaks names again
    - moving the Move buttons to the second line gave the name 176px, but the status pill overlapped the
      buttons at 360px
- **Vertical alignment:** the clip table's cells become `vertical-align: middle` (`.clip-table td`, in
  `detail.css`). The drag rows are already `align-items: center`, so toggling Edit mode leaves the text
  where it was. The list's tables keep C1's baseline rule.

**Rationale**:
- **Accepted departure from the plan.** The plan's "at the start of each clip row" becomes "after the
  position number, before the file name, in reading order" (and, in Edit mode below 30rem, the box starts
  the second line), because every measured layout with the box first broke camera names.
- The box spans the card's lines, as in a media list, and the file name keeps its area.
- Each screen's layout stays in that screen's stylesheet: the component never reaches into a grid it does
  not own.
- Every width is measured:
  - no layout breaks a 12-character camera name inside the word
  - no layout overlaps two facts
  - the read table keeps C1's ~11rem floor
- **The visible cost:** Edit rows in a panel between 54rem and 58rem wide (windows of about 930–994px)
  now use the two-line layout.
- `.col-status` keeps 12.5rem, because its longest label, "New, not yet in reel.yaml", needs it. The
  comment in `detail.css` is updated to the new sum.

### The box: size, fit and states

**Context**: The endpoint returns at most 320×180, and a clip displayed in portrait yields a portrait image.
The page must not shift, must show a placeholder while loading, and must show absence without alarm.

**Explored**:
- `object-fit: cover`, which fills the box but crops a portrait frame to a sliver of its middle, against
  `contain`, which shows the whole frame with bands
- a fade-in on load (see "No fade-in" below)
- a new "no image" icon against the existing `film` icon

**Decision**: `src/events/ClipThumb.tsx`:

```tsx
export function ClipThumb({ eventId, clip }: { eventId: string; clip: Clip })
```

- **The box** is `<span className="clip-thumb" data-state=… data-dimmed=…>`:
  - `display: block`, `inline-size: 100%` of its column, `aspect-ratio: 16 / 9`
  - `border-radius: var(--r-sm)`, `overflow: hidden`
  - a 1px edge and a `--surface-2` fill. The edge is an inset ring on `::after`, drawn over the image so
    that a frame reaches the box's corners, in `color-mix(in oklab, var(--fg) 12%, transparent)`. That is
    `--fg` at low strength, as `edit.css` mixes `--accent`: it darkens the edge of a light frame in the light
    scheme and lightens a dark one in the dark scheme, where a solid `--border` line would show as a pale
    hairline around every dark frame. (Settled at implementation; the plan said a `--border` edge.)

  The screens make the column 5rem wide (80×45 CSS px) at every width. That is 4× the source at a device
  pixel ratio of 1, and 2× at 2. The box MUST have its final size before any byte arrives, so nothing
  shifts.
- **MISSING** (`clip.status === 'missing'`): `ClipThumb` renders the box alone, with
  `data-state="missing"`, a dashed `--border-strong` edge, no fill, no image and no request. It is
  `aria-hidden`, because the row's "Missing from disk" pill already says it. The component MUST NOT build a
  URL for a MISSING clip.
- **Otherwise**: `ClipThumb` renders `<LoadingThumb key={src} src name dimmed />`. `LoadingThumb` renders
  the box itself, so `data-state` sits on the element that owns the state
  (`useState<'loading' | 'loaded' | 'failed'>`). Keying it by URL resets the state when a row's URL
  changes, as it does when a re-read brings the clip a new `mtime`. It renders:
  - `<img src width={320} height={180} alt={`Frame from ${name}`} loading="lazy" decoding="async"
    fetchPriority="low" draggable={false} onLoad={…'loaded'} onError={…'failed'} />`
    - The attributes give the aspect ratio before CSS applies.
    - `fetchPriority="low"` keeps thumbnails behind the page's own requests (see "Loading").
    - CSS fits the image with `inline-size: 100%; block-size: 100%; object-fit: contain`, so a portrait
      frame shows whole with `--surface-2` bands.
    - `color: transparent` stops Firefox from painting the alt text over the placeholder while loading.
    - `draggable={false}` stops a native image drag from starting on a pointer-down in a drag row. Only the
      handle drags there.
  - `data-state="loading"` until `load` fires. Under `prefers-reduced-motion: no-preference` the box
    shimmers, reusing C1's `skeleton-shimmer` keyframes by name, with the same gradient as `.skeleton`.
    Under reduced motion the fill stands still, in `--border` as `.skeleton`'s does. No `@keyframes` is
    added. (Changed in review: six passes, then the still fill. See "Changed during review".)
  - `'failed'`: the image is replaced by `<span role="img" aria-label={`No preview for ${name}`}>`. It holds
    `<Icon name="film" />` and the words "No preview" (`aria-hidden`, `--text-xs`, `--fg-muted`), stacked and
    centered, on the same `--surface-2` fill. It is neutral, with no error tone.
- **Dimming**: `data-dimmed` when `clip.status === 'ignored'`, and the image gets `opacity: 0.55`. The row's
  own CSS already dims its text.
- **No fade-in.** A remounted row (after a Refresh, or on entering Edit mode) gets its image from the
  browser's cache at once, and a fade would make every remount flicker.
- **No effect and no ref.**
  - StrictMode's double render in development still creates one `<img>` and sends one request.
  - React 19 attaches `load`/`error` and sets every other attribute before `src` (checked in `react-dom`
    19.2.8). So `loading` and `fetchpriority` apply before the request starts, and a load from the memory
    cache still reaches `onLoad`.
- **`fileName` is shared.** It moves from `EventDetail.tsx` into `common.tsx` as an export.
  - `EventDetail`, `ClipThumb` and `ClipOrderList` import it, and `ClipOrderList`'s private copy is
    deleted.
  - The visible name and the alt text then come from one function.
- **The stylesheet.** `src/events/thumbs.css` holds `.clip-thumb` and its states in `@layer components`,
  and `ClipThumb.tsx` imports it.
  - It uses only existing tokens and adds no color: its one mix is of `--fg`.
  - Its shimmer declaration sits inside `@media (prefers-reduced-motion: no-preference)`, with the literal
    loop duration `1.6s` and a finite count of 6.

**Rationale**:
- The component owns its states, and each screen owns only a column width. A future size change is a few
  numbers in two stylesheets.
- The `film` icon already exists, so `ui/Icon.tsx` and its license notice stay untouched. The missing box
  is decorative, because the status pill carries its meaning (status never by color alone).

### Loading, pacing and the browser cache

**Context**:
- An event can hold about 380 clips in one chapter.
- The endpoint runs two extractions at once.
- The service speaks HTTP/1.1, so a browser opens at most six connections to it. The page's own reads
  and writes share them; the WebSocket has its own pool.

**Explored**:
- a client-side queue (N at a time, via `IntersectionObserver`)
- prefetching a whole chapter
- native `loading="lazy"` alone
- Chromium's request priorities. An image starts at Low and is raised to High once layout finds it in the
  viewport. High is the same priority as `fetch()`. Requests of equal priority wait for a connection in
  the order they were made.

**Decision**: Native `loading="lazy"`, `decoding="async"` and `fetchPriority="low"`. The client MUST NOT add
its own queue, retry or prefetch.
- Chromium loads lazy images within about 1250–2500px of the viewport. At 1280×800, with rows about 61px
  tall, that is roughly 30 of a large chapter's rows. The rest load as the operator scrolls.
  - Measured at implementation: the Playwright container's headless Chromium reports no connection type,
    and so uses its widest distance, 3000px. It requested 55 of `Många klipp`'s 60 rows before any scroll.
    The distance is the browser's choice, not the page's.
- **Priority.** Without a hint, a Save, a Render or a re-read started during a cold-cache load would queue
  behind every visible thumbnail not yet sent. With `fetchPriority="low"` every thumbnail stays below the
  page's own requests, so they take the next connection a thumbnail frees. That is at most about one
  extraction (about 0.5 s with the probe on the fixture clips, per `clip-thumbnails`' measurements).
  Firefox before 132 ignores the hint and loses only this ordering. Task 4.1 measures it.
- **One address per clip version.** The URL is a pure function of the event id, the identity and the
  clip's `mtime` as the detail gives it, so a row shown again for an unchanged clip uses the same address.
  With `Cache-Control: private, max-age=86400` the browser serves it without a request. The same applies to
  C5's quiet re-read, which never unmounts the rows. A clip replaced on disk comes back from the next read
  with a new `mtime`, so its row asks for the new frame at once.

**Rationale**: There is no JavaScript pacing to maintain, and the endpoint's semaphore already protects the
host. A client queue would duplicate the browser's own scheduler. A prefetch would extract frames for rows
the operator never looks at. One attribute makes the browser put the page's own requests first.

### The URL, typed from the schema

**Context**: Types come from the schema only, and the list and detail carry no thumbnail field.

**Explored**:
- a hand-built query string with `encodeURIComponent`
- `URLSearchParams` over an object typed from `paths`

Both encode the identity. Only the second lets `tsc` check the parameter's name.

**Decision**: `src/api/thumbnail.ts`:

```ts
import { encodeEventId } from '../route'
import type { Clip } from './event'
import type { paths } from './schema'

const THUMBNAIL_PATH = '/api/v1/events/{event_id}/thumbnail' satisfies keyof paths
type ThumbnailQuery = NonNullable<paths[typeof THUMBNAIL_PATH]['get']['parameters']['query']>

export function thumbnailUrl(eventId: string, clip: Pick<Clip, 'identity' | 'mtime'>): string {
  const query: Record<string, string> =
    clip.mtime == null
      ? ({ clip: clip.identity } satisfies ThumbnailQuery)
      : ({ clip: clip.identity, v: clip.mtime } satisfies ThumbnailQuery)
  const path = THUMBNAIL_PATH.replace('{event_id}', () => encodeEventId(eventId))
  return `${path}?${new URLSearchParams(query)}`
}
```

Two details were settled while implementing:
- **The address is built from the checked constant.** A second, literal copy of the route in the template
  would not be checked, so a typo there would pass `tsc`. The replacement is a function, so no `$` pattern
  in an id could be read as a replacement pattern (`encodeURIComponent` encodes `$` anyway).
- **`query` is annotated `Record<string, string>`.** Without it, TypeScript normalises the two branches
  to `{ clip; v?: undefined } | { clip; v: string }`, which `URLSearchParams` does not accept. Each
  branch still `satisfies` the generated query type, so an unknown or renamed key fails the build.

- **The version.** `v` is the detail's `mtime` string, unparsed and unformatted. The server ignores its
  value; it only makes the address change when the clip file does. The detail gives every clip on disk an
  `mtime`, and `ClipThumb` never builds a URL for a MISSING clip, so the no-`v` branch is only the race of
  a clip that vanished while the detail was read.
- **Encoding.** `URLSearchParams` encodes the identity as a form value, and Starlette's query parsing
  decodes each form back. Task 4.1 exercises all of them with the portrait fixture's name.
  - `/` and non-ASCII letters are percent-encoded: `Kvällen/s1710004.mp4` becomes
    `Kv%C3%A4llen%2Fs1710004.mp4`.
  - A space becomes `+`, a comma `%2C`, and a literal `+` `%2B`.
- **A renamed route fails the build.** If `clip-thumbnail-endpoint` names the route or a parameter
  differently, `satisfies` or `ThumbnailQuery` fails `tsc --noEmit`. Task 1.1 then stops and reports rather
  than renaming here.
- **No fetch.** The module has no fetch and reads no status codes: `<img>` makes the request, and every
  failure looks the same to it (see "Failure presentation").

**Rationale**: It is the house rule that a URL lives in `api/`. The route string MUST be written only in
this module, where it is checked against the generated `paths`.

### Failure presentation

**Context**: The endpoint tells 404 (not in the listing) apart from 502 `thumbnail_failure:
thumbnail_failed` and from its other 502s. An `<img>` sees none of them: any non-image answer, and a dropped
connection, fires `error`.

**Explored**: Fetching each thumbnail with `fetch()` to read the problem body, then showing a blob URL.
This would allow a label for each kind of failure. But it replaces the browser's lazy loading, cache and
decoding with hand-written code (object URLs to revoke, abort on unmount), for a distinction the operator
cannot act on from this box.

**Decision**: One neutral state for every failure: "No preview".
- A failure MUST NOT raise an alert or a toast, and the component MUST NOT retry while the row is mounted.
- A Refresh remounts the row. The browser asks again only if its cache holds nothing, and failures are not
  cached, because problem responses carry no caching headers.
- The 404 for a MISSING clip never happens, because the component does not ask. A 404 for any other clip
  means the listing changed on disk, which the page's own Refresh reports properly.
- A service-wide failure shows the same way. When the cache directory cannot be written, or `config.yaml`
  is invalid, every box on the page shows "No preview". The cause is in each 502's problem detail, and
  `auto-reel thumbs` stops on the same error, naming the directory (see Risks).

**Rationale**: A thumbnail is a convenience. The clip's real problems are reported where they already are:
the event's latest job for `trasig.mp4`, the row's status, and the page's read failures. `auto-reel thumbs`
prints the per-clip ERROR line, with the ffmpeg failure, for anyone who needs the cause.

### Getting the event id to the rows

**Context**: Neither `ChapterPanel` nor `ClipOrderList` receives the event id.

**Explored**: A React context provided once by `EventDetail`, read by `ClipThumb`. It needs fewer edited
lines, but it is a hidden dependency that fails only at runtime outside the provider, and no module uses
context today.

**Decision**: Explicit props.
- `ReadyView` passes `eventId` to `ChapterPanel`.
- `EventEditor` passes `eventId` to `ClipOrderList`, which passes it to `ClipRow` and `IgnoredRow`, and they
  pass it to `RowBody`.
- The id is a stable string, so the memoised rows re-render no more often than before.

**Rationale**: The types enforce the prop at every mount point, and the change is a handful of lines,
visible in review.

### File ownership

**Context**: C1, C4 and C5 own the files this change mounts into. The plan asks each change to keep its
shared-file edits few and named.

**Explored**: None beyond the placement above. Every edit is a mount point, a prop or a width.

**Decision**:
- **New, owned here:** `src/events/ClipThumb.tsx`, `src/events/thumbs.css`, `src/api/thumbnail.ts`
- **Edited, localized:**
  - `src/events/EventDetail.tsx`: import `ClipThumb` and `fileName`, delete the private `fileName`, pass
    `eventId` to `ChapterPanel`, and add one `<col>`, one `<th>` and one `<td>` per clip row
  - `src/events/common.tsx`: export `fileName`
  - `src/events/detail.css`:
    - `.col-thumb` (5rem) and `.cell-thumb`'s zero inline padding
    - the updated width comment (39rem, file column 11rem at 50rem)
    - `.clip-table td { vertical-align: middle }`
    - the `thumb` area in both card-area blocks
  - `src/edit/ClipOrderList.tsx`: import `ClipThumb` and `fileName`, delete the private copy, thread
    `eventId`, one `<ClipThumb>` in `RowBody`, and one header-strip `<span />`
  - `src/edit/EventEditor.tsx`: one prop
  - `src/edit/edit.css`:
    - the wide column list
    - the narrow block: breakpoint 54rem → 58rem, columns, areas and `column-gap`
    - one new `@container (width < 30rem)` block with the areas
  - `web/README.md`: the screens paragraph, the three new tree entries, and "file names" on the
    `common.tsx` tree line
- **Not touched:** `package.json`, the lockfile, `ui/*`, `styles/*`, `labels.ts`, `tones.ts`, `jobs/*`,
  `api/event*.ts`, `App.tsx`, `route.ts`, `openapi.json`, `schema.d.ts`, `docs/high-level-design.md`.
- **Specs:** two ADDED requirements, and one MODIFIED requirement ("Reading a screen never changes state")
  that neither C4 nor C5 modifies. This change archives after both, so its gate task re-bases that block on
  the current `openspec/specs/web-app/spec.md` text.

**Rationale**: A reviewer of C4's or C5's files sees a named, small diff. No behavior of either change is
altered, only where the new column sits.

### Verification fixtures

**Context**: The spec's scenarios need a large chapter and a portrait clip. The dev library has neither, and
its script is shared by every screen.

**Explored**:
- **Symlinks against hard links for the large chapter.** The cache key hashes the resolved path, so 60
  symlinks to four files collapse to four extractions.
- **`-display_rotation` on a stream copy, checked in the session scratchpad with ffmpeg 8.1.2.** ffprobe
  reports `rotation=90` on the copy, and `clip-thumbnails`' argument list turns it into a 101×180 JPEG. The
  scene in that JPEG is turned by 90°: the source was recorded in landscape, and the matrix turns it the
  way a player does.

**Decision**: The fixtures are ad hoc, only in this agent's own library copy (`dev-clip-thumbnails-screen`,
port 8111), and never committed.
- **`2024/2024-09-18 - Många klipp`**: 60 **hard links**, `m01.mp4`…`m60.mp4`, cycling through the regular
  files `clips/s1710001.mp4`…`s1710004.mp4`, with no `reel.yaml`. Hard links give 60 keys and a real
  cold-cache queue, and use no extra disk.
- **`2024/2024-09-19 - Stående`**: `stående klipp, 1.mp4`, made with
  `ffmpeg -display_rotation:v:0 90 -i clips/s1710001.mp4 -c copy "<event>/stående klipp, 1.mp4"`. This is a
  stream copy with a phone-style rotation matrix.
  - Its name holds a space, a comma and `å`, so it also exercises the `clip` query's encoding.
  - Its thumbnail MUST be portrait-shaped: a natural size of 101×180, shown whole with bands at its sides.
  - A landscape 320×180 image is a defect in `clip-thumbnails` (the display rotation was not applied),
    to be reported, not fixed here. The turned scene is expected.
- **The cache.** The service runs with `XDG_CACHE_HOME=<scratch>/verify/clip-thumbnails-screen/xdg`, so the
  thumbnail cache is isolated, can be inspected, and can be emptied for cold-cache checks.
- **Browser contexts.**
  - A cold-cache check empties that directory and then opens a new browser context, because the browser's
    own cache would otherwise answer from an earlier visit.
  - Playwright turns the HTTP cache off in any context that uses `route()`. Every check that relies on
    the browser cache (no refetch in Edit mode, after a Refresh, or on leaving Edit mode) therefore runs
    in a context that never routes.

**Rationale**: Each fixture exists only to make one scenario observable. None of them changes the shared
script or another agent's library.

### Changed during review

The review found one major and four minor defects, and the known removed-row issue. All six were fixed on
the pr branch after the rebase onto `missing-clips-screen`:

1. **The idle shimmer burned CPU.** See Risks, "A shimmer on many boxes". `thumbs.css` now declares
   `animation: skeleton-shimmer 1.6s linear 6`, still inside the no-preference block. When the animation
   ends, `background-position` returns to the declared `0 0`, where the 300%-wide gradient shows only
   `--border`: the reduced-motion look, with no jump.
2. **Edit rows were 8px shorter than the table's.** The wide `.clip-item` kept C4's `padding-block:
   var(--s-1)`, so the 45px frame sat 4px from the dividers, and every row shrank when Edit mode opened. It
   is now `var(--s-2)`, the read table's cell padding and the narrow block's. Measured at 1280px, both
   rows are 62px.
3. **Edit mode scrolled sideways at 320–335px** (WCAG 1.4.10, reflow). Below 30rem the facts beside the
   box are narrower than a `nowrap` time. In that block, `.clip-mtime` may wrap, with `text-wrap: balance`,
   so the date and the clock time each keep a line.
4. **The read cards wrapped at 360–375px.** Every time wrapped "PM" onto a line of its own, and the NEW
   pill ("New, not yet in reel.yaml") took two lines. The phone layout's last line is now `'pos size
   mtime mtime'`, so the time takes the rest of the line. Below 22rem (viewports under about 384px) the
   longest pill no longer fits beside the box, so the status starts under it: `'pos thumb file file' /
   'pos status status status' / 'pos size mtime mtime'`. At 390px the pill still fits beside the box. The card time
   also gets `text-wrap: balance`, for the narrowest phones.
5. **Read cards broke an 18-character camera name** mid-word on NEW clips in a 30–33rem panel (a 540px
   window). Beside the longest pill the file column kept only about 140px. The clip table's phone layout
   now starts at 33rem, not 30rem; the rule matches only `.clip-table tbody tr`.
6. **After Remove or Undo at 390px, the row sat partly under the save bar.** `ClipOrderList` scrolled
   only the focused button into view. It now scrolls that button's whole row (`block: 'nearest'`, inside
   the page's scroll padding). The same applies to Move up and Move down, whose rows are taller with the
   frame.

**Verified in the Playwright container.** Camera-style names (`YYYYMMDDhhmmss.mp4`) were swapped into the
detail JSON in the browser only (`page.route`), on Två kapitel with its NEW clip:
- **Read view:**
  - at 360, 375, 390, 520, 540 and 560px, in both schemes, every name, pill and time keeps one line
  - at 320px, no horizontal scroll and no overlap
- **Edit mode:** no horizontal scroll at any of those widths.
- **Row heights:** 62px in the table and in Edit mode at 1280px.
- **Save bar:** at 390 and 996px, the removed row lies whole between the header and the save bar, and the
  row given back by Undo is in view.

## Failure behavior and idempotency

- **The page never fails because of a thumbnail.** The detail read and the thumbnails are independent
  requests, and a failed thumbnail changes one box.
- **No partial state.** The client writes nothing. The service's cache writes are atomic (temp file, then
  rename, `clip-thumbnails`), so a request aborted by navigating away leaves no half file. A later request
  extracts again.
- **Re-runs.** Opening the page again, Refresh, and entering or leaving Edit mode reuse the same URLs while
  the clips are unchanged on disk. The browser serves them from its cache. After that expires, the browser revalidates with the `ETag`, and the
  service answers 304 without extracting. Extraction runs at most once per key.
- **No `--force`, worker or render interaction.** Thumbnails are not a render input, and a running render
  does not change what a thumbnail returns. No `RENDER_GRAPH_VERSION` bump, API change or migration.

## Risks / Trade-offs

- **[A clip replaced while its page is open]** Its row keeps the old frame until the page reads the
  detail again (a Refresh, or C5's quiet re-read), which brings the new `mtime` and so a new `v`. →
  Accepted: the day-long browser cache no longer hides a replaced clip.
- **[Six connections, two extractions]** On a cold cache, a large chapter queues requests at the service.
  → Accepted with `fetchPriority="low"`, which puts the page's own reads and writes first (see "Loading"). Task 4.1 measures a
  Refresh, and a read made while the rows stay mounted, during a cold-cache load. If either waits longer
  than 2 s, the implementer reports it rather than adding a client queue.
- **[Edit rows switch to two lines earlier]** Moving C4's narrow breakpoint from 54rem to 58rem gives
  windows of about 930–994px the two-line row. → Accepted: that layout is C4's own, already verified, and
  it keeps every fact. The alternative was a file column of about 100px there. Task 1.1 stops if C4 landed
  other grid values.
- **[A service-wide failure looks like many clip failures]** An unwritable cache directory or an invalid
  `config.yaml` turns every box into "No preview", with no hint on the page. → Accepted for v1. The cause is one request away
  in the problem detail and in `auto-reel thumbs`. A page-level notice would need the client to read status
  codes (see "Failure presentation"), and it is left for a real need.
- **[A shimmer on many boxes]** A large chapter holds many loading boxes at once, and a box the browser
  defers (lazy, far below the view) stays loading until the operator scrolls near it. → Not painting an
  off-screen box does **not** stop its animation from ticking. Review measured `Stor dag` (400 rows, warm
  cache): 345 deferred boxes animating forever cost 60 style recalculations per second, about 26% of a core,
  with no input. The shimmer therefore runs six passes (about 10 s), long enough for the boxes in view to
  fill, and then rests on the still `--border` fill, the reduced-motion look. A box whose image starts
  loading later, after a scroll, shows the still fill. Measured after the fix, 12 s after the loaded count
  settles: no running animation, 0 style recalculations and under 1 ms of main-thread work in 5 s of idle,
  in the read view and in Edit mode. A box also stops shimmering once its image loads. Under reduced motion
  there is no animation. C4's 400-row keyboard check is re-run once with thumbnails (task 4.2).
- **[C1's baseline alignment]** Middle alignment in the clip table moves a pill a pixel or two relative to
  its neighbours. → This applies to the clip table only, it matches the drag rows, and the list's tables are
  unchanged.
- **[The gates' code differs from what is cited here]** C4 and C5 are still being implemented. → Task 1.1
  re-reads the landed files and stops on any mismatch that changes a mount point. The widths above are
  measured against C4's `edit.css` as it stands; a changed column list there is such a mismatch.

## Migration Plan

- Rebuild `web/dist` with the `web/README.md` container command. `serve` mounts it as before. There are no
  new packages, so no `npm ci` is needed.
- Nothing is migrated. Rollback: revert the web change. The service's cache stays valid, and is used by
  `auto-reel thumbs` and the endpoint.

## Open Questions

None. A replaced clip's frame is settled by the endpoint's published `v` parameter ("The URL, typed from
the schema").
