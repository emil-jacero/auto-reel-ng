## Why

The operator's request, 2026-10-03: "I would like for the play feature to work outside the edit view".

A clip can be played only in Edit mode (HLD **D-16**, change `clip-preview-screen`): the player lives in the clip's Cuts
panel, which exists only in Edit mode. On the event page's normal view the operator sees a thumbnail, a name, a status
and, for a clip with cuts, "2 cuts · −4.5 s" (`ReadCuts`), and to look at the clip itself must enter Edit mode, a mode
that holds unsaved-changes rules, a save bar and a Cuts panel full of controls that write `reel.yaml`. Watching footage
is a read; it should not need the editor.

`clip-preview-proxy` (the gate) made that player good: it plays the clip's 540p preview copy when one is ready (sound in
Firefox for the Sony clips whose PCM audio Firefox cannot play, research `pcm-audio.md` §1.2), the original otherwise,
with an explicit **Play original** (HLD §4.10 v2, **D-21** for the copy's contract). This change gives the read view
that same player. It is HLD §6 phase 9 (GUI v2), a client-only slice after the gate.

## What Changes

- **A Watch control on every clip row of the event page's read view** whose file is on disk (any status but missing).
  It is the same control, with the same words, as Edit mode's: "Watch" with the play icon, named "Watch <name>", and
  while its player is open "Hide player", named "Hide player of <name>". It is the row's Play control: the name
  "Play <name>" is the open player's own Play button (`playName`), so the row's control keeps Edit mode's word to stay
  distinct from it.
- **It opens the existing preview component, in a row of its own under the clip's row.** The component is reused, not
  forked: it plays the preview copy when one is ready and the original otherwise, says which, offers Play original,
  and shows the no-sound note for the original in Firefox, all as `clip-preview-proxy` made it. One preview is open
  at a time; Close and Escape return keyboard focus to the row's Watch control.
- **The player has no cut controls here.** No Set From, no Set To, nothing that edits. The clip's cuts, as the event
  page already reads them (`useReadCuts`), are drawn read-only on the cut bar, and **Skip cuts** stays as a view
  option on a clip that has cuts, plays the clip as the movie will. Failures that today say "stop editing" say
  "Refresh" here.
- **Nothing loads until a Watch is pressed.** The 400-clip event creates no video element and makes no media, proxy
  or filmstrip request on opening, scrolling or refreshing.
- **One thing plays at a time on the event page.** A clip's player and the page's Movie player can both exist in the
  read view (they cannot in Edit mode), so a video that starts pauses another that plays. Nothing is closed.
- **Spec and docs**: four ADDED requirements in `web-app` (no MODIFIED: the two requirements the gate modifies are
  left alone and referred to), `web/README.md`, HLD edits (task 5.1).

## Non-goals

- **Not a second player.** `ClipPreview` gets one optional prop's worth of change (it is read-only when it is given
  no `onSet`); its file choice, copy probe, notes and keyboard rules are the gate's and are not restated.
- **No timeline.** `timeline-view`, `timeline-trim`, `timeline-overlays` and the filmstrip are other changes. This
  change requests no filmstrip and no Prepare action (`proxy-enqueue-endpoint`): an unprepared clip plays its original.
- **The thumbnail is not a button here.** Edit mode makes it one (a second way to Watch); the read view gets one
  control per row, and the thumbnail keeps its box and its "No preview" behavior unchanged.
- **No cut editing from the read view, no pointer drag on the bar that writes anything.** Seeking is playback, not an
  edit.
- **No live update** of a clip's proxy state, the same as the gate: the state is the one the event detail was read
  with.
- **No server work, no new endpoint, no new dependency** (Principle VII), no change to what Save writes, to
  `reel.yaml`, to staleness or to the render. No `RENDER_GRAPH_VERSION` bump.
- **Edit mode is unchanged.** Its Cuts panel, its Watch control and its thumbnail button keep their behavior and their
  requirements; `EventEditor` is not refactored (its announcer stays its own).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `web-app`:
  - ADDED `Requirement: The event page watches a clip on request`: the control, where the player opens, one at a
    time, focus, nothing loads before it, what a re-read does to an open player, size and look.
  - ADDED `Requirement: A clip watched on the event page is played, not edited`: no Set From / Set To, the cuts
    read-only on the bar, Skip cuts, the keyboard order, the read view's live region and "Refresh" advice, writes
    nothing.
  - ADDED `Requirement: The event page plays one video at a time`: a started video pauses the other one.

  The first two requirements refer to `Edit mode previews a clip on request` and `A clip's preview plays its preview
  copy when one is ready` for everything the player does; neither is modified.

## Impact

- **Packages:** `web/` only: `events/EventDetail.tsx` (the row's cell, the store, the live region), `events/watch.ts`
  (new, pure), `events/ClipWatch.tsx` (new), `events/onePlayer.ts` (new, small), `events/detail.css`,
  `preview/ClipPreview.tsx` and `preview/playback.ts` (the read-only difference), `README.md`; plus
  `docs/high-level-design.md`.
- **CLI vs API (Principle V):** untouched; the page is a client of routes that exist (`media`, and `proxy` from the
  gates), reading `reel.yaml` through the `reel` read it already makes.
- **Rendered output:** unchanged. No `RENDER_GRAPH_VERSION` bump; no staleness fingerprint input.
- **Schemas:** `reel.yaml`, `config.yaml`, `web/openapi.json` and `schema.d.ts` are unchanged; no Alembic migration,
  no rescan.
- **Dependencies:** none new.
- **Gate (merged into origin/main before implementation):** `clip-preview-proxy`, which adds `preview/source.ts`,
  the Play original control, `probeProxy`, and the proxy state on the `clip` prop of `ClipPreview`. Task 1.1
  re-checks every name on main. This change is written against the gate's own design, not its code.
- **Evidence relied on:** `synthesis.md` §5 row 9 and the user's request above; `pcm-audio.md` §1.2 and §2 (a) for why
  the copy matters in this view (Firefox 155 and 157 are silent on 2947 of the archive's 5574 clips' originals);
  the code at `ac4f356` (`ClipPreview.tsx`, `previews.ts`, `CutsPanel.tsx`, `ReadCuts.tsx`, `EventDetail.tsx`,
  `MoviePanel.tsx`) for what is reused.
- **Size (Principle VIII):** one package, one capability delta (three ADDED), ten tasks.
