## Why

The operator's request, 2026-10-03, with screenshots of the event page's read view: "Watching a clip should be a play
button on the clip. Also if one player, any player, is already playing and you start a clip player it should pause the
other one."

Two things in the page today do not match that.

1. **Playing a clip is a text button in the file cell.** `clip-play-read-view` gave every clip on disk a "Watch" button
   under the clip's name and above its cuts indicator (`events/ClipWatch.tsx`, `WatchButton`). The frame beside it, the
   one thing in the row that looks like a video, does nothing. That change chose the word "Watch" over "Play" because
   an open player's own button is named "Play <name>" and two controls with one name would be ambiguous (its design,
   "The row's control is Watch, not Play"). The operator has now asked for the play control on the clip itself, so the
   reason to avoid "Play" has to be met another way: the control changes its name while the player is open.
2. **"One player" is two mechanisms, each installed in one place.** `playback/exclusive.ts` is a registry the Movie
   section and the Timeline claim from by hand; `events/onePlayer.ts` is a capturing `play` listener that
   `EventDetailBody` installs for the clip players. A new kind of player has to be remembered by whichever mechanism
   it joins, and a pair of players that neither mechanism names is not covered. The operator said "any player".

## What Changes

- **A play control on the clip's thumbnail in the read view.** A button laid over the thumbnail's box, filling it, with a
  play glyph in a disc at its centre, named "Play <name>"; it replaces the "Watch" button in the file cell, which goes.
  It is seen on hover, on keyboard focus, while the player is open, and always under a coarse pointer; it is always
  reachable by Tab. Its box is the thumbnail's (at least 80 x 45 CSS pixels), so a press or tap anywhere on the frame
  reaches it and the 44 x 44 rule holds. A missing clip gets none. While the player is open the control shows the hide
  icon and is named "Hide player of <name>", which is also what keeps its name apart from the player's own "Play
  <name>" / "Pause <name>". Opening, one player at a time, nothing loading before a press, Close and Escape returning
  focus to the control, and what a re-read does to an open player are as `clip-play-read-view` made them.
- **One coordinator for "one video plays".** A single module, `playback/coordinator.ts`, replaces `exclusive.ts` and
  `onePlayer.ts`: one capturing `play` listener on the document, installed once in `main.tsx`, pauses every other playing
  `<video>` of the page. No player claims or releases anything, so the movie player, a clip's player in the read view, a
  clip's preview in Edit mode and the Timeline are covered without being named, and so is any player added later. It
  pauses and does nothing else: it never closes, replaces, restarts or seeks a player.
- **The Timeline does not take playback back across a boundary.** When another video starts while the Timeline's file is
  changing at a clip boundary, the Timeline stays paused. (Without it the Timeline's own resume would be the last start
  and would pause the player the operator had just started.)
- **Specs and docs**: three MODIFIED requirements in `web-app`, one ADDED in `event-timeline`, `web/README.md` and the
  HLD (D-15, D-16, D-20, section 4.10 and section 6), as tasks.

## Non-goals

- **Edit mode's thumbnail is unchanged.** It is already a "Watch <name>" button (a second way to the Cuts panel's
  Watch); its words, its box and its requirement stay. Only the read view's control moves to the thumbnail.
- **No autoplay on open is added or removed.** A player does not play by itself when it opens (as before); the operator presses its Play, which the coordinator sees.
- **No closing, queueing or resuming.** The paused player stays where it is; nothing resumes it when the other stops.
- **No new player, no new route, no server work, no new dependency** (Principle VII). `ClipPreview`, `previews.ts`
  and the player's keys, notes and failures are untouched. No `RENDER_GRAPH_VERSION` bump.
- **No change to the readouts.** The time readouts of the clip player and the Timeline are `time-readouts-legible`
  (the gate); this change neither touches nor depends on its formatter.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `web-app`:
  - MODIFIED `Requirement: The event page watches a clip on request`: the control is the play control over the
    thumbnail (name, glyph, when it is seen, its area, no Watch button in the file cell, the open state's name), with the
    scenarios that named "Watch" renamed.
  - MODIFIED `Requirement: Every clip row shows a frame from its clip`: the read view's thumbnail carries the play control
    ("outside Edit mode the thumbnail SHALL NOT be focusable" no longer holds for the control); Edit mode's rule is
    unchanged.
  - MODIFIED `Requirement: The event page plays one video at a time`: every pair of the page's players, one rule held in
    one place, no pair named, with the thumbnail's start, the Timeline and Edit mode's preview among the scenarios.
- `event-timeline`:
  - ADDED `Requirement: The Timeline pauses, and is paused, like every other player`: what a pause by another player
    leaves untouched, and the boundary case.

## Impact

- **Packages:** `web/` only: `events/ClipWatch.tsx` (the `WatchButton` becomes the thumbnail's control), `events/EventDetail.tsx`
  (the thumbnail cell, the file cell, the removed effect), `events/ClipThumb.tsx` (an optional overlay slot, no behavior
  change), `events/detail.css`, `playback/coordinator.ts` (new, replaces `playback/exclusive.ts` and `events/onePlayer.ts`
  with their tests), `main.tsx`, `movie/MoviePanel.tsx` and `timeline/useTimelineVideo.ts` (their claim and release calls
  go), `web/README.md`; plus `docs/high-level-design.md`.
- **CLI vs API (Principle V):** untouched; the page reads the routes it reads.
- **Rendered output:** unchanged. No `RENDER_GRAPH_VERSION` bump; no staleness fingerprint input.
- **Schemas:** `reel.yaml`, `config.yaml`, `web/openapi.json` and `schema.d.ts` unchanged; no migration.
- **Dependencies:** none new.
- **Gate:** `time-readouts-legible` (web only, a shared time formatter and the readout CSS of the clip player and the
  Timeline). It is not on `origin/main` (`143f0fc`) when this is written, so nothing here uses its names; the two changes
  can touch `preview/preview.css` and `timeline/timeline.css`, and `ClipPreview.tsx`'s header, but this change edits none
  of them. Task 1.1 re-checks.
- **Evidence relied on:** the operator's request above; `clip-play-read-view`'s design (the Watch-not-Play decision and
  why, the player row, the store) and its archived specs; the code at `143f0fc` (`events/ClipWatch.tsx`,
  `events/onePlayer.ts`, `playback/exclusive.ts`, `movie/MoviePanel.tsx`, `timeline/useTimelineVideo.ts`,
  `events/EventDetail.tsx`, `events/thumbs.css`, `preview/preview.css`); the HTML media-element rules (the `play` event
  fires when `paused` becomes false and does not bubble, so one capturing listener on the document hears every video;
  a seek or a `load()` fires no `play`). The v2 research (`synthesis.md` section 5, `timeline-library.md`) decides the
  Timeline's single `<video>` with a source swap at clip boundaries, which is why the boundary case exists.
- **Size (Principle VIII):** one package, two capability deltas, nine tasks.
