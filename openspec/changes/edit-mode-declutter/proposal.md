## Why

Edit mode on `main` (946a9a2) has grown a second layer of controls on top of every chapter. The operator's
feedback of 2026-10-04, from two screenshots, in their words: "Why is the interface so cluttered? I want the editing
of the name to be in the popup. It should be the same workflow for main and chapters. Remove editing from red. And
remove the title card edit button to the top bar cleaning up the section below. The button should just say Edit
Titlecard", "Remove the title card toggle button and section", "The timeline editor should be open when you click
on Edit for the event. Remove the old button", and "Remove the card style for this event section completely, I want
all title card related settings in the popup only." The same day, from a screenshot of the marks toolbar: "This is
not lining up."

Four pieces of Edit mode each grew in its own change and none was removed when the next arrived:

- chapter names are renamed by an inline pencil (`chapter-inline-rename`, #113, D-13), and the event's own chapter
  has a second "Main title card" line with its own pencil that edits the event title;
- every chapter carries a card row ("Title card 2025-01-15 7.0 s Black DejaVu Sans Uses the event style"), the card
  editor dialog (#133, D-24) opening from it;
- the event-wide look has two page sections of its own, "Card style for this event" (`title-card-event-style`) and
  the Title cards On/Off switch (`title-card-toggle`, #123, D-25);
- the Timeline has an Open/Close button in Edit mode, though Edit mode's whole point is trimming on it (`timeline-trim`,
  D-20).

The card editor dialog already holds the card's fields and the live preview (D-24); it only lacks the name, the
length and the event-wide fields. This change makes it the one place for every name and every title-card setting and
takes the rest off the page. HLD §6 phase 8 (GUI v2), D-20 (timeline), D-24 (card model), D-25 (decorators).
Research behind the timeline's opening rule: `research/v2/synthesis.md` §3 and finding X6 (the Timeline needs the
clips' facts, so it opens only for an event whose proxies are prepared, otherwise it shows its Prepare state); that
state is what an Edit mode without proxies shows instead of the track.

## What Changes

- **Chapter header bar** (Main and every chapter, identically): the name as plain text, an **Edit Titlecard** button
  (icon and text, 44 px target, named "Edit title card for <name>") before the clip count and the chapter tools. The
  card row, the "Main title card" line, the "from the folder name" line and every rename pencil go.
- **The card editor dialog** becomes the one place for names and cards, as two tabs with one live preview above or
  beside them:
  - **This title card**: Name first (a chapter's name, validated and enforced as the inline rename was; for Main the
    event title, the Details form's Title field), then the card's own fields as today, plus **Length** (seconds, the
    drag's bounds). A card that already has its own `title` shows it as "Card title (overrides the name)" with "Use
    the name"; no new override can be added.
  - **All title cards in this event**: the fields of "Card style for this event", each with "Use project default",
    and the **Title cards On / Off** switch.
- **Removed from the page**: the Title cards section, the Card style for this event section, the card rows, the "Main
  title card" line, the rename pencils; their components, strings and tests are deleted.
- **Timeline in Edit mode**: opens with Edit mode and has no Open/Close button. The read view keeps "Open timeline".
- **Marks toolbar** ("This is not lining up"): Mark count, Clear marks, Rotate marked left/right and Move marked
  to… become one aligned unit: one control height token, one baseline, consistent gaps, the reason text muted and
  centred with the controls or a single hint line below, wrapping in aligned rows at 390 and 320 px.
- Specs: `web-app` (MODIFIED: chapters, later-clip notes, the card dialog, event card style, Title cards switch, "a
  card says which fields it overrides", inherited choice, opening subtitle; ADDED: the one popup, the marks unit)
  and `event-timeline` (MODIFIED: the Timeline sections, the selection, the length drag; REMOVED: the chapter list's
  card row). HLD: §4.10, §6, D-13/D-20/D-24/D-25 notes.

## Capabilities

### New Capabilities

### Modified Capabilities
- `web-app`: names and title-card settings move into the card dialog; the page loses the rename pencils, the Main
  title card line, the card style and Title cards sections; the marks toolbar is aligned.
- `event-timeline`: Edit mode's Timeline is open on entry with no toggle; the chapter list's card row is removed and
  a card is selected from its block or the chapter bar's button.

## Impact

- Packages: **web** only (`web/src/edit/`, `web/src/edit/card/`, `web/src/timeline/TimelineSection.tsx`, CSS). Docs: HLD.
- CLI/API: none touched; the existing preview, fonts and `PUT` are used as they are.
- Rendered output: unchanged; `RENDER_GRAPH_VERSION` and the staleness fingerprint untouched. `reel.yaml` and
  `config.yaml` schema: unchanged (the same keys are written as before: `metadata.title`, chapter `name`,
  `chapters[].card`, `look.title_card`, `look.decorators`). Alembic and rescans: none.
- Dependencies: none new (D-8, D-20). Net code removed: InlineName, TitleCard, CardRow, CardStylePanel, TitleCardsSwitch.
- Complexity: the two-tab dialog replaces five page-level components and a closed/open toggle; the name rules are
  reused from `chapterNames.ts` and `inlineName.ts`, not duplicated.

## Non-goals

- No change to the read view (its Timeline button, chapter headings and card words stay).
- No new override of a card's own title; no editing of fades, shadow or other `look.title_card` keys.
- No new endpoint, no change to how `reel.yaml` is written, no change to Save, the save bar or the draft model.
- No change to reorder, Move marked to…'s behaviour (only its layout), the poster panel, Details form, clip rows,
  Timeline card playback or the length drag.
