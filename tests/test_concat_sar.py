"""The concat pre-flight compares SAR normalized (``vaapi-sar-uniform``).

An unset SAR (absent, empty, ``N/A`` or ``0:1``) is displayed as square, so it must
not block a stream-copy concat of an otherwise uniform set; a concrete non-square SAR
still must.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Optional, Sequence

import pytest

from auto_reel_ng.ffmpeg.runtime import FfmpegRuntime
from auto_reel_ng.render.concat import is_copy_uniform, normalize_sar, probe_copy_fields

_UNSET = object()  # a stream with no ``sample_aspect_ratio`` key at all


def _streams(sar: object) -> dict[str, object]:
    video: dict[str, object] = {
        "codec_type": "video",
        "codec_name": "h264",
        "profile": "High",
        "width": 1920,
        "height": 1080,
        "pix_fmt": "yuv420p",
        "time_base": "1/12800",
    }
    if sar is not _UNSET:
        video["sample_aspect_ratio"] = sar
    audio = {
        "codec_type": "audio",
        "codec_name": "aac",
        "sample_rate": "48000",
        "channels": 2,
        "channel_layout": "stereo",
    }
    return {"streams": [video, audio]}


class _ProbeStub:
    """A runtime whose ffprobe answers per path from canned stream JSON."""

    def __init__(self, sars: dict[str, object]) -> None:
        self._sars = sars

    def run_ffprobe(self, args: Sequence[str]) -> subprocess.CompletedProcess[str]:
        payload = json.dumps(_streams(self._sars[Path(args[-1]).name]))
        return subprocess.CompletedProcess(list(args), 0, stdout=payload, stderr="")


def _uniform(first: object, second: object) -> bool:
    stub = _ProbeStub({"a.mp4": first, "b.mp4": second})
    return is_copy_uniform(stub, [Path("a.mp4"), Path("b.mp4")])  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "unset", ["N/A", "0:1", "", None, _UNSET], ids=["na", "zero", "empty", "none", "missing"]
)
def test_an_unset_sar_is_uniform_with_square(unset: object) -> None:
    assert _uniform(unset, "1:1") is True
    assert _uniform("1:1", unset) is True


@pytest.mark.parametrize(
    "unset", ["N/A", "0:1", None, _UNSET], ids=["na", "zero", "none", "missing"]
)
def test_probe_copy_fields_holds_the_normalized_sar(unset: object) -> None:
    stub = _ProbeStub({"a.mp4": unset})
    fields = probe_copy_fields(stub, Path("a.mp4"))  # type: ignore[arg-type]
    assert fields.sample_aspect_ratio == "1:1"


def test_a_real_sar_difference_still_blocks_the_copy() -> None:
    assert _uniform("4:3", "1:1") is False
    assert _uniform("4:3", "N/A") is False
    assert _uniform("4:3", "4:3") is True


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(None, "1:1"), ("", "1:1"), ("N/A", "1:1"), ("0:1", "1:1"), ("1:1", "1:1"), ("4:3", "4:3")],
)
def test_normalize_sar(raw: Optional[str], expected: str) -> None:
    assert normalize_sar(raw) == expected


def _raw_sar(runtime: FfmpegRuntime, path: Path) -> Optional[str]:
    result = runtime.run_ffprobe(
        ["-v", "error", "-select_streams", "v:0", "-show_streams", "-of", "json", str(path)]
    )
    streams = json.loads(result.stdout)["streams"]
    value = streams[0].get("sample_aspect_ratio")
    return None if value is None else str(value)


@pytest.mark.has_ffmpeg
def test_is_copy_uniform_over_real_files_with_and_without_sar(
    runtime: FfmpegRuntime, make_clip
) -> None:
    unset = make_clip("unset.mp4", width=320, height=240, setsar="0")
    square = make_clip("square.mp4", width=320, height=240, setsar="1")
    # Not vacuous: the first file really carries an unset SAR, the second a square one.
    assert _raw_sar(runtime, unset) in (None, "N/A", "0:1")
    assert _raw_sar(runtime, square) == "1:1"

    assert is_copy_uniform(runtime, [unset, square]) is True
