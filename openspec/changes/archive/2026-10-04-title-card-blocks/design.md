## Context

What is on `main` (read before writing this):

- `GET /api/v1/events/{id}` returns `chapters[]` each with `card` (`ResolvedCardOut`: `duration` seconds,
  `background` `black|video`, `font_family`, sizes, `text_color`, `position`, `title`, `subtitle`) or `null` with
  `card_error`, and `title_card` / `title_card_error` for the event-wide style (`web/src/api/schema.d.ts`,
  `title-card-write-api`). The default chapter is named `""`; its title is the event title.
- The render draws a card only when `look.decorators` includes `title`, for a chapter that resolved a title clip
  and still has a surviving segment: the card sits before (black) or over (video) the title clip's first kept
  span, else the chapter's first surviving segment (`openspec/specs/title-card`, "Title decorator places each
  chapter's card"; "A video-background card is attached over the chapter's first segment"). A video card is
  clamped to its segment; a black card adds its duration.
- The Timeline lays shown clips end to end from proxy facts (`web/src/timeline/layout.ts`: `shownClips`,
  `trackClips`, `trackLayout`, `chapterBands`), windows with `visibleClips`, holds one cut selection
  (`Selected` in `Timeline.tsx`), and is mounted in the read view and in Edit mode. The page's read of
  `reel.yaml` (`cuts/ReadCuts.tsx`) and Edit mode's draft (`edit/draft.ts`, which sends `look` back as read)
  both carry `look`.
- Edit mode's chapter list is `edit/ClipOrderList.tsx`; the default chapter shows `TitleCard` (the event-title
  control, `edit/TitleCard.tsx`).

## Research & Decisions

### Where a card block is drawn
**Context**: the user wants a black card "as its own span before the chapter" and a video card "over the start of
the chapter's first clip".
**Explored**: drawing the video block on the clip tile itself. The tile already carries the filmstrip, hatched
cut spans, trim handles (Edit mode) and the analysis marks, and the existing rule "A press handed to a nearer
handle selects and focuses the handle that took it" (`event-timeline`) shows how contested that surface is.
**Decision**: a **card lane** directly above the clips (under the chapter band). A black card is a block of its
own width at its own track position; a video card is a block aligned to the footage it covers (same x range as the
first kept span's start) with a short edge marker down to the clip, so it reads as "on" that footage.
**Rationale**: no press or focus conflict with handles; both kinds are real buttons in one lane, in one tab
order, and the black card's time is visible as space.

### Black cards add time, so the track needs a map
**Context**: clips are laid end to end by `layout()` and everything else (playhead, follow, scrub, handles, marks)
is in clip time and positioned by `timeToPx`.
**Decision**: keep **clip time** as the one time the playhead, cuts, handles and marks use; add a pure
`cardGaps` offset map: `trackX(clipTimeMs)` adds the lengths of every black card whose anchor lies at or before
that clip time, and `clipTimeAt(trackMs)` inverts it (a track time inside a black card returns "in card k", not a
clip time). Drawing sites convert once (`trackX`); playback and scrub keep working in clip time. A press on the
lane inside a black card selects the card and does not move the playhead.
**Rationale**: the smallest change that is honest about time; the alternative (a layout of cards and clips as
one list) rewrites `follow`, `position`, `scrub`, `handles` and their tests, which is not a small batch (VIII).
**Limitation, stated in the UI**: the Timeline plays footage; the playhead crosses a black card's span without
waiting, and the movie length readout counts the card.

### The anchor
**Decision**: `cardPlacements(chapters, shown clips, cuts, cardsOn)` returns, per chapter, one of `anchored`
(clip index, `atMs` = the end of a cut that starts at 0 of the anchor clip, else 0, and the first kept span's
length), `no-footage` (the chapter has no shown clip, or every shown clip is wholly cut: the render inserts no
card), or `off` (`look.decorators` lacks `title`: the render draws none). The anchor clip is the chapter's title
clip. The event detail does not say which clip is the title clip, so the model uses **the first shown clip of
the chapter** — the baseline of `event-resolution` ("first included clip"); a clip with `title: true` elsewhere
in the chapter is the one case where this is wrong, and Open Questions records it. A wholly cut first clip moves
the anchor to the next shown clip with a kept span, as the render does.
A **black** card is drawn at the anchor clip's track position of 0 (before the clip and its leading cut), a
**video** card at `atMs`, with width `min(duration, first kept span)` — the render's clamp, shown as such.
**Rationale**: a black card before a clip whose first seconds are cut is, in the movie, still the card followed
by the kept footage, so the order is right and no time is invented; the video card must start where the footage
is actually shown.

### Cards that are not drawn are said, not guessed
**Decision**: when `title_card_error` or a chapter's `card_error` is set, the lane shows one note with the error
and no block for the affected chapters; when `look.decorators` lacks `title`, blocks are drawn in an **off**
look (dashed outline, the word "off", no time added) with a single note "Title cards are off for this event; the
render draws none". Never fabricate a duration or a background (Principle I).

### Selection
**Decision**: a pure reducer `CardSelection = { chapter: string } | null` held by the event page above the read
view and Edit mode (as the dismissals are). `chapter` is the chapter's key: the saved name in the read view, the
draft chapter key in Edit mode (equal to the saved name for a chapter present when Edit mode opened). Selecting a
card clears the Timeline's cut selection and selecting a cut clears the card, so one thing is selected. The
selection ends when its chapter is deleted or when the event is read again without it. It is not stored and not
in the URL.
**Rationale**: matches how the dismissals are kept; the Refresh that closes the Timeline section must not lose
what the list shows selected.

### The Edit-mode list row
**Decision**: a row `CardRow` at the head of each chapter in `ClipOrderList`: title, subtitle ("No subtitle"
when empty), duration, "Black" or "Video", the font name, from the saved resolved card matched by chapter key.
A chapter added in the draft has no saved card: its row says the card is drawn after Save, and is not selectable.
A renamed chapter shows its saved card (its title follows the chapter name only after Save, because the engine
resolves it on the saved document); the row says "Saved name: …" when the draft name differs. The Main row keeps
the existing event-title control inside it, so the title line stays the one control it is (D-13).

### Words
`cardWords(card, chapterHeading)` → "Title card for Dag 2, 4.0 s, over video" / ", on black"; the opening card is
"Title card for the opening" with the event title. Duration uses the page's time format, one decimal.

### Failure and idempotency
Read-only: nothing is written, nothing is requested. A re-read replaces the cards; the selection survives while
its chapter does. A card with a non-finite or non-positive duration is refused by the model with a `ModelError`
naming the field (Principle I), and the lane shows that card as unreadable rather than drawing a guess.

## Risks / Trade-offs

- A black card shifts everything right of it: marks, handles and the playhead must go through `trackX`. Mitigated
  by one conversion function and a test that every position helper in `position.ts`/`handles.ts` is fed clip time.
- First-clip-as-title-clip can disagree with an explicit `title: true` (see Open Questions).
- The Timeline will not show the text over the footage; operators see the block, not the frame, until the preview
  change.

## Open Questions

- Should the event detail report each chapter's title clip so the anchor is exact? Not blocking: the baseline is
  right for every event without a `title:` override, and this change does not add an API field (Principle V,
  one layer at a time). If wrong in practice, a follow-up adds `title_clip` to `ChapterOut`.
