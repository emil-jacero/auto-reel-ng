"""Golden tests for the render fingerprint: stability, sensitivity, device/host
independence, and no-ffprobe (task 1.1)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from auto_reel_ng.reel.document import Chapter, ClipRef, Metadata, ReelDocument
from auto_reel_ng.staleness.fingerprint import COMPONENTS, compute_fingerprint

FFMPEG_VERSION = (7, 1)


def _document(title: str = "Party") -> ReelDocument:
    return ReelDocument(
        metadata=Metadata(title=title),
        chapters=(Chapter(name="", clips=(ClipRef("clip.mp4"),)),),
    )


def _event_dir(tmp_path: Path, *, content: bytes = b"clip-bytes") -> Path:
    (tmp_path / "clip.mp4").write_bytes(content)
    return tmp_path


def _fingerprint(
    event_dir: Path, *, document=None, look_defaults=None, ffmpeg_version=FFMPEG_VERSION
):
    return compute_fingerprint(
        document if document is not None else _document(),
        event_dir=event_dir,
        look_defaults=look_defaults if look_defaults is not None else {},
        ffmpeg_version=ffmpeg_version,
    )


def test_unchanged_event_is_fingerprint_stable(tmp_path: Path) -> None:
    event_dir = _event_dir(tmp_path)
    first = _fingerprint(event_dir)
    second = _fingerprint(event_dir)
    assert first == second
    assert first.combined == second.combined


def test_editorial_change_moves_only_editorial(tmp_path: Path) -> None:
    event_dir = _event_dir(tmp_path)
    baseline = _fingerprint(event_dir)
    changed = _fingerprint(event_dir, document=_document(title="Different Party"))

    assert changed.editorial != baseline.editorial
    assert changed.combined != baseline.combined
    for name in ("defaults", "clip_set", "engine"):
        assert changed.component(name) == baseline.component(name)


def test_defaults_change_moves_only_defaults(tmp_path: Path) -> None:
    event_dir = _event_dir(tmp_path)
    baseline = _fingerprint(event_dir)
    changed = _fingerprint(event_dir, look_defaults={"transitions": "fade"})

    assert changed.defaults != baseline.defaults
    assert changed.combined != baseline.combined
    for name in ("editorial", "clip_set", "engine"):
        assert changed.component(name) == baseline.component(name)


def test_clip_signal_change_moves_only_clip_set(tmp_path: Path) -> None:
    event_dir = _event_dir(tmp_path, content=b"short")
    baseline = _fingerprint(event_dir)

    (event_dir / "clip.mp4").write_bytes(b"a much longer replacement clip")
    changed = _fingerprint(event_dir)

    assert changed.clip_set != baseline.clip_set
    assert changed.combined != baseline.combined
    for name in ("editorial", "defaults", "engine"):
        assert changed.component(name) == baseline.component(name)


def test_engine_version_bump_moves_only_engine(tmp_path: Path) -> None:
    event_dir = _event_dir(tmp_path)
    baseline = _fingerprint(event_dir)
    changed = _fingerprint(event_dir, ffmpeg_version=(8, 0))

    assert changed.engine != baseline.engine
    assert changed.combined != baseline.combined
    for name in ("editorial", "defaults", "clip_set"):
        assert changed.component(name) == baseline.component(name)


def test_device_selection_does_not_move_the_fingerprint(tmp_path: Path) -> None:
    # The fingerprint never takes a profile/device argument at all, so a caller
    # rendering under CPU vs GPU necessarily computes the same value (D-C1).
    event_dir = _event_dir(tmp_path)
    cpu_run = _fingerprint(event_dir)
    gpu_run = _fingerprint(event_dir)
    assert cpu_run.combined == gpu_run.combined


def test_all_components_are_covered() -> None:
    assert set(COMPONENTS) == {"editorial", "defaults", "clip_set", "engine"}


def test_no_probing_occurs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    event_dir = _event_dir(tmp_path)

    def _forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("compute_fingerprint must not shell out to ffmpeg/ffprobe")

    monkeypatch.setattr(subprocess, "run", _forbidden)
    monkeypatch.setattr(subprocess, "Popen", _forbidden)

    _fingerprint(event_dir)  # must not raise
