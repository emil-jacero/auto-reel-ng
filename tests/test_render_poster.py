"""Tests for the event poster frame: resolution, extraction, the cover, and the atomic finalize.

Pure tests (argument strings, resolution) need no ffmpeg; the rest render real clips and measure
the pictures (red then blue, so which frame was taken is unambiguous).
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import replace
from pathlib import Path
from typing import Optional

import pytest

from auto_reel_ng.accel.profiles import CPUProfile
from auto_reel_ng.errors import PosterFrameError, RenderVerificationError
from auto_reel_ng.event.plan import RenderPlan, ResolvedChapter, ResolvedClip
from auto_reel_ng.ffmpeg.runtime import FfmpegRuntime
from auto_reel_ng.probe import probe_media
from auto_reel_ng.probe.metadata import ClipMetadata
from auto_reel_ng.reel.document import Metadata, Poster, ReelDocument, Trim
from auto_reel_ng.render import RenderOptions
from auto_reel_ng.render import orchestrator as orch
from auto_reel_ng.render import render_movie
from auto_reel_ng.render.poster import (
    PosterChoice,
    cover_part_path,
    embed_cover,
    embed_cover_args,
    extract_poster,
    poster_args,
    poster_part_path,
    poster_path,
    resolve_poster,
    verify_poster,
)
from auto_reel_ng.render.target import TargetSpec
from auto_reel_ng.render.verify import verify_output
from auto_reel_ng.staleness.fingerprint import compute_fingerprint
from auto_reel_ng.staleness.gate import evaluate
from auto_reel_ng.staleness.manifest import manifest_path, read_manifest, write_manifest

TARGET = TargetSpec(
    width=320,
    height=240,
    fps=10,
    video_codec="h264",
    video_encoder="libx264",
    pix_fmt="yuv420p",
    sample_aspect_ratio="1:1",
    fill_color="black",
    audio_codec="aac",
    audio_sample_rate=48000,
    audio_channels=2,
)


def _facts(
    name: str = "a.mp4",
    *,
    duration: float = 40.0,
    rotation: Optional[int] = None,
    sar: Optional[str] = "1:1",
    hdr: bool = False,
) -> ClipMetadata:
    return ClipMetadata(
        path=Path("/lib") / name,
        duration=duration,
        fps=10,
        video_codec="h264",
        profile=None,
        width=320,
        height=240,
        sample_aspect_ratio=sar,
        display_aspect_ratio=None,
        pix_fmt="yuv420p",
        video_bitrate=None,
        rotation=rotation,
        color_transfer="smpte2084" if hdr else None,
        is_hdr=hdr,
        audio=None,
        creation_time=None,
    )


def _plan(*clips: ResolvedClip, poster: Optional[Poster] = None, unplayed: str | None = None):
    return RenderPlan(
        metadata=Metadata(title="Movie"),
        look={"target_resolution": [320, 240]},
        chapters=(ResolvedChapter(name="", clips=clips),),
        poster=poster,
        poster_unplayed=unplayed,
    )


# -- resolution ------------------------------------------------------------- #


def test_the_default_is_the_first_played_clip_at_the_thumbnail_position() -> None:
    plan = _plan(ResolvedClip("a.mp4"), ResolvedClip("b.mp4"))
    facts = {"a.mp4": _facts("a.mp4", duration=40.0), "b.mp4": _facts("b.mp4")}
    choice, warnings = resolve_poster(plan, facts)
    assert choice == PosterChoice("a.mp4", 10.0, None, "default")
    assert warnings == ()


def test_the_default_follows_the_configured_thumbnail_position() -> None:
    plan = _plan(ResolvedClip("a.mp4"))
    choice, _ = resolve_poster(plan, {"a.mp4": _facts("a.mp4", duration=40.0)}, position=0.5)
    assert choice == PosterChoice("a.mp4", 20.0, None, "default")


def test_an_explicit_poster_is_taken_from_the_original_clip_before_trims() -> None:
    clip = ResolvedClip("b.mp4", cut_spans=(Trim(0.0, 20.0),), rotate=90)
    plan = _plan(ResolvedClip("a.mp4"), clip, poster=Poster("b.mp4", 30.0))
    facts = {"a.mp4": _facts("a.mp4"), "b.mp4": _facts("b.mp4")}
    choice, warnings = resolve_poster(plan, facts)
    assert choice == PosterChoice("b.mp4", 30.0, 90, "explicit")
    assert warnings == ()


@pytest.mark.parametrize("reason", ["ignored", "excluded", "missing"])
def test_an_unplayed_poster_clip_falls_back_with_one_warning(
    reason: str, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    # an Alembic ``fileConfig`` run by an earlier test disables every logger that already exists
    monkeypatch.setattr(logging.getLogger("auto_reel_ng.render.poster"), "disabled", False)
    plan = _plan(ResolvedClip("a.mp4"), poster=Poster("gone.mp4", 3.0), unplayed=reason)
    with caplog.at_level(logging.WARNING, logger="auto_reel_ng.render.poster"):
        choice, warnings = resolve_poster(plan, {"a.mp4": _facts()})
    assert choice == PosterChoice("a.mp4", 10.0, None, "default")
    assert len(warnings) == 1 and "gone.mp4" in warnings[0] and reason in warnings[0]
    assert any("gone.mp4" in record.message for record in caplog.records)


def test_a_time_past_the_end_is_a_typed_error_naming_clip_time_and_duration() -> None:
    plan = _plan(ResolvedClip("a.mp4"), poster=Poster("a.mp4", 90.0))
    with pytest.raises(PosterFrameError) as caught:
        resolve_poster(plan, {"a.mp4": _facts(duration=40.0)})
    message = str(caught.value)
    assert "a.mp4" in message and "90" in message and "40" in message


def test_a_time_equal_to_the_duration_is_past_the_end() -> None:
    plan = _plan(ResolvedClip("a.mp4"), poster=Poster("a.mp4", 40.0))
    with pytest.raises(PosterFrameError):
        resolve_poster(plan, {"a.mp4": _facts(duration=40.0)})


def test_no_played_clip_means_no_poster() -> None:
    assert resolve_poster(_plan(), {}) == (None, ())


# -- arguments (golden) ----------------------------------------------------- #

OUT = Path("/out/p.part")


def _vf(args: list[str]) -> str:
    return args[args.index("-vf") + 1]


def test_plain_clip_arguments() -> None:
    choice = PosterChoice("a.mp4", 10.0, None, "default")
    args = poster_args(_facts(), choice, target=TARGET, output=OUT)
    assert args == [
        "-hide_banner", "-nostdin", "-v", "error", "-noautorotate",
        "-ss", "10.000", "-i", "/lib/a.mp4", "-map", "0:v:0", "-an", "-sn",
        "-frames:v", "1",
        "-vf",
        "scale=trunc(iw*sar/2)*2:ih,scale=320:240:force_original_aspect_ratio=decrease,"
        "pad=320:240:(ow-iw)/2:(oh-ih)/2:black,setsar=1",
        "-c:v", "mjpeg", "-q:v", "2", "-f", "image2", "-update", "1", "-y", "/out/p.part",
    ]  # fmt: skip


def test_a_display_rotated_clip_with_rotate_uses_the_renderer_turn() -> None:
    # probe rotation 90 = a clockwise turn of 270 (transpose=2); rotate 90 adds a quarter: none
    both = poster_args(
        _facts(rotation=90), PosterChoice("a.mp4", 1.0, 90, "explicit"), target=TARGET, output=OUT
    )
    assert "transpose" not in _vf(both)
    display_only = poster_args(
        _facts(rotation=90), PosterChoice("a.mp4", 1.0, None, "explicit"), target=TARGET, output=OUT
    )
    assert _vf(display_only).startswith("transpose=2,scale=")
    extra = poster_args(
        _facts(rotation=None),
        PosterChoice("a.mp4", 1.0, 180, "explicit"),
        target=TARGET,
        output=OUT,
    )
    assert _vf(extra).startswith("transpose=1,transpose=1,scale=")


def test_an_hdr_clip_is_tone_mapped_before_anything_else() -> None:
    args = poster_args(
        _facts(hdr=True), PosterChoice("a.mp4", 1.0, None, "default"), target=TARGET, output=OUT
    )
    assert _vf(args).startswith("zscale=t=linear:npl=100,tonemap=hable,")


def test_the_cover_is_embedded_by_a_stream_copy() -> None:
    args = embed_cover_args(Path("m.part"), Path("p.jpg.part"), Path("m.cover.part"))
    assert "-c" in args and args[args.index("-c") + 1] == "copy"
    assert args[args.index("-disposition:v:1") + 1] == "attached_pic"
    assert args[args.index("-map_chapters") + 1] == "0"
    assert args[args.index("-map_metadata") + 1] == "0"
    assert args[-3:] == ("-f", "mp4", "m.cover.part")


def test_the_sidecar_names_follow_the_movie() -> None:
    movie = Path("/o/2024/2024-06-27 - Grillkväll.mp4")
    assert poster_path(movie) == Path("/o/2024/2024-06-27 - Grillkväll-poster.jpg")
    assert poster_part_path(movie).name == "2024-06-27 - Grillkväll-poster.jpg.part"
    assert cover_part_path(movie).name == "2024-06-27 - Grillkväll.mp4.cover.part"


# -- real ffmpeg ------------------------------------------------------------ #

ffmpeg = pytest.mark.has_ffmpeg


def _signal(runtime: FfmpegRuntime, image: Path, key: str, crop: str = "iw:ih:0:0") -> float:
    result = runtime.run(
        ["-i", str(image), "-frames:v", "1"]
        + ["-vf", f"crop={crop},signalstats,metadata=mode=print:file=-", "-f", "null", "-"]
    )
    match = re.search(rf"lavfi\.signalstats\.{key}=([0-9.]+)", result.stdout)
    assert match, result.stdout
    return float(match.group(1))


RED_U, BLUE_U = 90, 240


def _is_blue(runtime: FfmpegRuntime, image: Path) -> bool:
    u = _signal(runtime, image, "UAVG")
    assert abs(u - BLUE_U) < 40 or abs(u - RED_U) < 40, u
    return abs(u - BLUE_U) < 40


@pytest.fixture
def red_blue(runtime: FfmpegRuntime, tmp_path: Path) -> Path:
    """8 s, 10 fps, 320x240 with audio: red for 3 s, then blue."""
    clip = tmp_path / "a.mp4"
    runtime.run(
        ["-y", "-f", "lavfi", "-i", "color=red:s=320x240:r=10:d=3"]
        + ["-f", "lavfi", "-i", "color=blue:s=320x240:r=10:d=5"]
        + ["-f", "lavfi", "-i", "sine=frequency=440:duration=8"]
        + ["-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0,format=yuv420p[v]"]
        + ["-map", "[v]", "-map", "2:a", "-c:v", "libx264", "-c:a", "aac", str(clip)]
    )
    return clip


def _render(
    runtime: FfmpegRuntime,
    clip: Path,
    out: Path,
    *,
    poster: Optional[Poster] = None,
    unplayed: str | None = None,
    cut: tuple[Trim, ...] = (),
    overwrite: bool = False,
    fingerprint: bool = False,
    poster_position: float = 0.25,
):
    plan = _plan(ResolvedClip(clip.name, cut_spans=cut), poster=poster, unplayed=unplayed)
    plan = replace(plan, metadata=Metadata(title="Movie"))
    fp = None
    if fingerprint:
        fp = compute_fingerprint(
            ReelDocument(metadata=Metadata(title="Movie")),
            event_dir=clip.parent,
            look_defaults={},
            ffmpeg_version=runtime.version,
        )
    options = RenderOptions(
        event_dir=clip.parent,
        output_dir=out,
        clip_facts={clip.name: probe_media(clip, runtime=runtime)},
        runtime=runtime,
        overwrite=overwrite,
        fingerprint=fp,
        poster_position=poster_position,
    )
    return render_movie(plan, CPUProfile(), options)


def _streams(runtime: FfmpegRuntime, movie: Path) -> list[dict]:
    result = runtime.run_ffprobe(
        [
            "-v",
            "error",
            "-show_entries",
            "stream=codec_type,codec_name:stream_disposition=attached_pic",
        ]
        + ["-print_format", "json", str(movie)]
    )
    return json.loads(result.stdout)["streams"]


def _no_leftovers(out: Path) -> bool:
    return not [p for p in out.rglob("*") if p.name.endswith(".part")]


@ffmpeg
def test_a_default_render_writes_the_sidecar_and_one_cover(
    runtime: FfmpegRuntime, red_blue: Path, tmp_path: Path
) -> None:
    result = _render(runtime, red_blue, tmp_path / "out", fingerprint=True)

    sidecar = result.poster_path
    assert sidecar is not None and sidecar == poster_path(result.output_path)
    assert sidecar.name == "Movie-poster.jpg" and sidecar.is_file()
    verify_poster(runtime, sidecar, TARGET)
    assert not _is_blue(runtime, sidecar)  # 25% of 8 s = 2 s: still red
    covers = [s for s in _streams(runtime, result.output_path) if s["disposition"]["attached_pic"]]
    assert [c["codec_name"] for c in covers] == ["mjpeg"]
    manifest = read_manifest(red_blue.parent)
    assert manifest is not None and manifest.poster == sidecar.name
    assert _no_leftovers(tmp_path / "out")


@ffmpeg
def test_an_explicit_poster_is_the_original_clips_frame_not_the_cuts(
    runtime: FfmpegRuntime, red_blue: Path, tmp_path: Path
) -> None:
    # t=1 s is red in the original; the cut removes 0-2 s, so a cut-relative 1 s would be 3 s: blue
    result = _render(
        runtime, red_blue, tmp_path / "out", poster=Poster("a.mp4", 1.0), cut=(Trim(0.0, 2.0),)
    )
    assert result.poster_path is not None
    assert not _is_blue(runtime, result.poster_path)
    late = _render(
        runtime, red_blue, tmp_path / "late", poster=Poster("a.mp4", 6.0), cut=(Trim(0.0, 2.0),)
    )
    assert late.poster_path is not None and _is_blue(runtime, late.poster_path)


@ffmpeg
def test_a_fallback_poster_renders_with_a_warning(
    runtime: FfmpegRuntime, red_blue: Path, tmp_path: Path
) -> None:
    result = _render(
        runtime, red_blue, tmp_path / "out", poster=Poster("gone.mp4", 6.0), unplayed="ignored"
    )
    assert any("gone.mp4" in w and "ignored" in w for w in result.warnings)
    assert result.poster_path is not None and not _is_blue(runtime, result.poster_path)


@ffmpeg
def test_a_time_past_the_end_fails_before_anything_is_written(
    runtime: FfmpegRuntime, red_blue: Path, tmp_path: Path
) -> None:
    out = tmp_path / "out"
    with pytest.raises(PosterFrameError, match=r"a\.mp4.*90.*8"):
        _render(runtime, red_blue, out, poster=Poster("a.mp4", 90.0), fingerprint=True)
    assert not out.exists() or not list(out.rglob("*"))
    assert not manifest_path(red_blue.parent).exists()


@ffmpeg
def test_a_render_takes_the_default_frame_at_the_configured_position(
    runtime: FfmpegRuntime, red_blue: Path, tmp_path: Path
) -> None:
    result = _render(runtime, red_blue, tmp_path / "out", poster_position=0.75)
    assert result.poster_path is not None
    assert _is_blue(runtime, result.poster_path)  # 75% of 8 s = 6 s: blue, not the 25% red


@ffmpeg
def test_a_stale_part_never_passes_as_the_frame(
    runtime: FfmpegRuntime, red_blue: Path, tmp_path: Path
) -> None:
    facts = probe_media(red_blue, runtime=runtime)
    out = tmp_path / "p.part"
    out.write_bytes(b"\xff\xd8stale")
    with pytest.raises(PosterFrameError, match="a.mp4"):
        extract_poster(
            runtime, facts, PosterChoice("a.mp4", 50.0, None, "explicit"), target=TARGET, output=out
        )
    assert not out.exists()


@ffmpeg
def test_a_time_with_no_frame_raises_the_typed_error(
    runtime: FfmpegRuntime, red_blue: Path, tmp_path: Path
) -> None:
    facts = probe_media(red_blue, runtime=runtime)
    out = tmp_path / "p.part"
    with pytest.raises(PosterFrameError, match="a.mp4"):
        extract_poster(
            runtime, facts, PosterChoice("a.mp4", 50.0, None, "explicit"), target=TARGET, output=out
        )


def _half_clip(runtime: FfmpegRuntime, tmp_path: Path, *, display_rotation: int) -> Path:
    stored = tmp_path / "stored.mp4"
    runtime.run(
        ["-y", "-f", "lavfi", "-i", "color=white:size=320x240:rate=10:duration=2"]
        + ["-vf", "drawbox=x=160:y=0:w=160:h=240:color=black:t=fill,setsar=2"]
        + ["-c:v", "libx264", "-pix_fmt", "yuv420p", str(stored)]
    )
    clip = tmp_path / "phone.mp4"
    runtime.run(
        ["-y", "-display_rotation:v:0", str(display_rotation), "-i", str(stored)]
        + ["-map", "0", "-c", "copy", str(clip)]
    )
    return clip


@ffmpeg
@pytest.mark.parametrize("rotate", [None, 90])
def test_a_rotated_clip_with_non_square_pixels_gives_an_upright_square_pixel_poster(
    runtime: FfmpegRuntime, tmp_path: Path, rotate: Optional[int]
) -> None:
    clip = _half_clip(runtime, tmp_path, display_rotation=90)
    facts = probe_media(clip, runtime=runtime)
    assert facts.rotation == 90 and facts.sample_aspect_ratio == "2:1"
    out = tmp_path / "poster.jpg"
    extract_poster(
        runtime,
        facts,
        PosterChoice("phone.mp4", 0.5, rotate, "explicit"),
        target=TARGET,
        output=out,
    )

    verify_poster(runtime, out, TARGET)  # 320x240
    probed = runtime.run_ffprobe(
        ["-v", "error", "-show_entries", "stream=sample_aspect_ratio,width,height"]
        + ["-print_format", "json", str(out)]
    )
    stream = json.loads(probed.stdout)["streams"][0]
    assert stream.get("sample_aspect_ratio") in (None, "1:1")
    # display rotation 90 shows the white half at the bottom; rotate 90 turns it to the left
    white, black = (
        ("100:60:110:170", "100:60:110:10") if rotate is None else ("40:100:30:70", "40:100:250:70")
    )
    assert _signal(runtime, out, "YAVG", white) > 200
    assert _signal(runtime, out, "YAVG", black) < 40


@ffmpeg
def test_a_wide_pixel_clip_is_padded_not_stretched(
    runtime: FfmpegRuntime, make_clip, tmp_path: Path
) -> None:
    clip = make_clip("wide.mp4", width=320, height=240, fps=10, duration=1.0, setsar="2")
    facts = probe_media(clip, runtime=runtime)
    out = tmp_path / "poster.jpg"
    extract_poster(
        runtime, facts, PosterChoice("wide.mp4", 0.2, None, "explicit"), target=TARGET, output=out
    )
    # shows as 640x240: fitted to 320x120 and padded black above and below
    assert _signal(runtime, out, "YAVG", "320:50:0:0") < 20
    assert _signal(runtime, out, "YAVG", "320:50:0:95") > 30


@ffmpeg
def test_verification_ignores_the_cover_and_catches_a_missing_or_doubled_one(
    runtime: FfmpegRuntime, red_blue: Path, tmp_path: Path
) -> None:
    covered = _render(runtime, red_blue, tmp_path / "out").output_path
    sidecar = poster_path(covered)

    facts = verify_output(runtime, covered, TARGET, cover=True)
    assert verify_output(runtime, covered, TARGET).width == facts.width  # ignored when not asked

    bare = tmp_path / "bare.mp4"
    runtime.run(["-y", "-i", str(covered), "-map", "0:v:0", "-map", "0:a", "-c", "copy", str(bare)])
    with pytest.raises(RenderVerificationError, match="cover"):
        verify_output(runtime, bare, TARGET, cover=True)
    assert verify_output(runtime, bare, TARGET) is not None

    doubled = tmp_path / "doubled.mp4"
    runtime.run(  # a second picture on a movie that already has one
        ["-y", "-i", str(covered), "-f", "image2", "-i", str(sidecar), "-map", "0", "-map", "1:v"]
        + ["-c", "copy", "-disposition:v:2", "attached_pic", "-f", "mp4", str(doubled)]
    )
    with pytest.raises(RenderVerificationError, match="cover"):
        verify_output(runtime, doubled, TARGET, cover=True)


@ffmpeg
def test_movie_facts_equal_those_of_the_same_movie_without_a_cover(
    runtime: FfmpegRuntime, red_blue: Path, tmp_path: Path
) -> None:
    covered = _render(runtime, red_blue, tmp_path / "out").output_path
    bare = tmp_path / "bare.mp4"
    runtime.run(["-y", "-i", str(covered), "-map", "0:v:0", "-map", "0:a", "-c", "copy", str(bare)])
    with_cover = probe_media(covered, runtime=runtime)
    without = probe_media(bare, runtime=runtime)
    assert replace(with_cover, path=bare, video_bitrate=None) == replace(
        without, video_bitrate=None
    )
    chapters = [json.loads(runtime.run_ffprobe(["-v", "error", "-show_chapters", "-print_format",
                                               "json", str(m)]).stdout)["chapters"]
                for m in (covered, bare)]  # fmt: skip
    assert chapters[0] == chapters[1] and chapters[0]


@ffmpeg
def test_a_forced_re_render_replaces_both_files(
    runtime: FfmpegRuntime, red_blue: Path, tmp_path: Path
) -> None:
    out = tmp_path / "out"
    first = _render(runtime, red_blue, out)
    assert first.poster_path is not None and not _is_blue(runtime, first.poster_path)

    skipped = _render(runtime, red_blue, out, poster=Poster("a.mp4", 6.0))
    assert skipped.skipped and not _is_blue(runtime, first.poster_path)  # nothing replaced

    second = _render(runtime, red_blue, out, poster=Poster("a.mp4", 6.0), overwrite=True)
    assert second.poster_path == first.poster_path
    assert _is_blue(runtime, first.poster_path)
    stream_pic = [
        s for s in _streams(runtime, second.output_path) if s["disposition"]["attached_pic"]
    ]
    assert len(stream_pic) == 1
    assert _no_leftovers(out)


@ffmpeg
def test_a_kill_after_the_poster_part_leaves_nothing_new(
    runtime: FfmpegRuntime, red_blue: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "out"
    first = _render(runtime, red_blue, out, fingerprint=True)
    before = {p: p.read_bytes() for p in (first.output_path, poster_path(first.output_path))}
    manifest_before = manifest_path(red_blue.parent).read_bytes()

    def _killed(*_a: object, **_k: object) -> None:
        assert poster_part_path(first.output_path).is_file()  # the poster .part is there
        raise KeyboardInterrupt("killed while embedding")

    monkeypatch.setattr(orch, "embed_cover", _killed)
    with pytest.raises(KeyboardInterrupt):
        _render(
            runtime, red_blue, out, poster=Poster("a.mp4", 6.0), overwrite=True, fingerprint=True
        )

    assert {p: p.read_bytes() for p in before} == before
    assert manifest_path(red_blue.parent).read_bytes() == manifest_before
    assert _no_leftovers(out)


@ffmpeg
def test_a_kill_at_the_movie_rename_leaves_no_manifest_and_a_stale_event(
    runtime: FfmpegRuntime, red_blue: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "out"
    real_replace = orch.os.replace

    def _killed(src: object, dst: object) -> None:
        if Path(str(dst)).suffix == ".mp4":
            raise KeyboardInterrupt("killed before the movie rename")
        real_replace(src, dst)  # type: ignore[arg-type]

    monkeypatch.setattr(orch.os, "replace", _killed)
    with pytest.raises(KeyboardInterrupt):
        _render(runtime, red_blue, out, fingerprint=True)

    movie = out / "Movie.mp4"
    assert not movie.exists()
    assert not manifest_path(red_blue.parent).exists()
    assert _no_leftovers(out)
    verdict = evaluate(red_blue.parent, movie, compute_fingerprint(
        ReelDocument(metadata=Metadata(title="Movie")), event_dir=red_blue.parent,
        look_defaults={}, ffmpeg_version=runtime.version))  # fmt: skip
    assert verdict.stale


@ffmpeg
def test_a_dry_run_plans_the_poster_extraction_and_writes_nothing(
    runtime: FfmpegRuntime, red_blue: Path, tmp_path: Path
) -> None:
    out = tmp_path / "out"
    plan = _plan(ResolvedClip(red_blue.name), poster=Poster("a.mp4", 6.0))
    options = RenderOptions(
        event_dir=red_blue.parent,
        output_dir=out,
        clip_facts={red_blue.name: probe_media(red_blue, runtime=runtime)},
        runtime=runtime,
        dry_run=True,
        temp_dir=tmp_path / "scratch",
    )
    result = render_movie(plan, CPUProfile(), options)
    assert result.poster_path == out / "Movie-poster.jpg"
    assert any("-frames:v" in c and "6.000" in c for c in result.commands)
    assert not out.exists()


def test_a_manifest_written_without_a_poster_records_null(tmp_path: Path) -> None:
    fingerprint = compute_fingerprint(
        ReelDocument(metadata=Metadata(title="Movie")),
        event_dir=tmp_path,
        look_defaults={},
        ffmpeg_version=(7, 1),
    )
    path = write_manifest(tmp_path, fingerprint, output="Movie.mp4", engine_identity="x")
    assert json.loads(path.read_text(encoding="utf-8"))["poster"] is None
