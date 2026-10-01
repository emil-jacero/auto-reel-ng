## ADDED Requirements

### Requirement: The event detail places clips not in reel.yaml by the render's adoption rule

`GET /api/v1/events/{event_id}` SHALL list every clip on disk that the event's `reel.yaml` does not list,
whether NEW or IGNORED, in the chapter that a render's adoption rule names for it (headless-cli, "NEW-clip
adoption policy"). That is the chapter named after the clip's folder when `reel.yaml` names that chapter, and
the default chapter otherwise. A NEW clip is therefore shown in the chapter a render adopts it into.

Within a chapter, those clips SHALL follow the clips that `reel.yaml` lists. Among themselves they SHALL be
in the sort rule's order, which is the order a render appends them in. When `reel.yaml` does not name the
default chapter and a clip is placed there, the detail SHALL list the default chapter after the chapters
`reel.yaml` names. The detail SHALL list no other chapter that `reel.yaml` does not name. An event without a
`reel.yaml` SHALL keep listing the chapters its folders seed, which are the chapters a render seeds.

Leaving ignored clips aside, the detail read before a render SHALL therefore list the same chapters, in the
same order and each with the same clips in the same order, as `reel.yaml` lists once the render has adopted
the event's NEW clips. The one exception is a chapter that the detail lists only for ignored clips: a render
adopts no ignored clip, so `reel.yaml` does not gain that chapter. The read SHALL apply this placement
without adopting anything, and SHALL stay read-only and probe-free.

#### Scenario: A NEW clip is shown in its folder's chapter

- **WHEN** the `reel.yaml` of `2024-08-20 - Två kapitel - Tjörn` lists `s1710001.mp4` in its default chapter
  and `Kvällen/s1710002.mp4`, `Kvällen/s1710003.mp4` in `Kvällen`, and `Kvällen/s1710004.mp4` is on disk
  but not listed
- **THEN** the detail lists `Kvällen` as `Kvällen/s1710002.mp4` (active), `Kvällen/s1710003.mp4` (active),
  `Kvällen/s1710004.mp4` (new), and the default chapter as `s1710001.mp4` (active) alone

#### Scenario: A clip in a folder without a chapter is shown in the default chapter

- **WHEN** an event's `reel.yaml` names only the default chapter, listing `s1710001.mp4`, and
  `Dag 2/s1710002.mp4` and `Dag 2/s1710003.mp4` are on disk
- **THEN** the detail lists exactly one chapter, the default chapter, holding `s1710001.mp4` (active) and then
  both `Dag 2` clips (new) in the sort rule's order, and lists no `Dag 2` chapter

#### Scenario: A document that names no chapters is shown as one default chapter

- **WHEN** an event's `reel.yaml` holds only `metadata`, and the event holds `s1710001.mp4` in its folder and
  `Kvällen/s1710002.mp4`
- **THEN** the detail lists one chapter, the default chapter, holding both clips as new in the sort rule's
  order, and lists no `Kvällen` chapter

#### Scenario: An ignored clip in a folder without a chapter is shown in the default chapter

- **WHEN** an event's `reel.yaml` names only the default chapter and ignores `Dag 2/s1710002.mp4`, which is
  on disk
- **THEN** the detail lists `Dag 2/s1710002.mp4` in the default chapter with status ignored, and lists no
  `Dag 2` chapter

#### Scenario: An event without reel.yaml shows its folder seed

- **WHEN** an event has no `reel.yaml` and holds `s1710001.mp4` in its folder and `Kvällen/s1710002.mp4`
- **THEN** the detail lists the default chapter holding `s1710001.mp4` and a `Kvällen` chapter holding
  `Kvällen/s1710002.mp4`, both new, and no `reel.yaml` is written

#### Scenario: The page's chapters are the movie's chapters

- **WHEN** the detail of an event is read while it has NEW clips in a folder whose chapter `reel.yaml` names,
  in a folder whose chapter it does not name, and in the event folder; then `auto-reel render` adopts them;
  then the detail is read again
- **THEN** both reads list the same chapters, each with the same clips in the same order, ignored clips
  aside, and these are the chapters and clips that `reel.yaml` then lists
- **AND** every clip the first read listed as new, the second lists as active
