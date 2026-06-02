## Why

auto-reel never wrote its editorial decisions down: chapters were derived from subdirectories at scan time
and clip order from a sort rule, so the *edit* lived only in folder layout and code. auto-reel-ng needs a
durable, GUI-editable record of every editorial decision — order, chapters, trims, what's the title, what's
excluded — because the GUI (HLD §4.10) must reorder clips, create chapters, and approve trims, and a headless
CLI must reproduce the same result. This change establishes `reel.yaml` as that record (HLD §4.6, D-2/D-7):
the **authoritative editorial source of truth**, seeded once from disk structure as a hint, after which the
filesystem layout no longer dictates the edit.

## What Changes

- **`reel.yaml` v0 schema, model, and round-trip loader/writer.** A versioned (`version: 0`) document with
  `metadata`, `look`, `chapters` (structure: ordered clip references), `clips` (a flat map of per-clip
  properties keyed by identity), and `ignore`. Parse → typed model → write, preserving comments/key order
  (round-trip YAML). Validation is **fail-loud** — never fabricate or silently drop (carrying over the probe
  ethos that fixes auto-reel's silent fake-metadata bug).
- **Normalized structure vs. properties.** `chapters[]` owns order and membership (references only); `clips{}`
  owns per-clip attributes (cut-range `trims`, `title`, `rotate`, `exclude`). A clip's trims survive
  reordering and chapter moves because position and attributes never live together.
- **Identity = path relative to the event root** (e.g. `Reception/00400.mp4`), unique by construction (camera
  numbering like `00400.mp4` repeats across subdirs). GUI displays the basename.
- **Trims are CUT ranges** — an ordered list of `{in, out, reason}` spans to remove (multiple per clip), the
  natural shape for analysis output (§4.5) and a black-head/frozen-tail clip. **BREAKING** vs. any prior
  read of trims as keep-ranges.
- **Discovery seeds a complete document; disk becomes a hint.** First scan uses folder structure
  (`<year>/<event>/`, subdirs → chapters, root → default chapter) only to *seed* a complete `reel.yaml`.
  Thereafter the loader never consults folder layout for structure. Includes folder-name metadata seeding
  (`YYYY-MM-DD - Title [- Location]`) and **auto-reel import** (old `metadata`/`title`/`sort`/`title_card`
  format → v0).
- **Reconcile: an explicit disk⋈reel diff.** A pure function classifies every clip as NEW (on disk, not in
  doc), MISSING (in doc, not on disk → fail loud, never drop), ACTIVE, or IGNORED, plus apply operations
  ("add to chapter", "ignore") expressed as document mutations. Seeding is reconcile against an empty
  document. Dismissals live in the `ignore:` list **in `reel.yaml`** so they survive a derived-DB rebuild
  (D-7) — the `.reelignore` idea promoted into the document, per file.
- **Resolved render plan.** Resolving a document against its event dir produces a fully-explicit, ordered
  plan: chapter/order/membership resolved, per-clip properties applied, title baseline (first clip of each
  chapter unless overridden), and `look` defaults filled from the server-level `config.yaml` (D-2, with
  `config.yaml` demoted to server defaults only).

## Capabilities

### New Capabilities
- `reel-document`: the `reel.yaml` v0 schema — typed document model, fail-loud parse/validate, round-trip
  write, version handling, and auto-reel-format import.
- `event-resolution`: resolving a document + event dir into a render-ready plan — event-relative-path
  identity, chapter/order/membership resolution, cut-range trim and property application, title baseline, and
  `look`-default layering from server `config.yaml`.
- `event-reconcile`: discovery seeding (folder-structure-as-hint) and the explicit disk⋈reel diff —
  NEW/MISSING/ACTIVE/IGNORED classification and add/ignore apply operations as document mutations.

### Modified Capabilities
<!-- None. `media-probe` types (ClipMetadata) are consumed unchanged; no existing requirement changes. -->

## Impact

- **New code:** `auto_reel_ng/reel/` (schema/model, loader/writer, import), `auto_reel_ng/event/` (discovery,
  resolution, reconcile); tests with fixture event dirs and golden `reel.yaml` round-trips.
- **New dependency:** a round-trip YAML library (`ruamel.yaml`) to preserve comments/key order on write.
- **Consumes:** `media-probe` (`ClipMetadata` for clip identity/content facts); the existing fail-loud error
  and logging modules.
- **Consumed by:** the future render pipeline (#4, reads the resolved plan), the job scheduler / FastAPI
  service and Postgres index (#7, persists reconcile results as derived state), and GUI v1 (#8, reads the
  resolved plan, writes the document).

## Non-goals

- **No Postgres, no FastAPI, no GUI** (phases #7/#8). Reconcile is delivered as a pure engine function over
  `(disk, document)`; persisting its results as a derived index and the reel.yaml-first GUI write path are
  service/GUI concerns. This change only provides the library they call.
- **No render execution** (#4). `event-resolution` produces the plan; building the ffmpeg graph, real chapter
  markers, and concat are out of scope.
- **No analysis** (#6). `trims` carry approved cut ranges and a `reason`, but detecting black/white/freeze and
  the sidecar detection cache are a later change.
- **No pluggable ingest-layout framework** (D-6). This change ships the built-in `<year>/<event>/` discovery;
  the general layout-parser plugin system is deferred.
- **No content-hash clip identity.** Identity is the event-relative path; hash-based rename detection (which
  ties into §4.13 change detection) is deferred.
