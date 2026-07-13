## Why

§4.13 is an explicit HLD requirement: *the system must not schedule (or run) a render for an event unless
a relevant change has been detected* — and it has been deliberately parked (T1/§8.14) since phase 7
began. Today every trigger re-renders everything: `_staleness_filter` is the identity function, `enqueue`
queues every event, and the worker renders whatever it claims. With the full service stack now live
(enqueue/worker/serve) — and a GUI "Render" button coming in phase 8 — unconditional re-rendering of a
whole archive graduates from annoyance to footgun. This change fills the seams that phases 6–7 left
waiting: the `_staleness_filter` no-op, the reserved `jobs.fingerprint` column, and the
`.auto-reel/cache/` sidecar home (D-AN4).

## What Changes

- Add a **probe-free render fingerprint**: a hash over the event's editorial document (`reel.yaml`
  canonical content), the resolved project look defaults (D-2), the on-disk clip set with each clip's
  content signal (size + mtime_ns, hash opt-in — the analysis cache's `clip_signal` precedent), and an
  **engine identity** (hand-bumped `RENDER_GRAPH_VERSION` constant + ffmpeg version string). No ffprobe
  calls — probe output is a function of file bytes, which the signals already cover — so the fingerprint
  is cheap enough for enqueue, claim, scan, and API reads, and **host-independent**: rendering the same
  event on CPU vs GPU is *not* a change (detection keys on upstream inputs only).
- Add a **render manifest sidecar**: `render-manifest.json` in `<event>/.auto-reel/cache/`, written by the
  engine **only on actual render success** (never on skip), recording the fingerprint, per-component
  sub-hashes (editorial / defaults / clip_set / engine — explainable staleness), output name, and
  timestamps. **Sidecar only — no Postgres mirror** (scan-on-request makes bulk queries unnecessary;
  deferred to the phase-8/9 index). The manifest travels with the media and survives a DB wipe (D-7).
- Add **one shared staleness gate** — stale ⇔ no manifest ∨ fingerprint differs ∨ output missing — applied
  at three points: the CLI `render` filter (the waiting seam), `enqueue` (CLI and API: fresh events are
  not enqueued), and the **worker's claim-time recheck** (a queued event that reverted to its
  last-rendered state skips instead of re-rendering).
- **BREAKING: collapse `--overwrite` into `--force`.** One flag that bypasses the gate *and* replaces an
  existing output ("render it again"). `render --overwrite` is removed; `enqueue`/`POST /jobs` gain
  `force`, carried on the job row (additive column) so it survives to claim time. The engine's
  skip-if-exists mechanics are unchanged — only the operator surface collapses.
- Surface **explainable staleness**: `scan` prints per-event freshness with the changed components
  ("stale: clips, editorial"); the API event detail includes the same. `jobs.fingerprint` is stamped at
  enqueue (the reserved column earns its keep).
- In gated paths, the **gate verdict drives output replacement**: an event judged stale renders with
  overwrite — once the gate exists, the manifest (not bare file existence) is what "already done" means,
  and a stale event's existing output is by definition outdated. The engine's skip-if-exists remains as a
  backstop for ungated/direct use. This closes the otherwise-infinite loop for "output exists but no
  manifest" (stale → engine skip → still no manifest → stale …).
- Add a **one-time manifest adoption tool** (`auto-reel adopt-renders`): for events whose output exists,
  the operator asserts "current outputs are up to date" and manifests are written at the current
  fingerprint — so deploying this change onto the existing rendered archive does not trigger a full
  re-render. Explicit, operator-invoked, never automatic.

## Capabilities

### New Capabilities
- `change-detection`: The fingerprint composition and its probe-free/host-independent contract, the
  staleness gate rule (including force bypass and the MISSING-clip edge), the render-manifest sidecar
  (location, contents, write discipline), and explainable per-component staleness.

### Modified Capabilities
- `movie-assembly`: On actual render success (not skip/dry-run) the engine writes the render manifest when
  a fingerprint is supplied with the job.
- `headless-cli`: `render` gates events through the staleness check and replaces `--overwrite` with
  `--force` (**BREAKING**); `enqueue` gates and gains `--force`; `scan` reports per-event staleness with
  reasons; a ninth subcommand `adopt-renders` performs the one-time manifest adoption.
- `job-store`: Schema gains a `force` boolean; `fingerprint` changes from reserved to stamped-at-enqueue;
  `enqueue` accepts both.
- `job-scheduler`: The worker rechecks staleness at claim time (after the plan rebuild) and completes
  fresh non-forced jobs as skipped-`done` without rendering.
- `api-service`: `POST /jobs` accepts `force` and reports a distinct "fresh — not enqueued" outcome;
  event detail includes staleness + reasons.

## Impact

- **New module**: `auto_reel_ng/staleness/` (or similar): fingerprint, manifest read/write, gate.
- **Engine**: `render_movie`/`RenderOptions` carry an optional fingerprint; manifest written after the
  atomic finalize.
- **Persistence**: one additive migration (`force`); `enqueue` signature grows (`force`, `fingerprint`).
- **CLI/API/worker**: gate calls at the three points; `--overwrite` removed (**BREAKING** for any script
  using it — replace with `--force`).
- **Reuses**: `clip_signal` (analysis cache), `.auto-reel/cache/` layout, D-2 config resolution, the
  atomic-finalize guarantee (output-exists is trustworthy input to the gate).
- **Tests**: fingerprint stability/sensitivity matrix, manifest write discipline, gate at all three
  points, force paths, MISSING-clip edge.

## Non-goals

- **No Postgres mirror / event index** — sidecar is the sole home; bulk indexing is phase 8/9.
- **No content hashing by default** — size+mtime (the analysis-cache precedent); hash opt-in config for
  the paranoid, but in-place same-size edits are accepted blind spots by default.
- **No automatic re-render on engine upgrade beyond the constant** — `RENDER_GRAPH_VERSION` is bumped by
  hand with documented duty; no source hashing.
- **No GUI surfaces** — badges/tooltips are phase 8; this change only makes scan/API expose the data.
- **No automatic manifest backfill** — un-manifested outputs register stale; settling them is the
  operator's explicit choice (`adopt-renders` to trust them, or let them re-render). Nothing adopts
  silently.
