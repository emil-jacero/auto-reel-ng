## MODIFIED Requirements

### Requirement: Each chapter's title card is a block on the Timeline

The Timeline SHALL show a lane of title cards directly above the clips, from the event detail's resolved cards
(`chapters[].card`) and the detail's `title_cards.enabled` (the draft's Title cards switch while it differs, in Edit mode), with one block per chapter whose card the render draws: a
chapter with a shown clip that has footage left after the cuts, when title cards are enabled. The block
SHALL show the card's title text (its resolved `title`), its length, and its look in words and shape, never by
colour alone:

- a **black** card SHALL be a block of its own, as long as the card's `duration`, **before** the chapter's first
  footage, and SHALL add its length to the track: the clips after it start that much later. A cut at the start of
  the chapter's first clip does not move it: the card opens the chapter, and the leading cut's hatch follows it.
- a **video** card SHALL be a block over the **start** of the chapter's first footage, aligned with the footage it
  covers, joined to the clip by an edge marker, as long as the card's `duration` or the first kept span if that
  is shorter, and SHALL add no time. It SHALL start where the first kept span starts, so a clip whose first 3 s
  are cut puts the block at 3 s.
- the **opening card** (the default chapter's) SHALL be first when the default chapter plays first, as the page
  lists the chapters.

A chapter's card anchors at its first shown clip; when every part of that clip is cut, at the next shown clip of
the chapter that has footage, as the render moves it. A chapter with no shown clip, or whose shown clips are
wholly cut, SHALL have no block. When title cards are not enabled, every chapter with footage SHALL have its block drawn in an off look (a dashed
outline and the word "not enabled", no time added) and the lane SHALL say once that the render draws no title cards for
the event, adding "set by the project's config.yaml" when the detail's `title_cards.source` is `project`. The page
SHALL NOT guess the effective state from `reel.yaml` alone: it SHALL use the detail's `title_cards`, which the
engine resolves from the event and the project, and the movie's length SHALL be presented as final whenever that
answer exists, never with a "not counted" caveat. When `title_cards` is null (`title_cards_error`), the lane SHALL
say so with the service's words and draw no block. When the event's card style or a chapter's card could not
be resolved (`title_card_error`, `card_error`), the lane SHALL say so with the service's words and draw no block
for the cards affected; a card with a duration that is not a finite number above zero SHALL be said as unreadable,
never drawn at a guessed length. A card block SHALL be drawn only when in view (the track's windowing), and its
look SHALL meet the contrast of the rest of the page in the light and in the dark scheme.

Each block SHALL show a miniature of its card as its background: the card's own image ("Card images are fetched
once and kept"), fitted to cover the block, so that a black card is dark and a video card is its text over the
clip's filmstrip. A black card's block SHALL keep a light inner ring in the dark scheme, so that it is told from the
page. The card's title SHALL be written over the miniature when it fits the block, and the block's accessible name
and tooltip SHALL carry it always. A block SHALL be at least 24 px wide however far the track is zoomed out, drawn
over the neighbouring track without moving it, so that a card is still pressed; its time on the track SHALL not
change. While a card's image is missing, the block SHALL show the card's title on black. The Timeline plays and shows
the cards: "The Timeline plays the title cards as the movie will" and "The playhead can be put in a card" say how, and
no note SHALL say that the Timeline does not play cards. A press in a black card's span SHALL select the card and
SHALL also put the playhead there.

#### Scenario: A black card before the second chapter
- **WHEN** an event with the chapters "" (opening card black, 3.0 s) and "Dag 2" (black, 4.0 s) has a 20 s clip in
  each, at 40 px per second
- **THEN** the lane shows the opening block first, 120 px wide, then the clip 800 px wide, then "Dag 2"'s block
  160 px wide before its clip, and the chapter band's "Dag 2" starts at the block

#### Scenario: A video card sits on the footage and adds no time
- **WHEN** "Dag 2" has a video card of 4.0 s and its first clip is 20 s
- **THEN** the block is 160 px wide at the clip's first pixel, the clip does not move, and the movie's length does
  not change

#### Scenario: A leading cut moves a video card, not a black card
- **WHEN** the first clip of each of two chapters has a cut from 0 to 3.0 s, one chapter's card being black and
  the other's video
- **THEN** the black card is drawn before the clip's start, and the video card begins at 3.0 s of the clip

#### Scenario: A card longer than its footage
- **WHEN** a video card of 7.0 s is on a first clip whose first kept span is 3.0 s
- **THEN** the block is 3.0 s wide, as the render clamps it, and its words say "3.0 s of 7.0 s"

#### Scenario: A chapter cut away entirely has no card
- **WHEN** every clip of a chapter is wholly cut
- **THEN** the lane has no block for it

#### Scenario: The title decorator is off
- **WHEN** the detail has `title_cards: {enabled: false, source: "event"}`
- **THEN** the blocks are drawn in the off look with no time added, and the lane says the render draws no title cards

#### Scenario: The decorators are not set in reel.yaml
- **WHEN** the event's `reel.yaml` has no `look.decorators` and the detail has `title_cards: {enabled: true, source: "default"}`
- **THEN** the blocks are drawn as cards that play, their black lengths are in the movie's length, and nothing says
  "unset" or "not counted"

#### Scenario: The project turns them off
- **WHEN** the detail has `title_cards: {enabled: false, source: "project"}`
- **THEN** the blocks are off, and the lane says it is set by the project's config.yaml

#### Scenario: The decorators are not a list
- **WHEN** the detail has `title_cards: null` and `title_cards_error` names `look.decorators`
- **THEN** the lane shows that text and no block, and the movie's length does not claim to count cards

#### Scenario: The switch is turned off in the draft
- **WHEN** in Edit mode the operator turns Title cards Off and has not saved
- **THEN** the blocks go off and the movie's length drops the black cards at once, and Reset brings them back

#### Scenario: A card that cannot be resolved
- **WHEN** the detail has `title_card_error: "look.title_card.font_family"` and every chapter's `card` is null
- **THEN** the lane shows that text in a note and no block, and the clips, cuts and playhead are unaffected

#### Scenario: A press in a black card's span
- **WHEN** the operator presses inside a black card's block with the playhead at 5.0 s of a clip
- **THEN** the card is selected and the playhead is in the card at the press, showing its image

#### Scenario: A zoomed-out card stays pressable
- **WHEN** a 3.0 s black card is drawn at 4 px per second (12 px wide)
- **THEN** its block is 24 px wide, the clips after it start where they did, and a press on it selects the card

#### Scenario: A block shows its card
- **WHEN** a black card's image has been fetched and the Timeline is in the dark scheme
- **THEN** the block's background is that image, its title is written over it when it fits, its accessible name
  carries the title, and a light ring marks its edge

### Requirement: Play follows the playhead through the clips, skipping cuts

A **Play** button (**Pause** while playing) SHALL play from the playhead. It SHALL play as the movie will: no frame that lies wholly inside a cut is shown, cuts are joined as the render joins them, and a cut that runs to the end of a clip, or ends within 0.1 s of the clip's length, ends playing of that clip at that cut's start (the rules of the clip preview, D-16). At the end of a clip it SHALL go on into the next clip's proxy, or into the title card that comes before it ("The Timeline plays the title cards as the movie will"); at the end of the timeline it SHALL stop with the playhead at the end. The proxy's sound (AAC) SHALL play, in Firefox as in Chrome, including for a clip whose source has PCM audio. The playhead SHALL follow the video while it plays, and the button's state SHALL be in its words ("Play", "Pause"), not in its icon alone. Moving the playhead while playing SHALL continue playing from the new place: a touch tap, a click and a drag on the track or the ruler are such moves, and none of them SHALL leave the Timeline paused. Play SHALL wait until the page's read of the cuts has answered, so that no frame inside a cut is shown for want of them (the button SHALL say, in words, that the cuts are being read); where the cuts could not be read, Play SHALL be available and the note that the cuts could not be read SHALL say that Play does not skip cuts.

If the browser refuses to start playing without a gesture, or the proxy fails to play, the Timeline SHALL say so by cause in a note, as the clip preview does, and stay paused.

#### Scenario: Cuts are skipped
- **WHEN** a clip lists a cut from 2.0 to 4.0 s and the playhead plays from 1.0 s
- **THEN** no frame between 2.0 and 4.0 s is shown and the playhead goes from 2.0 s to 4.0 s of that clip

#### Scenario: Play goes on into the next clip
- **WHEN** the playhead plays to the end of the first of three clips
- **THEN** the video loads the second clip's proxy and plays on from its first frame, and the playhead keeps moving through the whole timeline

#### Scenario: A tap while playing goes on playing
- **WHEN** the Timeline is playing and the operator taps (touch) or clicks (mouse, with no delay between press and release) the track at another place
- **THEN** the playhead moves there, the button still says "Pause", and the video's time keeps advancing

#### Scenario: Play waits for the cuts
- **WHEN** the Timeline is open while the page's read of the cuts is still on its way and the operator presses Play or Space on the playhead
- **THEN** nothing plays, the Timeline says that the cuts are being read, and Play works as soon as they have been read

#### Scenario: The cuts could not be read
- **WHEN** the read of the cuts failed and the operator presses Play
- **THEN** it plays, and the note says that Play does not skip cuts

#### Scenario: A Sony PCM clip has sound in Firefox
- **WHEN** the Timeline plays a clip whose source is a Sony XAVC clip with PCM audio in Firefox 155 or newer
- **THEN** the clip's audio is heard (a decoded audio peak above zero), because it is the proxy's AAC track that plays

#### Scenario: Play does not start two videos
- **WHEN** the Timeline is playing and the operator presses Play on the event's movie
- **THEN** the Timeline pauses

## ADDED Requirements

### Requirement: The Timeline plays the title cards as the movie will

When the Timeline plays into a **black** card's span, the player area SHALL show that card's image in place of the
video, fitted inside the same box as the video (letterboxed, uncropped), with the card's fade-in and fade-out as its
opacity over the card's length. The playhead SHALL advance in real time for the card's whole `duration`, without any
video playing, and then playback SHALL go on into the chapter's first clip at that clip's first kept frame. The
Timeline SHALL load and seek that clip's proxy during the card, so that the hand-over shows the clip's frame with no
gap of black or of a stale picture; the card's image SHALL be removed only when that frame is ready to be shown, and
if it is not ready when the card ends the card SHALL stay on its last frame until it is. A **video** card's image
(text on transparency) SHALL be laid over the playing video for the card's window, from the start of the first kept
span to its clamped end, drawn above the video at the same size and position, with the fades as opacity; it SHALL
add no time and SHALL not touch the video. The card's fades SHALL be the project's default fades (2 s in, 2 s out)
scaled so that their sum does not exceed the card's length, as the render clamps them, because the event detail does
not carry them; the Timeline SHALL say once, in the card inspector slot's words, that a fade set by the event's or
the project's `look.title_card` is not shown here.

Pause and Play, Space on the playhead, and a seek SHALL work inside a card: Pause stops the card's clock where it is,
and Play goes on from there. A video that starts elsewhere on the page ("The Timeline pauses, and is paused, like every
other player") SHALL pause the Timeline during a card too, with the playhead where it stopped and no announcement; the
card's clock SHALL NOT go on by itself afterwards. A card's span in a cut-skipping play SHALL be played whole. The
sound of a card is silence; the Timeline SHALL not start an audio element for it.

The card clock SHALL be the browser's frame clock, and SHALL be driven by elapsed time, not by a count of frames, so a
slow frame does not stretch the card. A page that is hidden SHALL pause the clock as it pauses a video.

#### Scenario: Play from zero through the opening card
- **WHEN** an event whose opening card is black and 7.0 s is played from 0:00 on Chrome 154 and on Firefox 155 or
  newer
- **THEN** the card's image is shown, the playhead moves from 0 to 7.0 s over about 7 s, and then the first clip's
  video plays from its first frame with the card gone, and the sampled playhead never goes backwards

#### Scenario: The hand-over has no gap
- **WHEN** the card ends and the clip's proxy was loaded and sought during the card
- **THEN** no sampled frame between the card's last frame and the clip's first shows the page's background, and the
  video's `currentTime` is the clip's first kept time when the card goes

#### Scenario: A video card over the video
- **WHEN** the Timeline plays a chapter whose card is video and 4.0 s over its first clip
- **THEN** the card's image is above the video for 4.0 s of the clip's time, the video keeps playing under it, the
  card's opacity rises over its fade-in and falls over its fade-out, and the image is gone after the window

#### Scenario: Pause and Play inside a card
- **WHEN** the operator presses Pause 1.2 s into a 7.0 s black card and then Play
- **THEN** the playhead stops at 1.2 s of the card, the image stays, the button says "Play", and Play goes on from 1.2 s
  and ends the card 5.8 s later

#### Scenario: Another player starts during a card
- **WHEN** the Timeline is inside a black card and the operator presses Play on the event's movie
- **THEN** the Timeline is paused with its playhead where it was, the movie plays, nothing is announced, and the card
  does not go on

#### Scenario: A slow frame does not stretch the card
- **WHEN** the browser presents no frame for 500 ms during a 7.0 s card
- **THEN** the card still ends 7.0 s after it began, within one frame

### Requirement: The playhead can be put in a card, and the readouts count card time

Pressing or dragging the playhead, on the ruler or on the track, into a black card's span SHALL put the playhead in
that card at that point and show that card's image there (opacity from its fades at that time), with no video change
beyond what the clip after the card needs for "The Timeline plays the title cards as the movie will". The playhead
SHALL be at the pointer in the card; the time it names SHALL count the card. The Event readout SHALL count the cards'
time: with the playhead 1.0 s into the opening card it reads "Event 0:01.00 of 2:43.76", the length being the movie's length with its
black cards, as the readout's scale is chosen from it. Inside a card the Clip readout SHALL read "Card 0:01.20 of
0:07.00" (the time in the card and the card's length, written to one scale so that the readout's width does not
change), and the clip's name cell SHALL name the card ("Title card for the opening"). The playhead slider's value text
SHALL say "title card for <chapter>, 1.2 s of 7.0 s; event 0:01.20 of 2:43.76" in a card, and `aria-valuenow` SHALL be
the position on the whole timeline including cards.

A frame step (Left, Right) and Shift/Page steps SHALL be taken on the timeline including cards: a step by seconds
(Shift, Page Up, Page Down) that lands in a card stops there; a frame step into the card from the clip before it SHALL
land on the card's first instant, and from the card on the clip's first frame; Home SHALL be the start of the opening
card when the opening card is black and End the last frame of the last clip. Within a card, Left and Right SHALL move by
one frame of the movie's output rate if the Timeline knows it, else by 0.1 s; the Timeline SHALL not claim frame
accuracy in a card. The end of a scrub, a key step and a click that end in a card SHALL be announced once ("Playhead at
title card for the opening, 1.20").

#### Scenario: A press into a mid card
- **WHEN** the event has a 4.0 s black card between two chapters and the operator presses the track 1.0 s into the
  card's span
- **THEN** the card's image is shown, the playhead is 1.0 s into the card, the Clip readout reads "Card 0:01.00 of
  0:04.00", and the Event readout reads the clip time before the card plus 1.0 s

#### Scenario: A drag across a card
- **WHEN** the operator drags the playhead from the end of the clip before a card, through the card, to the start of the
  next chapter's clip
- **THEN** the card's image shows while the pointer is in its span and the video returns after it, never more than one
  `<video>` for the Timeline and one seek in flight

#### Scenario: The Event readout counts card time
- **WHEN** the playhead is 3.00 s into the opening card of an event whose movie is 2:43.76 long
- **THEN** the Event readout reads "Event 0:03.00 of 2:43.76" and the Clip readout reads "Card 0:03.00 of" the card's length

#### Scenario: The slider says it is in a card
- **WHEN** a screen reader reads the playhead 1.2 s into the opening card of 7.0 s
- **THEN** its value text names the title card, 1.2 s of 7.0 s, and the event time including cards

### Requirement: Card images are fetched once and kept

When the Timeline opens, the page SHALL ask for every card's image once, for the cards the lane draws, one request at a
time, in play order, from `POST /api/v1/events/{id}/title-card/preview` with each card's resolved text, background and
length (and the draft event title for the opening card, and the draft's style when it differs from the saved one),
and SHALL keep each answer as an object URL keyed by the card's draft body and the style. The page SHALL ask for no
more than one at a time, and SHALL NOT start another request while the previous one is in flight. A `503` SHALL be
waited out for its `Retry-After` (at most 30 s a card, at least 1 s) and asked again up to three times, after which the
card is left without an image and said in words once; any other failure SHALL leave the card without an image and be
said by cause once, as the card inspector's preview does, and never retried by itself. While a card has no image its
block, and the player area during it, SHALL show its title on black. An edit to a card or to the event's card style in
Edit mode SHALL fetch only the cards affected, after the same quiet time as the inspector's preview, and SHALL replace
the old image only when the new one has arrived. Object URLs SHALL be revoked when the card changes, is removed, or the
Timeline closes. The cards' requests SHALL write nothing and SHALL not hold the page's other requests back.

#### Scenario: One request at a time, in order
- **WHEN** the Timeline opens on an event with six chapters
- **THEN** six requests are made one after another in play order, never two at once, and each block shows its image
  as it arrives

#### Scenario: A busy service
- **WHEN** a request is answered 503 with `Retry-After: 2`
- **THEN** the card is asked again after 2 s, the other cards wait behind it, and the page shows the card's title on
  black meanwhile

#### Scenario: Only the edited card is fetched
- **WHEN** the operator edits the third chapter's card title in the inspector and stops typing
- **THEN** one request is made for that card after the quiet time, the other cards' images are kept, and the block
  and the player show the new image when it arrives

#### Scenario: A card that cannot be drawn
- **WHEN** a card's request is answered 502
- **THEN** the card's block and its span in the player show the title on black, the cause is said once in words, and no
  further request is made for that card until it is edited

#### Scenario: Closing the Timeline lets go
- **WHEN** the Timeline section is closed
- **THEN** every object URL it made has been revoked and no request is in flight
