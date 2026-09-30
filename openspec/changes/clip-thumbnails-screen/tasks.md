## 1. Gate

- [x] 1.1 Confirm that the three gates are archived on `main`:
  `ls openspec/changes/archive/ | grep -E -- '-(clip-thumbnail-endpoint|event-edit-screen|render-progress-screen)$'`
  must print three directories. Stop and report to the supervisor if any is missing. Then re-check what this
  change builds on against the landed code (design, "Context"), and stop and report on any mismatch that
  moves a mount point or a name. Do not rename anything here.
  - **The endpoint:**
    - `web/src/api/schema.d.ts` has the path `/api/v1/events/{event_id}/thumbnail` with a `get` whose query
      parameters are the required `clip` and the optional `v`
    - the route answers 200 `image/jpeg` with a strong `ETag` and `Cache-Control: private, max-age=86400`
    - it answers 404 for a MISSING clip, and 502 with `thumbnail_failure: thumbnail_failed` for an
      extraction failure
    - it serves IGNORED and NEW clips (they are in the detail's listing)
    - its problem responses carry no caching headers
  - **The screens:**
    - `EventDetail.tsx`'s `ChapterPanel` and its five `<col>`s
    - `detail.css`'s card areas
    - C4's `ClipOrderList.tsx`: `RowBody`, `IgnoredRow`, the seven-span `.clip-order-head`, the private
      `fileName`, and how `EventEditor` renders it
    - `edit.css`'s wide column list, its `column-gap`, and its `@container (width < 54rem)` block. The
      design's widths and breakpoints were measured against these values, so any other value is a mismatch.
    - C5's `load({ quiet })`, which keeps the rows mounted
  - **The docs:** D-11 is in `docs/high-level-design.md` §7, and §4.10 lists clip thumbnails in v1. If
    either says something this change does not ship, stop and report.
  - **The spec:** re-base the MODIFIED block in `specs/web-app/spec.md` on the current
    `openspec/specs/web-app/spec.md` text of "Reading a screen never changes state", keeping any edit that
    another change made.
  - **Set up** per the dev-env runbook §9 with `SLUG=clip-thumbnails-screen` and `N=11`:
    - database `arel_clip_thumbnails_screen`, library `../dev-clip-thumbnails-screen`, port 8111
    - `serve` with `XDG_CACHE_HOME=/tmp/claude-1000/-var-home-emil-dev-larnet-auto-reel-project/72ded660-4d8e-435c-8a06-07bf9520945a/scratchpad/verify/clip-thumbnails-screen/xdg`
    - in that library copy only, the two ad hoc events from design, "Verification fixtures":
      `2024/2024-09-18 - Många klipp` (60 hard links to the regular files in `clips/`, never symlinks) and
      `2024/2024-09-19 - Stående` (`stående klipp, 1.mp4`, display rotation 90). Confirm with
      `ffprobe -show_entries stream_side_data=rotation` that the copy reports `rotation=90`.
    - never port 8080, `../auto-reel-dev` or `auto-reel-media/`

  Verify:
  - `npx tsc --noEmit` and `npm run build` pass on the untouched tree
  - `curl -si` on the thumbnail of Grillning's `s1710001.mp4` gives 200 `image/jpeg`, of Trasig's
    `trasig.mp4` 502 with `thumbnail_failure: thumbnail_failed`, and of Sommarlov's `borttagen.mp4` 404
  - `git diff --stat main -- openspec/specs` is empty

## 2. web/ — the URL and the component

- [x] 2.1 Add `src/api/thumbnail.ts` (`thumbnailUrl`, with the route checked by `satisfies keyof paths` and
  the query typed from `paths`: `clip` is the identity, and `v` the clip's `mtime` exactly as the detail
  gives it), and move `fileName` from `EventDetail.tsx` into an export of `src/events/common.tsx`, imported
  back by `EventDetail.tsx` (design, "The URL, typed from the schema").
  Verify:
  - `tsc --noEmit` passes
  - temporarily changing `thumbnail` to `thumbnails` in `THUMBNAIL_PATH`, or `v` to `version` in the query,
    makes `tsc` fail; restore it
  - `grep -rn "function fileName" web/src/events` prints only `common.tsx`
- [x] 2.2 Add `src/events/ClipThumb.tsx` and `src/events/thumbs.css` (`@layer components`), per design "The
  box: size, fit and states":
  - the missing box
  - `LoadingThumb` keyed by URL and rendering the box itself, with `loading="lazy"`, `decoding="async"`,
    `fetchPriority="low"`, `width={320}`, `height={180}`, `draggable={false}` and the alt text
  - the loading shimmer, reusing `skeleton-shimmer` inside a `no-preference` block
  - the failed box: `film`, "No preview", `role="img"` and its name
  - the dimmed ignored image

  Verify:
  - `tsc --noEmit` and `npm run build` pass
  - `grep -n '@keyframes\|JSX.Element\|autoFocus' web/src/events/ClipThumb.tsx web/src/events/thumbs.css`
    prints nothing
  - the three motion grep commands in `web/README.md`, run over `web/src/events`, pass
  - `thumbs.css` uses no color literal (`grep -nE '#[0-9a-fA-F]{3}|oklch|rgb' web/src/events/thumbs.css`
    prints nothing)

## 3. web/ — mount points and docs

- [x] 3.1 Mount the component in the read view (design, "Where the thumbnail sits", "Getting the event id to
  the rows"):
  - in `EventDetail.tsx`: `eventId` to `ChapterPanel`, then per table a `col-thumb` `<col>`, a
    visually hidden "Preview" `<th role="columnheader" scope="col">`, and per row a
    `<td role="cell" className="cell-thumb">` with `<ClipThumb>`
  - in `detail.css`:
    - `.col-thumb` (5rem) and `.clip-table .cell-thumb { padding-inline: 0 }`
    - the updated width comment (39rem; file column 11rem at 50rem)
    - `.clip-table td { vertical-align: middle }`
    - the `thumb` area in both card layouts, with `'pos size size mtime'` as the last line below 30rem

  Verify:
  - `tsc --noEmit` and `npm run build` pass
  - in the running service, `2024-06-27 - Grillning med grannar` shows four images at 1280px
  - at 866px (a 50rem panel, the table's narrowest), each of Två kapitel's `.cell-file` cells is at least
    176px (11rem) wide
  - at 390px, Två kapitel shows each box beside its row's facts, with
    `document.documentElement.scrollWidth <= innerWidth`
  - at 390px, no two cells of a row have intersecting text rectangles (`Range.getClientRects()` per cell,
    and the box's own rectangle)
  - `git diff --stat` lists only the files named in design, "File ownership"
- [x] 3.2 Mount the component in Edit mode:
  - in `EventEditor.tsx`: pass `eventId` to `ClipOrderList`
  - in `ClipOrderList.tsx`: thread `eventId` through `ClipRow` and `IgnoredRow` to `RowBody`, render
    `<ClipThumb>` between the position and `.clip-file`, add one `<span />` to `.clip-order-head`, and replace
    the private `fileName` with the import
  - in `edit.css`:
    - the 5rem column in the wide list
    - the narrow block moved from `@container (width < 54rem)` to `(width < 58rem)`, with its columns,
      areas and `column-gap: var(--s-2)`
    - a new `@container (width < 30rem)` block with the areas `'handle pos file file moves' / '. . thumb
      facts facts'`

  Verify:
  - `tsc --noEmit` and `npm run build` pass
  - in the running service, Grillning's Edit mode shows a box in every row, with the header strip still
    aligned to its columns at 1280px and at 996px (a 58rem panel, the wide grid's narrowest)
  - at 996px each `.clip-file` is at least 164px wide
  - at 390px each `.clip-name` renders on one line (its client rectangles share one top)
  - Move down on the first clip moves its frame to row 2 and keeps focus on the button, as C4 specifies
  - the three motion grep commands pass over `web/src/edit`
  - `grep -rn "function fileName" web/src` prints only `common.tsx`
- [x] 3.3 Update `web/README.md`:
  - in the screens paragraph, each clip row's frame (lazy, "No preview" on failure, none for a missing
    clip)
  - in the file tree, `api/thumbnail.ts`, `events/ClipThumb.tsx` and `events/thumbs.css`, and "file
    names" on the `common.tsx` line
  - the dependency budget is unchanged

  Verify that `grep -n "ClipThumb\|thumbnail.ts\|thumbs.css" web/README.md` shows the three tree entries,
  and that `git diff web/README.md` touches no other section.

## 4. Verification against the dev library

- [x] 4.1 Run an ad-hoc Playwright pass for the read view from the session scratchpad, **never
  committed**:
  - script: `/tmp/claude-1000/-var-home-emil-dev-larnet-auto-reel-project/72ded660-4d8e-435c-8a06-07bf9520945a/scratchpad/verify/clip-thumbnails-screen/check_read.py`
  - container: `mcr.microsoft.com/playwright/python:v1.49.0-noble`, run with `--network host --ipc host`,
    with the Noto Sans fonts and `FONTCONFIG_FILE` per `web/README.md`
  - target: the built client on port 8111
  - locators scoped to `main:not([hidden])`
  - screenshots in that directory: Grillning, Två kapitel, Sommarlov, Trasig and Stående, in light and
    dark, at 1280, 768 and 390px (30 PNGs)
  - browser contexts per design, "Verification fixtures": each cold-cache check empties the `xdg`
    directory and opens a new context. Every check that relies on the browser's cache runs in a context
    that never called `route()`, because routing turns Playwright's HTTP cache off.

  Look at every screenshot, then check:
  - **Frames:**
    - Grillning shows four images with alt "Frame from s171000N.mp4"
    - every thumbnail request's `v` (decoded) equals that row's clip `mtime` in the event detail response
      the page received (request log against the detail JSON)
    - Två kapitel's `Kvällen` rows requested `clip=Kv%C3%A4llen%2F…` (request log), including the NEW
      `Kvällen/s1710004.mp4`
    - the IGNORED root `s1710004.mp4` image has computed `opacity` 0.55, and the others 1
    - Stående's request carries `clip=st%C3%A5ende+klipp%2C+1.mp4` and was answered 200
    - Stående's box is the same size as the others, and its image's natural size is 101×180, shown whole
      with bands at its sides. Its scene looks turned by 90°, as a player shows this fixture. Report against
      `clip-thumbnails` only a landscape 320×180 image.
  - **Absence:**
    - Sommarlov made no request naming `borttagen.mp4`, and its box is the dashed empty one
    - Trasig shows "No preview" with the film icon, and `getByRole('img', { name: 'No preview for
      trasig.mp4' })` resolves
    - Trasig shows no `role="alert"` beyond what it showed before this change, and no toast
    - the `serve` access log holds exactly one thumbnail request for `trasig.mp4`
  - **Lazy, no shift, not blocking:**
    - Många klipp at 1280×800 on a cold cache (the `xdg` directory emptied, a new context) requests fewer
      than 60 thumbnails before any scroll, and 60 after scrolling to the end
    - with every `**/thumbnail*` request held by `page.route`, then released, on Två kapitel: each row's
      bounding box is identical before and after the release, and the summed `layout-shift` entries
      (`PerformanceObserver`, buffered) are 0
    - with thumbnails held for 5 s on Grillning, the heading and all four rows' facts are visible before
      any image, and each box has `data-state="loading"`
    - on a cold cache, open Många klipp, then press Refresh at once: the event's GET completes in under
      2 s (record the time)
    - on a cold cache, open Många klipp, and while its thumbnails load, with the rows still mounted, time a
      `fetch()` of the event's detail URL made from the page (`page.evaluate`). It stands in for a Save, a
      Render or C5's quiet re-read, and it completes in under 2 s (record the time).
    - if either check fails, stop and report (design, "Risks")
  - **Motion:** with thumbnails held, the loading box's computed `animation-name` is `skeleton-shimmer`,
    with duration `1.6s`, under `reduced_motion='no-preference'`, and `none` under `'reduce'`.
  - **Access:**
    - nothing in a `.clip-thumb` is focusable: tabbing through Två kapitel never lands inside one, and
      every `.clip-thumb` and its children report `tabIndex` -1
    - axe-core (wcag2a, wcag2aa, injected ad hoc) reports zero violations on Två kapitel and Trasig in both
      schemes
  - **Phone width:** at 390px, on all five pages in both schemes:
    - `scrollWidth <= innerWidth`
    - every row still shows its box, position, file name, status, size and time
    - no two of them overlap (the text-rectangle check of task 3.1)

  Verify: every item passes, and the PNGs and the check's output are in the verify directory.
- [x] 4.2 Run the Edit-mode and "changes nothing" checks with the same setup:
  - script: `…/verify/clip-thumbnails-screen/check_edit.py`
  - screenshots: Grillning and Två kapitel in Edit mode, light and dark, at 1280, 768 and 390px (12 PNGs)

  Check:
  - **Same frames, no refetch** (in a context that never calls `route()`): entering Edit mode on Grillning
    shows the same four frames as its table, and the `serve` access log gains no thumbnail line. Leaving
    Edit mode, and a Refresh within the `max-age`, also add none.
  - **Drag only by the handle:** pressing the mouse on a row's thumbnail and moving 60px down, then
    releasing, fires no `dragstart` and leaves the order unchanged. Dragging the same row by its handle
    still moves it, and its frame moves with it.
  - **Ignored rows:** Två kapitel's ignored row in Edit mode shows its image dimmed.
  - **Scale:** C4's `2024/2024-09-15 - Stor dag` recipe (400 symlinks to one cut clip), re-created in this
    library copy. Its symlinks resolve to one file, so after one extraction every image comes from the
    service's cache: the check measures a page of 400 images, not extraction. The median time for 10
    keyboard steps and 10 Move down clicks stays under C4's 100 ms budget, started on a cold cache with the
    images still arriving. Record the numbers.
  - **Phone width:** at 390px in Edit mode:
    - `scrollWidth <= innerWidth`
    - each row shows its handle, position, box, file name, move buttons, status, size and time, with no
      two of them overlapping
    - each `.clip-name` renders on one line
  - **Changes nothing:**
    - before the pass, record `auto-reel jobs list` and touch a marker file
    - empty the `xdg` cache, then open Grillning in a new context
    - the cache now holds four JPEGs
    - `find ../dev-clip-thumbnails-screen/library -newer <marker>` prints nothing
    - the jobs list is identical
    - every request the pages made was a `GET`
  - **Idle:** with Grillning shown and all four images loaded, 60 s of idling makes no request.

  Verify: every item passes, the PNGs are in the verify directory, and `git status` shows no Playwright,
  fixture or screenshot file in the repository.

## 5. Validation

- [x] 5.1 Run the gates:
  - `npx tsc --noEmit` and `npm run build` in the node:22 container
  - the full `.venv/bin/python -m pytest`, which must keep the web-mount and OpenAPI drift tests green
  - no Python file changed, so these run only to confirm that nothing changed:
    - `.venv/bin/python -m black --check auto_reel_ng tests`
    - `.venv/bin/python -m isort --check auto_reel_ng tests`
    - `.venv/bin/python -m mypy auto_reel_ng`
    - `.venv/bin/python -m pylint auto_reel_ng`

  Verify:
  - all of the above pass
  - the motion grep gate passes over `web/src`
  - `git diff main -- web/package.json web/package-lock.json web/openapi.json web/src/api/schema.d.ts
    web/src/ui web/src/styles` is empty
  - `openspec validate clip-thumbnails-screen --strict` passes
