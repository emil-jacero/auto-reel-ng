## Context

`event-poster-engine` (the gate) adds `poster: {clip, at}` to `reel.yaml` (`at` in seconds of the clip, before
cuts), validates it with typed errors, resolves the effective poster (the chosen frame, else the first played
clip's thumbnail frame, with a fallback when the chosen clip is missing, ignored or excluded), writes
`<stem>-poster.jpg` with the movie and claims it in `render-manifest.json`, and makes the sidecar's absence a
staleness reason. This change reads and edits that, and reuses the engine's poster resolution and frame extraction;
it adds no rule of its own about which frame is the poster (Principle V). Today the movie player's poster is
`thumbnailUrl(first played clip)`, the events list carries no thumbnail field and stays probe-free
(`api-service`, "Clip thumbnail endpoint"), and Edit mode's draft carries cuts, cards, style and rotation
(`web/src/edit/draft.ts`) that the Timeline edits through `EditBinding` (`timeline/editing.ts`).

## Goals / Non-Goals

**Goals:** a poster for every event on the list and the page; one place to choose a frame, on the Timeline the
operator already trims on; reads stay probe-free and database-free.

**Non-Goals:** drawing the poster in the browser for the saved state; a poster per chapter; crop or zoom of the
frame; a new job kind; touching the proxy cache's key or contents; a waveform or any timeline library.

## Decisions

**D1. The list gets no poster field; the client builds the URL.** `GET …/events/{id}/poster.jpg` resolves the
effective poster server-side, so the list response, which has no per-event resolution, stays as it is and the cover
`<img src>` needs only the event id. An event with no playable clip answers 404 and the page shows the
placeholder. *Alternative:* a `poster` object on every list row would make the list resolve every event's
document and clip set per request; rejected as the list's cost grows with the library.

**D2. The detail reports `poster`, the endpoint serves it.** The detail's `poster` is
`{clip, at, source}`: `source: event` with the chosen `clip` and `at`; `source: default` with the first played
clip and `at: null` (the thumbnail's own frame time depends on the clip's duration, which a probe-free read does
not know, so it is not invented). When the chosen clip cannot be used (missing, ignored, excluded) the detail
reports the default and a `poster_note` naming why; a poster the loader refuses
makes `reel.yaml` unreadable, as any bad field does, and is the event's failure (the engine validates it at load,
so there is no document to report a partial answer from). The played clips are the detail's own chapters (a NEW
disk clip counts, a missing, ignored or excluded one does not): what a render adopts. The page needs these to word "Default: first
clip" or "Chosen frame" and to jump the Timeline playhead to the chosen frame.

**D3. Where the image comes from.** In order: (1) the rendered sidecar, only when the event is not stale and the
manifest claims the sidecar (the verdict is probe-free, so is this); (2) a frame drawn at the poster time from the
original clip through the engine's poster extraction (the render's own function, so the draw and the sidecar agree
on turn, pixel aspect and HDR; the proxy is left out so there is one rule for the picture), or, for the default,
the engine's thumbnail. Draws are cached beside the thumbnails (`thumbs` cache, outside the library) keyed like D-11
(clip size, mtime, `at`, size, version) so a repeat answers without ffmpeg; a failed draw is remembered 60 s like a
thumbnail's. Same extraction cap and single-flight as thumbnails, shared with them. The `ETag` identifies the
bytes (sidecar: its size and mtime; draw: the cache key); `Cache-Control: private, no-cache`, so an edited poster
shows at once and a revalidation costs a 304 with no extraction. *Alternative:* `max-age=86400` as thumbnails have;
rejected, a saved poster would show the old frame for a day.

**D4. The draft frame is taken from the Timeline's own video, in the browser.** "Use as poster" copies the frame
the Timeline's one `<video>` shows into a canvas and keeps it as an object URL for the poster area ("Chosen frame,
not saved"); the server is never asked to draw a frame for an unsaved time. That adds no endpoint, no cache growth
from arbitrary `at` values, and shows exactly the frame the operator sees. The proxy has rotation and SAR applied
(D-21), so the snapshot is the turned picture. It is a preview only: the saved poster is always the engine's
frame from the original. The button is enabled only when the playhead is on a played clip, its video has a decoded
frame at that time and no save is pending. *Alternative:* `poster.jpg?clip=&at=` for drafts, rejected for the
cache growth and a second code path.

**D5. The playhead's time is the clip's own time before cuts.** The timeline model maps the playhead to a clip and
a time on that clip's frame grid in whole milliseconds (the existing `clipAt`, the track's card shifts); the draft
stores `at` as seconds to the millisecond. A time inside a cut is allowed (`at` is before cuts, as the engine
defines it). A playhead on a title-card block (not footage) disables the button and says why.

**D6. The editorial body follows the card rule.** `poster` absent keeps what `reel.yaml` has (a client that does not
know posters cannot erase one); `null` removes it; `{clip, at}` sets it. The body model checks shape only; every
value rule is the engine's (`clip` an identity, `at` finite and ≥ 0; the engine does not require the clip to be played, it
falls back with a note) and a refusal is a 400 naming `poster.clip` or `poster.at`. The engine's own editorial
write keeps a poster on `null` and removes it on `{}`; the route maps the body's absent to the engine's `None` and
the body's `null` to `{}`, so the wire says what this change specifies and the engine is unchanged. `at` below the clip's duration needs a probe, so it is checked at render, not at
write: the page may hold an `at` the engine later reports. A poster edit makes the event stale through the
editorial component and enqueues nothing.

**D7. The page's words.** Poster area states are `Default: first clip` and `Chosen frame` (and `Chosen frame, not
saved` for a draft); `Use default` sets the draft to `null`. The draft carries `poster` as `undefined` (as read),
`null` (removed) or `{clip, at}`; the unchanged case writes nothing (byte-identical echo). A clip that leaves the
event (removed missing clip, moved out) while chosen is shown with the engine's fallback note after save, not
rewritten silently.

## Risks / Trade-offs

- [The chosen frame differs by a few ms between the proxy draw and the render's frame] → the sidecar is the
  truth once fresh; while stale the picture says "drawn from the proxy" only in the API's `source`, never claims it
  is the render's frame.
- [A cover on every list row means many images] → `loading="lazy"`, fixed aspect box so nothing shifts, the
  extraction cap of two and single-flight bound the server; a first load of a big library draws on demand.
- [A cross-origin or tainted canvas] → proxy and page are same origin; if the snapshot throws, the button reports
  it and the poster is not changed.
- [Firefox decodes the proxy's frame differently from Chrome] → verified in both browsers (task 6); the saved
  poster never depends on the browser.

## Open Questions

None blocking. If `event-poster-engine` names the detail's default differently, the API field names follow
its resolution function; the contract here (`clip`, `at`, `source`) is the web's.
