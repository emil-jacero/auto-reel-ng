# `web/` — the browser client (GUI v1)

React 19 + Vite + TypeScript, built ahead of time into static assets that
`auto-reel serve` mounts at `/` (decision **D-8**, HLD §4.10). **No Node process
exists at runtime** — the deployment stays the single Python process, and the
service starts normally when `dist/` is absent.

Two screens so far. The **event list** (slice B of §4.10) answers
"which events need a render, and why": every event grouped by year, its clip
counts, its staleness verdict with reasons in words, and its latest job. A click
anywhere on an event's row (not on its controls, and not one that selects text)
opens its **event page** (slice C) at `#/event/<id>`, as its title does; the title
link stays the row's one keyboard stop. Two events that would read the same (the
same date, title and location, ignoring case) also show their folder's path, for
example `2024/2024-07-14 - Kalas`, and say that they read the same as another
event; the title link is described by both, the note first, since two paths can
differ only in a letter's case, which screen readers do not voice. An empty
library says so and how to add an event; when the Needs render choice hides every
event, the list says nothing needs rendering and offers **Show all events**, which
hands focus back to the All choice.
Each finished read and each filter change is announced with the counts. The event
page shows the event's facts, with the folder name beside a title that differs from
it; one render region holding the verdict and the latest job (when the verdict says
"movie name changed", because the title, date or location changed since the last
render, it adds on a line of its own that the next render saves the movie under its
new name and that the movie under its old name stays on disk, naming both files as the
service sent them); then the **Movie**
section, when the event has a rendered movie; then its chapters, each listing the
clips it plays, numbered in play order, and then its ignored clips, unnumbered. Each
clip shows its status (an included clip's quietly, so the exceptions stand out), size
and time; a clip from another folder is named by its path in the event folder; and any
clip `reel.yaml` lists that is missing from disk is named. A clip with **cuts**
(`reel.yaml`'s `trims`: spans the movie leaves out, D-D) shows, under its name, how
many and the time they cut out ("2 cuts · −4.5 s"), a disclosure (`<details>`) that
lists them; the page reads them with `GET …/reel` after each event read, writes
nothing, and if that read fails shows the clips without cuts and a note that says why.
The Movie section (D-15) shows when the verdict cites neither `no_manifest` nor
`output`. It plays the movie in the browser's own player, says whether it is
**Current** or **Outdated**, and names its file and size as the movie route's one-byte
answer gives them (the old name after a rename). Nothing of the movie loads before
Play (`preload="none"`; the poster is the first played clip's thumbnail). The player's
address carries the file's entity-tag, so a new render gets a new player. What it
cannot play is said by cause (no file, unreadable, empty, no answer, no picture, a
failed load or a browser error, a file changed while it played), with Try again, a
download or the new movie to load. Its facts also say "Recorded {time} · version
{fingerprint}" from the event detail's `movie`, and under them a **Chapters** jump list
(`movie/ChapterList.tsx`) when `movie.chapters` gives two or more it can rely on
(`movie/chapters.ts`: starts that strictly increase, no blank name; none is computed on
the client, and a movie rendered before chapter times were recorded gets no list). A
row's button seeks to the chapter's start and plays, also before the first Play; the
current chapter is marked "Current chapter" (words and an icon, `aria-current`), follows
the player's position and is never announced; an outdated movie's list says "As
rendered". A Refresh keeps the player (the same `<video>`,
playing or paused, while the rest of the page reads; its verdict and facts are hidden
until the read answers); Edit mode stops playback. The list
and the page read on open and on Refresh — no timer polling (job state arrives
over the jobs WebSocket), never a cache — and report a failed read by its cause,
telling a service that did not answer ("not reachable", with what to check) from
one that sent an answer its route does not publish ("an unexpected answer", with
the request, its path decoded, the status, and where to look). Each clip row, on
the event page and in Edit mode, shows a frame from its clip (the service's
thumbnail, D-11; 80 × 45, and 128 × 72 in the chapter tables at desktop width):
requested only
as its row nears the view and behind the page's own requests, in a box sized before
it arrives, and kept by the browser while the clip is unchanged. A frame the service
cannot give shows "No preview"; a missing clip asks for none and shows an empty
outline. A frame that failed asks once more why: when three or more fail with the
service's own cause (a 502 with no thumbnail failure kind and no event failure), the page adds one quiet
note, "Previews are unavailable", pointing to `auto-reel thumbs`. The list stays mounted while an event page is
open, so Back returns to it without a new read —
unless the client recorded meanwhile that an event changed (`markEventsChanged()`
in `events/changes.ts`, called by the slices that write or render): then the list
reads again when shown, in place, keeping its rows, filter and scroll until the new
read answers. Every page sits in one shell: a sticky header with the Events link,
the jobs connection (Live, Connecting… or Reconnecting…, and while live how many
jobs render and wait) and a System / Light / Dark theme control, remembered per
browser (see "Design system").

**Rendering** (slice E). An event's page offers **Render** when it needs a render,
or **Render anyway** (confirmed) when it is up to date, and follows the job live:
waiting for a worker, a progress bar with its percentage and a time-left estimate,
cancelling, and how it ended — a failure with the service's error text. Every job
shown is dated by its state — when it finished (rendered) or ended (failed or
canceled), started or was queued — whether it came from the connection or a read. **Cancel**
stops a queued job at once and asks first for a running one, and for any job while the
connection is down. Each list row shows its
event's job live and offers a compact Render; a finished render re-reads the list and
the page in place, keeping what is shown until the new read answers. One WebSocket
per tab (`src/jobs/store.ts`) carries every job, reconnects by itself (also when it has seen no
frame for 40 s: the service sends a heartbeat after 15 s of silence), and reads once any
job that ended while it was down. A row's Render is confirmed to assistive technology
only, since the row shows its job and a toast would cover the rows below; toasts, naming
each event by its title and date, tell how renders started in the tab ended.
Jobs progress only while an `auto-reel worker` runs against the same database; with
none, a job shows "Waiting for a worker". While an event's `reel.yaml` lists a clip
missing from disk, its render would fail, so neither the page nor the row offers one:
the page says which clip (or how many) and to restore it or remove it in Edit mode,
and the row says "Blocked by missing clips". A job already queued keeps its Cancel.
Both screens hold Render back from their last read of the event, so a clip that vanished
since is refused by the service instead (a 409 `missing_clips`, which Render anyway cannot
override): the page says the render was not queued and names the clips, a row raises a
toast naming them (three, and how many more), and both re-read so their own guard takes over.

The event page's **Edit mode** (slice D) is the client's first write. **Edit** reads the
event's `reel.yaml` (`GET …/reel` and its `ETag`) and turns the page into an editor: the
title, date, location and description as `reel.yaml` itself says them (an empty field
inherits from the folder name, and says so), and each chapter's clips as a list to
reorder — drag a clip's handle (mouse, pen or touch), lift it from the keyboard (Space
or Enter, the arrows, Space or Enter; Escape cancels), or press its Move up / Move down.
The rows keep the table's columns (`--clip-*`), so entering Edit mode moves nothing but
the position number, and they name each clip as the table does (`clipNames`), a folder
part included where a chapter lists a clip from another folder. **Marks** (`clip-group-select-drag`): a
box at each clip frame's top right marks it (not for missing or ignored clips); dragging
a marked clip's handle, or lifting it from the keyboard, moves every marked clip, in page
order, to the drop position as one edit, and Move clips' Pick marked picks them; marks
are not a change to save and clear after a move or a Save. A drag can also take a
clip into another chapter (`cross-chapter-drag`; one `DndContext` around every chapter,
`edit/ChapterDrag.tsx`), by pointer or keyboard: dropped before any of its clips or after
the last, the clip lands exactly there, as one edit with Move clips' rules (the "from"
badge, the counts, the save body). Over another chapter nothing moves: a line marks the
gap, and a copy of the clip follows the pointer naming the chapter and the position;
past a chapter's first or last clip the arrows cross into the chapter before or after,
passing over a deleted one, and Page Down / Page Up jump to the first position of the
next or the previous chapter. Held near the window's top or bottom edge, a pointer
scrolls the page, at the window's edge at most about 2,000 px/s (faster if the pointer
is held outside the window). A chapter that plays no clip shows an area to drop clips
on. A missing clip stays in its chapter, a deleted chapter's placeholder takes nothing, and
no drag starts while a save or a Move clips is pending. Move up / Move down never take a
clip into another chapter; ignored clips are listed but never move. Each chapter's own
tools row, under its heading, edits the chapters themselves
(**D-13**): a chapter is renamed at its **title**, a button with a pencil that becomes a
text field (Enter or leaving it keeps the name, Escape drops it; the event's own chapter
keeps its name, and shows a **Main title card** line whose title is the event's, edited in
the same draft as the Title field), **Move up** / **Move down**, **Delete** (only once the
chapter plays no clip, and for the event's own chapter only once it lists no ignored
clip; until Save it stays in its place with **Undo**), and **Move clips…**, a dialog
that moves the picked clips (on disk only, checkboxes, Enter moves) to the end of
another chapter, a clip moved back returning to its place. **Add chapter** follows the
last chapter. A name is trimmed, must not be empty, and must differ, ignoring case,
from every other chapter's name and from `Main`. Wherever an edit changes what a name
means for clips added to a folder later (D-12: they join the chapter named exactly
after their folder, else the event's own), the name field (or the Add chapter dialog) and the chapter say so. A name typed and not kept
holds Save back, as a cut typed and not added does. A
save that changes the chapter list writes every chapter as shown, so every NEW clip
joins `reel.yaml` where the page shows it. A clip moved in shows where it came from;
a chapter saved without clips reads "No clips" on the event page. A chapter's heading counts the clips
it plays; its removed and ignored lists count their own. A missing clip (listed in
`reel.yaml`, not on disk) has a **Remove**, under its name (after its facts on a narrow
panel), that takes it out of the play order into a list captioned, for example, "1 clip
removed from reel.yaml when you save", with **Undo** until Save; Save then drops only
its `reel.yaml` entry and its own per-clip properties, and no file on disk is touched.
Every clip on disk that a chapter plays has a **Cuts** control after its move buttons
(under its name on a wide panel; under the handle, with the count only, on a narrow one)
that shows a panel under the row (**D-14**): the clip's cuts (start → end, length, the
reason in words; `manual` reads "Cut by hand") and two typed times, as seconds (`75.5`),
`m:ss` (`1:15.5`) or `h:mm:ss` (`1:01:15.5`), with up to three decimals after `.` or `,`.
**Add cut** refuses, at the field and in words, a time it cannot read, an end that is not
after the start, and an overlap with another cut. The panel knows a clip's length from its
preview (below) once Watch has read it, else from the `duration` the event detail carries
(the length measured when the clip's thumbnail was made; `null` until one was, and only the
detail read after that carries it, so on a first visit to an event the thumbnails Edit mode
asks for show up in the detail only on the next read, for example a reload). With a length
the panel says where the clip ends, refuses a cut that ends after that, and marks a listed
one that does ("Past the clip’s end"); without one it says the render stops a cut past the
clip's end there and that a cut over the whole clip leaves the clip out (and, if it is its chapter's
title clip, moves the chapter's title card to the next clip that plays), and accepts the cut.
A cut made here is saved with the reason
`manual`. **Remove** keeps a cut read from `reel.yaml` listed, struck through, with
**Undo** (refused, in words, when another cut now overlaps it); a cut added in this Edit
mode just goes. A time typed but not added counts as unsaved, is named in the save bar
("Cut typed on s1710001.mp4, not added"), marks its clip's Cuts control "typed" (also
while the panel is hidden) and holds Save back, as a date typed in part does; it survives hiding the panel, Move clips and a drag into another chapter, since the editor, not the row, holds
the panel's state. A save writes only the changed clips' `trims` (their title-clip choice,
rotation and exclusion as read; no empty entry), and a cut on a NEW clip writes its
chapter, since `reel.yaml` refuses properties for a clip no chapter lists. A missing
clip shows how many cuts it has, and offers no Cuts control.
The panel's first control, **Watch**, opens the clip's preview there (**D-16**,
`preview/`); in Edit mode the clip's thumbnail is a "Watch <name>" button that shows the
panel and opens it in one press (not the drag handle; the box keeps its size). One preview
is open at a time, and none exists until asked for: no `<video>` and no request to the
media route (`GET …/media?clip=&v=<mtime>`, `api/clipMedia.ts`) before Watch, on any
number of clips. The preview has its own controls on a native `<video>` (no `controls`, no
autoplay, the thumbnail as poster): Close (Escape too; focus returns to the opener), Play
/ Pause (a press while the clip loads plays it once it can; an opened preview says when it
is ready), a playhead slider (Space plays or pauses, arrows 0.1 s, Page Up / Page Down 1
s, Home / End; a press or a drag along it; it says `0:01.234 of 0:06.02, in cut 2`, at
most once a second while playing), **Skip cuts**, **Set From** and **Set To**. Under the
picture, a cut bar draws the clip's cuts by shape (solid, a removed one dashed, the span
typed in the fields outlined, only while Add cut would accept it) with a legend of the
kinds drawn. While a preview is open, the panel's Watch reads **Hide player**. Set From /
Set To write the playhead's time to the millisecond in the panel's format; it counts as
typed, so the typed mark and the save bar's hold apply. Skip cuts plays the clip as the
movie will: two frame intervals ahead of each presented frame
(`requestVideoFrameCallback`), so a dropped frame never lets a cut frame show (the one
kept frame just before a cut may go unshown), cuts joined as the render joins them, and a
cut that ends within 0.1 s of the clip's end stops playback at its start. The preview's
length is the browser's own read of the file (`loadedmetadata`, `durationchange`), kept per
media address for the Edit session, never sent or saved; once read it wins over the detail's
`duration`, since Set From and Set To write times in it. What the browser cannot do is a note,
announced once: no sound (Firefox and the Sony cameras' PCM audio), no picture (HEVC,
MPEG-4 Part 2, with a Download), and, after one `Range: bytes=0-0` read of the media route
(`api/probe.ts`, the movie probe's own table), why a clip cannot play: gone from disk or
changed since the page was read (stop editing to read the event again; never "Refresh",
which leaves Edit mode), an empty file, an unreadable one, a format this browser does not
play (Download), or no answer (Try again). A preview writes nothing; a pending save or
Move clips makes Set From / Set To unavailable but leaves playback alone; a clip moved
within its chapter keeps playing, and one moved to another chapter reopens paused where it
stood; Reset closes every preview.

**Play on the event page** (GUI v2, **D-16**, `events/ClipWatch.tsx`, change
`clip-play-overlay-one-player`): outside Edit mode, every clip row whose file is on disk (any
status but missing; an ignored or an excluded clip too) has a **play control on its
thumbnail**: a button over the whole frame with a play glyph in a disc, named "Play <name>"
(there is no button in the file cell). The glyph is seen on hover, on keyboard focus, while the
player is open and always without a fine hovering pointer; the button is always in the tab
order, and a press or tap anywhere on the frame reaches it. It opens the same preview
component as Edit mode's Watch (not a fork) in a row of its own under the clip's row, as wide
as the table and named "Player for <name>": the preview copy when one is ready, else the
original, with Play original and the Firefox no-sound note exactly as above. While the player is
open the control shows the hide icon and is named "Hide player of <name>", so it never shares a
name with the player's own "Play <name>" / "Pause <name>". The player does not play by itself
when it opens. One player is open at a time; Close and Escape return focus to the control;
nothing loads (no `<video>`, no media, proxy or filmstrip request) until a press, on any
number of clips. The player is **read-only**: it is given no `onSet`, so it has no Set From /
Set To; the clip's cuts (the ones the page's cuts indicator already reads from `reel.yaml`;
none for an excluded clip) are drawn on the bar, and **Skip cuts** stays as a view option for
a clip that has one. A clip that is gone or changed on disk says "Press Refresh to read the
event again, then watch the clip anew" (never "stop editing"). Its words are announced through
the read view's own live region. A quiet re-read (a job ended) leaves an open player playing; a
clip replaced on disk continues paused at the same time on its new file; a copy built
meanwhile does not change the file under the operator; a clip that went missing closes its
player and moves focus to its row (to the heading when no row is left). Refresh and Edit mode
close it.

**One video plays at a time** (`playback/coordinator.ts`, installed once in `main.tsx`): one
capturing `play` listener on the document pauses every other playing `<video>` of the page. No
player claims or releases anything, so the Movie section's player, a clip's player in the read
view, a clip's preview in Edit mode and the Timeline are covered without being named, and so is
a player added later. It only pauses: nothing is closed, replaced, restarted or seeked, and
nothing is announced. The Timeline's one extra rule: when another video starts while its file
changes at a clip boundary, it stays paused (`resumeOrYield` in `timeline/follow.ts`).

**Which file plays** (GUI v2, **D-16**/**D-21**, `preview/source.ts`): the clip's **preview
copy** when the event detail's `proxy` says `ready` with a usable `facts.duration`, else the
original, with a line under the picture that says which plays and why when it is the
detail's doing (out of date, could not be built, no usable length). The choice is made from
the detail alone: a clip with no ready copy costs no request. The copy's address carries its
entity tag as `v`, read with one `Range: bytes=0-0` request when the preview opens
(`probeProxy`, D-15), because Chrome fails a replaced file at an address that served the old
one. A ready copy adds the last control, **Play original** / **Play preview copy**: it
swaps the file under the playhead (same media time, playing stays playing, focus stays on
it, announced), the choice follows the clip to another chapter and is forgotten when the
preview closes. The copy has AAC, so the Sony PCM clips have sound in Firefox: the no-sound
note belongs to the original and, with a ready copy, points at Play preview copy. While the
copy plays the clip's length is `facts.duration` (the original's, as probed), not the
browser's reading of the copy, which is about 20 ms off and can be shorter. A copy that
cannot play is told by cause (gone, unreadable, empty, refused, no answer), never as "changed
on disk", with Play original beside Try again. Sound from a Sony PCM clip: the copy plays it
in every browser; the original in Chrome and WebKit, not in Firefox. Verified in Chrome
(channel `chrome`, the image
`localhost/playback-research:chrome`) and Firefox; Playwright's own Chromium cannot decode
H.264. A
save bar says what changed, with one primary action: **Save**, or a failure's way
on while it holds Save back (Reload latest after a conflict, Back to the event list for
a vanished event). It is held at the window's bottom while it takes at most two fifths
of the window and the window is at least 28rem (448px) tall, which leaves room for the
sticky header, a chapter heading and a whole clip row; otherwise (a failed save in a
short window, any bar at 400 % zoom) it rests in the page after the last chapter. A
save's answer, and every zoom or resize while the bar rests, keeps its focused control
in the window, unless the operator scrolled it away (a `resize` that changes no size,
as a phone's URL bar fires, is ignored). Keyboard focus that lands partly hidden
(outside the window, or under the sticky header, a chapter heading or the held bar;
the description field, whose caret alone the browser would scroll to) is brought into
view whole; focus from a pointer press never scrolls, so the press lands where made.
Ctrl+S (Cmd+S on a Mac) saves from anywhere on the page in Edit mode, says why in the live
region when Save is held back, and is left to the browser outside Edit mode (the button's
`aria-keyshortcuts` and tooltip name it; the rules are in `edit/saveShortcut.ts`).
Save sends one whole-document `PUT` under `If-Match` with only the
operator's edits applied (`edit/draft.ts`); a failure keeps the edits and says why, in a
compact alert inside the bar that fits a 320px window (a third of a phone's height for a
conflict, two fifths with the service's full detail), and a conflict offers Reload
latest or Overwrite with mine. A save that gets no answer says the service is not
reachable, without the browser's error text, and an error in the page itself says so,
never "not reachable". A successful save is confirmed by a toast that names the event by
its title and date. When the `reel.yaml` read fails, **Try again** keeps the failure and
its focus while it reads, then moves focus to the fields' heading. A save never enqueues
a render. The list's "Needs attention" folder names open their event's page; when an
event's date or title is unusable, that page shows the failure and a form to fix them.

Unsaved edits are never discarded silently: closing or reloading the tab gets the
browser's own prompt, and Back, Forward, a link, a typed address, Refresh and Stop
editing ask "Discard unsaved changes?" first. Each history entry the client accepts
carries its index in `history.state` (`route.ts` stamps the entry shown when the app
loads, and each new one), so a refused Back or Forward is undone by going back the
other way and the history stays as it was; Discard redoes the move. A refused link or
typed address stays behind as a Forward entry. While a save is in flight nothing
leaves: Refresh and Stop editing wait, and a navigation is undone with a note that
the save is still running.

```
src/
├── main.tsx              mounts App; imports styles/index.css first
├── App.tsx               the route switch inside the shell; keeps the list mounted
├── route.ts              hash routes (#/event/<id>) and the unsaved-edit navigation guard — no router library
├── format.ts             formatInstant: the one way every time is written (see "Design system")
├── styles/
│   ├── index.css         the cascade layer order, then the four files below
│   ├── reset.css         box sizing, zeroed margins; [hidden] always wins
│   ├── tokens.css        colors (OKLCH, light-dark()), spacing, radii, type, motion
│   ├── base.css          elements, typographically only
│   └── components.css    buttons, panels, data tables, pills, alerts, dialog, toasts
├── shell/
│   ├── AppShell.tsx      skip control, sticky header, theme control, toast region
│   ├── theme.ts          System / Light / Dark, kept per browser
│   └── shell.css         the header and the page frame
├── ui/
│   ├── Icon.tsx          inline-SVG icons (Lucide paths, ISC; notice in the file)
│   ├── Pill.tsx          a status: icon + words on a tone
│   ├── Alert.tsx         an inline message: tone, title, detail, action
│   ├── Skeleton.tsx      placeholder rows, and the announced read status
│   ├── Clock.tsx         a running time in a fixed-width cell, and `Clip 0:00.96 of 0:39.84` as a pair (clock.ts writes it)
│   ├── Dialog.tsx        a modal over the native <dialog>
│   ├── returnFocus.ts    the rule for giving focus back to a dialog's opener (+ returnFocus.test.ts)
│   ├── toast.ts          the toast store: toast.success / info / error, keepToastsClearOf (+ toast.test.ts)
│   └── ToastRegion.tsx   where toasts appear (rendered once by the shell)
├── api/
│   ├── schema.d.ts       generated (see below)
│   ├── http.ts           shared response reading and problem parsing; no answer vs an unpublished one
│   ├── events.ts         the list fetch: URL, status codes
│   ├── event.ts          the one-event fetch: URL, status codes
│   ├── jobs.ts           enqueue, one job, cancel: URLs, status codes; the jobs WebSocket URL
│   ├── reel.ts           the editorial read and write: ETag in, If-Match out
│   ├── movie.ts          the event's movie URL (typed from the schema) and its one-byte probe
│   ├── headers.ts        Content-Range, Content-Disposition and entity-tag parsers (pure, no imports)
│   ├── probe.ts          one byte of a media route: the response-to-kind table the movie and a clip share
│   ├── thumbnail.ts      a clip's thumbnail URL, typed from the schema; readFailedThumbnail reads why a failed one failed
│   ├── clipMedia.ts      a clip's media and preview-copy URLs, the copy's one-byte probe, and the read that says why a clip cannot play
│   ├── clipMedia.test.ts the copy's address and probe (npm test)
│   ├── proxies.ts        a clip's filmstrip URL and the proxy job's enqueue, with its answers as values (+ proxies.test.ts)
│   └── proxies.test.ts   the filmstrip address and every answer of POST …/proxies (npm test)
├── edit/
│   ├── EventEditor.tsx   Edit mode: the reel read, chapter edits, the save bar, saves and failures
│   ├── ChapterDrag.tsx   the one drag context around every chapter: sensors, targets, the copy, words, focus
│   ├── dragSlots.ts      where a dragged clip can land: slots, keyboard steps, pointer targets; a gap mode while a marked group is held (pure)
│   ├── marks.ts          Edit mode's marks: toggling, pruning, Pick marked, the words spoken (pure; marks.test.ts, groupMove.test.ts)
│   ├── ClipOrderList.tsx one chapter's clips: its sortable list, a drop target, buttons; Remove / Undo
│   ├── ChapterTools.tsx  a chapter's tools row, a deleted chapter's placeholder, Add chapter
│   ├── ChapterDialogs.tsx the name dialog (Add chapter) and Move clips
│   ├── InlineName.tsx    a title that is its own rename control: button, field, keep / drop / refuse
│   ├── inlineName.ts     the keep / unchanged / refused rule, the title line, the unkept-name test (pure, + inlineName.test.ts)
│   ├── TitleCard.tsx     the event's own chapter's Main title card line, over the draft's title
│   ├── chapterNames.ts   chapter name rules and what a name means for later clips (pure)
│   ├── MetadataForm.tsx  title, date, location, description, and inherited values
│   ├── SaveBar.tsx       the save bar and a failed save's alert
│   ├── saveShortcut.ts   Ctrl/Cmd+S: when Save cannot act, the chord, what a held-back press says (pure, + saveShortcut.test.ts)
│   ├── draft.ts          the edit model: chapters, write body, moved, removed and trimmed cuts, dirty (pure, + trimCut.test.ts)
│   ├── unsaved.ts        the unsaved-changes guard and its question
│   ├── chapters.css      the chapter tools, the deleted placeholder and the chapter dialogs
│   ├── drag.css          the dragged copy, the line where a drop lands, an empty chapter's area
│   └── edit.css          Edit mode's fields, rows and save bar
├── cuts/
│   ├── times.ts          typed times read and written, a cut's checks, the cut words and reasons (pure, + times.test.ts)
│   ├── CutsPanel.tsx     Edit mode's Cuts control and panel, and the cut list both views share
│   ├── ReadCuts.tsx      the event page's cut indicator and list, and the read of its cuts
│   └── cuts.css          the control, the panel and the event page's indicator
├── movie/
│   ├── MoviePanel.tsx    the event page's Movie section: probe, player, troubles by cause
│   ├── ChapterList.tsx   the chapter jump list under the player: jump, current mark (+ chapters.test.ts)
│   ├── chapters.ts       which chapter times may be relied on, the current chapter, jump words (pure)
│   ├── facts.ts          the detail's `movie`: listed chapters and version words (pure, + facts.test.ts)
│   ├── labels.ts         words and looks for the movie's age and troubles, MediaError words
│   └── movie.css         the section, its 16:9 frame and the chapter list
├── preview/
│   ├── previews.ts       the editor's previews: one open, its opener, kept playheads, lengths, the original chosen over a copy (pure)
│   ├── previews.test.ts  the override's life (npm test)
│   ├── source.ts         which file plays (copy or original) and the words that say so (pure)
│   ├── source.test.ts    the table and the words (npm test)
│   ├── playback.ts       skip spans, where playback goes per frame, slider keys, the preview's words (pure)
│   ├── playback.test.ts  Edit mode's words byte for byte, the read-only advice, when Skip cuts is offered (npm test)
│   ├── ClipPreview.tsx   a clip's preview, in the Cuts panel or (read-only) on the event page: the video, controls, cut bar, notes
│   └── preview.css       the preview, the cut bar, and the thumbnail as a Watch button (Edit mode)
├── playback/
│   ├── coordinator.ts    one playing video per page: a started video pauses the others; installed in main.tsx (pure, + coordinator.test.ts)
├── timeline/             the event page's Timeline (GUI v2, D-20): read only in the read view, trim handles in Edit mode; the pure modules have tests under npm test
│   ├── model.ts          time and pixels, zoom, windowing, cut spans, trim limits, snapping (whole ms; + model.test.ts, trim.test.ts)
│   ├── layout.ts         which clips, when a proxy is ready, chapter bands, drawn cuts, movie length, filmstrip tiles (pure)
│   ├── position.ts       the playhead as a clip and a time on its frame grid; steps across clip boundaries (pure)
│   ├── keys.ts           the playhead's keys (pure); follow.ts: playing through the cuts and into the next clip (pure)
│   ├── scrub.ts          the seek coalescer: one load or seek in flight, always ending at the last target (pure)
│   ├── playhead.ts       the playhead's external store; labels.ts: the Timeline's words, the Prepare answers (pure)
│   ├── handles.ts        what a key does to a trim handle, Enter at the playhead, which overlapping handle a finger meant, when a mouse press came without pointer events, what a snap says (pure, + handles.test.ts)
│   ├── dragStore.ts      the edge in the air while a handle is dragged: only the handle, its live span and the fields read it (pure)
│   ├── cards.ts          the title cards (pure): placement as the render does, the black-card track map, words, the selection reducer (+ cards.test.ts); CardLane.tsx draws the lane, CardInspector.tsx the slot, useCardSelection.ts the page's selection
│   ├── editing.ts        what Edit mode gives the Timeline: the draft's cuts, onTrim, onAdd, locked, the preview store (types)
│   ├── TrimHandle.tsx    a clip's trim handles: sliders with pointer capture, snapping and keys
│   ├── CutFields.tsx     the selected cut's Start and End, typed, in step with the handles
│   ├── TimelineSection.tsx  the section: Open / Close, then notes, Prepare or the track by what the proxies allow
│   ├── Prepare.tsx       the Prepare state and the proxy job's behaviour (usePrepare)
│   ├── Timeline.tsx      the open Timeline: the picture, transport, zoom and the track; Track.tsx, Filmstrip.tsx, Playhead.tsx
│   ├── useTimelineVideo.ts  the one <video>: src swaps, coalesced seeks, Play through cuts and clips
│   ├── useVisibleRange.ts   the track scroller's range, once per frame
│   ├── overlays/         the analysis lane (`timeline-overlays`): suggestions under their clips; approval, dismissal and restore in Edit mode (`timeline-overlay-decisions`)
│   │   ├── suggestions.ts       a suggestion's state from the cuts, the approval check, the decisions, the A / R keys, stacking over the track, roving order, words (pure, + suggestions.test.ts)
│   │   ├── control.ts           what the Timeline is given (`analysis`): the cuts as they are, the dismissals, how to decide; `decideControl` builds the decision from Edit mode's binding (+ control.test.ts)
│   │   ├── useAnalysis.ts       the one read of the analysis, when the track mounts
│   │   ├── useSuggestions.tsx   the hook `Timeline` calls: marks, lane, notes and the selected detail
│   │   ├── Dismissals.ts        the suggestions dismissed on this page visit (held by `EventDetail`)
│   │   ├── SuggestionLane.tsx, SuggestionDetail.tsx   the marks (buttons) and the detail with the decision buttons
│   │   └── overlays.css         the marks, their states and the detail
│   └── timeline.css      the section, the track, the cuts' hatch and the playhead
├── jobs/
│   ├── store.ts          the one jobs WebSocket: live jobs, reconnect + silence watchdog, endings (toasts, re-reads)
│   ├── useJob.ts         which job an event shows (live or last read); the event's proxy job; the connection's counts
│   ├── kinds.ts          renders vs proxy jobs: the newest of each per event, the header's render counts (pure, + kinds.test.ts)
│   ├── shownJob.ts       the rule that picks the job version to show: a read's requeue and cancel request are followed while the connection is down (pure, + shownJob.test.ts)
│   ├── status.ts         which job statuses are active (pure)
│   ├── eta.ts            the time-left estimate (pure)
│   ├── labels.ts         words for cancel outcomes, the connection and a held-back render
│   ├── JobsIndicator.tsx the header's connection state and counts
│   ├── announce.ts       what the slice tells assistive technology only (a row's Render)
│   ├── JobProgress.tsx   a job's status words, bar and figures
│   ├── RenderControl.tsx the event page's Render, Render anyway and Cancel region
│   ├── LiveJobCell.tsx   a list row's live job cell and compact Render
│   └── jobs.css          this slice's styles
└── events/
    ├── EventList.tsx     the list: load/refresh, summary, filter, year panels
    ├── EventDetail.tsx   the event page: status, counts, clip panels, the Edit toggle and the needs-attention form
    ├── ClipThumb.tsx     a clip row's thumbnail: lazy, loading, "No preview", missing
    ├── ClipWatch.tsx     the read view's play control (over the thumbnail), the player's row, and its live region
    ├── watch.ts          which clips can be watched; the play control's name; what a re-read does to an open player (pure, + watch.test.ts)
    ├── list.css          the list's layout and column widths
    ├── detail.css        the event page's layout, render region and clip column properties
    ├── thumbs.css        the thumbnail's 16:9 box and its states
    ├── loadState.ts      what the event page shows while it reads, and what a Refresh carries (pure, + loadState.test.ts)
    ├── thumbHealth.ts    the page's count of previews failing for the service's reason (the note), + thumbHealth.test.ts
    ├── common.tsx        helpers both screens share (file names, sizes, verdict, failure sentences) and clip names
    ├── changes.ts        "an event changed": markEventsChanged(), useEventsVersion()
    ├── grouping.ts       groupByYear, needsRender, lookAlikes (pure)
    ├── labels.ts         words for reasons, job statuses, failures, clip statuses, unanswered requests
    └── tones.ts          the tone and icon of each status (the words stay in labels.ts)
```

`labels.ts` maps each vocabulary through a `Record` over its generated union, so
a reason, job status, failure kind or clip status added, renamed or removed in the engine is a
`tsc --noEmit` error until it is given words.

## The Node toolchain runs in podman

Nothing is installed on the host — the same arrangement as the containerized
Postgres test fixture. Run all four commands from the **repository root**:

```bash
# install dependencies (writes web/node_modules/ and web/package-lock.json)
podman run --rm -v "$PWD/web:/app:Z" -w /app docker.io/library/node:22 npm install

# dev server on http://127.0.0.1:5173, proxying /api (and the WS) to the service;
# --network host is what lets the proxy reach 127.0.0.1:8080
podman run --rm --network host -v "$PWD/web:/app:Z" -w /app docker.io/library/node:22 \
    npx vite --host 127.0.0.1 --port 5173

# production build → web/dist/ (runs `tsc --noEmit` first)
podman run --rm -v "$PWD/web:/app:Z" -w /app docker.io/library/node:22 npm run build

# the frontend gate on its own
podman run --rm -v "$PWD/web:/app:Z" -w /app docker.io/library/node:22 npx tsc --noEmit

# the unit tests (Node's built-in runner, no DOM: the toast store, the dialog's focus rule)
podman run --rm -v "$PWD/web:/app:Z" -w /app docker.io/library/node:22 npm test
# `npm run check` (and `build`) also type-checks the tests (`tsconfig.test.json`)
```

`npm run dev` expects a running `auto-reel serve` on `127.0.0.1:8080` (its default
bind). To proxy to a service elsewhere, set `AUTO_REEL_API`, for example
`podman run --rm --network host -e AUTO_REEL_API=http://127.0.0.1:8101 …` with the
dev-server command above. Client code addresses the API **by path alone** — never
an absolute base URL — so the same code works behind the dev proxy and when the
service serves the built assets. Same origin either way; the service needs no CORS.
With the service down, Vite's proxy answers each request itself with a bare 500, so
under `npm run dev` the screens say the service sent an unexpected answer, where the
built client served by `auto-reel serve` says it is not reachable.

Two things to know when containers run side by side:

- `:Z` gives a mount a private SELinux label. A second container that mounts `web/`
  with `:Z` (for example `npm run build`) relabels it and cuts off a running dev
  server (`EACCES` on `.vite/deps`). Don't build while Vite runs, or mount with `:z`
  in both.
- Screens checked ad hoc in the Playwright container (never committed, see "Checks")
  render `system-ui` in a CJK fallback font with no bold face. For representative
  screenshots, copy the host's Noto Sans files into the mounted scratch directory and
  run with `-e FONTCONFIG_FILE=/work/fonts/fonts.conf`:

  ```xml
  <fontconfig>
    <include ignore_missing="yes">/etc/fonts/fonts.conf</include>
    <dir>/work/fonts</dir>
    <match target="pattern"><test name="family"><string>system-ui</string></test>
      <edit name="family" mode="assign" binding="strong"><string>Noto Sans</string></edit></match>
    <alias binding="strong"><family>sans-serif</family><prefer><family>Noto Sans</family></prefer></alias>
  </fontconfig>
  ```

## A library to develop against

The shared fixture holds one event, which cannot show what the screens must render.
`scripts/make_dev_library.py` builds a small real-footage library from it (the fixture
is only read). It cuts 6 s stream-copied clips and lays out 11 events across 2023 and
2024: 10 that list normally, plus 1 that needs attention. Part of the library is rendered through
the real queue, then disk is edited so the screens show every state:

- fresh, and stale for `editorial`, `output_renamed` (`2024-06-27 - Grillning med grannar`,
  retitled after its render, so its movie is still on disk under the old name), `clip_set`
  and `no_manifest`; no event is stale for `output` until its movie is removed by hand
- NEW and MISSING clips
- a named chapter, an IGNORED clip and a NEW clip inside a chapter (`2024-08-20 - Två kapitel -
  Tjörn`: a `Main` table and a `Kvällen` table on its event page)
- an event whose folder name (`2024/Blandat`) has no date, dated by its `reel.yaml` (`2024-11-02`)
- a same-name output clash (`2024-07-14 - Kalas` and `2024-07-14 - kalas`, same date, differing
  only in case)
- latest jobs that are `done`, `failed` and `queued`
- an event the list cannot read (`2024-02-30 - Omöjligt datum`, an impossible date), shown as an
  error row under "Needs attention"

The service needs Postgres even to list events (the list carries each event's latest
job). One-time setup, from the repository root:

```bash
# a persistent dev database at the dev-default URL (named volume survives restarts)
podman run -d --name auto-reel-ng-dev-db \
    -e POSTGRES_USER=auto_reel_ng -e POSTGRES_PASSWORD=auto_reel_ng -e POSTGRES_DB=auto_reel_ng \
    -v auto-reel-ng-dev-db:/var/lib/postgresql/data -p 127.0.0.1:5432:5432 \
    docker.io/library/postgres:16-alpine
.venv/bin/python -m alembic upgrade head

# build (or rebuild from scratch) the library beside the fixture
.venv/bin/python scripts/make_dev_library.py ../auto-reel-dev
```

Then run the service against it and the dev server as above, and open
<http://127.0.0.1:5173/>:

```bash
.venv/bin/auto-reel serve ../auto-reel-dev/library   # after a reboot: podman start auto-reel-ng-dev-db
```

Renders scheduled from the GUI run only while a worker runs against the same database
(`--device cpu` renders without a GPU):

```bash
.venv/bin/auto-reel worker ../auto-reel-dev/library --device cpu
```

## Regenerating the API types

The client's types are **generated, never hand-written**. Two committed artifacts:

```
auto_reel_ng/api response models
        │  app.openapi()
        ▼
   web/openapi.json          ◄── pytest fails when this is stale
        │  openapi-typescript
        ▼
   web/src/api/schema.d.ts   ◄── tsc --noEmit fails when client code reads
        │                        what the types no longer describe
        ▼
      client code
```

After any change to an endpoint's request or response model, run **both**, from the
repository root:

```bash
.venv/bin/python -m auto_reel_ng.api.openapi > web/openapi.json
podman run --rm -v "$PWD/web:/app:Z" -w /app docker.io/library/node:22 npm run generate:types
```

Both files are committed. Hand-editing either is pointless — regenerating
overwrites it — and `tests/test_api_openapi.py` fails, naming the disagreement,
until `web/openapi.json` matches what the application produces.

## Design system

Plain CSS, inline SVG and native HTML, inside the dependency budget below: no CSS
framework, no component library, no icon package, no web font (decision **D-10**,
HLD §7).

- **Layers.** `styles/index.css` declares `@layer reset, tokens, base, components,
  screens;` once, and `main.tsx` imports it first. Every stylesheet wraps all of its
  rules in exactly one of those layers — unlayered CSS would beat every layer. A
  screen's styles live next to it (`events/list.css`), and a later change adds its
  **own** file in `@layer components` or `@layer screens` (`edit/edit.css`,
  `jobs/jobs.css`) rather than editing one of these for its own rules. `base` sets
  no layout on elements; layout lives in classes.
- **Tokens** (`styles/tokens.css`) are the only place a color, size or duration is
  chosen. Every color is one OKLCH `light-dark(<light>, <dark>)` value: neutrals on
  hue 260, one indigo accent on 265, and five status tones (`ok`, `warn`, `err`,
  `info`, `idle`), each with a `-bg`, a `-fg` and a solid. Text pairs meet WCAG AA
  in both schemes; `--fg-subtle` is for icons and borders, never text. The scheme
  follows the OS until the header's theme control sets `data-theme` on `<html>`
  (stored per browser under `auto-reel:theme`, and applied before the first paint
  by the inline script in `index.html`). The control and that script also set both
  `theme-color` metas, so the browser's own interface color is the chosen scheme's
  page background; System gives each meta its OS scheme's color back.
  `--media-bg`, behind a video picture, is the one deliberate constant: black in both
  schemes, since native player controls draw light glyphs and letterbox bands read as
  part of the picture.
- **Status is never color alone.** A status is a `Pill`: an icon and its words, on
  its tone. Tone and icon come from `events/tones.ts`, the words from `labels.ts`.
  The usual state of a clip row, included, keeps its words and icon without the
  pill's fill and edge (`events/detail.css`, in both views), so the exceptions stand out.
- **Clip columns.** The clip tables publish their widths as `--clip-col-pos`,
  `--clip-thumb-w`, `--clip-col-status`, `--clip-col-size` and `--clip-col-mtime` on
  `.event-detail` (`events/detail.css`; an 8rem frame in a panel of 64rem or more,
  else 5rem), for Edit mode's grid to line up with them.
- **Times.** Every time a screen shows is written by `src/format.ts`
  (`formatInstant`): short month and day, hour and minute, the year only when it is
  not the current one, never seconds, in the browser's locale; the exact instant
  stays in `<time dateTime>`. Event dates are calendar dates and stay `YYYY-MM-DD`,
  as the folders write them.
- **Hover means a target.** Only table rows that open something take a hover fill
  (the list's event rows), and only for a pointer that hovers (`@media (hover:
  hover)`), since a touch screen keeps `:hover` on the last row tapped; "Needs
  attention" rows and the event page's clip table take none. Edit mode's clip rows
  keep their own hover, which brings out their drag handle and move buttons.
- **Shared pieces, by fixed name.** `ui/Icon` (`<Icon name="…" />`, decorative unless
  given a `label`), `ui/Pill`, `ui/Alert` (with an `action` slot; `role="alert"` by
  default), `ui/Skeleton` (`SkeletonRows`, `LoadStatus`), `ui/Dialog`, `ui/toast`
  with `ui/ToastRegion`, and `markEventsChanged()`. Classes on native elements:
  `btn` plus `btn-primary`, `btn-secondary`, `btn-ghost` or `btn-danger` (plus
  `btn-icon`, or `btn-compact` for a control inside a row); `pill`, `badge` and
  `alert` with `data-tone`; `panel` (with `panel-header` and `panel-meta`);
  `data-table`; `segmented`; `dialog-fields`, `dialog-actions`; `visually-hidden`. The header's
  `<div className="shell-status">` is the slot for status indicators: it takes the room the
  rest of the header leaves and is a size container (`shell-status`), so a status
  collapses by that room (`@container shell-status`), not by the window's width.
- **Busy controls.** A control the operator pressed that now waits for an answer
  gets `aria-disabled="true"` and `aria-busy="true"` and ignores clicks (a ref
  guard) until the answer. It never gets the `disabled` attribute, which drops
  keyboard focus to `<body>`. `.btn[aria-busy="true"]` shows a loader. Other
  controls of a locked form may use `disabled`.
- **Dialogs.** `<Dialog open title onClose initialFocus>`: pass the safe action's
  ref as `initialFocus` — never React's `autoFocus`, which fires while the dialog
  is still closed. Escape calls `onClose`; a close the caller starts does not. The
  children are the consequence, then a `dialog-actions` row: everything but that row
  becomes the dialog's description (`aria-describedby`), so the consequence is read
  when the dialog opens. A dialog that asks for input puts its fields in a direct
  child with class `dialog-fields` (a `<form>`; its submit button may sit in the
  actions row with `form=`): it is left out of the description too, and rendered
  between the body and the actions, so a long list of choices is never read out
  when the dialog opens (Edit mode's Move clips). No prop to pass.
- **Toasts** appear bottom right. A page with a bar held at the bottom of the window
  registers it with `keepToastsClearOf(bar)` (and releases it in the same effect's
  cleanup): the region then sits above the bar while it is stuck, and below it at the
  page's end, so no toast covers it. The page also puts the bar's height in front of
  `html`'s `scroll-padding-bottom` (an inline value on `:root`, `calc(<height> +
  var(--scroll-pad-bottom))`) while the bar is held, and removes it while the bar
  rests (in the page after the editor, it holds no room at the window's bottom). It
  is not a custom property on purpose: a changed custom property on `:root` restyles
  every descendant, about 100 ms on a page of 400 rows. The region publishes its own height as
  `--toast-region-h` on `:root` (absent when empty), and, while a bar is registered,
  its height plus the gap as `--toast-rise-h`, for the toasts that rise with the bar;
  `html`'s `scroll-padding-bottom` and the page's bottom padding add them, so a
  sticky error toast never covers keyboard focus or the end of the page. While toasts
  sit above a resting bar, the region also publishes that height as `--toast-room-h`
  and the bar keeps that room before itself (`edit.css`), so they cover no control;
  `place()` reruns when the page above the bar changes size. At most three toasts are
  held: a fourth drops the oldest success or info toast, and when all three are errors
  only a new error drops the oldest (a success or info toast is not shown then). The
  region is a manual popover shown in the top layer, shown again each time a modal
  dialog opens, so a toast is visible above the dialog and its backdrop (inert until
  the dialog closes); `Dialog` also stops the success and info clocks while it is open
  (`enterModal`) and gives focus back to its opener only while focus is still the
  dialog's. The stacks
  announce each toast once (`aria-atomic="false"`), each Dismiss is described by its
  message, and dismissing the focused toast hands focus to the next toast, else the
  previous one, else the control it came from, else the page's `h1`, without
  scrolling.
  While a modal dialog is open the region is inert and carries `data-under-modal`
  (its Dismiss buttons and links are drawn at half opacity); an error raised then is
  not announced. The above/below choice reads the bar as it would sit without the room
  it carries, so it switches at one scroll position in both directions. The pure rules
  have unit tests; the dialog, popover and room behaviour is checked only in a browser.
- **Touch.** Under `@media (pointer: coarse)` every `btn`, `segmented` option, toast
  link, the header's Events link and the back link take a tap in at least 44 × 44 px:
  an invisible `::after` around the control, so no box moves (segmented options grow
  to 44 px wide, the theme options only from a 26rem window, and the back link to
  44 px tall, with the folder beside it padded down to keep its first line on the
  link's). The shared action rows (an alert's, a dialog's, `page-actions`,
  `toolbar`) keep 1rem between wrapped lines, so two stacked areas never meet; a
  new row that can stack buttons does the same. In a table row of the list, a Render's
  area stops at the top of its cell (the line above the row is not its to take) and
  reaches further below instead. The brand name waits for a 34rem window, for the
  wider theme options. A fine pointer sees none of it. A new control class
  that is smaller than 44 px joins that rule.
- **Motion.** Every `transition` takes its duration from a `--dur-*` token; the
  tokens become `0ms` under `prefers-reduced-motion: reduce`. Every `animation` and
  its `@keyframes` sit inside `@media (prefers-reduced-motion: no-preference)`, with
  a literal loop duration (for example `1.2s`), never a `--dur-*` token. Each change
  runs this gate over its own directory:

  ```bash
  grep -rnE 'transition[^;]*[0-9.]+m?s\b' <dir>            # prints nothing
  grep -rn 'animation[^;]*--dur-' <dir>                    # prints nothing
  grep -rnE '(^|[^-])animation(-name)?:|@keyframes' <dir>  # each hit inside a no-preference block
  ```

- **Support floor.** Evergreen browsers from 2024 on: Chrome and Edge 123, Firefox
  120, Safari 17.5 — the `light-dark()` floor. `vite.config.ts` sets
  `build.cssTarget` to them, so the build keeps native nesting and `light-dark()`.
  An older engine falls back to browser-default colors; nothing stops working.

## Dependency budget

`react`, `react-dom`, the one drag-and-drop library — `@dnd-kit/core`,
`@dnd-kit/sortable` and `@dnd-kit/utilities`, the legacy line, added by the reorder
slice (D-8) — `vite`, `@vitejs/plugin-react`, `typescript`, and `openapi-typescript`
(dev). **No component library, no CSS framework, no router, and no state-management
or data-fetching library at GUI v1.** Any addition must be justified in the proposal
of the slice that demonstrably needs it. The design system adds nothing to it.

## Checks

`tsc --noEmit` is the frontend gate: the types are generated from the schema, so
drift is a compile error, and the API's behavior is covered by `pytest`. `npm test`
runs Node's built-in runner (`node:test`, no DOM, no added package) over the pure
modules that hold logic worth unit-testing. There is no browser automation in the
repo.

**The timeline's model** (GUI v2, D-20) is `src/timeline/model.ts`: pure functions
for where a clip sits at a zoom, which clips and ticks are near the view, how a
clip's cuts are drawn and numbered, how far a trim handle may go and what it snaps
to. Every time it takes or returns is a whole number of **milliseconds** (`Ms`), so
a value it returns is one the Cuts panel writes and reads back; a clip's duration
and frame rate are arguments with no default, and a value that is not above zero
throws a `ModelError`. The Timeline section (`timeline-view`) imports its layout, zoom,
windowing and cut-span functions; trim limits and snapping are the trim handles' (`timeline-trim`, with `handles.ts`). Its
tests (`model.test.ts`, `trim.test.ts`) and those of the timeline's other pure modules run
under `npm test`.

**The analysis lane** (`timeline-overlays`, `src/timeline/overlays/`) draws the event's cached suggestions
(`GET …/analysis`, read once when the track is shown) as buttons under their clips. A suggestion's state
(pending, cut, partly cut, dismissed) is derived from the clip's cuts, never stored, and a legend under the lane
spells out its icons and glyphs. The event page shows the lane in the read view, which decides nothing, and, with the trim handles, in Edit mode from the draft's cuts, where it decides
(`timeline-overlay-decisions`). **Approve as cut** (the detail's button, or **A** on a focused mark, never from a text field) adds the suggestion to the
draft through the Cuts panel's own add, with the suggestion's kind as the cut's reason: the save bar counts one cut added, Save writes a trim
`{in, out, reason: black|white|freeze}`, and removing the cut or Reset returns the mark to pending. **Dismiss** and **Restore** (**R** toggles) are for the page
visit only, are no edit and need no Save. `decideControl` (`overlays/control.ts`) builds the lane's `decide` from Edit mode's binding (`EditBinding.onAdd`,
`locked`, `announce`); the decision rules (`decideApprove`, `decideDismiss` in `suggestions.ts`) are pure and tested under `npm test`. While a save or a
Move clips is pending the decisions are unavailable and the detail says so.

`src/edit/card/` is the title-card inspector (`title-card-inspector`): `model.ts` (the nine overrides,
change detection, the preview request, which field a refusal names), `preview.ts` (the debounce, abort and
retry state machine, with injected timers and client), `specs.ts` (the draft card as the blocks and rows
show it; the clip a video card sits over), the hooks `useFonts` / `usePreview`, and the components. The
draft slice and the write are in `edit/draft.ts`. Pure parts are tested by `npm test`.

`src/edit/cardStyle.ts` and `CardStylePanel.tsx` are the event-wide card style (`title-card-event-style`):
`cardStyle.ts` is the pure model (the seven `look.title_card` fields, `styleChanged`, `applyStyle` which gives the
`look` a save writes, `overrides` / `overrideWords`, `effective`), `CardStylePanel.tsx` the "Card style for this
event" disclosure in Edit mode. The style is `Draft.style` in `edit/draft.ts` beside the card drafts; the
inspector's font and colour controls (`card/FontField.tsx`, `card/ColorField.tsx`) are shared with the panel.

`src/edit/decorators.ts` and `TitleCardsSwitch.tsx` are the Title cards On / Off switch (`title-card-toggle`):
`decorators.ts` is the pure model (`setTitleCards` gives the event's own `look.decorators` a position means, `applyDecorators`
the `look` a save writes), `TitleCardsSwitch.tsx` the control in Edit mode. The override is `Draft.decorators`; the state shown
is the detail's `title_cards` (`timeline/cards.ts` `cardsEnabled`), never read from `reel.yaml`. `card/choice.ts` is the pure
rule for which option of a Background / Position choice is shown chosen or inherited.

Movie playback is checked ad hoc in Chrome (Playwright's channel `chrome`) or Firefox,
never in Playwright's bundled Chromium, which cannot decode H.264 and would make a
working player look broken.
