## 1. event/ — `checked_claim` (item `claimant-selection-composed-twice-cli-api`)

- [x] 1.1 Red first: add `tests/test_event_claims.py` (no marker, `tmp_path` event folders, `today` passed in).
  Cases, each calling `checked_claim(event_dir, order=DEFAULT_CLIP_ORDER, today=...)`:
  - a folder-named event with a real date and title → `(document, None)`, and no `reel.yaml` was written
  - a `reel.yaml` event whose metadata overrides the folder name → the document carries the overridden title
  - no date in the folder name, a year-only folder, a future date → `(None, reason)` with the
    `EventMetadataError` reason text (no event-name prefix)
  - an unparseable `reel.yaml` and a `reel.yaml` that is not UTF-8 → `(None, reason)` (the `ReelError` text)
  - a folder with no `reel.yaml` and permissions `000` → `(None, reason)` whose text contains `Permission
    denied`; restored with `chmod` in a `finally`/fixture; `pytest.mark.skipif(os.geteuid() == 0, ...)`
  - a patched loader raising `ValueError` → `(None, reason)`; a patched loader raising `RuntimeError`
    propagates (a bug is not an event's problem)
  Verify: `.venv/bin/python -m pytest tests/test_event_claims.py` fails with `ModuleNotFoundError` for
  `auto_reel_ng.event.claims`.
- [x] 1.2 Add `auto_reel_ng/event/claims.py` with `checked_claim` exactly as the design's signature, mapping
  `EventMetadataError` → `exc.reason`, other `ReelError` → `str(exc)`, `OSError`/`ValueError` → `cannot read the
  event: <detail>`; do not edit `event/__init__.py`. Add a test that parses the module with `ast` and asserts its only package-relative imports are `..errors` and `..reel` (the layering guard, design "Why two modules"; a subprocess import check cannot work, because importing any `auto_reel_ng` module runs the package root, which imports the CLI and so `render`). Verify: all of 1.1 passes; with the `OSError` branch
  removed the `000` case fails with `PermissionError`, then restore it; `.venv/bin/python -m mypy
  auto_reel_ng/event/claims.py` is clean.

## 2. render/ — `output_collision` (item `worker-claim-time-output-collision-recheck`)

- [x] 2.1 Red first: add `tests/test_render_claims.py` (no marker; real `tmp_path` project trees with the
  `year-event` layout, `reel.yaml` files written with the repo's writer or a literal YAML string). Cases, each
  calling `output_collision(event_dir, walk_root=..., layout="year-event", order=..., today=...)`:
  - two events with the same date and title (folder-named and `reel.yaml`-named) → each gets an
    `OutputCollision` whose `output_path` is `2024/2024-06-21 - Midsommar.mp4` and whose `claimed_by` is the
    other's directory
  - **edited into a collision after the fact:** two events with distinct paths (so no collision), then the second
    `reel.yaml` title is rewritten to the first's → the collision now appears (the worker scenario)
  - case-only (`Midsommar` / `midsommar`) and Unicode-normalization-only (NFC/NFD) differences collide
  - same title on different dates or in different years → `None`
  - a three-way collision lists both others, sorted by path
  - a named event the layout does not walk (a folder outside `year-event`'s shape) still counts as a claimant
    and collides with a walked event of the same path
  - a walked event that fails (malformed `reel.yaml`, no date) and a `000` sibling claim nothing and do not
    stop the check of the others (skip the `000` case as root)
  - the named event itself failing (no date) → `None`, and the layout is not walked (patch `get_layout` to
    raise: the test passes only because nothing called it)
  - an unknown layout name → `LayoutError` propagates; a walk root that cannot be listed → `OSError` propagates
  - `output_collision_message(PurePosixPath("2024/x.mp4"), ["a", "b"])` equals `output path 2024/x.mp4 is also
    claimed by a, b; set a distinct title or location in reel.yaml`
  Verify: the file fails with `ModuleNotFoundError` for `auto_reel_ng.render.claims`.
- [x] 2.2 Add `auto_reel_ng/render/claims.py`: the `OutputCollision` dataclass, `output_collision` (the four
  steps in the design, `Path`-equality alias rule, no `years`) and `output_collision_message`. Import
  `output_relpath` and `find_output_collisions` from `.orchestrator`, `checked_claim` from `..event.claims` and
  `get_layout` from `..ingest`; do not edit `render/orchestrator.py` or `render/__init__.py`. Verify: 2.1
  passes; `.venv/bin/python -m mypy auto_reel_ng` is clean; `python -c "import auto_reel_ng.render.claims"`
  from a fresh interpreter shows no import cycle; `git diff --stat` lists only the two new modules.
- [x] 2.3 Cross-check against the two existing callers without editing them: a test in
  `tests/test_render_claims.py` builds one project tree and asserts that, for each event, the engine's
  `claimed_by` names equal the API's `events_read.output_collision(settings, event_dir, today=...)` result
  (ids compared through `event_id_for`), including a case-only collision and an unreadable-folder sibling (skip as
  root). Verify: the test passes against current `api/`; it is what the API change deletes or turns into a
  delegation test when it adopts the engine function.

## 3. Docs

- [x] 3.1 In `docs/high-level-design.md` D-9, append an amendment line ("*Amended 2026-10-02, change
  `engine-output-claims`:*") stating that which events claim an output path, and who else claims it, is decided by
  one engine rule (`event/claims.py`, `render/claims.py`) used by the CLI, the API and the worker, that an event
  that fails to load claims nothing, and that the worker rechecks at claim time. Verify by rereading D-9
  against the two deltas: no claim about call sites that this change does not list as adopted by a named
  follow-up.

## 4. Validation

- [x] 4.1 Run `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`,
  then `.venv/bin/python -m mypy auto_reel_ng`, `.venv/bin/python -m pylint auto_reel_ng`, and the full
  `.venv/bin/python -m pytest` (`requires_db` needs podman; say so if it is unavailable). Verify all are clean or
  green apart from the known cairo `no-member` noise and the five font-dependent skips, and that
  `tests/test_cli_output_collisions.py` and `tests/test_api_output_collision.py` pass unedited.
- [x] 4.2 Run `openspec validate engine-output-claims --strict`. Verify it passes and that
  `git status --short` lists only the two modules, the two test files, `docs/high-level-design.md` and
  `openspec/changes/engine-output-claims/`.
