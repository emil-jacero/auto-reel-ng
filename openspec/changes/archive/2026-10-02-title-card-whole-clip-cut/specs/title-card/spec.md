## MODIFIED Requirements

### Requirement: Title decorator inserts a synthetic title segment

The engine SHALL register a `title` decorator (an inserter) selectable via `look.decorators`. When applied, it
SHALL insert one synthetic title segment for each chapter that resolved a title clip (the clip resolved as
`is_title`), carrying the producer reference, the resolved card duration, the look-derived card config, and the
chapter membership of the segment it precedes. The card SHALL be placed immediately before the title clip's
first surviving segment (for a clip with partial cuts, its first kept span). When cuts remove the title clip
entirely, so that it contributes no segment, the card SHALL instead be placed immediately before the first
surviving source segment of the same chapter, so the chapter still opens with its card. When every clip of the
chapter is cut away, so that the chapter has no source segment, no card SHALL be inserted for it. A chapter
that resolved no title clip SHALL get no card. When `look.decorators` does not include `title` (or is absent),
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
