"""A timed-overlay segment is split at its window (video-card-bridge-window).

The CPU overlay bridge (hwdownload, overlay, hwupload on VAAPI) must cover only the seconds a
title card can show, not the rest of a long first clip. Covers the pure split rule, the commands
the head and the tail get on each kind of profile, the orchestrator's single materialization and
shared segment list (plan, run, progress, chapters) and, with real ffmpeg, that the joined movie
keeps every frame and a continuous audio track.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import replace
from datetime import date
from fractions import Fraction
from pathlib import Path
from typing import Optional

import pytest
from test_title_card_overlay import _amd, _caps, _card_overlay, _clip, _segment, _target

from auto_reel_ng.accel.models import Vendor
from auto_reel_ng.accel.profiles import CPUProfile, NvencProfile
from auto_reel_ng.errors import RenderError
from auto_reel_ng.event.plan import RenderPlan, ResolvedChapter, ResolvedClip
from auto_reel_ng.probe import probe_media
from auto_reel_ng.reel.card import ChapterCard
from auto_reel_ng.reel.document import Metadata
from auto_reel_ng.render import ProducedSegment, RenderOptions, Segment
from auto_reel_ng.render import orchestrator as orch
from auto_reel_ng.render import producers, render_movie
from auto_reel_ng.render.card_window import build_join_command, split_segment
from auto_reel_ng.render.normalize import AudioSidecar, build_normalize_command
from auto_reel_ng.render.segments import OverlaySpec

# --------------------------------------------------------------------------- #
# The pure split rule                                                          #
# --------------------------------------------------------------------------- #

FPS = 30.0


def _card(end: float = 7.0) -> OverlaySpec:
    return _card_overlay(end=end)


def test_a_180s_clip_under_a_7s_card_is_a_head_and_a_tail() -> None:
    head, tail = split_segment(_segment(overlays=(_card(),)), FPS, 180.0)
    assert (head.start, head.end, head.is_full_clip) == (0.0, 7.0, False)
    assert head.overlays == (_card(),)
    assert (tail.start, tail.end, tail.is_full_clip) == (7.0, 180.0, False)
    assert tail.overlays == ()
    assert not head.copy_eligible and not tail.copy_eligible
    for piece in (head, tail):
        assert (piece.identity, piece.source_path, piece.chapter, piece.rotate) == (
            "clip.mp4",
            Path("/ev/clip.mp4"),
            "",
            None,
        )


def test_the_split_lands_on_the_frame_grid_and_the_window_is_untouched() -> None:
    head, tail = split_segment(_segment(overlays=(_card(7.01),)), FPS, 180.0)
    assert head.end == pytest.approx(211 / 30)
    assert tail.start == head.end  # exactly: no gap, no overlap
    assert head.overlays[0].end == 7.01


def test_a_window_that_is_a_whole_number_of_frames_does_not_gain_one() -> None:
    # 7.0 * 30 is 210.00000000000003 in floats; the epsilon keeps it at 210 frames
    head, _ = split_segment(_segment(overlays=(_card(),)), FPS, 180.0)
    assert round(head.end * FPS) == 210


def test_a_trimmed_anchor_splits_inside_its_span() -> None:
    segment = _segment(is_full_clip=False, start=12.0, end=60.0, overlays=(_card(),))
    head, tail = split_segment(segment, FPS, 48.0)
    assert (head.start, head.end) == (12.0, 19.0)
    assert (tail.start, tail.end) == (19.0, 60.0)


def test_the_boundary_is_a_multiple_of_the_frame_period_at_23_976() -> None:
    fps = 24000 / 1001
    head, tail = split_segment(_segment(overlays=(_card(7.0),)), fps, 100.0)
    frames = Fraction(head.end - 0.0).limit_denominator(10**9) * Fraction(24000, 1001)
    assert abs(float(frames) - round(float(frames))) < 1e-6
    assert round(float(frames)) == 168  # ceil(7 * 23.976)
    assert tail.start == head.end


@pytest.mark.parametrize("length", [7.5, 7.99, 3.0, 7.0])
def test_a_remainder_under_a_second_or_a_window_covering_the_segment_is_not_split(
    length: float,
) -> None:
    segment = _segment(overlays=(_card(),))
    assert split_segment(segment, FPS, length) == (segment,)


def test_a_remainder_of_exactly_a_second_is_split() -> None:
    assert len(split_segment(_segment(overlays=(_card(),)), FPS, 8.0)) == 2


@pytest.mark.parametrize(
    "overlays",
    [
        (),
        (OverlaySpec(source="/t/mark.png"),),
        (_card_overlay(), OverlaySpec(source="/t/mark.png")),
    ],
    ids=["none", "untimed", "mixed"],
)
def test_segments_without_only_timed_overlays_are_unchanged(overlays) -> None:
    segment = _segment(overlays=overlays)
    assert split_segment(segment, FPS, 180.0) == (segment,)


def test_a_synthetic_segment_is_never_split() -> None:
    segment = Segment(chapter="", producer="title", duration=30.0, overlays=(_card(),))
    assert split_segment(segment, FPS, 30.0) == (segment,)


def test_a_timed_overlay_that_is_not_yet_materialized_has_no_window_to_split_at() -> None:
    segment = _segment(overlays=(OverlaySpec(producer="title", producer_config=None),))
    assert split_segment(segment, FPS, 180.0) == (segment,)


# --------------------------------------------------------------------------- #
# The commands                                                                 #
# --------------------------------------------------------------------------- #


def _pair(profile, *, audio: bool = True, start: Optional[float] = None):
    clip = _clip(180.0, audio=audio)
    whole = _segment(overlays=(_card(),))
    if start is not None:
        whole = _segment(is_full_clip=False, start=start, end=start + 180.0, overlays=(_card(),))
    head, tail = split_segment(whole, FPS, 180.0)
    sidecar = AudioSidecar(Path("/t/audio.m4a"), start, 180.0)
    return (
        build_normalize_command(head, clip, _target(), profile, Path("/t/head.mp4"), audio=False),
        build_normalize_command(tail, clip, _target(), profile, Path("/t/tail.mp4"), audio=sidecar),
    )


def _output_tail(args: tuple[str, ...], output: str) -> tuple[str, ...]:
    """The last arguments before (and including) the first output file ``output``."""
    i = args.index(output)
    return args[i - 3 : i + 1]


def _after(args: tuple[str, ...], flag: str) -> str:
    return args[args.index(flag) + 1]


def test_on_vaapi_only_the_head_goes_through_the_cpu_bridge() -> None:
    head, tail = _pair(_amd())
    assert _after(head.args, "-ss") == "0" and _after(head.args, "-t") == "7"
    graph = _after(head.args, "-filter_complex")
    assert "hwdownload,format=nv12" in graph
    assert "overlay=x=0:y=0:format=auto:enable='between(t,0,7)'" in graph
    assert graph.endswith("[vo0]format=nv12,hwupload[vout]")
    assert head.duration == 7.0

    assert _after(tail.args, "-ss") == "7"
    assert _output_tail(tail.args, "/t/tail.mp4") == ("-t", "173", "-an", "/t/tail.mp4")
    joined = " ".join(tail.args)
    assert tail.duration == 173.0
    assert "scale_vaapi" in _after(tail.args, "-vf")
    for banned in ("hwdownload", "hwupload", "-filter_complex", "overlay", "card.png", "-loop"):
        assert banned not in joined, banned
    assert tail.args.count("-i") == 2  # the clip for its video, the clip again for the audio


def test_on_the_cpu_profile_the_head_has_the_overlay_and_the_tail_is_plain() -> None:
    head, tail = _pair(CPUProfile())
    assert "overlay=" in _after(head.args, "-filter_complex")
    assert "hwdownload" not in " ".join(head.args) and "hwupload" not in " ".join(head.args)
    assert "-filter_complex" not in tail.args and "overlay" not in " ".join(tail.args)
    assert _after(tail.args, "-ss") == "7"


def test_a_hardware_overlay_profile_still_uses_the_cpu_overlay_for_the_head() -> None:
    head, tail = _pair(NvencProfile(_caps(can_overlay_hw=True, vendor=Vendor.NVIDIA)))
    assert "overlay=x=0:y=0:format=auto" in _after(head.args, "-filter_complex")
    assert "overlay_cuda" not in " ".join(head.args)
    assert "-filter_complex" not in tail.args


def test_the_head_is_video_only_and_a_whole_segment_still_has_its_audio() -> None:
    head, _ = _pair(_amd())
    assert "-an" in head.args and "-c:a" not in head.args and "0:a:0" not in head.args
    assert head.args.count("-i") == 2  # the clip and the card
    whole = build_normalize_command(
        _segment(overlays=(_card(),)), _clip(180.0), _target(), _amd(), Path("/t/seg.mp4")
    )
    assert "0:a:0" in whole.args and _after(whole.args, "-c:a") == "aac" and "-an" not in whole.args


def test_the_tail_writes_the_audio_of_the_whole_segment_as_a_second_output() -> None:
    _, tail = _pair(_amd())
    args = tail.args
    assert args[-1] == "/t/audio.m4a" and args[args.index("/t/tail.mp4") - 1] == "-an"
    i = args.index("-i", args.index("-i") + 1)  # the second input
    assert args[i - 2 : i + 2] == ("-t", "180", "-i", "/ev/clip.mp4") or args[i - 4 : i + 2] == (
        "-ss",
        "0",
        "-t",
        "180",
        "-i",
        "/ev/clip.mp4",
    )
    assert args[args.index("/t/tail.mp4") + 1 : -1] == (
        "-map", "1:a:0", "-c:a", "aac", "-ar", "48000", "-ac", "2"
    )  # fmt: skip
    assert tail.output_path == Path("/t/tail.mp4") and tail.duration == 173.0


def test_a_trimmed_segments_audio_is_cut_from_its_own_span() -> None:
    head, tail = _pair(CPUProfile(), start=12.0)
    i = tail.args.index("-i", tail.args.index("-i") + 1)
    assert tail.args[i - 4 : i + 2] == ("-ss", "12", "-t", "180", "-i", "/ev/clip.mp4")
    assert _after(head.args, "-ss") == "12" and _after(tail.args, "-ss") == "19"


def test_a_clip_without_audio_gets_silence_of_the_segments_length_beside_the_tail() -> None:
    _, tail = _pair(CPUProfile(), audio=False)
    joined = " ".join(tail.args)
    assert "anullsrc=channel_layout=stereo:sample_rate=48000" in joined
    assert _output_tail(tail.args, "/t/tail.mp4")[:2] == ("-t", "173")
    assert tail.args[tail.args.index("lavfi") + 1] == "-t"
    assert tail.args[tail.args.index("lavfi") + 2] == "180"
    assert tail.args[-1] == "/t/audio.m4a" and "/ev/clip.mp4" in tail.args


def test_the_join_copies_the_pieces_video_and_the_one_audio_track() -> None:
    command = build_join_command(
        Path("/t/join.txt"), Path("/t/audio.m4a"), Path("/t/seg.mp4"), duration=180.0
    )
    assert command.args == (
        "-y", "-f", "concat", "-safe", "0", "-i", "/t/join.txt", "-i", "/t/audio.m4a",
        "-map", "0:v:0", "-map", "1:a:0", "-c", "copy", "/t/seg.mp4",
    )  # fmt: skip
    assert command.duration == 180.0 and command.output_path == Path("/t/seg.mp4")


# --------------------------------------------------------------------------- #
# The orchestrator                                                             #
# --------------------------------------------------------------------------- #


@pytest.fixture
def card_producer(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    calls: list[Path] = []

    def produce(segment: Segment, target, dest: Path) -> ProducedSegment:
        del segment, target
        calls.append(dest)
        dest.write_bytes(b"png")
        return ProducedSegment(image_path=dest, duration=7.0, fade_in=2.0, fade_out=2.0)

    monkeypatch.setitem(producers._REGISTRY, "fake-card", produce)  # pylint: disable=W0212
    return calls


def _opts(tmp_path: Path, duration: float = 180.0, **kw: object) -> RenderOptions:
    return RenderOptions(
        event_dir=Path("/ev"),
        output_dir=tmp_path / "out",
        clip_facts={"clip.mp4": _clip(duration), "b.mp4": replace(_clip(10.0), path=Path("b.mp4"))},
        runtime=None,  # type: ignore[arg-type]
        **kw,  # type: ignore[arg-type]
    )


def _anchor_plan() -> tuple[Segment, ...]:
    anchor = _segment(overlays=(OverlaySpec(producer="fake-card", producer_config=None),))
    second = _segment(identity="b.mp4", source_path=Path("/ev/b.mp4"))
    return (anchor, second)


def test_the_card_is_rendered_once_and_a_dry_run_lists_head_tail_and_join(
    card_producer: list[Path], tmp_path: Path
) -> None:
    scratch = tmp_path / "scratch"
    result = orch._plan_only(  # pylint: disable=protected-access
        _anchor_plan(),
        _target(),
        CPUProfile(),
        _opts(tmp_path, dry_run=True, temp_dir=scratch),
        tmp_path / "out" / "Movie.mp4",
    )
    assert card_producer == [scratch / "card_000_0.png"]
    head, tail, join, second, concat = result.commands
    card = str(scratch / "card_000_0.png")
    assert (
        card in head and "-filter_complex" in head and head[-1] == str(scratch / "seg_000_head.mp4")
    )
    assert card not in tail and "-filter_complex" not in tail
    assert tail[-1] == str(scratch / "seg_000_audio.m4a")
    assert str(scratch / "seg_000_tail.mp4") in tail
    assert join[-1] == str(scratch / "seg_000.mp4") and "copy" in join
    assert second[-1] == str(scratch / "seg_001.mp4")
    assert concat[-1] == str(tmp_path / "out" / "Movie.mp4")
    assert len(result.commands) == 5


def test_a_segment_too_short_to_split_plans_one_command(
    card_producer: list[Path], tmp_path: Path
) -> None:
    result = orch._plan_only(  # pylint: disable=protected-access
        _anchor_plan(),
        _target(),
        CPUProfile(),
        _opts(tmp_path, duration=7.5, dry_run=True, temp_dir=tmp_path / "s"),
        tmp_path / "out" / "Movie.mp4",
    )
    assert len(result.commands) == 3  # the anchor whole, the second clip, the concat
    assert result.commands[0][-1].endswith("seg_000.mp4")


def test_progress_pieces_report_their_share_of_the_segments_weight() -> None:
    seen: list[float] = []
    progress = orch._Progress(seen.append, {0: 10.0}, normalize_end=1.0)  # pylint: disable=W0212
    head, tail = progress.step(0, 0.0, 0.25), progress.step(0, 0.25, 1.0)
    assert head is not None and tail is not None
    head(0.5)
    head(1.0)
    tail(0.0)
    tail(1.0)
    assert seen == pytest.approx([0.125, 0.25, 1.0])


def test_an_unregistered_producer_still_fails_loud_naming_the_segment(tmp_path: Path) -> None:
    anchor = _segment(overlays=(OverlaySpec(producer="nope"),))
    with pytest.raises(RenderError, match=r"segment 0 \('clip.mp4'\).*unknown segment producer"):
        orch._normalize_segment(  # pylint: disable=protected-access
            0,
            anchor,
            target=_target(),
            profile=CPUProfile(),
            options=_opts(tmp_path),
            scratch=tmp_path,
            progress=orch._Progress(None, {}, normalize_end=1.0),  # pylint: disable=W0212
        )


def test_a_clip_without_facts_is_left_whole_for_its_command_to_refuse(
    card_producer: list[Path], tmp_path: Path
) -> None:
    options = replace(_opts(tmp_path), clip_facts={})
    segment = _anchor_plan()[0]
    plan = orch._plan_encodes(  # pylint: disable=protected-access
        0, segment, target=_target(), options=options, scratch=tmp_path
    )
    assert len(plan.encodes) == 1 and plan.join is None
    with pytest.raises(RenderError, match="no clip facts"):
        orch._build_segment_command(  # pylint: disable=protected-access
            0, segment, target=_target(), profile=CPUProfile(), options=options, scratch=tmp_path
        )


# --------------------------------------------------------------------------- #
# Real ffmpeg: the join                                                        #
# --------------------------------------------------------------------------- #

_W, _H = 320, 180
_LEVELS = 28  # luma = 16 + 8 * (frame % 28): a frame number read back from a flat corner


def _signature_clip(runtime, path: Path, duration: float, *, audio: bool) -> Path:
    args = [
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c=black:s={_W}x{_H}:r=30:d={duration},"
        f"geq=lum='16+8*mod(N,{_LEVELS})':cb=128:cr=128",
    ]
    if audio:
        args += ["-f", "lavfi", "-i", f"sine=frequency=440:sample_rate=48000:duration={duration}"]
    args += ["-c:v", "libx264", "-crf", "12", "-pix_fmt", "yuv420p", "-g", "30"]
    if audio:
        args += ["-c:a", "aac", "-b:a", "192k", "-shortest"]
    runtime.run([*args, str(path)])
    return path


def _event(runtime, tmp_path: Path, name: str, *, audio: bool, duration: float = 20.0):
    event = tmp_path / name
    event.mkdir()
    _signature_clip(runtime, event / "a.mp4", duration, audio=audio)
    facts = {"a.mp4": probe_media(event / "a.mp4", runtime=runtime)}
    plan = RenderPlan(
        metadata=Metadata(title="Movie", date=date(2024, 6, 21), location=""),
        look={
            "decorators": ["title"],
            "target_resolution": [_W, _H],
            "video_codec": "h264",
            "title_card": {"fade_in": 1.0, "fade_out": 1.0, "text_color": "#FFFFFF"},
        },
        chapters=(
            ResolvedChapter(
                name="",
                clips=(ResolvedClip(identity="a.mp4", is_title=True),),
                card=ChapterCard(background="video", duration=7.0),
            ),
        ),
    )
    options = RenderOptions(
        event_dir=event, output_dir=event / "out", clip_facts=facts, runtime=runtime
    )
    return plan, options


def _render_both(runtime, tmp_path, monkeypatch, *, audio: bool):
    plan, options = _event(runtime, tmp_path, "split", audio=audio)
    split = render_movie(plan, CPUProfile(), options)
    with monkeypatch.context() as patch:
        patch.setattr(orch, "split_segment", lambda segment, fps, length: (segment,))
        plan2, options2 = _event(runtime, tmp_path, "whole", audio=audio)
        whole = render_movie(plan2, CPUProfile(), options2)
    return split.output_path, whole.output_path


def _frames(runtime, movie: Path) -> list[dict]:
    out = runtime.run_ffprobe(
        ["-v", "error", "-count_frames", "-select_streams", "v:0", "-show_frames",
         "-show_entries", "frame=pts_time", "-print_format", "json", str(movie)]
    )  # fmt: skip
    return json.loads(out.stdout)["frames"]


def _corner_levels(runtime, movie: Path) -> list[int]:
    """The flat corner's luma per frame: the burned-in frame number, away from the card text."""
    result = subprocess.run(
        [runtime.ffmpeg_path, "-v", "error", "-i", str(movie), "-vf",
         "crop=8:8:0:0,format=gray", "-fps_mode", "passthrough", "-f", "rawvideo", "-"],
        capture_output=True, check=True,
    )  # fmt: skip
    data = result.stdout
    return [sum(data[i : i + 64]) // 64 for i in range(0, len(data), 64)]


def _pcm(runtime, movie: Path) -> list[int]:
    result = subprocess.run(
        [runtime.ffmpeg_path, "-v", "error", "-i", str(movie), "-map", "0:a:0", "-f", "s16le",
         "-ac", "1", "-ar", "48000", "-"],
        capture_output=True, check=True,
    )  # fmt: skip
    data = result.stdout
    return [int.from_bytes(data[i : i + 2], "little", signed=True) for i in range(0, len(data), 2)]


@pytest.mark.has_fonts
@pytest.mark.has_ffmpeg
def test_the_split_movie_has_every_frame_of_the_unsplit_one(
    has_fonts: None, runtime, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    split, whole = _render_both(runtime, tmp_path, monkeypatch, audio=True)
    frames, ref = _frames(runtime, split), _frames(runtime, whole)
    assert len(frames) == len(ref) == 600
    times = [float(f["pts_time"]) for f in frames]
    assert all(abs(b - a - 1 / 30) < 1e-4 for a, b in zip(times, times[1:]))
    assert times == pytest.approx([float(f["pts_time"]) for f in ref], abs=1e-4)
    levels, ref_levels = _corner_levels(runtime, split), _corner_levels(runtime, whole)
    assert len(levels) == len(ref_levels) == 600
    # consecutive through the join (frames 205-215 straddle it), and the same picture as unsplit
    expected = [round(8 * (n % _LEVELS) * 255 / 219) for n in range(600)]  # gray: full range
    assert max(abs(a - b) for a, b in zip(levels, expected)) <= 4
    assert max(abs(a - b) for a, b in zip(levels, ref_levels)) <= 2


@pytest.mark.has_fonts
@pytest.mark.has_ffmpeg
def test_the_movie_and_chapter_durations_agree_within_a_frame(
    has_fonts: None, runtime, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    split, whole = _render_both(runtime, tmp_path, monkeypatch, audio=True)
    assert probe_media(split, runtime=runtime).duration == pytest.approx(
        probe_media(whole, runtime=runtime).duration, abs=1 / 30
    )


@pytest.mark.has_fonts
@pytest.mark.has_ffmpeg
def test_the_audio_is_continuous_across_the_join(
    has_fonts: None, runtime, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    split, whole = _render_both(runtime, tmp_path, monkeypatch, audio=True)
    pcm, ref = _pcm(runtime, split), _pcm(runtime, whole)
    assert abs(len(pcm) - len(ref)) <= 1024
    tone_step = max(abs(b - a) for a, b in zip(ref[2048:-2048], ref[2049:-2048]))
    seam = 7 * 48000
    window = pcm[seam - 4096 : seam + 4096]
    steps = [abs(b - a) for a, b in zip(window, window[1:])]
    assert max(steps) <= 2 * tone_step, (max(steps), tone_step)
    # no dropout: the tone's envelope never collapses near the seam
    assert max(abs(v) for v in pcm[seam - 512 : seam + 512]) > 0.5 * max(abs(v) for v in ref)


@pytest.mark.has_fonts
@pytest.mark.has_ffmpeg
def test_a_clip_without_audio_has_silence_of_equal_length_on_both_pieces(
    has_fonts: None, runtime, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    split, whole = _render_both(runtime, tmp_path, monkeypatch, audio=False)
    pcm, ref = _pcm(runtime, split), _pcm(runtime, whole)
    assert abs(len(pcm) - len(ref)) <= 1024
    assert max(map(abs, pcm)) == 0


@pytest.mark.gpu
@pytest.mark.has_fonts
@pytest.mark.has_ffmpeg
def test_on_the_hardware_profile_the_tail_stays_off_the_bridge_and_the_frames_match(
    has_fonts: None, runtime, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from auto_reel_ng.accel import detect_capabilities, select_profile  # pylint: disable=C0415

    profile = select_profile(detect_capabilities(runtime))
    if profile.vendor is Vendor.CPU:
        pytest.skip("no usable hardware accelerator on this host")
    plan, options = _event(runtime, tmp_path, "planned", audio=True)
    planned = render_movie(
        plan, profile, replace(options, dry_run=True, temp_dir=tmp_path / "plan-scratch")
    )
    head, tail = planned.commands[0], planned.commands[1]
    assert "hwdownload,format=nv12" in " ".join(head)
    assert "hwdownload" not in " ".join(tail) and "-filter_complex" not in tail

    plan, options = _event(runtime, tmp_path, "hw", audio=True)
    output = render_movie(plan, profile, options).output_path
    assert len(_frames(runtime, output)) == 600
    with monkeypatch.context() as patch:
        patch.setattr(orch, "split_segment", lambda segment, fps, length: (segment,))
        plan, options = _event(runtime, tmp_path, "hw-whole", audio=True)
        whole = render_movie(plan, profile, options).output_path
    assert len(_frames(runtime, whole)) == 600
    assert abs(len(_pcm(runtime, output)) - len(_pcm(runtime, whole))) <= 1024
