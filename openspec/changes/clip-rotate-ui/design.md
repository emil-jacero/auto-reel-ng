## Context

- **Meaning (D-23).** `rotate` is "turn this clip N degrees clockwise from how it plays now", where "how it plays now"
  is the picture after the container's display rotation. The render applies `(display + rotate) mod 360`.
- **What the service serves already carries the display rotation and never `rotate`.** Thumbnails (`clip-thumbnails`),
  proxies (`clip-proxies`, "Editorial rotation is not baked in") and filmstrip sprites (cut from the proxy) are upright
  by display rotation; the original file played by a browser is upright by the same rule. So one rule fits all: the GUI
  applies **only** the extra `rotate` turn, in CSS, to each picture. This is what makes the preview equal the render.
- **Where `rotate` is read.** `reel.yaml` is the source of truth. Edit mode's `Baseline.read` is the `ReelDocument`
  (`clips.<identity>.rotate`); the read view already reads the document after every event read for cuts
  (`cuts/ReadCuts.tsx`, `fetchReel`). `ClipOut` carries no `rotate`, and this change adds none (no schema change).
- **Draft.** `edit/draft.ts` keeps cuts as a `Cuts` map over a baseline and `buildWriteBody` already passes an entry's
  `rotate` through; a rotation map joins the draft the same way, so `isDirty`, Reset and the write body follow.
- **Marks** (`edit/marks.ts`, `clip-group-select-drag`) are state beside the draft; the group controls act on the marked
  identities that are on disk.

## Goals / Non-Goals

**Goals:** a sideways clip is fixed in one or two presses and the fix is visible everywhere before Save; remembered in
`reel.yaml`; same Undo/Reset/Save model; works by keyboard and finger.

**Non-Goals:** no engine, API, schema or cache change; no regenerating proxies, sprites or thumbnails; no flip/mirror;
no arbitrary angles; no change to the rendered Movie player (the render already turned it); no rotate on the
Timeline's lane itself (the lane's widths are durations).

## Decisions

1. **A pure turn model, `web/src/rotate/turn.ts`, under `npm test`.** `normalizeTurn(n)` maps any multiple of 90 (also
   -90, 360, 450) into 0/90/180/270 and anything else to `null` (shown as no turn, never guessed; the loader refuses
   such values). `stepTurn(current, ±1)` adds a quarter turn clockwise (+1, "right") or anticlockwise (-1, "left")
   and returns 0 for no turn. `turnWords(90)` is "Rotated 90 degrees". `turnTransform(turn, box, shape)` returns the
   CSS `transform` for a picture of aspect `shape` (width over height of the picture as served) in a box of aspect
   `box`: `rotate(<turn>deg)` plus, for 90 and 270, `scale(k)` with `k = min(box / shape', shape' / box)`-style fit so
   the turned picture lies inside the box (contain). Alternatives rejected: swapping the box to portrait (moves every
   row, breaks the fixed 16:9 thumbnail contract and `no row moves`), and re-requesting a rotated thumbnail (a second
   cache keyed by an editorial value; D-11 and D-21 keep editorial edits out of the caches).
2. **Rotation lives in the draft as a map, `Rotations`, beside `Cuts`.** The baseline is read from the document; the
   draft holds only changed identities; a value equal to the baseline is dropped. `buildWriteBody` writes `rotate` for a
   changed clip (0 writes nothing: the key is removed, as `entry.rotate == null` already means). Undo steps back
   one change at a time like cuts; Reset clears the map.
3. **Controls are a pair of icon buttons per clip row** (`rotate-ccw`/`rotate-cw` icons; `Icon.tsx` gains `rotate-cw`),
   named "Rotate <name> left" / "Rotate <name> right", in the row's action cluster, each a 44 px target when the
   pointer is coarse and the row's existing control height otherwise (`Every control is large enough to touch`).
   The group buttons live in the marks line and are disabled when nothing on disk is marked.
4. **Turned pictures share one wrapper.** A `Turned` component (`web/src/rotate/Turned.tsx`) wraps an image or video
   in a box that keeps its own aspect and `overflow: hidden`, with the transform on the child; it takes the turn and the
   picture's aspect. The play overlay and the mark box are siblings of the transform, never children, so they stay
   upright and in their corners.
5. **The Timeline** turns its single `<video>` element and each filmstrip tile the same way. The video element's box is
   the preview area; the tiles keep the lane height (90 px) and the clip's lane width (set by duration, never by shape),
   and a turned tile is fitted inside it. Trim handles, the playhead and the suggestions are untouched.
6. **Aspect needs a shape.** The picture's shape comes from what the component already knows: the sprite geometry for
   a tile (`facts` dims and `tile` size), `video.videoWidth/Height` for a video once metadata loads, the thumbnail's
   `naturalWidth/Height` once loaded. Until known, the box is the fixed 16:9 and the turn is applied with the
   16:9 shape; no layout shift because the box never changes size.

## Risks / Trade-offs

- A turned landscape thumbnail is pillar-boxed in its 16:9 box (the picture is smaller). Accepted: moving rows is worse.
- Display-rotation assumption: if a rotated sample's thumbnail or proxy were not upright, the CSS turn would be wrong
  by the display rotation. Mitigated by a task test on the rotated samples (`h264-720p-rotate90-aac.mp4`,
  `hevc-mov-rotate90-aac.mov`, `h264-portrait-1080x1920-aac.mp4`) in Chrome and Firefox. The unexplained single-frame
  SSIM 0.744 on the rotated 720p phone clip (research `proxies.md`) is looked at here by eye.
- Saved-but-unrendered: after Save the movie is stale (the fingerprint includes `rotate`), as for any editorial edit;
  the existing staleness verdict says so. No new text.
- Firefox: the original clip is silent there (existing note); proxies carry AAC; a turned preview is no different.
