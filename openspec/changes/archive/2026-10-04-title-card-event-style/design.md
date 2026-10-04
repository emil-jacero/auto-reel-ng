## Context

On main already: `look.title_card` as the event layer (`title-card`, D-24); the detail's `title_card`
(`TitleStyleOut`: the resolved event style: duration, background, font_family, title_font_size,
subtitle_font_size, text_color, position) and `title_card_error`; `GET /api/v1/fonts` (D-22);
`POST …/title-card/preview` with an optional `style` (a draft of `look.title_card`) and `event_title`;
`look` an opaque map in the editorial `PUT`, with a `look.title_card` the engine refuses answered 400 naming
`look.title_card.<field>` (`api-service`). The web editor sends `look: read.look` unchanged
(`draft.ts` `buildWriteBody`) and no look UI exists in `web/src` today (checked with `rg -i "look" web/src`:
only the write-back and unrelated status "looks").

Merged by `title-card-inspector` (read against main, 2026-10-04): `edit/card/model.ts` (`CardDraft`, nine
overrides, `null` = follow the event style, `cardChanged`, `previewRequest`, `refusalOf`), `edit/card/Fields.tsx`
(`FieldShell`, `TextField`, `NumberField`, `Choice`, each with "Use event style"), `edit/card/useFonts.ts`,
`edit/card/usePreview.ts` + `preview.ts` (`PreviewController`: debounce 250 ms, cancelling, previous image kept),
`edit/card/Preview.tsx` (`CardPreview`), `edit/card/specs.ts` (`EventStyle`, the *saved* resolved style, and
`draftSpec`), and `Draft.cards` with `setCardField` / `resetCard` in `edit/draft.ts`. This change follows those
names; `EventStyle` becomes partial so a field the page does not know is `undefined`, never invented.

## Goals / Non-Goals

**Goals:** one place for the event layer; every card says what it overrides; the inspector and preview see the
draft event style before it is saved; a save writes only `look.title_card`.

**Non-Goals:** editing the project `config.yaml` look; a style for anything but title cards; fades, outline and
shadow fields (kept as read); per-card duration by drag (`title-card-duration-drag`); any API change; a
look "picker" of named presets.

## Decisions

**1. A style draft beside the card drafts.** `cardStyle.ts` (pure, no runtime imports, like `draft.ts`) holds
`StyleDraft = Partial<Record<StyleField, string | number>>` where `StyleField` is the seven fields of the
engine's card overrides, and absent means unset. `baseline` = `read.look.title_card` restricted to those
fields. Two helpers: `styleChanged(read, draft)` (field-wise, normalised numbers, so 80 and "80" are equal and
an edit undone is no change) and `applyStyle(readLook, draft)` returning the new `look`.
Rationale: the same shape the inspector uses for a card, so one field editor renders both layers (the inspector
passes a card draft, this panel passes the style draft), and the engine stays the only authority on validity.

**2. The write.** `look` = `{...read.look, title_card: {...readTitleCard, ...setFields}}` with a field the
operator cleared deleted from it and `title_card` itself deleted when it ends empty and the read one was
non-empty; a read `look` without `title_card` and a draft without fields stays byte-identical, so the existing
"unmodified save is a no-op" contract holds. Keys the panel does not model (`fade_in`, `outline` …) are kept
as read. Alternative rejected: sending the whole resolved `TitleStyleOut`; that would write every default into
`reel.yaml` and freeze the project defaults into the event.

**3. What an unset field shows.** The detail's `title_card` is the *saved* resolved style, so it is the right
placeholder for a field the event never set, and the right answer to "what is the project default" only while
the event layer is empty for that field. When the operator clears a field the saved event layer set, the lower
layer is not known to the client, and it is not guessed: the field says "Project default" with no number, and
the preview image (which the engine draws from the draft) is the truth. Fabricating a value is the one thing
the constitution forbids.

**4. The live preview takes the style.** The inspector's preview hook gains one input, the draft style, sent
as the body's `style` (the whole draft `look.title_card` map, so an unset field is absent, not null). The
panel shows its own preview of the opening card (`chapter: ""`, black background for a Black default, the
text on a neutral checker for Video, since a video card is transparent), through the same hook, so debounce,
cancelling and the previous-image-while-loading rules are the inspector's.

**5. "Overrides" is read from the draft, not the resolved card.** A resolved card cannot tell an inherited
value from an equal override. The chapter list row and the inspector list the keys present in the card draft
("Overrides font, color"), or "Uses the event style" when none. A card whose draft sets a field equal to the
event style still counts as overriding it; "Use event style" clears it.

**6. Errors.** A 400 whose problem names `look.title_card.<field>` is shown at that field (the inspector's
mapping for `card.<field>`, with the other prefix); a `title_card_error` opens the panel with the words and
the stored raw values editable, so a hand-written bad value can be fixed in the page. Client checks stay
minimal (a number field takes a number; the colour field takes text) since the engine decides.

**7. Placement.** A disclosure row "Card style for this event" at the top of the chapter list in Edit mode,
closed by default, a native `<details>`-style control so it needs no new dependency; the save bar says
"Card style changed" next to the count of changed cards.

## Risks / Trade-offs

- A cleared field has no number to show (Decision 3). Accepted: honest over pretty; the preview shows it.
- Two overlapping requirements in `web-app` ("Saving an edit writes only what the operator changed") may have
  been modified by `title-card-inspector` for card writes. This delta only ADDs a requirement that states the
  `look` exception, so it cannot clash; archiving may fold the two sentences together.
- Defaults the engine changes later alter the placeholder, not any stored value.
