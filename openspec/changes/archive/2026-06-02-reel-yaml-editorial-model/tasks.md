## 1. Package, dependency & data model

- [x] 1.1 Add `ruamel.yaml` to project dependencies (round-trip writer, D-G); create `auto_reel_ng/reel/` and `auto_reel_ng/event/` packages and a `ReelError` (and any subtypes) in the existing error hierarchy.
- [x] 1.2 Define the typed document model in `reel/`: `ReelDocument {version, metadata, look, chapters, clips, ignore}`, `Chapter {name, clips: list[ClipRef]}`, `ClipProperties {trims, title, rotate, exclude}`, `Trim {in, out, reason: str}` (reason is an open string, D-K), with clip identity as the event-relative path. `look` is an opaque map in v0 (D-I) — not modeled internally. Frozen/immutable where practical, with `to_dict()` for logging.
- [x] 1.3 Define the resolved-plan model in `event/`: `RenderPlan` / `ResolvedChapter` / `ResolvedClip` carrying explicit order, applied cut spans, resolved title flag, and resolved `look`.

## 2. reel-document — schema, parse & validate

- [x] 2.1 Implement v0 parse from YAML into `ReelDocument`; treat a missing `version` key as legacy and route to import (§3). (spec: Versioned reel.yaml v0 schema; Structure and properties are normalized apart)
- [x] 2.2 Enforce event-relative-path identity: unique within a document; reject ambiguous/duplicate references. (spec: Clip identity is the event-relative path)
- [x] 2.3 Parse `trims` as an ordered list of cut spans `{in, out, reason}`, multiple per clip. (spec: Trims are ordered cut ranges)
- [x] 2.4 Fail-loud validation: reject unknown `version`, `out <= in`, negative times, and `chapters` references with no valid identity; errors name the offending location; never fabricate or silently drop. Carry `look` opaquely — do not reject it on inner keys. (spec: Fail-loud parse and validation; `look` is carried opaquely in v0)
- [x] 2.5 Tests: valid document parses to the expected model; each invalid case (bad version, bad trim, negative time, dangling reference, duplicate identity) raises a clear, located error.

## 3. reel-document — round-trip writer & legacy import

- [x] 3.1 Implement the writer via `ruamel.yaml`, always emitting `version: 0` and preserving comments/key order on unchanged content. (spec: Round-trip preserving writer; Versioned reel.yaml v0 schema)
- [x] 3.2 Round-trip test: a hand-authored `reel.yaml` with comments loads and re-writes byte-stable.
- [x] 3.3 Implement auto-reel legacy import: map `metadata` → `metadata`, `title_card` → `look`, honor `sort` for order; report (never silently drop) anything unmappable; output a `version: 0` document. (spec: Import of auto-reel legacy format)
- [x] 3.4 Tests: legacy `metadata`+`title_card` import into v0 `metadata`/`look`; an unmappable field (e.g. `sort: custom_order` with manual map) is reported, not dropped.

## 4. event-resolution — document → render plan

- [x] 4.1 Resolve a document + event dir into a fully-explicit `RenderPlan` (chapters and clips materialized in document order) without re-reading folder structure for membership/order. (spec: Resolve a document into a fully-explicit render plan)
- [x] 4.2 Guarantee deterministic ordering with a defined, total tiebreak; never depend on dict iteration order. (spec: Deterministic ordering)
- [x] 4.3 Apply per-clip properties: carry cut spans, apply `rotate`, and omit `exclude: true` clips from the plan while leaving them in the document. (spec: Apply per-clip properties)
- [x] 4.4 Compute the title baseline (first included clip per chapter) with explicit `title: true/false` override. (spec: Title baseline with override)
- [x] 4.5 Produce the plan's `look` by top-level shallow-merge of the document's opaque `look` over the server-config default `look` (document key wins; default-only keys carried; absent/partial defaults tolerated) (D-2/D-I/D-J). (spec: Look merged with server-config defaults)
- [x] 4.6 Tests: plan lists clips in document order; repeated resolution is identical; excluded clip absent but retained in document; default vs overridden title clip; default-only look key carried, document key overrides, absent defaults tolerated.

## 5. event-reconcile — discovery seeding & disk⋈reel diff

- [x] 5.1 Implement discovery seeding: subdirs → chapters, root clips → default chapter, folder name (`YYYY-MM-DD - Title [- Location]`) → metadata, producing a complete v0 document. (spec: Discovery seeds a complete document from folder structure)
- [x] 5.2 Implement the pure `reconcile(disk_listing, document)` classifier → NEW / MISSING / ACTIVE / IGNORED; no document or filesystem mutation; MISSING reported, never dropped. (spec: Reconcile classifies disk against the document)
- [x] 5.3 Express seeding as reconcile against an empty/absent document (all-NEW path). (spec: Seeding is reconcile against an empty document)
- [x] 5.4 Implement apply-operations returning a mutated document: "add" places a NEW clip into a named chapter; "ignore" records the identity in `ignore`; source files never touched. (spec: Apply operations mutate the document, not the filesystem)
- [x] 5.5 Tests (fixture event dirs): subdirs seed chapters; folder name seeds metadata; NEW/MISSING/ACTIVE/IGNORED classification; empty document → all-NEW; add references the clip without moving files; ignore round-trips so a re-reconcile classifies it IGNORED.

## 6. Wire-up & quality

- [x] 6.1 Expose the public API from the packages: load/validate/write document, import legacy, resolve plan, seed/reconcile/apply; consume `media-probe` `ClipMetadata` for clip content facts.
- [x] 6.2 Ensure `task lint:check` (black/isort/mypy/pylint) and `pytest` pass clean across the new packages.
