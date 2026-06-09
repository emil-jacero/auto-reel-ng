## Context

Phases 1–6 built the engine as a stack of pure-ish, well-tested library layers. None of them is
reachable from a shell: `scan_event` handles a single event directory, and there is no project
walk, config file, or entry point. This change adds the thin driver layer — HLD §4.11 (headless
CLI) + §4.7 (project model) + D-6 (pluggable layouts) + D-2 (config layering) — so the whole
pipeline runs end to end.

It is explicitly **phase #7's left half**, carved out from the scheduler/API/Postgres. That split
is deliberate: the scheduler (§4.8) cannot enqueue without a project scan and a candidate-event
list, and it is additionally gated by the unresolved §8.14 change-detection research. Building the
scan/wire layer as a standalone CLI first gives the scheduler a ready-made core to wrap later,
keeps this slice testable, and unblocks dogfooding now.

The CLI is almost entirely **wiring**: it consumes existing engine APIs unchanged. The real design
content is three small decisions (layout abstraction, config layering, adoption policy) and one
seam (where staleness will later slot in).

## Goals / Non-Goals

**Goals:**
- A named, pluggable layout registry mapping a project root → events; `year-event` + `flat` built-ins.
- A `config.yaml` loader and D-2 layering that feeds `resolve(look_defaults=…)`.
- An `auto-reel` entry point with `render`/`scan`/`analyze`/`import`, per-event isolation, and a
  defined NEW-clip adoption policy.
- Headless tests mocking at the `render_batch` boundary; one `has-ffmpeg` end-to-end render.

**Non-Goals:**
- No scheduler, FastAPI, WebSocket, or Postgres.
- No staleness/change-detection (§4.13/§8.14) — the CLI renders what you select; the seam is noted below.
- No GUI, no new layouts beyond the two built-ins, no analysis approve→`Trim` apply.

## Decisions

**D-CLI1 — Layout is a function `(root, years?) → Iterable[EventRef]`, name-registered.**
A layout yields `EventRef{event_dir, metadata_hint}`; it does not open clips (that stays
`scan_event`). `year-event` and `flat` register into a dict keyed by name; `config.yaml`/CLI select
by name; an unknown name fails loud. This is the minimal shape that satisfies D-6 without inventing
a plugin-discovery mechanism — registration is an in-process call, extensible later.
*Alternative:* hardcode the two walks in the CLI — rejected; D-6 explicitly wants layouts pluggable.

**D-CLI2 — Config layering composes opaque `look` maps; CLI flags are the top layer.**
`resolve()` already accepts `look_defaults` opaquely (D-J), so layering is just dict-merge in
priority order: folder/layout seed → `config.yaml` → event `reel.yaml` → CLI flags. The CLI builds
the merged `look_defaults` and passes it through; it does **not** reach into look internals. Absent
config is an empty layer; malformed config fails loud (engine convention).
*Alternative:* a typed config schema validating every look field now — deferred; the look map is
intentionally opaque at this layer, and over-typing it here would duplicate the render layer's contract.

**D-CLI3 — Adoption policy: seed-on-first-scan, adopt-NEW-on-render, report-MISSING-loud.**
`reconcile()` classifies but never mutates, so the CLI owns the policy:
- No `reel.yaml` → `seed_document` from disk structure (the D-F seeding case).
- Has `reel.yaml`, disk has `NEW` clips → `render` calls `add_clip` to adopt each `NEW` clip into
  the default chapter (configurable), so an added file is never silently dropped.
- `MISSING` (referenced, absent from disk) → reported loudly, never auto-removed (`reconcile`
  already refuses to remove it; the CLI surfaces it).
`scan` only *reports* `NEW`/`MISSING`; only `render` mutates the in-memory document (and persists
via the reel writer). Auto-adopt is the safe default because dropping a clip the operator added is
the worse failure; making it configurable leaves room for a stricter "explicit adoption" mode later.
*Alternative:* require explicit adoption always — rejected as the default; it makes the common case
(drop a new clip in, re-render) need a manual step, and silently-dropped footage was an auto-reel pain point.

**D-CLI4 — Profile selection per run, `--device` overrides (D-3).**
The CLI runs capability detection once, calls `select_profile` (auto-pick best), and applies
`--device` as the explicit override, threading the selection into `RenderOptions.render_node`.
One profile per invocation is sufficient; multi-device scheduling is a scheduler concern (D-4).

**D-CLI5 — Exit codes reflect per-event outcomes.**
`render_batch` already isolates failures into `BatchOutcome`. The CLI maps outcomes to a process
exit code: zero when all selected events succeed (or dry-run), non-zero when any event errored,
while still having rendered the rest. This keeps batch automation honest without aborting good work.

## Risks / Trade-offs

- **First contact with real footage** → the engine has only been unit-tested; running
  `auto-reel-media/` end to end will likely surface latent probe/normalize/concat issues on unseen
  input. That is a *feature* of this slice (dogfooding), but expect follow-up fixes outside it.
- **Auto-adopt could include unwanted clips** (e.g. a stray export) → mitigated by `scan` showing
  `NEW` before `render`, by `original/` and `.reelignore` conventions carried from auto-reel, and by
  the policy being configurable. The opposite default (silent drop) is worse.
- **Config layering ambiguity** if both `config.yaml` and CLI set partial look maps → resolved by a
  strict, documented merge order (D-CLI2); tested directly (precedence scenarios).
- **No staleness yet** means re-running `render` re-encodes unchanged events → accepted for v1;
  `--overwrite` governs clobbering. See the seam below.

## Migration Plan

- Additive only: new `ingest/`, `config/`, `cli/` modules and a `[project.scripts]` entry; no
  changes to existing engine modules or their requirements. Rollback = remove the entry point and
  the three modules.
- `import` provides the auto-reel → v2 migration path for existing `metadata.yaml`/`reel.yaml`.

## Open Questions

- **Staleness seam (deferred to §8.14 / phase #7).** A future `is_stale(event)` check belongs
  *between* candidate-event enumeration and `render_batch` enqueue. This change should structure the
  `render` flow so that inserting a filter there later is a localized change (enumerate → [future
  staleness filter] → build jobs → `render_batch`), without implementing it now.
- **Where does `config.yaml` live relative to the project root vs the input dir?** Lean: at the
  project root the layout walks. Settle during apply.
- **Should `analyze` run as part of `render`?** No in v1 (suggestions have no auto-apply); kept a
  separate subcommand. Revisit when an approval surface exists.
