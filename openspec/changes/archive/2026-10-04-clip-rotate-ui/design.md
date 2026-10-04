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
`reel.yaml`; same Reset/Save model; works by keyboard and finger.

**Non-Goals:** no engine, API, schema or cache change; no regenerating proxies, sprites or thumbnails; no flip/mirror;
no arbitrary angles; no change to the rendered Movie player (the render already turned it); no rotate on the
Timeline's lane itself (the lane's widths are durations).

## Decisions

1. **A pure turn model, `web/src/rotate/turn.ts`, under `npm test`.** `normalizeTurn(n)` maps any multiple of 90 (also
   -90, 360, 450) into 0/90/180/270 and anything else to `null` (shown as no turn, never guessed). `stepTurn(current,
   way)` adds a quarter turn clockwise ("right") or anticlockwise ("left"). `turnWords(90)` is "Rotated 90 degrees";
   `turnsOf(clips)` reads a document's turns. The fit is made in CSS, not computed: a box that holds a turned picture is
   a size container (`container-type: size`), and for 90 and 270 the picture's own box is swapped (its width is the
   box's height and the other way round, `100cqb` by `100cqi`) before it is rotated, so `object-fit: contain` fits any
   picture shape whole in the unchanged box without measuring a box or a picture. Alternatives rejected: swapping the
   box to portrait (moves every row, breaks the fixed 16:9 thumbnail contract and `no row moves`), a computed
   `scale()` from measured aspects (needs a resize observer and the picture's dimensions before it is right), and
   re-requesting a rotated thumbnail (a second cache keyed by an editorial value; D-11 and D-21 keep editorial edits
   out of the caches).
2. **Rotation lives in the draft as a map, `Rotations`, beside `Cuts`.** The baseline is read from the document; the
   draft holds only changed identities; a value equal to the baseline is dropped. `buildWriteBody` writes `rotate` for a
   changed clip (0 writes nothing: the key is removed, as `entry.rotate == null` already means). Edit mode has no
   global Undo (its Undo buttons restore a removed clip, chapter or cut): a turn is stepped back by the opposite
   turn, and Reset clears the map.
3. **Controls are a pair of icon buttons per clip row** (`rotate-ccw`/`rotate-cw` icons; `Icon.tsx` gains `rotate-cw`),
   named "Rotate <name> left" / "Rotate <name> right", in the row's action cluster, each a 44 px target when the
   pointer is coarse and the row's existing control height otherwise (`Every control is large enough to touch`).
   The group buttons live in the marks line and are disabled when nothing on disk is marked.
4. **Turned pictures share one stylesheet.** `rotate.css` turns an `img` or `video` that has `data-turn` and is a direct
   child of a `data-turned` box (the thumbnail box, the player's stage, the Timeline's stage). The play overlay and the
   mark box are siblings of the picture, never children, so they stay upright and in their corners.
5. **The Timeline** turns its single `<video>` element and each filmstrip tile the same way. The video element's box is
   the preview area; the tiles keep the lane height (90 px) and the clip's lane width (set by duration, never by shape),
   and a turned tile is fitted inside it. Trim handles, the playhead and the suggestions are untouched.
6. **No shape is needed.** Because the fit is made by the browser (decision 1), the client reads no picture dimensions;
   a tile of a filmstrip, whose picture is a sprite background, is turned inside its tile box with a scale from the tile's
   own place (`tileWidth * scale` by the lane height), which the sprite geometry already gives.

## Risks / Trade-offs

- A turned landscape thumbnail is pillar-boxed in its 16:9 box (the picture is smaller). Accepted: moving rows is worse.
- Display-rotation assumption: if a rotated sample's thumbnail or proxy were not upright, the CSS turn would be wrong
  by the display rotation. Mitigated by a task test on the rotated samples (`h264-720p-rotate90-aac.mp4`,
  `hevc-mov-rotate90-aac.mov`, `h264-portrait-1080x1920-aac.mp4`) in Chrome and Firefox. The unexplained single-frame
  SSIM 0.744 on the rotated 720p phone clip (research `proxies.md`) is looked at here by eye.
- Saved-but-unrendered: after Save the movie is stale (the fingerprint includes `rotate`), as for any editorial edit;
  the existing staleness verdict says so. No new text.
- Firefox: the original clip is silent there (existing note); proxies carry AAC; a turned preview is no different.
