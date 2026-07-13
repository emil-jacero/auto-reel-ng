"""Tests for the staleness gate: fresh, each stale arm, reasons, MISSING clip (task 1.3)."""

from __future__ import annotations

from pathlib import Path

from auto_reel_ng.reel.document import Chapter, ClipRef, Metadata, ReelDocument
from auto_reel_ng.staleness.fingerprint import compute_fingerprint, engine_identity
from auto_reel_ng.staleness.gate import MISSING_OUTPUT, NO_MANIFEST, evaluate
from auto_reel_ng.staleness.manifest import write_manifest

FFMPEG_VERSION = (7, 1)


def _document(title: str = "Party", clips: tuple[str, ...] = ("clip.mp4",)) -> ReelDocument:
    return ReelDocument(
        metadata=Metadata(title=title),
        chapters=(Chapter(name="", clips=tuple(ClipRef(c) for c in clips)),),
    )


def _fingerprint(event_dir: Path, **overrides: object):
    document = overrides.pop("document", None) or _document()
    look_defaults = overrides.pop("look_defaults", {})
    ffmpeg_version = overrides.pop("ffmpeg_version", FFMPEG_VERSION)
    return compute_fingerprint(
        document, event_dir=event_dir, look_defaults=look_defaults, ffmpeg_version=ffmpeg_version
    )


def _render(event_dir: Path, fingerprint, *, output_name: str = "Party.mp4") -> Path:
    write_manifest(
        event_dir, fingerprint, output=output_name, engine_identity=engine_identity(FFMPEG_VERSION)
    )
    output_path = event_dir / output_name
    output_path.write_bytes(b"rendered")
    return output_path


def _setup(tmp_path: Path, *, content: bytes = b"clip-bytes") -> Path:
    (tmp_path / "clip.mp4").write_bytes(content)
    return tmp_path


def test_fresh_event_has_no_reasons(tmp_path: Path) -> None:
    event_dir = _setup(tmp_path)
    fingerprint = _fingerprint(event_dir)
    output_path = _render(event_dir, fingerprint)

    verdict = evaluate(event_dir, output_path, fingerprint)

    assert verdict.stale is False
    assert verdict.reasons == ()


def test_no_manifest_is_stale(tmp_path: Path) -> None:
    event_dir = _setup(tmp_path)
    fingerprint = _fingerprint(event_dir)

    verdict = evaluate(event_dir, event_dir / "Party.mp4", fingerprint)

    assert verdict.stale is True
    assert verdict.reasons == (NO_MANIFEST,)


def test_missing_output_is_always_stale(tmp_path: Path) -> None:
    event_dir = _setup(tmp_path)
    fingerprint = _fingerprint(event_dir)
    output_path = _render(event_dir, fingerprint)
    output_path.unlink()

    verdict = evaluate(event_dir, output_path, fingerprint)

    assert verdict.stale is True
    assert MISSING_OUTPUT in verdict.reasons


def test_reasons_name_exactly_the_changed_components(tmp_path: Path) -> None:
    event_dir = _setup(tmp_path)
    baseline = _fingerprint(event_dir)
    output_path = _render(event_dir, baseline)

    # A clip changes, and the editorial document changes; defaults/engine do not.
    (event_dir / "clip.mp4").write_bytes(b"replaced content, different size")
    changed_fp = _fingerprint(event_dir, document=_document(title="Renamed Party"))

    verdict = evaluate(event_dir, output_path, changed_fp)

    assert verdict.stale is True
    assert set(verdict.reasons) == {"editorial", "clip_set"}


def test_missing_referenced_clip_is_stale_via_clip_set(tmp_path: Path) -> None:
    event_dir = _setup(tmp_path)
    baseline = _fingerprint(event_dir)
    output_path = _render(event_dir, baseline)

    (event_dir / "clip.mp4").unlink()
    changed_fp = _fingerprint(event_dir)

    verdict = evaluate(event_dir, output_path, changed_fp)

    assert verdict.stale is True
    assert "clip_set" in verdict.reasons
