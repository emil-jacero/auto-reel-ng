"""Tests for the filmstrip's pure parts: the plan, the keyframe choice, the ffmpeg arguments, the
record and its lookup (``clip-filmstrips``). Real encodes are in ``test_proxies_filmstrip_ffmpeg.py``.
"""

from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path
from typing import List, Optional

import pytest

from auto_reel_ng.errors import EngineError, FfmpegError, FilmstripError, ProxyCacheError
from auto_reel_ng.proxies import ProxyEntry, ProxyFacts
from auto_reel_ng.proxies import filmstrip as filmstrip_module
from auto_reel_ng.proxies import proxy_key
from auto_reel_ng.proxies.filmstrip import (
    FILMSTRIP_VERSION,
    Filmstrip,
    ensure_filmstrip,
    filmstrip_args,
    jpeg_size,
    keyframe_ordinals,
    lookup_filmstrip,
    plan,
)

# --------------------------------------------------------------------------- #
# the error
# --------------------------------------------------------------------------- #


def test_a_filmstrip_error_names_the_clip_and_the_cause() -> None:
    error = FilmstripError("/lib/C0047.MP4", "no keyframe")
    assert isinstance(error, EngineError)
    assert not isinstance(error, ProxyCacheError)
    assert (error.clip, error.reason) == ("/lib/C0047.MP4", "no keyframe")
    assert str(error) == "/lib/C0047.MP4: no keyframe"


# --------------------------------------------------------------------------- #
# the plan
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("width", "height", "tile_width"),
    [(960, 540, 160), (540, 960, 50), (640, 360, 160), (720, 540, 120), (540, 540, 90)],
)
def test_a_tile_is_90_px_high_and_as_wide_as_the_shape_gives(
    width: int, height: int, tile_width: int
) -> None:
    layout = plan(25.0, width, height)
    assert (layout.tile_width, layout.tile_height) == (tile_width, 90)
    assert layout.tile_width % 2 == 0


@pytest.mark.parametrize(
    ("duration", "interval", "tiles", "columns", "rows"),
    [
        (0.04, 1, 1, 1, 1),  # a single frame
        (0.48, 1, 1, 1, 1),  # C0047
        (1.0, 1, 1, 1, 1),
        (1.04, 1, 2, 2, 1),
        (25.0, 1, 25, 10, 3),
        (25.025, 1, 26, 10, 3),
        (100.0, 1, 100, 10, 10),
        (120.0, 1, 120, 10, 12),  # exactly 120 tiles at one second
        (120.5, 2, 61, 10, 7),  # one over: the interval widens
        (130.0, 2, 65, 10, 7),
        (3720.0, 31, 120, 10, 12),  # 62 minutes
    ],
)
def test_the_interval_and_the_tile_count_follow_the_duration(
    duration: float, interval: int, tiles: int, columns: int, rows: int
) -> None:
    layout = plan(duration, 960, 540)
    assert (layout.interval, layout.tiles, layout.columns, layout.rows) == (
        interval,
        tiles,
        columns,
        rows,
    )
    assert layout.tiles <= 120


def test_the_sprite_size_is_the_grid_times_the_tile() -> None:
    landscape = plan(25.0, 960, 540)
    assert (landscape.width, landscape.height) == (1600, 270)
    assert (plan(130.0, 960, 540).width, plan(130.0, 960, 540).height) == (1600, 630)
    portrait = plan(12.0, 540, 960)
    assert (portrait.width, portrait.height) == (500, 180)


@pytest.mark.parametrize("duration", [0.0, -1.0, float("nan"), float("inf")])
def test_a_duration_that_is_not_positive_and_finite_is_refused(duration: float) -> None:
    with pytest.raises(ValueError, match="duration"):
        plan(duration, 960, 540)


def test_a_proxy_without_a_size_is_refused() -> None:
    with pytest.raises(ValueError, match="size"):
        plan(10.0, 0, 540)


# --------------------------------------------------------------------------- #
# which keyframe each tile shows
# --------------------------------------------------------------------------- #


def every(gap: float, until: float) -> List[float]:
    """Keyframe times ``0, gap, 2 gap, ...`` before ``until``."""
    count = math.ceil(until / gap - 1e-9)
    return [round(i * gap, 6) for i in range(count)]


def test_a_tile_is_the_latest_keyframe_at_or_before_its_second() -> None:
    times = every(0.48, 5.0)  # 0, .48, .96, 1.44, 1.92, 2.4, 2.88, 3.36, 3.84, 4.32, 4.8
    layout = plan(5.04, 960, 540)
    assert layout.tiles == 6
    # second 1 -> .96 (2); 2 -> 1.92 (4); 3 -> 2.88 (6); 4 -> 3.84 (8); 5 -> 4.8 (10)
    assert keyframe_ordinals(times, layout) == [0, 2, 4, 6, 8, 10]


def test_a_keyframe_exactly_on_a_second_is_that_seconds_tile() -> None:
    times = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5]
    assert keyframe_ordinals(times, plan(3.0, 960, 540)) == [0, 2, 4]


def test_a_clip_with_one_keyframe_is_one_tile_of_its_first_frame() -> None:
    assert keyframe_ordinals([0.0], plan(0.48, 960, 540)) == [0]


def test_a_wider_interval_picks_from_its_own_seconds() -> None:
    layout = plan(130.0, 960, 540)
    assert layout.interval == 2
    ordinals = keyframe_ordinals(every(0.5, 130.0), layout)
    assert len(ordinals) == 65
    assert ordinals[:3] == [0, 4, 8]  # 0 s, 2 s, 4 s at a keyframe every half second


def test_a_stream_that_starts_after_zero_still_gets_its_first_keyframe() -> None:
    times = [0.023, 0.523, 1.023]
    assert keyframe_ordinals(times, plan(1.5, 960, 540)) == [0, 1]


def test_the_last_tile_falls_in_the_tail_after_the_last_keyframe() -> None:
    # 25.025 s at 29.97 fps: a keyframe every 15 frames, the last at 24.524 s; tile 25 is at 25.0 s
    times = every(15 * 1001 / 30000, 25.025)
    layout = plan(25.025, 960, 540)
    ordinals = keyframe_ordinals(times, layout)
    assert layout.tiles == 26 and ordinals[-1] == len(times) - 1


def test_keyframes_further_apart_than_the_interval_are_refused_naming_the_tile() -> None:
    with pytest.raises(ValueError, match="tile 1 would show the same keyframe as tile 0"):
        keyframe_ordinals([0.0, 1.9], plan(2.5, 960, 540))


def test_a_proxy_without_keyframes_is_refused() -> None:
    with pytest.raises(ValueError, match="no keyframe"):
        keyframe_ordinals([], plan(2.0, 960, 540))


def test_keyframes_out_of_order_are_refused() -> None:
    with pytest.raises(ValueError, match="time order"):
        keyframe_ordinals([0.0, 1.0, 0.5], plan(2.0, 960, 540))


# --------------------------------------------------------------------------- #
# the ffmpeg arguments (golden)
# --------------------------------------------------------------------------- #


def args_for(duration: float, width: int, height: int, ordinals: List[int]) -> List[str]:
    return filmstrip_args(
        Path("/c/proxy.mp4"), plan(duration, width, height), ordinals, Path("/b/f.jpg")
    )


def test_the_arguments_for_a_landscape_clip() -> None:
    assert args_for(25.0, 960, 540, list(range(25))) == [
        "-hide_banner",
        "-nostdin",
        "-v",
        "error",
        "-y",
        "-skip_frame",
        "nokey",
        "-i",
        "/c/proxy.mp4",
        "-map",
        "0:v:0",
        "-an",
        "-sn",
        "-dn",
        "-vf",
        "select="
        + "("
        + "+".join(f"eq(n\\,{i})" for i in range(16))
        + ")+("
        + "+".join(f"eq(n\\,{i})" for i in range(16, 25))
        + "),"
        "scale=160:90:flags=bicubic,tile=10x3:nb_frames=25",
        "-frames:v",
        "1",
        "-c:v",
        "mjpeg",
        "-q:v",
        "5",
        "-f",
        "image2",
        "-update",
        "1",
        "/b/f.jpg",
    ]


def test_the_filter_of_a_portrait_clip_has_narrow_tiles() -> None:
    args = args_for(12.0, 540, 960, list(range(12)))
    assert args[args.index("-vf") + 1].endswith("scale=50:90:flags=bicubic,tile=10x2:nb_frames=12")


def test_the_filter_of_a_three_tile_clip_is_one_row() -> None:
    args = args_for(2.52, 960, 540, [0, 2, 4])
    assert args[args.index("-vf") + 1] == (
        "select=eq(n\\,0)+eq(n\\,2)+eq(n\\,4),scale=160:90:flags=bicubic,tile=3x1:nb_frames=3"
    )


@pytest.mark.parametrize("tiles", [1, 16, 17, 100, 109, 120])
def test_no_select_sum_has_more_terms_than_ffmpeg_nests(tiles: int) -> None:
    """ffmpeg's expression parser fails ("Cannot allocate memory") past about 100 nested terms,
    which the dogfood run met on a 109-tile clip: no sum may hold more than ``SUM_TERMS``."""
    args = args_for(float(tiles), 960, 540, list(range(tiles)))
    expression = args[args.index("-vf") + 1].split(",scale=")[0].removeprefix("select=")
    stack = [1]  # the terms summed so far at each open level
    widest = calls = index = 0
    while index < len(expression):
        if expression.startswith("eq(", index):  # a term: skip its own parentheses
            index = expression.index(")", index) + 1
            calls += 1
            continue
        char = expression[index]
        if char == "(":
            stack.append(1)
        elif char == ")":
            widest = max(widest, stack.pop())
        elif char == "+":
            stack[-1] += 1
        index += 1
    widest = max(widest, stack.pop())
    assert not stack
    assert calls == tiles
    assert widest <= 50  # ffmpeg gives up near 100


def test_the_sprite_decodes_keyframes_only_and_never_audio() -> None:
    args = args_for(2.52, 960, 540, [0, 2, 4])
    assert args[args.index("-skip_frame") + 1] == "nokey"
    assert "-an" in args and "-sn" in args and "-dn" in args


# --------------------------------------------------------------------------- #
# the record and its lookup
# --------------------------------------------------------------------------- #

FACTS = {
    "proxy_version": 1,
    "duration": 25.0,
    "fps": {"num": 25, "den": 1},
    "vfr": False,
    "frames": 625,
    "width": 960,
    "height": 540,
    "source_width": 1920,
    "source_height": 1080,
    "rotation": None,
    "audio_codec": "aac",
    "encode_path": "cpu",
    "fallback_reason": None,
}

RECORD = {
    "version": FILMSTRIP_VERSION,
    "tiles": 25,
    "interval": 1,
    "columns": 10,
    "rows": 3,
    "tile_width": 160,
    "tile_height": 90,
    "width": 1600,
    "height": 270,
    "bytes": 10,
}


def entry_in(tmp_path: Path, facts: object, *, jpeg: Optional[bytes] = b"jpeg bytes") -> ProxyEntry:
    directory = tmp_path / ("a" * 64)
    directory.mkdir()
    (directory / "proxy.mp4").write_bytes(b"proxy")
    (directory / "facts.json").write_text(json.dumps(facts), encoding="utf-8")
    if jpeg is not None:
        (directory / "filmstrip.jpg").write_bytes(jpeg)
    parsed = ProxyFacts.from_json(FACTS)
    assert parsed is not None
    return ProxyEntry(
        key=directory.name,
        directory=directory,
        proxy_path=directory / "proxy.mp4",
        facts_path=directory / "facts.json",
        facts=parsed,
    )


def test_a_recorded_filmstrip_with_its_file_is_found(tmp_path: Path) -> None:
    entry = entry_in(tmp_path, {**FACTS, "filmstrip": RECORD})
    found = lookup_filmstrip(entry)
    assert found is not None
    assert found.to_json() == RECORD
    assert found.path == entry.directory / "filmstrip.jpg"
    assert found.generated is False


def test_the_facts_reader_still_accepts_an_entry_with_a_filmstrip(tmp_path: Path) -> None:
    entry = entry_in(tmp_path, {**FACTS, "filmstrip": RECORD})
    assert ProxyFacts.from_json(json.loads(entry.facts_path.read_text())) == entry.facts


def test_an_entry_without_a_record_has_no_filmstrip(tmp_path: Path) -> None:
    assert lookup_filmstrip(entry_in(tmp_path, FACTS)) is None


def test_a_record_without_its_file_is_absent(tmp_path: Path) -> None:
    assert lookup_filmstrip(entry_in(tmp_path, {**FACTS, "filmstrip": RECORD}, jpeg=None)) is None


def test_a_file_of_another_size_than_recorded_is_absent(tmp_path: Path) -> None:
    entry = entry_in(tmp_path, {**FACTS, "filmstrip": RECORD}, jpeg=b"a longer jpeg than recorded")
    assert lookup_filmstrip(entry) is None


def test_a_record_from_another_version_is_absent(tmp_path: Path) -> None:
    entry = entry_in(tmp_path, {**FACTS, "filmstrip": {**RECORD, "version": FILMSTRIP_VERSION - 1}})
    assert lookup_filmstrip(entry) is None


@pytest.mark.parametrize(
    "broken",
    [
        {"tiles": True},  # a bool is not a number
        {"tiles": 25.0},
        {"tiles": 0},
        {"bytes": "11"},
        {"columns": None},
    ],
)
def test_a_damaged_record_is_absent_never_defaulted(tmp_path: Path, broken: dict) -> None:
    assert (
        lookup_filmstrip(entry_in(tmp_path, {**FACTS, "filmstrip": {**RECORD, **broken}})) is None
    )


def test_a_record_with_a_missing_member_is_absent(tmp_path: Path) -> None:
    short = {k: v for k, v in RECORD.items() if k != "interval"}
    assert lookup_filmstrip(entry_in(tmp_path, {**FACTS, "filmstrip": short})) is None


def test_unreadable_facts_are_absent_not_an_error(tmp_path: Path) -> None:
    entry = entry_in(tmp_path, FACTS)
    entry.facts_path.write_text("not json", encoding="utf-8")
    assert lookup_filmstrip(entry) is None
    entry.facts_path.write_text("[1, 2]", encoding="utf-8")
    assert lookup_filmstrip(entry) is None


def test_the_record_round_trips() -> None:
    film = Filmstrip.from_json(RECORD, Path("/x/filmstrip.jpg"))
    assert film is not None and film.to_json() == RECORD


def test_the_filmstrip_version_is_not_part_of_the_proxy_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clip = tmp_path / "C0001.MP4"
    clip.write_bytes(b"clip")
    before = proxy_key(clip)
    monkeypatch.setattr(filmstrip_module, "FILMSTRIP_VERSION", FILMSTRIP_VERSION + 1)
    assert proxy_key(clip) == before


# --------------------------------------------------------------------------- #
# reading the sprite's size back
# --------------------------------------------------------------------------- #


def jpeg(width: int, height: int, *, before: bytes = b"", marker: int = 0xC0) -> bytes:
    """The head of a JPEG: SOI, optional segments, a frame header, then the scan marker."""
    frame = bytes([8]) + height.to_bytes(2, "big") + width.to_bytes(2, "big") + bytes([3])
    frame += bytes([1, 0x22, 0, 2, 0x11, 1, 3, 0x11, 1])
    segment = bytes([0xFF, marker]) + (len(frame) + 2).to_bytes(2, "big") + frame
    return b"\xff\xd8" + before + segment + b"\xff\xda\x00\x02"


def test_the_size_is_read_from_the_frame_header() -> None:
    assert jpeg_size(jpeg(1600, 270)) == (1600, 270)
    assert jpeg_size(jpeg(500, 180, marker=0xC2)) == (500, 180)  # progressive


def test_segments_before_the_frame_header_are_skipped() -> None:
    app0 = b"\xff\xe0" + (16).to_bytes(2, "big") + b"JFIF\x00" + bytes(9)
    dht = b"\xff\xc4" + (5).to_bytes(2, "big") + bytes(3)  # a Huffman table is not a frame
    assert jpeg_size(jpeg(160, 90, before=app0 + dht)) == (160, 90)


@pytest.mark.parametrize(
    "data",
    [b"", b"\x89PNG\r\n\x1a\n", b"\xff\xd8", b"\xff\xd8\xff\xda\x00\x02", jpeg(1, 1)[:8]],
)
def test_a_file_without_a_frame_header_has_no_size(data: bytes) -> None:
    assert jpeg_size(data) is None


# --------------------------------------------------------------------------- #
# what the probe of the proxy may say
# --------------------------------------------------------------------------- #


class CannedProbe:
    """A runtime whose one ffprobe answers ``stdout`` (or fails); ffmpeg must never be started."""

    def __init__(self, stdout: str = "", error: Optional[Exception] = None) -> None:
        self.stdout, self.error, self.ffprobes = stdout, error, 0

    def with_timeout(self, seconds: float) -> "CannedProbe":
        assert seconds > 0
        return self

    def run_ffprobe(self, args: List[str]) -> subprocess.CompletedProcess[str]:
        self.ffprobes += 1
        if self.error is not None:
            raise self.error
        return subprocess.CompletedProcess(args, 0, self.stdout, "")

    def run(self, args: List[str]) -> subprocess.CompletedProcess[str]:
        raise AssertionError("ffmpeg must not start after a refused probe")


STREAM = "width=960|height=540|duration=25.000000"
KEY = "pts_time=0.000000|flags=K__"


@pytest.mark.parametrize(
    ("stdout", "reason"),
    [
        (STREAM + "\n" + "\n".join(f"pts_time={i}.0|flags=K__" for i in range(25)), None),
        # ^ control: a good probe passes (and then runs ffmpeg, which this runtime refuses)
        ("width=960|height=540|duration=N/A\n" + KEY, "no usable video stream"),
        ("width=960|height=540\n" + KEY, "no usable video stream"),
        (KEY, "no usable video stream"),  # no stream at all
        ("width=960|height=540|duration=0.000000\n" + KEY, "no usable duration"),
        ("width=960|height=540|duration=-3.0\n" + KEY, "no usable duration"),
        ("width=960|height=540|duration=nan\n" + KEY, "no usable duration"),
        (f"{STREAM}\npts_time=0.000000|flags=___", "no keyframe"),
        (f"{STREAM}\npts_time=N/A|flags=K__", "keyframe of the proxy has no time"),
        (f"{STREAM}\nflags=K__", "keyframe of the proxy has no time"),
    ],
)
def test_a_probe_that_cannot_give_the_facts_fails_the_filmstrip_with_no_default(
    tmp_path: Path, stdout: str, reason: Optional[str]
) -> None:
    entry = entry_in(tmp_path, FACTS, jpeg=None)
    probe = CannedProbe(stdout)
    if reason is None:
        with pytest.raises(AssertionError, match="ffmpeg must not start"):
            ensure_filmstrip(Path("/lib/C0001.MP4"), entry, runtime=probe)  # type: ignore[arg-type]
        return
    with pytest.raises(FilmstripError) as caught:
        ensure_filmstrip(Path("/lib/C0001.MP4"), entry, runtime=probe)  # type: ignore[arg-type]
    assert reason in caught.value.reason and caught.value.clip == "/lib/C0001.MP4"
    assert probe.ffprobes == 1
    assert not (entry.directory / "filmstrip.jpg").exists()


def test_a_failing_ffprobe_is_named(tmp_path: Path) -> None:
    entry = entry_in(tmp_path, FACTS, jpeg=None)
    failing = CannedProbe(error=FfmpegError("Command exited 1: ffprobe x\nstderr:\nnope"))
    with pytest.raises(FilmstripError, match="ffprobe could not read the proxy"):
        ensure_filmstrip(Path("/lib/C0001.MP4"), entry, runtime=failing)  # type: ignore[arg-type]
