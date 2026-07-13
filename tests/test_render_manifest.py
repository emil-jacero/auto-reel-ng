"""Tests for the engine's manifest write on success (task 2.1): only after the atomic
finalize, never on skip/dry-run/failure/no-fingerprint."""

from __future__ import annotations

from pathlib import Path

import pytest

from auto_reel_ng.accel.profiles import CPUProfile
from auto_reel_ng.errors import RenderError
from auto_reel_ng.event.plan import RenderPlan, ResolvedChapter, ResolvedClip
from auto_reel_ng.probe import probe_media
from auto_reel_ng.reel.document import Metadata, ReelDocument
from auto_reel_ng.render import RenderOptions
from auto_reel_ng.render import orchestrator as orch
from auto_reel_ng.render import render_movie
from auto_reel_ng.staleness.fingerprint import compute_fingerprint
from auto_reel_ng.staleness.manifest import read_manifest


def _plan() -> RenderPlan:
    return RenderPlan(
        metadata=Metadata(title="Movie"),
        look={"target_resolution": [320, 240]},
        chapters=(ResolvedChapter(name="", clips=(ResolvedClip(identity="a.mp4"),)),),
    )


def _fingerprint(event_dir: Path, runtime):
    return compute_fingerprint(
        ReelDocument(metadata=Metadata(title="Movie")),
        event_dir=event_dir,
        look_defaults={},
        ffmpeg_version=runtime.version,
    )


def test_success_writes_the_manifest_after_finalization(runtime, make_clip, tmp_path: Path) -> None:
    clip_a = make_clip("a.mp4", width=320, height=240, fps=30, duration=1.0)
    facts = {"a.mp4": probe_media(clip_a, runtime=runtime)}
    fingerprint = _fingerprint(tmp_path, runtime)
    options = RenderOptions(
        event_dir=tmp_path,
        output_dir=tmp_path / "out",
        clip_facts=facts,
        runtime=runtime,
        fingerprint=fingerprint,
    )

    result = render_movie(_plan(), CPUProfile(), options)

    manifest = read_manifest(tmp_path)
    assert manifest is not None
    assert manifest.fingerprint == fingerprint.combined
    assert manifest.output == result.output_path.name


def test_skip_does_not_touch_the_manifest(runtime, make_clip, tmp_path: Path) -> None:
    clip_a = make_clip("a.mp4", width=320, height=240)
    facts = {"a.mp4": probe_media(clip_a, runtime=runtime)}
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    (out_dir / "Movie.mp4").write_text("untouched")
    fingerprint = _fingerprint(tmp_path, runtime)
    options = RenderOptions(
        event_dir=tmp_path,
        output_dir=out_dir,
        clip_facts=facts,
        runtime=runtime,
        fingerprint=fingerprint,
    )

    result = render_movie(_plan(), CPUProfile(), options)

    assert result.skipped is True
    assert read_manifest(tmp_path) is None


def test_dry_run_does_not_write_a_manifest(runtime, make_clip, tmp_path: Path) -> None:
    clip_a = make_clip("a.mp4", width=320, height=240)
    facts = {"a.mp4": probe_media(clip_a, runtime=runtime)}
    fingerprint = _fingerprint(tmp_path, runtime)
    options = RenderOptions(
        event_dir=tmp_path,
        output_dir=tmp_path / "out",
        clip_facts=facts,
        runtime=runtime,
        dry_run=True,
        fingerprint=fingerprint,
    )

    result = render_movie(_plan(), CPUProfile(), options)

    assert result.dry_run is True
    assert read_manifest(tmp_path) is None


def test_failure_leaves_no_manifest(
    runtime, make_clip, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clip_a = make_clip("a.mp4", width=320, height=240)
    facts = {"a.mp4": probe_media(clip_a, runtime=runtime)}
    fingerprint = _fingerprint(tmp_path, runtime)
    options = RenderOptions(
        event_dir=tmp_path,
        output_dir=tmp_path / "out",
        clip_facts=facts,
        runtime=runtime,
        fingerprint=fingerprint,
    )

    def _boom(*_a: object, **_k: object) -> bool:
        raise RenderError("forced failure")

    monkeypatch.setattr(orch, "is_copy_uniform", _boom)

    with pytest.raises(RenderError):
        render_movie(_plan(), CPUProfile(), options)

    assert read_manifest(tmp_path) is None


def test_no_fingerprint_writes_no_manifest(runtime, make_clip, tmp_path: Path) -> None:
    clip_a = make_clip("a.mp4", width=320, height=240)
    facts = {"a.mp4": probe_media(clip_a, runtime=runtime)}
    options = RenderOptions(
        event_dir=tmp_path, output_dir=tmp_path / "out", clip_facts=facts, runtime=runtime
    )

    result = render_movie(_plan(), CPUProfile(), options)

    assert result.output_path.exists()
    assert read_manifest(tmp_path) is None
