## Context

On `main` (read 2026-10-04): the editorial body already has `chapters[].card` (`CardBody`: `title`, `subtitle`,
`duration`, `background`, `font_family`, `title_font_size`, `subtitle_font_size`, `text_color`, `position`, all
nullable = inherit). A chapter sent with `card` absent/`null` **keeps** the persisted card, `{}` removes it, and a
card follows its chapter's rename (`api-service`, "The editorial document carries each chapter's title card"). The
event detail has the engine-resolved `card` per chapter and `title_card` for the event, `null` with `card_error` /
`title_card_error` when unresolvable. `GET /fonts` lists `family`, `display_name`, `weights`, `default`; it serves no
font file. The preview route returns a PNG at the event's target resolution; a `video` card is text on full
transparency; `card.title` and `event_title` are bounded to 200, `card.subtitle` to 400, at most two draws at once,
503 with `Retry-After` when busy. No preview option takes a video frame.

`web/src/edit/draft.ts` holds the draft (`chapters`, `orders`, `removed`, `metadata`, `cuts`), keyed by `ChapterKey`
so a rename moves nothing; `buildWriteBody` currently writes chapters as `{name, clips}` (so cards are kept, never
sent) and `isDirty`, the save bar and `unsaved.ts` read the same draft. `title-card-blocks` (the gate, archived on `main`) added the cards as blocks and rows with one selection shared by
the Timeline and the list. The names it built, read from `main` on 2026-10-04: the selection is `useCardSelection`
(`timeline/useCardSelection.ts`, a `CardsBinding`: `selected` is the card's chapter by its **saved** name, `""` the
opening; `select`, `clear`, `retain`), kept by the event page above the read view and Edit mode. A row is `CardRow`
(`edit/CardRow.tsx`, data in `cardRows.ts`) and is selectable only for a chapter read from the document or the
disk; a chapter added in this session shows "Its title card is drawn after Save" and is not selectable, so it has
no card to edit. The inspector slot is `CardInspector` (`timeline/CardInspector.tsx`), mounted by `TimelineSection`
outside the collapsible body, so it is there whether the Timeline is open or not; today it holds only the words
"Card editing comes next". The clip a card sits over is `cardPlacements(...).clip` (an index into the shown
clips), which needs proxy facts; without them the page uses the chapter's first shown clip. The "Main title card"
line (`edit/TitleCard.tsx`) edits `metadata.title` and stays: it is the event's title control, not the opening card's
`card.title`. Edit mode's `EditBinding` (`timeline/editing.ts`) is what the editor hands the Timeline section.

## Goals / Non-Goals

**Goals:** edit one card's text, background, font and style in the draft; see it drawn by the real renderer while
editing; one undo/save path.

**Non-Goals:** dragging a card's length and a `duration` field (a card keeps the duration it has; the draft passes it
through untouched), the event-wide style `look.title_card` (read-only here; per-card overrides only), adding or
deleting cards (every chapter has one), per-option font faces in the picker (see Risks), any API or engine change.

## Decisions

**D1. Cards are a draft slice keyed by chapter key.** `Draft.cards: ReadonlyMap<ChapterKey, CardDraft>` holds only
cards the operator touched; `CardDraft` is the nine override fields with `null` = inherit. The baseline of a chapter is
`read.chapters[].card` (matched by its read name). A card counts as changed when its normalised overrides differ from
the baseline's, so editing a field back to its read value is no change. *Alternative:* edit the resolved card and diff
against defaults, rejected because it would write every inherited value as an override and lose "Use event style".

**D2. The write sends `card` only for a changed card.** `buildWriteBody` adds `card` to a chapter whose card changed;
a card whose overrides are all `null` is sent as `{}` (removes it); an untouched chapter sends no `card` and so keeps
what `reel.yaml` holds. A chapter added in this session has no card (its row is not selectable), so it sends none. A changed card of a chapter the document does not list (disk-only) is written from the view, as an order change is. Because the key is the chapter
key, a rename needs no extra work and the service carries the card. A card edit makes `writtenFromView` irrelevant:
a card-only change writes the chapters list the same way a rename-only change does. *Alternative:* always send every
card, rejected because it turns every save into a write of the whole card set and hides unchanged ones from the
byte-identical no-op rule.

**D3. What an empty field shows.** The title placeholder is computed from the draft, not read from the detail: the
chapter's current draft name, or the draft `metadata.title` (else the title read from the folder name) for the opening
card; so renaming the chapter or editing the event title updates it. Every other inherited value (font, sizes, colour,
position, background) is shown from the detail's resolved `card`, as the muted "event style" value; for a chapter added
in this session, from `title_card`. When the engine could not resolve (`card: null`, `card_error`), the inspector says
so in the error's words, the inherited values read "unknown", and the fields still work; it fabricates no default.

**D4. Title and subtitle are plain text.** Any text is kept; the title never changes the chapter's name or the
movie's chapter list. The subtitle is a multi-line text area (the engine draws the string as given and wraps each line
within the card column); no line limit of the page's own. The preview's 200 / 400 character bounds are the preview's:
beyond them the page says "Too long to preview (limit 200)" at the field, makes no request, and keeps the text, which
still saves.

**D5. The preview is one hook over the draft.** `useCardPreview(draftCard, context)` builds the request body, waits
250 ms of quiet, aborts the previous request (`AbortController`), shows the previous image until the new one is
loaded (object URL swapped, old one revoked), and reduces failures to words by the service's cause: 400 names the
field (shown at the field too), 422 the bound, 502 the cause, 503 "busy, trying again" using `Retry-After` for one
automatic retry, no answer "the service did not answer". The request sends `chapter` = the draft chapter name, `card`
= the non-null overrides, and for a non-opening chapter with no title override `card.title` = the draft chapter name,
and for the opening card `event_title` = the draft event title, so the preview matches the draft even for a rename or
an added chapter the service has not seen. The image never gets a stale answer: a response for a superseded request is
dropped.

**D6. Video background composes in the page.** The service draws a Video card as text on transparency. The page
layers that PNG over an `<img>` of the thumbnail of the clip the card sits over (the same clip `title-card-blocks`
draws it over, honouring title clip, exclusion and whole-clip cuts), at the same aspect ratio, sized as the preview.
The thumbnail is the clip's thumbnail frame (`clip-thumbnails`, 25 % of its duration by default), **not** its first
frame, and the preview says "Backdrop: a frame from <clip>, not the exact start". No frame-extracting call is made,
because the page may not start ffmpeg and the preview has no video-frame option. With no playing clip or no thumbnail
the text is drawn on a plain checkerboard with "No clip frame to show it over". *Alternative:* the proxy filmstrip
first tile, rejected because proxies are optional.

**D7. The font picker lists names and previews through the card.** A listbox of `display_name` (the default marked),
keyboard operable, selecting sets `font_family`; the effect is the live preview. Own-face samples need font files the
service does not serve and nine extra draws per open; this change makes neither.

**D8. Selection opens the inspector.** The inspector reads the selected card from the shared selection
(`CardsBinding`) and renders in `CardInspector`'s slot, in Edit mode only (the read view keeps the card's words,
without the "comes next" note, and no fields): beside the list on wide windows, as a sheet below the Timeline on narrow
ones; Escape or selecting another block closes or switches it without losing the draft. An inspector is not a modal.

**D9. Pure model, node:test.** Normalising, diffing, placeholder choice, request-body building, the save-bar count and
the validation-to-field mapping live in pure modules tested with the existing `node:test` runner (`npm test`);
components stay thin.

**D10. Validation at the field.** A 400 problem body's `detail` names `card.<field>` of the chapter; the page maps the
field name to the control and shows the message there (and in the save bar's problem list); editing that field retires
the message. A message for no known field shows at the card's top.

## Risks / Trade-offs

- Thumbnail frame is not the card's true backdrop → worded as a frame from the clip; a later frame-at-time route would
  remove the caveat.
- Picker cannot show each family in its own face → live preview, and a follow-up (serve `fonts/` or sample PNGs) is
  recorded in the HLD note.
- Preview load: two draws at once per process → 250 ms debounce, abort, one request in flight per inspector.
- Overrides stored for a chapter that is then deleted → the card goes with it; Undo restores it with the chapter.
- The gate's names differ from the roles used here → task 1.1 pins them before any code.
- The "Main title card" line and the opening card's `card.title` could be confused → the line stays as the event
  title's control (its requirement is unchanged); the inspector's title for the opening card says "Follows the event
  title" while empty, so the relation is on screen.
