"""Round-trip and corruption-handling tests for the render manifest sidecar (task 1.2)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from auto_reel_ng.reel.document import Metadata, ReelDocument
from auto_reel_ng.render import output_relpath
from auto_reel_ng.staleness.fingerprint import compute_fingerprint, engine_identity
from auto_reel_ng.staleness.manifest import (
    ChapterTime,
    TitleCardSpan,
    manifest_path,
    read_manifest,
    recorded_movie_path,
    recorded_output_in,
    recorded_output_path,
    records_output,
    write_manifest,
)

FFMPEG_VERSION = (7, 1)


def _fingerprint(event_dir: Path):
    document = ReelDocument(metadata=Metadata(title="Party"))
    return compute_fingerprint(
        document, event_dir=event_dir, look_defaults={}, ffmpeg_version=FFMPEG_VERSION
    )


def test_manifest_round_trips(tmp_path: Path) -> None:
    fingerprint = _fingerprint(tmp_path)
    path = write_manifest(
        tmp_path, fingerprint, output="Party.mp4", engine_identity=engine_identity(FFMPEG_VERSION)
    )

    assert path == manifest_path(tmp_path)
    assert path.exists()

    manifest = read_manifest(tmp_path)
    assert manifest is not None
    assert manifest.fingerprint == fingerprint.combined
    assert manifest.components["editorial"] == fingerprint.editorial
    assert manifest.components["clip_set"] == fingerprint.clip_set
    assert manifest.output == "Party.mp4"
    assert manifest.engine_identity == engine_identity(FFMPEG_VERSION)
    assert manifest.written_at


def test_missing_manifest_reads_as_none(tmp_path: Path) -> None:
    assert read_manifest(tmp_path) is None


def test_corrupt_manifest_reads_as_none(tmp_path: Path) -> None:
    fingerprint = _fingerprint(tmp_path)
    write_manifest(tmp_path, fingerprint, output="Party.mp4", engine_identity="x")

    manifest_path(tmp_path).write_text("{ not valid json", encoding="utf-8")

    assert read_manifest(tmp_path) is None


def test_schema_version_mismatch_reads_as_none(tmp_path: Path) -> None:
    fingerprint = _fingerprint(tmp_path)
    write_manifest(tmp_path, fingerprint, output="Party.mp4", engine_identity="x")

    path = manifest_path(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["version"] = 999
    path.write_text(json.dumps(payload), encoding="utf-8")

    assert read_manifest(tmp_path) is None


def test_structurally_incomplete_manifest_reads_as_none(tmp_path: Path) -> None:
    path = manifest_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"version": 1}), encoding="utf-8")

    assert read_manifest(tmp_path) is None


def test_manifest_lives_beside_the_analysis_cache(tmp_path: Path) -> None:
    fingerprint = _fingerprint(tmp_path)
    write_manifest(tmp_path, fingerprint, output="Party.mp4", engine_identity="x")

    assert manifest_path(tmp_path) == tmp_path / ".auto-reel" / "cache" / "render-manifest.json"


#: Every shape the output-naming rule (D-9) produces: dated, dated with a location, undated,
#: undated with a location, and a year below 1000 (zero-padded folder and date prefix).
_NAME_SHAPES = (
    Metadata(title="Grillning med Grannar", date=date(2024, 6, 27)),
    Metadata(title="Midsommar", date=date(2023, 6, 23), location="Dalarna"),
    Metadata(title="Blandat"),
    Metadata(title="Blandat", location="Hemma"),
    Metadata(title="Gammal", date=date(999, 1, 2)),
)


@pytest.mark.parametrize("new", _NAME_SHAPES, ids=lambda m: output_relpath(m).as_posix())
@pytest.mark.parametrize("old", _NAME_SHAPES, ids=lambda m: output_relpath(m).as_posix())
def test_recorded_output_path_inverts_output_relpath(
    tmp_path: Path, old: Metadata, new: Metadata
) -> None:
    """The helper finds exactly where D-9 put the old name, whatever the event is called now.

    It restates where ``output_relpath`` places a name; a change to that rule fails here
    until the helper follows it.
    """
    out = tmp_path / "library-output"

    found = recorded_output_path(output_relpath(old).name, out / output_relpath(new))

    assert found == out / output_relpath(old)


def test_recorded_output_path_reads_no_disk(tmp_path: Path) -> None:
    """Pure: the same answers under an output directory that does not exist."""
    out = tmp_path / "does-not-exist" / "library-output"
    assert not out.exists()

    for old in _NAME_SHAPES:
        for new in _NAME_SHAPES:
            found = recorded_output_path(output_relpath(old).name, out / output_relpath(new))
            assert found == out / output_relpath(old)
    assert not (tmp_path / "does-not-exist").exists()


def test_recorded_movie_path_places_dated_and_undated_names(tmp_path: Path) -> None:
    out = tmp_path / "out"
    expected = out / "2025" / "2025-01-02 - New.mp4"

    assert (
        recorded_movie_path("2024-06-27 - Old.mp4", expected)
        == out / "2024" / "2024-06-27 - Old.mp4"
    )
    assert recorded_movie_path("Undated.mp4", expected) == out / "Undated.mp4"
    assert recorded_movie_path("Undated.mp4", out / "Other.mp4") == out / "Undated.mp4"


@pytest.mark.parametrize("recorded", ["", ".", "..", "a/b.mp4", "2024/2024-06-27 - Old.mp4"])
def test_recorded_movie_path_refuses_anything_but_a_bare_file_name(
    tmp_path: Path, recorded: str
) -> None:
    assert recorded_movie_path(recorded, tmp_path / "2025" / "2025-01-02 - New.mp4") is None


def _record(event_dir: Path, output: str) -> None:
    event_dir.mkdir(parents=True, exist_ok=True)
    write_manifest(
        event_dir, _fingerprint(event_dir), output=output, engine_identity=engine_identity((7, 1))
    )


def test_records_output_matches_the_exact_file(tmp_path: Path) -> None:
    event = tmp_path / "event"
    event.mkdir()
    _record(event, "2024-06-27 - Old.mp4")
    out = tmp_path / "out"

    assert records_output(event, out / "2024" / "2024-06-27 - Old.mp4")
    assert not records_output(event, out / "2023" / "2024-06-27 - Old.mp4")  # another year folder
    assert not records_output(event, out / "2024" / "2024-06-27 - Other.mp4")  # another name


def test_records_output_is_case_and_unicode_insensitive(tmp_path: Path) -> None:
    event = tmp_path / "event"
    event.mkdir()
    _record(event, "2024-06-27 - Gr\u00e5 Kv\u00e4ll.mp4")  # precomposed
    out = tmp_path / "out"

    assert records_output(
        event, out / "2024" / "2024-06-27 - gra\u030a kva\u0308ll.mp4"
    )  # NFD, lower


def test_records_output_is_false_without_a_usable_manifest(tmp_path: Path) -> None:
    out = tmp_path / "out" / "2024" / "2024-06-27 - Old.mp4"
    absent = tmp_path / "absent"
    absent.mkdir()
    malformed = tmp_path / "malformed"
    _record(malformed, "2024-06-27 - Old.mp4")
    manifest_path(malformed).write_text("{not json", encoding="utf-8")
    wrong_version = tmp_path / "wrong-version"
    _record(wrong_version, "2024-06-27 - Old.mp4")
    payload = json.loads(manifest_path(wrong_version).read_text(encoding="utf-8"))
    payload["version"] = 999
    manifest_path(wrong_version).write_text(json.dumps(payload), encoding="utf-8")
    dotdot = tmp_path / "dotdot"
    _record(dotdot, "..")

    for event in (absent, malformed, wrong_version, dotdot):
        assert not records_output(event, out)


# --- superseded names (change prune-renamed-command) -------------------------------------------


def _write(event: Path, output: str) -> None:
    event.mkdir(exist_ok=True)
    write_manifest(event, _fingerprint(event), output=output, engine_identity="x")


def _superseded(event: Path) -> tuple[str, ...]:
    manifest = read_manifest(event)
    assert manifest is not None
    return manifest.superseded


def test_first_manifest_has_no_superseded_names(tmp_path: Path) -> None:
    _write(tmp_path / "e", "A.mp4")

    assert _superseded(tmp_path / "e") == ()


def test_a_rename_records_the_previous_output_as_superseded(tmp_path: Path) -> None:
    event = tmp_path / "e"
    _write(event, "2024-06-27 - Grillning med Grannar.mp4")
    _write(event, "2024-06-27 - Grillkv\u00e4ll med grannarna.mp4")

    manifest = read_manifest(event)
    assert manifest is not None
    assert manifest.output == "2024-06-27 - Grillkv\u00e4ll med grannarna.mp4"
    assert manifest.superseded == ("2024-06-27 - Grillning med Grannar.mp4",)


def test_several_renames_accumulate_in_order(tmp_path: Path) -> None:
    event = tmp_path / "e"
    for name in ("A.mp4", "B.mp4", "C.mp4"):
        _write(event, name)

    assert _superseded(event) == ("A.mp4", "B.mp4")


def test_a_write_under_the_same_name_keeps_the_list(tmp_path: Path) -> None:
    event = tmp_path / "e"
    for name in ("A.mp4", "B.mp4", "B.mp4", "B.mp4"):
        _write(event, name)

    assert _superseded(event) == ("A.mp4",)


def test_renaming_back_removes_the_current_name_from_the_list(tmp_path: Path) -> None:
    event = tmp_path / "e"
    for name in ("A.mp4", "B.mp4", "A.mp4"):
        _write(event, name)

    manifest = read_manifest(event)
    assert manifest is not None
    assert manifest.output == "A.mp4"
    assert manifest.superseded == ("B.mp4",)


def test_a_name_is_listed_once(tmp_path: Path) -> None:
    event = tmp_path / "e"
    for name in ("A.mp4", "B.mp4", "A.mp4", "B.mp4", "C.mp4"):
        _write(event, name)

    assert _superseded(event) == ("A.mp4", "B.mp4")


def test_a_manifest_without_the_field_reads_as_empty(tmp_path: Path) -> None:
    event = tmp_path / "e"
    _write(event, "A.mp4")
    payload = json.loads(manifest_path(event).read_text(encoding="utf-8"))
    payload.pop("superseded", None)
    manifest_path(event).write_text(json.dumps(payload), encoding="utf-8")

    assert _superseded(event) == ()


@pytest.mark.parametrize("value", ["x", ["A.mp4", 3], {"a": "b"}, 7, None])
def test_a_malformed_superseded_field_reads_as_empty_and_stays_valid(
    tmp_path: Path, value: object
) -> None:
    event = tmp_path / "e"
    _write(event, "B.mp4")
    payload = json.loads(manifest_path(event).read_text(encoding="utf-8"))
    payload["superseded"] = value
    manifest_path(event).write_text(json.dumps(payload), encoding="utf-8")

    manifest = read_manifest(event)
    assert manifest is not None
    assert manifest.output == "B.mp4"
    assert manifest.superseded == ()


def test_an_unreadable_previous_manifest_contributes_nothing(tmp_path: Path) -> None:
    event = tmp_path / "e"
    _write(event, "A.mp4")
    manifest_path(event).write_text("{ not json", encoding="utf-8")
    _write(event, "B.mp4")

    assert _superseded(event) == ()


def test_the_superseded_list_is_not_part_of_the_fingerprint(tmp_path: Path) -> None:
    event = tmp_path / "e"
    _write(event, "A.mp4")
    first = read_manifest(event)
    _write(event, "B.mp4")
    second = read_manifest(event)

    assert first is not None and second is not None
    assert second.fingerprint == first.fingerprint
    assert dict(second.components) == dict(first.components)
    assert second.written_at


def test_recorded_output_in_places_dated_and_undated_names(tmp_path: Path) -> None:
    out = tmp_path / "out"

    assert recorded_output_in("2024-06-27 - X.mp4", out) == out / "2024" / "2024-06-27 - X.mp4"
    assert recorded_output_in("Party.mp4", out) == out / "Party.mp4"


def test_recorded_output_path_agrees_with_recorded_output_in(tmp_path: Path) -> None:
    out = tmp_path / "out"
    for expected in (out / "2023" / "2023-01-02 - Z.mp4", out / "Undated.mp4"):
        for recorded in ("2024-06-27 - X.mp4", "Party.mp4"):
            assert recorded_output_path(recorded, expected) == recorded_output_in(recorded, out)


# --- chapter times (change render-chapter-times) -----------------------------------------------

_TWO_CHAPTERS = (
    ChapterTime(name="Intro", start_ms=0, end_ms=1500),
    ChapterTime(
        name="Beach",
        start_ms=1500,
        end_ms=6000,
        title_card=TitleCardSpan(start_ms=2000, end_ms=5000),
    ),
)


def _write_chapters(event: Path, chapters: object) -> None:
    event.mkdir(exist_ok=True)
    write_manifest(
        event,
        _fingerprint(event),
        output="A.mp4",
        engine_identity="x",
        chapters=chapters,  # type: ignore[arg-type]
    )


def _stored_chapters(event: Path) -> object:
    return json.loads(manifest_path(event).read_text(encoding="utf-8"))["chapters"]


def _set_chapters_field(event: Path, value: object) -> None:
    payload = json.loads(manifest_path(event).read_text(encoding="utf-8"))
    payload["chapters"] = value
    manifest_path(event).write_text(json.dumps(payload), encoding="utf-8")


def test_chapter_times_round_trip(tmp_path: Path) -> None:
    event = tmp_path / "e"
    _write_chapters(event, _TWO_CHAPTERS)

    manifest = read_manifest(event)
    assert manifest is not None
    assert manifest.chapters == _TWO_CHAPTERS
    assert _stored_chapters(event) == [
        {"name": "Intro", "start_ms": 0, "end_ms": 1500, "title_card": None},
        {
            "name": "Beach",
            "start_ms": 1500,
            "end_ms": 6000,
            "title_card": {"start_ms": 2000, "end_ms": 5000},
        },
    ]


def test_a_manifest_written_without_chapter_times_stores_null(tmp_path: Path) -> None:
    event = tmp_path / "e"
    _write(event, "A.mp4")

    manifest = read_manifest(event)
    assert manifest is not None and manifest.chapters is None
    assert _stored_chapters(event) is None


def test_a_version_1_manifest_without_the_field_reads_as_valid_with_none(tmp_path: Path) -> None:
    event = tmp_path / "e"
    _write_chapters(event, _TWO_CHAPTERS)
    payload = json.loads(manifest_path(event).read_text(encoding="utf-8"))
    del payload["chapters"]
    manifest_path(event).write_text(json.dumps(payload), encoding="utf-8")

    manifest = read_manifest(event)
    assert manifest is not None
    assert manifest.chapters is None
    assert manifest.output == "A.mp4"


_GOOD = {"name": "A", "start_ms": 0, "end_ms": 100, "title_card": None}


@pytest.mark.parametrize(
    "value",
    [
        "x",
        7,
        {"name": "A"},
        [_GOOD, "x"],
        [{**_GOOD, "start_ms": True}],
        [{**_GOOD, "end_ms": 1.5}],
        [{**_GOOD, "start_ms": "0"}],
        [{**_GOOD, "start_ms": -1}],
        [{**_GOOD, "start_ms": 200}],
        [{k: v for k, v in _GOOD.items() if k != "name"}],
        [{**_GOOD, "name": 3}],
        [{k: v for k, v in _GOOD.items() if k != "end_ms"}],
        [{**_GOOD, "title_card": {"start_ms": 50, "end_ms": 150}}],
        [{**_GOOD, "title_card": {"start_ms": 60, "end_ms": 50}}],
        [{**_GOOD, "title_card": "x"}],
        [{**_GOOD, "title_card": {"start_ms": 0}}],
        [_GOOD, {**_GOOD, "start_ms": 100, "end_ms": 50}],
    ],
)
def test_a_malformed_chapter_list_reads_as_none_as_a_whole(tmp_path: Path, value: object) -> None:
    event = tmp_path / "e"
    _write(event, "A.mp4")
    _set_chapters_field(event, value)

    manifest = read_manifest(event)
    assert manifest is not None
    assert manifest.chapters is None
    assert manifest.output == "A.mp4"


def test_a_rewritten_manifest_does_not_carry_chapters_over(tmp_path: Path) -> None:
    event = tmp_path / "e"
    _write_chapters(event, _TWO_CHAPTERS)
    _write(event, "A.mp4")

    manifest = read_manifest(event)
    assert manifest is not None and manifest.chapters is None


def test_chapter_times_leave_the_other_fields_and_the_fingerprint_alone(tmp_path: Path) -> None:
    plain, with_chapters = tmp_path / "p", tmp_path / "c"
    _write(plain, "A.mp4")
    _write_chapters(with_chapters, _TWO_CHAPTERS)
    a, b = read_manifest(plain), read_manifest(with_chapters)

    assert a is not None and b is not None
    assert (a.fingerprint, dict(a.components), a.output, a.superseded) == (
        b.fingerprint,
        dict(b.components),
        b.output,
        b.superseded,
    )
