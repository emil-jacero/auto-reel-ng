## ADDED Requirements

### Requirement: A render the service refuses for a missing clip is told, and the screen re-reads
The service refuses an enqueue with a 409 whose conflict kind is `missing_clips` when the event plays a
clip that is missing from disk ("Enqueue refuses an event that plays a clip missing from disk"). Both
Render controls that send an enqueue request (the event page's Render and Render anyway, and a list row's
Render) SHALL handle that answer, in addition to the answers listed in "An event's page schedules its
render" and "The event list shows live job state and offers a render". The client SHALL tell it from the
other 409s by the published conflict kind, not by the problem's prose, and a `missing_clips` answer that
carries no list of clips SHALL be reported as an answer the client does not understand, as a 409 without
its kind is, never as "already active".

The refusal can only reach a screen whose read is out of date, because both screens already hold Render
back for the clips their read lists as missing. It means a played clip has gone missing since that read.
No job is enqueued and none is shown, and the screen SHALL re-read so that its own guard takes over:

- **On the event's page**, the render region SHALL say, in words with an error icon, that the render was not
  queued because the event plays clips that are missing from disk, SHALL name each clip the answer lists,
  and SHALL say to restore them, or remove them in Edit mode. The page SHALL then re-read the event. When
  the re-read lists the clips as blocking the render, the page offers neither Render nor Render anyway, as
  "An event's page schedules its render" requires, and keeps the refusal's words in view. When the re-read
  lists no blocking clip (the clips came back), the page offers Render again and the operator may press it.
  When the pressed control is gone after the re-read, keyboard focus SHALL move to the render region's job
  status, never to the document's body.
- **On a list row**, an error notification SHALL name the pressed event as the row's other notifications do
  (by its title followed by its date, or by its folder name when it has no title), SHALL say that its render
  was not queued because clips are missing from disk, SHALL name the clips (the first three, and their
  number when there are more), and SHALL link to the event's page. The list SHALL then re-read, so that the row shows its missing clips and says that they block its
  render in place of the Render control.

A refusal SHALL NOT create, show or announce a job, and SHALL NOT change the event's saved `reel.yaml`.

#### Scenario: The page learns of a clip that vanished after it was read
- **WHEN** the operator has `2024-09-04 - Hämtad` open, which needs a render and whose clips are all on disk,
  the clip `s1710004.mp4` is then deleted from its folder, and the operator presses Render
- **THEN** no job is enqueued, the page says that the render was not queued because `s1710004.mp4` is
  missing from disk and to restore it or remove it in Edit mode, and after its re-read the page offers
  neither Render nor Render anyway and lists `s1710004.mp4` among the clips missing from disk

#### Scenario: Keyboard focus survives the refusal
- **WHEN** the operator presses Enter on Render on that page, and the answer is the refusal
- **THEN** keyboard focus is on the render region's job status, and the next Tab reaches the next control
  of the page, not the top of the document

#### Scenario: The clip came back before the page re-read
- **WHEN** the refusal reaches the page, and the clip is on disk again by the time the page re-reads
- **THEN** the page offers Render again, and pressing it sends a new enqueue request

#### Scenario: Several clips are all named
- **WHEN** the refusal lists `Kväll/gone-a.mp4` and `gone-b.mp4`
- **THEN** the page names both

#### Scenario: A list row learns of the clip
- **WHEN** the list shows `2024-06-27 - Grillkväll med grannarna` offering Render, one of its clips is deleted
  from its folder, and the operator presses its Render
- **THEN** no job is enqueued, an error notification names “Grillkväll med grannarna” with its date, says
  that its render was not queued because the named clip is missing from disk, and links to its page
- **AND** after the list re-reads, the row shows 1 missing clip and says that missing clips block its
  render, and offers no Render

#### Scenario: A refusal without its clips is not understood
- **WHEN** the service answers an enqueue with a 409 whose conflict kind is `missing_clips` but whose body
  lists no clips
- **THEN** the screen says that the render was not queued and names the status it received, and it does not
  follow any job

#### Scenario: The refusal fits a phone-width window
- **WHEN** the page of `2024-09-04 - Hämtad` is shown 390 pixels wide and shows the refusal
- **THEN** the page does not scroll horizontally, and the refusal's words and the clip's name are fully
  visible
