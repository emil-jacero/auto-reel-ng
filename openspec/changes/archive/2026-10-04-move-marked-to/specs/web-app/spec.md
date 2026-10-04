## ADDED Requirements

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

**Move** SHALL be `aria-disabled` (never `disabled`, as the busy-control rule says) and SHALL give its reason in words,
named by `aria-describedby` and visible beside it, in each of these states, and press nothing:

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
not overlap another control's. The group SHALL wrap in a window 320 CSS pixels wide, on its own line under the marks
line's other controls, without a horizontal page scroll, in both color schemes. The group SHALL keep its place and its
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

## MODIFIED Requirements

### Requirement: The event page reorders clips within a chapter

An event's page SHALL offer an **Edit** mode on the page itself. Entering or leaving it SHALL NOT change the
page's address. Entering Edit mode SHALL read the event's editorial document from the service. When that read
fails, the page SHALL say why, using the same words it uses for a failed event read, and SHALL offer no
editing. Entering Edit mode SHALL keep keyboard focus on the control that entered it, and leaving Edit mode,
by any path, SHALL move keyboard focus to the page's level-one heading.

While in Edit mode, the editor's chapter lists and metadata fields SHALL take the place of the chapter tables,
the facts and the description. Each chapter keeps its level-two heading, and each clip row keeps the facts the
table shows: its position, the clip's name as the event page's table names it, its status in words, size and
modification time, with absent facts shown as absent. The event's verdict and latest job stay shown. Leaving
Edit mode, by any path, SHALL read the event again and show the tables. Only the operator's own actions SHALL
end Edit mode or change what it holds: a read of the event that the page would start by itself while Edit mode
is open SHALL NOT discard the edits.

In Edit mode, each chapter SHALL list its clips in the order the page shows them. The operator SHALL be able
to move a clip to any other position **within its own chapter** in each of three ways:

- by dragging the clip's handle with a mouse, pen or touch. A drag SHALL start only from the handle, and a
  tap or click on the handle SHALL NOT start one. A scroll gesture that starts anywhere else on the page
  SHALL scroll it.
- from the keyboard, on the clip's handle: one key lifts the clip, the arrow keys move it, one key drops it,
  and Escape cancels, leaving the order as it was
- with a **Move up** and a **Move down** control on every movable row. After such a move, keyboard focus SHALL
  stay on the moved clip's row.

Every keyboard or control move, and every drop or cancel, SHALL be announced to assistive technology with the
clip's name, as the event page's table names it, and its position out of the number of clips the chapter plays
(its ignored clips, and the missing clips the operator removed, are not counted). Move up and Move down SHALL
NOT take a clip into another chapter. A clip changes chapter only when it is dragged into another chapter (see
"Edit mode drags clips between chapters") or moved with Move marked to… (see "Edit mode moves the marked clips to a chapter"). A missing clip's drag SHALL stop at its own chapter's edge. Among the clips
a chapter held when Edit mode opened and still holds, the page SHALL count as moved the fewest clips whose
moves explain the new order, so that moving one clip from position 1 to position 5 moves one clip, not five.
Each such clip counted as moved SHALL show its position from when Edit mode opened. A clip moved in from
another chapter SHALL count as one moved clip, and SHALL show the chapter it came from instead.

Clips the event ignores are not part of the play order. Each chapter SHALL list them after its other clips,
marked as ignored, and they SHALL NOT be movable or counted in the chapter's positions. A missing clip SHALL
stay listed and movable, and SHALL never be dropped from its chapter, except when the operator removes it
with its own control (see "Edit mode removes a missing clip from reel.yaml on request"). A NEW clip SHALL be
movable like any other.

#### Scenario: Dragging a clip to the front
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar`, the operator drags `s1710004.mp4` above
  `s1710001.mp4`
- **THEN** the chapter lists `s1710004.mp4`, `s1710001.mp4`, `s1710002.mp4`, `s1710003.mp4`, and
  `s1710004.mp4` shows that it was at position 4

#### Scenario: Reordering from the keyboard
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator focuses the handle of `Kvällen/s1710002.mp4`,
  lifts it, presses Down once, and drops it
- **THEN** `Kvällen` lists `s1710003.mp4`, `s1710002.mp4`, `s1710004.mp4`, and a screen reader hears that
  `s1710002.mp4` moved to position 2 of 3

#### Scenario: Escape cancels a keyboard move
- **WHEN** on `2024-06-27 - Grillning med grannar`, the operator lifts `s1710001.mp4` from the keyboard, moves
  it two places, and presses Escape
- **THEN** the clip is back at position 1, the order is unchanged, and the cancel is announced

#### Scenario: The move controls keep focus on the moved clip
- **WHEN** on `2024-09-01 - Sommarlov`, the operator activates **Move down** on `s1710002.mp4`
- **THEN** `s1710002.mp4` is at position 2, keyboard focus is still on its row, and its move is announced

#### Scenario: A clip cannot leave its chapter
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator activates **Move up** on `Kvällen/s1710002.mp4`,
  the first clip of `Kvällen`
- **THEN** the control says that it is unavailable, nothing moves, and `Main` is unchanged: only a drag or Move marked to… takes a clip into another chapter

#### Scenario: A missing clip cannot leave its chapter
- **WHEN** on `2024-09-01 - Sommarlov`, after adding a chapter `Morgon`, the operator drags `borttagen.mp4`
  downward toward `Morgon`, past the bottom of `Main`, and releases it
- **THEN** the dragged clip stopped at the bottom edge of `Main`, `borttagen.mp4` is still at position 3 of
  `Main`, and `Morgon` plays no clip

#### Scenario: An ignored clip is listed but cannot move
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn`
- **THEN** `Main` lists `s1710001.mp4` and then `s1710004.mp4`, marked as ignored, and `s1710004.mp4` has no
  handle and no move controls

#### Scenario: A missing clip keeps its place
- **WHEN** Edit mode opens on `2024-09-01 - Sommarlov`, whose `reel.yaml` lists the missing `borttagen.mp4`
  last
- **THEN** `borttagen.mp4` is listed at position 3, marked as missing, and can be moved like the others

#### Scenario: A large chapter is fully editable
- **WHEN** an event holds 400 clips in one chapter
- **THEN** all 400 are listed in Edit mode, and any of them can be moved to any position in the chapter

#### Scenario: The editorial document cannot be read
- **WHEN** the operator enters Edit mode on an event whose `reel.yaml` became unparseable after the page was
  read
- **THEN** the page shows the unparseable-document failure in words, with the service's detail, and offers
  no editing

### Requirement: Edit mode names clips and the saved event as the other screens do

Edit mode SHALL name each clip by the rule the event page's table uses, applied to the chapter's current name
and to every clip the chapter lists now or listed when Edit mode opened. A chapter names a clip by its file
name while every one of those clips lies in the folder named like the chapter's current name (the event
folder, for the event's own chapter). Otherwise it names the clip by its path inside the event folder. So a
clip moved in and a new name take the names the table will give once saved, while a clip moved out or
removed renames nothing until the edits are saved. The same name SHALL be used in
these places:

- the clip's row
- the names of its controls: its handle, its move controls, and its remove or undo control
- what Edit mode announces about the clip

Moving a clip within its chapter, or removing one, SHALL NOT change how its chapter names its clips. Two edits
can change it. A clip from another folder moved into a chapter makes the chapter name its clips by their
paths, and so does a new name that is no longer its folder's.

When a save succeeds, the notification that confirms it SHALL name the event by the title the save left it
with, followed by that date when it is known, since titles repeat. When the title is not known to the page,
the notification SHALL name the event by its folder name. The page SHALL NOT guess a title or a date that the
service resolves from the folder name.

#### Scenario: A chapter that lists a clip from another folder
- **WHEN** the `reel.yaml` of `2024-08-20 - Två kapitel - Tjörn` lists `Kvällen/s1710004.mp4` in its default
  chapter after `s1710001.mp4`, and the operator opens Edit mode
- **THEN** `Main` names its clips `s1710001.mp4` and `Kvällen/s1710004.mp4`, and its ignored clip
  `s1710004.mp4`, as the page's table named them, and the handle of the second is named
  "Reorder Kvällen/s1710004.mp4"

#### Scenario: The saved event is named by its title and date
- **WHEN** the operator changes the location of `2024-06-27 - Grillning med grannar` in Edit mode and saves
- **THEN** the notification says the event was saved, and names it "Grillkväll med grannarna" with its date
  2024-06-27

#### Scenario: A clip moved in from another folder is named by its path
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator moves `s1710002.mp4` from `Kvällen` to `Main`
- **THEN** `Main` names its clips `s1710001.mp4` and `Kvällen/s1710002.mp4`, and its ignored clip
  `s1710004.mp4`, and the second's Move up is named "Move Kvällen/s1710002.mp4 up"

#### Scenario: A renamed chapter names its clips by their paths
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator renames `Kvällen` to `Kväll`
- **THEN** `Kväll` names its clips `Kvällen/s1710002.mp4`, `Kvällen/s1710003.mp4` and `Kvällen/s1710004.mp4`, as
  the event page's table names them once the rename is saved

### Requirement: Edit mode adds, renames, reorders and deletes chapters

In Edit mode the operator SHALL be able to change the event's chapters themselves. Every control below SHALL
be reachable with the keyboard and SHALL name, to assistive technology, the chapter it acts on.

- **Add chapter**, after the last chapter, SHALL ask for a name and add an empty chapter with that name at the
  end.
- **Rename** SHALL start at the chapter's title. Edit mode SHALL show each chapter's title as a button
  with a pencil icon that is visible without hover or focus, and there SHALL be no separate Rename button
  or dialog. Pressing the title (with a pointer, or Enter or Space on it) SHALL turn it into a text field that
  holds the chapter's name, selected. The event's own chapter (the default chapter, whose clips are the event
  folder's) has no name to rename. Its title card shows the event's title, and clips without a chapter of
  their own join it. While the event lists other chapters, the page SHALL say this beside it. Its title card
  is edited as "The event's own chapter is the main title card" below says.
- **Move up** and **Move down** SHALL move a chapter one place among the chapters, and SHALL be offered only
  while the event lists more than one chapter. After such a move, keyboard focus SHALL stay on the pressed
  control. At either end, the control that cannot move further SHALL say that it is unavailable.
- **Delete** SHALL remove a chapter only once it plays no clip. Its clips must first be moved to another
  chapter, or removed when missing. The event's own chapter can be deleted only when, in addition, it lists no
  ignored clip that the page would list under it again after the save: one from the event folder, or from a
  folder no chapter is named after. Such a clip would bring the chapter back, holding only ignored clips.
  When a chapter cannot be deleted, pressing Delete SHALL change nothing and leave focus on Delete. The page
  SHALL show and announce why the chapter cannot be deleted.

Each chapter SHALL offer only the controls that apply to it. An event that lists one chapter, the event's own,
offers Add chapter and none of the others. The only chapter left, a deleted one aside, SHALL NOT offer Delete,
Move up or Move down, so that an event never saves without a chapter.

**The name field.** The field SHALL be named "Name of chapter <name>" to assistive technology. Before it is
pressed, the title SHALL be named by the chapter's name alone, so that the chapter's heading, region and
controls are named as before, and that pressing it renames SHALL be its description.

- Enter, not during an input-method composition, SHALL keep the name. So SHALL moving keyboard focus out of
  the field. Escape SHALL drop what was typed. After Enter or Escape, keyboard focus SHALL be on the title
  again; after focus moves out of the field it stays where the operator put it.
- A name equal to the chapter's current name, once the spaces around it are removed, SHALL close the field and
  change nothing, and nothing is announced.
- A refused name SHALL be explained under the field and announced. The field stays open and keeps its text.
  On Enter it keeps keyboard focus; when focus has already left the field, the field does not take it back.
- At most one name field SHALL be open. Pressing another title closes the open field: an accepted name typed
  in it is kept, as when focus leaves it, and a refused one is dropped.
- Opening and closing the field SHALL NOT change the height of the chapter's heading row, nor move the
  chapter's controls or clips, except that a refusal, and the notes of "Edit mode says what a chapter's name
  means for clips added later", appear under the field while it is open.
- Reset, a save starting, and the unsaved-changes question SHALL close an open field without keeping what was
  typed. While a save or a move of marked clips is pending, the title SHALL say that it is unavailable and SHALL NOT
  open the field (the busy-control rule).
- A field that holds a name typed and not kept SHALL count as unfinished, as a date typed in part and a cut
  typed and not added do: Save is unavailable, Ctrl+S saves nothing and says that a name is typed and not
  kept, and leaving Edit mode asks first. Pressing Save with a pointer first moves focus out of the field,
  which keeps an accepted name before the press lands.

**The event's own chapter is the main title card.** Whatever the number of chapters, the event's own chapter
SHALL show, under its heading and before its notes and controls, a line labelled "Main title card" that holds
the event's title as a button of the same kind as a chapter's title. The chapter keeps its name, `Main` or
`Clips`, in its heading, in its controls' names, in announcements and in the chapter list of Move marked to….

- The title shown SHALL be the title in the editor's draft when it is not blank, else the title the page
  resolved from the folder name, marked as from the folder name, else the word "Untitled". The page SHALL NOT
  guess a title.
- Pressing it SHALL open the same field on the draft's title, the one the metadata form's Title field edits.
  A title kept there appears in the Title field, a title typed in the Title field appears on the line, and
  Reset, the changed mark and the save bar's "Title" treat them as one edit. Enter and Escape, leaving the
  field, the one open field, the unfinished rule and the busy rule are the name field's.
- Any text SHALL be kept as the title, with no rule of the page's. A blank title means that it inherits from
  the folder name, and the field SHALL say so in the words of the metadata form ("Left empty: inherits from
  the folder name when saved"). The service's refusal of an unusable title stays at the metadata form and is
  retired by editing the title in either place.
- While the draft's title differs from the title read, the line SHALL say that saving changes the movie's
  file name, that if the movie was already rendered the next render saves it under the new name, and that the
  movie under its old name stays on disk. It SHALL NOT name a file: the event page names them after the
  save, from the verdict.

When the browser's primary pointer is coarse, each of these controls, the chapter titles, the main title card's title, Add chapter and Undo SHALL take a tap
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
with Enter or in the Add chapter dialog, and nothing SHALL change. The
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
- **WHEN** Edit mode opens on `2024-06-27 - Grillning med grannar`
- **THEN** its one chapter offers no chapter rename, Move up, Move down or Delete (its main title
  card line edits the event's title), and the page offers Add chapter after it

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
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator presses the title `Kvällen`
- **THEN** the title becomes a text field named "Name of chapter Kvällen", with `Kvällen` selected and keyboard
  focus in it, and the chapter's heading row is no taller, and its controls and clips no lower, than before
  (within 1 pixel)
- **WHEN** the operator types ` Kväll på stranden `, with spaces around it, and presses Enter
- **THEN** the heading reads `Kväll på stranden`, keyboard focus is on that title, the rename is announced,
  and the save bar says that 1 chapter was renamed. The chapter offers no Rename button.

#### Scenario: Renaming with the keyboard only
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator tabs to the title `Kvällen`, presses Space,
  types `Kväll`, and presses Enter
- **THEN** the chapter is named `Kväll`, keyboard focus is on its title, and the next Tab reaches the chapter's
  Move up

#### Scenario: Leaving the field keeps an accepted name
- **WHEN** the operator opens the field on `Kvällen`, types `Kväll`, and presses Tab
- **THEN** the chapter is named `Kväll`, keyboard focus is on the control after the title and not on the
  title, and the rename is announced

#### Scenario: Escape drops what was typed
- **WHEN** the operator opens the field on `Kvällen`, types `Kväll`, and presses Escape
- **THEN** the title reads `Kvällen`, keyboard focus is on it, nothing is announced, and the page shows no
  unsaved changes

#### Scenario: Pressing the title and changing nothing
- **WHEN** the operator opens the field on `Kvällen` and presses Enter without typing, and again types
  `Kvällen` with spaces around it and presses Enter
- **THEN** each time the field closes, keyboard focus is on the title, and nothing is announced or counted as
  an edit

#### Scenario: A refused rename keeps the field open
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator opens the field on `Kvällen`, types `main` and
  presses Enter
- **THEN** the field stays open with `main`, keeps keyboard focus, and explains under it that `Main` is how the
  page names the event's own chapter. The refusal is announced, the field is marked invalid, and no chapter
  changes. Typing `Morgon` removes the refusal.

#### Scenario: A refused name is not lost when focus leaves
- **WHEN** the operator types `main` in that field and presses Tab
- **THEN** the field stays open with its refusal, keyboard focus is on the control after it, and the chapter
  is still named `Kvällen`

#### Scenario: An empty name, and a name already taken
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, after adding a chapter `Morgon`, the operator opens the
  field on `Morgon`, presses Enter with the name deleted, and then types `KVÄLLEN` and presses Enter
- **THEN** the first is refused because a chapter needs a name, and the second because a chapter called
  `Kvällen` exists, each in the words Add chapter's dialog uses for the same name

#### Scenario: One field at a time
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, after adding a chapter `Morgon`, the operator opens the
  field on `Kvällen`, types `Kväll`, and presses the title `Morgon`
- **THEN** `Kvällen` is renamed `Kväll`, and only the field on `Morgon` is open
- **WHEN** the operator types `main` in `Morgon`'s field and presses the title `Kväll`
- **THEN** `Morgon` keeps its name, `Morgon`'s field is closed, and only the field on `Kväll` is open

#### Scenario: A name typed and not kept holds Save
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator changes the title in the metadata form, opens
  the field on `Kvällen`, types `Kväll`, and presses Ctrl+S
- **THEN** nothing is saved, "Not saved: a name is typed and not kept." is announced, and Save says that it is
  unavailable. After the operator presses Enter and then Ctrl+S, one save is sent and carries both edits.

#### Scenario: Reset closes the field
- **WHEN** the operator opens the field on `Kvällen`, types `Kväll`, and presses Reset
- **THEN** no field is open, the title reads `Kvällen`, and the page shows no unsaved changes

#### Scenario: The event's own chapter keeps no name
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn`
- **THEN** `Main` has no chapter rename and says that it has no name of its own because its title card shows the
  event's title. Under `Main`'s heading, a line "Main title card" shows the title `Två kapitel` as a button
  with a pencil icon, and `Kvällen` has its own title button in its heading.

#### Scenario: Renaming the main title card edits the event's title
- **WHEN** Edit mode opens on `2024-06-27 - Grillning med grannar`, in which one chapter is listed, and the
  operator presses the title on the "Main title card" line, types `Grillkväll med grannarna`, and presses
  Enter
- **THEN** the line shows `Grillkväll med grannarna`, the metadata form's Title field holds the same, keyboard
  focus is on the line's title, and the save bar says "Title" changed. The chapter is still headed `Clips`.
  The line says that saving changes the movie's file name, and names no file.
- **WHEN** the operator then types `Grillkväll` in the metadata form's Title field
- **THEN** the line shows `Grillkväll`
- **WHEN** the operator saves
- **THEN** one `PUT` is sent whose metadata title is `Grillkväll` and whose chapters and clips are as read,
  and the line no longer says anything about the file name

#### Scenario: Emptying the main title card
- **WHEN** the operator opens the field on the main title card of `2024-06-27 - Grillning med grannar`, which
  reads `Grillning med grannar` from `reel.yaml`, deletes the text, and presses Enter
- **THEN** the field, while it was open, said "Left empty: inherits from the folder name when saved". The line
  now shows the title resolved from the folder name, marked as from the folder name, and the Title field is
  empty with the same hint.

#### Scenario: The main title card with no title at all
- **WHEN** the page has no title for the event, in `reel.yaml` or resolved from the folder name
- **THEN** the line shows "Untitled" in muted type, and pressing it opens an empty field

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
- **THEN** `Kvällen vid grillen` has a title that can be renamed, but no Delete, Move up or Move down, and the save bar
  says that 4 clips moved, 1 chapter was added and 1 chapter deleted

#### Scenario: Chapter controls on a phone
- **WHEN** the operator opens Edit mode on `2024-08-20 - Två kapitel - Tjörn` on a touch screen 320 pixels wide
- **THEN** a tap anywhere in a 44 × 44 pixel area around each of `Kvällen`'s title, Move up,
  Move down and Delete, and around `Main`'s main title card title and Add chapter, reaches that control and
  no other (centred on each, except
  that the areas of Move up and Move down meet at the edge they share, as a clip row's move pair's do), and
  the page does not scroll horizontally

#### Scenario: Chapter controls wait for a save
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, with a rename pending, the operator presses Save, and the
  service has not answered yet
- **THEN** Add chapter and every chapter's title, Move up, Move down and Delete, and the main
  title card's title, say that they are unavailable, and pressing them changes nothing and opens no field

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

### Requirement: Edit mode lists, adds and removes a clip's cuts

A clip's cuts are the spans of it that the movie leaves out. Each has a start and an end, in seconds from the
clip's start, and may have a reason. In Edit mode, every included or new clip that `reel.yaml` does not exclude (a clip on disk that a chapter
lists, or will list once the edits are saved) SHALL offer a **Cuts** control. The control SHALL say how many
cuts the clip has and, when it has any, how much time they cut out. Pressing it SHALL show or hide a panel
under the clip's row and SHALL leave keyboard focus on the control. The control SHALL say to assistive
technology whether the panel is shown, and SHALL name the clip as its row names it. In the keyboard order, the
Cuts control SHALL come after the row's other controls, and the panel's controls straight after it.

The panel SHALL list the clip's cuts in their order, each with its number in the list, its start and end, its
length and its reason in words. A clip without cuts SHALL say that the whole clip plays. A missing clip that
`reel.yaml` does not exclude SHALL show, in its row, how many cuts it has, and SHALL offer no Cuts control: its file is not on disk to cut, and
removing it from `reel.yaml` takes its cuts with it. Once the operator removes it, its row SHALL NOT show its
cuts any more, since the save drops them. An ignored clip SHALL have no cuts and no Cuts control.
An excluded clip is not in the movie, so its cuts do not apply: its row SHALL show no cuts and SHALL offer no
Cuts control, whether the clip is on disk or missing. Its cuts stay in `reel.yaml`, and a save SHALL write
them back unchanged.

**Times.** A cut's times are places in the clip, not moments in a day, so the format for moments ("Times are
written one way on every screen") does not apply to them. The page SHALL write a time as minutes and seconds
(`1:02.35`), with hours in front from one hour on (`1:01:15.5`). It SHALL write up to three decimals and no
trailing zero. It SHALL write a length under a minute in seconds (`1.5 s`), and from a minute on as a time. The time a clip's cuts cut out SHALL count, once,
every span that one or more of its cuts covers, as the render does.

**Adding a cut.** The panel SHALL take a start and an end, typed, and add the cut on request. Spaces around a
time SHALL be ignored. A time SHALL be accepted in each of these forms, with an optional decimal part of one
to three digits after `.` or `,`:

- seconds (`75.5`)
- minutes and seconds, the seconds as two digits below 60 (`1:15.5`)
- hours, minutes and seconds, the minutes and seconds each as two digits below 60 (`1:01:15.5`)

The cut SHALL be refused, and nothing added, when either time is empty or in no accepted form, or has more
than three decimals. It SHALL also be refused when its end is not after its start, when it shares more
than an instant with another cut of the clip that is not removed, or when it ends after the clip's length
once the page knows that length (below). A refusal SHALL be shown at the field it concerns, which SHALL
receive keyboard focus. It SHALL be announced, and it SHALL say what to type, which cut the new one overlaps,
or the clip's length. A cut that only touches another, the end of one being the start of the other, SHALL
be accepted. Times SHALL be compared to the millisecond, as they are typed and written, so a cut that starts
where another is shown to end touches it.

An added cut SHALL take its place in the list by its start, after every cut that starts at the same time or
earlier. It SHALL be saved with the reason `manual`. After an addition:

- both fields SHALL be empty again, with keyboard focus on the start field
- the addition SHALL be announced with the cut's times, the clip's name and its new cut count

**The clip's length.** The page knows a clip's length from one of two places, and the first it has wins: the
length the clip's preview has read from the clip's file in this Edit mode ("Edit mode previews a clip on
request"), else the duration the event detail gives the clip when it is not null (a thumbnail of the clip was
made before). The preview's length wins because it is the one Set From and Set To write times from, so a cut
set at the end of the clip is never refused. A null duration is unknown, never zero. When the page knows the
length from neither, the panel SHALL say that the page does not know the clip's length, that a cut that runs
past the clip's end stops there, and that a cut over the whole clip leaves the clip out of the movie, and it
SHALL NOT refuse a cut for its length. Once the page knows the length, from either place, the panel SHALL
state it beside its fields, SHALL refuse a cut that ends after it, and SHALL mark each listed cut that ends
after it ("A clip's preview sets cut times at the playhead and plays the clip as the movie will"), and
it SHALL still say that a cut over the whole clip leaves the clip out of the movie. The
duration of a clip the event detail gives SHALL NOT be sent anywhere, and neither length SHALL be saved.

**What a whole-clip cut does to a title card.** Wherever the panel says that a cut over the whole clip leaves
the clip out of the movie, it SHALL add that when the clip is its chapter's title clip, the chapter's title card
moves to the next clip of the chapter that plays. The render places a chapter's title card before the first
clip it plays when the title clip is cut away, and adds none to a chapter in which every clip is cut away. The
page does not know which clip is a chapter's title clip, so the sentence is conditional and the same for every
clip.

**Removing a cut.** Each cut SHALL offer **Remove**, which names the clip and the cut. A cut read from
`reel.yaml` SHALL then stay listed in its place, marked as removed when the edits are saved, with an **Undo**
that puts it back. Keyboard focus SHALL move to that Undo, and after an Undo to the cut's Remove. An Undo that
would make the cut share more than an instant with a cut added in this Edit mode SHALL be refused, as adding
that cut would be: the cut stays removed, keyboard focus stays on its Undo, and the refusal is shown in the
cut's row, announced, and names the cut to remove first. Two cuts read from `reel.yaml` that overlap there
SHALL NOT refuse each other's Undo: an Undo only goes back to what was read. A cut added in this Edit mode SHALL simply be gone.
Keyboard focus SHALL then move to the Remove of the cut that took its place, or of the cut before it, or to
the start field when no cut is left. Each removal and each Undo SHALL be
announced. After any addition, removal or Undo, the control holding keyboard focus SHALL be fully visible,
not covered by the page header, the chapter's heading or the save bar.

**Typed but not added.** While a panel's fields hold a typed time that was not added, the event SHALL count as
having unsaved changes. The save bar SHALL say that a cut was typed but not added, naming the clip as its row
names it when only one clip holds one, also after an edit that changes that name. Save, and Overwrite with mine after a conflict, SHALL say that they are unavailable until
the cut is added or its fields are cleared. Hiding the panel SHALL keep what was typed, and so SHALL moving the
clip to another chapter. The Cuts control of each clip whose panel holds such a time SHALL say so in words, at
every width and to assistive technology, also while its panel is hidden, so that the clip holding Save back
is found on its row. Reset SHALL empty every panel's fields.

While a save is in flight, the panel's fields, Add cut, Remove and Undo SHALL say that they are unavailable
and change nothing when used. The Cuts control SHALL still show and hide its panel, since that changes nothing
to save.

The Cuts control and every control in the panel SHALL take a tap anywhere in an area of at least 44 × 44 CSS
pixels around it when the primary pointer is coarse, reaching no other control, as every button does ("Every
control is large enough to touch"). With every panel hidden, the Cuts control SHALL NOT make a row taller in a
window 320 or 390 pixels wide. No panel SHALL make the page scroll horizontally from 320 pixels up.

#### Scenario: Opening a clip's cuts
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar`, the operator presses the Cuts control of
  `s1710001.mp4`
- **THEN** a panel under its row says that the whole clip plays and offers a start and an end field and Add
  cut. Keyboard focus is still on the Cuts control, which says that its panel is shown.

#### Scenario: Adding a cut with typed times
- **WHEN** in that panel the operator types `0` as the start and `1,5` as the end and presses Enter
- **THEN**
  - the panel lists one cut, from `0:00` to `0:01.5`, 1.5 s long, its reason "Cut by hand"
  - the Cuts control reads "1 cut · −1.5 s"
  - both fields are empty, with keyboard focus on the start field
  - the addition is announced
  - the save bar says that 1 cut was added

#### Scenario: Every accepted form of a time
- **WHEN** on `s1710002.mp4` of `2024-06-27 - Grillning med grannar`, the operator adds a cut from ` 0:00:01.25 `
  to `0:02.5`, and then one from `4` to `0:06`
- **THEN** the panel lists the cuts from `0:01.25` to `0:02.5` and from `0:04` to `0:06`, in that order, and the
  Cuts control reads "2 cuts · −3.25 s"

#### Scenario: A time the page cannot read
- **WHEN** on `s1710002.mp4` of `2024-06-27 - Grillning med grannar`, the operator types `1:5` as the start and
  `2` as the end and asks to add the cut, then types `-1` as the start, then `0.1234`
- **THEN** each is refused at the start field, which keeps keyboard focus. The first two are refused as no time
  the page can read, naming the three forms. The last is refused for its four decimals. No cut is added.

#### Scenario: A cut that does not end after it starts
- **WHEN** on `s1710002.mp4` of `2024-06-27 - Grillning med grannar`, the operator types `3` as the start and
  `2` as the end and asks to add the cut
- **THEN** the cut is refused at the end field, which receives keyboard focus, saying that a cut must end after
  it starts, and no cut is added

#### Scenario: A clip never previewed is not checked for length
- **WHEN** on `s1710002.mp4` of `2024-06-27 - Grillning med grannar`, whose detail gives a duration of `null`
  and whose preview was not opened in this Edit mode, the operator adds a cut from `5` to `7`
- **THEN** the cut is accepted and listed, and the panel says that the page does not know the clip's length and
  that a cut that runs past the clip's end stops there

#### Scenario: A clip whose duration the service gives is checked before any preview
- **WHEN** on `s1710001.mp4` of `2024-06-27 - Grillning med grannar`, whose detail gives a duration of `6.02`
  and whose preview was not opened in this Edit mode, the operator adds a cut from `5` to `7`
- **THEN** the panel says that the clip ends at `0:06.02`, the cut is refused at the end field, which receives
  keyboard focus, saying that `0:07` is after the clip's end at `0:06.02`, and no cut is added
- **WHEN** the operator types `0:06.02` as the end and adds the cut
- **THEN** the cut from `0:05` to `0:06.02` is listed

#### Scenario: The panel says where a whole-clip cut sends the title card
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar`, the operator opens the Cuts panel of
  `s1710001.mp4`, the first clip of its chapter, before and after opening its preview
- **THEN** both times the panel says that a cut over the whole clip leaves the clip out of the movie and that,
  when it is the chapter's title clip, the chapter's title card moves to the next clip of the chapter that plays

#### Scenario: A cut that overlaps another
- **WHEN** `s1710001.mp4` of `2024-06-27 - Grillning med grannar` has a cut from `0:00` to `0:01.5`, and the
  operator adds one from `1` to `2`
- **THEN** it is refused, saying that it overlaps cut 1 (`0:00` to `0:01.5`)
- **WHEN** the operator then adds one from `1.5` to `2`
- **THEN** it is accepted and listed second

#### Scenario: Removing a cut read from reel.yaml, and undoing it
- **WHEN** the `reel.yaml` of `2024-06-27 - Grillning med grannar` gives `s1710003.mp4` a cut from 0 to 1.2
  seconds with the reason `black`, and in Edit mode the operator presses that cut's Remove
- **THEN** the cut stays listed, marked as removed when the edits are saved, with an Undo that has keyboard
  focus, and the save bar says that 1 cut is removed
- **WHEN** the operator presses that Undo
- **THEN** the cut is listed as before, its reason "Black frames", keyboard focus is on its Remove, and the page
  shows no unsaved changes

#### Scenario: An Undo that would overlap is refused
- **WHEN** with that same `reel.yaml`, the operator removes the cut from 0 to 1.2 seconds of `s1710003.mp4`, adds
  one from `1` to `2`, and presses the removed cut's Undo
- **THEN** the Undo is refused, saying that cut 1 overlaps cut 2 (`0:01` to `0:02`) and that cut 2 must be
  removed first. Cut 1 stays removed, keyboard focus stays on its Undo, and the save bar still says that 1 cut
  was added and 1 removed.

#### Scenario: Read cuts that overlap do not refuse each other's Undo
- **WHEN** the `reel.yaml` of `2024-06-27 - Grillning med grannar` gives `s1710002.mp4` cuts from 0 to 3 seconds
  and from 2 to 4 seconds, and the operator removes both and presses each one's Undo
- **THEN** both are listed as before, and the page shows no unsaved changes

#### Scenario: A cut starts where another is shown to end
- **WHEN** the `reel.yaml` of `2024-06-27 - Grillning med grannar` gives `s1710003.mp4` a cut from 0 to 3.2033333
  seconds, listed as ending at `0:03.203`, and the operator adds one from `3.203` to `4`
- **THEN** it is accepted and listed second

#### Scenario: Removing a cut added in this Edit mode
- **WHEN** on `s1710001.mp4` of `2024-06-27 - Grillning med grannar`, the operator adds a cut from `0` to `1.5`
  and presses its Remove
- **THEN** the panel says that the whole clip plays again, keyboard focus is on the start field, and the page
  shows no unsaved changes

#### Scenario: A missing clip's cuts are shown, not edited
- **WHEN** the `reel.yaml` of `2024-09-01 - Sommarlov` gives the missing `borttagen.mp4` a cut from 0 to 2
  seconds, and the operator opens Edit mode
- **THEN** the row of `borttagen.mp4` says that it has 1 cut and offers Remove but no Cuts control, while
  `s1710002.mp4` and `s1710004.mp4` offer theirs
- **WHEN** the operator presses Remove on `borttagen.mp4`
- **THEN** its row is listed as removed when the edits are saved and no longer says that it has a cut

#### Scenario: An excluded clip offers no cuts
- **WHEN** the operator enters Edit mode on an event whose `reel.yaml` excludes `s1710002.mp4`, which is on
  disk and has a cut from `0` to `1.5`
- **THEN** its row offers no Cuts control and shows no cut count, the other clips of the chapter still offer
  theirs, and saving another edit writes the cut back unchanged

#### Scenario: An ignored clip has no cuts
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn`
- **THEN** the ignored `s1710004.mp4` offers no Cuts control, and every clip `Main` and `Kvällen` play offers one,
  the new `Kvällen/s1710004.mp4` included

#### Scenario: A cut typed but not added holds Save back
- **WHEN** on `s1710001.mp4` of `2024-06-27 - Grillning med grannar`, the operator types `2` as the start, adds
  nothing, and hides the panel
- **THEN** the save bar says that a cut was typed on `s1710001.mp4` but not added, and Save says that it is
  unavailable. Opening the panel again shows `2` in the start field.
- **WHEN** the operator then presses the browser's Back
- **THEN** the page stays and asks "Discard unsaved changes?"

#### Scenario: A typed cut moves with its clip
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator types `2` as the start of a cut on
  `Kvällen/s1710002.mp4`, which `Kvällen` names `s1710002.mp4`, adds nothing, and marks that clip and moves it to
  `Main` with Move marked to…
- **THEN** the save bar now says that a cut was typed on `Kvällen/s1710002.mp4` but not added, Save says that
  it is unavailable, and the clip's Cuts panel, now in `Main`, is still shown with `2` in the start field

#### Scenario: Hidden panels holding typed text are marked on their rows
- **WHEN** on `2024-06-27 - Grillning med grannar`, the operator types `5` in the start field of `s1710002.mp4`
  and hides its panel, then types `1:00` in the start field of `s1710004.mp4` and hides that panel
- **THEN** the save bar says that cuts were typed on 2 clips but not added, and the Cuts controls of those two
  clips, and of no other, say "typed" and that a cut was typed but not added
- **WHEN** the operator clears the field of `s1710002.mp4`
- **THEN** its Cuts control no longer says so, and the save bar names `s1710004.mp4`

#### Scenario: Cut controls wait for a save
- **WHEN** on `2024-06-27 - Grillning med grannar`, with a cut added to `s1710001.mp4` and its panel shown, the
  operator presses Save and the service has not answered yet
- **THEN** the start and end fields, Add cut and the cut's Remove say that they are unavailable, typing and
  pressing them change nothing, and the Cuts control still hides and shows the panel

#### Scenario: Cuts on a phone
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn` on a touch screen 320 pixels wide
- **THEN** each clip row is as tall as on the page before this change, and a tap anywhere in a 44 × 44 pixel area
  around the Cuts control of `Kvällen/s1710002.mp4` reaches that control and no other
- **WHEN** the operator opens that panel and adds a cut from `0` to `1`
- **THEN** the page does not scroll horizontally, and a tap anywhere in a 44 × 44 pixel area around each of the
  panel's fields, Add cut and the cut's Remove reaches that control and no other

### Requirement: Edit mode drags clips between chapters

While the event lists more than one chapter, a deleted one aside, the operator SHALL be able to drag a clip
on disk (active or new) that a chapter plays into any other listed chapter. The operator SHALL be able to
drop it there before any clip that chapter plays, or after the last of them. Both ways a clip is dragged
within its chapter SHALL do this:

- **with a mouse, pen or touch**, from the clip's handle. While the dragged clip is held near the window's
  top or bottom edge, the page SHALL scroll by itself, so that a chapter out of view can be reached. The
    speed SHALL grow with how far into the edge the pointer is, from nothing at the inner edge of the
    scrolling zone, and with the pointer at the window's very edge it SHALL be at least 600 and at most 2,000
    CSS pixels per second, however many rows the page holds.
- **from the keyboard**, on the clip's handle:
  - Down at a chapter's last position SHALL take the clip to the first position of the next listed chapter.
  - Up at a chapter's first position SHALL take it to after the last clip of the chapter before.
  - A deleted chapter's placeholder SHALL be passed over.
  - Page Down SHALL take the clip to the first position of the next listed chapter, and Page Up to the first
    position of the chapter before, wherever the clip is held. A chapter the clip does not play is entered at
    its first gap, before its first clip, and an empty one at its area. At the last chapter (Page Down) or the
    first (Page Up), and for a missing clip, which stays in its chapter, and while one chapter is listed, the
    key SHALL move nothing. When it moves the clip, the place the clip is then over (the line, or the empty
    chapter's area) and the dragged copy SHALL both be in the window, however far the page had to scroll to
    get there. A Page Down or Page Up pressed while a clip is lifted SHALL NOT otherwise scroll the page, whether
    or not it moved the clip.
  - Escape SHALL cancel and leave every chapter as it was, with the clip's handle in view again (its whole
    row, or its first line when the row is taller than the room left).

A chapter that plays no clip SHALL show, in Edit mode, an area for clips. While the event lists another
chapter, a deleted one aside, the area SHALL say that clips can be dragged into it. When the chapter is the
only one listed, the area SHALL say only what "Edit mode adds, renames, reorders and deletes chapters" states
for it, because no other chapter has a clip to drag. The area SHALL be shown whether or not a drag is under
way. A clip dropped on it SHALL become the chapter's first clip.

While a clip is dragged over another chapter:

- the page SHALL show where a drop puts it: a line at the place between two of that chapter's clips or after
  its last clip, or, for a chapter that plays no clip, its area marked as the target
- a copy of the clip SHALL follow the pointer and SHALL name the target chapter and the position that the drop
  gives the clip
- that chapter's clips SHALL NOT move to make room, and no part of the page SHALL change size or place;
  within the clip's own chapter, its other clips still make room, as before
- the clip's own row SHALL stay in its chapter, marked as the clip being moved, until it is dropped
- while the clip is held by a pointer, no other part of the page SHALL show that the pointer is over it,
  and the pointer SHALL show that it holds the clip
- in forced colors, the line and the copy's edge SHALL stay visible

Within its own chapter, a clip SHALL stay at its place while the pointer is over its own row, however tall
the row is: lifting a clip and releasing it there moves nothing.

A drop into another chapter SHALL be one edit. The clip leaves its chapter and joins the other one at the
position where it was dropped. Every other clip keeps its order. Then:

- its row SHALL show the chapter it came from, and it SHALL count once as a moved clip, in its new chapter's
  heading and in the save bar, as a clip moved with Move marked to… does
- a clip dragged back to the chapter and the position it had when Edit mode opened SHALL count as no move;
  with no other edit, the page SHALL show no unsaved changes
- it SHALL keep its cuts and its other per-clip properties. Its Cuts control SHALL be as it was, and its
  panel stays shown or hidden as it was and keeps any time typed but not added
- Save SHALL write it as it writes a clip moved with Move marked to… ("Saving an edit writes only what the operator
  changed"). Reset, the unsaved-changes question, a conflict and Overwrite SHALL treat it as any other edit

Every target in another chapter SHALL be announced to assistive technology, and so SHALL a drop and a
cancel. The announcement names the clip as its row named it when it was lifted. A target or a drop in another
chapter SHALL name that chapter, and SHALL give the position out of the number of clips that chapter would
then play. Within the clip's own chapter the announcements SHALL stay as "The event page reorders clips
within a chapter" states. While more than one chapter is listed, the instructions for a keyboard drag SHALL
say that the arrows cross into the chapter before or after, and that Page Down and Page Up jump to the next
or the previous chapter.

After a drop into another chapter, by pointer or keyboard, keyboard focus SHALL be on the moved clip's
handle in its new chapter. The handle and the row's first line (its handle, name and Cuts control) SHALL be
fully visible, not covered by the page header, the chapter's heading or the save bar. A row taller than that
space SHALL be scrolled so that its first line is (see "Edit mode keeps keyboard focus in view and never
drops it").

Some clips cannot be marked ("Edit mode marks clips to move together"), so Move marked to… never moves them,
and those SHALL NOT be taken into another chapter by a drag either:

- a missing clip: its drag SHALL stop at its own chapter's edge, from the keyboard too. While more than one
  chapter is listed, its lift SHALL say that it stays in its chapter.
- an ignored clip, and a missing clip the operator removed: neither has a handle

A release over a deleted chapter's placeholder SHALL move nothing and SHALL be announced as a drop that
changed nothing. While a save is in flight, or while a move of marked clips is being applied, no clip SHALL be
lifted, and a drop SHALL move nothing. Move marked to…, and Move up and Move down, SHALL work as they
did before.

Above the chapters, Edit mode SHALL say how clips are moved:

- with one chapter: that a clip is dragged by its handle or moved with its arrows, and that a chapter can be
  added with Add chapter, below the chapters, after which clips can be dragged between chapters
- with more than one chapter: that a clip can also be dragged into another chapter, and that Move marked to… moves the marked clips to a chapter

On a coarse pointer a drag SHALL start only from the handle, as within a chapter. In a window 320 CSS pixels
wide or wider, and in both color schemes, no state of a drag SHALL make the page scroll horizontally. Under
reduced motion, no clip SHALL slide into place, and the dragged copy SHALL NOT slide between positions.

#### Scenario: Dragging a clip into the chapter above
- **WHEN** in Edit mode on `2024-08-20 - Två kapitel - Tjörn`, the operator drags `Kvällen/s1710003.mp4` by its
  handle up into `Main` and holds it over the upper half of `s1710001.mp4`
- **THEN** a line shows above `s1710001.mp4`, the dragged copy says it goes to `Main` at position 1 of 2, and
  `s1710001.mp4` has not moved
- **WHEN** the operator releases it there
- **THEN**
  - `Main` plays `Kvällen/s1710003.mp4` and then `s1710001.mp4`, the first marked as coming from `Kvällen`,
    and its heading says 1 clip moved
  - `Kvällen` plays `s1710002.mp4` and the new `s1710004.mp4`, and its heading counts no clip moved
  - keyboard focus is on the handle of `Kvällen/s1710003.mp4` in `Main`, and the row's first line is fully
    visible above the save bar
  - "s1710003.mp4 moved to “Main”, position 1 of 2" is announced
  - the save bar says that 1 clip moved and that saving adds 1 new clip to `reel.yaml`

#### Scenario: Saving a dragged clip
- **WHEN** after that drag the operator saves
- **THEN** `reel.yaml`'s default chapter lists `Kvällen/s1710003.mp4` and then `s1710001.mp4`, `Kvällen` lists
  `Kvällen/s1710002.mp4` and then `Kvällen/s1710004.mp4`, `s1710004.mp4` is still ignored, and no other line
  of the file changed

#### Scenario: Dragging a clip back leaves nothing to save
- **WHEN** after the drag into `Main` on `2024-08-20 - Två kapitel - Tjörn`, the operator drags
  `Kvällen/s1710003.mp4` back into `Kvällen` and releases it between `s1710002.mp4` and `s1710004.mp4`
- **THEN** both chapters play what they played when Edit mode opened, no row is marked as moved, and the page
  shows no unsaved changes

#### Scenario: Crossing into the next chapter from the keyboard
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator focuses the handle of `s1710001.mp4`, lifts the
  clip and presses Down
- **THEN** "s1710001.mp4 is over “Kvällen”, position 1 of 4" is announced, and a line shows above
  `s1710002.mp4` in `Kvällen`
- **WHEN** the operator presses Down again and drops the clip
- **THEN**
  - `Kvällen` plays `s1710002.mp4`, `s1710001.mp4`, `s1710003.mp4` and `s1710004.mp4`, with `s1710001.mp4`
    marked as coming from `Main`
  - `Main` plays no clip, still lists the ignored `s1710004.mp4`, and shows its area for clips dragged into it
  - "s1710001.mp4 moved to “Kvällen”, position 2 of 4" is announced
  - keyboard focus is on the handle of `s1710001.mp4` in `Kvällen`

#### Scenario: Crossing into the chapter before from the keyboard
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator lifts `Kvällen/s1710002.mp4` from the keyboard,
  presses Up once and drops it
- **THEN** "s1710002.mp4 is over “Main”, position 2 of 2" was announced, and `Main` plays `s1710001.mp4` and
  then `Kvällen/s1710002.mp4`

#### Scenario: Page Down jumps to the next chapter from the keyboard
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator lifts `s1710001.mp4` from the keyboard and presses
  Page Down
- **THEN** "s1710001.mp4 is over “Kvällen”, position 1 of 4" is announced, and a line shows above
  `s1710002.mp4` in `Kvällen`
- **WHEN** the operator presses Page Down again
- **THEN** the line has not moved and nothing is announced
- **WHEN** the operator presses Page Up
- **THEN** "s1710001.mp4 is over position 1 of 1." is announced, and the line in `Kvällen` is gone
- **WHEN** the operator drops the clip
- **THEN** "s1710001.mp4 dropped at position 1 of 1, unchanged." is announced, and both chapters are as they were

#### Scenario: Page Down and Page Up cross a long chapter in one press
- **WHEN** an event holds 400 clips in its own chapter and 3 in a second chapter, `Kväll`, and the operator
  lifts the 200th clip of the first chapter from the keyboard and presses Page Down
- **THEN** "c0200.mp4 is over “Kväll”, position 1 of 4" is announced, and the line above `Kväll`'s first clip
  and the dragged copy are both in the window
- **WHEN** the operator presses Page Up
- **THEN** "c0200.mp4 is over position 1 of 400." is announced, and the first clip's row and the dragged copy
  are both in the window
- **WHEN** the operator presses Escape
- **THEN** the clip is back at position 200 of 400, with its handle in the window

#### Scenario: Page Up jumps to the chapter before from the keyboard
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator lifts `Kvällen/s1710004.mp4` from the keyboard
  (the third position of `Kvällen`), presses Page Up and drops it
- **THEN** "s1710004.mp4 is over “Main”, position 1 of 2" was announced, and `Main` plays `Kvällen/s1710004.mp4`
  and then `s1710001.mp4`

#### Scenario: Page keys with one chapter or a missing clip move nothing
- **WHEN** in a window 390 × 600 on `2024-06-27 - Grillning med grannar`, which has one chapter, the operator
  lifts `s1710001.mp4` from the keyboard and presses Page Down with the page scrolled to its top
- **THEN** the clip is still over its own place, nothing is announced, and the page has not scrolled
- **WHEN** on `2024-09-01 - Sommarlov`, after adding a chapter `Morgon`, the operator lifts `borttagen.mp4` and
  presses Page Down
- **THEN** the clip is still over its place in `Main`, and `Morgon` plays no clip

#### Scenario: Escape cancels a drag into another chapter
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator lifts `s1710001.mp4` from the keyboard, presses
  Down twice, and presses Escape
- **THEN** both chapters are as they were, keyboard focus is on the handle of `s1710001.mp4`, fully visible,
  and "Move cancelled. s1710001.mp4 is back at position 1 of 1." is announced

#### Scenario: A tall row lifted and released in place
- **WHEN** in a window 390 × 844 on `2024-08-20 - Två kapitel - Tjörn`, with the Cuts panel of
  `Kvällen/s1710003.mp4` shown, the operator presses its handle, moves the pointer 10 pixels and releases it
- **THEN** "Picked up s1710003.mp4, position 2 of 3." and "s1710003.mp4 dropped at position 2 of 3,
  unchanged." are announced, and `Kvällen` plays `s1710002.mp4`, `s1710003.mp4` and `s1710004.mp4` as before

#### Scenario: Dragging a clip into an empty chapter
- **WHEN** on `2024-06-27 - Grillning med grannar`, the operator adds a chapter `Kvällen vid grillen`
- **THEN** the new chapter shows an area that says clips can be dragged into it
- **WHEN** the operator drags `s1710004.mp4` onto that area
- **THEN** the area is marked as the target, the dragged copy says it goes to `Kvällen vid grillen` at position
  1 of 1, and nothing else on the page has moved
- **WHEN** the operator releases it and saves
- **THEN** `reel.yaml` lists `s1710001.mp4`, `s1710002.mp4` and `s1710003.mp4` in the default chapter and
  `s1710004.mp4` in `Kvällen vid grillen`, and the save bar said that 1 chapter was added and 1 clip moved

#### Scenario: A deleted chapter takes no clip
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator marks all three clips of `Kvällen` and moves them to `Main`
  with Move marked to…, deletes `Kvällen`, adds a chapter `Morgon`, lifts `Kvällen/s1710004.mp4` (last in `Main`)
  from the keyboard and presses Down
- **THEN** "Kvällen/s1710004.mp4 is over “Morgon”, position 1 of 1" is announced: the deleted `Kvällen` was
  passed over
- **WHEN** the operator presses Escape, then drags `Kvällen/s1710004.mp4` with the mouse and releases it over
  the deleted `Kvällen`
- **THEN** no chapter changed, and the drop is announced as one that changed nothing

#### Scenario: A missing clip stays in its chapter
- **WHEN** on `2024-09-01 - Sommarlov`, after adding a chapter `Morgon`, the operator lifts `borttagen.mp4`
  from the keyboard
- **THEN** "Picked up borttagen.mp4, position 3 of 3. It is missing, so it stays in “Main”." is announced
- **WHEN** the operator presses Down and drops it
- **THEN** `borttagen.mp4` is still at position 3 of `Main`, and `Morgon` plays no clip

#### Scenario: A dragged clip keeps its cuts and what was typed
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator opens the Cuts of `Kvällen/s1710002.mp4`, adds a
  cut from 0 to 1.5 seconds, types `2` in the start field, and drags the clip into `Main` after `s1710001.mp4`
- **THEN** in `Main` the clip's Cuts panel is still shown, listing that cut, and its start field holds `2`;
  keyboard focus is on its handle, and the row's first line (handle, name, Cuts control) is fully visible,
  below the chapter's heading and above the save bar; the save bar says that a cut was typed on
  `Kvällen/s1710002.mp4` and not added, and Save says that it is unavailable

#### Scenario: No drag while a save is in flight
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, with a dragged clip not yet saved, the operator presses Save
  and the service has not answered yet
- **THEN** pressing Space on the handle of `s1710001.mp4` lifts nothing and announces nothing, a mouse drag
  from that handle moves nothing, and every chapter stays as it was

#### Scenario: Dragging by touch on a phone
- **WHEN** on a touch screen 390 pixels wide, on `2024-08-20 - Två kapitel - Tjörn`, a touch starts on the
  handle of `Kvällen/s1710002.mp4` and moves up into `Main` above `s1710001.mp4` before it lifts
- **THEN** `Main` plays `Kvällen/s1710002.mp4` first, and the page did not scroll horizontally
- **WHEN** a touch starts on that clip's name and moves up
- **THEN** the page scrolls, and no clip moves

#### Scenario: The edge scrolls fast enough to cross a long chapter, and no faster
- **WHEN** an event holds 400 clips in its own chapter and 3 in a second chapter, the operator lifts the second
  chapter's first clip with the pointer, with the page scrolled to that chapter, and holds the pointer at the
  window's very top edge (its first pixel row) for 2 seconds
- **THEN** the page scrolled up between 1,200 and 4,000 CSS pixels over those 2 seconds (an average between 600
  and 2,000 per second)
- **WHEN** the operator moves the pointer out of the scrolling zone
- **THEN** the page stops scrolling
- **WHEN** the operator holds the pointer in the middle of the zone (a tenth of the window's height below its
  top edge) for 2 seconds
- **THEN** the page scrolls up by between a quarter and three quarters of what it scrolled at the very edge

#### Scenario: Reaching a chapter out of view
- **WHEN** an event holds 400 clips in its own chapter and 3 in a second chapter, and the operator drags the
  second chapter's first clip up and holds it at the window's top edge
- **THEN** the page scrolls up by itself until the first chapter's first clip is in view
- **WHEN** the operator releases the clip over the upper half of that first clip
- **THEN** the clip is at position 1 of 401 in the first chapter, and the second chapter plays 2 clips

#### Scenario: The hint says how to reach other chapters
- **WHEN** Edit mode opens on `2024-06-27 - Grillning med grannar`, which has one chapter
- **THEN** the hint above the chapters says that a chapter can be added with Add chapter, below the chapters,
  and that clips can then be dragged between chapters
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn`
- **THEN** the hint says that a clip can be dragged into another chapter, and that Move marked to… moves the marked clips to a chapter

#### Scenario: Nothing shifts while dragging over another chapter
- **WHEN** in a window 320 pixels wide, in the light and in the dark scheme, on `2024-08-20 - Två kapitel -
  Tjörn`, the operator drags `s1710001.mp4` over `Kvällen` and holds it between `s1710002.mp4` and
  `s1710003.mp4`
- **THEN** every clip row and both chapter panels keep the size and place they had before the drag, the line
  between the two clips is visible beside the dragged copy, and the page does not scroll horizontally

### Requirement: Edit mode previews a clip on request

In Edit mode, the Cuts panel of every clip that offers one (an included or new clip on disk) SHALL offer a
**Watch** control as the panel's first control. Pressing it SHALL open the clip's preview, a player for the
clip, in the panel, above the clip's cuts, and pressing it while the preview is open SHALL close it. The
control SHALL be named "Watch <name>", where <name> is the clip's name as its row names it, and SHALL say to
assistive technology whether the preview is open. While the preview is open, the control SHALL show that a press
closes it: its words SHALL be "Hide player", and its name "Hide player of <name>". The preview SHALL be a region
named "Player for <name>".

**From the row.** In Edit mode, the thumbnail of every clip that offers a Cuts panel SHALL also be a button
named "Watch <name>" that opens the same preview in one press. Pressing it SHALL show the clip's Cuts panel
when it is hidden, open the preview there, closing any other, and move keyboard focus to the preview's Play.
Pressing it while the preview is open SHALL keep the preview open and move keyboard focus to its Play. The
thumbnail SHALL keep its box, its size and its place in the row: being a button changes no row's size or
position. It SHALL NOT start a drag: the drag handle stays a control of its own, and a clip moves only by its handle or
its move buttons. A thumbnail that could not be shown (its "No preview" box) SHALL open the preview all the
same.

**What it plays.** The preview SHALL play the clip's preview copy when the clip has a ready one, and the clip's
own file, the original, otherwise, as "A clip's preview plays its preview copy when one is ready" requires. The
original is the file the service serves from `GET /api/v1/events/{event_id}/media?clip=<identity>`. The event id
and the clip's full identity SHALL be sent exactly as the event detail gives them, and the clip's modification
time, exactly as the event detail gives it, as `v`. Until it plays, the preview SHALL show the clip's thumbnail. It SHALL NOT start playing by
itself. A preview opened with Watch, from the panel or the thumbnail, SHALL stand at the clip's start, also
after an earlier preview of the clip was closed elsewhere in it. A clip displayed in portrait, such as a phone
clip whose container rotates it, SHALL be shown whole, turned as a player shows it. Unless a scenario of this
requirement says that its clip has a ready preview copy, it SHALL be read for a clip that has none.

**Nothing loads before it is asked for.** The page SHALL NOT request a clip's media or its preview copy, and
SHALL NOT create a video element for either, before the operator opens that clip's preview. This SHALL hold for any number of clips,
for Cuts panels that are shown, and on entering, scrolling and leaving Edit mode. Closing a preview SHALL
stop its playback and any loading of its file.

**One at a time.** Opening a preview SHALL close any other clip's preview, so that Edit mode never holds more
than one video element. Edit mode SHALL show no movie player: the event's "Movie" section belongs to the read
view, which Edit mode replaces.

**Keyboard and focus.** Opening a preview SHALL move keyboard focus to its Play control. The preview's
controls SHALL come in this keyboard order, each reachable and usable by keyboard alone:
1. **Close**, named "Close the player of <name>"
2. **Play** / **Pause**, which says which it does
3. the **playhead**, a slider over the clip's length
4. **Skip cuts**
5. **Set From**
6. **Set To**
7. **Play original** or **Play preview copy**, present only while the clip has a ready preview copy

Each control SHALL name the clip as its row names it. Close, and Escape pressed while keyboard focus is in the
preview, SHALL close the preview and move keyboard focus to the control that opened it: the Watch control, or
the clip's thumbnail. Hiding the Cuts panel SHALL close its preview, leaving keyboard focus on the Cuts
control. No control of a closed preview SHALL keep focus.

**Play** SHALL be usable from the moment the preview opens. Pressed before the browser has read the clip, it
SHALL play the clip once the browser can. A preview opened with Watch, its thumbnail or Try again SHALL announce,
once, that the clip is ready to play, with its length.

**The playhead.**
- Space on it SHALL play or pause the clip, as Play does, and SHALL NOT scroll the page.
- It SHALL take the Left and Down arrows to step back 0.1 seconds and the Right and Up arrows to step on 0.1
  seconds. Page Down and Page Up SHALL step one second, and Home and End SHALL go to the clip's start and
  end. Each step SHALL stay within the clip.
- A press or a drag along it SHALL move to the time under the pointer.
- It SHALL say its value to assistive technology as the time and the clip's length, in the format the Cuts
  panel writes times (`0:01.234 of 0:06.02`), and SHALL add when the time lies inside a cut. While the clip
  plays, the value it says SHALL change at most once a second.
- Until the preview has read the clip's length, the playhead, Set From and Set To SHALL say that they are
  unavailable and change nothing.

The preview SHALL show the playhead's time and the clip's length as a readout that says what it is and keeps its
width, as "Running times are written to a fixed width and say what they are" requires (`Clip 0:01.23 of 0:06.02`).
The slider's value text stays in the Cuts panel's format, above.

**Sizes and look.**
- The picture SHALL be shown whole in a box of fixed 16:9 proportions, as wide as the panel allows up to 640
  CSS pixels and never taller than 360. The box SHALL have that size before the clip's file is read, so that
  nothing on the page moves when it is.
- In a window 320 pixels wide or more, the preview SHALL NOT make the page scroll horizontally.
- When the primary pointer is coarse, each of its controls SHALL take a tap anywhere in an area of at least
  44 × 44 CSS pixels around it, reaching no other control. The playhead SHALL take a tap across its whole
  width in an area at least 44 pixels tall.
- It SHALL follow the page's color scheme in both schemes. No state of it SHALL be shown by color alone.
- It SHALL animate nothing. The playhead moves only with playback or a seek.

**What the browser cannot do, by cause.** Each of these SHALL be shown in the preview as a note, never as an
alert, and announced once through Edit mode's live region. Keyboard focus SHALL stay in the preview, on
Close when the control that held it went:
- **No sound.** When the original plays and the browser reports that it finds no audio it can play in the clip, the preview SHALL say
  that this browser finds no sound it can play in the clip, and that if a Sony camera recorded it, its sound
  is PCM, which Firefox does not play and Chrome does, and the render keeps it. The note SHALL NOT state as
  fact a cause or a sound the page does not know of: the clip may have no audio track at all. Playback SHALL
  be otherwise unchanged, never muted. The note SHALL NOT be shown while the preview copy plays. When the clip
  has a ready preview copy whose facts name an audio codec, the note SHALL add that the preview copy plays with
  sound and that Play preview copy plays it; when the facts name none (the clip has no audio), the note SHALL stay
  as it is and SHALL NOT promise sound from the copy.
- **No picture.** When the browser reads the clip but shows no picture of it, the preview SHALL say that this
  browser cannot show the clip's picture, and SHALL offer the clip's file as a download. Its controls SHALL
  stay.
- **It cannot play the clip.** (This is the original's. The preview copy's failures are the ones "A clip's
  preview plays its preview copy when one is ready" lists.) When the browser refuses the original, the page SHALL ask the service for the
  clip's first byte, once, to tell why. It SHALL then say:
  - that the clip is no longer on disk, with the service's detail, when the service answers that it is not a
    clip of the event
  - that the clip changed on disk since the page was read, when the service serves a file whose modification
    time differs from the one the event detail gave
  - in both of these cases, the advice to stop editing (saving first to keep the edits), so that the event is
    read again, and then to open the player again. The page SHALL NOT call this a refresh: in Edit mode the
    page's Refresh leaves Edit mode. The edits SHALL stay untouched until the operator acts.
  - that the clip's file is empty, when the service answers that the file has no first byte
  - that the clip could not be read, with the failure kind's words and the service's detail, when the service
    answers that it cannot read it
  - that this browser cannot play the clip's format, offering the file as a download, when the service serves
    it
  - that the service gave no usable answer, saying which, with a Try again that opens the preview anew, when it
    gives none. Try again SHALL move keyboard focus to the reopened preview's Play.

  A failure SHALL NOT be retried by itself.

**Within Edit mode.**
- Opening, closing, playing and seeking a preview SHALL write nothing and SHALL NOT count as an edit. They
  SHALL bring no save bar and SHALL NOT trigger the unsaved-changes question.
- While a save is in flight or a move of marked clips is pending, Set From and Set To SHALL say that they are unavailable
  and change nothing. Play, the playhead, Skip cuts and Close SHALL stay usable.
- A clip moved within its chapter SHALL keep its preview, playing or not.
- A clip moved into another chapter, by a drag or by Move marked to…, SHALL keep its preview open at the same time,
  paused. The reopened preview SHALL take no keyboard focus and SHALL NOT scroll the page. After a drop,
  keyboard focus is on the clip's handle, and the handle and the row's first line are fully visible, as
  "Edit mode drags clips between chapters" requires; a row made taller than the view by its preview is
  scrolled so that its first line is, and the preview under it may lie partly outside the view.
- Reset SHALL close every preview. Leaving Edit mode SHALL close it.

#### Scenario: Nothing loads until a preview is opened
- **WHEN** the operator opens Edit mode on `2024-09-15 - Stor dag`, whose root chapter plays 400 clips, scrolls
  to its end, and shows the Cuts panels of `c0001.mp4`, `c0200.mp4` and `c0400.mp4`
- **THEN** the page holds no video element and has made no media request
- **WHEN** the operator presses Watch in the panel of `c0400.mp4`
- **THEN** its preview opens with keyboard focus on "Play c0400.mp4", nothing plays, and every media request
  names `c0400.mp4` and carries its modification time as `v`

#### Scenario: Playing and seeking from the keyboard
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar`, using only the keyboard, the operator shows the
  Cuts panel of `s1710001.mp4`, presses Watch and then Space
- **THEN** the clip plays, and the control with focus is now named "Pause s1710001.mp4"
- **WHEN** the operator presses Space again, moves to the playhead, and presses Home, then Right three times
- **THEN** the clip is paused, and the playhead says `0:00.3 of 0:06.02` in a browser that reads the clip's
  length as 6.02 seconds
- **WHEN** the operator presses End, then Page Down
- **THEN** the playhead says `0:05.02 of 0:06.02`
- **WHEN** the operator presses Space on the playhead
- **THEN** the clip plays and the page does not scroll; Space again pauses it

#### Scenario: Opening another preview closes the first
- **WHEN** the preview of `s1710001.mp4` of `2024-06-27 - Grillning med grannar` is playing, and the operator
  shows the Cuts panel of `s1710002.mp4` and presses its Watch
- **THEN** the preview of `s1710001.mp4` is closed, its Watch control says that it is not open, and its file
  is no longer loading. The preview of `s1710002.mp4` is open, with keyboard focus on its Play.

#### Scenario: Closing gives focus back
- **WHEN** keyboard focus is on the playhead of an open preview and the operator presses Escape
- **THEN** the preview closes, and keyboard focus is on that clip's Watch control
- **WHEN** the operator opens it again and presses Close
- **THEN** the preview closes, and keyboard focus is on the Watch control again
- **WHEN** the operator opens it again and presses the clip's Cuts control
- **THEN** the panel and the preview are hidden, and keyboard focus stays on the Cuts control

#### Scenario: Watching from the row in one press
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar`, with every Cuts panel hidden, the operator tabs
  to the thumbnail of `s1710002.mp4`, which is named "Watch s1710002.mp4", and presses Enter
- **THEN** the clip's Cuts panel is shown with its preview open, keyboard focus is on "Play s1710002.mp4",
  nothing plays, and no other row changed its size; the rows above it did not move, and the rows after it
  moved down only by the height that the opened panel added to its row
- **WHEN** the operator presses Escape
- **THEN** the preview closes, its panel stays shown, and keyboard focus is on the thumbnail of `s1710002.mp4`
- **WHEN** the operator presses the thumbnail of `s1710001.mp4` with the pointer
- **THEN** the preview of `s1710001.mp4` opens, the one of `s1710002.mp4` is closed, and no drag starts: every
  clip keeps its place
- **WHEN** in Edit mode on `2024-10-05 - Trasig`, whose thumbnail shows "No preview", the operator presses the
  thumbnail of `trasig.mp4`
- **THEN** its preview opens and says that the clip's file is empty

#### Scenario: A portrait clip is shown whole
- **WHEN** the event `2024-05-19 - Provklipp` holds `h264-720p-rotate90-aac.mp4`, a 1280×720 clip that its
  container turns to portrait, and the operator opens its preview and plays it
- **THEN** the picture is taller than wide and wholly inside the preview's 16:9 box, with empty bands at its
  sides. The box is as large as the box of a landscape clip in the same panel would be.

#### Scenario: No sound for a Sony clip in Firefox
- **WHEN** in Firefox, which plays no PCM audio, the operator opens the preview of `sony-xavc-1080p25-pcm.mp4`
  of `2024-05-19 - Provklipp`, whose preview copy is not ready
- **THEN** the preview says that this browser finds no sound it can play in the clip, and that if a Sony
  camera recorded it, its sound is PCM, which Chrome plays and the render keeps. The note is announced once,
  and the clip plays its picture on request, not muted.
- **WHEN** the same preview is opened in Chrome
- **THEN** no such note is shown
- **WHEN** in Firefox, the operator opens the preview of a clip with no audio track whose preview copy is ready
  and whose facts name no audio codec
- **THEN** the note is shown without the sentence that the preview copy plays with sound

#### Scenario: A picture this browser cannot show
- **WHEN** in Chrome, the operator opens the preview of the HEVC clip `hevc-mov-rotate90-aac.mov` of
  `2024-05-19 - Provklipp`
- **THEN** the preview says that this browser cannot show the clip's picture and offers the clip as a
  download, and its controls stay
- **WHEN** in Firefox, which refuses that clip, the operator opens the same preview
- **THEN** the preview says that this browser cannot play the clip's format and offers the clip as a download

#### Scenario: An empty clip says so
- **WHEN** in Edit mode on `2024-10-05 - Trasig`, whose only clip `trasig.mp4` is an empty file, the operator
  opens its preview
- **THEN** the preview says that the clip's file is empty and that there is nothing to play. The page shows no
  alert, the words are announced once, and keyboard focus is in the preview.

#### Scenario: Try again opens the preview anew
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar`, the service gives no answer when the operator
  opens the preview of `s1710001.mp4`, and then answers again
- **THEN** the preview says that the service is not reachable and offers Try again
- **WHEN** the operator presses Try again
- **THEN** the preview opens anew, ready to play, with keyboard focus on "Play s1710001.mp4", and Escape closes
  it

#### Scenario: A clip removed from disk since the page was read
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar`, `s1710004.mp4` is deleted from disk and the
  operator then opens its preview
- **THEN** the preview says that the clip is no longer on disk and advises stopping editing, saving first to
  keep the edits, to read the event again, and offers no download

#### Scenario: A clip changed on disk since the page was read
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar`, after the page was read, `s1710002.mp4` is
  replaced on disk by a file of the same name that no browser can play, and the operator opens its preview
- **THEN** the preview says that the clip changed on disk since the page was read and advises stopping editing,
  saving first to keep the edits, to read the event again, rather than blaming the clip's format. It offers no
  download, and the edits are as they were

#### Scenario: The preview follows its clip
- **WHEN** in Edit mode on `2024-08-20 - Två kapitel - Tjörn`, the preview of `s1710001.mp4` is paused at
  `0:02.5`, and the operator drags that clip into `Kvällen`
- **THEN** in `Kvällen`, the clip's Cuts panel is shown with its preview open, paused, at `0:02.5`
- **AND** keyboard focus is on the clip's handle, and the handle and the row's first line lie fully between the
  bottom of the page header or the chapter's heading and the top of the save bar, also in a window 390 × 844
  pixels
- **WHEN** the preview of `Kvällen/s1710002.mp4` is playing and the operator presses that clip's Move down
- **THEN** it keeps playing

#### Scenario: A pending save leaves playback alone
- **WHEN** on `2024-06-27 - Grillning med grannar`, with a cut added to `s1710001.mp4` and its preview open, the
  operator presses Save and the service has not answered yet
- **THEN** Set From and Set To say that they are unavailable, and pressing them changes no field, while Play,
  the playhead and Close still work and keyboard focus stays on Save

#### Scenario: Previewing is not an edit
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar`, the operator opens the preview of
  `s1710002.mp4`, plays it, seeks it and closes it, and then presses the browser's Back
- **THEN** no save bar is shown at any time, and the page goes back to the event list without asking about
  unsaved changes

#### Scenario: Reset closes the preview
- **WHEN** on `2024-06-27 - Grillning med grannar`, with the title changed and the preview of `s1710001.mp4`
  open, the operator presses Reset
- **THEN** the preview is closed and its panel is hidden, and the page holds no video element

#### Scenario: A preview on a phone
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn` on a touch screen 320 pixels wide, and the
  operator opens the preview of `Kvällen/s1710002.mp4`
- **THEN** the page does not scroll horizontally, and the picture's box is 16:9 inside the panel. A tap anywhere
  in a 44 × 44 pixel area around Close, Play, Skip cuts, Set From and Set To reaches that control and no other.
  A tap anywhere along the playhead, up to 22 pixels above or below its centre line, moves it.

#### Scenario: The player's time says what it is and does not move
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar` the operator opens the preview of `s1710001.mp4`
  (6.02 s) and plays it to the end
- **THEN** the header reads `Clip 0:00.00 of 0:06.02`, then `Clip 0:01.50 of 0:06.02`, and `Clip 0:06.02 of 0:06.02`
  at the end; the readout's bounding box has the same width in every sample taken during the playthrough, and the
  close button does not move

### Requirement: A clip's preview sets cut times at the playhead and plays the clip as the movie will

**The cut bar.** Under the picture, the preview SHALL show a bar along the clip's length. It SHALL show:
- every cut the clip's panel lists that is not removed, read and added alike
- each cut that is removed until the save, drawn differently
- while the panel's fields hold a start and an end that the panel would accept as a cut, that typed span,
  drawn differently again
- the playhead

Each kind SHALL differ by its shape, not by its color alone, and a legend SHALL name each kind the bar shows.
A cut that runs past the clip's end SHALL be drawn up to that end. The bar SHALL follow every change to the
panel's cuts and fields at once.

**Set From and Set To.**
- **Set From** SHALL write the playhead's time into the panel's start field, and **Set To** into its end field.
  The playhead's time is the time of the file that plays, the original or its preview copy, which are the same.
- The time SHALL be written to the millisecond, in the format the panel writes times (`0:01.234`, `0:02.5`).
  The panel SHALL read it back as that same time.
- Keyboard focus SHALL stay on the pressed control, and the new value SHALL be announced.
- Neither SHALL add a cut. The written time SHALL count as a cut typed but not added: the clip's Cuts control
  SHALL say "typed", and the save bar SHALL hold Save back until the cut is added or its fields cleared, as for
  any typed time.

**Skip cuts** SHALL be a control that says whether it is on, and it SHALL start off.
- While it is on, playback SHALL show no frame that lies wholly inside a cut the panel lists that is not
  removed. Cuts are joined as the render joins them, overlapping or touching ones as one.
- Playback reaching a cut SHALL continue at the cut's end, jumping over each cut once, also when the cut ends
  between two frames. Playback SHALL never stall at a cut.
- A cut that runs to the clip's end, or that ends less than 0.1 seconds before the end the browser reads,
  SHALL stop playback, paused, at that cut's start. Browsers read a clip's length up to 60 ms longer than the
  render does, so a cut that ends where the render's clip ends counts as running to the end.
- Play pressed while the playhead is inside a cut SHALL start at that cut's end. When no footage follows it,
  or when the playhead is at the clip's end, Play SHALL start at the first footage of the clip outside every
  cut. When the cuts cover the whole clip, Play SHALL play nothing and SHALL say that the cuts cover the whole
  clip.
- While it is off, playback SHALL show every moment of the clip.
- In either state, moving the playhead into a cut while the clip is paused SHALL show that moment, so that a
  time can be set from inside a cut.

**The clip's length.** The page SHALL take a clip's length from its preview when the preview has read it, else
from the duration the event detail gives the clip when that is not null, and from nowhere else. The preview reads
it from the file that plays: as the browser reads it from the original's file, or, while the clip's preview copy
plays, as the duration in the copy's facts, which is the original's duration as the engine probed it ("A clip's
preview plays its preview copy when one is ready"). The preview's length SHALL win over the detail's whenever
both exist, because Set From and Set To write times in it, and a browser can read up to 60 ms more than the
probe's duration. A detail duration of `null` SHALL be treated as unknown, never as zero.
- Once it has the length, the clip's panel SHALL say where the clip ends beside its fields (`This clip ends at
  0:06.02`).
- The panel SHALL refuse a cut that ends after the clip's length, compared to the millisecond as the panel
  writes times. The refusal SHALL be at the end field, or at the start field when the start lies at or after
  the length, since no end could then fix it. It SHALL name the cut's time and the clip's length. A cut that
  ends exactly at the length SHALL be accepted.
- Each cut the panel lists that ends after the length SHALL be marked as running past the clip's end. Nothing
  SHALL refuse it, and its Undo SHALL NOT be refused for it.
- The page SHALL keep the length the preview read for the clip while Edit mode stays open: after the preview
  closes, after another opens, and after the clip moves to another chapter. It SHALL forget it when the
  clip's modification time changes, and when Edit mode closes. The detail's duration belongs to the clip's
  current file, so a replaced file's old duration SHALL NOT be used: the next detail gives the new one, or
  `null`.
- When the browser reads a different length for the original while it plays, the panel SHALL use the latest.
  What the browser reads from a preview copy SHALL NOT change the length.
- Neither length SHALL be saved, sent to the service or shown anywhere outside Edit mode.

#### Scenario: The bar shows the clip's cuts
- **WHEN** the `reel.yaml` of `2024-06-27 - Grillning med grannar` gives `s1710003.mp4` a cut from 0 to 1.2
  seconds with the reason `black`, and in Edit mode the operator opens that clip's preview, adds a cut from
  `3` to `4` and removes the read cut
- **THEN** the bar shows the cut from 3 to 4 seconds as a cut and the span from 0 to 1.2 seconds as removed,
  each drawn differently, and the legend names a cut and a cut removed when you save

#### Scenario: Setting a cut at the playhead
- **WHEN** in the preview of `s1710001.mp4` of `2024-06-27 - Grillning med grannar`, with the playhead at
  `0:01.2`, the operator presses Set From
- **THEN** the start field holds `0:01.2`, keyboard focus is on Set From, "From set to 0:01.2" is announced, the
  clip's Cuts control says "typed", and the save bar says that a cut was typed on `s1710001.mp4` but not added
- **WHEN** the operator moves the playhead to `0:02.5`, presses Set To, and then presses Add cut
- **THEN** the bar showed the typed span from 1.2 to 2.5 seconds before the addition. The panel then lists the
  cut from `0:01.2` to `0:02.5`, the Cuts control reads "1 cut · −1.3 s", and the save bar says that 1 cut was
  added.

#### Scenario: A time set while playing is written to the millisecond
- **WHEN** the preview of `s1710001.mp4` plays and the operator presses Set From while it plays
- **THEN** the start field holds the playhead's time at that moment, rounded to the millisecond and written
  without a trailing zero, such as `0:02.607`, and the panel accepts it

#### Scenario: Skipping cuts while playing
- **WHEN** `s1710002.mp4` of `2024-06-27 - Grillning med grannar` has a cut from `1` to `2`, and the operator
  turns Skip cuts on, moves the playhead to `0:00.5` and plays the clip
- **THEN** no frame between 1 and 2 seconds is shown, and playback continues from 2 seconds
- **WHEN** the operator turns Skip cuts off and plays the clip again from `0:00.5`
- **THEN** the frames between 1 and 2 seconds are shown

#### Scenario: A cut that ends between two frames is jumped over once
- **WHEN** `s1710002.mp4` of `2024-06-27 - Grillning med grannar`, a 50 fps clip, has a cut from `1` to
  `2.01`, which ends between its frames at 2 and 2.02 seconds, and the operator turns Skip cuts on and plays
  the clip from `0:00.5`
- **THEN** playback goes on past 2.5 seconds within a second of reaching the cut, the cut is jumped over once,
  and no frame that lies wholly between 1 and 2.01 seconds is shown

#### Scenario: A cut to the clip's end ends playback
- **WHEN** `s1710002.mp4` also has a cut from `5` to `0:06.02`, where ffprobe and the render end the clip,
  Skip cuts is on, and the operator plays the clip from `0:04.5`, in Chrome, which reads the clip's length as
  6.02 seconds, and again in Firefox, which reads it as 6.08 seconds
- **THEN** in each, playback stops at 5 seconds, paused, with no frame after 5 seconds shown
- **WHEN** the operator presses Play again
- **THEN** playback starts from the clip's start

#### Scenario: Cuts over the whole clip leave nothing to play
- **WHEN** `s1710001.mp4` has one cut from `0` to its end (`0:06.02`, in a browser that reads that length),
  Skip cuts is on, and the operator presses Play
- **THEN** nothing plays, and the page says that the cuts cover the whole clip

#### Scenario: A cut past the clip's end is refused once its length is known
- **WHEN** in a browser that reads its length as 6.02 seconds, the operator opens the preview of
  `s1710001.mp4` of `2024-06-27 - Grillning med grannar`, closes it, and adds a cut from `5` to `7`
- **THEN** the panel says that the clip ends at `0:06.02`. The cut is refused at the end field, which receives
  keyboard focus, saying that `0:07` is after the clip's end at `0:06.02`. No cut is added.
- **WHEN** the operator types `0:06.02` as the end and adds the cut
- **THEN** the cut from `0:05` to `0:06.02` is listed
- **WHEN** the operator adds a cut from `7` to `8` on the same clip, and then one from `0:06.02` to `7`
- **THEN** each is refused at the start field, saying that its start is at or after the clip's end

#### Scenario: A listed cut past the end is marked, not refused
- **WHEN** the `reel.yaml` of `2024-06-27 - Grillning med grannar` gives `s1710002.mp4` a cut from 3723.125 to
  3725.5 seconds, and the operator opens that clip's preview
- **THEN** the cut is listed as running past the clip's end and is not drawn on the bar beyond it. Removing it
  and pressing its Undo is not refused.

#### Scenario: The length stays with the clip
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator opens and closes the preview of `s1710001.mp4`,
  marks that clip and moves it to `Kvällen` with
  Move marked to…, and adds a cut from `5` to `7` on it there
- **THEN** the cut is refused for ending after the clip's length

#### Scenario: The preview's length wins over the service's duration
- **WHEN** the detail gives `s1710001.mp4` of `2024-06-27 - Grillning med grannar` a duration of `6.02`, and in
  Firefox, which reads its length as 6.08 seconds, the operator opens the preview, presses Set To at the end of
  the clip and adds the cut from `5`
- **THEN** the panel says that the clip ends at `0:06.08`, and the cut from `0:05` to `0:06.08` is listed, not
  refused

#### Scenario: A listed cut past the end is marked from the service's duration
- **WHEN** the `reel.yaml` of `2024-06-27 - Grillning med grannar` gives `s1710002.mp4` a cut from 3723.125 to
  3725.5 seconds, the detail gives that clip a duration of `6.02`, and no preview was opened
- **THEN** the cut is listed as running past the clip's end, and removing it and pressing its Undo is not
  refused

#### Scenario: Cutting to the original's end while its preview copy plays
- **WHEN** the detail gives `s1710001.mp4` of `2024-06-27 - Grillning med grannar` a ready preview copy whose
  facts say `6.02` seconds, the browser reads the copy as 6.0 seconds, and the operator opens the preview, plays
  the copy, and adds a cut from `5` to `0:06.02`
- **THEN** the panel says that the clip ends at `0:06.02` and lists the cut, not refused

### Requirement: A notification raised under a dialog is shown above it

While a modal dialog is open, a notification that is shown SHALL be visible above the dialog and its
backdrop: an error notification SHALL be fully readable there at any window width from 320 CSS pixels up.
It MAY not take focus or clicks until the dialog closes. Opening a dialog while notifications are already
shown SHALL leave them visible above it.

While a modal dialog is open, the clock that dismisses a success or info notification by itself SHALL be
stopped, so that none disappears before the operator can see it. When the last open dialog closes, each such
clock SHALL continue with the time it had left. An error notification stays until it is dismissed, as always.

#### Scenario: A render ends while Render anyway is open
- **WHEN** on `2023-06-23 - Midsommar - Dalarna`, which is up to date, the operator presses Render anyway, and
  while the dialog "Render anyway?" is open a render of `2024-08-20 - Två kapitel - Tjörn` fails
- **THEN** the error notification naming "Två kapitel" is visible above the dialog and its backdrop, in
  windows 1280 and 390 pixels wide, in the light and the dark theme, and still shown after the dialog is
  closed with Escape

#### Scenario: A success notification does not run out under a dialog
- **WHEN** a render of another event ends while the "Render anyway?" dialog is open, which raises the success
  notification “Rendered …”, and the operator waits more than 5 seconds before pressing Cancel
- **THEN** the notification was visible above the dialog throughout, and it is still shown when the dialog
  closes
- **AND** it disappears by itself about 5 seconds after the dialog closed

#### Scenario: A notification already shown when the dialog opens
- **WHEN** an error notification is shown on the event page and the operator then opens the Add chapter
  dialog
- **THEN** the error notification is still visible above the dialog

### Requirement: Edit mode saves with Ctrl+S or Cmd+S

While Edit mode has read the event's editorial document, pressing **S** with Ctrl (or Cmd on a Mac), without
Shift or Alt, SHALL act as the Save control does, from wherever keyboard focus is on the page, including a
text field, a clip row's control, the header and the page's body. Reaching Save SHALL NOT take a Tab stop
for every control before it.

The key press SHALL NOT open the browser's own "Save page" dialog, whether or not anything is saved. Before
the document has been read, and while its read has failed, the press SHALL be left to the browser. A press
with Shift or Alt, a held key's repeats, and a press during an IME composition SHALL NOT save, and Shift or
Alt SHALL leave the browser's own meaning of the key alone.

When Save is available, the press SHALL send the same write the Save control sends (the same changes, the
same version check), SHALL announce "Saving…", and SHALL show the same outcomes: the "Saved" notification and
the event page when it is written, and the save bar's failure with its choices when it is not. The press
SHALL NOT move keyboard focus. Save is available under the rules of "Saving an edit writes only what the
operator changed" and "Edit mode's save bar stays compact and fits the window": the shortcut SHALL NOT
save in any state where the Save control is held back.

When Save is held back, the press SHALL send nothing and SHALL announce why:

- with nothing to save: "Nothing to save."
- with a date typed in part, or a cut typed and not added: "Not saved:" and what is unfinished
- after a conflict: that Reload latest or Overwrite with mine comes first
- after the event is found gone: that the event no longer exists
- while a clip is lifted by the drag and not yet dropped or cancelled: that the lifted clip comes first
  ("Not saved: drop or cancel the lifted clip first."), because the order shown is not yet the order that
  a write would carry

While a save is in flight, while a move of marked clips is still being applied, or while a dialog is open (including
the question "Discard unsaved changes?" and the confirmation of Overwrite with mine), the press SHALL send
nothing and say nothing. It SHALL NOT answer a dialog's question.

The Save control SHALL name the shortcut to assistive technology and in its tooltip, and the bar SHALL NOT
show more text for it.

#### Scenario: Saving from the first field
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar`, the operator changes the location in the
  location field and, with keyboard focus still in that field, presses Ctrl+S
- **THEN** exactly one write is sent with the changed location, the live region says "Saving…", the browser's
  Save page dialog does not open, and the event page shows with a "Saved" notification

#### Scenario: Saving after a keyboard reorder without tabbing
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar`, the operator lifts its first clip by its
  handle from the keyboard, moves it down one place, drops it, and with focus still on that handle presses
  Cmd+S (the meta key)
- **THEN** one write is sent with the new clip order, and no Tab was pressed between the drop and the save

#### Scenario: Nothing has changed
- **WHEN** in Edit mode on `2024-08-02 - Badutflykt - Varberg`, with no edit made, the operator presses Ctrl+S
- **THEN** no request is sent, the live region says "Nothing to save.", and the browser's Save page dialog
  does not open

#### Scenario: A date typed in part
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar`, the operator changes the location, clears
  the date's year and presses Ctrl+S
- **THEN** no request is sent, the live region says that the date is incomplete and that nothing was saved,
  and the Save control is still unavailable

#### Scenario: After a conflict the shortcut waits like Save
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar`, the operator changes the location, the
  event's `reel.yaml` is changed by hand, the operator saves and the save bar shows the conflict, and then
  the operator presses Ctrl+S
- **THEN** no request is sent, the live region says that Reload latest or Overwrite with mine comes first,
  and the confirmation of Overwrite with mine does not open

#### Scenario: A failed shortcut save keeps the field and the edits
- **WHEN** in Edit mode on `2024-08-02 - Badutflykt - Varberg`, the operator edits the title, presses Ctrl+S
  in the title field, and the request gets no answer
- **THEN** the save bar says that the service is not reachable and offers Retry, the edit is kept, and
  keyboard focus is still in the title field

#### Scenario: A second press during the save does nothing
- **WHEN** the operator presses Ctrl+S, and presses it again, and again as a held key repeats, before the
  service has answered the first
- **THEN** exactly one write is sent, and "Saving…" is announced once

#### Scenario: A dialog's question is not answered
- **WHEN** in Edit mode with unsaved changes, the operator presses Refresh so that "Discard unsaved
  changes?" opens, and presses Ctrl+S
- **THEN** no request is sent, nothing is announced, the dialog stays open with focus on Keep editing, and
  the edits are kept

#### Scenario: A lifted clip is not saved at its old place
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar`, the operator changes the location, lifts
  its first clip with Space, moves it down one place with ArrowDown and, before dropping it, presses Ctrl+S
- **THEN** no request is sent, the live region says that the lifted clip must be dropped or cancelled first,
  and the clip is still lifted; after the drop, Ctrl+S sends one write with the location and the new order

#### Scenario: Other chords keep their meaning
- **WHEN** in Edit mode with unsaved changes, the operator presses Ctrl+Shift+S
- **THEN** the page does not save, and does not cancel the browser's own handling of the key

#### Scenario: The shortcut is named
- **WHEN** an unsaved change brings in the save bar
- **THEN** its Save control has the keyboard shortcut Control+S (Meta+S) declared to assistive technology,
  its tooltip reads "Save (Ctrl+S, or ⌘S on a Mac)", and the bar is not taller or wider than before at
  390 × 844

### Requirement: Edit mode marks clips to move together

In Edit mode, every clip that a chapter plays and that is on disk (active or new) SHALL have a **mark**: a
checkbox in the top-right corner of its thumbnail, named "Mark <name>", where <name> is the clip's name as its row
names it. A marked clip SHALL show a check icon inside the box, so that its state is not told by colour alone, and the
box SHALL be exposed to assistive technology as checked. Pressing the box, or Space on it, SHALL mark an unmarked clip
and unmark a marked one. The box SHALL be 24 CSS pixels square and SHALL lie inside the thumbnail's box, with its
top-right corner within 6 CSS pixels of the thumbnail's top-right corner, in the one-line layout and in the narrow
layout. The thumbnail's own size and place SHALL stay as they are ("Every clip row shows a frame from its clip").

When the browser's primary pointer is coarse, a tap anywhere in a 44 × 44 CSS pixel area around the box SHALL reach the
mark, taking precedence over the clip's Watch button where the two overlap; the rest of the thumbnail SHALL still open
the clip's preview. The areas of the mark and of the row's other controls SHALL NOT otherwise overlap. When the primary
pointer is fine, the mark SHALL keep the 24 pixel box and nothing around it.

Three kinds of clip SHALL have no mark, as a drag does not take them into another chapter ("Edit mode drags
clips between chapters"): a missing clip, an ignored clip, and a missing clip the operator removed. The line above the chapters SHALL
say so in a few words.

Marking is not an edit. It SHALL NOT show the save bar, SHALL NOT count as an unsaved change, SHALL NOT enable Reset or
Save, and SHALL NOT make leaving Edit mode ask first. Marks SHALL be kept per clip, whichever chapter it is in, and a
mark SHALL stay on its clip when another edit moves the clip (Move up, Move down, a drag of another clip), and when the
Cuts panel is opened or closed.

A line above the chapters SHALL always be present in Edit mode, saying how clips are marked, that dragging a marked
clip's handle moves all marked clips, and that Move marked to… moves them to a chapter. While at least one clip is marked, the same line SHALL show how many ("1 clip
marked", "3 clips marked") and a **Clear marks** button. The line SHALL keep its height whether or not it shows the
count, so that marking the first clip, and clearing the last mark, move no row.

Each change of a mark, and Clear marks, SHALL be announced once to assistive technology, with the clip's name and the
count ("s1710002.mp4 marked. 2 clips marked.", "s1710002.mp4 unmarked. No clips marked.", "Marks cleared."). Marks
SHALL end as follows:

- a clip that a drag or Move marked to… moves into another chapter, or that a group drag moves, SHALL be unmarked by that
  move; a drop that changes nothing SHALL leave every mark
- all marks SHALL end on a successful Save, on Reset, when Edit mode is left, and when the editor reads the event's
  `reel.yaml` again (Reload latest)
- a drag of an unmarked clip, Move up, Move down, adding, renaming or deleting a chapter, and cut edits SHALL leave
  marks as they are

The mark and Clear marks follow the busy-control rule: while a save is in flight or a move of marked clips is being applied, they
SHALL be aria-disabled and ignore presses, never `disabled`. A mark's keyboard focus ring SHALL be visible in both
color schemes and in forced colors. Pressing Clear marks SHALL move keyboard focus to that line, since the button leaves with the count.
The mark SHALL NOT start a drag, and a press on it SHALL NOT lift its row. Marking
a clip in a chapter that plays 400 clips, in a Chromium window 1280 × 900, SHALL reach the next painted frame within
100 ms (the median of five runs, each in a fresh Edit mode).

#### Scenario: Marking two clips
- **WHEN** in Edit mode on `2024-08-20 - Två kapitel - Tjörn`, the operator marks `Kvällen/s1710002.mp4` and then
  `Kvällen/s1710003.mp4` with the boxes at the top right of their frames
- **THEN**
  - each box shows a check icon and is exposed as checked, named "Mark s1710002.mp4" and "Mark s1710003.mp4"
  - the line above the chapters says "2 clips marked" and offers Clear marks
  - "s1710003.mp4 marked. 2 clips marked." was announced, and the save bar is not shown
  - no row moved when the first mark was made

#### Scenario: Missing and ignored clips have no mark
- **WHEN** on `2024-09-01 - Sommarlov` the operator looks at the row of the missing `borttagen.mp4`, and on
  `2024-08-20 - Två kapitel - Tjörn` at the row of the ignored `s1710004.mp4`
- **THEN** neither row has a mark, and the line above the chapters says that missing and ignored clips cannot be
  marked

#### Scenario: Marking by touch next to the Watch button
- **WHEN** on a touch screen 390 pixels wide, on `2024-08-20 - Två kapitel - Tjörn`, the operator taps in a
  44 × 44 pixel area centred on the box of `Kvällen/s1710002.mp4`, which sits over the top right of its Watch button
- **THEN** the clip is marked and its preview did not open
- **WHEN** the operator taps the middle of that thumbnail
- **THEN** the clip's preview opens and the mark is unchanged

#### Scenario: Marks are not an unsaved change
- **WHEN** on `2024-06-27 - Grillning med grannar` the operator marks `s1710001.mp4` and `s1710003.mp4`, and then
  leaves Edit mode
- **THEN** no question about unsaved changes was asked and the save bar was never shown
- **WHEN** the operator enters Edit mode again
- **THEN** no clip is marked and the line shows no count

#### Scenario: A mark with the keyboard only
- **WHEN** using only the keyboard on `2024-06-27 - Grillning med grannar`, the operator tabs to the mark of
  `s1710002.mp4`, which shows a focus ring, and presses Space, and then tabs to Clear marks and presses Enter
- **THEN** "s1710002.mp4 marked. 1 clip marked." and then "Marks cleared." were announced, and keyboard focus is on
  the line above the chapters (reachable by script, not by Tab), not lost to the page

#### Scenario: Marks are held while a save is pending
- **WHEN** on `2024-06-27 - Grillning med grannar`, after moving `s1710004.mp4` up one place, the operator presses
  Save and the service has not answered yet, and then presses a clip's mark
- **THEN** the mark does not change, and it is aria-disabled, not `disabled`

#### Scenario: A mark survives other edits and ends on Save
- **WHEN** on `2024-06-27 - Grillning med grannar` the operator marks `s1710002.mp4`, moves `s1710001.mp4` down one
  place, shows the Cuts of `s1710002.mp4`, and then saves
- **THEN** `s1710002.mp4` was still marked after the move and after the Cuts panel, and after the save no clip is
  marked

#### Scenario: Marking in a long chapter
- **WHEN** in a Chromium window 1280 × 900, on an event whose one chapter plays 400 clips, the operator marks the
  200th clip, five times, each in a fresh Edit mode
- **THEN** the median time from the press to the next painted frame is at most 100 ms

### Requirement: Dragging a marked clip moves the whole marked group

While two or more clips are marked, lifting any marked clip SHALL lift all marked clips, in each of the ways a clip
is lifted ("The event page reorders clips within a chapter", "Edit mode drags clips between chapters"): by its handle
with a mouse, pen or touch, and from the keyboard on its handle. Only a marked clip's handle lifts a group. Lifting an
unmarked clip SHALL lift that clip alone, with the marks left as they are, and a drag of one marked clip while no other
is marked SHALL be a drag of that clip alone. A drag SHALL still start only from a handle, and a coarse-pointer
scroll that starts anywhere else SHALL scroll the page.

The **group** is every marked clip, from every listed chapter, in page order: the chapters as listed, and in each its
play order. A drop SHALL be one edit. The group SHALL leave the chapters it was in, and SHALL join the chapter it is
dropped in as one run, in its page order, at the place of the drop. The place is a **gap** of that chapter: the line
above one of its clips, or the line after its last clip, or the area of a chapter that plays none. The run SHALL go
before the first clip at or after the gap that is not itself in the group, or at the chapter's end when there is none.
Every clip that is not in the group SHALL keep its order and its chapter. A chapter that loses all its clips SHALL
play none.

Every chapter, the group's own too, is a target of gaps while a group is held:

- the page SHALL show the line at the gap, and for a chapter that plays none its area marked as the target, in the
  own chapter as in another
- no row SHALL move to make room, in any chapter, and no part of the page SHALL change size or place
- a copy of the lifted clip SHALL follow the pointer, naming the number of clips and the target chapter and the
  position the run would start at out of the number of clips that chapter would then play ("3 clips to “Main”,
  starting at position 1 of 4"); within the group's only chapter it SHALL name the position without the chapter
- every held row SHALL be marked as held, by words available to assistive technology and by dimming, and the lifted
  clip's own row SHALL be marked as the clip being moved; no row's position number SHALL change while the group is
  held
- in forced colors, the line and the copy's edge SHALL stay visible

After the drop:

- each moved clip SHALL show the chapter it came from instead of its old position when it changed chapter, and SHALL
  count once as a moved clip in its new chapter's heading and in the save bar, as a clip moved with Move marked to… does;
  within a chapter the page SHALL count the fewest clips that explain the new order, as for any reorder
- a clip that returns to the chapter and place it had when Edit mode opened SHALL count as no move; with no other
  edit, the page SHALL show no unsaved changes
- each clip SHALL keep its cuts and its other per-clip properties, its Cuts panel shown or hidden as it was, and any
  time typed but not added
- Save SHALL write the order as it writes the order after Move marked to…, and Reset, the unsaved-changes question, a
  conflict and Overwrite SHALL treat it as any other edit
- the moved clips SHALL be unmarked, and keyboard focus SHALL be on the lifted clip's handle in its new place, with the
  row's first line fully visible, below the page header and the chapter's heading and above the save bar
- a drop that leaves every chapter's order as it was SHALL change nothing, SHALL leave the marks, and SHALL be
  announced as unchanged

From the keyboard, a held group SHALL be moved through the gaps of every chapter in page order with the Up and Down
arrows, and to the first gap of the next or the previous chapter with Page Down and Page Up, as a clip is moved across
chapters; Escape SHALL cancel. The instructions for a keyboard drag SHALL say, while two or more clips are marked, that
a marked clip moves with all the marked clips.

Every lift, target, drop and cancel SHALL be announced to assistive technology: "Picked up 3 marked clips.", "3 marked
clips are over “Main”, starting at position 1 of 4.", "3 clips moved to “Main”, starting at position 1 of 4.", "3
marked clips dropped, unchanged." and "Move cancelled. 3 marked clips are back where they were." Within the group's
only chapter a target is spoken as "starting at position 2 of 4" without the chapter's name.

No group SHALL be lifted, and a drop SHALL move nothing, while a save is in flight or a move of marked clips is being applied.
A release over a deleted chapter's placeholder SHALL move nothing and SHALL be announced as unchanged. A cancelled
drag SHALL leave the marks. While a pointer holds a group, no other part of the page SHALL show the pointer over it
and the pointer SHALL show that it holds the clips, as for a clip. Under reduced motion the copy SHALL NOT slide between
positions. In a window 320 CSS pixels wide or wider, in both color schemes, no state of a group drag SHALL make the page
scroll horizontally. Dropping a group of 50 clips into another chapter on a page whose chapters play 400 clips SHALL
reach the next painted frame within 150 ms longer than dropping one clip there (the median of five runs, in a Chromium
window 1280 × 900).

#### Scenario: Dragging two marked clips into the chapter above
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn` the operator marks `Kvällen/s1710002.mp4` and
  `Kvällen/s1710003.mp4`, drags the handle of `Kvällen/s1710003.mp4` up into `Main` and holds it over the upper half
  of `s1710001.mp4`
- **THEN** a line shows above `s1710001.mp4`, the copy says "2 clips to “Main”, starting at position 1 of 3", the
  two held rows are dimmed and marked as held, and no row has moved
- **WHEN** the operator releases it
- **THEN**
  - `Main` plays `Kvällen/s1710002.mp4`, `Kvällen/s1710003.mp4` and then `s1710001.mp4`, the first two marked as
    coming from `Kvällen`, and its heading says 2 clips moved
  - `Kvällen` plays the new `s1710004.mp4` alone
  - no clip is marked and the line above the chapters shows no count
  - keyboard focus is on the handle of `Kvällen/s1710003.mp4` in `Main`
  - "2 clips moved to “Main”, starting at position 1 of 3." is announced
  - the save bar says that 2 clips moved and that saving adds 1 new clip to `reel.yaml`

#### Scenario: A group from two chapters lands as one run in page order
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn` the operator marks `s1710001.mp4` (in `Main`) and
  `Kvällen/s1710003.mp4`, drags the handle of `Kvällen/s1710003.mp4` down, and releases it on the line after the last
  clip of `Kvällen`
- **THEN** `Kvällen` plays `Kvällen/s1710002.mp4`, the new `s1710004.mp4`, `s1710001.mp4` and then
  `Kvällen/s1710003.mp4` (the group in page order: `Main`'s clip first), `Main` plays no clip and shows its area for
  clips, and "2 clips moved to “Kvällen”, starting at position 3 of 4." is announced

#### Scenario: Moving a group within its own chapter
- **WHEN** on `2024-06-27 - Grillning med grannar` the operator marks `s1710001.mp4` and `s1710003.mp4`, drags the
  handle of `s1710001.mp4` and holds it between `s1710003.mp4` and `s1710004.mp4`
- **THEN** a line shows between those two clips, the copy says "2 clips, starting at position 2 of 4" without a chapter
  name, and no row moved to make room, including `s1710002.mp4`
- **WHEN** the operator releases it
- **THEN** the chapter plays `s1710002.mp4`, `s1710001.mp4`, `s1710003.mp4` and `s1710004.mp4`, the save bar counts
  the fewest clips that explain that order, nothing is marked, and "2 clips moved, starting at position 2 of 4." is
  announced
- **WHEN** the operator saves
- **THEN** `reel.yaml` lists the four clips in that order and no other line of the file changed

#### Scenario: A drop beside the group changes nothing
- **WHEN** on `2024-06-27 - Grillning med grannar` the operator marks `s1710002.mp4` and `s1710003.mp4` and drops them on
  the line between them
- **THEN** the chapter plays what it played, "2 marked clips dropped, unchanged." is announced, the save bar is not
  shown, and both clips are still marked

#### Scenario: Dragging an unmarked clip moves only that clip
- **WHEN** on `2024-06-27 - Grillning med grannar` the operator marks `s1710001.mp4` and `s1710002.mp4`, and drags
  the handle of the unmarked `s1710004.mp4` above `s1710001.mp4`
- **THEN** the chapter plays `s1710004.mp4`, `s1710001.mp4`, `s1710002.mp4` and `s1710003.mp4`, the other rows made
  room while it was dragged as they did before this change, and `s1710001.mp4` and `s1710002.mp4` are still marked

#### Scenario: One marked clip drags as a clip
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn` the operator marks only `Kvällen/s1710003.mp4` and drags its handle
  up into `Main` over the upper half of `s1710001.mp4`
- **THEN** the copy says it goes to `Main` at position 1 of 2 as for any single clip, `Main` plays
  `Kvällen/s1710003.mp4` and then `s1710001.mp4`, and the clip is no longer marked

#### Scenario: A group dragged back leaves nothing to save
- **WHEN** after the first scenario on `2024-08-20 - Två kapitel - Tjörn`, the operator marks `Kvällen/s1710002.mp4` and
  `Kvällen/s1710003.mp4` in `Main` again and drags them back to the line above the new `s1710004.mp4` in `Kvällen`
- **THEN** both chapters play what they played when Edit mode opened, no row is marked as moved, and the page shows no
  unsaved changes

#### Scenario: A group with the keyboard only
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, using only the keyboard, the operator marks `Kvällen/s1710002.mp4`
  and `Kvällen/s1710003.mp4`, focuses the handle of `Kvällen/s1710003.mp4`, lifts it with Space, presses Up
  until the gap above `s1710001.mp4` and drops it
- **THEN** "Picked up 2 marked clips." and "2 marked clips are over “Main”, starting at position 1 of 3." were
  announced before "2 clips moved to “Main”, starting at position 1 of 3.", `Main` plays the two clips and then
  `s1710001.mp4`, and keyboard focus is on the handle of `Kvällen/s1710003.mp4` in `Main`
- **WHEN** the operator repeats the lift on the marked clips in `Main` and presses Escape
- **THEN** "Move cancelled. 2 marked clips are back where they were." is announced, the order is unchanged, and the
  clips are still marked

#### Scenario: Page Down takes the group to the next chapter
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn` the operator marks `s1710001.mp4` and `Kvällen/s1710003.mp4`, lifts
  `s1710001.mp4` from the keyboard and presses Page Down
- **THEN** "2 marked clips are over “Kvällen”, starting at position 1 of 4." is announced and a line shows above
  `Kvällen/s1710002.mp4`

#### Scenario: No group while a save is in flight
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, with two clips marked and an unsaved reorder, the operator presses
  Save and the service has not answered yet
- **THEN** pressing Space on a marked handle lifts nothing and announces nothing, a mouse drag from it moves
  nothing, and every chapter stays as it was

#### Scenario: A group dragged by touch
- **WHEN** on a touch screen 390 pixels wide, on `2024-08-20 - Två kapitel - Tjörn`, with `Kvällen/s1710002.mp4` and
  `Kvällen/s1710003.mp4` marked, a touch starts on the handle of the first and moves up into `Main` above
  `s1710001.mp4` before it lifts
- **THEN** `Main` plays both clips first, and the page did not scroll horizontally
- **WHEN** a touch starts on a marked clip's name and moves up
- **THEN** the page scrolls and no clip moves

#### Scenario: Reaching a long chapter with a group
- **WHEN** an event holds 400 clips in its own chapter and 3 in a second chapter, `Kväll`, the operator marks the
  second chapter's first two clips, lifts one with the pointer and holds it at the window's top edge
- **THEN** the page scrolls up as for one clip ("Edit mode drags clips between chapters"), and releasing the group over
  the upper half of the first chapter's first clip puts both at positions 1 and 2 of 402 there, leaving `Kväll` with 1
  clip

#### Scenario: A held group changes nothing's size
- **WHEN** in a window 320 pixels wide, in the light and in the dark scheme, on `2024-08-20 - Två kapitel - Tjörn`, the
  operator holds the marked `s1710001.mp4` and `Kvällen/s1710003.mp4` over `Kvällen`, between `s1710002.mp4` and the new
  `s1710004.mp4`
- **THEN** every clip row and both chapter panels keep the size and place they had before the drag, the line between
  the two clips is visible beside the copy, no position number changed, and the page does not scroll horizontally

#### Scenario: A group drop is fast
- **WHEN** in a Chromium window 1280 × 900, on an event whose first chapter plays 400 clips and whose second plays 3, the
  operator marks 50 clips of the first chapter and drops them into the second, five times in a fresh Edit mode each
- **THEN** the median time from the release to the next painted frame is at most 150 ms longer than that of dropping
  one unmarked clip from the first chapter into the second

### Requirement: Edit mode chooses the event's poster on the Timeline
In Edit mode the Timeline SHALL offer **Use as poster**. Pressed, it SHALL set the draft's poster to the clip
under the playhead and the playhead's time in that clip, in seconds to the millisecond and before the clip's cuts
(a time inside a cut is allowed), and SHALL take the frame the Timeline's video shows as the draft picture of
the poster area. It SHALL be disabled, with the reason in words, when the playhead is outside every clip (the playhead
never rests on a title-card block: it stays on footage), when the video has no decoded frame at the playhead, and while a save or a move of marked clips is pending; a snapshot that fails SHALL change nothing and say so. Keyboard focus SHALL stay on the button and the
change SHALL be announced once.

Edit mode's **poster area** (a Poster panel above the Timeline; the page header's cover belongs to the read view) SHALL say what the poster is:
**Default: first clip** when the draft has no poster, **Chosen frame** when it has one as saved, and **Chosen
frame, not saved** for a draft that differs from the saved one. **Use default** SHALL remove the draft's poster and
SHALL be unavailable when there is none. The poster is a part of the one draft: Save writes `poster` with the
existing editorial write (`poster: {clip, at}`, or `null` to remove, and nothing when the poster was not
changed), Undo of the poster and Reset restore the saved one, an unmodified draft writes nothing, the save bar
says "poster changed", and Unsaved edits are never discarded silently. After a save the poster area shows the
image from the poster endpoint, not the snapshot. A poster whose clip the draft removes, moves out of the event
or ignores SHALL be marked in the poster area ("this clip does not play, the default is used") and SHALL NOT be
rewritten silently. A chosen clip that the detail reports with a `poster_note` SHALL show that note. Clips whose
rotation the page shows turned (`rotate`) SHALL be snapshotted and shown turned.

#### Scenario: Use as poster sets the draft from the playhead
- **WHEN** the playhead is at 0:12.500 of `s1710002.mp4` in Edit mode and Use as poster is pressed
- **THEN** the draft's poster is that clip at 12.5 s, the poster area shows that frame as "Chosen frame, not
  saved", the save bar says "Poster changed", and focus is still on the button

#### Scenario: Saving writes the poster once
- **WHEN** the draft's poster is changed and Save is pressed
- **THEN** one `PUT …/reel` carries `poster: {clip, at}`, a save of an unchanged poster carries none, and the poster
  area then shows the served image as "Chosen frame"

#### Scenario: Use default removes the chosen frame
- **WHEN** an event with a saved poster is edited, Use default is pressed and Save is pressed
- **THEN** the write carries `poster: null`, the area says "Default: first clip", and Reset before Save restores
  the saved poster

#### Scenario: The button is off where it cannot act
- **WHEN** a save is pending, an open clip preview holds the page's video, or the video has no decoded frame
- **THEN** Use as poster is disabled and says why

#### Scenario: A rotated clip is chosen turned
- **WHEN** the clip is shown turned and Use as poster is pressed on it
- **THEN** the draft picture is turned the same way

#### Scenario: The same behavior in Chrome and Firefox, in both schemes, at 1280 and 390 px
- **WHEN** the steps above are run in Chrome and in Firefox, light and dark, at 1280 and 390 px width
- **THEN** each has the same words and results, nothing overflows, and every control is large enough to touch

#### Scenario: Reading does not write
- **WHEN** the list, the page and Edit mode are opened and the Timeline's playhead is moved without pressing Use as
  poster
- **THEN** no request other than reads is sent

## REMOVED Requirements

### Requirement: Edit mode moves clips to another chapter
**Reason**: The per-chapter Move clips button and its dialog (with Pick all and Pick marked) are redundant since the
operator marks clips and drags the group ("Edit mode marks clips to move together", "Dragging a marked clip moves the
whole marked group"). Its non-drag job is taken over by Move marked to… in the marks line.
**Migration**: Mark the clips to move, then use Move marked to… (choose the chapter, press Move) or drag a marked clip's
handle. A move to the end of a chapter is the same edit as a drop there.
