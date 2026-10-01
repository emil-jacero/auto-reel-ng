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
    manifest_path,
    read_manifest,
    recorded_output_path,
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
