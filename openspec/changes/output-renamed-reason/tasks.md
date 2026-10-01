## 1. Baseline (gate: none)

- [ ] 1.1 Confirm the code and the specs this change was designed against. Stop and report to the supervisor if a
  check fails in a way the design does not cover.
  - This command prints nothing:
    `git diff 93721b3 -- auto_reel_ng/staleness auto_reel_ng/render/orchestrator.py web/src/events/labels.ts tests/test_staleness_gate.py tests/test_staleness_manifest.py tests/test_cli_render_staleness.py tests/test_api_events.py tests/test_api_editorial_write.py tests/test_editorial_write_e2e.py tests/test_api_openapi.py openspec/specs/change-detection/spec.md openspec/specs/api-service/spec.md`
    If only a spec differs (for example, `adopt-into-folder-chapter` archived first), re-base this change's
    MODIFIED blocks on the current text and re-run `openspec validate output-renamed-reason --strict`.
  - `grep -n "reasons.append(StalenessReason.OUTPUT)" auto_reel_ng/staleness/gate.py` hits `evaluate`.
  - `grep -n "output=output_path.name" auto_reel_ng/render/orchestrator.py auto_reel_ng/cli/commands.py` hits both
    manifest writers. If either now records anything other than the bare file name, stop: the lookup rule
    assumes the name.
  - `sed -n '/^def output_relpath/,/^_K = /p' auto_reel_ng/render/orchestrator.py` still puts a dated name under
    `f"{metadata.date.year:04d}"` and an undated one at the output root (D-9).
  - `ls openspec/changes/archive | grep renamed-label-and-zoom-bar` prints nothing, because that change is gated on
    this one.

  Verify: every check holds, or the difference is in the final report.

## 2. staleness/ — locate the recorded movie, cite the rename

- [ ] 2.1 Red first, in `tests/test_staleness_manifest.py`:
  - Add `test_recorded_output_path_inverts_output_relpath`, parametrised over every old × new pair (25) of these
    `Metadata` shapes:
    - `("Grillning med Grannar", 2024-06-27)`
    - `("Midsommar", 2023-06-23, location "Dalarna")`
    - `("Blandat",)` (undated)
    - `("Blandat", location "Hemma")`
    - `("Gammal", date(999, 1, 2))`

    With `out = tmp_path / "library-output"`, it asserts
    `recorded_output_path(output_relpath(old).name, out / output_relpath(new)) == out / output_relpath(old)`.
    Import `output_relpath` from `auto_reel_ng.render`.
  - Add `test_recorded_output_path_reads_no_disk`. It runs on paths under a directory that does not exist and gets
    the same answers, because the helper is pure.

  Run it and see an `ImportError`. Then add `_DATE_PREFIX`, `_year_folder` and `recorded_output_path` to
  `auto_reel_ng/staleness/manifest.py` exactly as in the design ("Code shape"), with `import re`, and list
  `recorded_output_path` in `__all__`. Verify:
  - `.venv/bin/python -m pytest tests/test_staleness_manifest.py` passes: 25 pairs plus the existing tests.
  - `.venv/bin/python -m mypy auto_reel_ng` is clean.
- [ ] 2.2 Red first, in `tests/test_staleness_gate.py`. Add a helper that writes a fake movie at
  `tmp_path / "out" / output_relpath(meta)` and a manifest recording `.name`, then evaluates against
  `out / output_relpath(new_meta)`. Add `_as_before(reasons)`, which maps `output_renamed` to `output`. Add these
  tests; each asserts the exact tuple, `verdict.stale is True`, and `_as_before(...)` equal to the tuple today's gate
  returns, written out literally:
  - `test_retitle_cites_output_renamed`: Grillning (2024-06-27) retitled `Grillkväll med grannarna` gives
    `("editorial", "output_renamed")`; as before, `("editorial", "output")`.
  - `test_location_change_cites_output_renamed`: `Dalarna` → `Leksand`.
  - `test_date_moved_to_another_year_cites_output_renamed`: 2023-06-23 → 2022-06-23.
  - `test_a_recorded_value_that_is_not_a_bare_movie_file_cites_output`: the retitled Grillning with its old movie on
    disk, but a manifest recording, one at a time, `""`, `"2024"`, an absolute path to an existing file, and
    `"../<an existing file>"`. Each gives `("editorial", "output")`.
  - `test_renamed_with_old_movie_deleted_cites_output`: `("editorial", "output")`.
  - `test_expected_movie_present_cites_neither`: a leftover file at the new path gives `("editorial",)`.

  In `test_component_members_are_exactly_the_fingerprint_components`, add `StalenessReason.OUTPUT_RENAMED` to the
  `non_components` tuple. Run and see the three rename tests fail with `output` where `output_renamed` is expected
  (the other three already pass on today's gate, by design). Then
  implement in `auto_reel_ng/staleness/gate.py` as in the design:
  - `OUTPUT_RENAMED = "output_renamed"`, declared right after `OUTPUT`;
  - `_absent_output_reason()`, and `evaluate()` calling it only when the expected path does not exist. It looks up
    only a bare file name (`Path(recorded).name == recorded`) and accepts only `.is_file()`;
  - the class docstring saying what each member means, and for `output_renamed` that the next render writes under
    the new name and the old movie stays;
  - the module docstring's stale rule.

  Verify:
  - `.venv/bin/python -m pytest tests/test_staleness_gate.py tests/test_staleness_fingerprint.py tests/test_staleness_manifest.py`
    passes;
  - the existing gate tests are unmodified apart from that one tuple, and
    `test_reasons_are_enum_members_carrying_the_unchanged_wire_values` still expects
    `("editorial", "clip_set", "output")`.

## 3. Callers that reuse the gate (tests only; no code change in cli/, api/, scheduler/, render/)

- [ ] 3.1 CLI, real ffmpeg, no database. In `tests/test_cli_render_staleness.py`, add
  `test_retitle_scans_as_renamed_and_render_keeps_the_old_movie`, reusing `_project` (`2024-06-21 - Party`):
  1. `render`, then record `old.stat()` for `<output>/2024/2024-06-21 - Party.mp4`.
  2. Replace `Party` with `Party Renamed` in `reel.yaml`. `scan` prints `stale: editorial, output_renamed`.
  3. Keep the clip's bytes and overwrite `00400.mp4` with `b""`. `render` returns 1. Then:
     - `read_manifest` is unchanged;
     - no `2024-06-21 - Party Renamed.mp4` exists;
     - the old movie's `st_size` and `st_mtime_ns` are unchanged;
     - `scan` still prints `output_renamed`.
  4. Restore the clip. `render` returns 0. Then:
     - the new movie exists;
     - the old movie's `st_size` and `st_mtime_ns` are unchanged;
     - `read_manifest(event_dir).output == "2024-06-21 - Party Renamed.mp4"`;
     - `scan` prints `fresh`.
  5. Rename to `Fest` and run `render --force`. The year folder holds exactly the three movies.

  Verify:
  - `.venv/bin/python -m pytest tests/test_cli_render_staleness.py` passes;
  - with `_absent_output_reason` temporarily returning `StalenessReason.OUTPUT`, only this test's `scan` assertions
    fail. Restore it.
- [ ] 3.2 API, `requires_db`.
  - In `tests/test_api_events.py`, add `test_renamed_event_reads_output_renamed_on_list_and_detail`:
    1. `_make_fresh(project, <Barbecue>)`.
    2. Set `metadata.title` in the persisted `reel.yaml` to `Grillkväll`, as a ruamel round trip like
       `scripts/make_dev_library.py` `_edit_title` does. The list item and the detail both carry
       `{"stale": True, "reasons": ["editorial", "output_renamed"]}`.
    3. Delete the old movie. Both now carry `["editorial", "output"]`.
  - Also add `test_deleted_movie_still_reads_output`: `_make_fresh`, delete the movie, and the reasons are
    `["output"]`.
  - In `tests/test_api_editorial_write.py`, tighten `test_save_makes_a_previously_fresh_event_stale`:
    - the echoed verdict and the follow-up `GET` both have reasons `["editorial", "output_renamed"]`;
    - the fake movie still reads `b"already-rendered"`;
    - `GET /api/v1/jobs` is `[]`.

  Verify that `.venv/bin/python -m pytest tests/test_api_events.py tests/test_api_editorial_write.py` passes
  (podman Postgres).
- [ ] 3.3 Worker path, `requires_db`, real CPU render. In `tests/test_editorial_write_e2e.py`
  `test_editorial_write_save_stale_render_cycle`:
  - after step 3's title edit, assert `verdict["reasons"] == ["editorial", "output_renamed"]` on the PUT echo and on
    the follow-up GET;
  - take `original_output.stat()` before step 4;
  - after step 4, assert that `original_output` still exists with the same `st_size` and `st_mtime_ns`, and that
    `read_manifest(root / EVENT_ID).output == "2024-06-21 - Renamed Trip.mp4"`;
  - update the module docstring's flow (`stale: editorial, output_renamed`; the old movie is kept).

  Verify that `.venv/bin/python -m pytest tests/test_editorial_write_e2e.py` passes.

## 4. Published contract and client build

- [ ] 4.1 Regenerate the published artifacts, see the client build fail, and add the label:
  1. Regenerate:
     - `.venv/bin/python -m auto_reel_ng.api.openapi > web/openapi.json`
     - `podman run --rm -v "$PWD/web:/app:Z" -w /app docker.io/library/node:22 sh -c 'npm ci && npm run generate:types'`
  2. In `tests/test_api_openapi.py` `test_staleness_reasons_are_published_as_a_closed_enumeration`, also assert
     that `"output_renamed"` is in `published["enum"]` and in `published["description"]`.
  3. Run `npx tsc --noEmit` in the same container. It fails with `TS2741` naming `output_renamed` in
     `src/events/labels.ts`. This failure is expected; it proves the exhaustive map catches the new member.
  4. Add `output_renamed: 'renamed — renders under the new name; the old movie stays',` to `REASON_LABEL`, right
     after `output`.

  Verify:
  - `grep -n 'StalenessReason: ' web/src/api/schema.d.ts` shows `"output" | "output_renamed" | "editorial"`;
  - `.venv/bin/python -m pytest tests/test_api_openapi.py` passes, drift test included;
  - `podman run --rm -v "$PWD/web:/app:Z" -w /app docker.io/library/node:22 sh -c 'npx tsc --noEmit && npm run build'`
    passes;
  - `git status --short web/` lists only `openapi.json`, `src/api/schema.d.ts` and `src/events/labels.ts`
    (`dist/` and `node_modules/` are ignored).

## 5. Docs

- [ ] 5.1 Record the decision.
  - `docs/high-level-design.md` D-9 gains "*Amended 2026-10-01 (change `output-renamed-reason`):*". After a render,
    a new title, date or location changes the movie's path. The engine never deletes, moves, renames or overwrites
    the previous movie. The next render writes the new path beside it and records the new name. Until then, the
    verdict cites `output_renamed` instead of `output`. Removing the old file is the operator's call. A render
    still replaces the file at its own path, so a case-only rename on a case-insensitive filesystem replaces the
    old movie, as before.
  - `README.md` "Change detection": in the first paragraph, "the manifest's recorded output file is missing"
    becomes "the event's movie is missing from its expected path (today's title, date and location, D-9)". Add a
    bullet for renaming an event: `output_renamed` while the old movie is on disk; `output` means the movie is
    really gone; the next render keeps the old file; delete it by hand if both are not wanted. In the editorial
    write paragraph, "the very next read reports `stale: editorial`" gains "(with `output_renamed` too when the
    save changed the title, date or location)".
  - `scripts/make_dev_library.py`: the Grillning comment `# stale: editorial` becomes
    `# stale: editorial, output_renamed (its old movie stays)`.

  Verify:
  - reread all three against the change-detection delta: replace-only, the keep rule, no automatic deletion;
  - `grep -n "output_renamed" docs/high-level-design.md README.md scripts/make_dev_library.py` hits each file.

## 6. Validation

- [ ] 6.1 Verification against a scratch dev library, from the session scratchpad; never committed.
  - **Setup:** create your own database `arel_<slug>`, never `auto_reel_ng`, and run `alembic upgrade head`. Build
    the library with `.venv/bin/python scripts/make_dev_library.py <scratch>/dev`. Run `serve` on port **8123**,
    never 8080 or 5173. Never use `auto-reel-media/`.
  - **`scan`:** `auto-reel scan <scratch>/dev/library` prints `stale: editorial, output_renamed` for
    `Grillkväll med grannarna`. After `2024/2024-07-14 - Kalas.mp4` is deleted from `library-output`, Kalas prints
    `stale: output`.
  - **Reads:** `GET /api/v1/events` and the Grillning detail report `["editorial", "output_renamed"]`.
  - **Writes:** `GET …/reel` for the ETag, then `PUT` with `If-Match`.
    - Location `Leksand` on `2024/2024-06-21 - Midsommar - Dalarna` echoes `["editorial", "output_renamed"]`.
    - Date `2022-06-23` on `2023/2023-06-23 - Midsommar - Dalarna` echoes `["editorial", "output_renamed"]` too, and
      its movie stays in `library-output/2023/`.
  - **Render:** `POST /api/v1/jobs` for Grillning (`"device": "cpu"`), then run `auto-reel worker --device cpu`
    with the same `DATABASE_URL` until the job is `done`. The worker also claims the `2024/Blandat` job the script
    leaves queued; that is expected. Then:
    - `library-output/2024/` holds both `2024-06-27 - Grillning med Grannar.mp4`, with its size and mtime as
      before, and `2024-06-27 - Grillkväll med grannarna.mp4`;
    - the detail reads `{"stale": false, "reasons": []}`.
  - **Cleanup:** stop `serve` and the worker by their own PIDs, drop the database, and delete the scratch library.

  Verify: every observation matches, recorded in the final report with the commands used.
- [ ] 6.2 Run the gates:
  - `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`
  - `.venv/bin/python -m mypy auto_reel_ng`
  - `.venv/bin/python -m pylint auto_reel_ng`
  - the full `.venv/bin/python -m pytest`, including `requires_db` (podman)
  - `npx tsc --noEmit && npm run build` in the node:22 container
  - `openspec validate output-renamed-reason --strict`

  Verify that all are clean or green, apart from the known cairo `no-member` noise and the five font-dependent
  skips.
