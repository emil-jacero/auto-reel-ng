## Context

§4.13/§8.14 were parked as T1 through all of phase 7; the seams were built waiting: `_staleness_filter`
(identity no-op in `cli/commands.py`), the reserved `jobs.fingerprint` column (7a), and the
`.auto-reel/cache/` sidecar directory with its `clip_signal` size+mtime contract (phase 6, D-AN4). The
atomic-finalize guarantee (7b, D-S2) makes "a file at the final path is a complete verified render" true —
a load-bearing input to any staleness rule. The 2026-07-12 explore session settled the §8.14 questions
(memory: `auto-reel-ng-phase7-decisions`, T1 entry); this design records them and the one wrinkle found
while drafting: gate-verdict-drives-overwrite.

## Goals / Non-Goals

**Goals:**
- A no-op-safe pipeline: scanning, enqueueing, or batch-rendering an unchanged project performs **zero**
  renders (§4.13's core requirement), with `--force` as the explicit bypass.
- A fingerprint cheap enough to compute at every decision point (no ffprobe, no full-file reads by
  default) and identical on every host.
- Staleness that can explain itself (which component changed).
- A safe landing on the existing archive (no surprise full re-render; explicit adoption instead).

**Non-Goals:** PG mirror/event index, default content hashing, GUI surfaces, automatic adoption, source
hashing for engine identity (see proposal).

## Decisions

### D-C1 — Probe-free, host-independent fingerprint
`fingerprint = H(editorial, defaults, clip_set, engine)` where *editorial* = the event's `reel.yaml`
content in canonical form (or the folder-seed equivalent when absent), *defaults* = the resolved D-2 look
defaults that feed `resolve()`, *clip_set* = the sorted on-disk clip identities each with its
`clip_signal` (size + mtime_ns; sha256 when the existing hash opt-in is enabled), *engine* = a hand-bumped
`RENDER_GRAPH_VERSION` constant + the ffmpeg version string. *Why probe-free:* ffprobe output is a pure
function of file bytes, which the signal already covers — so omitting probe data loses nothing while
making the fingerprint computable at enqueue/scan/API time in microseconds. *Why host-independent:* the
device/vendor path (CPU vs VAAPI encode of the same look) is deliberately **excluded** — same movie,
different producer; including it would poison cross-process comparison (API enqueues, worker renders).
*Alternative rejected:* hashing the resolved `RenderPlan` — needs probes, and adds nothing the components
don't already determine.

### D-C2 — Sidecar manifest, no mirror
`render-manifest.json` lives in `<event>/.auto-reel/cache/` (the D-AN4 home, beside analysis entries).
Contents: schema version, the fingerprint, the four component sub-hashes, output filename, engine identity
(readable form: constant + ffmpeg version), and a written-at timestamp. It is the **sole** persistent
record — no Postgres copy. *Why:* every consumer (CLI filter, enqueue, claim recheck, scan, API events
read) touches the event dir at decision time anyway (7c scan-on-request); a mirror would be a second
disk⇄DB sync mechanism ahead of the phase-8/9 index that will subsume it. D-7 holds trivially: the
manifest travels with the media and survives a DB wipe.

### D-C3 — One gate function, three call sites
`evaluate(event_dir, …) → Verdict{stale: bool, reasons: [components]}` with the rule: **stale ⇔ no
manifest ∨ fingerprint ≠ manifest.fingerprint ∨ output missing**. Call sites: (1) `cmd_render`'s
`_staleness_filter` — finally not the identity; (2) enqueue (CLI + API `POST /jobs`) — fresh events are
reported, not enqueued; (3) the worker at claim time, after the plan rebuild — catching both disk changes
while queued *and* reverts (a queued event back at its last-rendered state completes as skipped-`done`
without rendering). `--force` bypasses the gate at every site. Reasons come from comparing component
sub-hashes — free explainability (D).

### D-C4 — Gate verdict drives overwrite in gated paths
Once the gate exists, **the manifest — not bare file existence — is the meaning of "already done"**: a
stale verdict implies the existing output is outdated, so gated paths render with overwrite. The engine's
skip-if-exists stays untouched as a backstop for ungated/direct library use. *Why this is load-bearing:*
without it, "output exists but no manifest" loops forever (stale → engine skips on existence → no manifest
written → still stale). It also upgrades 7b's requeue absorption: a requeued finished orphan is now
absorbed by manifest verification (fresh → skipped-`done`) rather than bare existence — strictly stronger,
since a mid-concat crash leaves no manifest and correctly re-renders.

### D-C5 — Manifest write discipline: engine writes it, only on actual render success
The caller (CLI/worker) computes the fingerprint pre-render and passes it via `RenderOptions`; the engine
writes the manifest immediately after the atomic finalize (verify → rename) succeeds. Never on skip, never
on dry-run, never on failure; absent fingerprint (direct library use) → no manifest, event simply stays
stale-by-absence. *Why the engine:* both driving paths (CLI `render`, worker) converge in `render_movie`,
and writing after the rename means a manifest can never describe an output that didn't finish. *Sequencing
note:* fingerprint is computed **before** the render (adoption may rewrite `reel.yaml` during
`prepare_event`; the manifest must record the state that was actually rendered — which is post-adoption
disk state, so compute it **after** `prepare_event`/persist, before rendering).

### D-C6 — `--force` absorbs `--overwrite` (BREAKING, CLI-only)
One operator concept: "render it again". `--force` bypasses the gate and replaces output; `--overwrite` is
removed from `render` (scripts migrate by renaming the flag). The engine's `RenderOptions.overwrite`
mechanics are unchanged (now driven by gate verdict ∨ force). Jobs carry an additive `force` boolean so
the flag survives enqueue → claim; `POST /jobs` takes `force`; the GUI's future "Re-render" button is a
forced enqueue.

### D-C7 — Explicit one-time adoption for the existing archive
`auto-reel adopt-renders`: for each selected event whose output file exists, write a manifest at the
current fingerprint — the operator's assertion that today's outputs reflect today's inputs. Explicit,
never automatic, reported per event; events without outputs are untouched (they're genuinely unrendered).
*Why:* deploying the gate onto years of already-rendered footage must not schedule an archive-wide
re-render (hours of GPU time) just because manifests didn't exist yet. *Alternative rejected:* silent
adopt-on-first-scan — violates "nothing adopts silently" (the operator may *know* an output is outdated).

### D-C8 — Engine identity = documented constant + ffmpeg version
`RENDER_GRAPH_VERSION` is bumped by hand when a change alters produced output for identical inputs
(command-graph changes, filter changes, encoder flag changes); the ffmpeg version string is read from the
runtime the process actually uses. Under-bump risk (missed re-renders) is accepted and mitigated by
`--force`; over-bump costs one archive re-render. *Alternative rejected:* hashing render-module source —
false-positives on every refactor.

## Risks / Trade-offs

- **[mtime granularity / in-place same-size edits]** → size+mtime_ns misses an edit that preserves both.
  Accepted default (same trust the analysis cache extends); sha256 opt-in exists for the paranoid.
- **[Fingerprint drift between call sites]** → enqueue-time and claim-time computations must agree or jobs
  flap. Mitigation: one function, one canonicalization, golden tests asserting byte-identical fingerprints
  across (enqueue vs claim) invocations on an unchanged fixture.
- **[Adoption during render mutates editorial]** → `prepare_event(adopt=True)` rewrites `reel.yaml`, which
  changes the editorial component *during* the pipeline. Mitigation (D-C5): compute the fingerprint after
  prepare/persist — the manifest records what was actually rendered. Scenario-tested.
- **[Manifest corruption/hand-editing]** → unreadable manifest = no manifest = stale. Fail-open to
  re-render, never fail-closed to skip.
- **[TOCTOU between gate and render]** → disk changes after the claim-time check but before render finish;
  the manifest then records pre-change fingerprints? No: fingerprint is computed from the same disk state
  the plan was built from; a change mid-render is caught the *next* gate pass. Accepted (same window every
  build system has).
- **[BREAKING `--overwrite` removal]** → any existing script/automation using it breaks loudly (unknown
  flag). Accepted: pre-1.0, single operator, migration is a rename.

## Migration Plan

1. Fingerprint + manifest module with golden stability/sensitivity tests (pure, no consumers yet).
2. Engine: `RenderOptions.fingerprint` + manifest write after finalize.
3. Gate function; wire site 1 (CLI `render` + flag collapse), then site 2 (enqueue CLI/API + migration for
   `force` + fingerprint stamping), then site 3 (worker claim recheck).
4. `adopt-renders` + `scan`/API staleness surfaces.
5. **Operator step on deploy: run `adopt-renders` once** over the existing archive (documented in README).
6. **Rollback:** module and column are additive; reverting the CLI flag collapse restores `--overwrite`;
   manifests on disk are inert JSON if the gate is removed.

## Open Questions

- **Canonical form of the editorial component:** raw file bytes (simplest; whitespace edits register as
  changes) vs parsed-and-canonicalized YAML (semantic; a reformat is not a change). Lean: **parsed
  canonical** — ruamel round-trips preserve comments, and a GUI (phase 8) rewriting `reel.yaml` must not
  strobe staleness on formatting. Settle at implementation with a test either way.
- **Does `enqueue` stamp reasons too?** The fingerprint column takes the value; are the component reasons
  worth a JSONB column now, or is recomputing at read time fine? Lean: recompute (they're cheap and the
  manifest holds the sub-hashes). Settle when wiring the API response.
