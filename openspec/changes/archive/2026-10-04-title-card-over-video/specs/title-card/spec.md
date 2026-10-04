## ADDED Requirements

### Requirement: Title decorator places each chapter's card

The engine SHALL register a `title` decorator (an inserter) selectable via `look.decorators`. When applied, it
SHALL insert one synthetic title segment for each chapter that resolved a title clip (the clip resolved as
`is_title`), carrying the producer reference, the chapter's own card duration, the chapter's effective card
config (the event-wide style with the chapter's `card` overrides applied) and text, and the chapter membership of
the segment it precedes. The card SHALL be placed immediately before the title clip's
first surviving segment (for a clip with partial cuts, its first kept span). When cuts remove the title clip
entirely, so that it contributes no segment, the card SHALL instead be placed immediately before the first
surviving source segment of the same chapter, so the chapter still opens with its card. When every clip of the
chapter is cut away, so that the chapter has no source segment, no card SHALL be inserted for it. A chapter
that resolved no title clip SHALL get no card. A card whose effective background is `video` SHALL NOT be inserted as a segment; it SHALL be attached to the
anchor segment instead, and never drawn as a black card (see "A video-background card is attached over the
chapter's first segment"). When `look.decorators` does not include `title` (or is absent),
no title segment SHALL be produced and behavior SHALL be unchanged.

#### Scenario: Title segment inserted before a chapter's title clip
- **WHEN** the `title` decorator is applied to a plan whose default chapter has a title clip
- **THEN** the segment list contains a synthetic title segment immediately before that chapter's title clip, carrying that chapter's name

#### Scenario: Per-chapter title segments
- **WHEN** the `title` decorator is applied to a plan with two chapters that each have a title clip
- **THEN** a synthetic title segment is inserted before each chapter's title clip

#### Scenario: No title decorator means no card
- **WHEN** `look.decorators` does not include `title`
- **THEN** the segment list contains no synthetic title segment

#### Scenario: Partially cut title clip keeps its anchor
- **WHEN** the chapter's title clip has a cut span over its first seconds and a kept span after it
- **THEN** the synthetic title segment is placed immediately before that clip's first kept span, exactly as for an uncut clip

#### Scenario: Fully cut title clip moves the card to the next clip
- **WHEN** a chapter is `[a.mp4 (title, 10 s), b.mp4]` and a cut span covers all of `a.mp4`
- **THEN** the chapter's synthetic title segment is placed immediately before `b.mp4`'s first segment, carrying that chapter's name and heading, and the chapter has exactly one card

#### Scenario: Fully cut title clip with later surviving clips in several chapters
- **WHEN** two chapters each have a title clip, the first chapter's title clip is wholly cut, and the second chapter is untouched
- **THEN** the first chapter's card moves to its next surviving segment, the second chapter's card stays before its title clip, and each card still carries its own chapter's name

#### Scenario: Chapter cut away entirely gets no card
- **WHEN** every clip of a chapter, including its title clip, is wholly cut
- **THEN** no synthetic title segment is produced for that chapter and the chapter is absent from the segment list, as it is without the decorator

#### Scenario: Chapter without a title clip gets no card
- **WHEN** no clip of a chapter resolved as the title clip
- **THEN** no synthetic title segment is produced for that chapter, whether or not its clips are cut

#### Scenario: Each chapter's card has its own length
- **WHEN** the default chapter's card sets `duration: 3`, a second chapter's card sets `duration: 10`, and the third chapter has no card
- **THEN** the three synthetic title segments last 3 s, 10 s and the event-wide duration

#### Scenario: A chapter's card overrides apply to that chapter only
- **WHEN** one chapter's card sets `font_family` and `text_color` and another chapter sets nothing
- **THEN** only the first chapter's title segment carries those values in its config

#### Scenario: A video background is attached, not failed
- **WHEN** a chapter's card sets `background: video`, or `look.title_card.background` is `video`
- **THEN** the render succeeds, no title segment is drawn as black for that chapter, and the card is attached over
  the chapter's first segment


### Requirement: A video-background card is attached over the chapter's first segment

When a chapter's resolved card has the background `video`, the `title` decorator SHALL NOT insert a synthetic
title segment for it. It SHALL instead attach the card, as an overlay, to the segment the card would otherwise
precede (the chapter's title clip's first surviving segment, else the chapter's first surviving source segment).
The overlay SHALL show the card from the start of that segment for the card's duration, fading in and out
according to the card's fade settings. Attaching the card SHALL NOT change the length of any segment, chapter or
the movie. A chapter that gets no inserted card (no title clip, or every clip cut away) SHALL get no attached
card either. A chapter whose resolved background is `black` SHALL get its card exactly as before, as an inserted
synthetic segment, whatever the other chapters' backgrounds are. This requirement applies to the default chapter,
whose card opens the movie, as to any other. It takes precedence over the insertion wording of "Title decorator
inserts a synthetic title segment" for chapters whose background is `video`.

#### Scenario: Video card is attached, nothing is inserted
- **WHEN** the `title` decorator is applied to a plan whose default chapter has a title clip and a resolved
  background of `video`
- **THEN** the segment list has no synthetic title segment, and the title clip's first segment carries one
  overlay for the title producer with the card's duration and fades

#### Scenario: Movie length is unchanged
- **WHEN** an event with a `video` card on a chapter is rendered and again with the card removed
- **THEN** the two movies have the same duration (within one frame), and the same chapter start and end times

#### Scenario: Text is on the footage during the window and gone after it
- **WHEN** a 7 s `video` card with 2 s fades is rendered over a plain mid-grey clip with a white card text
- **THEN** a frame sampled in the middle of the window shows the text over the footage, and a frame sampled after
  the window is the footage alone

#### Scenario: Black card is unchanged
- **WHEN** a chapter's resolved background is `black` in a plan where another chapter's is `video`
- **THEN** the black chapter has an inserted synthetic title segment, and its normalize command is the same as it
  was before video cards existed

#### Scenario: Mixed chapters
- **WHEN** a plan has two chapters, the first with a `video` card and the second with a `black` card
- **THEN** the first chapter's first segment carries the overlay and no segment is inserted for it, and the
  second chapter has an inserted title segment before its title clip

#### Scenario: Anchor follows cuts
- **WHEN** a `video` chapter's title clip has a cut over its first seconds, or is wholly cut
- **THEN** the overlay is on that clip's first kept span, or on the chapter's first surviving segment

#### Scenario: Chapter without footage gets no card
- **WHEN** every clip of a `video` chapter is cut away, or the chapter resolved no title clip
- **THEN** no overlay is attached for that chapter and the segment list is as it is without the decorator

#### Scenario: Segment shorter than the card
- **WHEN** a `video` card of 7 s is attached to a segment of 3 s
- **THEN** the card is shown for 3 s, the render result carries a warning naming the card's duration and the
  segment's, and the render succeeds

#### Scenario: Title-card span is not recorded for an attached card
- **WHEN** a movie with a `video` card on a chapter is rendered
- **THEN** that chapter's recorded title-card span is `null`, as for a chapter with no title-card segment

### Requirement: A video-background card is rendered on a transparent canvas

The renderer SHALL render a card whose background is `video` to an RGBA image at the target resolution on which
every pixel outside the text, outline and shadow is fully transparent. The renderer SHALL otherwise lay the card
out exactly as a `black` card: the same text, font resolution (including the fail-loud error), sizes, outline,
shadow and position. The renderer SHALL NOT paint the configured background colour or opacity for a `video`
card. The same renderer entry point SHALL serve both backgrounds, so a preview and a render of a card are drawn
by the same code.

#### Scenario: Transparent outside the text
- **WHEN** a `video` card with the title "Midsommar" is rendered at 1920x1080
- **THEN** the corner pixels have alpha 0, and the pixels on the title's glyphs have alpha 255 and the text colour

#### Scenario: Same layout as a black card
- **WHEN** the same title, style and target are rendered once with `black` and once with `video`
- **THEN** the pixels where the video card is opaque are the pixels where the black card's text is drawn

#### Scenario: Black card image is unchanged
- **WHEN** a `black` card is rendered with the same style as before video cards existed
- **THEN** its image is pixel-identical to what was rendered before

#### Scenario: Video card with an unresolvable font still fails loud
- **WHEN** a `video` card names a font family that does not resolve
- **THEN** the renderer raises the typed font error naming the family, as for a `black` card

## REMOVED Requirements

### Requirement: Title decorator inserts a synthetic title segment
**Reason**: replaced by "Title decorator places each chapter's card", which keeps every insertion rule for `black`
cards and no longer fails a `video` card loud, now that the engine renders it.
**Migration**: none; the behaviour of `black` cards is unchanged.
