## Why

GUI v1 (HLD **§6 phase 8**, §4.10) is feature-complete on `main` (`bca64f2`). Its look is locked as **D-10**
(one quiet, data-dense visual system) and its clip frames as **D-11** (one thumbnail per clip). The final
end-to-end pass and its design and completeness critics found six defects on the event page. Each one
reproduces read-only against the final build (design, "The findings, re-checked"):

- **The page shows a fact the data doesn't carry.** This is the class of bug HLD §2 (problem 5) and
  Principle I exist to prevent.
  - The read view numbers an ignored clip as if it played. `2024-08-20 - Två kapitel - Tjörn` lists
    `3 s1710004.mp4 Ignored`, although an ignored clip has no place in the play order, and Edit mode lists
    the same chapter unnumbered.
  - While the page reads, its heading shows the folder name `2024-06-27 - Grillning med grannar`. The read
    then replaces it with a different name, `Grillkväll med grannarna`, and the placeholder rows have the
    list's shape. The page reflows by 133 px when the read answers.
- **Two things that differ look the same.**
  - One chapter lists `s1710004.mp4` twice. One is `Kvällen/s1710004.mp4`, placed in the root chapter, and
    the other is the ignored root file. Both have the same name and the same alt text, so the operator can't
    tell which one plays.
  - The two events `2024-07-14 - Kalas` and `2024-07-14 - kalas` have identical pages (heading `Kalas`,
    date `2024-07-14`). Yet v1 asks the operator to fix exactly this output collision by hand.
- **The page groups the wrong things together (D-10).**
  - The verdict sits outside the render card, while the job and Render sit inside it.
  - The clip summary sits closer to that card than to the table it describes.
  - Every row spends a 200 px column on the same grey "Included" pill, which hides the new, missing and
    ignored clips the operator scans for.
  - The one visual cue for telling clips apart, the frame (D-11), is 80×45 at desktop width, next to a
    526 px file column that holds 12-character names.

## What Changes

- **The header groups the event's facts, then its render state.**
  - The back link's line also shows the event's folder name. It appears whenever the heading shows a
    title that differs from it, which tells `Kalas` from `kalas`. The heading carries it as its description
    for assistive technology, because focus lands on the heading and reading on from there never reaches
    the line above it.
  - One meta line under the heading holds the date and location, the clip counts and total size, and the
    read time.
  - Then the description.
  - Then one render region: the verdict and its reasons, the latest job, and Render or Cancel. It is framed
    as one card. `RenderControl` is unchanged. The page wraps it and drops the inner card's frame.
- **Clip tables.**
  - Each chapter lists the clips it plays first, numbered from 1. After them it lists its ignored clips,
    with no position, as Edit mode already does. Its heading counts the played clips and then the ignored
    ones (`1 clip · 1 ignored`).
  - An included clip's status keeps its word and icon but loses the pill's fill and edge. The same rule
    also reaches Edit mode's rows, through their existing `data-status` attribute, so both views agree.
  - A chapter that lists a clip from another folder names every one of its clips by its path in the
    event folder (for example `Kvällen/s1710004.mp4`). The thumbnail's text alternative and its
    "No preview for …" name follow.
- **Larger frames at desktop width.** Where a chapter's panel is at least 64rem wide, the thumbnail box
  is 128×72 (8rem, 16:9, sized before the image arrives). The card layouts keep 80×45. The service's
  320×180 frame stays sharp at 2× (D-11). The widths are published as custom properties that Edit mode's
  grid can read.
- **Loading keeps the page's shape.**
  - The heading shows a placeholder bar. It is still named by the folder name for assistive technology.
  - The meta line, the render region and the clip rows each get a placeholder of their own shape and
    height, with thumbnail boxes, and they fit a 320 px window. When the read answers at 1280 px, the first
    chapter moves by at most 8 px, not 133 px. At phone width the shift is smaller than today's but not
    zero, since wrapped reasons and titles are known only after the read (design, "Loading").
- **Docs:** `web/README.md`: the event-page sentence, the quiet included status and the clip column
  properties under "Design system", and the `detail.css` / `common.tsx` lines of the file tree.

## Non-goals

- **Edit mode's own rows** (`web/src/edit/`, owned by `edit-mode-polish`) are left alone:
  - its grid tracks
  - its clip names in rows, labels and announcements
  - its Remove placement

  This change exports `clipNames`/`ClipName` and the track properties (`--clip-col-pos`, `--clip-thumb-w`,
  `--clip-col-status`, `--clip-col-size`, `--clip-col-mtime`, the names `edit-mode-polish`'s proposal
  reads) so that Edit mode can adopt them (design, "Files and parallel changes"). The quiet "Included" rule is the one exception: it
  is CSS in `detail.css` and touches no `edit/` file.
- **The render region's internals** (`web/src/jobs/`, owned by `jobs-live-polish`), the list
  (`event-list-polish`), toasts and dialogs (`ui-a11y-polish`), and the shared date/time formatter
  (`event-list-polish`) are left alone. This change keeps the two `toLocale…` expressions in
  `EventDetail.tsx` verbatim, so the formatter's one-line call-site edits apply unchanged.
- **The missing-clips warning's role** (`role="note"`) is `ui-a11y-polish`'s one-attribute call site in
  this change's file.
- **Status words:** `CLIP_STATUS_LABEL` (`events/labels.ts`) is unchanged, including "New, not yet in
  reel.yaml", which is why the Status column keeps its width.
- **Not in this round** (they need the user's decision): the adoption of NEW sub-folder clips into the
  default chapter (D-CLI3), and the "movie file missing" verdict after a retitle. This change only
  *names* an adopted clip correctly. It does not move it.
- **No API, engine or schema change.** No new dependency.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `web-app`: three MODIFIED requirements, each re-based on the current `openspec/specs/web-app/spec.md` at
  task 1.1. No sibling polish change modifies any of the three.
  - `Requirement: The event page shows the event's chapters and clips`. This covers:
    - the folder name beside a title, as the heading's description
    - the verdict and the latest job in one region
    - ignored clips after the played ones, with no position, even where the service lists a new clip
      after an ignored one
    - an included clip's quiet status
    - names across folders
    - placeholders in the page's shape, with a heading that never shows a name the read replaces, fitting
      the window from 320 px
  - `Requirement: Every clip row shows a frame from its clip`. This covers the table box's size by window
    width, and a text alternative that follows the name the row shows.
  - `Requirement: Thumbnails never hold up or break a page`. One phrase: the "No preview for <name>" label
    follows the name the row shows, as the text alternative does. The rest is unchanged.

## Impact

- **Packages:** `web/` only, plus `web/README.md`.
  - `src/events/EventDetail.tsx` changes the header, `EventFacts`, `ReadyView`, `ChapterPanel` and
    `Counts`, and adds the placeholders. It leaves alone the Edit / Stop editing button element, which
    `edit-mode-polish` owns.
  - `src/events/detail.css` gains the header, the render region's frame, the quiet status rule, the
    track properties, the 64rem container rule and the placeholder shapes.
  - `web/README.md` gains the sentences listed under "Docs".
  - `src/events/common.tsx` gains `clipNames` and `ClipName`.
  - `src/events/ClipThumb.tsx` gains an optional `name` prop, which defaults to today's file name.
  - `thumbs.css` is unchanged: the box already fills its column.
- **CLI vs API (Principle V):** neither is touched. The page reads only what `GET /api/v1/events/{id}`
  already returns.
- **Rendered output:** unchanged. **No `RENDER_GRAPH_VERSION` bump.** The fingerprint inputs are
  unchanged.
- **Schemas:** no `reel.yaml`, `config.yaml` or API change, **no Alembic migration**, no rescan.
  `web/openapi.json` and `schema.d.ts` are untouched.
- **Dependencies:**
  - **Gates:** none. The change starts from `main` at `bca64f2` and runs in parallel with
    `edit-mode-polish`, `jobs-live-polish`, `event-list-polish`, `ui-a11y-polish` and `serve-clean-exit`.
    Task 1.1 re-bases the spec blocks on whatever of those has archived first. Three of them add
    one-line call sites in this change's files: `jobs-live-polish` (`title` on `RenderControl`),
    `event-list-polish` (the formatter and failure wording) and `ui-a11y-polish` (the warning's role).
    Whichever change lands second re-applies them (design, "Files and parallel changes").
  - **New runtime dependencies:** none (D-8's budget is unchanged).
- **Size (Principle VIII):** one package, one capability delta (three requirements) and 9 tasks.
