"""Tests for the poster sidecar as a claim: manifest field, scan verdict, render guard, prune.

No ffmpeg: manifests are written directly and the movies and sidecars are stand-in files.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from auto_reel_ng.cli.main import main
from auto_reel_ng.config import default_output_dir
from auto_reel_ng.reel.document import Chapter, ClipRef, Metadata, Poster, ReelDocument
from auto_reel_ng.render.claims import claimed_movie
from auto_reel_ng.staleness import fingerprint as fingerprint_module
from auto_reel_ng.staleness.fingerprint import compute_fingerprint
from auto_reel_ng.staleness.gate import StalenessReason, evaluate
from auto_reel_ng.staleness.manifest import (
    manifest_path,
    read_manifest,
    records_poster,
    write_manifest,
)

MOVIE = "2024-06-21 - Party.mp4"
SIDECAR = "2024-06-21 - Party-poster.jpg"


def _document(poster: Poster | None = None) -> ReelDocument:
    return ReelDocument(
        metadata=Metadata(title="Party"),
        chapters=(Chapter(name="", clips=(ClipRef("00400.mp4"),)),),
        poster=poster,
    )


def _event(root: Path, name: str = "2024-06-21 - Party") -> Path:
    event_dir = root / "2024" / name
    event_dir.mkdir(parents=True, exist_ok=True)
    (event_dir / "00400.mp4").write_bytes(b"")
    return event_dir


def _record(
    event_dir: Path, *names: str, poster: str | None = None, document: ReelDocument | None = None
):
    fingerprint = compute_fingerprint(
        document or _document(), event_dir=event_dir, look_defaults={}, ffmpeg_version=(7, 1)
    )
    for name in names:
        write_manifest(event_dir, fingerprint, output=name, engine_identity="x", poster=poster)
    return fingerprint


def _touch(path: Path, data: bytes = b"x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _edit(event_dir: Path, **fields: object) -> None:
    payload = json.loads(manifest_path(event_dir).read_text(encoding="utf-8"))
    payload.update(fields)
    payload = {k: v for k, v in payload.items() if v != "<drop>"}
    manifest_path(event_dir).write_text(json.dumps(payload), encoding="utf-8")


# -- the manifest field ------------------------------------------------------ #


def test_the_manifest_records_the_sidecar_name(tmp_path: Path) -> None:
    event_dir = _event(tmp_path)
    _record(event_dir, MOVIE, poster=SIDECAR)
    manifest = read_manifest(event_dir)
    assert manifest is not None and manifest.poster == SIDECAR


def test_a_manifest_without_the_field_or_with_none_expects_no_sidecar(tmp_path: Path) -> None:
    event_dir = _event(tmp_path)
    _record(event_dir, MOVIE)
    manifest = read_manifest(event_dir)
    assert manifest is not None and manifest.poster is None
    _edit(event_dir, poster="<drop>")
    manifest = read_manifest(event_dir)
    assert manifest is not None and manifest.poster is None


@pytest.mark.parametrize("bad", [7, ["a.jpg"], "", ".", "..", "sub/a.jpg", "../a.jpg"])
def test_a_malformed_field_reads_as_none_without_spoiling_the_manifest(
    tmp_path: Path, bad: object
) -> None:
    event_dir = _event(tmp_path)
    _record(event_dir, MOVIE, poster=SIDECAR)
    _edit(event_dir, poster=bad)
    manifest = read_manifest(event_dir)
    assert manifest is not None and manifest.poster is None and manifest.output == MOVIE


def test_the_poster_is_not_carried_over_from_the_previous_manifest(tmp_path: Path) -> None:
    event_dir = _event(tmp_path)
    fingerprint = _record(event_dir, MOVIE, poster=SIDECAR)
    write_manifest(event_dir, fingerprint, output=MOVIE, engine_identity="x")
    manifest = read_manifest(event_dir)
    assert manifest is not None and manifest.poster is None


# -- the scan verdict -------------------------------------------------------- #


def _rendered(tmp_path: Path, *, with_sidecar: bool, poster: str | None = SIDECAR):
    event_dir = _event(tmp_path)
    fingerprint = _record(event_dir, MOVIE, poster=poster)
    movie = _touch(tmp_path / "out" / "2024" / MOVIE)
    if with_sidecar:
        _touch(movie.with_name(SIDECAR))
    return event_dir, movie, fingerprint


def test_a_whole_output_is_fresh(tmp_path: Path) -> None:
    event_dir, movie, fingerprint = _rendered(tmp_path, with_sidecar=True)
    assert not evaluate(event_dir, movie, fingerprint).stale


def test_a_deleted_sidecar_makes_the_event_stale_with_reason_output(tmp_path: Path) -> None:
    event_dir, movie, fingerprint = _rendered(tmp_path, with_sidecar=False)
    verdict = evaluate(event_dir, movie, fingerprint)
    assert verdict.stale and verdict.reasons == (StalenessReason.OUTPUT,)


def test_a_sidecar_that_is_a_folder_is_missing(tmp_path: Path) -> None:
    event_dir, movie, fingerprint = _rendered(tmp_path, with_sidecar=False)
    movie.with_name(SIDECAR).mkdir()
    assert evaluate(event_dir, movie, fingerprint).reasons == (StalenessReason.OUTPUT,)


def test_a_manifest_with_no_poster_expects_no_sidecar(tmp_path: Path) -> None:
    event_dir, movie, fingerprint = _rendered(tmp_path, with_sidecar=False, poster=None)
    assert not evaluate(event_dir, movie, fingerprint).stale


def test_an_old_manifest_without_the_field_stays_fresh(tmp_path: Path) -> None:
    event_dir, movie, fingerprint = _rendered(tmp_path, with_sidecar=False)
    _edit(event_dir, poster="<drop>")
    assert not evaluate(event_dir, movie, fingerprint).stale


def test_a_poster_edit_is_stale_with_the_editorial_component(tmp_path: Path) -> None:
    event_dir, movie, _ = _rendered(tmp_path, with_sidecar=True)
    edited = compute_fingerprint(
        _document(Poster("00400.mp4", 4.0)),
        event_dir=event_dir,
        look_defaults={},
        ffmpeg_version=(7, 1),
    )
    assert evaluate(event_dir, movie, edited).reasons == (StalenessReason.EDITORIAL,)


def test_the_render_graph_version_is_nine_and_moves_the_engine_component(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    event_dir = _event(tmp_path)
    assert fingerprint_module.RENDER_GRAPH_VERSION == 11
    now = _record(event_dir, MOVIE)
    monkeypatch.setattr(fingerprint_module, "RENDER_GRAPH_VERSION", 8)
    before = compute_fingerprint(
        _document(), event_dir=event_dir, look_defaults={}, ffmpeg_version=(7, 1)
    )
    assert before.engine != now.engine and before.editorial == now.editorial


# -- the render guard -------------------------------------------------------- #


def test_another_events_recorded_poster_is_claimed(tmp_path: Path) -> None:
    owner = _event(tmp_path, "2024-06-21 - Party")
    newcomer = _event(tmp_path, "2024-06-21 - Party 2")
    _record(owner, "2024-06-21 - Old.mp4", poster=SIDECAR)  # its movie is named otherwise
    movie = tmp_path / "out" / "2024" / MOVIE  # no movie here: only the sidecar exists
    _touch(movie.with_name(SIDECAR))

    found = claimed_movie(newcomer, movie, events=[owner, newcomer])
    assert found is not None and found.recorded_by == (owner,)
    assert claimed_movie(owner, movie, events=[owner, newcomer]) is None  # its own file


def test_a_sidecar_nobody_records_is_not_claimed(tmp_path: Path) -> None:
    owner = _event(tmp_path, "2024-06-21 - Party")
    newcomer = _event(tmp_path, "2024-06-21 - Party 2")
    _record(owner, "2024-06-21 - Old.mp4")
    movie = tmp_path / "out" / "2024" / MOVIE
    _touch(movie.with_name(SIDECAR))
    assert claimed_movie(newcomer, movie, events=[owner, newcomer]) is None


def test_records_poster_finds_the_dated_sidecar_in_its_year_folder(tmp_path: Path) -> None:
    event_dir = _event(tmp_path)
    _record(event_dir, MOVIE, poster=SIDECAR)
    sidecar = tmp_path / "out" / "2024" / SIDECAR
    assert records_poster(event_dir, sidecar)
    assert not records_poster(event_dir, tmp_path / "out" / "2024" / "other-poster.jpg")


# -- prune-renamed ----------------------------------------------------------- #

OLD = "2024-06-21 - Old Party.mp4"
OLD_SIDECAR = "2024-06-21 - Old Party-poster.jpg"
NEW = "2024-06-21 - New Party.mp4"
EVENT = "2024-06-21 - New Party"


def _renamed(root: Path, *, old_sidecar: bool = True) -> tuple[Path, Path]:
    event_dir = _event(root, EVENT)
    _record(event_dir, OLD, NEW, poster="2024-06-21 - New Party-poster.jpg")
    output = default_output_dir(root) / "2024"
    _touch(output / OLD, b"old")
    _touch(output / NEW, b"new")
    _touch(output / "2024-06-21 - New Party-poster.jpg", b"new poster")
    if old_sidecar:
        _touch(output / OLD_SIDECAR, b"old poster")
    return event_dir, output


def test_dry_run_lists_the_sidecar_with_its_movie_and_deletes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "proj"
    _, output = _renamed(root)
    assert main(["prune-renamed", str(root)]) == 0
    assert "+ poster" in capsys.readouterr().out
    assert (output / OLD).exists() and (output / OLD_SIDECAR).exists()


def test_yes_deletes_the_superseded_movie_and_its_sidecar_only(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    _, output = _renamed(root)
    assert main(["prune-renamed", str(root), "--yes"]) == 0
    assert not (output / OLD).exists() and not (output / OLD_SIDECAR).exists()
    assert (output / NEW).exists() and (output / "2024-06-21 - New Party-poster.jpg").exists()


def test_a_sidecar_without_its_movie_is_not_listed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "proj"
    _, output = _renamed(root)
    (output / OLD).unlink()
    assert main(["prune-renamed", str(root), "--yes"]) == 0
    assert "No superseded movies found." in capsys.readouterr().out
    assert (output / OLD_SIDECAR).exists()


def test_a_movie_without_a_sidecar_is_pruned_alone(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    _, output = _renamed(root, old_sidecar=False)
    assert main(["prune-renamed", str(root), "--yes"]) == 0
    assert not (output / OLD).exists()


def test_a_sidecar_another_event_records_is_kept(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    _, output = _renamed(root)
    other = _event(root, "2024-06-22 - Other")
    _record(other, "2024-06-22 - Other.mp4", poster=OLD_SIDECAR)
    assert main(["prune-renamed", str(root), "--yes"]) == 0
    assert not (output / OLD).exists()
    assert (output / OLD_SIDECAR).read_bytes() == b"old poster"
