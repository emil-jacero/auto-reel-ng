## Why

auto-reel had no way to leave part of a clip out of the movie except to cut the file by hand. auto-reel-ng
made cuts part of the editorial model: a clip's `trims` in `reel.yaml` are the spans the render removes, any
number per clip (decision **D-D**, "Trims are CUT ranges"), and the render keeps the footage around them
(`render-segments`). `reel.yaml` is the place to author them (D-2, Principle II). The complete-state
`PUT …/reel` has carried them since `editorial-write-api` (D-E2).

The GUI cannot touch them. GUI v1's Edit mode (HLD **§6 phase 8**, §4.10 slice D) reorders clips, edits
metadata, removes missing clips and, once `chapter-management-screen` lands, edits chapters. It shows no cut
and makes none. The event page does not show them either, so the page does not show what the movie will
leave out. §4.10 puts drag-trim in the v3 timeline editor and approving analysis cuts in v2. Until then the
operator hand-edits `reel.yaml`, which is the habit this rewrite exists to retire.

The operator asked for this ("do 1 and 2"). This change is item 2: cut editing with **typed** times. Item 1
is `chapter-management-screen`, which this change builds on.

## What Changes

- **A Cuts control on every played clip that is on disk, in Edit mode.** It opens a panel under the clip's row
  that lists the clip's cuts (start → end, length, reason) and adds one from two typed times.
  - Accepted forms: seconds (`75.5`), `m:ss` (`1:15.5`) and `h:mm:ss` (`1:01:15.5`), with up to three
    decimals after `.` or `,`.
  - A cut is refused, at the field and in words, when a time cannot be read, when it does not end after it
    starts, or when it overlaps another cut of the clip. These are the engine's own rules (non-negative,
    `out > in`), plus the no-overlap rule the `reel-document` spec states.
  - The page does not know a clip's length: no read is probe-free and carries it. The panel says what the
    render does with a cut past the clip's end: it stops at the end, and a cut over the whole clip leaves the
    clip out of the movie.
  - The control shows the clip's cut count and the time cut out ("2 cuts · −4.5 s"). On a phone it sits in the
    row's empty cell under the drag handle and shows the count only, so no row grows (measured on main's build).
- **Remove** on each cut. A cut read from `reel.yaml` stays listed, struck through, with **Undo** until the edits
  are saved. An Undo that would overlap a cut added since is refused, as adding that cut would be. A cut added
  in this Edit mode is simply gone. A cut added in Edit mode is written with the reason
  `manual`, the value D-K documents for a cut made by hand.
- **Missing and ignored clips.** A missing clip's cuts are shown in its row, not edited: its file is not
  there to cut, and removing its entry drops them (as today). An ignored clip has no cuts, since `reel.yaml`
  holds no properties for a clip no chapter lists.
- **What a save writes.** Only the changed clips' `trims`, with their `title`, `rotate` and `exclude` as read.
  A clip left with no cut and no other property leaves the `clips` map, rather than staying as an empty
  entry (`{}`). A cut on a NEW clip writes that clip's chapter from the page, because `reel.yaml` refuses
  properties for a clip no chapter lists (a real `PUT` confirmed it). That adopts the chapter's NEW clips, and
  the save bar already counts those.
- **The save bar** counts cuts added and cuts removed. A cut typed but not yet added holds Save back and is
  named in the save bar with its clip, as a date typed only in part is today, so a typed cut is never lost
  silently. What was typed survives hiding the panel and moving the clip to another chapter: the editor, not
  the row, holds it, because Move clips mounts the row anew in its new chapter.
- **The event page** (read view) shows, beside each clip that has cuts, a compact indicator ("2 cuts ·
  −4.5 s") that opens the list. The page reads the cuts with the same `GET …/reel` Edit mode uses, after the
  event read, and still writes nothing. If that read fails, the page says so in a note and shows the clips
  without cuts.
- **Docs.** `web/README.md` (Edit mode, the event page, the file tree). `docs/high-level-design.md` gets a new
  **D-14**, which pulls typed cut editing forward from v3 and states how the page validates without a clip
  length, plus §4.10's v1 bullet and slice row D.

## Non-goals

- **Scrubbing, preview frames, proxies, drag-trim, keep-ranges.** These stay v3 (§4.10). Approving analysis
  suggestions stays v2.
- **A clip-length check.** The detail is probe-free and no read gives a duration (`api/schemas.py` 30-50).
  Adding one is an API decision, recorded as an open question, not made here.
- **Editing a cut in place.** Remove it and add the new one. Editing a reason is out too: a GUI cut's reason
  is `manual`.
- **Keeping a clip's other cuts' formatting.** When a clip's cuts change, the engine rewrites its whole
  `trims` list. Its other cuts keep their values, but lose flow style (`{in: 0, out: 1.5}`) and end-of-line
  comments (`event/editorial.py` 273-289; confirmed by a real `PUT`). An engine fix is a follow-up.
- **Merging overlapping cuts.** The render merges overlapping cuts that `reel.yaml` already holds, and the page
  shows them as read. The page refuses to add an overlapping cut rather than rewrite one the operator did not
  touch.
- **Any API, engine, schema or dependency change, and any change to the render.**

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `web-app`. All of the following are in the one capability.
  - Two ADDED requirements:
    - `Requirement: Edit mode lists, adds and removes a clip's cuts`
    - `Requirement: The event page shows each clip's cuts`
  - One MODIFIED requirement:
    - `Requirement: Saving an edit writes only what the operator changed`, as `chapter-management-screen`
      leaves it. It adds the cut counts in the save bar, undone cut edits, and the write rules for a clip's
      cuts, including a NEW clip's chapter and a document that names no chapters.

## Impact

- **Packages:** `web/` only, plus two documentation files.
  - new `web/src/cuts/`:
    - `times.ts`: parsing and writing times, the cut checks, the summary, and the reason labels. Pure.
    - `CutsPanel.tsx`: the Edit-mode toggle and panel.
    - `ReadCuts.tsx`: the event page's indicator and list, and the hook that reads the cuts.
    - `cuts.css`
  - `web/src/edit/`:
    - `draft.ts`: `Draft.cuts`, the cut operations, the `clips` write rule, and NEW-clip adoption in
      `writtenFromView`
    - `EventEditor.tsx`: reducer actions, the panel store, the typed-cut hold, the summary, the hint and the
      announcements
    - `ClipOrderList.tsx`: the toggle and panel in `ClipRow`, and a missing clip's cut badge (not on its removed row)
    - `SaveBar.tsx`: one prop renamed (`dateIncomplete` → `unfinished`)
    - `edit.css`: one selector and the narrow placement of the toggle
  - `web/src/events/EventDetail.tsx`: `ReadyView` reads the cuts and `ChapterPanel` shows them.
  - `web/src/ui/Icon.tsx`: two icons, `scissors` and `chevron-down`.
  - `web/README.md` and `docs/high-level-design.md` (D-14, §4.10).
- **CLI vs API (Principle V):** neither is touched. The GUI writes through the existing `PUT …/reel`, which
  calls the engine operation `apply_editorial_write`, open to any client. The CLI has never edited cuts, and
  hand-editing `reel.yaml` stays the CLI path.
- **Rendered output:** unchanged for identical inputs. There is no `RENDER_GRAPH_VERSION` bump, and the
  fingerprint's inputs are unchanged. A saved cut changes the editorial component, as any edit does, so the
  event reads "edited since last render".
- **Schemas:** no change to `reel.yaml` or `config.yaml`, and no API change. No Alembic migration and no
  rescan. `web/openapi.json` and `schema.d.ts` are untouched.
- **Dependencies:**
  - **Gate:** `chapter-management-screen` must be archived on main. This change extends its `Draft`,
    `Baseline`, `writtenFromView` and `buildWriteBody(baseline, draft)`, and re-bases the MODIFIED requirement
    on its text.
  - **New runtime dependencies:** none. D-8's budget is unchanged: native form controls, the existing `Icon`,
    no time-parsing library.
- **Size (Principle VIII):** one package plus docs, one capability delta (2 added, 1 modified), and 9 tasks.
