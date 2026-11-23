## Why

The operator reported (2026-11-18): "Playback in editor is not smooth between the clips. When the playback goes from
one clip to the next it hangs for a split second, then continues."

This is a recorded trade-off, not a regression. D-20 (HLD §7, "The timeline is built in the repo") chose **one
`<video>` whose `src` is swapped at clip boundaries (a short flash is accepted)** and listed "a second preloaded
`<video>` for seamless boundaries" among what stays. At each boundary the Timeline today:
- notices the end of the clip, then swaps `src`, so the decoder and the audio path are torn down;
- waits for `loadedmetadata`, then seeks (always, even to the first frame), then waits for `seeked`;
- calls `play()` and waits for `playing`.

Nothing of the next clip is fetched or decoded before the boundary. A read-only probe of the running app
(2026-11-18, `docs/research/seamless-playback.md`) timed that chain at 35 to 60 ms in headless Chromium and Firefox
on loopback, plus 4 to 53 ms before the end was noticed. The proxy request, with its `no-cache` revalidation, was 4
to 17 ms of it. In a spike, two alternating, preloaded elements lost 20 to 30 ms less play time at every boundary in
all three browsers tried.

The title-card bridge already shows the fix works: the card's clip is loaded and sought behind the card, and that
hand-over has no gap (`timeline-plays-cards`). This change applies the same pattern to plain clip-to-clip
boundaries.

It is the last of the four follow-ups the operator agreed on 2026-11-18: shortcuts, a clip context menu, a plain clip
list, and seamless playback. It belongs to the editor workspace (HLD §6 item 10, GUI v3; `docs/editor-workspace.md`).
The operator chose the proper fix only, with no interim mitigation shipped on its own.

## What Changes

- **Two videos, one shown.** The Timeline's stage holds a **shown** `<video>` and, while the Timeline plays, one
  **standby** `<video>`:
  - The standby is muted and invisible (opacity 0, still rendered). It is hidden from assistive technology and
    unreachable by Tab.
  - While a clip plays, the standby loads the next clip's proxy and is sought to that clip's **first kept frame**:
    after a leading cut, the cut's end, not 0. It also carries that clip's turn.
- **The hand-over.** On the last kept frame of the playing clip:
  - the Timeline pauses the shown video, which keeps that frame on screen;
  - it unmutes the standby and plays it;
  - on the standby's first presented frame the two swap roles. The freed element then preloads the clip after that.
  - The playhead, cut skipping and the readout follow the new shown video as before.
- **Fallback, never worse than today.**
  - If the standby holds the right clip but is not ready yet, the last frame stays on screen until it is.
  - If the standby holds anything else (a re-targeted or failed load, or a clip shorter than its load), the boundary
    loads the clip into the shown video as today.
- **What does not change.** A boundary through a black title card keeps today's card bridge, which loads the clip
  behind the card. Scrubs, clicks, frame steps and cut skips inside a clip still drive only the shown video, through
  the seek coalescer.
- **The page's one-video rule.** The Timeline's two elements count as one player:
  - a paused standby never counts as playing;
  - the hand-over is the Timeline playing on, not a new start;
  - a clip preview releases both elements, as it released the one before.
- **Use as poster** takes the shown video's frame.
- **A boundary gate.** Measured in headed Chrome and Firefox over 20 boundaries, the incoming clip loses at most one
  frame of play time at the 90th percentile, and no frame is held longer than steady play holds one plus one frame.
  The measured scrub, frame-step and card hand-over gates are re-measured.

## Non-goals

- Gapless jumps over a cut **inside** a clip. Those stay a seek of the playing video, measured at p90 17 to 41 ms
  (`docs/research/browser-playback.md` §11). The standby could serve them later.
- Using the standby for scrubs, clicks, frame steps or Previous/Next clip.
- A crossfade or a gapless join of the sound. The sound stops at the outgoing clip's last frame and starts with the
  incoming one.
- Media Source Extensions or one continuous stream. That needs fragmented proxies, a `PROXY_VERSION` bump and
  re-encoding the archive (D-21).
- Changing the proxy encode, the proxy route or its `Cache-Control`. On loopback the request is 4 to 17 ms, which the
  preload hides. The route serves the current file whatever `v` says, so `immutable` caching could splice two versions.
- Preloading while the Timeline is paused, or preloading more than one clip ahead.
- The read view: it has no Timeline.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `event-timeline`:
  - ADDED "Play crosses a clip boundary without a pause" (with the measured gate) and "The Timeline's standby video
    is never seen, heard or counted as a player".
  - MODIFIED "The playhead scrubs one video": one shown video, and the flash is accepted only for a move of the
    playhead.
  - MODIFIED "Edit mode holds one video at a time": one player, whose standby exists only while it plays.
  - MODIFIED "The Timeline shows a clip's turn": the shown video, and the standby carries its clip's turn before it
    is shown.
- `web-app`: MODIFIED "The event page plays one video at a time". The Timeline's standby taking over at a clip
  boundary does not count as starting.

## Impact

- **Web only.**
  - `timeline/useTimelineVideo.ts` holds the two elements, the preload and the hand-over.
  - A new pure module `timeline/standby.ts` holds the standby's target and its load/seek/ready state, tested with
    `node:test`.
  - `timeline/Timeline.tsx` and `timeline.css` render the stage.
  - `timeline/posterFrame.ts` reads the shown element.
  - `playback/coordinator.ts` treats the Timeline's elements as one player through a predicate.
- **Unchanged:**
  - No API, engine, proxy-encode or route change, and no `Cache-Control` change.
  - No `reel.yaml` or `config.yaml` schema change, no Alembic migration and no rescan.
  - Rendered output, the staleness fingerprint and `RENDER_GRAPH_VERSION` do not change.
  - The CLI is untouched: this is browser playback of proxies, with no engine capability for the CLI to reach
    (Principle V).
  - No new dependency.
- **Complexity (Principle VII).** The cost is a second decoder while playing, and a hook that tracks which element is
  shown. A simpler fix does not remove the stall: skipping the extra seek, or warming the cache, still tears down the
  decoder at each swap. A second element is the smallest change that does (design, Research & Decisions).
- **Depends on** the last change of the plain clip bin series (`docs/editor-workspace.md`), and through it on
  `editor-shortcuts` and `clip-context-menu`. These touch the same Timeline and workspace files.
  - `clip-tab-and-player` (in that series) modifies two of the same requirements: "Edit mode holds one video at a
    time" and "The event page plays one video at a time", for the bin's player.
  - This change's MODIFIED blocks are copied from today's main specs, so task 0.1 copies them again from the
    archived result before any code.
- **Size:** about 2 to 3 days.
