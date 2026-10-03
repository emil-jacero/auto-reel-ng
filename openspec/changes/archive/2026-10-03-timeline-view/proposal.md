## Why

GUI v1 edits cuts by typed times, with a one-clip preview (D-14, D-16). HLD §4.10 moved "the full timeline editor"
into v2 (2026-10-01, the operator's decision): one track for the whole event, with a filmstrip, scrubbing and,
later, drag-trim and analysis overlays. The v2 research (`research/v2/`: `synthesis.md`, `proxies.md`,
`timeline-library.md`, `pcm-audio.md`) settled the ground under it, and the gates of this change have built it:

- **D-20 (timeline)**: built in the repo, no library; the pure model (`web/src/timeline/model.ts`) landed with
  `timeline-model`. The research prototype showed the interaction cost is small (60 fps drag to 400 clips at 4x CPU
  with windowing) and that no surveyed library gives keyboard access.
- **D-21 (proxy contract)**: a 540p H.264 + AAC proxy and a filmstrip sprite per clip, in a cache outside the
  library, with a `facts.json` per clip. `proxy-state-read` puts each clip's proxy state and facts on the event
  detail, `proxy-media-endpoints` serves the proxy and the sprite, and `proxy-enqueue-endpoint` starts the
  `proxy` job. The API has no clip fps or dimensions of its own (HLD §4.9: the events read is probe-free), so
  **a timeline can only be laid out from proxy facts**; research X6, risk 9.

What is missing is the screen. Nothing in `web/` lays a clip out by its length, scrubs, or starts a proxy job,
and the render region would show a `proxy` job as a render the moment `proxy-enqueue-endpoint` lands (the jobs
reads gain `kind`; the event page shows "the newest job it knows for that event").

This is HLD **§6 phase 9** (GUI v2), the first slice of the timeline editor: **read-only** (research §5, row 10).
Trim handles (`timeline-trim`) and analysis overlays (`timeline-overlays`) build on it. The Firefox decision is
the user's (locked in the v2 brief): the proxies carry AAC, so the timeline, and any clip preview that plays a
proxy, has sound in Firefox; the original clip stays silent there with the existing note.

## What Changes

- **A Timeline section on the event page** (read view; `web/` only; no new route). Its own toggle, not an entry
  to Edit mode: Edit mode owns the draft, the Save bar and the unsaved-edits guard, and this slice writes nothing.
  `timeline-trim` decides how the same component is mounted inside Edit mode.
  - Closed by default. **Nothing loads until it is opened**: no `<video>`, no media request, whatever the number of
    clips.
  - Absent in Edit mode. A Refresh or leaving Edit mode closes it (the page's content is replaced).
- **A Prepare state** when any clip the timeline would show has no ready proxy: per-state counts in words, a
  **Prepare proxies** button (`POST /api/v1/events/{id}/proxies`), live progress of the `proxy` job over the
  existing WebSocket, and a re-read of the event when the job ends. Opening the timeline never starts a job.
- **The timeline** once every shown clip has a ready proxy:
  - a ruler, the clips laid end to end in play order with their widths from the proxy facts' duration, a
    **chapter band**, and each clip's **filmstrip** (the sprite, drawn tile by tile)
  - the clips' existing cuts as striped spans (read from `GET …/reel`, as the event page already does); no
    handles, no edits
  - **zoom** (buttons, keys, Fit; 4 to 240 px/s, the model's bounds) inside the timeline's own scroller, **windowed** rendering
  - a **playhead** that scrubs on one `<video>`: pointer on the ruler or track, keys, a slider; the video's `src`
    swaps to the next clip's proxy at a boundary (a short flash is accepted)
  - **Play / Pause** from the playhead, skipping cuts as the movie will (D-16's merge rules, reused), advancing
    clip to clip, with sound
  - the movie's length (source length minus the cuts)
- **One playing video per page**: starting the timeline pauses the movie player, and the reverse.
- **Jobs read by kind.** The render region, the list rows and the header counts show `render` jobs only (the
  `job-kind` change did this in code: `web/src/jobs/kinds.ts`); a `proxy` job is shown only by the Prepare state,
  in its own words. This change writes the rule into the `web-app` requirements and adds the proxy side.
- **Quality bar**: keyboard and a slider's ARIA, 320–1280 px with no page-level horizontal scroll, reduced motion,
  light and dark, 44 px touch targets under a coarse pointer, state never by color alone. The research's scrub gate
  holds in Chrome 154 and Firefox ≥ 155 on the shipped proxy: **median scrub ≥ 30 fps and frame-step p90 ≤ 60 ms**.
- **HLD**: D-20 gains the first-slice record; §4.10, §6 phase 9, D-15 and D-16's "what stays v2" lines are updated.

### Non-goals

- Trim handles, snapping, typed-time sync, Save (`timeline-trim`); the analysis lane and approve/reject
  (`timeline-overlays`); undo.
- Reordering or moving clips between chapters on the timeline (stays list-based in Edit mode).
- A waveform or loudness lane; a second preloaded `<video>` for seamless boundaries; HLS, live transcode, or a
  synced `<audio>` sidecar (all rejected in the v2 brief).
- Cancelling a proxy job from the page (the cancel endpoint exists, a control for it is not this slice);
  an `original/` folder's clips (discovery skips them, so they have no proxy).
- Pinch zoom and Ctrl+wheel zoom (buttons and keys only); remembering the timeline's open state or zoom across
  visits.
- Any change to the API, the engine, `reel.yaml`, or the proxy contract. If the gates' wire names differ from the
  ones this change assumes, it follows the generated types (task 1.1), not the other way round.

## Capabilities

### New Capabilities

- `event-timeline`: the event page's Timeline section: when it opens, the Prepare state, the track (layout from
  proxy facts, chapter band, cuts, filmstrip, zoom, windowing), the scrubbing playhead and Play, keyboard,
  accessibility and layout.

### Modified Capabilities

- `web-app`: two requirements read "the newest job" and "jobs rendering" without a kind (the code already filters;
  the requirements do not say so). They become the newest **render** job and the **render** counts, so a `proxy`
  job is never shown as a render
  ("A render's progress is shown live", "The client follows render jobs live over one connection").

## Impact

- **Packages**: `web/` only (`web/src/timeline/` new; `web/src/api/proxies.ts` new; small edits in `web/src/jobs/`,
  `web/src/events/EventDetail.tsx`). `docs/high-level-design.md`. No Python, no `openapi.json`/`schema.d.ts`
  regeneration (the gates did that).
- **API / CLI**: both untouched (Principle V: the endpoints and `auto-reel proxies` already exist).
- **Rendered output**: unchanged. `RENDER_GRAPH_VERSION` is not bumped; the staleness fingerprint inputs are
  unchanged (proxies are not an input, D-21).
- **`reel.yaml` / `config.yaml`**: unchanged. **Alembic migration / rescan**: none.
- **Dependencies**: none added (no timeline library, no test runner: the existing `node:test` runner and
  `tsconfig.test.json` cover the pure modules). `@dnd-kit` is not used here. The bundle delta is measured and
  recorded in task 8.2 (budget: the research prototype measured +5.6 KB gz JS, +2.6 KB gz CSS for the whole
  interaction layer; this read-only slice is expected below that, plus the Prepare state).
- **Depends on** (merged before this change is implemented): `timeline-model`, `proxy-state-read`,
  `proxy-media-endpoints`, `proxy-enqueue-endpoint` (and through them `job-kind`, `proxy-encode`,
  `filmstrip-sprites`, `proxy-job`).
- **Principle VIII**: one package, one screen section; the Prepare state and the job-kind filter are its
  prerequisites on the page, not separate features. Read-only: no write path is added except the explicit
  Prepare action.
