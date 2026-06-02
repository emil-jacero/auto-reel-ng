## Context

auto-reel computed the edit at scan time and never persisted it: chapters were subdirectories, clip order
was a sort rule, and "which clip is the title" was implicit. auto-reel-ng must surface and edit those
decisions in a GUI (HLD §4.10) and reproduce them headlessly, so the edit has to become durable, addressable
data. HLD §4.6/§4.7 names `reel.yaml` the editorial source of truth and Postgres a derived, disk-rebuildable
index (D-7); D-2 layers a project-level config under the event file.

This design covers the engine library only — schema, model, loader/writer, discovery seeding, resolution to
a render plan, and the reconcile diff. No Postgres, FastAPI, GUI, or render execution (those are later
phases); this change provides the pure functions they will call. The `media-probe` `ClipMetadata` type
already exists and supplies clip content facts.

## Goals / Non-Goals

**Goals:**
- A versioned (`version: 0`), fail-loud, round-trippable `reel.yaml` schema and typed model.
- Editorial structure (`chapters`) cleanly separated from per-clip properties (`clips`), sharing one identity.
- Discovery that uses folder layout only as a *seed*, after which `reel.yaml` is the sole authority for the edit.
- A pure `reconcile(disk, document)` diff and apply-operations, with seeding as its degenerate (empty-doc) case.
- Resolution of a document into a fully-explicit, ordered render plan with `look` defaults from server config.
- auto-reel-format import.

**Non-Goals:**
- Persistence (Postgres), the FastAPI service, and the GUI write path (phases #7/#8).
- Render execution / ffmpeg graph / chapter muxing (#4); analysis detection (#6).
- The pluggable ingest-layout framework (D-6) — ship the `<year>/<event>/` built-in only.
- Content-hash clip identity and §4.13 render-staleness fingerprinting.

## Decisions

### D-A — Scan-as-hint, not scan-as-layer
Folder structure seeds a *complete* `reel.yaml` at discovery; afterward the loader never reads folder layout
to determine structure. The document is authoritative and complete, not a sparse overlay on a live disk
baseline.
- **Why:** with a GUI as the editor, one authoritative document beats a live merge against a shifting
  filesystem. Chapters fully decouple from folders (a GUI-created chapter has no subdir), and folders can be
  reorganized freely.
- **Alternatives considered:**
  - *Sparse overlay* (disk = permanent baseline, reel.yaml = deltas). Rejected: forces an implicit/explicit
    duality and a delta-diffing writer; "unlisted = baseline" ordering is subtle. Its one big win —
    drop-in clips auto-appear — matters less when the GUI deliberately places new clips (see D-F/reconcile).
  - *Always-fully-explicit but disk stays a live layer.* Rejected: still couples structure to folder layout.

### D-B — Normalized structure vs. properties
`chapters[]` holds order + membership (ordered lists of clip references only). `clips{}` is a flat map of
per-clip attributes (`trims`, `title`, `rotate`, `exclude`) keyed by identity.
- **Why:** a relational normalization — a clip's trims survive reordering and chapter moves because position
  and attributes never live in the same record. The GUI's arrangement view edits `chapters`; its
  clip/timeline view edits `clips[id]`.
- **Alternative:** properties nested inline in the chapter clip list. Rejected: moving/reordering a clip
  would drag or orphan its trims; two edit surfaces fight over one structure.

### D-C — Identity = event-relative path
A clip is keyed by its path relative to the event root (`Reception/00400.mp4`); the GUI displays the basename.
- **Why:** unique by construction. Camera numbering (`00400.mp4`) repeats across subdirs/SD cards — the
  project's own sample media collides on bare filename. Readable, unlike a synthetic id.
- **Alternatives:** *bare filename* (rejected: collisions); *synthetic id / content hash* (deferred: opaque
  YAML, heavier; the rename-survival it buys belongs with the §4.13 fingerprint work).
- **Consequence:** reorganizing folders on disk breaks identity — which is exactly a reconcile event (D-F).

### D-D — Trims are CUT ranges
`trims` is an ordered list of `{in, out, reason}` spans to *remove*; everything else is kept. Multiple spans
per clip allowed.
- **Why:** resolves the HLD's latent "cut vs keep" ambiguity. Analysis (§4.5) emits regions-to-remove, and a
  clip with a black head *and* a frozen tail needs two spans — natural as cuts, awkward as keeps.
- **Alternative:** keep-ranges. Rejected (inverts naturally-emitted data; multi-region is clumsy). A
  hand-authoring "keep only" convenience is deferred — the GUI generates cut spans fine.

### D-E — `ignore:` list lives in `reel.yaml`
A per-file dismissal ("this disk file is deliberately not in the edit") is recorded in the document's
`ignore:` list, not in the DB.
- **Why:** an ignore is a decision that is neither in the structure nor derivable from disk (the file still
  exists). If it lived only in the derived DB, a rebuild (D-7) would resurrect every dismissed file as NEW.
  Putting it in the document keeps the DB 100% derived. This is auto-reel's `.reelignore` promoted into the
  document, per file.

### D-F — Reconcile is a pure disk⋈reel diff; seeding is its empty-doc case
`reconcile(disk_listing, document)` classifies every clip as NEW (on disk, not referenced, not ignored),
MISSING (referenced, not on disk), ACTIVE (both), or IGNORED, and offers apply-operations ("add to chapter
X", "ignore") that return a mutated document. Discovery seeding is `reconcile` against an absent/empty
document.
- **Why:** one mechanism for first-scan and ongoing drift. MISSING is reported and **never silently dropped**
  (probe ethos). The engine never mutates structure on its own — the operator (CLI/GUI) decides.

### D-G — reel.yaml-first writes; round-trip YAML
Writes target `reel.yaml` first; any derived store (future DB) is reindexed after. The writer preserves
comments and key order via `ruamel.yaml`.
- **Why:** keeps `reel.yaml` always-authoritative and the DB always throw-away-safe (no divergence window).
  Round-trip preservation keeps the git-friendly, human-co-authored file from churning on machine writes.
- **Alternatives:** *DB-first write-buffer* (rejected: reintroduces a "two sources disagree" window — the
  exact thing the model avoids; the GUI instead batches a gesture into one save). *PyYAML* (rejected: drops
  comments and reorders keys → noisy diffs).

### D-H — Two models: document vs. resolved plan
The loader yields a **document** (what the file says). `event-resolution` turns a document + event dir into a
**resolved plan**: chapters/order/membership materialized, properties applied, title baseline computed (first
clip of each chapter unless overridden), and `look` filled from the server `config.yaml` (D-2, with
config.yaml demoted to server-level defaults only). Render and GUI consume the plan; only the document is
written back.

### D-I — `look` is an opaque passthrough in v0
v0 does NOT model the internal fields of `look` (title-card font/size/color/fades, codec, resolution). The
loader parses, preserves, and round-trips `look` as an opaque map; resolution merges it with the server
default `look` by a **shallow merge at the top level** (a document top-level `look` key wins over the same key
in the default). The structured `look`/`title-card` schema is defined later by the title/overlay change (#5),
which is the consumer that actually needs the fields.
- **Why:** nothing in this change renders, so validating `look` internals would be speculative; an opaque
  passthrough lets the document carry look settings forward without coupling this change to #5's schema.

### D-J — `config.yaml` grows with the project; not defined here
This change does not define the `config.yaml` file format. It reads whatever server-default `look` map is
provided (possibly empty/absent) and shallow-merges it (D-I). `config.yaml` is expected to grow incrementally
as later changes need defaults; for v0 the resolver simply tolerates an absent or partial defaults map.

### D-K — `trims.reason` is an open string
`reason` is a free-form string, not a fixed enum. Known values (`black`, `white`, `freeze`, `manual`) are
documented for the GUI/analysis but not enforced, so analysis (#6) can introduce new kinds without a schema change.

## Risks / Trade-offs

- **Drop-in clips no longer auto-appear** (cost of D-A) → reconcile surfaces NEW files explicitly; the GUI/CLI
  prompts the operator. Accepted as the better behavior with a GUI.
- **Folder reorg breaks event-relative-path identity** (D-C) → treated as a reconcile event; content-hash
  rematching is a documented future upgrade tied to §4.13.
- **Round-trip YAML fidelity is imperfect** (ruamel can still normalize some constructs) → constrain the
  schema to plain scalars/maps/sequences; golden round-trip tests assert byte-stable rewrites of unchanged docs.
- **Resolution must be deterministic** (stable order from the same inputs) → define total orderings explicitly
  (listed order, then a documented tiebreak) and test them; never depend on dict iteration order.
- **auto-reel import drift** → import is best-effort with a fail-loud report of anything it cannot map
  (e.g. `sort: custom_order`), never a silent partial import.

## Migration Plan

- No deployed consumers yet; this is additive library code. New package dirs `auto_reel_ng/reel/` and
  `auto_reel_ng/event/`, plus the `ruamel.yaml` dependency.
- `version: 0` is written on every document. A loaded document with no `version` key is treated as the
  auto-reel legacy format and routed to the importer, which emits a `version: 0` document.
- Rollback = drop the new packages/dependency; nothing else depends on them yet.

## Open Questions

- **Reconcile granularity** — whether reconcile runs per-event only, or a project-level sweep aggregates
  per-event results (likely a thin service-layer loop over the per-event function; deferred to #7).

_Resolved during proposal review:_ `look` is an opaque passthrough in v0 (D-I), deferred to the title/overlay
change (#5); `config.yaml` is not defined here and grows with the project (D-J); `trims.reason` is an open
string (D-K).
