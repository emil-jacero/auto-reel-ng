## 1. Gate

- [ ] 1.1 Confirm the base. This change has no gate and is independent of `output-renamed-reason` and `renamed-label-and-zoom-bar`. It starts from `main` at `93721b3` or later. Re-check the names the design cites, and stop and report to the supervisor on any mismatch:
  - `auto_reel_ng/cli/adoption.py`: `prepare_event` has the `adopt_chapter` parameter and the single-chapter loop (`_ensure_chapter` → `order_clips(result.new, …)` → `add_clip`), and `_ensure_chapter` appends a missing chapter last
  - `auto_reel_ng/api/events_read.py` `_build_chapters`:
    - it keeps the seed branch for `document is None`
    - `order = document.sort or order` comes before the document-chapters loop
    - the `listing.by_chapter` loop creates a `ChapterOut` for a folder the document does not name
  - `grep -rn "adopt=True" auto_reel_ng` lists only `cli/build.py` (`prepare_and_persist`), and `scheduler/worker.py` and `cli/commands.py` reach adoption only through `prepare_and_persist`
  - `grep -rn "adopt_chapter" auto_reel_ng tests scripts` lists only `cli/adoption.py`
  - `docs/high-level-design.md` §7 ends at **D-11**, and no other open change claims D-12: `grep -rn "D-12" docs openspec/changes --include=*.md | grep -v -e /archive/ -e /adopt-into-folder-chapter/` prints nothing

  Then re-base the MODIFIED block in `specs/headless-cli/spec.md` on the current `openspec/specs/headless-cli/spec.md` "NEW-clip adoption policy", so no archived wording is lost.

  Verify: `openspec validate adopt-into-folder-chapter --strict` passes.

## 2. cli/ — one placement rule, used by adoption

- [ ] 2.1 Add `place_disk_clips(document, listing, identities, *, event_dir, order)` to `cli/adoption.py`, with the signature, docstring and group order from design "One placement function, in `cli/adoption.py`":
  - an identity's folder chapter comes from `listing.by_chapter`
  - its target is the folder chapter if `document.chapter(folder) is not None`, else `DEFAULT_CHAPTER_NAME`
  - groups come in document chapter order, then `""` last when the document lacks it, with no empty groups
  - each group is sorted with `order_clips(…, document.sort or order)`
  - an identity the listing does not hold raises `ReconcileError`

  Add direct tests to `tests/test_cli_adoption.py`. They use touched files and documents written with `write_document` or literal YAML, and need no ffmpeg:
  - a clip in `Kvällen/` → `Kvällen` when the document names it
  - a clip in `Dag 2/` → `""` when the document names only `""`
  - a root clip → `""`
  - a document that names no chapters: every clip → `""`
  - the document names only `Kvällen`, with NEW `b.mp4` (12:00) and `Dag 2/c.mp4` (11:00) under `DEFAULT_CLIP_ORDER`: the result is `(("", ("Dag 2/c.mp4", "b.mp4")),)`; a NEW `Kvällen/d.mp4` added to that case yields `Kvällen`'s group first
  - the same case with the document's own `sort: {method: filename}` orders by name
  - an identity not in the listing raises `ReconcileError`

  Verify:
  - `.venv/bin/python -m pytest tests/test_cli_adoption.py` passes
  - `.venv/bin/python -m mypy auto_reel_ng` is clean
- [ ] 2.2 Make `prepare_event` adopt by the rule (design snippet "`prepare_event` becomes").
  - Remove the `adopt_chapter` parameter.
  - Loop over `place_disk_clips(authored, listing, result.new, …)`, calling `_ensure_chapter` per target (it can only create `""`) and `add_clip` per clip. `adopted` is the concatenation of the groups.
  - Rewrite the module docstring's policy bullet, and the `PreparedEvent` and `prepare_event` docstrings, to state the folder rule with its default-chapter fallback, citing **D-12** (amends D-CLI3).

  **First** add these tests to `tests/test_cli_adoption.py` and see the first one fail on the current code (the clip lands in `""`):
  - `test_new_clip_joins_its_folders_chapter`, the spec's `2024-08-20 - Två kapitel - Tjörn` case: `Kvällen` becomes `Kvällen/s1710002.mp4`, `Kvällen/s1710003.mp4`, `Kvällen/s1710004.mp4`, and `""` stays `s1710001.mp4` alone
  - `test_new_clips_in_a_folder_without_a_chapter_join_the_default_chapter`: `Dag 2/…` is appended to `""` and no `Dag 2` chapter appears
  - `test_clips_from_two_folders_enter_the_default_chapter_in_rule_order`, the spec scenario: `""` is appended after `Kvällen`, listing `Dag 2/c.mp4`, `b.mp4`
  - `test_document_naming_no_chapters_adopts_every_clip_into_the_default_chapter`, for a `reel.yaml` of `version: 0` plus `metadata` only
  - `test_a_clip_adopted_earlier_stays_where_it_is`: a `reel.yaml` with `Kvällen/s1710004.mp4` in `""`. `prepared.adopted == ()`, `prepared.changed is False`, `persist(prepared) is None`, and the file's bytes are unchanged.

  Verify:
  - before the code change, `.venv/bin/python -m pytest tests/test_cli_adoption.py -k folders_chapter` fails, showing `Kvällen/s1710004.mp4` in `""`
  - after it, `.venv/bin/python -m pytest tests/test_cli_adoption.py` passes with every pre-existing test unchanged (`test_adopt_new_clip_into_default_chapter` and the order and legacy-`sort` tests adopt root clips only)
  - `grep -rn "adopt_chapter" auto_reel_ng tests scripts` prints nothing
  - `.venv/bin/python -m pytest -m "not requires_db"` passes
  - `.venv/bin/python -m mypy auto_reel_ng` is clean
- [ ] 2.3 Add `tests/test_cli_render_adoption.py`: a real render through `main([...])` over a scratch library in `tmp_path`, marked `@pytest.mark.has_ffmpeg`, using the `runtime` and `make_clip` fixtures (1.0 s, 320×240, moved into place as in `tests/test_cli_render_staleness.py`). Every run is `main(["render", str(root), "-o", str(out), "--device", "cpu"])`:
  1. `2024/2024-08-20 - Två kapitel - Tjörn` holds `s1710001.mp4`, `Kvällen/s1710002.mp4` and `Kvällen/s1710003.mp4`. The first render exits 0 and seeds `""` = [`s1710001.mp4`] and `Kvällen` = [`Kvällen/s1710002.mp4`, `Kvällen/s1710003.mp4`].
  2. Add `Kvällen/s1710004.mp4` and `Dag 2/s1710005.mp4`. The second render:
     - exits 0, and stdout contains `adopted 2 new clip(s)`
     - `load_document(reel.yaml)` has exactly the chapters `""` = [`s1710001.mp4`, `Dag 2/s1710005.mp4`] and `Kvällen` = [`Kvällen/s1710002.mp4`, `Kvällen/s1710003.mp4`, `Kvällen/s1710004.mp4`], and no `Dag 2` chapter
     - `runtime.run_ffprobe(["-v", "error", "-show_chapters", "-print_format", "json", <movie>])` reports two chapters. The second is titled `Kvällen` and spans 3.0 s ± 0.3, and the first spans 2.0 s ± 0.3.
  3. A third render prints `FRESH` for the event and leaves `reel.yaml` byte-identical.

  Verify: `.venv/bin/python -m pytest tests/test_cli_render_adoption.py -v` passes on this host. The test is collected under `-m has_ffmpeg` and deselected by `-m "not has_ffmpeg"`.

## 3. api/ — the detail shows the same placement

- [ ] 3.1 In `api/events_read.py` `_build_chapters`, replace the `listing.by_chapter` loop with the `place_disk_clips` loop over every disk-only clip (NEW and IGNORED) from design "One placement function, in `cli/adoption.py`". Drop `order = document.sort or order`, leave the seed branch unchanged, and update the docstring (D-12: placed where a render adopts them). Import `place_disk_clips` beside the existing `from ..cli.adoption import REEL_FILENAME`.

  Add tests to `tests/test_api_events.py` (the module is `requires_db`). Each builds its own event under the `project` fixture's root with touched files and a literal `reel.yaml`, and reads `GET /api/v1/events/{event_id}`:
  - `test_detail_shows_a_new_clip_in_its_folders_chapter`, the spec's `Två kapitel` case, with names and statuses per chapter
  - `test_detail_shows_a_folder_without_a_chapter_in_the_default_chapter`: exactly one chapter, `""`, and no `Dag 2`
  - `test_detail_of_a_document_naming_no_chapters_is_one_default_chapter`
  - `test_detail_places_an_ignored_clip_like_a_new_one`: an ignored `Dag 2/s1710002.mp4` is listed in `""` with status `ignored`
  - `test_detail_chapters_are_the_chapters_render_adopts`, the spec scenario "The page's chapters are the movie's chapters":
    - setup: one event with a NEW clip in a named folder chapter, a NEW clip in a folder with no chapter, a NEW root clip, an ignored root clip, and `datetime` mtimes set with `os.utime`
    - steps: GET, then `persist(prepare_event(event_dir, order=DEFAULT_CLIP_ORDER))`, then GET again
    - per chapter, the non-ignored identities are equal across both reads and equal to `load_document(reel.yaml)`'s chapters
    - every first-read `new` is `active` in the second
  - the existing `test_event_detail_chapters_from_disk_listing_without_document` (seed view) passes unchanged

  Verify:
  - `.venv/bin/python -m pytest tests/test_api_events.py tests/test_api_openapi.py` passes (podman). The OpenAPI drift test passes unchanged.
  - `git diff --stat main -- web/` is empty
  - `.venv/bin/python -m mypy auto_reel_ng` is clean

## 4. docs

- [ ] 4.1 Add **D-12** to `docs/high-level-design.md` §7 after D-11, with the text in design "HLD: D-12 records the amendment" (amends D-CLI3, dated 2026-10-01, with the reason). Add the §4.6 sentence after "thereafter the file wins." In `README.md`'s "Adoption policy" bullet, replace "adopts any newly added clip into the default chapter (so it is never silently dropped)" with the folder rule and its fallback. Example: "adopts any newly added clip into the chapter named after its folder (the default chapter for a clip in the event folder itself), or into the default chapter when `reel.yaml` has no chapter of that name, so it is never silently dropped".

  Verify:
  - `grep -n "D-12" docs/high-level-design.md` shows the §7 entry and the §4.6 reference
  - `grep -n -A3 "Adoption policy" README.md` shows the folder rule and its default-chapter fallback (the bullet wraps, so read it rather than grep one phrase)
  - `grep -rn -e "(configurable)" -e "adopt_chapter" auto_reel_ng README.md docs/high-level-design.md` prints nothing (today it lists `cli/adoption.py` lines 8, 75, 79, 92 and 95)
  - `git diff --stat main -- openspec/changes/archive` is empty

## 5. Live check

- [ ] 5.1 Reproduce the end-to-end failure and see it fixed through the GUI's own path. Use the scratch directory and the database of your own that the implementation brief assigns: never the default `auto_reel_ng` database, never `auto-reel-media/`, never ports 8080 or 5173. Use port **8122**.
  1. With your `DATABASE_URL` exported, run `.venv/bin/alembic upgrade head`, then `.venv/bin/python scripts/make_dev_library.py <scratch>/dev`.
  2. Link one more clip into a folder that has no chapter: `mkdir "<scratch>/dev/library/2024/2024-08-02 - Badutflykt - Varberg/Dag 2" && ln -s <scratch>/dev/clips/s1710002.mp4 "<scratch>/dev/library/2024/2024-08-02 - Badutflykt - Varberg/Dag 2/s1710002.mp4"`.
  3. Start `.venv/bin/auto-reel serve <scratch>/dev/library --port 8122` and `.venv/bin/auto-reel worker`, both in the background with your `DATABASE_URL`. If the checkout has no `web/dist/index.html`, first build it with `podman run --rm -v "$PWD/web:/app:Z" -w /app docker.io/library/node:22 sh -c "npm ci && npm run build"`. The worker also runs the job the dev library leaves queued for `2024/Blandat`; that is expected.
  4. Check `curl -s "http://127.0.0.1:8122/api/v1/events/2024/2024-08-20%20-%20Tv%C3%A5%20kapitel%20-%20Tj%C3%B6rn" | jq '[.chapters[] | {name, clips: [.clips[] | "\(.identity) \(.status)"]}]'`:
     - `Kvällen` ends with `Kvällen/s1710004.mp4 new`
     - `""` holds `s1710001.mp4 active` and `s1710004.mp4 ignored`
  5. For Badutflykt, the same query lists `Dag 2/s1710002.mp4 new` in `""` and no `Dag 2` chapter.
  6. **Before rendering**, in Playwright (`podman run --rm --network host -v <scratch>:/work:Z mcr.microsoft.com/playwright/python:v1.49.0-noble …`, with a script in the scratch directory, never in the repo), open `http://127.0.0.1:8122/#/event/2024/2024-08-20%20-%20Tv%C3%A5%20kapitel%20-%20Tj%C3%B6rn` at 1280×900 and take the "before" screenshot. Check:
     - the `Kvällen` table lists `s1710004.mp4` as new
     - the `Main` table has no `Kvällen/` row
  7. Render both events with `curl -s -X POST -H 'Content-Type: application/json' -d '{"event_id": "<id>"}' http://127.0.0.1:8122/api/v1/jobs`. Poll `GET /api/v1/jobs/<job id>` until `done`.
  8. After the render:
     - each `reel.yaml` lists the clips exactly where step 4 or 5 showed them, ignored clips aside
     - the GETs of steps 4 and 5 show the same chapters and order, with every clip that was `new` now `active`
     - `ffprobe -v error -show_chapters -print_format json "<scratch>/dev/library-output/2024/2024-08-20 - Två Kapitel - Tjörn.mp4"` reports the untitled default chapter about one clip long (≈6 s) and `Kvällen` about three clips long (≈18 s of 6 s cuts)
     - the same Playwright script, run again, takes the "after" screenshot: the `Kvällen` table lists `s1710004.mp4` as included, and the `Main` table still has no `Kvällen/` row

  Then stop serve and the worker, drop your database, and remove the scratch library.

  Verify: record the GET outputs, the two `reel.yaml` files, the ffprobe chapter spans and the two screenshot paths in the implementation report.

## 6. Validation

- [ ] 6.1 Run the validation gates:
  - `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`
  - `.venv/bin/python -m mypy auto_reel_ng`
  - `.venv/bin/python -m pylint auto_reel_ng`
  - the full `.venv/bin/python -m pytest`, including `requires_db` and `has_ffmpeg`

  Verify:
  - all are clean or green, apart from the known cairo `no-member` noise and the environmental title-card skips
  - `RENDER_GRAPH_VERSION` in `auto_reel_ng/staleness/fingerprint.py` is unchanged (still 3)
  - `git diff --stat main -- alembic web` is empty
  - `openspec validate adopt-into-folder-chapter --strict` passes
