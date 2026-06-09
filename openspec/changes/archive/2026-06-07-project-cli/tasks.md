## 1. Ingest layouts (D-6)

- [x] 1.1 Create `auto_reel_ng/ingest/` package; define `EventRef` (event_dir + folder-name metadata hint)
- [x] 1.2 Define a `Layout` protocol `(root, years?) -> Iterable[EventRef]` and a name-keyed registry with a fail-loud lookup
- [x] 1.3 Implement `year-event` layout (walk `<year>/<event>/`, optional year filter) reusing `parse_folder_name`
- [x] 1.4 Implement `flat` layout (events directly under root)
- [x] 1.5 Register both built-ins; export public API
- [x] 1.6 Tests over a temp fixture tree: year-event walk, year filter, flat walk, unknown-name error

## 2. Project config + layering (D-2)

- [x] 2.1 Create `auto_reel_ng/config/` package; define a `ProjectConfig` (look map, layout name, default paths), all optional
- [x] 2.2 Loader: read `config.yaml`; tolerate missing; fail loud on malformed YAML / wrong-typed fields
- [x] 2.3 Implement layered resolution: folder seed → config.yaml → reel.yaml → CLI overrides; produce the merged `look_defaults` map
- [x] 2.4 Tests: missing-config defaults, malformed-config error, precedence (reel.yaml > config, CLI > config, config default applies)

## 3. CLI scaffold & wiring

- [x] 3.1 Create `auto_reel_ng/cli/` package; argument parser with subcommands `render`/`scan`(`list`)/`analyze`/`import`
- [x] 3.2 Add `[project.scripts]` `auto-reel = auto_reel_ng.cli.main:main` to `pyproject.toml`
- [x] 3.3 Shared option plumbing: project root, output dir, `--years`, `--device`, `--dry-run`, `--overwrite`, layout/config selection
- [x] 3.4 `--help` lists subcommands; unknown subcommand / bad args exit non-zero with usage

## 4. Adoption policy (D-CLI3)

- [x] 4.1 Per-event resolve helper: no reel.yaml → `seed_document`; else `load_document`
- [x] 4.2 `reconcile` disk vs document → classify NEW/ACTIVE/IGNORED/MISSING
- [x] 4.3 `render` path: adopt NEW into default chapter via `add_clip` (configurable); persist with the reel writer
- [x] 4.4 Report MISSING loudly; never auto-remove
- [x] 4.5 Tests: seed-on-first-scan, adopt-new, missing-reported (mock at document level, no ffmpeg)

## 5. `render` command (end to end)

- [x] 5.1 Enumerate candidate events via layout; structure flow as enumerate → [staleness seam, no-op] → build jobs → render_batch
- [x] 5.2 Per event: resolve doc (§4) → `probe_many` clip_facts → `resolve(look_defaults=…, clip_facts=…)` → build `RenderJob`
- [x] 5.3 Select profile once (capability detect + `select_profile`); apply `--device` → `RenderOptions.render_node`
- [x] 5.4 Build `RenderOptions` (event_dir, output_dir, clip_facts, runtime, overwrite, dry_run, render_node); call `render_batch`
- [x] 5.5 Map `BatchOutcome`s to console report + exit code (D-CLI5: non-zero if any event errored)
- [x] 5.6 Tests: end-to-end with engine mocked at `render_batch`; dry-run prints commands & writes nothing; one-bad-event isolation & exit code

## 6. `scan`, `analyze`, `import` commands

- [x] 6.1 `scan`/`list`: print events + clip reconcile classification; no render, no ffmpeg; assert no output written
- [x] 6.2 `analyze`: run `analyze_event` over selected events; print + cache segments; assert reel.yaml untouched
- [x] 6.3 `import`: read legacy metadata via `import_legacy`; write v2 reel.yaml; report imported fields; round-trip test

## 7. Integration & quality gate

- [x] 7.1 `has-ffmpeg`-marked end-to-end: generate a tiny clip, `auto-reel render` a one-event project, assert output exists & is playable-uniform
- [x] 7.2 Export public API from `auto_reel_ng/__init__.py` as appropriate (layouts, config, cli entry)
- [x] 7.3 `black`/`isort`/`mypy` clean over new modules; full `pytest` green
- [x] 7.4 README/usage note: the four `auto-reel` subcommands and a `config.yaml` example
