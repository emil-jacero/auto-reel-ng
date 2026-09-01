## Context

See proposal.md — Why. The mechanics that shape the approach:

`list_events(settings, job_store)` walks the configured layout and, per event, loads `reel.yaml`, calls
`scan_event` (a directory walk) and reconciles the two. `staleness_for(settings, event_dir, document,
runtime)` currently resolves its own inputs:

```python
look_defaults = resolve_look_defaults(load_project_config(settings.project_root))
fingerprint = compute_fingerprint(fp_document, event_dir=..., look_defaults=..., ffmpeg_version=...)
verdict = evaluate(event_dir, output_path, fingerprint)
```

`load_project_config` is uncached — it re-reads and re-parses `config.yaml` on every call. Its two
current call sites (`get_event`, the editorial write route) each handle one event per request, so the
cost is invisible; a per-event loop makes it N reads of one file whose value cannot differ between
iterations. `compute_fingerprint` takes `use_hash: bool = False`; no `api/` call site passes it, and
`evaluate` adds one manifest read plus one `exists()` on the expected output path.

`FfmpegRuntime` is already built once per process on `app.state.runtime` (D-C1), so the engine component
costs nothing per event. `read_manifest` never raises — an absent, unreadable or malformed manifest
returns `None` and the gate reports `no_manifest`.

## Goals / Non-Goals

**Goals:**
- One `GET /api/v1/events` answers which events need rendering, with the same verdict shape and the same
  reasons the detail response already returns.
- The per-request cost of the list grows by directory `stat`s and two small file operations per event —
  not by a config parse per event, and not by any read of clip content.
- One staleness code path shared by list, detail and the editorial write echo. No second implementation
  that could drift from the gate.

**Non-Goals (design level; see proposal.md for scope):**
- Removing the duplicate directory walk (reconcile walks, then the clip-set component walks again).
- Any change to what a fingerprint contains, or to `staleness/` at all.

## Research & Decisions

### Where the resolved look defaults are computed

**Context**: `staleness_for` resolving its own project config is correct for one event and quadratic-ish
in spirit for a list. The value is per-request, so the loop must not own it.

**Explored**: Three placements were considered — memoizing `load_project_config` (an `lru_cache` keyed
by root), caching `ProjectConfig` on `app.state`, and passing the resolved defaults into `staleness_for`
as a parameter.

**Decision**: `staleness_for` SHALL take the resolved look defaults as a required parameter; each route
resolves them once per request and passes them down.

```python
def staleness_for(
    settings: ApiSettings,
    event_dir: Path,
    document: Optional[ReelDocument],
    runtime: FfmpegRuntime,
    look_defaults: Mapping[str, object],
) -> StalenessOut: ...
```

**Rationale**: Caching is the tempting answer and the wrong one here. An `lru_cache` on
`load_project_config` would make a `config.yaml` edit invisible until process restart, contradicting
"responses MUST reflect disk changes made since any previous request" (D-A3) — the API's whole read
contract. Caching on `app.state` has the same staleness problem with more machinery. A parameter has no
lifetime, no invalidation question, and makes the per-request scope visible in the signature. The
detail and write call sites resolve one line earlier than they do today; nothing else moves.

### Unconditional field versus an opt-in query parameter

**Context**: The verdict costs something. `?staleness=true` would let a caller decline it.

**Decision**: The field SHALL be unconditional on `EventSummaryOut`.

**Rationale**: The GUI list — the endpoint's reason for existing — always wants it, so the flag would be
a permanently-on option plus a second response shape to test and to generate TypeScript for (D-8:
schema changes must be build errors, which is harder when a field's presence is a runtime condition).
Principle VII forbids a second code path without a real use. If measurement later shows the cost is
real, the answer is reducing the cost, not making correctness optional.

### The duplicate directory walk stays, and is measured

**Context**: Per event the list will walk the directory twice — `scan_event` for reconcile, then
`_hash_clip_set` for the clip-set component. That doubling *is* the change's cost.

**Explored**: Threading the already-walked `DiskListing` into `compute_fingerprint` would remove it, but
means changing a `staleness/` signature that the CLI, the worker and the enqueue path all share, to
serve one API caller — a lower layer bending for a higher one, against Principle VI.

**Decision**: Keep both walks. Measure the list against a realistic library and record the number in the
change; act on it only if the measurement justifies it.

**Rationale**: The optimization has no measurement behind it (Principle VII), and the honest number is
cheap to get — the list route already logs its own duration (`events scan: %d event(s) ... in %.3fs`),
so before/after is one log line each.

### The content-hash opt-in is prohibited by the spec, not by a comment

**Context**: `compute_fingerprint(use_hash=True)` sha256s every clip's bytes. On a per-event endpoint
that is a deliberate, bounded cost; on a whole-library list it is a full-library read.

**Decision**: The events list SHALL compute the clip-set component from size and mtime only. This is
stated as a requirement with its own scenario, not left as a default nobody passes.

**Rationale**: Today it holds by accident — no `api/` call site passes the flag. The moment the hash
opt-in gains a config surface, "the API just calls `compute_fingerprint`" turns a list request into a
library-wide read with no code change to review. A requirement makes that a spec violation.

### Failure behavior and idempotency

**Decision**: The list SHALL stay as loud as it is today and no louder. An unparseable `reel.yaml` in
any event already raises `EventReadError` from the shared load path and fails the whole list request —
that behavior is unchanged and inherited, not extended to the new code. A malformed or absent render
manifest is **not** an error: `read_manifest` returns `None` and the gate reports the event stale citing
`no_manifest`, which is the correct answer (nothing trustworthy says it was rendered). No event is
skipped, and no verdict is ever fabricated for an event whose state could not be read.

**Idempotency**: a `GET` is read-only and repeatable; two identical requests with no disk change between
them MUST return identical verdicts. There is no `--force` equivalent on a read, and no worker
interaction: the list computes a verdict, it never enqueues, writes a manifest, or transitions a job.

## Risks / Trade-offs

- **Cost on a cold or network-backed library.** The list roughly doubles its `stat` load and adds a
  manifest read plus an output-path `exists()` per event; on a spun-down HDD or a NAS that is felt,
  where on local SSD it is not. → Measured before and after via the route's existing duration log; the
  duplicate walk is the identified lever if the number is bad.
- **A verdict is a point-in-time answer.** An event can go stale the instant after the response is
  serialized. → Unchanged from the detail endpoint and from `scan`; the enqueue path re-evaluates the
  gate at `POST /jobs`, so the list is a display fact, never the authority that permits a render.
- **`staleness_for` gains a required parameter.** Every call site must pass it. → There are two, both in
  `api/`, both changed in this change; mypy makes a missed one a type error, not a runtime surprise.
- **Response growth.** Every event carries a verdict object with a reason list. → Small and bounded
  (four possible component names plus `output`), and it replaces N detail requests.

## Migration Plan

Additive. The response gains a field, so existing clients are unaffected; no database migration, no
rescan, no `RENDER_GRAPH_VERSION` bump, no `reel.yaml` or `config.yaml` schema change. Rollback is
reverting the change — nothing is persisted in the new shape, so there is no on-disk or in-database
state to undo.

One thing outlives the change and MUST land in `docs/high-level-design.md`: §4.9's probe-free read-model
paragraph currently forbids probing to fill a response field. It is extended, in the same voice, to
forbid content hashing on a whole-library read — the same rule (D-A3 plus Principle IV) applied to the
staleness path rather than the probe path, not a new decision and not a new D-n.

## Open Questions

- **What the measured cost actually is on a large library.** *Measured (task 3.1).* A scratch project of
  **200 events × 4 clips**, each clip a symlink into `auto-reel-media/input` (never mutated), timed around
  the same `list_events` call the route's duration log wraps — best of five warm runs, local NVMe:

  | | 200 events | per event |
  |---|---|---|
  | before (no staleness) | **0.023 s** | 0.12 ms |
  | after (with staleness) | **0.067 s** | 0.34 ms |
  | delta | **+0.044 s (2.95×)** | +0.22 ms |

  The relative number is the predicted one — the second directory walk plus a manifest read and an
  output `exists()` roughly triple a loop that previously only walked once — but the absolute number is
  67 ms for a library four times larger than the real one, well inside a list request's budget.
  **No follow-up is justified on this evidence:** removing the duplicate walk would bend a
  `staleness/` signature shared by the CLI, enqueue and the worker (Principle VI) to save ~0.2 ms per
  event. The measurement is warm-cache and local; a cold or network-backed library is where the ratio
  would be felt, and the route's own duration log is what should re-open this — not a re-run of this
  bench.
