## Why

After phases 1–6 there are six tested engine capabilities — probe, accel, reel, render, title,
analysis — and **zero ways to run any of them** without hand-writing Python. `scan_event` handles
a single event dir; nothing walks a project root, reads project defaults, or drives
scan→render end to end. This change is the headless driver (HLD §4.11) plus the project model
(§4.7), pluggable ingest layouts (D-6), and config layering (D-2). It is deliberately the
**left half of phase #7**, split out from the scheduler/API/Postgres so it ships as a clean,
testable vertical slice — and makes the whole pipeline runnable and dogfoolable on
`auto-reel-media/` for the first time.

## What Changes

- Add a **pluggable ingest-layout system** (D-6) that maps a project root → a list of event dirs.
  Ship two built-ins: `year-event` (`<year>/<event>/`, the auto-reel convention) and `flat`
  (events directly under the root). Layouts are name-registered so more can be added later.
- Add a **project `config.yaml`** (D-2) holding shared defaults (look/codec/resolution, ingest
  layout name, default paths). Resolution order: folder-seed → `config.yaml` → event `reel.yaml`
  → CLI-flag overrides. The `config.yaml` `look` map feeds `resolve(look_defaults=…)`, which
  already accepts it opaquely (D-J). Absent/partial config is tolerated.
- Add a **headless CLI** (§4.11) installed as a `console_scripts` entry point (`auto-reel`),
  chaining the engine end-to-end with per-event isolation (already provided by `render_batch` +
  `BatchOutcome`). Commands:
  - `render` — scan → reconcile → probe → resolve → `select_profile` → `render_batch` over selected
    events/years. Flags: `--dry-run` (prints ffmpeg commands), `--overwrite`, `--device` (D-3
    profile override), `--years`.
  - `scan` / `list` — dry inventory: events, clips, and `NEW`/`MISSING` from `reconcile`. No render.
  - `analyze` — run `analyze_event` (analysis-pass-v1) and print/cache suggested segments.
  - `import` — adopt auto-reel legacy `reel.yaml`/`metadata.yaml` via `import_legacy`.
- Establish a **NEW-clip adoption policy** (see design): seed on first scan; on later scans
  surface `NEW`/`MISSING`; `render` auto-adopts `NEW` into the default chapter (configurable) so an
  added clip is never silently dropped, while `MISSING` is reported loud.

## Capabilities

### New Capabilities
- `ingest-layout`: Map a project root to events via a named, pluggable layout; ship `year-event`
  and `flat` built-ins, with an optional year filter and folder-name metadata hints.
- `project-config`: A project `config.yaml` of shared defaults and the D-2 layering that resolves
  folder-seed → config → `reel.yaml` → CLI overrides.
- `headless-cli`: The `auto-reel` command surface and entry point that wires the engine end to
  end (`render`/`scan`/`analyze`/`import`), with per-event isolation and a NEW-clip adoption policy.

### Modified Capabilities
<!-- None. The CLI consumes existing engine APIs (scan_event, reconcile, resolve, select_profile,
     render_batch, analyze_event, import_legacy) unchanged; no engine requirement changes. -->

## Impact

- **New modules**: `auto_reel_ng/ingest/` (layout registry + built-ins), `auto_reel_ng/config/`
  (config.yaml schema + layering), `auto_reel_ng/cli/` (argument parsing + command wiring).
- **`pyproject.toml`**: add a `[project.scripts]` `auto-reel` entry point.
- **Reuses unchanged**: `scan_event`, `seed_document`, `load_document`, `reconcile`,
  `add_clip`/`ignore_clip`, `resolve`, `select_profile`, `probe_many`, `render_batch`/`RenderJob`/
  `RenderOptions`/`output_filename`, `import_legacy`, `analyze_event`.
- **First end-to-end exercise** of the full stack on real footage (`auto-reel-media/`); expect to
  surface latent probe/normalize/concat issues that only appear on unseen input.

## Non-goals

- **No job scheduler, no FastAPI/REST/WebSocket, no Postgres** — phase #7's right half and later.
- **No staleness / change-detection.** The CLI re-renders the events you select; the §4.13/§8.14
  render-skip gate is a separate, research-blocked slice. The design notes the seam where a future
  staleness check slots in before `render_batch`.
- **No GUI** (phases #8–10) and **no new layouts** beyond the two built-ins.
- **No analysis approve→`Trim` apply** — consistent with analysis-pass-v1 (Option A); `analyze`
  only prints/caches suggestions.
