# Proposal

## Why

The workspace (`editor-workspace-layout`, HLD D-28, §6 item 10 GUI) was meant to show the picture, the track and the
clip lists together, at a target window of 1280×720 (`docs/editor-workspace.md`, explore decisions 2026-11-15).
As built, the 240 px clip bin draws about 440 px of tools before its first clip row:

- the new-clip hint, about 95 px
- the Clips help toggle
- Rotate marked left and right, one row each
- Move marked to… with its label above the picker
- per chapter, a header bar and a separate tools row

At 1280×720 the bin pane is about 390 px tall, so it shows **no clip row** without scrolling. At 1440×900 it shows
about one. Each compact row also takes three lines, about 117 px.

Two causes:

1. **The page rules apply to a pane.** The marks line's rules ("The marks line is one aligned unit") wrap it by
   whole groups in a narrow window. The bin is narrow at every window size, so it always draws the 320 px-page form.
2. **Rows that stand still.** Rules made for a long page keep a row still: the marks line always present at a fixed
   height, and a chapter's tools in a row of their own. In a 390 px pane each such row costs a clip row.

Learning carried from auto-reel (HLD §2): the legacy tool had no way to see the order and the picture together. The
workspace exists to fix that, and a bin that shows no clips undoes it.

## What Changes

All of this is in the workspace only. The stacked Edit page (below 960 px, and the metadata fix editor) keeps
today's layout.

- **A wider bin.** The bin is `clamp(240px, 22vw, 320px)` wide. The picture is limited by height at both 1280×720
  and 1440×900, so the viewer loses no picture size.
- **The marks line keeps its two rows and never wraps further in the bin.** It stays at the top of the bin pane
  while the clips scroll, with a fixed height of at most 88 px.
  - Row 1: Help, the count and Clear marks.
  - Row 2: Rotate marked left and right, then the chapter picker and Move.
  - Rotate becomes icon-only, and the "Move marked to…" label names the group without being shown.
  - The toolbar is at most 88 px including its 1 px border.
  - Names, descriptions and `aria-disabled` reasons stay, and the icon buttons offer their names as tooltips.
  - Marking the first clip still moves no row.
  - The explore sketch of a single row does not fit a 282 px bin: the picker would get under 60 px (design D2).
- **No separate new-clip line.**
  - The sentence that a new clip joins `reel.yaml` once its chapter is saved moves into the Clips help.
  - The count saving adds stays in the top bar's unsaved summary, as the save-summary requirement already shows it.
  - A new clip's row already says New.
- **Each chapter header is one row**: the chapter's name, its clip count, then Edit title card, Move up, Move down and
  Delete as icon buttons with names and tooltips. The separate tools row goes.
- **Two-line clip rows in the bin.** A compact row is three lines today, about 117 px, because the two-line form
  starts only at a 22rem (352 px) container and the bin never reaches it.
  - The two-line form (handle, position, name and the row's tools; then thumbnail, length, status and Cuts) applies
    from the bin's own width.
  - Below about 17rem (272 px) Rotate goes to the second line, after Cuts.
  - A clip's status in a row is its icon alone with a fine pointer (decision 1a; words kept as hidden text and a
    tooltip, icons distinct per status).
  - Rows get tighter padding, for about 68 px each with a fine pointer.
  - Touch keeps today's taller rows.
- **Ignored clips follow the chapters in the wide bin** (decision 2b). From 960 px they are listed in one block
  after the last chapter, under "Ignored clips", each chapter's with a caption naming the chapter, and the bin's grid
  gap is 8 px instead of 12. Below 960 px they stay in their chapters.
- **Pass bar (fine pointer, nothing marked), counting the clip rows a chapter plays:**
  - at 1280×720 the bin shows at least 3 whole played rows without scrolling
  - at 1440×900 it shows all 4
  - Four rows at 1280×720 do not fit while the Timeline pane keeps its 280 px minimum: 391 px of pane less one bar
    and two chapter headers leaves room for about 3.5 rows.

## Non-goals

- The Timeline pane's own chrome (its heading row and the Re-analyze row). That is a separate change if wanted.
- Moving chapter tools into the inspector. That is `editor-selection`'s Event tab, if at all.
- Clip selection, a context menu or a menu button. The tools stay direct buttons.
- Any change to the stacked page's marks line, chapter header bar or hint below 960 px.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `web-app`:
  - MODIFIED "The marks line is one aligned unit": in the workspace it is one bar of fixed height with icon buttons.
  - MODIFIED "Edit mode moves the marked clips to a chapter": its group's place and wrap rules in the workspace.
  - MODIFIED "Edit mode adds, renames, reorders and deletes chapters": the header bar holds the tools as icon buttons
    in the workspace.
  - MODIFIED "The clip bin holds the chapters' clip lists": the bin's width, two-line rows, the ignored block and the
    rows-visible bar.
  - MODIFIED "State is never shown by color alone": the bin's rows show status as an icon alone with a fine pointer.
  - MODIFIED "The event page reorders clips within a chapter": the wide bin lists ignored clips after the chapters.

## Impact

- **Packages:** web only. `web/src/edit/EventEditor.tsx` (bin part), `web/src/edit/ChapterDrag.tsx` (chapter header),
  `web/src/edit/clipsHelp.ts`, `web/src/edit/workspace/workspace.css`, `web/src/edit/edit.css`. No CLI, API or engine
  change (Principle V untouched).
- **Rendered output:** no change for identical inputs. No `RENDER_GRAPH_VERSION` bump and no change to the staleness
  fingerprint inputs.
- **Schemas:** no `reel.yaml` or `config.yaml` change, no Alembic migration, no rescan.
- **Dependencies:** none new.
- **Order:** lands before `editor-selection`, which also touches bin rows and the inspector.
- **Size:** about one short session (Principle VIII): CSS, a few component variants and six requirement edits.
