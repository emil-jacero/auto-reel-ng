## ADDED Requirements

### Requirement: The title card dialog holds every name and every title-card setting

The title card dialog ("A selected title card opens its inspector in Edit mode") SHALL be the one place in Edit mode for a chapter's
name and for every title-card setting, the same for the event's own chapter and for every other chapter. The page SHALL hold no
other control for a name, a card or the event's card style. The dialog SHALL have one live preview of the card being edited, drawn by the
service from the draft ("The preview is drawn by the service while the operator edits"), visible whichever tab is shown, and two tabs in a
tab list named "Title card settings" (`role="tablist"`, each tab `role="tab"` with `aria-selected`, its panel `role="tabpanel"` named
by the tab). Left and Right Arrow, Home and End SHALL move between the tabs, and Tab SHALL move from the tab list into the shown panel.
Two tabs, not two stacked groups, keep the dialog the height of one tab and keep the preview in view while the operator edits either.

- **"This title card"** SHALL be shown when the dialog opens, except as the last bullet says. In this order it SHALL hold: the **Name**
  ("Edit mode adds, renames, reorders and deletes chapters"); **Card title (overrides the name)** with a **Use the name** button, only for a card
  whose draft has its own `title`, and no control that adds one; the **Subtitle**; **Background**; **Font**; **Title size**;
  **Subtitle size**; **Text colour**; **Position**; and **Length**. Each field but the Name SHALL have **Use event style** ("A card's fields are
  overrides that follow the event style until set"). The card's heading follows the Name: a card with no title of its own draws the name
  (the event's title for the opening card), and the preview, the dialog's name and the Timeline's blocks follow it as it is typed.
  Use the name SHALL remove the card's own title from the draft; the key goes from `reel.yaml` on Save.
- **Length** SHALL be a number field in seconds named "Length of the title card (seconds)", showing the card's length, else the event's default
  length as its placeholder with the words "Event style". It SHALL take whole tenths, from 0.5 to 60, and for a card over video no more than
  the first span of the chapter's anchor clip that the draft's cuts keep ("A black card's drag moves everything after it, and a video card's is bounded by its clip"), the limits the
  length drag has; a card whose limit makes it not adjustable SHALL say why and take no value. A typed length outside the limits, or not a number, SHALL be
  refused in words under the field that name the limits (never rounded to a value the operator did not type), SHALL keep the text, mark the field invalid and leave the draft as it was; an accepted one SHALL be written
  to the draft as it is typed, as the drag's release is, and a length equal to the one read SHALL count as no change. The field and the Timeline's length drag
  are two ways to edit the same `duration`: after a drag, the field shows the new length, and a length typed here is drawn on the Timeline
  at once. Use event style SHALL remove the card's `duration`.
- **"All title cards in this event"** SHALL hold the event-wide style fields of "Edit mode edits the event's card style in one place" and the
  Title cards On or Off switch of "Edit mode switches the event's title cards On or Off". Its edits SHALL change the preview of the card shown.
- A tab that holds a problem the operator cannot see, a refusal by the service at one of its fields or a field the dialog refused, SHALL say so in its label ("All title
  cards in this event, 1 problem"), and the dialog SHALL open on the first tab that holds one when the service's last answer named one.
- Every field SHALL work with the keyboard alone, have a visible label, be at least 44 × 44 CSS pixels where the primary pointer is coarse, and fit 320 to
  1280 CSS pixels without a horizontal page scroll in both colour schemes.

Every edit in either tab SHALL go into the page's one draft and be counted, saved, guarded and undone as every other Edit-mode edit: a
name as "chapter renamed" or "Title", a card as "title card changed", the style as "Card style changed", the switch as "Title cards turned off" or "Title cards
turned on". Save SHALL send the same whole-document `PUT` under `If-Match` that every edit sends, with only the keys of what changed.

#### Scenario: Two tabs, the name first
- **WHEN** the operator presses "Edit title card for Kvällen" on `2024-08-20 - Två kapitel - Tjörn`
- **THEN** the dialog opens on the tab "This title card" whose first field is the Name, named "Name of chapter Kvällen" and holding `Kvällen`,
  followed by Subtitle, Background, Font, Title size, Subtitle size, Text colour, Position and Length; the preview is shown above them at 390 px and beside
  them at 1280 px; and the tab "All title cards in this event" is one Arrow key away

#### Scenario: Switching tabs keeps the preview and the draft
- **WHEN** the operator types `Dag 2` in the Name field, moves to "All title cards in this event" with the Right Arrow, picks the text
  color `#FFD700`, and moves back
- **THEN** the preview was shown throughout and now shows `Dag 2` in `#FFD700`, the Name field still holds `Dag 2`, and the save bar says
  "1 chapter renamed" and "Card style changed"

#### Scenario: A card with its own title
- **WHEN** the chapter `Kvällen`'s card in `reel.yaml` has `title: Kväll på stranden` and the operator opens its dialog
- **THEN** the dialog shows the Name (`Kvällen`) and then "Card title (overrides the name)" holding `Kväll på stranden` with "Use the name"
- **WHEN** the operator presses Use the name
- **THEN** the field is gone, the preview draws `Kvällen`, and the next Save removes `title` from that card

#### Scenario: A card with no title of its own offers none to add
- **WHEN** the operator opens the dialog of a chapter whose card sets no `title`
- **THEN** there is no "Card title" field and no control that would add one, and the card's heading is the Name

#### Scenario: The same dialog for Main
- **WHEN** the operator opens "Edit title card for Main"
- **THEN** it has the same tabs and fields as a chapter's, its Name field is named "Title of the event" and edits the event's title, and its heading
  and the preview follow it

#### Scenario: Typing a length
- **WHEN** the operator types `6` in the Length field of a black card of 4.0 s
- **THEN** the draft holds `duration: 6.0`, the Timeline's card block is 6.0 s long, and the save bar counts one changed card
- **WHEN** the operator types `0.3`, and then `90`
- **THEN** each is refused under the field in words that name the limits 0.5 s and 60 s, the text is kept, and the card stays at 6.0 s

#### Scenario: A video card's length is bounded by its clip
- **WHEN** a card over video lies over a clip whose first kept span is 3.4 s and the operator types `5`
- **THEN** the field refuses it in words that name 3.4 s as the longest, and the draft is unchanged

#### Scenario: The drag and the field are one edit
- **WHEN** the operator drags a card's end edge to 6.0 s, releases, and opens the card's dialog
- **THEN** the Length field holds 6.0
- **WHEN** the operator types `7` and closes the dialog
- **THEN** the card block on the Timeline is 7.0 s long and Save writes `card.duration: 7.0`

#### Scenario: A problem in the other tab is shown on the tab
- **WHEN** the service answers a Save with 400 naming `look.title_card.title_font_size` and the operator opens a dialog
- **THEN** the dialog opens on "All title cards in this event", whose label says "1 problem", with the message at the field

#### Scenario: Nothing else on the page edits a name or a card
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn`, in light and dark at 1280 and 390 px
- **THEN** the page holds no pencil, no click-to-rename title, no "Main title card" line, no card row, no "Card style for this event" section and no Title cards
  section; each chapter's section is its header bar and its clips

#### Scenario: One save writes the keys that changed
- **WHEN** the operator renames `Kvällen` to `Kväll`, edits the opening card's event title, sets the style's position to Top and turns the cards Off, in the dialogs, and saves
- **THEN** one `PUT` under `If-Match` is sent whose chapter is named `Kväll`, whose metadata title is the new title, whose `look.title_card.position` is `top`
  and whose `look.decorators` is `[]`, and no other key differs from `reel.yaml` as read

### Requirement: The marks line is one aligned unit

The line above the chapters that shows how clips are marked and offers Clear marks, Rotate marked left, Rotate marked right and Move marked
to… ("Edit mode marks clips to move together", "Edit mode moves the marked clips to a chapter") SHALL read as one calm, aligned toolbar from 320 to
1280 CSS pixels wide, in both colour schemes and for both kinds of pointer.

- **One control height.** Clear marks, both Rotate buttons, Move and the chapter picker SHALL have the same height, one size for the line (at least 44 CSS pixels
  where the primary pointer is coarse), and the same corner radius.
- **One axis.** Controls in a row SHALL have their vertical centres within 1 CSS pixel of each other, and a text beside them (the
  marking hint, the count of marked clips, the label "Move marked to…") SHALL be centred on the same axis. No item SHALL sit higher or lower than
  its neighbours.
- **Consistent gaps.** The gap between two controls of a group, between two groups and between two rows SHALL each be one value, the same in every row and at every width.
- **Rows.** The first row SHALL hold the marking hint and, at its end, the count and Clear marks; the second SHALL hold Rotate marked left and right, then the Move marked to… group (label, picker,
  Move) where it fits; the reason SHALL be one hint line below the controls, muted, starting at the toolbar's left edge. The reason SHALL NOT float beside Move. The hint line
  SHALL keep its place and its height whether or not it speaks, so that marking the first clip moves no row.
- **Narrow windows.** Where the toolbar does not fit a row, it SHALL wrap by whole groups: the Move group goes on a row of its own with the label above, the picker filling the
  row beside Move; Rotate marked left and right share a row where they fit and otherwise take a row each at the same width. Every wrapped row SHALL keep the one height and the
  one axis, and nothing SHALL scroll horizontally at 320 CSS pixels.
- The names, descriptions, `aria-disabled` states and reasons of the controls ("Edit mode moves the marked clips to a chapter") are unchanged.

#### Scenario: Controls in a row share a height and an axis
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn` at 1280 px, light and dark, with one clip marked
- **THEN** the bounding boxes of Clear marks, Rotate marked left, Rotate marked right, the chapter picker and Move have the same height, and in each row the vertical centres of
  its controls, and of the label "Move marked to…" and the count, differ by at most 1 px

#### Scenario: The reason is one muted line below
- **WHEN** no clip is marked
- **THEN** "Mark a clip to move it." is one muted line below the controls, aligned to the toolbar's left edge, and not beside Move
- **WHEN** the operator marks a clip
- **THEN** no row of the toolbar and no chapter below it moves, and the line says "Choose a chapter."

#### Scenario: The toolbar wraps in aligned rows
- **WHEN** the window is 390 px wide and again 320 px, light and dark
- **THEN** the Move group is on its own row with the label above and the picker beside Move, every row's controls share one height and one centre line (within 1 px), the
  hint line is below them, and the page does not scroll horizontally

## MODIFIED Requirements

### Requirement: Edit mode adds, renames, reorders and deletes chapters

In Edit mode the operator SHALL be able to change the event's chapters themselves. Every control below SHALL
be reachable with the keyboard and SHALL name, to assistive technology, the chapter it acts on.

- **Add chapter**, after the last chapter, SHALL ask for a name and add an empty chapter with that name at the
  end.
- **Rename** SHALL be done in the title card dialog, in its Name field ("The title card dialog holds every
  name and every title-card setting"), by the one workflow for every chapter. A chapter's header bar SHALL show its name as plain text: not a
  button, with no pencil and no hover or focus change, and pressing it SHALL do nothing. There SHALL be no Rename
  button, no inline name field and no dialog of its own for a name. The event's own chapter (the default chapter,
  whose clips are the event folder's) has no name to rename: it is headed `Main` or `Clips` ("The event's own chapter
  is headed ..." below), its title card shows the event's title, and its Name field edits that title. Clips without a
  chapter of their own join it. While the event lists other chapters, the page SHALL say this beside it.
- **Move up** and **Move down** SHALL move a chapter one place among the chapters, and SHALL be offered only
  while the event lists more than one chapter. After such a move, keyboard focus SHALL stay on the pressed
  control. At either end, the control that cannot move further SHALL say that it is unavailable.
- **Delete** SHALL remove a chapter only once it plays no clip. Its clips must first be moved to another
  chapter, or removed when missing. The event's own chapter can be deleted only when, in addition, it lists no
  ignored clip that the page would list under it again after the save: one from the event folder, or from a
  folder no chapter is named after. Such a clip would bring the chapter back, holding only ignored clips.
  When a chapter cannot be deleted, pressing Delete SHALL change nothing and leave focus on Delete. The page
  SHALL show and announce why the chapter cannot be deleted.

**The header bar.** Every chapter's header bar, the event's own chapter's too, SHALL hold, in this order, the chapter's name as plain
text, an **Edit Titlecard** button and the chapter's clip count; the chapter's tools (Move up, Move down, Delete, offered by the rules above) stay in their own row under the bar, which is sticky and keeps one line. The
button SHALL show an icon and the words "Edit Titlecard", SHALL be named "Edit title card for <name>" (the event's own chapter: its
heading) and SHALL open the title card dialog on the "This title card" tab ("A selected title card opens its inspector in Edit mode"). A
chapter's section SHALL show nothing between its header bar and its clips but the tools row and the notes of this requirement and of "Edit mode says what
a chapter's name means for clips added later": no card row, no "Main title card" line, no source line ("from the folder name"). A chapter added in the draft has no saved card, and its
button SHALL be offered all the same: the dialog says that its card is drawn after Save and keeps the preview from the draft.

Each chapter SHALL offer only the controls that apply to it. An event that lists one chapter, the event's own,
offers Add chapter and none of the others. The only chapter left, a deleted one aside, SHALL NOT offer Delete,
Move up or Move down, so that an event never saves without a chapter.

**The Name field.** In the dialog the field SHALL be the first of "This title card" and SHALL be named "Name of chapter <name>"
for a chapter and "Title of the event" for the event's own chapter, where <name> is the name the draft holds when the dialog opens. The
header bar and the dialog's title name the chapter by its name alone.

- An accepted name SHALL be written to the draft as it is typed, so that the dialog's heading, its preview, the chapter's header
  bar behind the dialog and the picker of Move marked to… follow it. A name equal to the chapter's current name, once the spaces
  around it are removed, SHALL change nothing. A rename SHALL be announced once, when keyboard focus leaves the field or the dialog
  closes, and not for each key; typing a name and typing the old one back announces nothing.
- A refused name SHALL be explained under the field in words, in a `role="alert"` that is remounted for each refusal, and the
  field SHALL be marked invalid. The draft keeps the last accepted name, and the field keeps the typed text. Done, with a refused
  name in the field, SHALL keep the dialog open and put keyboard focus in the field. Escape and Close SHALL close the dialog, return the
  field's text to the draft's name, and announce that the name was not changed and why; they SHALL NOT keep a refused name.
- While the field holds a refused name, Ctrl+S SHALL save nothing and SHALL say "Not saved: the name is refused."
- While a save or a move of marked clips is pending, the field and the dialog's other fields SHALL say that they are unavailable
  and SHALL change nothing (the busy-control rule); the bar's Edit Titlecard button SHALL say so too and open nothing.
- Reset, a conflict and Overwrite SHALL treat a name as any other edit; Reset SHALL restore the chapters' names as read.

**The event's own chapter's name is the event's title.** For the event's own chapter the Name field SHALL edit the draft's
title, the one the Details form's Title field edits, in step with it in both directions, counted once in the save bar ("Title") and
undone by Reset as one edit.

- The field SHALL hold the draft's title. While that is blank it SHALL be empty with the title the page resolved from the folder
  name as its placeholder and the words "From the folder name", else the word "Untitled". The page SHALL NOT guess a title.
- Any text SHALL be kept as the title, with no rule of the page's. A blank title means that it inherits from the folder name, and
  the field SHALL say so in the words of the Details form ("Left empty: inherits from the folder name when saved"). The
  service's refusal of an unusable title stays at the Details form and is retired by editing the title in either place.
- While the draft's title differs from the title read, the dialog SHALL say that saving changes the movie's file name, that if the
  movie was already rendered the next render saves it under the new name, and that the movie under its old name stays on disk. It SHALL NOT name a
  file: the event page names them after the save, from the verdict.
- The card's heading follows the name. A card that has its own title ("Card title (overrides the name)") keeps it.

When the browser's primary pointer is coarse, each of these controls, the header bar's Edit Titlecard button, Add chapter and Undo SHALL take a tap
anywhere in an area of at least 44 × 44 CSS pixels around it that reaches no other control, as every button
does ("Every control is large enough to touch").

A name SHALL be accepted only when both of these hold, once the spaces around it are removed. The spaces are
the characters the engine removes from a chapter's name, so a name the page accepts is a name `reel.yaml`
loads:

- it is not empty
- compared by full Unicode case folding, the comparison the engine makes, it differs from the name of every
  other chapter of the event, including a deleted chapter not yet saved, and from `Main`, the name the page
  shows for the event's own chapter. So `ß`, `ss`, `SS` and `ẞ` are one name, as are `Kvällen` and `KVÄLLEN`.

A refused name SHALL be explained at the name field, which keeps keyboard focus when the name was asked for
with Done or in the Add chapter dialog, and nothing SHALL change. The
name saved is the accepted name without the spaces around it. A chapter's name SHALL be described to the
operator as the words on its title card in the movie.

A chapter the page showed when Edit mode opened SHALL, once deleted, stay listed in its place until the edits
are saved, marked as deleted when the edits are saved. It lists none of its clips. Such a chapter offers an **Undo** control that returns it to its place, and keyboard focus SHALL move to that Undo. A
chapter the operator added in this Edit mode and then deletes SHALL simply be gone. A chapter that plays no
clip SHALL say so in Edit mode, and that a chapter without clips is left out of the movie. While the event
lists another chapter, a deleted one aside, it SHALL also say that clips can be dragged into it, or moved into
it with Move marked to… (see "Edit mode drags clips between chapters"). When it is the only
chapter listed, a deleted one aside, it SHALL NOT say that: no other chapter has a clip to drag or to move,
and the page offers no Move marked to… there.

The event's own chapter SHALL be headed `Main` while any other chapter is listed, a deleted one aside, and
`Clips` otherwise, as on the event page. Every change to the chapters SHALL count as an unsaved edit, like a
move:

- it SHALL be announced
- Reset SHALL restore the chapters as read
- leaving with it unsaved SHALL ask first
- the save bar SHALL count it ("Saving an edit writes only what the operator changed")

While a save is in flight, every chapter control and Add chapter SHALL say that it is unavailable and SHALL
change nothing when pressed.

#### Scenario: A first chapter added to a one-chapter event
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar`, whose clips are all in its own chapter, the
  operator presses Add chapter, types `Kvällen vid grillen` and confirms
- **THEN** a chapter `Kvällen vid grillen` is listed last, saying that it plays no clip and that clips can be
  dragged into it or moved into it with Move marked to…; the first chapter's heading reads `Main` instead of
  `Clips`; keyboard focus is on the new chapter's heading; the addition is announced; and the save bar says
  "1 chapter added"

#### Scenario: A lone chapter offers only Add chapter
- **WHEN** Edit mode opens on `2024-06-27 - Grillning med grannar`, whose clips are all in its own chapter
- **THEN** its one chapter offers no Move up, Move down or Delete, its header bar shows `Clips` as plain text with an Edit Titlecard
  button (the dialog's Name field edits the event's title), and the page offers Add chapter after it

#### Scenario: A name already taken, or no name, is refused
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator adds a chapter named `kvällen`, then one named
  only with spaces, then one named `main`
- **THEN** each is refused at the name field, which keeps keyboard focus. `kvällen` is refused because a
  chapter called `Kvällen` exists. The blank name is refused because a chapter needs a name. `main` is refused
  because `Main` is the page's name for the event's own chapter. No chapter is added.

#### Scenario: A name the engine would fold into another is refused
- **WHEN** on `2024-09-14 - Gatufest`, an event with a chapter `Straße`, the operator adds a chapter named
  `STRASSE`, then one named `strasse`
- **THEN** each is refused at the name field, which keeps keyboard focus, because a chapter called `Straße`
  exists. No chapter is added. A name that merely resembles it, such as `Strasse 2`, is accepted.

#### Scenario: The spaces the engine removes are removed
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator adds a chapter named with a next-line character
  (U+0085) before and after `Hamnen`
- **THEN** the chapter is added as `Hamnen`, without those characters, and the next save writes `Hamnen` to
  `reel.yaml`, which loads

#### Scenario: Renaming a chapter
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator presses "Edit title card for Kvällen"
- **THEN** a dialog opens on "This title card" with keyboard focus in the Name field, named "Name of chapter Kvällen" and holding
  `Kvällen`; the header bar behind it shows `Kvällen` as plain text with no pencil
- **WHEN** the operator selects the name, types ` Kväll på stranden `, with spaces around it, and presses Done
- **THEN** the dialog is closed, keyboard focus is on that chapter's Edit Titlecard button, the heading reads `Kväll på stranden`, the rename was announced once, and the save bar says that 1
  chapter was renamed. The chapter offers no Rename button and its name is not pressable.

#### Scenario: Renaming with the keyboard only
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator tabs to "Edit title card for Kvällen", presses Enter, types `Kväll`
  in the Name field and presses Escape
- **THEN** the chapter is named `Kväll` (an accepted name is already in the draft), the dialog is closed, keyboard focus is on the
  Edit Titlecard button, and the next Tab reaches the chapter's Move up

#### Scenario: Main and a chapter are edited alike
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator opens "Edit title card for Main" and then "Edit title card for Kvällen"
- **THEN** each opens the same dialog on "This title card" with the Name field first; Main's is named "Title of the event" and holds
  `Två kapitel`, Kvällen's "Name of chapter Kvällen"; neither header bar has a pencil, a card row, a "Main title card" line or a
  "from the folder name" line

#### Scenario: Leaving the field keeps an accepted name
- **WHEN** the operator opens the dialog of `Kvällen`, types `Kväll` in the Name field, and presses Tab
- **THEN** the chapter is named `Kväll`, keyboard focus is on the control after the field and not back in it, the dialog stays open, and the rename is announced once

#### Scenario: Escape drops what was typed
- **WHEN** the operator opens the dialog of `Kvällen`, types `main` in the Name field, and presses Escape
- **THEN** the dialog is closed, keyboard focus is on the chapter's Edit Titlecard button, the chapter is named `Kvällen`, "Name not changed" with the reason is announced, and the page shows no unsaved changes

#### Scenario: Pressing the title and changing nothing
- **WHEN** the operator types `Kväll` in the Name field of `Kvällen` and then `Kvällen`, with spaces around it, and closes the dialog
- **THEN** the chapter is named `Kvällen`, nothing is announced or counted as an edit, and the page shows no unsaved changes

#### Scenario: A refused rename keeps the field open
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator types `main` in the Name field of `Kvällen`
- **THEN** the field stays as typed, is marked invalid and explains under it that `Main` is how the page names the event's own chapter; the
  refusal is announced, and the draft still holds `Kvällen`. Typing `Morgon` removes the refusal and the chapter is named `Morgon`.
- **WHEN** the operator types `main` again and presses Done
- **THEN** the dialog stays open and keyboard focus is in the field
- **WHEN** the operator presses Escape
- **THEN** the dialog closes, the chapter is named `Morgon`, the last name accepted, and "Name not changed" with the reason is announced

#### Scenario: A refused name is not lost when focus leaves
- **WHEN** the operator types `main` in that field and presses Tab
- **THEN** the field stays as typed with its refusal, keyboard focus is on the control after it, and the chapter is still named `Kvällen`

#### Scenario: An empty name, and a name already taken
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, after adding a chapter `Morgon`, the operator opens its dialog, deletes the name,
  and then types `KVÄLLEN`
- **THEN** the first is refused because a chapter needs a name, and the second because a chapter called `Kvällen` exists, each in
  the words Add chapter's dialog uses for the same name

#### Scenario: One field at a time
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, after adding a chapter `Morgon`, the operator renames `Kvällen` to `Kväll` in its dialog, presses Done, and opens "Edit title card for Morgon"
- **THEN** only the dialog of `Morgon` is open, `Kvällen`'s header bar reads `Kväll`, and the save bar counts the one rename

#### Scenario: A name typed and not kept holds Save
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator changes the title in the Details form, opens the dialog of `Kvällen`,
  types `main` and presses Ctrl+S
- **THEN** nothing is saved and "Not saved: the name is refused." is announced. After the operator types `Kväll`, closes the dialog and presses
  Ctrl+S, one save is sent and carries both edits.

#### Scenario: Reset closes the field
- **WHEN** the operator renames `Kvällen` to `Kväll` in its dialog, closes it, and presses Reset
- **THEN** the header bar reads `Kvällen`, the page shows no unsaved changes, and "Edit title card for Kvällen" opens a dialog whose Name field holds `Kvällen`

#### Scenario: The event's own chapter keeps no name
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn`
- **THEN** `Main` has no chapter rename and says that it has no name of its own because its title card shows the event's title; its
  header bar shows `Main`, an Edit Titlecard button and no other title control

#### Scenario: Renaming the main title card edits the event's title
- **WHEN** Edit mode opens on `2024-06-27 - Grillning med grannar`, in which one chapter is listed, and the operator opens "Edit title
  card for Clips" and types `Grillkväll med grannarna` in the field named "Title of the event"
- **THEN** the Details form's Title field holds the same, the dialog's preview shows it, the save bar says "Title" changed, and the
  dialog says that saving changes the movie's file name and names no file. The chapter is still headed `Clips`.
- **WHEN** the operator closes the dialog and types `Grillkväll` in the Details form's Title field and reopens the dialog
- **THEN** the Name field holds `Grillkväll`
- **WHEN** the operator saves
- **THEN** one `PUT` is sent whose metadata title is `Grillkväll` and whose chapters and clips are as read, and the dialog no longer says anything about
  the file name

#### Scenario: Emptying the main title card
- **WHEN** the operator deletes the text of the Name field of `2024-06-27 - Grillning med grannar`, which reads `Grillning med grannar` from `reel.yaml`
- **THEN** the field says "Left empty: inherits from the folder name when saved", shows the title resolved from the folder name as its
  placeholder with "From the folder name", and the Details form's Title field is empty with the same hint

#### Scenario: The main title card with no title at all
- **WHEN** the page has no title for the event, in `reel.yaml` or resolved from the folder name
- **THEN** the field is empty with the placeholder "Untitled"

#### Scenario: Moving a chapter up
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator presses Move up on `Kvällen`
- **THEN** `Kvällen` is listed first and `Main` second. Keyboard focus is still on `Kvällen`'s Move up, which
  now says that it is unavailable. The move is announced as chapter 1 of 2, and the save bar says that the
  chapter order changed.

#### Scenario: A chapter that plays clips cannot be deleted
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator presses Delete on `Kvällen`
- **THEN** nothing is deleted, and keyboard focus stays on Delete. The page shows and announces that `Kvällen`
  still plays 3 clips, which must first be moved to another chapter.

#### Scenario: Deleting an emptied chapter, and undoing it
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator moves all three clips of `Kvällen` to `Main` and
  presses Delete on `Kvällen`
- **THEN** `Kvällen` is listed in its place as deleted when the edits are saved, with an Undo control that has
  keyboard focus. The save bar says that 3 clips moved and that 1 chapter is deleted.
- **WHEN** the operator then presses that Undo
- **THEN** `Kvällen` is listed again, playing no clip. Keyboard focus is on its Delete, and the save bar no
  longer counts a deleted chapter.

#### Scenario: Main stays while it lists an ignored clip
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator moves `s1710001.mp4` to `Kvällen` and presses
  Delete on `Main`
- **THEN** nothing is deleted, and the page says that `Main` still lists 1 ignored clip that no other chapter
  will take

#### Scenario: Saving a deleted chapter
- **WHEN** after deleting the emptied `Kvällen` of `2024-08-20 - Två kapitel - Tjörn`, the operator saves
- **THEN** `reel.yaml` names one chapter, the event's own, listing `s1710001.mp4`, `Kvällen/s1710002.mp4`,
  `Kvällen/s1710003.mp4` and `Kvällen/s1710004.mp4`, and still ignores `s1710004.mp4`. The page then shows that
  one chapter, headed `Clips`.

#### Scenario: Reset restores the chapters
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator renames `Kvällen`, adds a chapter `Morgon`, moves
  `Kvällen` up, and presses Reset
- **THEN** the chapters are `Main` and `Kvällen` as read, in that order, and the page shows no unsaved changes

#### Scenario: A chapter edit is an unsaved edit
- **WHEN** the operator renames `Kvällen` on `2024-08-20 - Två kapitel - Tjörn` and presses the browser's Back
- **THEN** the event page stays, with the rename, and asks "Discard unsaved changes?"

#### Scenario: The last chapter stays
- **WHEN** on `2024-06-27 - Grillning med grannar`, the operator adds a chapter `Kvällen vid grillen`, moves all
  four clips of `Main` to it, and deletes `Main`
- **THEN** `Kvällen vid grillen` has a Name field in its dialog, but no Delete, Move up or Move down, and the save bar
  says that 4 clips moved, 1 chapter was added and 1 chapter deleted

#### Scenario: Chapter controls on a phone
- **WHEN** the operator opens Edit mode on `2024-08-20 - Två kapitel - Tjörn` on a touch screen 320 pixels wide
- **THEN** a tap anywhere in a 44 × 44 pixel area around each of `Kvällen`'s Edit Titlecard, Move up, Move down and Delete, and
  around `Main`'s Edit Titlecard and Add chapter, reaches that control and no other (centred on each, except
  that the areas of Move up and Move down meet at the edge they share, as a clip row's move pair's do), and
  the page does not scroll horizontally

#### Scenario: Chapter controls wait for a save
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, with a rename pending, the operator presses Save, and the
  service has not answered yet
- **THEN** Add chapter and every chapter's Edit Titlecard, Move up, Move down and Delete say that they are unavailable, and
  pressing them changes nothing and opens nothing

#### Scenario: A lone empty chapter does not point at Move clips
- **WHEN** Edit mode opens on `2024-10-05 - Tom mapp`, an event whose folder holds no clip, and the operator
  presses Add chapter, types `Kvällen vid grillen` and confirms
- **THEN** the new chapter, the only one listed, counts 0 clips, and it says "No clips. A chapter without
  clips is left out of the movie." It does not mention dragging clips or Move marked to…, and the page offers no Move marked to…

#### Scenario: A lone chapter whose only clip is ignored
- **WHEN** Edit mode opens on `2024-10-06 - Bara ignorerad`, an event that lists one chapter, whose only clip
  `s1710004.mp4` is ignored
- **THEN** the chapter lists the ignored clip under its heading and says "It plays no clip. A chapter without
  clips is left out of the movie." It does not mention dragging clips or Move marked to…

#### Scenario: A second chapter brings the hint back
- **WHEN** on `2024-10-05 - Tom mapp`, with `Kvällen vid grillen` added, the operator presses Add chapter,
  types `Morgonen` and confirms
- **THEN** both chapters say that they have no clips and that clips can be dragged into them or moved into
  them with Move marked to…
- **WHEN** the operator then deletes `Morgonen`
- **THEN** `Kvällen vid grillen` says again, as it did before the addition, that it has no clips and is left
  out of the movie, without mentioning dragging or Move marked to…

### Requirement: Edit mode says what a chapter's name means for clips added later

A clip that appears in an event's folder after its `reel.yaml` exists joins, at the next render, the chapter
named after the folder it is in (by case folding, as below), or the event's own chapter when no chapter has
that name. So a
chapter's name decides where clips added to that folder later go. Edit mode SHALL say so wherever an edit
changes that. It SHALL say it under the Name field of the title card dialog and in the Add chapter dialog, as the name is typed, and
beside the chapter after the edit,
until the edits are saved or undone:

- **Renaming or deleting a chapter whose name was the name of a folder of the event that holds clips.** No
  chapter is then named after that folder, so clips added to it later join the event's own chapter.
- **Adding a chapter named after such a folder, or renaming one to that name.** Clips added to that folder
  later join this chapter, and clips from it that other chapters list now stay where they are. The folder's
  ignored clips will be listed under this chapter.
- **Renaming or deleting a chapter that lists ignored clips.** They will be listed under the event's own
  chapter, because the page lists an ignored clip under the chapter named after its folder, or under the
  event's own chapter when none is.
- **Deleting the event's own chapter.** Clips added to the event folder later start a new `Main` chapter at
  the end, and so do the ignored clips of a chapter renamed or deleted in the same edits.

In these words the page SHALL name the event's own chapter by its heading at that moment: `Main` while
another chapter is listed, `Clips` when it is the only one.

A folder counts only while it holds a clip on disk. The page SHALL compare a name with a folder's by full
Unicode case folding, as the engine does: a chapter takes the clips of every folder whose name folds to its
own. A name that differs from a folder's only in case therefore attracts that folder's clips, and a chapter
renamed between two spellings of a folder's name keeps them. The page SHALL say what the edit changes, in the
folder's own spelling, and nothing when it changes nothing.

#### Scenario: Renaming a chapter named after its folder
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator opens "Edit title card for Kvällen" and types `Kväll` in the Name field
- **THEN** the text under the field says that no chapter will be named after the folder `Kvällen`, so clips added to it later will
  join `Main`. After the dialog is closed, the chapter `Kväll` says the same beside it.

#### Scenario: Dropping a rename says nothing
- **WHEN** after typing `Kväll` as above, the operator types `Kvällen` again
- **THEN** the text under the field is gone, and the chapter `Kvällen` says nothing about later clips

#### Scenario: A name that differs from the folder's only in case
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator renames `Kvällen` to `kvällen`
- **THEN** the rename is accepted, and the page says nothing about later clips, since the folder `Kvällen`
  still joins this chapter

#### Scenario: A new chapter whose name differs from a folder's only in case
- **WHEN** after renaming `Kvällen` to `Kväll` on `2024-08-20 - Två kapitel - Tjörn`, the operator adds a
  chapter and types `KVÄLLEN`
- **THEN** the dialog says that clips added to the folder `Kvällen` later will join this chapter

#### Scenario: A new chapter named after a folder
- **WHEN** after renaming `Kvällen` to `Kväll` on `2024-08-20 - Två kapitel - Tjörn`, the operator adds a
  chapter and types `Kvällen`
- **THEN** the dialog says that clips added to the folder `Kvällen` later will join this chapter, and that
  the clips from it listed in other chapters stay where they are

#### Scenario: Deleting a chapter named after its folder
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator moves the three clips of `Kvällen` to `Main` and
  deletes `Kvällen`
- **THEN** the deleted chapter says that clips added to the folder `Kvällen` later will join `Clips`, as the
  page now heads the event's own chapter, the only one left

#### Scenario: Renaming a chapter that lists an ignored clip
- **WHEN** the `reel.yaml` of `2024-08-20 - Två kapitel - Tjörn` also ignores `Kvällen/s1710004.mp4`, and the
  operator renames `Kvällen` to `Kväll`
- **THEN** the text under the field and then the chapter say that its 1 ignored clip will be listed under `Main`. After
  saving, the page lists `Kvällen/s1710004.mp4` as ignored under the event's own chapter, and `Kväll` lists
  `Kvällen/s1710002.mp4` and `Kvällen/s1710003.mp4`.

#### Scenario: Deleting a chapter that lists an ignored clip
- **WHEN** the `reel.yaml` of `2024-08-20 - Två kapitel - Tjörn` also ignores `Kvällen/s1710004.mp4`, and the
  operator moves the two clips `Kvällen` plays to `Main` and deletes `Kvällen`
- **THEN** the deleted chapter says that its 1 ignored clip will be listed under `Clips`, the event's own
  chapter's heading once it is the only one. After saving, the page lists `Kvällen/s1710004.mp4` as ignored under the event's own chapter.

### Requirement: A selected title card opens its inspector in Edit mode
Activating a title card in Edit mode, from its block on the Timeline (a press, Enter or Space) or from the **Edit Titlecard** button in its chapter's header bar, SHALL open that card's inspector in a modal dialog, over the page wherever the operator has scrolled to, named "Title card
for <chapter>" (the opening card: "Opening title card"). There SHALL be one card editor and one place for it, for the opening card and every chapter's alike: the inspector SHALL NOT
also be rendered in the page below the Timeline's track. The app's existing dialog component (`ui/Dialog`, the native `<dialog>`
with `showModal()`) SHALL be reused. The dialog SHALL hold the tabs, the Name and the card fields that "The title card dialog holds every name and every title-card setting" lists, and one live preview; the preview SHALL sit above the fields where the dialog is 600 CSS pixels
wide or narrower and beside them where it is wider. Opening it SHALL NOT scroll the page, SHALL NOT move the track, the ruler,
the playhead or the Timeline's video, and the page behind it SHALL NOT scroll while it is open. Focus SHALL move to the dialog's first
field when it opens and SHALL return to the button or block that opened it when it closes, unless the operator has already moved it to
a control outside the dialog. Escape and a Close button SHALL close it, as SHALL a "Done" button; none of them SHALL discard an
edit. Edits SHALL go into the page's one draft, as every other Edit-mode change does: the dialog has no Save or Cancel of its
own, and the save bar counts a changed card ("1 title card changed") while the dialog is open and after it is closed. The card's selection highlight, on its block and on its chapter's button, SHALL stay while the dialog is open and after it closes. Activating
a card that is already selected SHALL open the dialog again. At 600 CSS pixels wide or narrower the dialog SHALL be a full-screen
sheet. The dialog's Length field and the Timeline's length drag SHALL be two ways to edit the one draft `duration`. Every
control SHALL have a visible label and an accessible name, work with the keyboard alone, and be at least 44 × 44 CSS pixels where
the primary pointer is coarse. The dialog SHALL fit from 320 to 1280 CSS pixels wide without a horizontal page scroll, follow the
colour scheme, and add no motion when the operator prefers reduced motion. In the read view nothing changes: selecting a card
there opens no dialog and writes nothing.

#### Scenario: Opening from a row far down the page
- **WHEN** the page is scrolled to a chapter far below the Timeline and the operator presses that chapter's "Edit title card for <chapter>"
- **THEN** the dialog opens named "Title card for <chapter>" on "This title card" with focus in its Name field, the page has not
  scrolled, and the chapter's button and its block show as selected

#### Scenario: Selecting a card opens it
- **WHEN** the operator presses the title card block of the chapter `Reception` on the Timeline
- **THEN** the dialog opens named "Title card for Reception", the block and the chapter's Edit Titlecard button show as selected, and the keyboard reaches
  every field in reading order

#### Scenario: Editing and finishing
- **WHEN** the operator changes the title, sees the preview update, and presses Done
- **THEN** the dialog is closed, focus is back on the button that opened it, the save bar shows the change
  ("1 title card changed"), and Save writes `reel.yaml`

#### Scenario: Escape closes and keeps the edit
- **WHEN** the operator has typed a title and presses Escape
- **THEN** the dialog closes, focus returns to the button or block that opened it, the draft holds the edit, and the card stays selected

#### Scenario: Reopening the selected card
- **WHEN** the dialog has been closed and the operator presses the still-selected card again
- **THEN** the dialog opens again with the draft's values

#### Scenario: A narrow window
- **WHEN** the window is 390 CSS pixels wide, and again 320, and a card is open
- **THEN** the dialog is a full-screen sheet with the preview above the fields, nothing scrolls horizontally, and the page behind
  it does not scroll

#### Scenario: Selecting never moves the track
- **WHEN** a card is opened from its block and from its chapter's button, at 1280 and 390 px
- **THEN** the track's bounding box is the same before and after each and no inspector is in the page below it

#### Scenario: Switching and closing
- **WHEN** the dialog is open and the operator closes it, then presses another card
- **THEN** the other card's dialog opens, and the draft holds every edit made on both

### Requirement: Edit mode edits the event's card style in one place

The title card dialog's second tab, **All title cards in this event**, SHALL edit the event-wide title-card style, the `look.title_card` of
`reel.yaml`, and it is the only place that does: the page SHALL NOT hold a "Card style for this event" section or any other control for it. It SHALL offer these
fields: font family, title size, subtitle size, text color, position (center, top or bottom), default length, and default background (Black or
Video), each with a **Use project default** button. The font family SHALL be chosen from the families the service lists (`GET /api/v1/fonts`), each shown
in its own face or with the service's preview image, never typed. A field the style leaves unset SHALL say that
it follows the project default, with the value in force when the page read it as a placeholder; when the
operator clears a value that the saved style set, the field SHALL say "Project default" without a number,
because the page does not know it, and SHALL NOT show a value it does not have. Every field SHALL be reachable
and operable with the keyboard, and have a label, and a tap area of at least 44 by 44 pixels while the
primary pointer is coarse. The tab SHALL be disabled with Edit mode's other edit controls while a save is in flight.

The dialog's one live preview, drawn by the service from the draft (not the saved) style and the card being edited, SHALL show an
event-style edit at once, under the same rules as the card preview: debounced, a stale request cancelled, the previous image kept while the next
loads, and a failure told in words. When the service cannot resolve the saved event style (the event detail's `title_card_error`), the dialog SHALL open on this tab
showing that error in words and the stored values as typed, so the operator can correct them.

#### Scenario: Setting a font and a colour for every card
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn` in Edit mode, the operator opens "Edit title card for Main", chooses the tab "All title cards in this event",
  picks the font `DM Serif Display` and sets the text color `#FFD700`
- **THEN** the preview shows the opening card in that face and color before anything is saved, and the save
  bar says the card style changed

#### Scenario: An unset field follows the project default
- **WHEN** the event's `reel.yaml` sets no `look.title_card` and the operator opens the tab
- **THEN** each field shows the project default value as a placeholder and none shows as set

#### Scenario: Use project default clears a field
- **WHEN** the saved style sets a title size of 80 and the operator presses Use project default on it
- **THEN** the field says "Project default" and the save bar counts the change

#### Scenario: A cleared value does not invent a default
- **WHEN** the saved style sets a title size of 80 and the operator clears the field
- **THEN** the field says "Project default" with no number, the preview shows the card without the size, and
  the save bar counts the change

#### Scenario: A style the engine refuses is told and correctable
- **WHEN** the event's `look.title_card.position` is hand-written as `middle` and the operator opens a title card dialog
- **THEN** the dialog opens on "All title cards in this event" showing the service's refusal naming `position` and `middle` in the field, and
  choosing `center` clears the refusal

#### Scenario: The control is usable at a narrow width
- **WHEN** the window is 320 pixels wide and the operator opens the tab
- **THEN** every field is fully visible without horizontal page scroll

### Requirement: Edit mode switches the event's title cards On or Off

The title card dialog's second tab, "All title cards in this event", SHALL hold, once for the event, a control named "Title cards" with the choices On and Off, and the page SHALL NOT hold a Title cards section of its own. The control SHALL be showing the
state a render would have: the draft's choice, else the event detail's `title_cards.enabled`, with the words that say
where that came from ("Default", "Set in this event", "Set by the project's config.yaml"). Choosing Off SHALL make
the draft's `look.decorators` the event's own list without `title`, keeping the other names and their order, and the
empty list when the event has none; choosing On SHALL make it a list with `title` first and the other names kept. The
choice SHALL be an edit of the same draft as every other: counted in the save bar ("Title cards turned off", "Title
cards turned on"), undone by Undo and Reset, and no change when put back to the state read. A save SHALL write the
document as read with only `look.decorators` (and `look.title_card`, by its own rule) changed and every other key of
`look` as read, and SHALL NOT remove the key unless the draft is back to the state read. Turning cards Off SHALL
keep every card's edits in the draft. When the source is `project`, the control SHALL say that saving writes this
event's own list over the project's. When `title_cards` is null (`look.decorators` is not a list), the control SHALL
be disabled and show the service's `title_cards_error`. The control SHALL be disabled with the other edit controls while
a save is in flight, operable by keyboard, labelled, at least 44 by 44 CSS pixels where the primary pointer is coarse,
legible in both colour schemes from 320 to 1280 px wide without horizontal scroll, and SHALL make the Timeline, the dialog's preview and the movie's length follow the choice before any save. While cards are Off the dialog SHALL say "Title cards are off for this event" above its tabs and keep every card field editable.

#### Scenario: Turning cards off
- **WHEN** on an event with no `look.decorators` the operator chooses Off and saves
- **THEN** one `PUT` under `If-Match` writes `look.decorators: []` and nothing else changes, and the next read says `title_cards: {enabled: false, source: "event"}`

#### Scenario: Other decorators are kept
- **WHEN** the event's `look.decorators` is `[chapter, title]`, the operator chooses Off, and saves
- **THEN** the written list is `[chapter]`

#### Scenario: Back to the state read is no change
- **WHEN** the operator chooses Off and then On on an event that read `source: "default"`
- **THEN** the save bar shows no change and `look` goes back exactly as read

#### Scenario: Turning cards back on
- **WHEN** the event read `look.decorators: []`, the operator chooses On and saves
- **THEN** the written list is `[title]`

#### Scenario: Card edits survive Off
- **WHEN** the operator changes a card's subtitle, chooses Off, and then On
- **THEN** the subtitle edit is still in the draft

#### Scenario: A list that is not a list
- **WHEN** the detail has `title_cards: null` and `title_cards_error` naming `look.decorators`
- **THEN** the control is disabled and shows that text

### Requirement: A card says which fields it overrides and falls back to the event style

Each title card in Edit mode SHALL say in its dialog, above its fields, which of its fields it overrides: the names of the fields its draft sets ("Overrides font, color"), or "Uses the event
style" when it sets none. A field a card sets equal to the event style SHALL still count as an override. The
inspector's "Use event style" on a field SHALL remove that card's override of it, so the field then follows
the draft event style, not only the saved one, and the dialog's field and the card's preview SHALL show
the result without a save. A card's override of a field SHALL win over the event style, which SHALL win over
the project default.

#### Scenario: A card names its overrides
- **WHEN** the chapter `Kvällen` sets only `font_family` and `text_color` on its card
- **THEN** its dialog says "Overrides font, color" and the opening card's dialog says "Uses the event style"

#### Scenario: Use event style follows the draft style
- **WHEN** the event style's text color is edited to `#00FF00` and not saved, and the operator presses "Use event
  style" on the text color of `Kvällen`'s card
- **THEN** the inspector shows `#00FF00` as that card's color and its preview is drawn in it, and the card no
  longer lists color among its overrides

#### Scenario: A card's override beats a changed event style
- **WHEN** `Kvällen`'s card overrides the font and the operator changes the event style's font
- **THEN** `Kvällen`'s preview keeps its own font and every card without that override shows the new one

### Requirement: A choice that follows an inherited value shows it pressed in a muted style

Every segmented choice of the card dialog's "This title card" tab (Background, Position) and of the dialog's "All title cards in this event" tab (Default background, Position) that has no value of its own SHALL show the value it inherits as pressed, in a muted style
distinct from a chosen value and not by colour alone (a dashed outline), with the words "(event style)" for a
card's field and "(project default)" for the event style's, and SHALL expose it to assistive technology as the
inherited value, not as chosen. Pressing the inherited option SHALL set the field to that value as an override;
**Use event style** SHALL return it to the muted state. While the inherited value is unknown (`card: null`, or a
saved value the operator cleared) no option SHALL be shown pressed and the words SHALL say it is unknown.

#### Scenario: A card that follows the event style
- **WHEN** the event style's background is Video and a card sets none
- **THEN** Video is shown pressed in the muted style with "(event style)", Black is not, and the draft holds no background for the card

#### Scenario: Pressing the inherited option
- **WHEN** the operator presses the muted Video
- **THEN** the card sets Video as its own override (it is listed among its overrides) and the style is the chosen look

#### Scenario: The event style's own control
- **WHEN** the event's `look.title_card` sets no position and the project default is Center
- **THEN** the tab's Position shows Center muted with "(project default)"

#### Scenario: Unknown inherited value
- **WHEN** the operator cleared a saved size and the background of a card with `card: null`
- **THEN** no option is shown pressed and the words say the inherited value is unknown

### Requirement: The opening card's subtitle shows its default and can be set to none
The dialog's Subtitle field for the opening card SHALL, while the draft's subtitle is unset, show the resolved
card's `default_subtitle` as its placeholder with the words "Default" (lines joined by " / ", for example
`Default: 2024-08-20 / Plats: Tjörn`), and when that is empty `No subtitle`. The page SHALL NOT compose the default. The
field SHALL offer **No subtitle**, which sets the subtitle to the empty string, and **Use default**, which unsets it
(the key is removed on Save); the field SHALL keep the empty string and unset apart in the draft, in the dirty state
and in what Save and the preview send, so an explicit `""` is written as `""` and an unset subtitle is not written. A
subtitle typed into the field SHALL replace the default. For a chapter other than the opening one the field keeps its
"Event style: no subtitle" behaviour and offers neither button, since it has no default. The Timeline's card readout SHALL show the effective subtitle (`card.subtitle` of the detail, or the draft's
value when edited) and "No subtitle" only when it is empty. This requirement takes precedence over the sentence "The
subtitle SHALL be free text of any length that keeps its line breaks" only in adding the default; that sentence still holds.

#### Scenario: The default is the placeholder
- **WHEN** the opening card is selected for an event dated 2024-08-20 at `Tjörn` with no subtitle key
- **THEN** the Subtitle field is empty with the placeholder `Default: 2024-08-20 / Plats: Tjörn`, and **Use default** is not offered

#### Scenario: No subtitle writes the empty string
- **WHEN** the operator presses **No subtitle** and Saves
- **THEN** the request carries `subtitle: ""` for the default chapter, the field shows the placeholder `No subtitle` with **Use default** offered, and the Timeline's card readout says "No subtitle"

#### Scenario: Use default removes the key
- **WHEN** the card's saved subtitle is `""` and the operator presses **Use default** and Saves
- **THEN** the request carries no subtitle for that card, and the Timeline's card readout shows the date and place again

#### Scenario: Typing replaces the default
- **WHEN** the operator types `Hos mormor`
- **THEN** the preview and the Timeline's card readout show `Hos mormor` and no date or place

#### Scenario: A chapter card has no default controls
- **WHEN** a chapter other than the opening one is selected
- **THEN** the Subtitle field shows its existing placeholder and neither **No subtitle** nor **Use default** is offered

#### Scenario: The preview sends the empty string
- **WHEN** the draft's subtitle is `""`
- **THEN** the preview request carries `subtitle: ""`, and the image has no subtitle line

### Requirement: Edit mode moves the marked clips to a chapter

While the event lists more than one chapter, a deleted one aside, the line above the chapters that offers Clear marks
and Rotate marked left and right ("Edit mode marks clips to move together") SHALL also offer **Move marked to…**: a
group named by those words, holding a chapter picker and a button named **Move**. No chapter SHALL offer a Move clips
button, and the page SHALL NOT open a dialog to pick clips: the clips to move are the ones marked, and the page SHALL
NOT have a Pick all or a Pick marked control. When the event lists one chapter, the control SHALL NOT be offered, as no
other chapter has a place for a clip.

The picker SHALL be a native `select` named "Chapter to move the marked clips to". It SHALL list every chapter the
page lists, a deleted one aside, in the order the page lists them, each by the name its heading shows (the event's own
chapter as `Main`, as its heading reads), and it SHALL start on a first option that is no chapter, "Choose a chapter".
A chosen chapter that is then deleted SHALL return the picker to that option. Renaming a chapter SHALL change its name
in the list.

**Move** SHALL be `aria-disabled` (never `disabled`, as the busy-control rule says) and SHALL give its reason in words, named by `aria-describedby` and shown in the toolbar's one hint line ("The marks line is one aligned unit"), in each of these states, and press nothing:

- no clip is marked: "Mark a clip to move it."
- no chapter is chosen: "Choose a chapter."
- a save is in flight, or a move of marked clips is pending: "Unavailable while saving."

Pressing Move with a clip marked and a chapter chosen SHALL be one edit, made by the group move of "Dragging a marked
clip moves the whole marked group" and not by logic of its own: the group is every marked clip, from every listed
chapter, in page order; it SHALL leave the chapters it was in and SHALL join the end of the chosen chapter as one run, in
page order. A marked clip that is already in the chosen chapter joins that run too, so the run is the last clips of the
chapter. Every clip that is not marked SHALL keep its order and its chapter. A chapter that loses all its clips SHALL
play none. A clip SHALL NOT be put back after its old predecessors when it returns to the chapter it was in when Edit
mode opened: a move to the end is the same edit as a drop at the end of that chapter.

After the move:

- every moved clip SHALL be unmarked (the group is every marked clip, so no mark is left)
- the move SHALL be announced once, politely, with the number of clips and the chosen chapter's name, "3 clips moved to
  “Dag 2”." or "1 clip moved to “Main”."
- each moved clip that changed chapter SHALL show, in its row, the chapter it came from instead of its old position,
  and SHALL count once as a moved clip in its new chapter's heading and in the save bar, as a clip dragged does; within
  a chapter, the page SHALL count the fewest clips that explain the new order
- a clip SHALL keep its cuts and its other per-clip properties, its Cuts panel shown or hidden as it was, any time
  typed but not added, and its preview open as "Edit mode previews a clip on request" says
- Save SHALL write the order as it writes a drag's, and Reset, the unsaved-changes question, a conflict and Overwrite
  SHALL treat the move as any other edit
- keyboard focus SHALL stay on Move, the chosen chapter SHALL stay chosen, and no row SHALL be scrolled out of the
  operator's view by the move

A move that changes no chapter's order (the marked clips already are the last of the chosen chapter, in page order)
SHALL leave the draft, the marks and the save bar as they are and SHALL be announced as "Nothing moved." A clip that
has no mark (a missing clip, an ignored clip, a removed one) is never moved by this control, as it is never marked.

Move marked to… SHALL stay beside dragging. A drag of a marked clip takes the marked group to the place where it is
dropped (see "Dragging a marked clip moves the whole marked group"), from the keyboard on a handle too; Move marked
to… takes the same group, always to the end of one chosen chapter, with a keyboard, a screen reader or a touch screen
and with no drag at all. A clip's Move up and Move down still never take it into another chapter (see "The event page
reorders clips within a chapter").

On a coarse pointer the picker and Move SHALL each take a tap anywhere in an area at least 44 CSS pixels tall that does
not overlap another control's. The group SHALL wrap in a window 320 CSS pixels wide, on its own row under the marks line's other controls, its label above the picker and the picker beside Move, without a horizontal page scroll, in both color schemes. The group SHALL keep its place and its
height whether or not a clip is marked, so that marking the first clip moves no row, and its focus ring SHALL be
visible in both color schemes and in forced colors. Reading a screen SHALL NOT change what is chosen.

#### Scenario: Moving two marked clips from different chapters to Test
- **WHEN** in Edit mode on an event whose chapters are `Main`, `Kvällen` and `Test`, the operator marks `Main/a.mp4`
  and `Kvällen/c.mp4`, chooses `Test` in the picker and presses Move
- **THEN**
  - `Test` plays what it played before and then `a.mp4` and `c.mp4`, last, in that page order
  - neither clip is marked and the line above the chapters shows no count
  - "2 clips moved to “Test”." was announced once
  - the save bar says that 2 clips moved
  - the picker still shows `Test`, and keyboard focus is on Move
- **WHEN** the operator presses Save
- **THEN** `reel.yaml` lists `a.mp4` and `c.mp4` last in `Test`'s clips and nothing else changed

#### Scenario: Move says why it is unavailable
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn`, with no clip marked
- **THEN** Move is `aria-disabled` and not `disabled`, and the words "Mark a clip to move it." are beside it and are its
  description
- **WHEN** the operator marks `Kvällen/s1710002.mp4`
- **THEN** its reason reads "Choose a chapter."
- **WHEN** the operator chooses `Main` and presses Move
- **THEN** `s1710002.mp4` is last in `Main`, marked as coming from `Kvällen`, unmarked, and "1 clip moved to “Main”." is
  announced

#### Scenario: Moving with the keyboard only
- **WHEN** using only the keyboard on `2024-08-20 - Två kapitel - Tjörn`, the operator marks `Kvällen/s1710002.mp4` with
  Space, tabs to the picker, chooses `Main` with the arrow keys, tabs to Move and presses Enter
- **THEN** `s1710002.mp4` is last in `Main`, "1 clip moved to “Main”." was announced, and keyboard focus is on Move

#### Scenario: The marked clips already are last
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator moves `Kvällen/s1710002.mp4` to `Main` and marks it
  again, chooses `Main` and presses Move
- **THEN** "Nothing moved." is announced, the clip is still marked, and the save bar counts what it counted before

#### Scenario: One chapter offers no move
- **WHEN** Edit mode opens on `2024-06-27 - Grillning med grannar`, whose clips are all in one chapter
- **THEN** the line above the chapters offers no Move marked to…, and no chapter offers a Move clips button

#### Scenario: The old per-chapter control is gone
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn`, in Chrome and in Firefox
- **THEN** the words "Move clips" appear nowhere on the page, in any chapter's controls, dialogs or accessible names

#### Scenario: Move waits for a save
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, with a clip marked and a chapter chosen, the operator presses Save
  and the service has not answered yet, and then presses Move
- **THEN** Move is `aria-disabled` and says "Unavailable while saving.", and nothing moves

#### Scenario: A deleted chapter leaves the picker
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator chooses `Kvällen` in the picker and then deletes `Kvällen`
- **THEN** the picker lists `Main` only and shows "Choose a chapter"

#### Scenario: The control fits a phone
- **WHEN** on a touch screen 320 pixels wide, in the light and in the dark scheme, on
  `2024-08-20 - Två kapitel - Tjörn`, the operator looks at the line above the chapters
- **THEN** the picker and Move are on a line of their own, each takes a tap in an area at least 44 pixels tall, none
  overlaps another, and the page does not scroll horizontally
