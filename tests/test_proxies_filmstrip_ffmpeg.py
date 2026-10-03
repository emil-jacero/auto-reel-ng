"""Real-encode tests for the filmstrip (``clip-filmstrips``): the C0047 reproduction, tile counts
and contents on proxies made by ``ensure_proxy``, the record, idempotency and the failure paths.

Every test needs a real ffmpeg >= 7.1 (``has_ffmpeg``). The sources carry their own time in the
luma of every frame (``16 + 16 t``), so each tile of a sprite can be read back and compared with
the keyframe it should show. That ramp saturates after about 13 s: longer clips are checked by
count and size only.
"""

from __future__ import annotations

import json
import math
import os
import re
import subprocess
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest

from auto_reel_ng.accel.profiles import CPUProfile
from auto_reel_ng.errors import FfmpegError, FilmstripError, ProxyCacheError
from auto_reel_ng.ffmpeg.runtime import FfmpegRuntime
from auto_reel_ng.proxies import (
    FILMSTRIP_VERSION,
    Filmstrip,
    ProxyEntry,
    ProxySettings,
    ensure_filmstrip,
    ensure_proxy,
)
from auto_reel_ng.proxies import filmstrip as filmstrip_module
from auto_reel_ng.proxies import lookup_filmstrip
from auto_reel_ng.proxies.cache import read_entry
from auto_reel_ng.proxies.facts import ProxyFacts, write_facts
from auto_reel_ng.proxies.spec import gop_frames

pytestmark = pytest.mark.has_ffmpeg

#: The sprite's JPEG is full range, a gray read-back of it is (luma - 16) x 255 / 219.
GRAY_PER_SECOND = 16 * 255 / 219
#: Half the distance between two neighbouring keyframes' tiles at the contract's GOP.
TOLERANCE = 4.0


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def signal_clip(
    runtime: FfmpegRuntime,
    out: Path,
    *,
    frames: int,
    fps: str = "25",
    size: str = "640x360",
    audio: bool = True,
    ramp: bool = True,
) -> Path:
    """A clip of ``frames`` frames whose frame at time ``t`` has luma ``16 + 16 t``.

    ``ramp=False`` makes a plain test pattern instead (``geq`` is slow, and the ramp saturates
    after 13 s anyway), for the long clips that are only counted.
    """
    cmd = [runtime.ffmpeg_path, "-y", "-v", "error", "-f", "lavfi"]
    picture = (
        f"color=c=black:s={size}:r={fps},format=yuv420p,geq=lum='16+16*T':cb=128:cr=128"
        if ramp
        else f"testsrc2=s={size}:r={fps}"
    )
    cmd += ["-i", picture]
    if audio:
        cmd += ["-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000"]
    cmd += ["-frames:v", str(frames), "-c:v", "libx264", "-pix_fmt", "yuv420p"]
    if audio:
        cmd += ["-c:a", "aac", "-shortest"]
    subprocess.run([*cmd, str(out)], check=True, capture_output=True, text=True)
    return out


def proxy_of(runtime: FfmpegRuntime, clip: Path, cache: Path) -> ProxyEntry:
    return ensure_proxy(clip, settings=ProxySettings(cache), runtime=runtime, profile=CPUProfile())


def tile_grays(runtime: FfmpegRuntime, film: Filmstrip) -> List[int]:
    """The gray level at the centre of every tile of the sprite."""
    raw = subprocess.run(
        [runtime.ffmpeg_path, "-v", "error", "-i", str(film.path)]
        + ["-f", "rawvideo", "-pix_fmt", "gray", "-"],
        check=True,
        capture_output=True,
    ).stdout
    assert len(raw) == film.width * film.height
    return [
        raw[
            ((k // film.columns) * film.tile_height + film.tile_height // 2) * film.width
            + (k % film.columns) * film.tile_width
            + film.tile_width // 2
        ]
        for k in range(film.tiles)
    ]


def expected_gray(tile: int, interval: int, fps: Fraction) -> float:
    """The gray level of the latest keyframe at or before second ``tile x interval``."""
    gop = Fraction(gop_frames(float(fps)), 1) / fps
    at = Fraction(tile * interval)
    keyframe = math.floor(at / gop) * gop
    return float(keyframe) * GRAY_PER_SECOND


def probe_image(runtime: FfmpegRuntime, path: Path) -> List[Tuple[str, int, int]]:
    out = runtime.run_ffprobe(
        ["-v", "error", "-show_entries", "stream=codec_name,width,height", "-of", "json", str(path)]
    ).stdout
    return [(s["codec_name"], s["width"], s["height"]) for s in json.loads(out)["streams"]]


def facts_of(entry: ProxyEntry) -> Dict[str, Any]:
    return json.loads(entry.facts_path.read_text(encoding="utf-8"))


class Spy:
    """Wraps a real runtime, recording every ffmpeg and ffprobe call (shared across views)."""

    def __init__(self, inner: FfmpegRuntime, log: Optional[List[Tuple[str, List[str]]]] = None):
        self.inner = inner
        self.log: List[Tuple[str, List[str]]] = [] if log is None else log

    def with_timeout(self, seconds: float) -> "Spy":
        return type(self)(self.inner.with_timeout(seconds), self.log)

    def run(self, args: List[str]) -> "subprocess.CompletedProcess[str]":
        self.log.append(("ffmpeg", list(args)))
        return self.cut(args)

    def cut(self, args: List[str]) -> "subprocess.CompletedProcess[str]":
        return self.inner.run(args)

    def run_ffprobe(self, args: List[str]) -> "subprocess.CompletedProcess[str]":
        self.log.append(("ffprobe", list(args)))
        return self.inner.run_ffprobe(args)

    def calls(self, program: str) -> int:
        return sum(1 for name, _ in self.log if name == program)


def leftovers(cache: Path) -> List[str]:
    """Anything in the cache directory that is not a complete entry."""
    return sorted(p.name for p in cache.iterdir() if p.name.startswith("."))


@pytest.fixture
def cache(tmp_path: Path) -> Path:
    return tmp_path / "cache" / "proxies"


@pytest.fixture
def entry(runtime: FfmpegRuntime, tmp_path: Path, cache: Path) -> ProxyEntry:
    """A 3-second proxy with no filmstrip yet."""
    clip = signal_clip(runtime, tmp_path / "C0100.MP4", frames=75)
    return proxy_of(runtime, clip, cache)


# --------------------------------------------------------------------------- #
# the reproduction: the research chain loses the single-keyframe clip
# --------------------------------------------------------------------------- #

#: (frames at 25 fps, seconds, keyframes, tiles the research's ``fps=1`` chain yields, tiles wanted)
RESEARCH_CASES = [
    (1, 0.04, 1, 0, 1),
    (12, 0.48, 1, 0, 1),  # C0047
    (25, 1.0, 3, 1, 1),
    (26, 1.04, 3, 1, 2),
    (38, 1.52, 4, 1, 2),
    (63, 2.52, 6, 2, 3),
]


def research_chain(
    runtime: FfmpegRuntime, proxy: Path, out: Path
) -> "subprocess.CompletedProcess[str]":
    """The command of the proxies research: keyframes only, ``fps=1``, ``scale``, ``tile``."""
    return subprocess.run(
        [runtime.ffmpeg_path, "-hide_banner", "-nostdin", "-v", "error", "-y"]
        + ["-skip_frame", "nokey", "-i", str(proxy), "-map", "0:v:0", "-an"]
        + ["-vf", "fps=1,scale=160:90,tile=10x30", "-frames:v", "1"]
        + ["-c:v", "mjpeg", "-q:v", "5", "-f", "image2", "-update", "1", str(out)],
        capture_output=True,
        text=True,
        check=False,
    )


def frames_out_of_fps(runtime: FfmpegRuntime, proxy: Path) -> int:
    done = subprocess.run(
        [runtime.ffmpeg_path, "-hide_banner", "-nostdin", "-v", "info", "-skip_frame", "nokey"]
        + ["-i", str(proxy), "-map", "0:v:0", "-an", "-vf", "fps=1,showinfo", "-f", "null", "-"],
        capture_output=True,
        text=True,
        check=True,
    )
    return len(re.findall(r"Parsed_showinfo.*pts_time:", done.stderr))


@pytest.mark.parametrize(("frames", "seconds", "keyframes", "research", "wanted"), RESEARCH_CASES)
def test_the_research_chain_loses_tiles_and_ensure_filmstrip_does_not(
    runtime: FfmpegRuntime,
    tmp_path: Path,
    cache: Path,
    frames: int,
    seconds: float,
    keyframes: int,
    research: int,
    wanted: int,
) -> None:
    entry = proxy_of(runtime, signal_clip(runtime, tmp_path / "c.mp4", frames=frames), cache)
    assert len([p for p in _key_packets(runtime, entry)]) == keyframes

    # the old chain, on the very proxy: no frame at all for a single-keyframe clip
    assert frames_out_of_fps(runtime, entry.proxy_path) == research
    old = research_chain(runtime, entry.proxy_path, tmp_path / "old.jpg")
    if research == 0:
        assert old.returncode == 234
        assert "Nothing was written into output file" in old.stderr
        assert not (tmp_path / "old.jpg").exists()

    film = ensure_filmstrip(tmp_path / "c.mp4", entry, runtime=runtime)
    assert film.tiles == wanted == math.ceil(seconds)
    assert (film.width, film.height) == (film.columns * 160, film.rows * 90)


def _key_packets(runtime: FfmpegRuntime, entry: ProxyEntry) -> List[str]:
    out = runtime.run_ffprobe(
        ["-v", "error", "-select_streams", "v:0", "-show_entries", "packet=flags", "-of", "csv=p=0"]
        + [str(entry.proxy_path)]
    ).stdout
    return [line for line in out.splitlines() if "K" in line]


# --------------------------------------------------------------------------- #
# tile counts and contents on real proxies
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Case:
    name: str
    frames: int
    fps: str
    tiles: int
    columns: int
    rows: int
    #: True when the luma ramp still tells tiles apart (clips up to about 13 s).
    readable: bool


CASES = [
    Case("single-frame", 1, "25", 1, 1, 1, True),
    Case("c0047-0.48s", 12, "25", 1, 1, 1, True),
    Case("one-second", 25, "25", 1, 1, 1, True),
    Case("1.04s", 26, "25", 2, 2, 1, True),
    Case("2.52s", 63, "25", 3, 3, 1, True),
    Case("12s-50fps", 600, "50", 12, 10, 2, True),
    Case("12.5s-25fps", 313, "25", 13, 10, 2, True),
    Case("25s-25fps", 625, "25", 25, 10, 3, False),
    Case("25.025s-29.97fps", 750, "30000/1001", 26, 10, 3, False),
]


@pytest.fixture(scope="module")
def built(runtime: FfmpegRuntime, tmp_path_factory: pytest.TempPathFactory) -> Dict[str, Any]:
    """Every case's proxy and filmstrip, made once; the tests only read them."""
    root = tmp_path_factory.mktemp("filmstrips")
    cache = root / "cache"
    made: Dict[str, Any] = {}
    for case in CASES:
        clip = signal_clip(runtime, root / f"{case.name}.mp4", frames=case.frames, fps=case.fps)
        entry = proxy_of(runtime, clip, cache)
        before = facts_of(entry)
        film = ensure_filmstrip(clip, entry, runtime=runtime)
        made[case.name] = (entry, film, before)
    return made


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
def test_every_clip_gets_every_tile_in_a_sprite_of_the_planned_size(
    case: Case, built: Dict[str, Any], runtime: FfmpegRuntime
) -> None:
    entry, film, _ = built[case.name]
    assert (film.tiles, film.columns, film.rows) == (case.tiles, case.columns, case.rows)
    assert film.interval == 1 and (film.tile_width, film.tile_height) == (160, 90)
    assert film.generated is True and film.path == entry.directory / "filmstrip.jpg"
    assert probe_image(runtime, film.path) == [("mjpeg", case.columns * 160, case.rows * 90)]
    assert (film.width, film.height) == (case.columns * 160, case.rows * 90)
    assert film.bytes == film.path.stat().st_size > 0


@pytest.mark.parametrize("case", [c for c in CASES if c.readable], ids=lambda c: c.name)
def test_each_tile_shows_the_keyframe_at_or_before_its_second(
    case: Case, built: Dict[str, Any], runtime: FfmpegRuntime
) -> None:
    _, film, _ = built[case.name]
    fps = Fraction(case.fps)
    grays = tile_grays(runtime, film)
    wanted = [expected_gray(k, film.interval, fps) for k in range(film.tiles)]
    assert [round(g) for g in grays] == pytest.approx(wanted, abs=TOLERANCE)


def test_the_last_tile_is_not_dropped(built: Dict[str, Any]) -> None:
    counts = {
        name: built[name][1].tiles
        for name in ("25s-25fps", "12s-50fps", "1.04s", "25.025s-29.97fps")
    }
    assert counts == {"25s-25fps": 25, "12s-50fps": 12, "1.04s": 2, "25.025s-29.97fps": 26}


def test_the_record_is_in_the_facts_and_nothing_else_there_changed(
    built: Dict[str, Any],
) -> None:
    entry, film, before = built["25s-25fps"]
    after = facts_of(entry)
    assert after.pop("filmstrip") == {
        "version": FILMSTRIP_VERSION,
        "tiles": 25,
        "interval": 1,
        "columns": 10,
        "rows": 3,
        "tile_width": 160,
        "tile_height": 90,
        "width": 1600,
        "height": 270,
        "bytes": film.path.stat().st_size,
    }
    assert after == before


def test_the_c0047_clip_is_its_first_frame_without_error(
    built: Dict[str, Any], runtime: FfmpegRuntime
) -> None:
    entry, film, _ = built["c0047-0.48s"]
    assert (film.tiles, film.width, film.height) == (1, 160, 90)
    assert facts_of(entry)["filmstrip"]["tiles"] == 1
    assert tile_grays(runtime, film)[0] == pytest.approx(0, abs=TOLERANCE)  # time 0 is luma 16


def test_a_proxy_that_is_longer_than_120_seconds_gets_a_wider_interval(
    runtime: FfmpegRuntime, tmp_path: Path, cache: Path
) -> None:
    clip = signal_clip(runtime, tmp_path / "long.mp4", frames=130 * 25, size="320x180", ramp=False)
    entry = proxy_of(runtime, clip, cache)
    film = ensure_filmstrip(clip, entry, runtime=runtime)
    assert (film.interval, film.tiles, film.columns, film.rows) == (2, 65, 10, 7)
    assert (film.width, film.height) == (1600, 630)
    assert probe_image(runtime, film.path) == [("mjpeg", 1600, 630)]


def test_a_clip_of_the_maximum_tiles_is_cut_by_ffmpeg(
    runtime: FfmpegRuntime, tmp_path: Path, cache: Path
) -> None:
    """The dogfood run met ffmpeg's expression limit on a 109-tile clip (a 756 s sample)."""
    # a proxy-shaped file made directly (the proxy engine's own encode of ten minutes is slow)
    key = "b" * 64
    directory = cache / key
    directory.mkdir(parents=True)
    subprocess.run(
        [runtime.ffmpeg_path, "-y", "-v", "error", "-f", "lavfi"]
        + ["-i", "testsrc2=s=320x180:r=2", "-frames:v", "1200", "-c:v", "libx264"]
        + ["-bf", "0", "-g", "1", "-pix_fmt", "yuv420p", str(directory / "proxy.mp4")],
        check=True,
        capture_output=True,
    )
    facts = ProxyFacts.from_json(
        {**json.loads(PROXY_FACTS), "duration": 600.0, "frames": 1200, "width": 320, "height": 180}
    )
    assert facts is not None
    write_facts(directory, facts)
    entry = read_entry(directory)
    assert entry is not None

    film = ensure_filmstrip(tmp_path / "ten-minutes.mp4", entry, runtime=runtime)

    assert (film.interval, film.tiles, film.columns, film.rows) == (5, 120, 10, 12)
    assert probe_image(runtime, film.path) == [("mjpeg", 1600, 1080)]


PROXY_FACTS = json.dumps(
    {
        "proxy_version": 1,
        "duration": 1.0,
        "fps": {"num": 2, "den": 1},
        "vfr": False,
        "frames": 1,
        "width": 1,
        "height": 1,
        "source_width": 1,
        "source_height": 1,
        "rotation": None,
        "audio_codec": None,
        "encode_path": "cpu",
        "fallback_reason": None,
    }
)


def test_a_portrait_proxy_has_narrow_tiles(
    runtime: FfmpegRuntime, tmp_path: Path, cache: Path
) -> None:
    clip = signal_clip(runtime, tmp_path / "portrait.mp4", frames=300, size="360x640")
    entry = proxy_of(runtime, clip, cache)
    film = ensure_filmstrip(clip, entry, runtime=runtime)
    assert (film.tile_width, film.tile_height, film.tiles, film.rows) == (50, 90, 12, 2)
    assert (film.width, film.height) == (500, 180)
    assert probe_image(runtime, film.path) == [("mjpeg", 500, 180)]


def test_the_source_is_never_read(runtime: FfmpegRuntime, tmp_path: Path, cache: Path) -> None:
    clip = signal_clip(runtime, tmp_path / "gone.mp4", frames=75)
    entry = proxy_of(runtime, clip, cache)
    clip.unlink()  # the library is unmounted
    film = ensure_filmstrip(clip, entry, runtime=runtime)
    assert film.tiles == 3 and film.path.is_file()


# --------------------------------------------------------------------------- #
# idempotency and versions
# --------------------------------------------------------------------------- #


def test_a_recorded_filmstrip_costs_nothing(
    runtime: FfmpegRuntime, entry: ProxyEntry, tmp_path: Path
) -> None:
    first = ensure_filmstrip(tmp_path / "C0100.MP4", entry, runtime=runtime)
    spy = Spy(runtime)
    again = ensure_filmstrip(tmp_path / "C0100.MP4", entry, runtime=spy)  # type: ignore[arg-type]
    assert spy.log == []
    assert again.generated is False
    assert again.to_json() == first.to_json()
    assert lookup_filmstrip(entry) == again


def test_a_version_bump_rebuilds_the_sprite_and_never_the_proxy(
    runtime: FfmpegRuntime, entry: ProxyEntry, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ensure_filmstrip(tmp_path / "C0100.MP4", entry, runtime=runtime)
    proxy_before = (entry.proxy_path.read_bytes(), entry.proxy_path.stat().st_mtime_ns)
    monkeypatch.setattr(filmstrip_module, "FILMSTRIP_VERSION", FILMSTRIP_VERSION + 1)
    spy = Spy(runtime)
    assert lookup_filmstrip(entry) is None
    film = ensure_filmstrip(tmp_path / "C0100.MP4", entry, runtime=spy)  # type: ignore[arg-type]
    assert film.generated is True and film.version == FILMSTRIP_VERSION + 1
    assert facts_of(entry)["filmstrip"]["version"] == FILMSTRIP_VERSION + 1
    assert spy.calls("ffmpeg") == 1
    assert (entry.proxy_path.read_bytes(), entry.proxy_path.stat().st_mtime_ns) == proxy_before


def test_a_deleted_image_is_rebuilt(
    runtime: FfmpegRuntime, entry: ProxyEntry, tmp_path: Path
) -> None:
    ensure_filmstrip(tmp_path / "C0100.MP4", entry, runtime=runtime)
    (entry.directory / "filmstrip.jpg").unlink()
    assert lookup_filmstrip(entry) is None
    film = ensure_filmstrip(tmp_path / "C0100.MP4", entry, runtime=runtime)
    assert film.generated is True and film.path.is_file()


def test_the_proxy_is_not_touched_by_making_its_filmstrip(
    runtime: FfmpegRuntime, entry: ProxyEntry, tmp_path: Path
) -> None:
    before = (entry.proxy_path.read_bytes(), entry.proxy_path.stat().st_mtime_ns)
    ensure_filmstrip(tmp_path / "C0100.MP4", entry, runtime=runtime)
    assert (entry.proxy_path.read_bytes(), entry.proxy_path.stat().st_mtime_ns) == before
    assert sorted(p.name for p in entry.directory.iterdir()) == [
        "facts.json",
        "filmstrip.jpg",
        "proxy.mp4",
    ]


# --------------------------------------------------------------------------- #
# failures
# --------------------------------------------------------------------------- #


def assert_untouched(entry: ProxyEntry, cache: Path, facts: bytes, proxy: bytes) -> None:
    assert not (entry.directory / "filmstrip.jpg").exists()
    assert entry.facts_path.read_bytes() == facts
    assert entry.proxy_path.read_bytes() == proxy
    assert leftovers(cache) == []


def snapshot(entry: ProxyEntry) -> Tuple[bytes, bytes]:
    return entry.facts_path.read_bytes(), entry.proxy_path.read_bytes()


class Killed(Spy):
    """ffmpeg writes half a sprite and is killed."""

    def cut(self, args: List[str]) -> "subprocess.CompletedProcess[str]":
        Path(args[-1]).write_bytes(b"\xff\xd8 half a sprite")
        raise FfmpegError("Command exited -9: ffmpeg " + " ".join(args) + "\nstderr:\nKilled")


def test_a_killed_ffmpeg_leaves_nothing_and_the_next_run_builds_it(
    runtime: FfmpegRuntime, entry: ProxyEntry, cache: Path, tmp_path: Path
) -> None:
    facts, proxy = snapshot(entry)
    with pytest.raises(FilmstripError) as caught:
        ensure_filmstrip(tmp_path / "C0100.MP4", entry, runtime=Killed(runtime))  # type: ignore[arg-type]
    assert caught.value.clip == str(tmp_path / "C0100.MP4")
    assert "could not cut the filmstrip" in caught.value.reason
    assert_untouched(entry, cache, facts, proxy)

    film = ensure_filmstrip(tmp_path / "C0100.MP4", entry, runtime=runtime)  # not remembered
    assert film.generated is True


class WrongSize(Spy):
    """ffmpeg 'succeeds' but the sprite is 1600x180 instead of the planned size."""

    def cut(self, args: List[str]) -> "subprocess.CompletedProcess[str]":
        return self.inner.run(
            ["-v", "error", "-y", "-f", "lavfi", "-i", "color=c=gray:s=480x180", "-frames:v", "1"]
            + ["-f", "image2", "-update", "1", args[-1]]
        )


def test_a_sprite_of_the_wrong_size_is_refused_with_both_sizes(
    runtime: FfmpegRuntime, entry: ProxyEntry, cache: Path, tmp_path: Path
) -> None:
    facts, proxy = snapshot(entry)
    with pytest.raises(FilmstripError) as caught:
        ensure_filmstrip(tmp_path / "C0100.MP4", entry, runtime=WrongSize(runtime))  # type: ignore[arg-type]
    assert "is 480x180, expected 480x90" in caught.value.reason
    assert_untouched(entry, cache, facts, proxy)


class Silent(Spy):
    """ffmpeg exits 0 and writes nothing."""

    def cut(self, args: List[str]) -> "subprocess.CompletedProcess[str]":
        return subprocess.CompletedProcess(args, 0, "", "")


def test_an_ffmpeg_that_writes_nothing_is_refused(
    runtime: FfmpegRuntime, entry: ProxyEntry, cache: Path, tmp_path: Path
) -> None:
    facts, proxy = snapshot(entry)
    with pytest.raises(FilmstripError, match="wrote no filmstrip"):
        ensure_filmstrip(tmp_path / "C0100.MP4", entry, runtime=Silent(runtime))  # type: ignore[arg-type]
    assert_untouched(entry, cache, facts, proxy)


class Full(Spy):
    """The cache disk is full."""

    def cut(self, args: List[str]) -> "subprocess.CompletedProcess[str]":
        raise FfmpegError(
            "Command exited 234: ffmpeg x\nstderr:\nError writing trailer: No space left on device"
        )


def test_a_full_disk_is_the_caches_error_not_the_clips(
    runtime: FfmpegRuntime, entry: ProxyEntry, cache: Path, tmp_path: Path
) -> None:
    facts, proxy = snapshot(entry)
    with pytest.raises(ProxyCacheError, match="No space left on device"):
        ensure_filmstrip(tmp_path / "C0100.MP4", entry, runtime=Full(runtime))  # type: ignore[arg-type]
    assert_untouched(entry, cache, facts, proxy)


@pytest.mark.parametrize("content", ["this is not json", "[1, 2, 3]", '"text"', ""])
def test_unreadable_facts_fail_the_filmstrip_and_are_left_as_they_were(
    runtime: FfmpegRuntime, entry: ProxyEntry, cache: Path, tmp_path: Path, content: str
) -> None:
    entry.facts_path.write_text(content, encoding="utf-8")
    facts, proxy = snapshot(entry)
    spy = Spy(runtime)
    with pytest.raises(FilmstripError) as caught:
        ensure_filmstrip(tmp_path / "C0100.MP4", entry, runtime=spy)  # type: ignore[arg-type]
    assert caught.value.clip == str(tmp_path / "C0100.MP4")
    assert "facts" in caught.value.reason
    assert spy.log == []  # refused before any work
    assert_untouched(entry, cache, facts, proxy)


def test_a_corrupt_proxy_names_the_probe_failure(
    runtime: FfmpegRuntime, entry: ProxyEntry, cache: Path, tmp_path: Path
) -> None:
    entry.proxy_path.write_bytes(b"this is not an mp4 file at all")
    facts, proxy = snapshot(entry)
    with pytest.raises(FilmstripError, match="ffprobe could not read the proxy"):
        ensure_filmstrip(tmp_path / "C0100.MP4", entry, runtime=runtime)
    assert_untouched(entry, cache, facts, proxy)


def test_keyframes_further_apart_than_the_interval_are_refused(
    runtime: FfmpegRuntime, entry: ProxyEntry, cache: Path, tmp_path: Path
) -> None:
    longgop = tmp_path / "longgop.mp4"
    subprocess.run(
        [runtime.ffmpeg_path, "-y", "-v", "error", "-i", str(entry.proxy_path)]
        + ["-c:v", "libx264", "-g", "100", "-keyint_min", "100", "-sc_threshold", "0", "-an"]
        + [str(longgop)],
        check=True,
        capture_output=True,
    )
    entry.proxy_path.write_bytes(longgop.read_bytes())
    facts, proxy = snapshot(entry)
    with pytest.raises(FilmstripError, match="tile 1 would show the same keyframe as tile 0"):
        ensure_filmstrip(tmp_path / "C0100.MP4", entry, runtime=runtime)
    assert_untouched(entry, cache, facts, proxy)


class Crash(BaseException):
    """The process dies (a kill -9 cannot be caught; this is not an ``Exception``)."""


def test_a_crash_between_the_image_and_the_record_is_rebuilt_next_time(
    runtime: FfmpegRuntime,
    entry: ProxyEntry,
    cache: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    facts = entry.facts_path.read_bytes()
    real_replace = os.replace
    calls: List[str] = []

    def dying_replace(src: Any, dst: Any) -> None:
        calls.append(Path(dst).name)
        if Path(dst).name == "facts.json":
            raise Crash
        real_replace(src, dst)

    monkeypatch.setattr(filmstrip_module.os, "replace", dying_replace)
    with pytest.raises(Crash):
        ensure_filmstrip(tmp_path / "C0100.MP4", entry, runtime=runtime)
    monkeypatch.undo()

    assert calls == ["filmstrip.jpg", "facts.json"]
    assert (entry.directory / "filmstrip.jpg").is_file()  # the image landed first ...
    assert entry.facts_path.read_bytes() == facts  # ... and nothing records it
    assert "filmstrip" not in facts_of(entry)
    assert lookup_filmstrip(entry) is None  # so it counts as absent

    film = ensure_filmstrip(tmp_path / "C0100.MP4", entry, runtime=runtime)
    assert film.generated is True and facts_of(entry)["filmstrip"]["tiles"] == 3
    assert leftovers(cache) == []


def test_a_failure_to_record_removes_the_image_it_just_moved(
    runtime: FfmpegRuntime,
    entry: ProxyEntry,
    cache: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    facts, proxy = snapshot(entry)
    real_replace = os.replace

    def failing_replace(src: Any, dst: Any) -> None:
        if Path(dst).name == "facts.json":
            raise OSError(28, "No space left on device")
        real_replace(src, dst)

    monkeypatch.setattr(filmstrip_module.os, "replace", failing_replace)
    with pytest.raises(ProxyCacheError, match="No space left on device"):
        ensure_filmstrip(tmp_path / "C0100.MP4", entry, runtime=runtime)
    assert_untouched(entry, cache, facts, proxy)
