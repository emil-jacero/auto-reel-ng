## Why

auto-reel had no GUI (HLD §2, problem 8). Its operator cut a clip by guessing at times in a text editor, or
by cutting the file by hand. auto-reel-ng made cuts part of `reel.yaml` (D-D), and since **D-14**
(`clip-cuts-screen`) Edit mode adds a cut from two **typed** times. Two gaps remain:

- **The operator cannot see the clip.** To type `0:01.25`, the operator has to find that moment in another
  player.
- **The page does not know a clip's length.** No probe-free read carries a duration (HLD §4.9). D-14 therefore
  accepts a cut that runs past the clip's end and says what the render does with it. Inventing a length
  would repeat the legacy tool's core bug, fabricated metadata (§2, problem 5; Principle I).

On 2026-10-01 the operator decided what GUI v1 still needs: "A and B in this version, but i want C a full
editor in v2". This change is **B**. Edit mode plays a source clip, sets a cut's From and To at the
playhead, shows the clip's cuts on a bar under the picture, and plays the clip with its cuts skipped. The
clip's length, as the browser reads it from the file it plays, then refuses a cut past the clip's end. **A**
is `movie-player-screen` (D-15). **C**, the full timeline editor, is v2.

This is HLD **§6 phase 8** (GUI v1), slice D. `media-endpoints` serves the bytes, which keeps this change in
`web/` (Principle VIII). The research step R0 (`docs/research/browser-playback.md`, landed by
`media-endpoints`) and this change's own spike settle every playback fact the design rests on. No §8 item is
open for it: §8.11's proxies and the PCM audio path stay v2, and this change narrows around them.

## What Changes

- **A clip's preview in its Cuts panel** (Edit mode, the event page; no new screen or route).
  - **Opening.** A **Watch** control opens a player in the panel, above the cuts. It shows the clip's
    thumbnail until it plays, and it never plays by itself.
  - **One press from the row.** In Edit mode the clip's thumbnail is a **Watch** button too: it shows the
    Cuts panel and opens the same player there. It keeps the thumbnail's size, is not the drag handle, and a
    failed thumbnail opens the player as well.
  - **One at a time.** Opening a preview closes any other. Edit mode replaces the read view, so the movie
    player (D-15) is never on the page beside it: Edit mode holds at most one video.
  - **Closing.** Close, or Escape inside the preview, closes it and gives keyboard focus back to the control
    that opened it (Watch, or the thumbnail). Hiding the panel closes it too.
  - **Nothing loads until it is opened.** No `<video>` and no media request exist before Watch is
    pressed, whatever the number of clips (the 400-clip fixture included).
- **The player's controls.**
  - Play / Pause.
  - A **playhead slider**: the pointer or the arrow keys move it in 0.1 s steps, and Page Up / Page Down,
    Home and End are supported too.
  - The time and the clip's length, in the panel's own time format.
  - **Skip cuts**, **Set From**, **Set To** and Close.
- **A cut bar** under the picture. It shows the clip's cuts as listed (read and added), the ones removed
  until the save, the span typed in the fields but not yet added, and the playhead. Each kind is drawn by
  shape as well as colour, and a legend names the kinds shown.
- **Set From / Set To** write the playhead's time into the cut's start or end field, to the millisecond, in
  the format `times.ts` writes (`0:01.234`). They add no cut by themselves. The text counts as a cut typed
  but not added, so G2's "typed" mark and the save bar's hold apply unchanged.
- **Skip cuts** plays the clip as the movie will:
  - no frame that lies wholly inside a listed cut is shown, each cut is jumped over once, and cuts are merged
    as the render merges them
  - a cut that runs to the clip's end, or ends within 0.1 s of the length the browser reads, stops playback at
    that cut's start
- **The clip's length**, once the preview has read it from the file:
  - is stated beside the cut fields
  - **refuses a cut that ends after it**, at its field and in words
  - marks a listed cut that runs past it

  It is kept for that clip until Edit mode closes or the file changes. A clip never previewed keeps D-14's
  rule and words.
- **What the browser cannot do is said, by cause** (R0):
  - **No sound in this browser.** Firefox plays the Sony PCM audio of 52 % of the archive silently.
  - **The picture cannot be shown.** HEVC and MPEG-4 Part 2 play sound over a black picture.
  - **Why a clip cannot play at all.** A one-byte read of the media route tells them apart: no longer on disk,
    a file changed since the page was read, an empty file, a folder that cannot be read, a format this browser
    does not play, or no answer. For the first two, the advice is to stop editing (saving first) to read the
    event again, never "Refresh", which leaves Edit mode.
  - Where the file is served and unchanged, a download of it is offered.
- **Edit mode's rules hold.**
  - A preview writes nothing and is no edit.
  - While a save or a Move clips is pending, Set From and Set To change nothing, and playback stays usable.
  - A clip moved within its chapter keeps playing.
  - A clip moved to another chapter, by a drag or by Move clips, keeps its preview open at the same time.
  - Reset closes every preview.
- **Docs.**
  - `web/README.md`: the Edit-mode paragraph and the file tree.
  - `docs/high-level-design.md`:
    - a new **D-16**
    - D-14's length sentence and its "previews" wording
    - §4.10's v1 bullet and slice row D

## Non-goals

- **Changing a file's bytes in any way**: proxies, transcodes, an AAC path for PCM audio, low-resolution
  previews. These are §8.11 and v2. Firefox stays silent on PCM clips, and the preview says so.
- **The timeline editor (v2):**
  - a filmstrip
  - scrub frames on hover
  - drag-trimming a cut on the bar
  - selecting a span on the bar
  - frame stepping
  - analysis overlays

  The bar shows cuts. It does not edit them.
- **A duration in the API**, or a length check for a clip never previewed. The length is the browser's read
  of one file in one Edit session. It is never saved, sent or shared.
- **Previews outside Edit mode's Cuts panels.** That means:
  - none on the event page's read view (the movie is `movie-player-screen`)
  - none for ignored or missing clips, which have no Cuts panel
  - no thumbnail control outside Edit mode, nor on a missing, removed or ignored clip's row: those thumbnails
    stay not focusable
- **Volume, mute, fullscreen, playback speed, picture-in-picture or captions.** The files carry no captions.
  No letter shortcuts either: the preview uses native buttons and the slider's standard keys.
- **Any engine, API, schema or dependency change**, and any change to the render.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `web-app`. All of the following are in the one capability.
  - Two ADDED requirements:
    - `Requirement: Edit mode previews a clip on request`
    - `Requirement: A clip's preview sets cut times at the playhead and plays the clip as the movie will`
  - Two MODIFIED requirements:
    - `Requirement: Every clip row shows a frame from its clip`. Its "The thumbnail SHALL NOT be focusable"
      gains the Edit-mode exception: a clip with a Cuts control has a thumbnail that is a "Watch <name>"
      button, keeping its box (supervisor decision, 2026-10-01).
    - `Requirement: Edit mode lists, adds and removes a clip's cuts`. Its sentence "The page does not know a
      clip's length" becomes the rule for a clip not yet previewed, and the refusals gain "ends after the
      clip's length, once known".

## Impact

- **Packages:** `web/` only, plus two documentation files.
  - new `web/src/api/clipMedia.ts`: the clip media address and the one-byte check of why a clip cannot play
  - new `web/src/preview/`:
    - `previews.ts`: the editor's preview store; pure
    - `playback.ts`: skip spans, slider keys and the slider's words; pure
    - `ClipPreview.tsx`
    - `preview.css`
  - `web/src/cuts/`:
    - `times.ts`: `checkCut` takes the clip's length, plus the past-end refusal, the length hint and the badge
    - `CutsPanel.tsx`: the Watch control, the player's place, Set From / Set To and the length checks
  - `web/src/edit/`:
    - `ClipOrderList.tsx`: `ClipRow` gives `CutsPanel` the event id and the clip's `mtime`, and `RowBody`
      wraps a cuttable clip's thumbnail in its Watch button
    - `EventEditor.tsx`: the preview store in the cut panel store, closed by Reset
  - `web/src/ui/Icon.tsx`: `pause`, `skip-forward` and `download`
  - `web/src/styles/tokens.css`: `--media-bg`, only when `movie-player-screen` has not added it
  - `web/README.md` and `docs/high-level-design.md` (D-16, D-14, §4.10)
- **CLI vs API (Principle V):** neither is touched. The preview reads `GET …/media?clip=`
  (`media-endpoints`), a file read that any client can make. A cut set at the playhead is saved by the
  existing `PUT …/reel` through `apply_editorial_write`.
- **Rendered output:** unchanged for identical inputs. There is no `RENDER_GRAPH_VERSION` bump, and the
  fingerprint's inputs are unchanged. A saved cut moves the editorial component, as any cut does.
- **Schemas:** no `reel.yaml` or `config.yaml` change, and no API change. There is no Alembic migration and no
  rescan. `web/openapi.json` and `schema.d.ts` are untouched.
- **Dependencies:**
  - **Gate:** `media-endpoints` **and** `cross-chapter-drag` must both be archived on main. This change
    reads the `/media` route's generated types. It builds on `cross-chapter-drag`'s `ClipRow`, the one
    `DndContext` and the cross-chapter remount, and on its edits to D-13 and §4.10.
  - **In parallel:** `movie-player-screen` (D-15) also edits HLD §7 / §4.10 and `web/README.md`. Whichever of
    the two lands first adds the token `--media-bg` (black in both schemes, with `movie-player-screen`'s exact
    value and comment), and the preview's stage reads it with no fallback. Whichever archives second re-bases
    the shared hunks and reuses the other's one-byte status mapping (tasks 1.1 and 5.1).
  - **New runtime dependencies:** none (D-8): native `<video>`, the existing `Icon`, no player library.
- **Size (Principle VIII):** one package plus docs, one capability delta (2 added, 2 modified), and 9 tasks.
