## Context

See proposal.md, "Why". The change starts from `main` at `bca64f2`. The code below is cited from there, and
task 1.1 re-checks it.

**The event page** (`web/src/events/EventDetail.tsx`)

- `EventDetail` (`:83`). The name is `state.event.title ?? folderName(eventId)` once the read answers,
  and `folderName(eventId)` while it reads (`:195-196`).
- The header (`:205-269`) holds, in this order:
  - the back link (`:206-209`)
  - the title row: the h1, then `.page-actions` with Refresh and the Edit / Stop editing toggle
    (`:210-253`)
  - `EventFacts` (`:254-261`)
  - `.page-meta` with `Counts`, `Read {state.fetchedAt.toLocaleTimeString()}` and `LoadStatus`
    (`:262-268`)
- While reading, the page shows one `.panel` with `SkeletonRows rows={4}` (`:271-278`). These are the
  list's 40 px date/title/pill rows.
- `EventFacts` (`:336-368`) shows `p.event-facts` (date · location) and the description when not editing.
  Then it shows `.status-line`: `StalenessCell` (the verdict) and `RenderControl` with the Edit-mode and
  missing-clip `blockedReason`.
- `ReadyView` (`:370-405`) shows the missing-clips `Alert`, then one `ChapterPanel` per chapter.
- `ChapterPanel` (`:429-513`):
  - a `.panel` with a `<colgroup>`
  - `{index + 1}` for every clip, the ignored ones included (`:481`)
  - `fileName(clip.identity)` (`:487`)
  - a `Pill` for every status, `active` included (`:490-495`)
  - the mtime `new Date(clip.mtime).toLocaleString()` (`:504`)

**Styles**

- `events/detail.css` (`@layer screens`):
  - `.status-line` (`:35-40`), `.counts` (`:42-45`)
  - the column widths: pos 3.5rem, thumb 5rem, status 12.5rem, size 6.5rem, mtime 11.5rem (`:52-73`)
  - the card layouts below 50rem, 33rem and 22rem (`:121-173`). The first sets
    `grid-template-columns: 2rem 5rem minmax(0, 1fr) auto` (a literal `5rem` thumbnail track), and the
    other two change only the areas.
- `.panel` is the size container (`styles/components.css:161-166`).
- `.pill` is `@layer components` (`:443-471`): padding, `--_bg`, `--_fg` and an inset box-shadow edge.
- `.skeleton` bars live at `:604-627`.
- `jobs/jobs.css` is `@layer components` (`:11`):
  - `.render-control` (`:279`)
  - `.render-card`, a framed grid whose edge turns accent on `[data-active]` (`:286-303`)
  - `.render-none` and `.render-blocked`, which are muted with no font size, so they render at 14 px
    beside the 13 px `.job-when` (`:328-331`)

**Shared helpers.** `events/common.tsx`: `folderName`, `fileName` (the last path segment,
`:18-20`) and `StalenessCell`. `events/ClipThumb.tsx` names its image `fileName(clip.identity)` (`:34`).
The box fills its column (`thumbs.css:6-13`, `inline-size: 100%; aspect-ratio: 16/9`), and the image is
the service's frame, fitted inside 320×180 (D-11).

**Edit mode**, owned by `edit-mode-polish` and not edited here:

- `ClipOrderList.tsx` renders every row as `li.clip-item[data-status]` (`:278`, `:315`, `:359`), with its
  status `Pill` in `.clip-status` (`:98-102`) and `fileName` for its names and labels.
- Its grid is `2rem 2rem 5rem minmax(0,1fr) 12rem 5.5rem 10.5rem 4.25rem` (`edit.css:200`).
- It lists the ignored clips unnumbered, after the played ones (`editableChapters`, `draft.ts:43-52`).

**The service.** `_build_chapters` (`api/events_read.py:325-376`) lists the document's clips in document
order. Disk-only clips follow in disk sort order, NEW and IGNORED interleaved. So an ignored clip is not
always last in a chapter's list. Disk discovery is one level deep (`event/discovery.py:118-140`). A
document chapter may still list any identity, for example `Kvällen/s1710004.mp4` in the root chapter,
which a render's adoption writes (D-CLI3).

## Goals / Non-Goals

**Goals:**

- Every finding of the brief's P4 section is fixed as reproduced, inside the owned files
  (`EventDetail.tsx` except the Edit / Stop editing button element, `detail.css`, `common.tsx`, and
  `ClipThumb.tsx` / `thumbs.css`).
- The read view and Edit mode agree on:
  - numbering (Edit mode is already right)
  - the included clip's quiet status (one CSS rule reaches both)
- The widths Edit mode needs, for its own alignment fix, are published once, as custom properties.
- The loading state shows the loaded page's shape, and never a name that the read replaces.

**Non-Goals:**

- No edit to `web/src/edit/`, `web/src/jobs/`, `web/src/ui/`, `web/src/shell/`, `web/src/styles/`,
  `events/labels.ts`, `events/tones.ts`, `EventList.tsx` or `list.css`.
- No new icon, no new token in `tokens.css`, and no change to status words.
- No change to how reads, refreshes and quiet re-reads behave (`load`, `reread`, `leaveEditMode` stay
  as they are).

## Research & Decisions

### Supervisor decisions (before implementation)

- **The polish round's context** is the supervisor's polish brief. Five sibling changes run in parallel with
  this one (`edit-mode-polish` P1, `jobs-live-polish` P2, `event-list-polish` P3, `ui-a11y-polish` P5 and
  `serve-clean-exit` P6). This change stays inside its own files ("Files and parallel changes"). Where two
  changes edit neighbouring `web/README.md` hunks, whichever lands second re-applies its own lines and keeps
  every side's.
- **The five column properties are final:** `--clip-col-pos`, `--clip-thumb-w`, `--clip-col-status`,
  `--clip-col-size` and `--clip-col-mtime`. `edit-mode-polish` reads exactly these. Neither change renames
  one alone (this design's first Open Question is answered).
- **The clip rows lose their hover fill.** `event-list-polish` deletes the generic `.data-table` row hover,
  so the chapter tables' rows no longer change colour under the pointer. That is intended: they are not
  clickable. The quiet word's contrast is therefore measured on `--surface` alone after that change lands
  (its 6.1:1 / 6.52:1 hover figures below stop applying).
- **The missing-clips `Alert`'s markup is left as it is.** `ui-a11y-polish` adds `role="note"` to it.
- **`clipNames` and `ClipName` are a stable, documented export.** `edit-mode-polish` lands after this change
  and adopts them in `ClipOrderList.tsx` (this design's second Open Question is answered). Their names,
  signatures and the `span.clip-dir` markup are part of that contract (and the `<wbr />` after it, see
  "Supervisor decisions (after implementation)").
- **The residual loading shift at phone width is accepted** (about 50 px at 390 on Grillning, "Loading: the
  page's own shape"), and documented here and in the spec's 1280-pixel scenario only.

### The findings, re-checked

**Context**: The brief requires every finding to be reproduced before it is fixed. The critics' minor
findings were not adversarially verified.

**Explored**: Two Playwright probes ran read-only against `http://127.0.0.1:8114/`, the final main build.
Every non-GET request was aborted, and none was attempted. They ran in light and dark, at 1280, 768 and 390
px (scratchpad `polish-spec/event-page-polish/p1.py` and `p2.py`, with results in `logs/p1.json`). A third
script (`mock.py`) moved the live DOM and injected the proposed CSS inside the browser only, to try the
layout before specifying it.

**Decision**: All six findings reproduce. None is dropped.

| Finding | Measured (1280 px, light, unless noted) |
|---|---|
| Header stack | Grillning: back link 80, h1 116–148, date 160–181, verdict 193–216, render card 224–282 (8 px below the verdict), `4 clips · 129.4 MiB · Read …` 294–313, first panel 337. The summary is 12 px under the card and 24 px above the panel it describes, and repeats that panel's own "4 clips". `.render-blocked` renders at 14 px beside the 13 px `.job-when`. |
| "Included" everywhere | The Status column is 200 px wide. Lång kväll shows 16 identical grey "Included" pills. Grillning's 4 rows are all "Included". |
| 80×45 thumbnails | Every box is 80×45, and the File column is 526 px for 59–101 px names. The image's natural size is 320×180, which is enough for a 128×72 box at 2×. |
| Ignored clip numbered | Två kapitel's `Main` reads `1 s1710001.mp4 Included`, `2 s1710004.mp4 Included`, `3 s1710004.mp4 Ignored`. Edit mode leaves the ignored row unnumbered. |
| Bare name outside its folder | That `Main` shows `s1710004.mp4` twice. The detail's identities are `Kvällen/s1710004.mp4` (active) and `s1710004.mp4` (ignored), and both images read "Frame from s1710004.mp4". |
| Loading | While reading, the h1 is `2024-06-27 - Grillning med grannar`, then `Grillkväll med grannarna`. The placeholder rows are 40 px, with no thumbnail box and no render card, and its panel starts at 204 against 337 once loaded: a 133 px reflow. |

The page's h1 area is also where the brief (P3) places the page's part of "two events with the same title
are indistinguishable". Both `2024-07-14 - Kalas` and `2024-07-14 - kalas` read h1 `Kalas`, date
`2024-07-14`, and neither page shows its folder name. This change includes that fix.

**Rationale**: Measured on the build the operator runs, not inferred from the code.

### The header: facts first, then one render region

**Context**: The verdict, the job and the Render action tell one story, but they sit in two bands. The
clip summary sits between that story and the table.

**Explored**:

- (a) The critic's fix puts the verdict inside `RenderControl`'s card. That edits `jobs/RenderControl.tsx`,
  which `jobs-live-polish` owns, by more than one line.
- (b) Wrap `StalenessCell` and `RenderControl` in a page-owned frame, and let the inner card drop its own
  frame on this page.
- (c) Leave the bands, and only tighten their gaps.

`mock.py` tried (b): the first panel moves from 337 to 310, and the story reads as one card, the
failed-job note included (Trasig).

**Decision**: (b). The header becomes, in order:

1. `.page-crumbs`: the back link (unchanged element), then the folder name (next section).
2. `.page-title-row`: unchanged. The h1 comes first, then `.page-actions`, whose Edit / Stop editing button
   is left to `edit-mode-polish`.
3. `.page-meta`. It holds `span.event-facts` (date · location, read view only, `--fg`, weight 500,
   `--text-base`), then `Counts` (now plain muted text: `span.counts`, weight 400), then
   `Read {state.fetchedAt.toLocaleTimeString()}`, then `LoadStatus`. The row keeps its place in Edit mode,
   where only the date and location drop out, as the Edit-mode requirement asks.
4. `p.description`, read view only.
5. `div.render-panel`, which holds `StalenessCell` and then `RenderControl`, with the same props and
   `blockedReason` expression as today.

`EventFacts` becomes `RenderPanel` (item 5). Items 3 and 4 move into `EventDetail`'s header.

```css
/* detail.css, @layer screens */
.render-panel {
  display: grid;
  gap: var(--s-3);
  min-inline-size: 0;
  padding: var(--s-3) var(--s-4);
  border: 1px solid var(--border);
  border-radius: var(--r-lg);
  background: var(--surface);
  transition: border-color var(--dur-med) var(--ease-out);

  /* A job in progress: the region takes the accent's edge, as the card did. */
  &:has(.render-card[data-active]) {
    border-color: color-mix(in oklab, var(--accent) 45%, var(--border));
  }

  /* The page frames the region: RenderControl's own card drops its frame here. */
  & .render-card {
    padding: 0;
    border: 0;
    border-radius: 0;
    background: none;
  }

  & :is(.render-none, .render-blocked) {
    font-size: var(--text-sm);
  }
}
```

`.status-line` and its rule go. `RenderControl`'s alerts (why a job failed, the collision notice) now sit
inside the region, under the job line, where they belong to the render story. The region MUST keep
`RenderControl`'s element and props as they are (the reset is CSS only), so `jobs-live-polish`'s one-line
call site re-applies.

The meta row's `4 clips · 129.4 MiB` still repeats the panel's `4 clips` on a one-chapter event (part of the
critic's finding). That is kept: the meta row is the event's summary (all chapters, the size, the new,
missing and ignored counts), and the panel's count is the chapter's. With several chapters they differ.

The review spike (scratchpad `polish-spec/event-page-polish/review/spike.py`, the design's CSS injected into
the live :8114 page) measured this layout at 1280: the region 193–286, the first panel at 310 (24 px under
it), the inner card's `border-top-width` 0px, in light and dark, with no horizontal scroll at 1280, 1024,
768, 390 and 320.

**Rationale**: This gives one card for the whole render story without editing `jobs/`. The screen layer
beats `@layer components` whatever the specificity, so the override is four properties and needs no
`!important`. `:has()` is already used in `jobs.css`, so it is within the support floor. Keeping
"Read <time>" in the meta line (the critic suggested moving it beside Refresh) keeps the list's pattern:
title row, then a meta row with the counts and the read time.

### The folder name beside a title

**Context**: A title and a date can be shared by two events (the output-collision fixture). The collision
notice then names folders that no page shows.

**Explored**:

- (a) Always show the folder.
- (b) Show it only when it differs from what the title, date and location would produce. That re-derives
  the folder-naming rule in the client (fragile, and `Kalas` would hide on one page of the pair).
- (c) Put it in `document.title`.

**Decision**: (a) with one exception. After the back link, `span.crumb-folder` shows `folderName(eventId)`
in `--font-mono`, `--text-sm`, `--fg-muted`, with `overflow-wrap: anywhere`. A `::before` separator is
hidden from assistive technology, declared twice as `components.css` declares its `data-label` text
(`content: '/'; content: '/' / '';`), so an engine below the alt-text syntax still draws it. The separator
is text, so it takes `--fg-muted`, not `--fg-subtle` (web-design-system: `--fg-subtle` is never text). A
visually hidden "Folder: " prefix names the line for assistive technology. It shows while the page reads
(the id is known from the address, so nothing is invented). Once the page is ready it shows only when
`title != null && title !== folderName(eventId)`, and it is hidden on a failed read, whose h1 already is
the folder name. `document.title` is unchanged.

The line comes before the h1, and focus lands on the h1 after every navigation, so a screen reader reading
on from the heading would never reach it. When the page is ready and the line is shown, the h1 MUST carry
`aria-describedby` with the line's `useId()` id, so the heading reads "Kalas" with the description
"Folder: 2024-07-14 - kalas", as `event-list-polish` describes its look-alike title links. While loading,
the h1 carries no description, because its accessible name already is the folder name. The id sits on an
inner span, `span.crumb-folder > span#id`, which holds the visually hidden "Folder: " and the folder name,
so the description never includes the separator (changed during implementation, item 1; accepted).

The class is `crumb-folder`, not `event-folder`. `event-list-polish` gives that name to its list rows'
folder line (`display: block`, in `list.css`), and Vite bundles every screen's CSS into one sheet, so two
rules with that name would meet on this page.

**Rationale**: The folder is the event's id and its place on disk. It needs no derivation, it is never
wrong, and it costs no band: it shares the back link's line. The exception keeps `Blandat / Blandat` from
repeating itself. The list shows the folder only on look-alike rows (`event-list-polish`), because there
it would double the text of every row. A page has one such line, so it shows the folder whenever the
title differs, and the collision notice's folder names always match something on the page.

### An included clip's status: quiet words

**Context**: The operator scans for new, missing and ignored clips. "Included" is the usual case, but it
has the same pill weight as they do.

**Explored**:

- (a) Show nothing for an included clip, and keep a visually hidden word. `mock.py` showed this leaves a
  Status column with a header over empty cells for every event with no exception, which reads as missing
  data.
- (b) Quiet words: the same word and icon, without the pill's fill and edge (`mockq.py`).
- (c) Move the exception pills into the File cell and drop the column. That breaks the column set that
  Edit mode must align with (`edit-mode-polish`).
- Narrowing `.col-status` (the critic's fix) cannot help while "New, not yet in reel.yaml"
  (`labels.ts`, not owned here) needs the width.

**Decision**: (b), by CSS on the existing markup, in `detail.css`. The rule MUST keep the word and the icon
(D-10: status is never color alone) and MUST NOT hide either:

```css
/* An included clip, the usual case: its word and icon, without a label's fill and edge (both views). */
:is(.clip-row, .clip-item)[data-status='active'] .pill {
  --_bg: transparent;
  --_fg: var(--fg-muted);
  padding-inline: 0;
  box-shadow: none;
  font-weight: 400;

  & > svg {
    color: var(--fg-subtle);
  }
}
```

The words and the icon stay. The rule is about the look only: "never by color alone" still holds, and
`--fg-muted` text meets 4.5:1 in both schemes (D-10). The review spike measured the quiet word at 6.85:1 on
`--surface` and 6.1:1 on the hover row in light, 7.38:1 and 6.52:1 in dark, and its `--fg-subtle` icon at
3.62:1 and 3.94:1 (non-text, 3:1). `li.clip-item[data-status]` is Edit mode's row, and
its only `.pill` is the status: the "moved" and "was N" marks are `.badge`. So Edit mode agrees with the
read view without any edit to `web/src/edit/`.

**Rationale**: The column keeps its meaning and the exceptions stand out, with no hidden information and
no layout change for Edit mode's alignment. The spec states the look in one sentence, because the
requirement already describes the status display. The convention outlives this change, and D-10 keeps its
conventions in `web/README.md`, "Design system", so task 4.1 records it there. The HLD gains no D-n entry.

### Ignored clips: after the played ones, with no position

**Context**: The service interleaves NEW and IGNORED disk-only clips in disk order. The read view numbers
every row.

**Decision**: `ChapterPanel` MUST partition `chapter.clips` stably, with the same predicate as Edit mode's
`editableChapters`: `played = clips.filter(c => c.status !== 'ignored')`, then `ignored`. It numbers
`played` from 1, and leaves each ignored row's `td.cell-pos` empty. The shipped Två kapitel already lists
its ignored clip last, so only the numbering shows there. The verification fixture adds a NEW root clip
that the service lists after the ignored one, to show the partition itself. The keys stay `clip.identity`. The panel meta counts the
clips the chapter plays, and the ignored ones after them: `plural(played.length, 'clip', 'clips')`, plus
`` ` · ${ignored.length} ignored` `` when there are any. So the heading's count is the last position
number, as in Edit mode, whose heading counts the clips the chapter plays (`edit-mode-polish`). The page's
counts line keeps counting every listed clip, with the ignored ones as a part (`5 clips · … · 1 ignored`):
2 + 2 played and 1 ignored add up to it. (Changed in review: the counts line counts the played clips too,
with their size, and the ignored ones after them. See "Changed during review".)

**Rationale**: This is exactly Edit mode's order (`editableChapters`): played in detail order, then
ignored. The two views of a chapter now list the same clips in the same order with the same numbers. An
empty position is how Edit mode already shows "not played".

### Names across folders

**Context**: A chapter can list a clip from another folder: the root chapter holding `Kvällen/…` (render
adoption), or a hand edit. Camera numbering repeats across folders, so bare names collide, as
`s1710004.mp4` did in the live data.

**Explored**:

- (a) Per clip: strip the chapter's own `folder/` prefix, else show the full identity. This fails in the
  mirror case: in chapter `Kvällen`, the root `s1710004.mp4` and `Kvällen/s1710004.mp4` would both read
  `s1710004.mp4`.
- (b) Per chapter: while every listed identity lies in the chapter's folder, show file names. Otherwise show
  every identity in full. Identities are unique within an event, so no two rows can read alike.

**Decision**: (b), in `events/common.tsx`. The names MUST come from the detail's identities only, never
from a guess about where a chapter's folder is:

```ts
/** The identity's folder: '' for a file at the event folder's root. */
function folderOf(identity: string): string

/**
 * How a chapter names its clips: by file name while every clip it lists lies in its
 * own folder (the event folder for the default chapter ''), else each by its path in
 * the event folder, so that no two of its rows read alike.
 */
export function clipNames(chapter: string, identities: readonly string[]): (identity: string) => string

/**
 * A name, its folder part muted: <span class="clip-dir">Kvällen/</span>s1710004.mp4.
 * A narrow cell breaks it after the folder (a <wbr /> follows span.clip-dir).
 */
export function ClipName({ name }: { name: string }): ReactNode
```

`ChapterPanel` computes `const nameOf = clipNames(chapter.name, chapter.clips.map(c => c.identity))`. The
File cell renders `<ClipName name={nameOf(clip.identity)} />`, and the row passes
`name={nameOf(clip.identity)}` to `ClipThumb`. `ClipThumb` gains an optional `name?: string`, which
defaults to `fileName(clip.identity)` as today, and uses it for "Frame from …" and
"No preview for …". That is why the spec delta also modifies "Thumbnails never hold up or break a page":
its "No preview for <file name>" becomes the row's name, in the same words as the frame's text alternative. `.clip-dir` is `color: var(--fg-muted)` in `detail.css`. Some cases for
the verification task:

| chapter | identities | names |
|---|---|---|
| `''` | `s1710001.mp4`, `Kvällen/s1710004.mp4`, `s1710004.mp4` | `s1710001.mp4`, `Kvällen/s1710004.mp4`, `s1710004.mp4` |
| `Kvällen` | `Kvällen/s1710002.mp4`, `Kvällen/s1710003.mp4` | `s1710002.mp4`, `s1710003.mp4` |
| `Kvällen` | `Kvällen/s1710002.mp4`, `s1710004.mp4` | `Kvällen/s1710002.mp4`, `s1710004.mp4` |
| `Förmiddag` (no folder) | `a.mp4`, `b.mp4` | `a.mp4`, `b.mp4` |

**Rationale**: The rule is chapter-wide and unambiguous, and the common case (the root chapter) keeps its
bare names. Edit mode's rows (`ClipOrderList.tsx`) still call `fileName`. Their many call sites (row,
handle, move, Remove and Undo labels, and the announcements) are more than a one-line change in a file
this change does not own, so `clipNames` and `ClipName` are exported for `edit-mode-polish` to adopt
("Open Questions").

### Thumbnail size, and the column contract

**Context**: The box fills a 5rem column at every width. The service's frame is at most 320×180 (D-11).
Edit mode's alignment fix (`edit-mode-polish`) needs the read view's final widths.

**Explored**:

- A 60rem threshold (the critic's) gives 8rem frames from a 1024 px window. Edit mode's tracks with an 8rem
  frame (handle 2rem, moves 4.25rem, 7 gaps, about 50.75rem fixed) would leave its file column 9.25rem at a
  60rem panel, under the 11rem an 18-character camera name needs.
- At 64rem the read table's file column keeps 22rem, and Edit mode's current tracks, with an 8rem frame,
  keep 13.25rem. How `edit-mode-polish` realigns those tracks is its own design.
- 10rem frames would be sharp too (320 px at 2×), but they make every row 106 px, against 89 px at
  8rem.

**Decision**: 8rem (128×72) where the chapter's panel is at least 64rem wide, 5rem (80×45) otherwise,
including every card layout. The widths are published as custom properties. Their names MUST be the ones
`edit-mode-polish` reads: its proposal lists `--clip-col-pos`, `--clip-thumb-w`, `--clip-col-status`,
`--clip-col-size` and `--clip-col-mtime`, each read with today's width as its fallback. A name that differs
fails silently: Edit mode would fall back to a 5rem frame while the table shows 8rem, and its "moves no
column" requirement would fail at 1280. So the thumbnail's property is `--clip-thumb-w`, not
`--clip-col-thumb`, and task 1.1 stops on any mismatch:

```css
/* detail.css, @layer screens: the clip columns, read by the table here and by Edit mode's grid. */
.event-detail {
  --clip-col-pos: 3.5rem;
  --clip-thumb-w: 5rem;
  --clip-col-status: 12.5rem;
  --clip-col-size: 6.5rem;
  --clip-col-mtime: 11.5rem;
}

/* A wide panel: a larger frame (128 × 72; the 320 × 180 source stays sharp at 2×). */
@container (width >= 64rem) {
  .event-detail .panel > * {
    --clip-thumb-w: 8rem;
  }
}
```

The `.clip-table .col-*` rules read `var(--clip-col-*)`. The card layouts'
`grid-template-columns: 2rem 5rem …` becomes `2rem var(--clip-thumb-w) …`, which is 5rem there, since a
card panel is under 50rem. `.panel > *` is the element set whose query container is the panel. The value
is inherited by everything inside it: the table here, and Edit mode's `.clip-order-head` and
`ol/ul.clip-order` rows.

The review spike confirmed both halves: the boxes measure 128×72 at 1280 and 1100 and 80×45 at 1024, 768,
390 and 320, and in Edit mode at 1280 `getComputedStyle` gives the thumbnail property `8rem` on
`.clip-order` and on `.clip-order-head` (5rem at 390). (The spike ran under the earlier name
`--clip-col-thumb`; the name does not change the mechanism.)

Rows at 1280 grow from 62 to 89 px. The box is sized by CSS before any byte arrives, and the `<img>`
keeps `width={320} height={180}`, so nothing moves when an image loads.

**Rationale**: This follows the critic's measure (8rem) with a threshold that is safe for both views.
One set of properties is the whole contract with Edit mode. `thumbs.css` needs no change, because the
box already fills its column. The contract outlives this change, so task 4.1 records the five names in
`web/README.md`, "Design system", as D-10 asks of its conventions.

### Loading: the page's own shape

**Context**: `SkeletonRows` has the list's shape, and the h1 shows a provisional name.

**Explored**: The critic suggested showing the list's cached title when the user came from the list. That
couples the page to the list's state and still differs on a direct open, so it was not adopted.

**Decision**: While `state.status === 'loading'`, the page MUST show these placeholders, and they MUST
carry no event data (the folder name comes from the address):

- **h1**: `<span className="visually-hidden">{folderName(eventId)}</span><span className="skeleton
  skeleton-h1" aria-hidden="true" />`. The folder name is the heading's accessible name, and its focus
  target is unchanged. `.skeleton-h1` is `display: inline-block; vertical-align: middle; inline-size:
  18rem; max-inline-size: 100%; block-size: 1.25rem`, so the h1 keeps its line box. The width MUST be a
  length, not a percentage of the h1: the h1 is a shrink-to-fit flex item whose only other content is
  absolutely positioned, so a percentage width resolves against a zero-width h1. The review spike showed
  exactly that with the first draft's `min(18rem, 70%)`: the bar was 0 px wide and the heading looked empty.
  With 18rem it shows, and at 390 the title row wraps as it does for a real title, so Refresh sits under
  the heading.
- **meta line**: `<span className="event-facts"><span className="skeleton skeleton-facts" aria-hidden="true"
  /></span>` (a 12rem bar, `display: inline-block; vertical-align: middle`, so the facts keep their own line
  height), then `LoadStatus` "Reading event…".
- **render region**: `<div className="render-panel" aria-hidden="true">` holding two rows, each a wrapping
  flex row (`flex-wrap: wrap; align-items: center; gap: var(--s-3)`):
  - a `skeleton-verdict` bar (5.5rem × 1.25rem) and a text bar
  - a short text bar, then a `skeleton-button` (6.5rem × 2rem, `--r-md`, pushed to the end)

  The text bars MUST shrink as `.skeleton-title` does (`flex: 0 1 auto; min-inline-size: 0`), because
  `.skeleton` is `flex: none`. The spike's fixed bars widened a 320 px page to 325 px. With shrinking bars
  it stays at 320.
- **content**: one `section.panel` with `aria-hidden="true"`, whose header has a heading bar. It holds a
  real `table.data-table.clip-table`: the same `<colgroup>` and `<thead>` as `ChapterPanel` (factored as
  `ClipTableHead`), and 4 `tr.clip-row`. Each row has a number bar, `<span className="clip-thumb"
  data-state="loading" />`, a file bar of varied width, a short status bar (the quiet word's shape), a size
  bar and a time bar. Bars in cells are `display: inline-block; vertical-align: middle`, so each row is laid
  out as a loaded row at every width and in the card layouts. At 1280 its height is the thumbnail box plus
  the cell padding, exactly as a loaded row. The status bar keeps the card layouts' status line from
  collapsing: without it a 320 px placeholder row was 99 px against 142 px loaded (about 120 px with it).

(Changed in review: the header's actions keep Edit's place while reading, and the placeholders fill with
`GrayText` in forced colors. See "Changed during review".)

The page stops importing `SkeletonRows` (`ui/Skeleton.tsx` is unchanged, and the list still uses it).
Every bar is the existing `.skeleton` class, whose shimmer is already gated behind
`prefers-reduced-motion: no-preference`. The box reuses the thumbnail's own loading state, which is gated
the same way. New sizes live in `detail.css` and carry no animation.

The review spike built this placeholder in the live page and measured it against the loaded layout. At
1280, 1100, 1024 and 768 the first chapter moves by 3 px when the read answers (Grillning: a 90 px
placeholder region against the 93 px loaded one), and at 1280 each placeholder row is 89 px, as a loaded
row. The spec pins 8 px at 1280, and task 5.1 measures it. At phone width the residual is larger and
depends on the read: 50 px at 390 on Grillning, where its reasons and its job line wrap inside the region,
and 80 px at 320, where its title also wraps. A description, wrapped reasons, a two-line title or a
failed-job note add height on arrival, and nothing can predict those without the read. The page no longer
reflows by 133 px at desktop width.

**Rationale**: Reusing the table's own markup is the only way the placeholder matches every breakpoint
without a second set of layout rules.

### Files and parallel changes

**Context**: The brief's five web changes run in parallel. This change owns `EventDetail.tsx` (except the
Edit / Stop editing header button), `detail.css`, `common.tsx`, `ClipThumb.tsx` and `thumbs.css` sizing.

**Decision**:

- **This change edits** `EventDetail.tsx`, `detail.css`, `common.tsx`, `ClipThumb.tsx` and `web/README.md`
  (the event-page sentence, two "Design system" sentences and two file-tree lines, task 4.1). It does not
  edit `thumbs.css`, and it touches no file that another change owns, not even for a one-line call site.
- **`edit-mode-polish` (P1)**:
  - It owns the Edit / Stop editing `<button>` element (`EventDetail.tsx:228-251`), which this change
    leaves byte-identical inside the unchanged `.page-actions`.
  - Its grid alignment builds its tracks from this change's column properties, each read with today's
    width as its fallback. Its proposal names them `--clip-col-pos`, `--clip-thumb-w`, `--clip-col-status`,
    `--clip-col-size` and `--clip-col-mtime`, and this change defines exactly those names ("Thumbnail size,
    and the column contract"). A fallback hides a misspelt name, so task 1.1 compares the names with
    `edit-mode-polish`'s design or `edit.css` and stops on any difference.
  - Its Edit rows can adopt `clipNames` / `ClipName` (and pass `name` to `ClipThumb`).
  - The quiet-status rule already reaches its rows through `li.clip-item[data-status='active'] .pill`. It
    must keep the `clip-item` class, `data-status` and the status `Pill`.
- **`jobs-live-polish` (P2)**: `jobs/*` is not edited. The frame reset depends on the class names
  `render-card`, `render-none` and `render-blocked` and on `render-card[data-active]`, which P2 keeps (its
  design leaves the card's markup alone). P2 adds one line, `title={event.title}`, on `<RenderControl>`.
  That element moves unchanged into `RenderPanel`, so its line re-applies there.
- **`event-list-polish` (P3)**: its design lists its call sites in this change's files.
  - **In `EventDetail.tsx`:** the imports, `describeProblem`'s 404 and 502 `detail`, `load()`'s
    `unreachable`/`unpublished` case, the "Read" span (`formatInstant(state.fetchedAt)`) and the clip time
    (`formatInstant(clip.mtime)`). This change leaves `describeProblem` and `load` as they are. It moves the
    "Read" span only within the header, into the meta row, and keeps the mtime cell's expression, so P3's
    lines rebase mechanically. Whichever change lands second re-applies the other's lines.
  - **In `common.tsx`:** the `UNREACHABLE_CAUSE` line and an import. This change adds exports below
    `fileName` and does not touch that line.
  - **The mtime column:** P3 measures its format at about 142 px at most, so `--clip-col-mtime` keeps
    11.5rem, which also fits today's format if P3 lands later. Narrowing it is one line, after both land.
  - Both screens use the same folder word, `folderName(eventId)`.
  - **In `web/README.md`:** P3 edits the list's sentences of the paragraph whose event-page sentence this
    change edits, and adds to "Design system" and the file tree, where this change also adds sentences and
    lines (task 4.1). `edit-mode-polish` edits the Edit-mode paragraph and the toast bullet. The hunks are
    neighbours, not shared, and whichever change lands second re-applies its own sentences on top of the
    others'.
- **`ui-a11y-polish` (P5)** adds `role="note"` to the missing-clips `Alert` in `ReadyView`, one attribute.
  This change leaves that element where it is.
  `ui/Skeleton.tsx`, `ui/Alert.tsx` and `components.css` are untouched here, and `.skeleton` and
  `.visually-hidden` are reused as they are.

**Rationale**: Every dependency between changes is either a named class, attribute or custom property,
or another change's one-line call site in this change's file, which whichever change lands second
re-applies.

### Verification fixture

**Context**: The shipped dev library does not have a root chapter that holds `Kvällen/s1710004.mp4`.
The live :8114 library has it only because a render adopted it.

**Decision**: In the implementing agent's own library copy only, add `Kvällen/s1710004.mp4` as the last
clip of `2024/2024-08-20 - Två kapitel - Tjörn/reel.yaml`'s root chapter. This is a text edit. It needs
no worker and no render. Then `GET …/events/<id>` must list `Main` as `s1710001.mp4` (active),
`Kvällen/s1710004.mp4` (active) and `s1710004.mp4` (ignored). Take the other screens from the shipped
library: Två kapitel before the edit, Kalas/kalas, Blandat, Grillning, Sommarlov and Omöjligt datum.

After the names are checked, a second step shows the partition itself, which the shipped data cannot,
because its ignored clip is already last. Copy `clips/s1710002.mp4` (a copy, never a hard link, so the
shared file's time stays) to `s1710009.mp4` in Två kapitel's root folder, then `touch` it. It is NEW, and
it sorts after `s1710004.mp4` by name and by time, so the service lists `Main` as `s1710001.mp4`,
`Kvällen/s1710004.mp4`, `s1710004.mp4` (ignored) and then `s1710009.mp4` (new).

**Rationale**: This reproduces the finding's exact state without running the adoption path that the brief
places out of this round, and gives the partition a case where it changes the order.

### Changed during implementation

The verification pass (task 5.1) found three things the decisions above did not foresee. Each is a
markup or CSS detail inside this change's files, and none changes a spec sentence:

1. **The heading's description is the folder line's inner span.** With the `id` on `span.crumb-folder`,
   Chromium's own accessibility tree already gave the h1 the description "Folder: 2024-07-14 - Kalas"
   (the `'/' / ''` alternative text is honoured). But Playwright 1.49's name computation reads the `::before`
   value raw and returned `"/" / " Folder: …"`. An engine inside the support floor that predates the
   alternative-text syntax (Firefox 120–127) also keeps the plain `content: '/'` and would read the slash.
   So the `useId()` id now sits on an inner span, `span.crumb-folder > span#id`, which holds the visually
   hidden "Folder: " and the folder name. The separator lives on the outer span, outside the subtree the
   description reads, so every engine and the test compute the same words. `.crumb-folder`'s text and look
   are unchanged.
2. **The crumb line is top-aligned, and the folder is padded as the back link is.** `align-items: baseline`
   placed "Events" about 4 px above the folder: an `inline-flex` link takes its baseline from its first
   item, the icon's bottom edge. `center` fixed one line but floated the link between two lines where the
   folder wraps (320 px). `flex-start`, with the folder's `padding-block: 0.125rem` matching the link's,
   puts both first lines on one line in every case.
3. **`ClipName` offers a break after the folder part** (`<wbr />` after `span.clip-dir`). In the 320 px
   cards `Kvällen/s1710004.mp4` broke inside the file name (`Kvällen/s17100` / `04.mp4`). It now breaks
   as `Kvällen/` / `s1710004.mp4`. The text content is unchanged.

Smaller choices, within the decisions:

- The `.counts` rule is gone, not restyled. `span.counts` inherits `.page-meta`'s muted colour and
  weight 400, which is what the design asks.
- `.back-link` loses `align-self: flex-start` and gains `flex: none`. It now sits in the `.page-crumbs`
  row rather than the header's column, so it must not shrink when the folder name wraps.
- The placeholder's text bars in the render region reuse `.skeleton-title` (`flex: 0 1 auto;
  min-inline-size: 0`), as the design describes, and the region's two rows are `.skeleton-line`. The
  in-cell bars are sized inline, as `SkeletonRows` sizes its title bars. The bars carry no data.
- The read view's rows keep their order through one list, `[...played, ...ignored]`, numbered while the
  index is within `played`, so each key is still `clip.identity`.

### Supervisor decisions (after implementation)

- **All four implementation changes are accepted:** the inner span that carries the heading's
  description id (item 1), the top-aligned crumb line (item 2), the `<wbr />` in `ClipName` (item 3), and
  the two small CSS changes (`.counts` removed, `.back-link`'s `flex: none`).
- **`clipNames` and `ClipName` stay exported and stable** for `edit-mode-polish`. The contract is their
  names, their signatures, `span.clip-dir` around the folder part, and the `<wbr />` after it.

### Changed during review

The supervisor's review (two Opus lenses, with skeptics re-checking each finding) confirmed four minor
findings and refuted none. All four were fixed on the pr branch, each in its own commit. None changes a
spec sentence.

1. **The README gave Edit mode's frames as 128 × 72.** Edit mode's grid keeps a literal `5rem` thumbnail
   track (`edit/edit.css`) until `edit-mode-polish` reads `--clip-thumb-w` (Risks). The review measured
   80 × 45 boxes in Edit mode at 1280 against 128 × 72 in the read view. The sentence in `web/README.md`
   now says "80 × 45, and 128 × 72 in the chapter tables at desktop width", which is true today.
   `edit-mode-polish` updates it when its rows adopt the property.
2. **Forced colors erased the loading page.** Every placeholder is a background: the `.skeleton` bars and
   the loading `.clip-thumb`, whose edge is a box-shadow. Forced colors drop both. So the h1 showed nothing
   (main showed the folder name there), the facts bar and the render region were empty, and the chapter
   placeholder showed real column headers over four blank rows. It read as an empty event rather than a
   loading one, against the requirement's "the heading SHALL show a placeholder". `detail.css` now adds,
   in `@layer screens`:

   ```css
   @media (forced-colors: active) {
     .event-detail :is(.skeleton, .clip-thumb[data-state='loading']) {
       forced-color-adjust: none;
       background: GrayText;
     }
   }
   ```

   This also covers a frame still loading in a loaded row and in Edit mode, which forced colors left blank
   in the same way. Measured with Chromium's forced colors at 1280 and 390, in the light and dark schemes:
   - all 32 placeholders paint (`GrayText` is rgb(96, 0, 0) on white, and rgb(63, 242, 63) on black)
   - the heading's bar is 288 × 20
   - the loaded page shows its four frames and no placeholder

   Without forced colors the placeholders keep their own fill (the shimmer's gradient, or `--border` under
   reduced motion), and `forced-color-adjust` stays `auto`.
3. **Refresh moved 88 px during every read.** The Edit button exists only in `ready`, so a plain read
   (opening the page, Refresh, leaving Edit mode) laid out Refresh alone at the end of the row. At 1280,
   Refresh went from x=1027 to 1115 and back, and the busy button left the pointer that pressed it. This
   was already so on main, but it was the one part of the header the placeholders still previewed wrong.
   While reading, `.page-actions` now holds `<span className="skeleton skeleton-action" aria-hidden="true" />`
   after Refresh (4.75rem × 2rem, `--r-md`). It is a sibling of the buttons, so `edit-mode-polish`'s Edit /
   Stop editing `<button>` stays byte-identical.

   The finding's fix kept the place on every read. That would move Refresh 88 px the other way when the
   operator retries a failed read, since a failed page has no Edit. So the loading state carries
   `editPlace`: true on the first read and after a ready page, false after a failure, and kept when a
   read restarts a read. Measured at 1280, 1024, 768 and 390 (Grillning):
   - Refresh's position is the same, within 0.4 px, on the first read, before, during and after a
     Refresh, and while the read that leaves Edit mode runs
   - the point that was pressed is still Refresh during the read
   - the place is 76 × 32, against Edit's 75.6 × 32 (Noto Sans in the container)
   - after a failed read (Omöjligt datum), there is no place and Refresh stays at x=1114.8 throughout
   - reduced motion still shows 0 animations while the read is held
4. **"N clips" meant two things on one screen.** The page's line counted every listed clip, with the
   ignored ones inside it. Each chapter's heading, and Edit mode's, counts the clips it plays, with the
   ignored ones after them. So Två kapitel (partition fixture) read "6 clips · 194.4 MiB · 1 new · 1
   ignored" above "3 clips · 1 ignored" and "2 clips", which looks like an arithmetic error. `Counts` now
   counts the played clips (`status !== 'ignored'`, so the new and missing ones are among them), then
   adds "· N ignored" as the headings do. Its size is now the played clips' size too. With the old total,
   "5 clips · 194.4 MiB" would include a clip that the five do not. Measured:
   - partition fixture: "5 clips · 162.0 MiB · 1 new · 1 ignored" (the chapters add up to 5, and 5 rows
     are numbered)
   - shipped library: "4 clips · 129.4 MiB · 1 new · 1 ignored" over "1 clip · 1 ignored" and "3 clips"
   - Edit mode: the same headings and the same line
   - Grillning, with no ignored clip: unchanged ("4 clips · 129.4 MiB")
   - Sommarlov: its missing clip is counted ("3 clips · 65.0 MiB · 1 missing")

   The requirement's "counts of its clips, their total size, and its new, missing and ignored clips"
   reads the same under this convention. The event list still counts every clip: its `clip_count` is the
   service's classification count, ignored clips included. So the shipped Två kapitel reads "5 clips"
   there and "4 clips · … · 1 ignored" here. The list never shows an ignored count, and aligning it is a
   service and list change, left as a follow-up (Risks).

## Failure behavior and idempotency

- **The page writes nothing.** No request is added: the thumbnail addresses and the reads are unchanged.
  A re-run, a `--force` render or a worker restart has no interaction with this change.
- **A failed read** replaces the page as today, with the h1 set to the folder name and no folder line,
  region or placeholder. The placeholders exist only in `loading`, so the page never shows an earlier
  state as current. A Refresh from a failed read keeps no place for Edit, so Refresh stays where it was
  (Changed during review, item 3).
- **A failed thumbnail** still shows "No preview for <name>", now with the row's name.
- **No new fallback invents a fact.** The folder name comes from the address, and the names come from the
  detail's identities.

## Risks / Trade-offs

- [The page resets `RenderControl`'s card frame from the screen layer] → The dependency is declared by
  class name. Task 5.1 checks that the inner card has no border and that the region takes the accent
  edge during a job, so a rename in `jobs.css` shows up in verification, not silently.
- [The quiet-status selector reaches Edit mode's markup] → It is keyed on `data-status` and `.pill`,
  which both views already render for this purpose. Task 5.1 checks Edit mode too.
- [Edit mode keeps bare names, and 5rem frames at desktop, until `edit-mode-polish` adopts the helpers and
  properties] → Recorded for the supervisor ("Open Questions"). Each side is correct on its own, since
  Edit mode's rows name what they show, and neither blocks the other. `web/README.md` gives the sizes as
  they are until then (Changed during review, item 1).
- [Edit's place is a fixed 4.75rem] → It matches the Edit button in the container's font (76 against
  75.6 px). In the operator's `system-ui` font the two may differ by a pixel or two, which moves Refresh by
  as much during a read, not by 88 px.
- [The event list counts ignored clips, the page does not] → The list's "N clips" is the service's
  `clip_count`, every classified clip, while the page's line is the played clips plus "· N ignored"
  (Changed during review, item 4). The page's own figures now agree with each other, and its line names the
  difference. Counting played clips in the list is a service change (`clip_count`) and an `EventList.tsx`
  change, left as a follow-up.
- [Taller rows: 89 px against 62 px at desktop] → A 380-clip chapter is about 10k px longer. Lazy loading
  still bounds the requests to rows near the view (the existing requirement). Card layouts keep 80×45.
- [Chapter-wide full paths make a folder chapter verbose when a hand edit adds one outside clip] → That is
  rare, and it is never ambiguous. The folder part is muted.
- [Placeholders cannot predict a description, wrapped reasons or a failed-job note] → The page no longer
  reflows by 133 px; the residual is the height of what only the read knows.

## Migration Plan

Web assets only. `npm run build` ships them with the next `auto-reel serve`, and there is no data, schema
or config migration. Rollback is a revert of the four source files and the README lines.

## Open Questions

These are for the supervisor. None changes this change's specs, approach or tasks. The first two are
answered (Supervisor decisions).

- **The column property names.** Answered (Supervisor decisions): the five names are final. This change
  uses `edit-mode-polish`'s published list, with `--clip-thumb-w` for the frame (the first draft said
  `--clip-col-thumb`). Neither side may rename alone: a fallback in `var()` hides the mismatch, and Edit
  mode then shows 80 px frames beside a 128 px table at 1280. If `edit-mode-polish` archives first with
  literal widths instead, its thumbnail track becomes `var(--clip-thumb-w)` (one line in `edit.css`).
- **Edit mode's names.** Answered (Supervisor decisions): `edit-mode-polish` adopts `clipNames` /
  `ClipName` in `ClipOrderList.tsx` after this change lands. Until then, Edit mode's `Main` on the fixture
  reads `s1710004.mp4` twice, as the read view did before.
- **An unassigned finding in this change's file**, left as it is: in Edit mode, the verdict stays stale
  after a live render ends (integration critic, minor), because `reread` is skipped while editing. Fixing
  it is behaviour plus a spec sentence. The missing-clips `Alert`'s role, which the same critics raised,
  is `ui-a11y-polish`'s one-attribute call site.
- **Another unassigned minor in this change's file**, left as it is: the design critic measured the back
  link at 71×24 at 390 (touch targets, together with `.btn-compact`, `.segmented` and the theme control in
  other changes' files). Its fix is one `@media (pointer: coarse)` rule across those files, so it belongs
  to one change, not four.
