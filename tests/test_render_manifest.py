"""Tests for the engine's manifest write on success (task 2.1): only after the atomic
finalize, never on skip/dry-run/failure/no-fingerprint."""

from __future__ import annotations

import json
import subprocess
from datetime import date
from pathlib import Path
from typing import Optional

import pytest

from auto_reel_ng.accel.profiles import CPUProfile
from auto_reel_ng.errors import RenderError
from auto_reel_ng.event.plan import RenderPlan, ResolvedChapter, ResolvedClip
from auto_reel_ng.probe import probe_media
from auto_reel_ng.reel.document import Metadata, ReelDocument, Trim
from auto_reel_ng.render import RenderOptions
from auto_reel_ng.render import orchestrator as orch
from auto_reel_ng.render import render_movie
from auto_reel_ng.staleness.fingerprint import compute_fingerprint
from auto_reel_ng.staleness.gate import evaluate
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


def test_a_title_with_a_separator_renders_one_file_the_gate_finds(
    runtime, make_clip, tmp_path: Path
) -> None:
    """The recorded name and the movie agree for a title with a path separator (D-9)."""
    clip_a = make_clip("a.mp4", width=320, height=240, fps=30, duration=1.0)
    facts = {"a.mp4": probe_media(clip_a, runtime=runtime)}
    metadata = Metadata(title="Mid/sommar", date=date(2024, 6, 21))
    document = ReelDocument(metadata=metadata)
    fingerprint = compute_fingerprint(
        document, event_dir=tmp_path, look_defaults={}, ffmpeg_version=runtime.version
    )
    plan = RenderPlan(
        metadata=metadata,
        look={"target_resolution": [320, 240]},
        chapters=(ResolvedChapter(name="", clips=(ResolvedClip(identity="a.mp4"),)),),
    )
    out = tmp_path / "out"
    options = RenderOptions(
        event_dir=tmp_path,
        output_dir=out,
        clip_facts=facts,
        runtime=runtime,
        fingerprint=fingerprint,
    )

    result = render_movie(plan, CPUProfile(), options)

    manifest = read_manifest(tmp_path)
    assert manifest is not None
    assert manifest.output == result.output_path.name
    assert result.output_path.parent == out / "2024"
    assert sorted(path.name for path in out.rglob("*") if path.is_file()) == [manifest.output]
    assert evaluate(tmp_path, result.output_path, fingerprint).reasons == ()


# --- chapter times (change render-chapter-times) -----------------------------------------------


def _ffprobe_json(runtime, path: Path, *args: str) -> dict:
    out = subprocess.run(
        [runtime.ffprobe_path, "-v", "error", "-print_format", "json", *args, str(path)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return json.loads(out)


def _movie_chapters(runtime, movie: Path) -> list[tuple[str, int, int]]:
    """``(title, start_ms, end_ms)`` per ``[CHAPTER]`` marker, read back from the finished movie."""
    chapters = _ffprobe_json(runtime, movie, "-show_chapters")["chapters"]
    assert all(c["time_base"] == "1/1000" for c in chapters)
    return [(c["tags"]["title"], int(c["start"]), int(c["end"])) for c in chapters]


def _two_chapter_plan(*, trim_first: bool, copy_audio: bool = False) -> RenderPlan:
    cuts = (Trim(start=1.0, end=1.5),) if trim_first else ()
    look: dict[str, object] = {"target_resolution": [320, 240]}
    if copy_audio:
        # make_clip's audio (44.1 kHz mono AAC), so uniform clips match the target and are copied.
        look.update(audio_sample_rate=44100, audio_channels=1)
    return RenderPlan(
        metadata=Metadata(title="Movie"),
        look=look,
        chapters=(
            ResolvedChapter(name="One", clips=(ResolvedClip(identity="a.mp4", cut_spans=cuts),)),
            ResolvedChapter(name="Two", clips=(ResolvedClip(identity="b.mp4"),)),
        ),
    )


def _render_two_chapters(
    runtime,
    make_clip,
    event_dir: Path,
    *,
    trim_first: bool,
    mixed: bool,
    copy_audio: bool = False,
    output_dir: Optional[Path] = None,
):
    clip_a = make_clip("a.mp4", width=320, height=240, fps=30, duration=2.0)
    clip_b = make_clip(
        "b.mp4", width=160 if mixed else 320, height=120 if mixed else 240, fps=30, duration=2.0
    )
    facts = {
        "a.mp4": probe_media(clip_a, runtime=runtime),
        "b.mp4": probe_media(clip_b, runtime=runtime),
    }
    fingerprint = _fingerprint(event_dir, runtime)
    options = RenderOptions(
        event_dir=event_dir,
        output_dir=output_dir or event_dir / "out",
        clip_facts=facts,
        runtime=runtime,
        fingerprint=fingerprint,
    )
    plan = _two_chapter_plan(trim_first=trim_first, copy_audio=copy_audio)
    return render_movie(plan, CPUProfile(), options), fingerprint, options, plan


@pytest.mark.parametrize(
    ("trim_first", "mixed", "copied"),
    [(True, False, False), (False, False, True), (False, True, False)],
    ids=["trimmed", "uniform-copy", "mixed-reencoded"],
)
def test_recorded_chapter_times_equal_the_movies_chapter_markers(
    runtime,
    make_clip,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    trim_first: bool,
    mixed: bool,
    copied: bool,
) -> None:
    joined: list[list[Path]] = []
    real_uniform = orch.is_copy_uniform

    def _spy(rt, intermediates):  # type: ignore[no-untyped-def]
        joined.append([Path(p) for p in intermediates])
        return real_uniform(rt, intermediates)

    monkeypatch.setattr(orch, "is_copy_uniform", _spy)
    result, _fp, _options, _plan_ = _render_two_chapters(
        runtime, make_clip, tmp_path, trim_first=trim_first, mixed=mixed, copy_audio=copied
    )

    # The uniform set is joined by stream copy (the source files themselves), the others re-encoded.
    assert all(p.parent == tmp_path for p in joined[0]) is copied
    manifest = read_manifest(tmp_path)
    assert manifest is not None and manifest.chapters is not None
    markers = _movie_chapters(runtime, result.output_path)
    assert [(c.name, c.start_ms, c.end_ms) for c in manifest.chapters] == markers
    assert [c.title_card for c in manifest.chapters] == [None, None]
    first, second = manifest.chapters
    assert first.start_ms == 0 and second.start_ms == first.end_ms
    # The numbers are measured, not the plan's: the first chapter is ~1.5 s trimmed, ~2 s otherwise.
    assert first.end_ms == pytest.approx(1500 if trim_first else 2000, abs=100)
    movie = _ffprobe_json(runtime, result.output_path, "-show_format")["format"]
    assert second.end_ms / 1000 == pytest.approx(float(movie["duration"]), abs=1 / 30)


def test_the_trimmed_chapter_is_shorter_than_its_clip(runtime, make_clip, tmp_path: Path) -> None:
    _render_two_chapters(runtime, make_clip, tmp_path, trim_first=True, mixed=False)

    manifest = read_manifest(tmp_path)
    assert manifest is not None and manifest.chapters is not None
    assert manifest.chapters[0].end_ms < 1800


def test_chapter_times_are_not_a_fingerprint_input(
    runtime, make_clip, tmp_path: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    result, fingerprint, _options, _plan_ = _render_two_chapters(
        runtime,
        make_clip,
        tmp_path,
        trim_first=True,
        mixed=False,
        output_dir=tmp_path_factory.mktemp("movies"),  # outside the event: it is not a clip
    )

    manifest = read_manifest(tmp_path)
    assert manifest is not None and manifest.chapters is not None
    assert manifest.fingerprint == fingerprint.combined
    recomputed = _fingerprint(tmp_path, runtime)
    assert recomputed.combined == fingerprint.combined
    assert evaluate(tmp_path, result.output_path, recomputed).reasons == ()


@pytest.mark.parametrize(
    "failing_step", ["is_copy_uniform", "verify_output"], ids=["before-concat", "after-concat"]
)
def test_a_skipped_dry_run_and_failed_render_keep_the_previous_chapter_times(
    runtime, make_clip, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failing_step: str
) -> None:
    result, fingerprint, options, plan = _render_two_chapters(
        runtime, make_clip, tmp_path, trim_first=True, mixed=False
    )
    before = read_manifest(tmp_path)
    assert before is not None and before.chapters is not None
    raw = (tmp_path / ".auto-reel" / "cache" / "render-manifest.json").read_bytes()
    movie_bytes = result.output_path.read_bytes()

    assert render_movie(plan, CPUProfile(), options).skipped is True
    dry = RenderOptions(**{**vars(options), "overwrite": True, "dry_run": True})
    assert render_movie(plan, CPUProfile(), dry).dry_run is True

    def _boom(*_a: object, **_k: object) -> bool:
        raise RenderError("forced failure")

    # verify_output runs on the .part after the concat, just before the movie is finalized.
    monkeypatch.setattr(orch, failing_step, _boom)
    failing = RenderOptions(**{**vars(options), "overwrite": True})
    with pytest.raises(RenderError):
        render_movie(plan, CPUProfile(), failing)

    assert (tmp_path / ".auto-reel" / "cache" / "render-manifest.json").read_bytes() == raw
    assert read_manifest(tmp_path) == before
    assert result.output_path.read_bytes() == movie_bytes
    assert evaluate(tmp_path, result.output_path, fingerprint).reasons == ()


def test_a_re_render_replaces_the_chapter_times(runtime, make_clip, tmp_path: Path) -> None:
    _result, _fp, options, plan = _render_two_chapters(
        runtime, make_clip, tmp_path, trim_first=False, mixed=False
    )
    first = read_manifest(tmp_path)
    assert first is not None and first.chapters is not None and len(first.chapters) == 2

    one_chapter = RenderPlan(metadata=plan.metadata, look=plan.look, chapters=(plan.chapters[0],))
    render_movie(one_chapter, CPUProfile(), RenderOptions(**{**vars(options), "overwrite": True}))

    second = read_manifest(tmp_path)
    assert second is not None and second.chapters is not None
    assert [c.name for c in second.chapters] == ["One"]
