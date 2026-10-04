## Why

The user asked (2026-10-03) that "each chapter should generate a title card", that the cards "be visible in the
editor, so that you can edit the title of it again, and maybe a subtitle", with the font and length editable too,
and chose the look: text on black, or text over the start of the chapter's first clip. The engine and the API for
that are on `main`: `title-card-model` (D-24, the per-chapter `card:` in `reel.yaml`), `title-card-over-video`
(a `video` card is an overlay on the chapter's first segment and adds no time), `title-card-fonts` (D-22) and
`title-card-write-api` (the event detail carries each chapter's resolved `card` and the event's `title_card`;
`GET /api/v1/fonts`; the PNG preview). Nothing in `web/` reads any of it: `grep -rn "\.card\b" web/src` finds
nothing, and the editor's only card is the "Main title card" line that edits the event title (D-13,
`web/src/edit/TitleCard.tsx`). An operator cannot see where a card falls in the movie, how long it is, or which
look it has, so editing one (the next changes) has nothing to attach to.

This is the first, read-and-select slice of the card editor in the v2 sequence. It builds on the Timeline now on
`main` (`timeline-view`, `timeline-trim`, `timeline-overlays`; D-20: in-repo `web/src/timeline/`, React and plain
CSS, no library, windowed rendering, a pure model tested by `node:test`). The timeline research
(`research/v2/timeline-library.md`, "Accessibility tree" and "Real work the prototype does not do") sets the bar
this change keeps: every element a real focusable control with a name, none distinguished by colour alone.

## What Changes

- **A card block per chapter on the Timeline**, in a lane of its own directly above the clips. A **black** card is
  its own span *before* the chapter, as long as the card is, and **adds time** to the track (the clips after it
  move right by its length). A **video** card is a block over the *start* of the chapter's first clip, as long as
  the card (shortened to the footage it sits on), and adds no time. It is drawn with its title text, with a look
  that differs from a clip, readable in light and dark, and never by colour alone. The opening card (the default
  chapter's) is first.
- **A card row at the head of each chapter in Edit mode's chapter list**: title, subtitle, duration, Black or
  Video, font name. Main's row is the opening card and keeps the existing event-title control (D-13).
- **One selection model** shared by the block and the row: selecting either selects the card; the other shows it
  selected. Keyboard operable; names such as "Title card for Dag 2, 4.0 s, over video". Selecting a card opens
  nothing but a placeholder inspector slot (the next change fills it).
- **Pure model additions** in `web/src/timeline/` (`timeline` capability): which chapters have a card and where
  it anchors (the render's rule, cuts included), the card spans and the clip-time to track-position map the black
  cards cause, the card's words, and the selection reducer. Tested by the existing `npm test`.
- **Data comes from the event detail's resolved cards** and `look.decorators` from the page's read of
  `reel.yaml`. Nothing is written, no endpoint added, no dependency added.

### Non-goals

- Editing a card: text, subtitle, font, length, background (next changes). No PUT, no preview request, no fonts
  request here.
- Playing a card on the Timeline. The Timeline plays footage; a black card's span is crossed by the playhead
  without time passing, and a video card's text is not drawn over the `<video>`. The PNG preview is the next
  change's.
- Dragging a card's edge to set its length; reordering cards; making `look.decorators: [title]` the default (the
  cards stay opt-in per project, `title-card-model`).
- Any change to the engine, API, `reel.yaml` or `config.yaml` schema, staleness fingerprint or
  `RENDER_GRAPH_VERSION`; no Alembic migration. Rendered output for identical inputs is unchanged.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `timeline`: the pure model gains card placement, the track map of black cards, card words and the card
  selection reducer.
- `event-timeline`: the card lane, the chapter list's card row, the shared selection and the inspector slot; the
  track requirement is modified so the movie's length counts black cards.

## Impact

- Package: `web/` only (`web/src/timeline/`, `web/src/edit/`, `web/src/cuts/ReadCuts.ts*` for `look`). The CLI and
  the API are untouched (Principle V: the engine and API already carry everything).
- Bundle: small and measured (D-8 budget); no new runtime dependency.
- HLD: `docs/high-level-design.md` §4.10 and §6 notes, and D-20 gain the card blocks; D-21 is not touched.
