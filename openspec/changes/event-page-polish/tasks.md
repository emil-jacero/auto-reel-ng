## 1. Gate

- [x] 1.1 Confirm the base. This change has no gate (it runs in parallel with `edit-mode-polish`, `jobs-live-polish`, `event-list-polish`, `ui-a11y-polish` and `serve-clean-exit`), but it starts from `main` at `bca64f2` or later. Re-check the names the design cites, and stop and report to the supervisor on any mismatch:
  - `web/src/events/EventDetail.tsx` has `EventFacts`, `ReadyView`, `Counts` and `ChapterPanel`
  - `ChapterPanel` still renders `{index + 1}`, `fileName(clip.identity)` and a status `Pill` per row
  - the header still holds `.page-meta` with `Read {state.fetchedAt.toLocaleTimeString()}` and `LoadStatus`
  - `web/src/events/detail.css` has `.status-line` and the five `.clip-table .col-*` widths
  - `web/src/events/ClipThumb.tsx` names its image `fileName(clip.identity)`
  - `web/src/jobs/jobs.css` still defines `.render-card` (with `[data-active]`), `.render-none` and `.render-blocked`
  - `web/src/edit/ClipOrderList.tsx` still renders `li.clip-item` with `data-status` and a status `Pill`

  Then:
  - List which sibling polish changes are already under `openspec/changes/archive/`, and record in a scratch note:
    - whether `event-list-polish` replaced the two `toLocale…` expressions (keep its replacements verbatim)
    - whether `edit-mode-polish` changed the Edit / Stop editing button (keep it byte-identical)
    - which column property names `edit-mode-polish` reads (its design, or `edit.css` once archived). They must be exactly `--clip-col-pos`, `--clip-thumb-w`, `--clip-col-status`, `--clip-col-size` and `--clip-col-mtime` (design, "Thumbnail size, and the column contract"). Stop and report on any difference: a `var()` fallback would hide it
    - whether `jobs-live-polish` added `title={event.title}` on `<RenderControl>`, and whether `ui-a11y-polish` added `role="note"` on the missing-clips `Alert` (keep both lines)
  - Re-base all three MODIFIED blocks in `specs/web-app/spec.md` on the current `openspec/specs/web-app/spec.md`, so no archived change's wording is lost.

  Verify: `openspec validate event-page-polish --strict` passes.

## 2. web/ — shared helpers

- [x] 2.1 In `src/events/common.tsx`, add `folderOf` (private), `clipNames(chapter, identities)` and `ClipName({ name })`, which puts the folder part in `span.clip-dir` (design, "Names across folders"). In `src/events/ClipThumb.tsx`, add an optional `name?: string` that defaults to `fileName(clip.identity)` and is used for "Frame from …" and "No preview for …". `ClipOrderList.tsx`'s call site stays unchanged.

  Verify:
  - `npx tsc --noEmit` and `npm run build` pass in the `node:22` container
  - a scratch script in the session scratchpad (never committed) runs in the `node:22` container. It bundles `common.tsx` with the esbuild that Vite ships (`npx esbuild src/events/common.tsx --bundle --format=esm --platform=node --jsx=automatic --outfile=<scratch>/common.mjs`), imports it, and asserts the four rows of the design's `clipNames` table, plus `clipNames('', [])` returning file names
  - `git diff --stat main -- web/src/edit` is empty

## 3. web/ — the event page

- [x] 3.1 Regroup the header in `src/events/EventDetail.tsx` and `detail.css` (design, "The header: facts first, then one render region" and "The folder name beside a title"):
  - `.page-crumbs`, holding the unchanged back link and `span.crumb-folder`, whose inner span carries a `useId()` id and holds the visually hidden "Folder: " prefix and the folder name (`::before` separator on the outer span, declared as `content: '/'; content: '/' / '';` in `--fg-muted`; design, "Changed during implementation", item 1). It shows while loading, and when ready only if the title is non-null and differs from `folderName(eventId)`. It never shows on a failed read.
  - when ready and the folder line is shown, `aria-describedby={folderId}` on the h1 (none while loading or on a failed read)
  - `.page-meta`, holding `span.event-facts` (date · location, read view only), `Counts` as `span.counts`, the unchanged `Read …` span and `LoadStatus`
  - the description after it
  - `EventFacts` becomes `RenderPanel`: `div.render-panel` wrapping `StalenessCell` and `RenderControl`, with the same props and `blockedReason` expression
  - `.render-panel` rules: the frame, the `:has(.render-card[data-active])` accent edge, the inner `.render-card` frame reset, and `--text-sm` for `.render-none` and `.render-blocked`
  - remove `.status-line`; `span.counts` reads at weight 400 and muted (the `.counts` rule goes, and it inherits both from `.page-meta`)

  Verify:
  - `npx tsc --noEmit` and `npm run build` pass
  - `git diff --stat main -- web/src/jobs web/src/ui web/src/edit` is empty
  - the Edit / Stop editing `<button>` element is byte-identical to `main`'s. That is, `diff <(git show main:web/src/events/EventDetail.tsx | sed -n '/One element in both modes/,/^            )}/p') <(sed -n '/One element in both modes/,/^            )}/p' web/src/events/EventDetail.tsx)` prints nothing
  - `grep -c 'toLocaleTimeString()' web/src/events/EventDetail.tsx` equals `main`'s count (or `event-list-polish`'s replacement appears unchanged, per 1.1)
- [x] 3.2 In `ChapterPanel` and `detail.css`, change the clip tables (design, "Ignored clips…", "Names across folders", "An included clip's status: quiet words"):
  - a stable partition: played rows numbered from 1, then ignored rows with an empty `td.cell-pos`
  - the panel meta: `plural(played.length, …)`, plus ` · N ignored` when there are any
  - `nameOf = clipNames(chapter.name, …)`, with `<ClipName>` in `td.cell-file` and `name={nameOf(…)}` on `ClipThumb`
  - the status cell keeps its `Pill` for every status
  - the quiet-status rule `:is(.clip-row, .clip-item)[data-status='active'] .pill` and `.clip-dir` go in `detail.css`
  - the mtime cell keeps its expression verbatim

  Verify:
  - `npx tsc --noEmit` and `npm run build` pass
  - the rendered numbering, names and quiet status are checked in 5.1
  - `git diff --stat main -- web/src/events/labels.ts web/src/events/tones.ts web/src/edit` is empty
- [x] 3.3 In `detail.css`, add the column contract (design, "Thumbnail size, and the column contract"):
  - `--clip-col-pos`, `--clip-thumb-w`, `--clip-col-status`, `--clip-col-size` and `--clip-col-mtime` on `.event-detail` (the names 1.1 confirmed)
  - `@container (width >= 64rem) { .event-detail .panel > * { --clip-thumb-w: 8rem } }`
  - every `.clip-table .col-*` width, and the thumbnail track of the card layout's `grid-template-columns` (below 50rem), read the properties; the box's comment says so

  Verify:
  - `npm run build` passes
  - outside comments, `grep -nE '[^0-9.]5rem' web/src/events/detail.css` hits only the `--clip-thumb-w: 5rem` default
  - `git diff --stat main -- web/src/events/thumbs.css web/src/edit/edit.css` is empty
- [x] 3.4 Add the placeholders in the page's shape (design, "Loading: the page's own shape"):
  - the h1's visually hidden folder name plus `.skeleton-h1`, sized by a length (`18rem`, `max-inline-size: 100%`), never a percentage of the h1
  - the facts bar in `.page-meta`
  - an `aria-hidden` `.render-panel` with the verdict and button bars, in wrapping rows whose text bars shrink (`flex: 0 1 auto; min-inline-size: 0`)
  - one `aria-hidden` `section.panel` holding a real `table.clip-table`, which uses a `ClipTableHead` shared with `ChapterPanel`, and 4 `tr.clip-row`, each with a `span.clip-thumb[data-state='loading']` and inline-block bars, a short status bar included
  - drop the `SkeletonRows` import and keep `LoadStatus`
  - the new sizes (`.skeleton-h1`, `.skeleton-facts`, `.skeleton-verdict`, `.skeleton-button`, and the in-cell bar display) go in `detail.css`, with no animation of their own

  Verify:
  - `npx tsc --noEmit` and `npm run build` pass
  - `grep -n SkeletonRows web/src/events/EventDetail.tsx` prints nothing
  - `git diff --stat main -- web/src/ui web/src/styles` is empty

## 4. Docs

- [x] 4.1 Update `web/README.md` (design, "Files and parallel changes"):
  - the event-page sentence (the "Two screens so far" paragraph) says:
    - the header shows the folder name beside a title
    - one render region holds the verdict and the latest job
    - a chapter lists its played clips numbered, then its ignored clips unnumbered
    - an included clip's status is quiet
    - a clip from another folder is named by its path
    - frames are 128×72 at desktop width
  - "Design system", the "Status is never color alone" bullet: one sentence that the usual state of a clip row (included) shows its words and icon without the pill's fill and edge (`events/detail.css`), so the exceptions stand out
  - "Design system": one sentence that the clip tables publish their widths as `--clip-col-pos`, `--clip-thumb-w`, `--clip-col-status`, `--clip-col-size` and `--clip-col-mtime` on `.event-detail` (8rem frames in a panel of 64rem or more), for Edit mode's grid
  - the file tree: `detail.css` (… and the clip column properties) and `common.tsx` (… and clip names)

  Verify: `git diff web/README.md` touches only those lines, `grep -n "folder name" web/README.md` hits the event-page sentence, and `grep -n "clip-thumb-w" web/README.md` hits "Design system".

## 5. Verification against the dev library

- [x] 5.1 Set up the agent's own environment per the dev-env runbook §9, with `SLUG=event-page-polish` and `N=18`:
  - database `arel_event_page_polish`, library `../dev-event-page-polish`
  - `auto-reel serve <library> --port 8118` over a fresh `npm run build`
  - no worker besides the one `make_dev_library.py` runs on this database while it builds the library (runbook §0), so `2024/Blandat`'s job stays queued
  - never port 8080, 5173 or 8114, `../auto-reel-dev`, `auto-reel-media/`, or another agent's database, library or port

  Drive `http://127.0.0.1:8118/` with a Playwright script kept in `<scratchpad>/verify/event-page-polish/`, never committed:
  - container `mcr.microsoft.com/playwright/python:v1.49.0-noble`, with `--network host` and the Noto `fonts.conf` the final pass used
  - locators scoped to `main:not([hidden])`
  - every non-GET request aborted and logged. The log must be empty at the end.

  Check each item, in this order:
  - **Header (1280, light, `2024-06-27 - Grillning med grannar`):**
    - `.page-crumbs` holds the back link and `.crumb-folder`, whose text is "Folder: " (visually hidden) and then `2024-06-27 - Grillning med grannar`
    - `.page-meta` starts with `2024-06-27` and holds `4 clips · …` and `Read `
    - `.render-panel` holds `.verdict` ("Needs render" with its reasons) and the job line with Render, and its inner `.render-card` has a computed `border-top-width` of `0px`
    - the first `section.panel` starts 24 ± 1 px below `.render-panel`'s bottom, and `.page-meta` ends above `.render-panel`
    - `2024/Blandat`, whose shipped job is queued, shows the region's border colour differing from Grillning's idle one
  - **Folder line:**
    - `2024-07-14 - Kalas` and `2024-07-14 - kalas` both read h1 `Kalas` and show `.crumb-folder` `2024-07-14 - Kalas` and `2024-07-14 - kalas` respectively
    - on each, `expect(h1).to_have_accessible_description("Folder: 2024-07-14 - Kalas")` (and `… - kalas`) passes
    - `2024/Blandat` has no `.crumb-folder`, and its h1 has no `aria-describedby`
    - `2024-02-30 - Omöjligt datum` (failed read) has no `.crumb-folder` and no `aria-describedby`, and its h1 is the folder name
  - **Numbering (Två kapitel as shipped):**
    - `Main`'s `.cell-pos` texts are `["1", ""]`, the empty one on the row with the Ignored pill, listed last, and its `.panel-meta` reads `1 clip · 1 ignored`
    - `Kvällen`'s are `["1", "2", "3"]`
    - in Edit mode (Edit, then Stop editing with no change), `Main` lists the same names in the same order
  - **Quiet status:**
    - on Grillning, every `tr[data-status='active'] .pill` has a transparent computed background and `box-shadow: none`, and reads "Included" beside its icon
    - `2024-07-14 - kalas`'s NEW pill and Två kapitel's Ignored pill keep their tone's fill
    - in Edit mode on Grillning, `li.clip-item[data-status='active'] .pill` is transparent too
    - the quiet word's contrast on its row background is at least 4.5:1 in light and in dark
  - **Names (fixture):** in this library copy only, add `Kvällen/s1710004.mp4` as the last clip of Två kapitel's root chapter (design, "Verification fixture"). `curl` the detail and confirm `Main` is `s1710001.mp4` (active), `Kvällen/s1710004.mp4` (active) and `s1710004.mp4` (ignored). Reload the page. Then:
    - `Main`'s file cells read `s1710001.mp4`, `Kvällen/s1710004.mp4` and `s1710004.mp4`, with `.clip-dir` `Kvällen/` on the second
    - its image alts are "Frame from s1710001.mp4", "Frame from Kvällen/s1710004.mp4" and "Frame from s1710004.mp4"
    - `Kvällen` reads `s1710002.mp4` and `s1710003.mp4`
  - **Partition (fixture, second step):** copy `clips/s1710002.mp4` to `s1710009.mp4` in Två kapitel's root folder and `touch` it (design, "Verification fixture"). `curl` the detail and confirm `Main` lists `s1710004.mp4` (ignored) before `s1710009.mp4` (new). Reload the page. Then:
    - `Main`'s `.cell-pos` texts are `["1", "2", "3", ""]` and its file cells read `s1710001.mp4`, `Kvällen/s1710004.mp4`, `s1710009.mp4` and `s1710004.mp4`, the last with the Ignored pill
    - its `.panel-meta` reads `3 clips · 1 ignored`
    - in Edit mode, `Main`'s movable rows and its ignored row list the same clips in the same order
  - **Thumbnails:**
    - on Grillning, every `.clip-table .clip-thumb` measures 128×72 at 1280, and 80×45 at 1024, 768 and 390
    - at 1280, with every `/thumbnail` response held 3 s by `page.route`, each row's bounding box is the same before and after the release
    - `getComputedStyle` on `.event-detail` gives `--clip-col-status` `12.5rem`, and on a `.clip-order` in Edit mode at 1280 gives `--clip-thumb-w` `8rem` (5rem at 390)
  - **Loading:** hold only the detail `GET` of Grillning for 2 s.
    - At 1280, during the hold:
      - `get_by_role("heading", level=1)` is named `2024-06-27 - Grillning med grannar`, the h1 has no visible text outside `.visually-hidden`, and its `.skeleton-h1` measures 288 × 20 px
      - `.load-status` reads "Reading event…"
      - an `aria-hidden` `.render-panel` is shown
      - 4 placeholder rows each measure the loaded row height ± 1 px, with a 128×72 `.clip-thumb[data-state='loading']`
      - record the placeholder panel's top
    - After the hold: the h1 reads `Grillkväll med grannarna`, and the first `section.panel`'s top is within 8 px of the recorded one.
    - At 390 and at 320: the placeholder boxes are 80×45, and `document.documentElement.scrollWidth <= clientWidth` during the hold.
    - With `reduced_motion='reduce'`: `document.getAnimations().length` is 0 during the hold.
  - **Edit mode:**
    - on Grillning, Edit keeps the `.render-panel` with the verdict and "Save or leave Edit mode to render" (computed `font-size` 13px), and `.page-meta` keeps the counts
    - Stop editing with no change puts focus on the h1 and shows the tables again
  - **Layout:** check Grillning, Två kapitel (fixture), `2024-07-14 - kalas`, `2024-10-05 - Trasig` and Omöjligt datum:
    - at 1280, 768, 390 and 320, in light and dark via the theme control: `document.documentElement.scrollWidth <= clientWidth`
    - save screenshots to `<scratchpad>/verify/event-page-polish/`, and look at every one
  - **axe-core:** injected ad hoc from the scratchpad (as the design-system verification did). It reports no serious or critical violation on Grillning, Två kapitel, `2024-07-14 - kalas`, the held loading state and Edit mode, in light and dark.

## 6. Validation

- [x] 6.1 Run the gates. Verify all pass:
  - `npx tsc --noEmit` and `npm run build` in the `node:22` container
  - `web-design-system`'s motion grep gate (its design, "Tokens and the support floor"), all three commands verbatim over `web/src/events`. This change adds no animation.
  - `grep -rn 'autoFocus' web/src/events` prints nothing
  - `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`, then `.venv/bin/python -m mypy auto_reel_ng`, then `.venv/bin/python -m pylint auto_reel_ng`
  - the full `.venv/bin/python -m pytest`, with the web-mount and OpenAPI drift tests green
  - `git diff --stat main -- auto_reel_ng tests scripts web/openapi.json web/src/api web/package.json web/package-lock.json web/src/edit web/src/jobs web/src/ui web/src/shell web/src/styles web/src/events/labels.ts web/src/events/tones.ts web/src/events/EventList.tsx web/src/events/list.css web/src/events/thumbs.css` is empty
  - `openspec validate event-page-polish --strict` passes
  - no Playwright script, screenshot or `.playwright` directory is in the worktree
