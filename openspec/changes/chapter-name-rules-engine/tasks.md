## 1. reel/ — chapter-name rules

- [ ] 1.1 In `reel/schema.py` add `check_chapter_names(names, *, source)` with the rules and messages from design "The rules" and call it from `_parse_chapters` in place of the exact-duplicate check (keep the `duplicate chapter name` prefix). Tests in `tests/test_reel_parser.py`: `"  "` and `"\t"` are refused as blank, `" Party"` and `"Party "` as padded, `Party`/`party` and `Straße`/`STRASSE` as duplicates naming `chapters[1]`, `chapters[0]` and both names, two exact duplicates and two `""` still refused, `""` + `Reception` + `Dag 2` loads, and the loaded names are unchanged.
- [ ] 1.2 In `reel/writer.py` call `check_chapter_names` on `doc.chapters` at the start of `write_document`. Tests in `tests/test_reel_writer.py`: a document with `"Party "` or with `Party` and `party` raises `ReelParseError`, an existing `reel.yaml` is byte-identical afterwards, and no `.reel.yaml.*.tmp` is left; a valid document still writes and round-trips.
- [ ] 1.3 In `reel/document.py` make `ReelDocument.chapter(name)` exact first, then `str.casefold()`; update its docstring. Tests in `tests/test_reel_values.py` or a new `tests/test_reel_document.py`: exact wins, case variant is found, `""` finds only the default chapter, an absent name returns `None`, a padded name returns `None`.

## 2. cli/ — adoption

- [ ] 2.1 In `cli/adoption.py` `place_disk_clips` key each bucket by the matched chapter's own name (`document.chapter(folder).name`) and update the docstring and module docstring. Tests in `tests/test_cli_adoption.py`: a new clip in `party/` joins chapter `Party` and is listed under `Party`; an exact match wins over a casefold one; a folder `Party ` goes to the default chapter and creates no chapter; the events-detail placement (`_build_chapters`) shows the clip under `Party`.
- [ ] 2.2 Test the seeding failures end to end in `tests/test_cli_adoption.py`: `prepare_event` plus `persist` on an event with no `reel.yaml` and folders `Party/` and `party/` fails with the duplicate chapter name error and writes no `reel.yaml`; the same for a metadata-only `reel.yaml` (left unchanged); the same for a folder with a trailing space.
- [ ] 2.3 Test that the other events of a scan are unaffected: `scan` over a root with one event holding `Party`/`party` chapters in its `reel.yaml` and one valid event reports the first as an unparseable `reel.yaml` error naming both chapters and the second normally. Add to `tests/test_cli_adoption.py` or the existing scan test module.

## 3. Docs

- [ ] 3.1 Amend `docs/high-level-design.md`: the "Amended 2026-10-02" paragraph on D-12 and the §4.1 `chapters` note, as in design "HLD", with the user's answer ("Enforce in engine") and the migration note. Verify: `grep -n "casefold" docs/high-level-design.md` finds both places.

## 4. Gates

- [ ] 4.1 `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`, then `.venv/bin/python -m mypy auto_reel_ng` and `.venv/bin/python -m pylint auto_reel_ng` clean (known cairo `no-member` noise only).
- [ ] 4.2 `.venv/bin/python -m pytest` passes (full suite; `-m "not requires_db"` and say so if podman is unavailable), and `openspec validate chapter-name-rules-engine --strict` passes.
