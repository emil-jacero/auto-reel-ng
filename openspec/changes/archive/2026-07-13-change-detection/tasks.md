## 1. Fingerprint + manifest core (pure, no consumers)

- [x] 1.1 Create the staleness module: the four-component fingerprint (editorial canonical form per the
  design's open question — settle parsed-canonical vs raw-bytes with a reformat test; defaults; clip_set
  reusing `clip_signal`; engine = new `RENDER_GRAPH_VERSION` constant + ffmpeg version) with per-component
  sub-hashes. Golden tests: stability across two invocations, sensitivity matrix (each component alone
  moves the fingerprint + its sub-hash), device-independence, no-ffprobe assertion.
- [x] 1.2 Manifest read/write for `<event>/.auto-reel/cache/render-manifest.json` (schema version,
  fingerprint, sub-hashes, output name, engine identity, timestamp). Tests: round-trip; corrupt/invalid →
  treated as absent (fail open); schema-version mismatch → absent.
- [x] 1.3 The gate: `evaluate(...)` → verdict {stale, reasons} per the rule (no manifest ∨ fingerprint
  differs ∨ output missing); reasons from sub-hash comparison. Tests: fresh, each stale arm, reasons name
  exactly the changed components, MISSING-referenced-clip → stale via clip_set.

## 2. Engine: manifest write on success

- [x] 2.1 Add optional fingerprint to `RenderOptions`; `render_movie` writes the manifest immediately
  after the atomic finalize succeeds — never on skip/dry-run/failure/no-fingerprint. Tests: all four
  never-write paths + the success path ordering (manifest only after rename).

## 3. CLI render + flag collapse (BREAKING)

- [x] 3.1 Wire the gate into `_staleness_filter` (compute after `prepare_event`/persist per D-C5 —
  fingerprint must reflect post-adoption disk); stale verdict (or `--force`) drives overwrite; fresh
  events reported and skipped. Replace `--overwrite` with `--force` in `render` (removed flag → usage
  error). Tests: unchanged project renders nothing on second run; edit → only that event re-renders;
  `--force` re-renders fresh + replaces output; `--overwrite` exits non-zero; adoption-then-fingerprint
  ordering.
- [x] 3.2 `scan` staleness column with reasons. Test fresh + stale-with-reasons output.

## 4. Store: force column + stamped fingerprint

- [x] 4.1 Additive Alembic migration: `force` boolean default false. Update model, schema-drift test.
- [x] 4.2 `enqueue(..., force=False, fingerprint=None)`: stamp both. Tests: defaults, values persisted,
  idempotent path unchanged.

## 5. Gated enqueue (CLI + API)

- [x] 5.1 CLI `enqueue`: gate per event — stale → job (fingerprint stamped); fresh → reported, no job;
  `--force` → all events, `force=true`. Tests: mixed stale/fresh project, force path, idempotence
  unchanged.
- [x] 5.2 API `POST /jobs`: gate + `force` field; 201 created / 409 active-duplicate / 200 "fresh — not
  enqueued" with verdict. Tests: all three outcomes + forced-fresh → 201.
- [x] 5.3 API event detail: staleness verdict + reasons in the response (read-only, no manifest writes).
  Tests: fresh, stale-with-reasons, and that GETs never write.

## 6. Worker: claim-time recheck

- [x] 6.1 After plan rebuild (skip if `job.force`): re-evaluate the gate; fresh → transition `done` with
  progress 1.0, no render; stale → render with overwrite. Tests: revert-while-queued → done without
  ffmpeg; forced fresh job renders; stale-with-existing-output replaces (no existence-skip); requeued
  finished orphan (manifest written, transition lost) → absorbed as done without re-render.

## 7. Adoption + closeout

- [x] 7.1 `auto-reel adopt-renders` (`--years` honored): manifest at current fingerprint iff output
  exists; renders nothing; per-event report (adopted / unrendered / already fresh). Update entry-point
  test to nine subcommands. Tests: archive adoption end-to-end (adopt → enqueue finds all fresh),
  unrendered skip.
- [x] 7.2 Docs: README — the gate semantics, `--force` migration note (**BREAKING**: `--overwrite`
  removed), `RENDER_GRAPH_VERSION` bump duty, and the deploy step "run `adopt-renders` once over an
  existing archive". Module docstrings.
- [x] 7.3 Full suite + lint green; dogfood on `auto-reel-media/`: render → re-run renders nothing → edit
  one `reel.yaml` → only that event re-renders (via both CLI and enqueue/worker paths); record results in
  the change notes.

  **Result (2026-07-12):** Full suite green (`pytest`, 300+ tests including the real podman-Postgres
  `requires_db` suite); `black`/`isort` clean; `mypy` clean (88 source files); `pylint` 9.97/10 with the
  only remaining findings pre-existing (`cairo` no-member in `render/title/render.py`, unrelated to this
  change; delta `+0.00` vs. the prior run). The `test_migrations_match_models` drift test confirms the
  new `force` column migration matches the SQLAlchemy model exactly.

  Dogfooded against a symlinked scratch copy of `auto-reel-media/input/2024/2024-06-27 - grillning med
  grannar` (4 real 1080p h264 clips) rather than the shared fixture directly — clips symlinked in
  read-only, all writes (reel.yaml, output/, `.auto-reel/cache/`) confined to scratch. `auto-reel render`
  end to end via the real AMD VAAPI GPU: first run renders in ~6s and writes the manifest; an immediate
  second run reports the event `FRESH` in ~2s with zero ffmpeg invocations; editing the `reel.yaml` title
  re-renders only that event (`OK`, new output filename, new manifest fingerprint). The `enqueue`/`worker`
  path was dogfooded separately against a throwaway podman Postgres with `alembic upgrade head`: `enqueue`
  on the fresh project reported `fresh, not enqueued` with zero jobs created; editing `reel.yaml` again
  and re-running `enqueue` created exactly one `queued` job; `auto-reel worker` claimed it, rebuilt the
  plan, re-evaluated the gate (stale, since the edit landed after enqueue), rendered, and transitioned the
  job to `done`; a follow-up `enqueue` against the now-fresh event again reported `fresh, not enqueued`,
  confirming the claim-time-written manifest round-trips correctly back through the gate.
