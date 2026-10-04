"""Every normalize path sets SAR 1:1 (``vaapi-sar-uniform``).

Golden-graph tests, no GPU needed. The defect: a clip with no SAR whose display rotation
and ``rotate`` cancel (net turn 0) normalized on VAAPI as a bare ``scale_vaapi``, which
passes the unset SAR through; the segment then probed ``N/A`` beside ``1:1`` ones and the
concat pre-flight refused the render. Every chain now ends in an explicit ``setsar=1``.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from test_render import _amd_caps, _clip, _source_segment, _target

from auto_reel_ng.accel.models import AcceleratorCapabilities, OpClass, OpParams, Vendor
from auto_reel_ng.accel.profiles import CPUProfile, NvencProfile, QsvProfile, VaapiProfile
from auto_reel_ng.accel.profiles.base import AccelProfile
from auto_reel_ng.probe.metadata import ClipMetadata
from auto_reel_ng.render.card_window import split_segment
from auto_reel_ng.render.normalize import AudioSidecar, NormalizeCommand, build_normalize_command
from auto_reel_ng.render.segments import OverlaySpec, Segment

_OUT = Path("/t/seg.mp4")


def _vaapi(pad_fill_ok: bool = True) -> VaapiProfile:
    return VaapiProfile(dataclasses.replace(_amd_caps(), pad_fill_ok=pad_fill_ok))


def _video_chain(command: NormalizeCommand) -> str:
    args = command.args
    flag = "-filter_complex" if "-filter_complex" in args else "-vf"
    return args[args.index(flag) + 1]


def _no_sar_clip(**overrides: object) -> ClipMetadata:
    """The Provklipp shape: 1920x1080, SAR ``N/A``, display matrix -90 (probed 270)."""
    rotation = overrides.pop("rotation", 270)
    clip = _clip(sar="N/A", **overrides)  # type: ignore[arg-type]
    return dataclasses.replace(clip, rotation=rotation)  # type: ignore[arg-type]


def _assert_square_after_the_gpu_scale(chain: str) -> None:
    assert "setsar=1" in chain, chain
    assert chain.rindex("setsar=1") > chain.index("scale"), chain


@pytest.mark.parametrize(
    ("clip", "segment", "pad_fill_ok"),
    [
        # the Provklipp clip: net turn 0, no pad -> was a bare scale_vaapi
        (_no_sar_clip(), _source_segment(rotate=270), True),
        (_no_sar_clip(), _source_segment(rotate=270), False),
        # a turned clip (CPU transpose between the transfers)
        (_no_sar_clip(), _source_segment(), True),
        # a padded clip with a correct and a faulty hardware fill
        (_clip(width=1440, height=1920, sar="N/A"), _source_segment(), True),
        (_clip(width=1440, height=1920, sar="N/A"), _source_segment(), False),
        # a trimmed segment (seeks into the clip)
        (_clip(sar="N/A"), _source_segment(is_full_clip=False, start=2.0, end=5.0), True),
        # software decode then upload
        (_clip(sar="N/A", codec="mpeg4"), _source_segment(), True),
    ],
    ids=[
        "net-zero-turn",
        "net-zero-turn-faulty-fill",
        "turned",
        "padded-gpu-fill",
        "padded-cpu-fill",
        "trimmed",
        "software-decode",
    ],
)
def test_every_overlay_free_vaapi_normalize_sets_sar_1_1(
    clip: ClipMetadata, segment: Segment, pad_fill_ok: bool
) -> None:
    command = build_normalize_command(segment, clip, _target(), _vaapi(pad_fill_ok), _OUT)
    _assert_square_after_the_gpu_scale(_video_chain(command))


def test_the_net_zero_turn_case_sets_sar_on_the_gpu_without_a_transfer() -> None:
    command = build_normalize_command(
        _source_segment(rotate=270), _no_sar_clip(), _target(), _vaapi(), _OUT
    )
    chain = _video_chain(command)
    assert chain == "scale_vaapi=w=1920:h=1080:force_original_aspect_ratio=decrease,setsar=1"
    assert "hwdownload" not in chain and "hwupload" not in chain
    assert "-noautorotate" in command.args


def _card() -> OverlaySpec:
    return OverlaySpec(source="/t/card.png", start=0.0, end=7.0, fade_in=2.0, fade_out=2.0)


def _bridge_pair(profile: AccelProfile) -> tuple[NormalizeCommand, NormalizeCommand]:
    clip = _clip(sar="N/A", duration=180.0)
    head, tail = split_segment(_source_segment(overlays=(_card(),)), 30.0, 180.0)
    sidecar = AudioSidecar(Path("/t/audio.m4a"), None, 180.0)
    return (
        build_normalize_command(head, clip, _target(), profile, Path("/t/h.mp4"), audio=False),
        build_normalize_command(tail, clip, _target(), profile, Path("/t/t.mp4"), audio=sidecar),
    )


def test_both_halves_of_a_video_card_anchor_set_sar_1_1_on_vaapi() -> None:
    head, tail = _bridge_pair(_vaapi())

    graph = _video_chain(head)
    assert "-filter_complex" in head.args
    # square pixels on the GPU, before the one download that feeds the CPU overlay
    assert graph.index("setsar=1") < graph.index("hwdownload") < graph.index("overlay=")
    assert graph.count("hwdownload") == 1 and graph.count("hwupload") == 1

    chain = _video_chain(tail)
    assert "-filter_complex" not in tail.args
    _assert_square_after_the_gpu_scale(chain)
    assert "hwdownload" not in chain and "hwupload" not in chain


def test_both_halves_of_a_video_card_anchor_set_sar_1_1_on_the_cpu() -> None:
    head, tail = _bridge_pair(CPUProfile())
    assert "setsar=1" in _video_chain(head)
    assert "setsar=1" in _video_chain(tail)


def _hw_caps(vendor: Vendor, method: str, pad: str) -> AcceleratorCapabilities:
    return AcceleratorCapabilities(
        vendor=vendor,
        usable=True,
        device=None,
        pad_filter=pad,
        can_overlay_hw=False,
        can_tonemap_hw=False,
        usable_encoders={"h264": "x"},
        decode_method=method,
        hw_decode={"h264": 8},
    )


_PROFILES: list[AccelProfile] = [
    CPUProfile(),
    VaapiProfile(_amd_caps()),
    VaapiProfile(dataclasses.replace(_amd_caps(), pad_fill_ok=False)),
    QsvProfile(_hw_caps(Vendor.INTEL, "qsv", "pad")),
    NvencProfile(_hw_caps(Vendor.NVIDIA, "cuda", "pad")),
]


@pytest.mark.parametrize("needs_pad", [False, True], ids=["no-pad", "pad"])
@pytest.mark.parametrize(
    "profile", _PROFILES, ids=["cpu", "vaapi", "vaapi-faulty-fill", "qsv", "nvenc"]
)
def test_every_profiles_normalize_fragment_ends_in_setsar_1(
    profile: AccelProfile, needs_pad: bool
) -> None:
    params = OpParams(width=1920, height=1080, codec="h264", needs_pad=needs_pad)
    # (a profile that cannot do this normalize hands back the CPU fragment)
    fragment = profile.fragment(OpClass.NORMALIZE, params)
    assert fragment.filter is not None and fragment.filter.endswith(",setsar=1")
