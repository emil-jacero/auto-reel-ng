## Why

On 2026-09-30 the operator asked for thumbnails on the clips: "not the first frame but some percentage into
the clip". An event page lists clips by file name, size and time only. Camera names such as `s1710002.mp4`
say nothing about what a clip shows, so choosing an order in Edit mode (slice D, `event-edit-screen`) means
opening the files elsewhere. Its design says so: "The time is the only ordering cue v1 has, because there are
no thumbnails." Legacy auto-reel had no GUI at all (HLD §2, problem 8).

HLD §4.10 listed thumbnails under GUI v2, and §8.11 listed their generation as research. The operator
approved pulling **clip thumbnails** into v1, recorded as **D-11** (HLD §7, change `clip-thumbnails`).
Proxies and scrubbing stay v3. The plan has three changes, following the house pattern of engine and CLI,
then API, then screen:

- `clip-thumbnails`: extraction and a cache outside the library, with `auto-reel thumbs`
- `clip-thumbnail-endpoint`: `GET /api/v1/events/{event_id}/thumbnail?clip=<identity>`
- this change: showing the thumbnails

It belongs to HLD **§6 phase 8** (GUI v1). It is gated on the endpoint, and on slices D and E, because its
rows live in their screens.

## What Changes

- **A frame from each clip, after its position number and before its file name, in reading order.** It
  appears in:
  - the event page's chapter tables, and in their card layout at phone width
  - Edit mode's reorder lists, both the movable rows and the dimmed ignored rows. In a panel narrower than
    30rem the file name takes the first line, and the frame starts the second, so that no camera name is
    broken inside the word.

  This departs from the plan's "at the start of each clip row": measured, a box first in the row leaves
  the file name too little room, and camera names break inside the word (design, "Where the thumbnail
  sits").

  The frame is the one the service extracts, a configured fraction into the clip (default 25%). It is shown
  in a fixed 16:9 box, whole and never cropped, so a portrait clip stands letterboxed in its box.
- **Thumbnails never get in the page's way.**
  - An image is requested only when its row comes near the visible part of the page (native lazy loading),
    at a low fetch priority so that the page's own reads and saves go first, and it is decoded without
    holding up the page.
  - The box has its final size before the image arrives, so no row moves when it loads or fails.
  - A placeholder shimmers while the image loads, and stands still under reduced motion.
- **Absence is shown honestly, never as an error.**
  - A clip whose frame the service cannot extract (the dev library's zero-byte `trasig.mp4`) shows a
    neutral "No preview" box with an icon. There is no alert, no toast and no retry.
  - A MISSING clip requests nothing and shows an empty dashed box. Its row's "Missing" status already says
    why.
  - An IGNORED clip's frame is dimmed like the rest of its row.
- **Accessible names.** Every image's text alternative is "Frame from <file name>". The "No preview" box
  is named "No preview for <file name>".
- **A replaced clip gets a new address.** Each URL carries the clip's `mtime`, exactly as the event detail
  gives it, as the endpoint's cache-busting `v` parameter. A clip replaced on disk therefore shows its new
  frame on the page's next read, not after the browser's day-long cache expires.
- **Types from the schema.** The URL helper reads the route and its `clip` and `v` query parameters from
  the generated `paths`, so if the endpoint or a parameter is renamed, `tsc --noEmit` fails.
- **Spec text that thumbnails would make false is corrected.** "Reading a screen never changes state" says
  that opening a screen changes no state the service holds. Reading a thumbnail can fill the service's
  thumbnail cache. The requirement now names that derived cache, which lives outside the library, as the
  one exception.

## Non-goals

- **Nothing the plan leaves out of all three changes:**
  - applying the editorial `rotate` to a thumbnail
  - poster or cover images on the event list
  - hover scrubbing, proxies or a larger preview on hover (v3)
  - avoiding black or frozen frames (later, with analysis review)
  - cache eviction
  - GPU decode
- **No choosing the frame in the GUI.** The fraction is `config.yaml`'s `thumbnails.position` (D-2),
  and changing it is a file edit.
- **No client-side request queue, retry or prefetch.** The browser's lazy loading and connection limits
  pace the requests, and the endpoint limits its own extractions (design, "Pacing").
- **No new field in the event list or detail responses.** The client builds each URL from the event id,
  the clip identity and the clip's `mtime` it already has, so the list and detail stay probe-free.
- **No API, engine, CLI or schema change**, no dev-library change, no new dependency, and no new icon.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `web-app`:
  - new `Requirement: Every clip row shows a frame from its clip`
  - new `Requirement: Thumbnails never hold up or break a page`
  - modified `Requirement: Reading a screen never changes state`: the service's derived thumbnail cache,
    which is outside the library, is named as the one state a read may fill. Every existing scenario stays
    true, and one scenario is added.

## Impact

- **Packages:** `web/` only, plus `web/README.md`.
  - New files:
    - `src/events/ClipThumb.tsx`: the component
    - `src/events/thumbs.css`: the box, in `@layer components`
    - `src/api/thumbnail.ts`: the URL, typed from `paths`
  - Small, local edits to shared files:
    - `src/events/EventDetail.tsx`: one column and one cell per clip row, and the event id passed to the
      chapter panel
    - `src/events/detail.css`: the column width, the card-layout areas, and vertical centering of the clip
      table's cells
    - `src/edit/ClipOrderList.tsx`: the thumbnail as a grid item of each row, the event id through its row
      props, and one header-strip cell
    - `src/edit/EventEditor.tsx`: passes `eventId` to `ClipOrderList`
    - `src/edit/edit.css`: one grid column, the narrow areas, and the narrow breakpoint moved from 54rem to
      58rem so that a camera name is never broken inside the word (design, "Where the thumbnail sits")
  - `docs/high-level-design.md` is not edited. D-11 and the §4.10 wording are `clip-thumbnails`'s, and task
    1.1 checks that they describe what this change ships.
- **CLI vs API (Principle V):** untouched. The page reads the endpoint `clip-thumbnail-endpoint` adds, which
  serves the engine's `thumbnail_for`. The CLI reaches the same function through `auto-reel thumbs`. This
  change adds no behavior to `api/`.
- **Rendered output:** unchanged. **No `RENDER_GRAPH_VERSION` bump.** Fingerprint inputs are unchanged.
  Thumbnails are not a render input, and the page reads them only.
- **Schemas:** no `reel.yaml`, `config.yaml` or API change here, **no Alembic migration**, and no rescan.
  `web/openapi.json` and `schema.d.ts` are consumed as `clip-thumbnail-endpoint` regenerates them, never
  edited.
- **Dependencies:**
  - **Gates:** `clip-thumbnail-endpoint`, `event-edit-screen` and `render-progress-screen` must all be
    archived on main. `clip-thumbnail-endpoint` is itself gated on `clip-thumbnails`.
  - **Packages added: none** (Principle VII, D-8). `package.json` and `package-lock.json` stay unchanged.
  - The "No preview" box reuses the existing `film` icon, so `ui/Icon.tsx` is untouched.
- **Size (Principle VIII):** one package, one capability delta (two added requirements and one modified),
  and nine tasks. The largest part is the layout edits in two existing screens' CSS.
