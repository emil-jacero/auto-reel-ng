## Why

On 2026-10-01 the operator settled what GUI v1 still needs: "A and B in this version, but i want C a full editor in
v2". **A** is this change: play the rendered movie on the event page. Today the page says whether an event needs a
render and runs the render (slice E), but the movie it produced can only be watched by finding the file on disk.
Legacy auto-reel had no GUI at all (HLD §2, problem 8), and it never wrote real chapters (problem 3), so its movies
were only ever checked in an external player.

The API side is `media-endpoints` (M1, this change's gate): `GET /api/v1/events/{event_id}/movie` streams the file
the staleness gate counts as the event's movie, with byte ranges, a strong `ETag` and `Cache-Control: private,
no-cache`. It also fixes the client contract: an event has a movie exactly when its staleness cites neither
`no_manifest` nor `output`. This change is the screen on top of it, a pure `web/` change as every screen since
slice C has been (Principle VIII). It belongs to **HLD §6 phase 8 (GUI v1)** and records **D-15**.

Real browsers decided the shape. Measured in Chrome 154 (channel `chrome`) and Firefox 132 against the real routes
on a dev library (design, "Research & Decisions"):
- **Loading the movie early is expensive.** With `preload="metadata"`, opening a page made Chrome send three
  open-ended range requests that read the 125 MB test movie from disk three times (367 MB), and Firefox read it
  once (125 MB). With `preload="none"` neither browser sends any request until Play.
- **A movie replaced on disk breaks a player at the same address.** After a render replaced the file, Chrome
  failed with a decode error (`MediaError` 3), even in a **new** `<video>` element at the same URL. The request
  log shows that the service sent that new element only the new file's bytes, so the stale state is Chrome's own,
  kept per URL. A new address played the new file cleanly. The event detail carries no movie version, so the page
  reads the file's `ETag` with a one-byte range request (p50 2.6 ms) and puts it in the address.
- **The native controls are usable from the keyboard** in both browsers: Space plays and pauses, Home and End
  jump, and the arrows seek (Firefox: ±5 s; Chrome: about 1 % of the length) or change the volume.
- **No chapter times exist on the client side.** The render manifest records none, and neither browser exposes
  the movie's real MP4 chapters to `<video>` (`textTracks.length` is 0 for a movie with two chapters).

## What Changes

- **The event page shows a "Movie" section** between the render region and the chapters when the event has a
  rendered movie by M1's rule. Sommarlov, Trasig, `2024-07-14 - kalas` and Blandat show none, and request nothing.
- **The browser's own player.** A native `<video controls>`: no custom controls, no autoplay, no loop, no
  captions control, no chapter list.
- **Nothing is loaded before Play.**
  - `preload="none"` keeps the movie's bytes off the wire until Play.
  - The poster is the thumbnail of the event's first played clip, the same address its row already shows, or
    none when there is no such clip or no frame.
- **Which movie, and how current.** The section says whether the movie is **Current** (the event is up to date)
  or **Outdated** (it needs a render, with a sentence on what that means), in words and an icon. It names the
  movie's file, which is the old name in the `output_renamed` case, and its size.
- **One address per movie file.**
  - On every read of the event, the page asks the service for one byte of the movie, a cheap request that
    reads the file's entity tag, name and size and checks that the movie is really served.
  - The player's address carries that tag as M1's ignored `v` parameter.
  - The re-read the page starts by itself when its job ends keeps the player, and playback, as it is when it
    finds the same file. When it finds a new file (a render finished), it mounts a fresh player at the new
    address. Keyboard focus moves to the new player when the old one had it.
  - A Refresh replaces the page's content with placeholders while it reads, as it does today, so it stops
    playback and the section returns with a paused player.
- **Failures by cause, never a black box without words.**
  - The probe's answers: the service has no movie file (404), the movie cannot be read (502, with its detail and
    kind), or the shared words for no answer or an unexpected answer.
  - After Play: a movie whose picture this browser cannot show (a legacy MPEG-4 movie adopted with
    `auto-reel adopt-renders` plays its sound only, with `videoWidth` 0 and no error event), a movie the browser
    cannot play (its own error, in words), and a movie file that changed while it played (offering "Load the new
    movie").
  - Each one offers what helps: a link that downloads the movie under its own name, or the new movie.
- **Fits every window and both schemes.**
  - A 16:9 frame that has its size before any byte arrives: at most 48rem wide and never taller than the window
    leaves below the header. At phone width it runs full width, edge to edge in its panel.
  - No horizontal scroll from 320px up, and a visible focus ring in both schemes.
  - Under a coarse pointer, its buttons and the download link take a 44px tap.
  - Nothing animates, so reduced motion is respected trivially.
- **Edit mode shows no movie.** Its read view is replaced by the editor, and leaving Edit mode reads the event
  again, as today.
- **Docs.** HLD **D-15** and §4.10's v1 bullet; `web/README.md` (screens, file tree, design system: the one new
  `--media-bg` token).

## Non-goals

- **A chapter jump list.** No probe-free source of chapter times exists, and browsers do not expose MP4 chapters.
  Recording the times at render time (in the manifest) is a v2 item beside the proxy work, as is a movie version
  in the event detail; a probe on request would break HLD §4.9's probe-free read model.
- **Captions or subtitles.** The movies carry none. The player shows no captions control rather than an empty one.
- **Custom controls, shortcuts or a player library** (D-8), and **picture-in-picture, playback speed or
  download controls** of our own. Whatever the browser's native controls offer stays as it is.
- **The clip preview in Edit mode** (B): that is `clip-preview-screen` (D-16).
- **Media facts the API does not give.** The duration is unknown until Play, and then the browser shows it. The
  page never computes or guesses it.
- **Any `api/`, engine or CLI change**, and any new field in the events reads. A movie version in the detail was
  considered and left out (design, "One address per movie file").
- **Server-side transcoding** (M1, §8.11, v2). A movie the browser cannot decode is reported, not converted.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `web-app`:
  - ADDED `Requirement: The event page plays the event's rendered movie`
  - ADDED `Requirement: The movie player says what it cannot play`
  - MODIFIED `Requirement: The event page says what a render does when the movie's name changed`: its scenario
    said that the renamed event's page "names no movie file". The render region still names none, but the new
    "Movie" section names the movie under its old name, taken from the movie route's answer.

## Impact

- **Packages:** `web/` only, plus `web/README.md` and `docs/high-level-design.md`.
  - New files:
    - `web/src/api/movie.ts`: the movie's address, typed from `paths`, and the one-byte probe
    - `web/src/api/headers.ts`: pure parsers for `Content-Range` and `Content-Disposition`
    - `web/src/movie/MoviePanel.tsx`: the section, its probe state and the player
    - `web/src/movie/labels.ts`: words and looks for the movie's age and troubles, exhaustive `Record`s
    - `web/src/movie/movie.css`: the frame and the section, in `@layer screens`
  - Small, local edits:
    - `web/src/events/EventDetail.tsx`: one `<MoviePanel>` at the top of `ReadyView`
    - `web/src/styles/tokens.css`: one token, `--media-bg`
- **CLI vs API (Principle V):** untouched. The page reads M1's movie route, which serves the file the staleness
  gate (`scan`, `render`) counts as the event's movie. No behavior is added to `api/`.
- **Rendered output:** unchanged. **No `RENDER_GRAPH_VERSION` bump.** The staleness fingerprint inputs are
  unchanged.
- **Schemas:** no `reel.yaml`, `config.yaml` or API change. **No Alembic migration** and no rescan.
  `web/openapi.json` and `schema.d.ts` are consumed as M1 regenerates them, never edited.
- **Dependencies:**
  - **Gate:** `media-endpoints` must be archived on `main`.
  - `cross-chapter-drag` is in flight. It edits `web/src/edit/**` and HLD §4.10/D-13, and this change edits
    neither of its files. Whichever archives second re-bases its §4.10 text (task 3.2).
  - **Packages added: none** (Principle VII, D-8). `package.json` and the lockfile stay unchanged, and
    `ui/Icon.tsx` gains no icon.
- **Size (Principle VIII):** one package, one capability delta (two added requirements and one modified), nine
  tasks. Most of the
  work is the component's states and their verification in a real browser.
