## Context

See proposal.md, "Why". Code on main 8fb4d16 (before the gates):

- **The preview** is `web/src/preview/ClipPreview.tsx` (one component, one `<video>`), its pure words and rules in
  `playback.ts`, its module store in `previews.ts`, and the media address in `web/src/api/clipMedia.ts`
  (`clipMediaUrl`, `checkClipMedia`, `changedSince`). `CutsPanel.tsx` mounts it and reads the clip's length with
  `useClipLength(previews, clipMediaUrl(eventId, {identity, mtime}))`.
- **The source is set in a layout effect** (`video.src = src`), never as a JSX attribute. Its cleanup keeps the
  playhead in the store while the preview is still open (`keepPlayhead`), pauses, removes the source and calls
  `load()`; `onLoadedMetadata` restores `previews.playhead(identity)`. That is how a clip that moves to another
  chapter reopens paused where it stood. A source swap is the same event, which this design reuses (Decision 3).
- **Set From / Set To** call `onSet(field, video.currentTime)`; the panel rounds to the millisecond and writes
  `0:02.607`. Skip cuts reads `frame.mediaTime` from `requestVideoFrameCallback`. Both are in the playing file's
  own media time.
- **The length** is `video.duration` of the file, stored by media address (`previews.setLength(src, …)`) and read
  back by the panel through the same address. D-16: Chrome's equals ffprobe's, Firefox's is up to 60 ms longer,
  never shorter, so the check never refuses a cut the render keeps whole.
- **The no-sound note** is `'mozHasAudio' in video && video.mozHasAudio === false` after `loadedmetadata`
  (`noSoundWords`). The failure path asks the service for the first byte (`checkClipMedia`) and compares the
  clip's `mtime` with `Last-Modified` (`changedSince`) to tell "changed on disk" from "cannot play the format".
- **The movie player** (D-15) already reads an entity tag with a one-byte range request and puts it in the address
  as `v` (`probeMovie`, `movie.ts`, over the shared `probeFirstByte` table in `probe.ts`).
- **No component test runner exists**; the pure modules run under `node --test` (`npm test`), the rest is `tsc`,
  the production build and Playwright from the scratchpad (never the repo).

**The gates, as planned** (`v2-plan.json`; both merge before this change is implemented, task 1.1 re-checks):

| Name used here | From | Meaning |
|---|---|---|
| `clip.proxy.state` | `proxy-state-read` | `absent | ready | stale | failed`, read by `stat` and JSON only |
| `clip.proxy.facts.duration` | `proxy-state-read` | the original's duration in seconds, written by the proxy job's probe; present when `ready` |
| `GET /api/v1/events/{event_id}/proxy?clip=&v=` | `proxy-media-endpoints` | the copy, through `media_response`; ETag header; absent copy: 404 problem body |

**As built** (re-checked on main b7b25c8, task 1.1): `ClipOut.proxy` is `ProxyOut | null` with `state:
ProxyState` (`absent | ready | stale | failed`), `facts: ProxyFactsOut | null` (`duration` in seconds, the
source's), `version: string | null` (the proxy file's entity tag without quotes, set when ready) and `reason`
(failed). `GET`/`HEAD /api/v1/events/{event_id}/proxy?clip=&v=` sends a strong `ETag` on 200/206/304, a 404
problem body for an absent copy, a 416 for an empty range, and ignores `v`. The names match this table.
`ProxyOut.version` is a field the plan did not list: it is the tag of the copy at the moment of the detail read.
Decision 2 still reads the tag with the one-byte request, because a snapshot tag cannot name a copy rebuilt after
the read; `version` is not used (a second source for the same value would be a way to disagree with itself).

The client follows the **generated** `schema.d.ts`, not this table: if a name differs, the web changes to the
generated name and the specs keep saying "the clip's proxy state", "the copy's facts" and "the preview copy's
address", which name no field.

## Goals / Non-Goals

**Goals:**
- Sound in the preview in every supported browser for every clip whose copy is ready, with no new server path.
- The v1 preview's behavior unchanged for a clip with no ready copy, and its controls, keys and notes the same.
- Cut times that mean the same thing whichever file plays: the playhead's time in milliseconds is the original's.

**Non-Goals:**
- Anything the timeline needs (filmstrip, boundary preload, Prepare). Nothing here requests a build.
- Remembering the operator's file choice beyond the open preview (no storage, no setting).

## Decisions

### 1. Which file plays is a pure function of the detail's proxy state

**Context**: the choice must be known when the preview opens, with no request, so that an unprepared clip costs
nothing and shows the v1 behavior at once.
**Explored**: asking the service on open (a probe per clip: a request where the detail already knows the answer);
deciding by browser (`mozHasAudio`): the copy helps Chrome too (smaller file, 15 to 23 ms to first frame against
97 to 191 ms for originals: `synthesis.md` §3).
**Decision**: `previewSource(proxy)` in a new pure `preview/source.ts` returns `{kind: 'copy', durationMs}` when
`state === 'ready'` and the facts give a finite duration above zero, else `{kind: 'original', why}` with `why` one
of `absent | stale | failed | unusable`. `unusable` is a `ready` state whose facts carry no usable duration: a gate
contract break, shown as "its preview copy has no usable length" and played as the original, never guessed
(Principle I). The operator's Play original overrides `copy` for that clip (Decision 3).
**Rationale**: one table, tested without a DOM; no request for a clip that cannot use a copy.

### 2. The address takes `v` from a one-byte probe made when the preview opens

**Context**: D-15: Chrome fails to play a replaced file at an address that served the old one. A copy is replaced
when `PROXY_VERSION` or the settings hash changes while the clip's `mtime` stays, so `clip.mtime` as `v` (the
original's rule) is not enough.
**Explored**: (a) `v` = the clip's `mtime`: wrong for the reason above. (b) An entity tag in the event detail's
`proxy`: the detail is a snapshot, and a copy rebuilt after the read would still carry the old tag; the gate's plan
lists no such field. (c) The movie's pattern: `probeFirstByte` on the unversioned route, read the `ETag`, then set
the source.
**Decision**: (c). `probeProxy(eventId, identity, signal)` in `clipMedia.ts` reuses `probeFirstByte` with a reader
that requires the `ETag` (so a 200 without one reads as unpublished, like the movie's). The tag-stripping function
moves out of `movie.ts` into `api/headers.ts` and both use it. The effect that sets the source runs the probe
first for a copy, keyed on the attempt like the source effect; until it answers the element has no source and the
poster and "Loading…" show. The probe's answer also names a vanished copy (404 problem) or an empty file (416)
before the element is asked to play, so those need no `MediaError` round trip.
**Rationale**: current tag, proven pattern, no field to guess. **Cost**: one tiny local round trip per open
(measured in task 5.1; the gate's own bar is a first frame within 100 ms of the element's request).

### 3. Switching file reuses the source effect's playhead hand-over

**Context**: Play original must keep the time, and keep playing if it was playing.
**Explored**: two `<video>` elements (breaks "Edit mode holds at most one video"); `currentTime` copied by hand
(duplicates what `keepPlayhead` and `onLoadedMetadata` already do for a moved clip).
**Decision**: the file is state: `choice` (`copy | original`), derived from `previewSource` unless the store holds
the operator's override. A change of `choice` changes `src`, so the existing layout-effect cleanup keeps the
playhead (it does so only for a preview that is still open and has read its metadata, which is the case) and
`onLoadedMetadata` restores it. The handler sets `phase` to `loading`, clears the notes, and sets `pendingPlay`
when the element was playing, so the same code that serves "Play pressed before the metadata" resumes it. The
store gains `original(identity)` and `setOriginal(identity, on)`: the override survives a remount (a move to
another chapter) as the playhead does, and `hide` / `hideAll` forget it. Keyboard focus stays on the control that
was pressed (the element is not remounted: `attempt` does not change).
**Rationale**: no new way to carry a time; the same 0.1 s of pause a moved clip already has. **Time** is the same in
both files because the gate encodes with `-fps_mode passthrough` and the video `start_time` equals the source's
(synthesis X9; `proxy-encode`'s own gate): task 5.1 checks it on the real files by seeking both to the same time
and comparing what Set From writes.

### 4. While the copy plays, the length is the facts' duration, stored under the clip's own address

**Context**: the copy's `video.duration` differs from the original's by about 21 ms, and not always upward (1080p50:
24.981 s for the copy, 25.003 s for the source; `synthesis.md` X6). D-16's "never shorter" guarantee would break:
a cut ending at the original's end would be refused as past the copy's end.
**Explored**: the copy's `video.duration` (breaks the guarantee); the detail's existing `duration` (the thumbnail
sidecar's: `null` until a thumbnail exists, so the copy would depend on thumbnails; the facts' own duration was
probed by the proxy job and is independent of them).
**Decision**: on `loadedmetadata` of the copy the preview stores `facts.duration` (to whole milliseconds with the
page's `toMs`) as the clip's length and ignores `durationchange` readings from the copy. The length is stored
under `clipMediaUrl(eventId, clip)`, the original's address, whichever file plays, so `CutsPanel`'s
`useClipLength` call does not change. Switching to the original lets the next `loadedmetadata` store the browser's
reading ("the latest wins", as before). The end of the copy's own media may come about 20 ms before that length:
End and a seek to the length clamp in the browser, the ended state counts as the clip's end under the existing
100 ms `END_SLACK_MS`, and nothing else reads the element's `duration`.

### 5. A copy's failure is told by cause, never by `Last-Modified`

**Decision**: the probe's answers (problem, empty, unreachable, unpublished) and the one-byte check after a
`MediaError` map to the existing words with a title naming the preview copy. Two differences from the original's
table: `changedSince` is not used (the copy's `Last-Modified` is the copy's file, not the clip's: comparing them
would claim every copy "changed on disk"), and the Download action keeps offering the **original** file
(`clipMediaUrl`), not the copy. Every copy failure adds a **Play original** action beside Try again (a gone or
unplayable copy is exactly when the original is the way out); the page does not switch by itself, so a failure
stays loud and one press away from the fallback. Try again re-runs the probe.

### 6. The no-sound note follows the file, and points at the copy

**Decision**: the note is computed only when `choice === 'original'`. When the copy is ready (the operator chose
the original, or `mozHasAudio` is false on a clip whose copy exists) its detail gains one sentence: the preview
copy plays with sound; use Play preview copy. No note for the copy: it carries AAC by contract (D-21), so a
browser that finds no audio in it reports a broken copy, not a PCM clip, and the page does not invent a cause
(Principle I).

### 7. One line says which file plays; one control swaps it, last in the keyboard order

**Decision**: a `<p class="preview-source">` under the transport says "Playing the preview copy" or "Playing the
original", with the stated reason when the original plays by default (`stale`, `failed`, `unusable`; `absent`
says nothing more, it is the common case). The control sits after Set To (position 7), so the v1 order and every
v1 selector keep their place; it is a button, named "Play original of <name>" / "Play preview copy of <name>",
visible text "Play original" / "Play preview copy", offered only when a copy is ready. A press announces "Playing
the original of <name>." through the editor's live region, with the new file's notes once its metadata is read
(one message: the region holds one). The line and the control add no height after open
(the line is present from the first render); the stage keeps its fixed 16:9 box. With a coarse pointer the actions row's
lines are 1.5rem apart (not 1rem): four 26px buttons wrap at phone width, and each tap area reaches 9px out.

### 8. Where each part is tested

Pure logic is in modules `npm test` runs: `source.ts` (the table, words, length) and `previews.ts` (the
override), `clipMedia.ts` (address, probe, failure table, with a `fetch` stand-in as `thumbnail.test.ts` does).
The component's wiring is verified by `tsc`, the production build and Playwright from the scratchpad in Chrome 154
and Firefox >= 155 (task 5.1), including decoded sound.

## Risks / Trade-offs

- **A gate's names differ from the plan** → task 1.1 reads the merged `schema.d.ts` and `proxy-media-endpoints`'
  route first and stops and reports on a mismatch; specs name no field.
- **The probe adds a round trip before the first frame** → local and one byte; measured against the gate's
  100 ms bar and reported. If it costs more than the `v` is worth, the alternative is Decision 2(b) with a tag in
  the detail (a gate change), not a guess here.
- **Proxy time is not exactly the source's on some clip** (a VFR source, a copy whose `start_time` differs) → Set
  From would write a time the original does not show at that frame. `proxy-encode` asserts equal `start_time`;
  task 5.1 compares Set From on both files for the Sony clip, `h264-1080p50-aac.mp4` and a rotated clip, and a mismatch beyond one frame
  fails the task. Cuts are stored in milliseconds (D-14), so a sub-frame difference is within what a cut means.
- **The length differs between the two files** (facts' against the browser's reading, up to 60 ms in Firefox) → a
  cut accepted while the copy plays can be marked "runs past the clip's end" after switching to the original in
  Firefox. Accepted: the same rule as v1's "latest reading wins", and a mark, not a refusal.
- **A stale snapshot** → the detail's state can be older than the disk. A `ready` copy that is gone fails with a
  404 problem and is told as such (Decision 5); a `stale` one is not requested. Neither is retried by itself.
- **Autoplay after a source swap** → `play()` follows a press; Chrome and Firefox keep user activation across the
  swap. Verified in task 5.1 in both; if one refuses, the preview stays paused and says nothing wrong (the press
  is repeated).
- **Disk, CPU and cache** are the gates' and `proxy-encode`'s; this change reads the cache through the service only.

## Migration Plan

None: a client change over two additive gate changes. A clip without a ready copy behaves as in v1. Rolling back
is reverting the web change; no data is written.
