"""Tests for the proxy contract's geometry, constants and cache key (D-21, clip-proxies)."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Optional

import pytest

from auto_reel_ng.proxies import spec
from auto_reel_ng.proxies.spec import (
    entry_dir,
    gop_frames,
    proxy_dimensions,
    proxy_key,
    spec_digest,
)

# --------------------------------------------------------------------------- #
# dimensions
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("width", "height", "sar", "rotation", "expected"),
    [
        (1920, 1080, None, None, (960, 540)),
        (3840, 2160, "1:1", None, (960, 540)),
        (1280, 720, None, 0, (960, 540)),
        (1080, 1920, None, None, (540, 960)),  # a portrait clip keeps its orientation
        (1280, 720, None, -90, (540, 960)),  # the probe normalises -90 to 270 ...
        (1280, 720, None, 270, (540, 960)),
        (1280, 720, None, 90, (540, 960)),
        (720, 576, "16:15", None, (720, 540)),  # anamorphic: not squashed
        (640, 360, None, None, (640, 360)),  # not upscaled
        (720, 480, None, None, (720, 480)),
        (1000, 667, None, None, (810, 540)),  # 809.6 rounds to the nearest even number
        (1920, 1080, "0:1", None, (960, 540)),  # the probe's "no ratio" counts as square
        (1280, 720, None, 180, (960, 540)),  # a half turn does not swap the sides
        (1, 1, None, None, (2, 2)),  # never below 2
    ],
)
def test_the_proxy_dimensions(
    width: int, height: int, sar: Optional[str], rotation: Optional[int], expected: tuple[int, int]
) -> None:
    result = proxy_dimensions(width, height, sar, rotation)
    assert result == expected
    assert result[0] % 2 == 0 and result[1] % 2 == 0 and min(result) >= 2


def test_a_display_short_side_of_exactly_540_is_kept() -> None:
    assert proxy_dimensions(960, 540, None, None) == (960, 540)


def test_a_square_pixel_ratio_in_any_spelling_gives_one_result() -> None:
    sizes = {proxy_dimensions(1920, 1080, sar, None) for sar in (None, "0:1", "1:1", "2:2")}
    assert sizes == {(960, 540)}


@pytest.mark.parametrize("sar", ["1:0", "abc", "16/15", "-1:1", ""])
def test_an_unusable_pixel_ratio_is_refused_not_assumed(sar: str) -> None:
    with pytest.raises(ValueError, match="sample aspect ratio"):
        proxy_dimensions(1920, 1080, sar, None)


def test_a_non_positive_coded_size_is_refused() -> None:
    with pytest.raises(ValueError, match="coded size"):
        proxy_dimensions(0, 1080, None, None)


# --------------------------------------------------------------------------- #
# the keyframe interval and the constants
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("fps", "frames"),
    [(25.0, 25), (50.0, 50), (30000 / 1001, 30), (24000 / 1001, 24), (0.2, 1), (29.97, 30)],
)
def test_one_keyframe_interval_is_a_second_of_frames(fps: float, frames: int) -> None:
    assert gop_frames(fps) == frames


def test_the_audio_encoder_is_the_native_one() -> None:
    assert spec.PROXY_AUDIO_ENCODER == "aac"


def test_the_contract_carries_the_values_e1_locked() -> None:
    assert spec.PROXY_BFRAMES == 2
    assert spec.PROXY_GOP_SECONDS == 1


# --------------------------------------------------------------------------- #
# the key
# --------------------------------------------------------------------------- #


def _clip(tmp_path: Path, name: str = "C0001.MP4", data: bytes = b"clip bytes") -> Path:
    clip = tmp_path / "lib" / name
    clip.parent.mkdir(parents=True, exist_ok=True)
    clip.write_bytes(data)
    os.utime(clip, ns=(1_700_000_000_000_000_000,) * 2)
    return clip


def test_the_key_is_stable(tmp_path: Path) -> None:
    clip = _clip(tmp_path)
    assert proxy_key(clip) == proxy_key(clip)
    assert len(proxy_key(clip)) == 64


def test_the_key_changes_with_the_size(tmp_path: Path) -> None:
    clip = _clip(tmp_path)
    before = proxy_key(clip)
    stat = clip.stat()
    with clip.open("ab") as handle:
        handle.write(b"x")
    os.utime(clip, ns=(stat.st_atime_ns, stat.st_mtime_ns))  # only the size differs
    assert proxy_key(clip) != before


def test_the_key_changes_with_the_modification_time(tmp_path: Path) -> None:
    clip = _clip(tmp_path)
    before = proxy_key(clip)
    os.utime(clip, ns=(1_700_000_000_000_000_000, 1_700_000_000_000_000_001))
    assert proxy_key(clip) != before


def test_the_key_changes_with_the_file_name(tmp_path: Path) -> None:
    clip = _clip(tmp_path)
    before = proxy_key(clip)
    renamed = clip.with_name("C0002.MP4")
    clip.rename(renamed)
    assert proxy_key(renamed) != before


def test_the_key_changes_with_the_proxy_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clip = _clip(tmp_path)
    before = proxy_key(clip)
    monkeypatch.setattr(spec, "PROXY_VERSION", spec.PROXY_VERSION + 1)
    assert proxy_key(clip) != before


@pytest.mark.parametrize(
    ("constant", "value"),
    [
        ("PROXY_BFRAMES", 0),
        ("PROXY_GOP_SECONDS", 2),
        ("PROXY_CRF", 28),
        ("PROXY_SHORT_SIDE", 720),
        ("PROXY_PRESET", "medium"),
        ("PROXY_AUDIO_BITRATE", "64k"),
        ("PROXY_AUDIO_CHANNELS", 1),
    ],
)
def test_a_contract_constant_edited_without_a_version_bump_still_rekeys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, constant: str, value: object
) -> None:
    clip = _clip(tmp_path)
    before, digest = proxy_key(clip), spec_digest()
    monkeypatch.setattr(spec, constant, value)
    assert spec_digest() != digest
    assert proxy_key(clip) != before


def test_two_symlinks_to_one_file_share_a_key(tmp_path: Path) -> None:
    clip = _clip(tmp_path)
    first = tmp_path / "a" / "link-one.mp4"
    second = tmp_path / "b" / "link-two.mp4"
    for link in (first, second):
        link.parent.mkdir()
        link.symlink_to(clip)
    assert proxy_key(first) == proxy_key(second) == proxy_key(clip)


def test_a_copy_in_another_directory_keeps_the_key(tmp_path: Path) -> None:
    clip = _clip(tmp_path)
    copy_dir = tmp_path / "moved"
    copy_dir.mkdir()
    copy = copy_dir / clip.name
    shutil.copy2(clip, copy)  # like ``cp -a``: the size and the mtime survive
    assert proxy_key(copy) == proxy_key(clip)


def test_a_missing_clip_raises_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        proxy_key(tmp_path / "gone.mp4")


def test_a_non_utf8_file_name_is_keyable(tmp_path: Path) -> None:
    clip = _clip(tmp_path, os.fsdecode(b"caf\xe9.mp4"))
    assert len(proxy_key(clip)) == 64


def test_entry_dir_is_the_key_under_the_cache_and_creates_nothing(tmp_path: Path) -> None:
    clip = _clip(tmp_path)
    cache = tmp_path / "cache" / "proxies"
    assert entry_dir(clip, cache) == cache / proxy_key(clip)
    assert not cache.exists()
