"""Clip filmstrips (D-21, ``clip-filmstrips``): one JPEG sprite per proxied clip.

A filmstrip is cut from the clip's finished proxy and from nothing else: the timeline draws a
clip's picture from it without decoding any video. It lives in the clip's proxy cache entry as
``filmstrip.jpg``, and its tile geometry is recorded in the entry's ``facts.json`` under a
``filmstrip`` object, so a reader places tile ``k`` from the record alone.

The tiles are chosen from the proxy's own keyframe list, not resampled by the ``fps`` filter.
That filter hands the encoder no frame at all for a clip with a single keyframe (the
research's lost sprite of a 0.48 s clip) and drops the last tile of clips whose tail is
shorter than a keyframe gap, so the tile count could not be trusted. Here tile ``k`` is the
latest keyframe at or before ``k x interval`` seconds and the count is
``ceil(duration / interval)``, exact by construction.

The sprite is built in the cache's hidden build directory (the kind its stale sweep already
removes), verified, and renamed into the entry before the record that describes it, so a
reader never sees a record without its file. A failure never touches the proxy and is not
remembered.
"""

from __future__ import annotations

import bisect
import json
import logging
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional, Sequence

from ..errors import FfmpegError, FilmstripError, ProxyCacheError
from ..ffmpeg.runtime import FfmpegRuntime
from . import cache, spec
from .cache import ProxyEntry

logger = logging.getLogger(__name__)

#: Bump whenever the tile spec or the extraction changes the sprite for the same proxy. Not part
#: of the proxy key: a bump rebuilds sprites from the proxies on disk and re-encodes none.
#: 1: the first format (90 px tiles, 10 columns, at most 120 tiles, keyframe selection).
FILMSTRIP_VERSION = 1

#: Every tile is this many pixels high; the width follows the proxy's displayed shape.
TILE_HEIGHT = 90
#: The grid has at most this many columns, filled left to right then top to bottom.
COLUMNS = 10
#: A filmstrip never has more tiles than this; a longer clip gets a wider interval.
MAX_TILES = 120
#: ``-q:v`` of the JPEG (the same quality as the D-11 thumbnails).
JPEG_QSCALE = 5
#: Most terms of one ``select`` sum (ffmpeg's expression parser nests a level per term).
SUM_TERMS = 16
#: Seconds the sprite's ffmpeg run is given (about 7,200 keyframes of a 62-minute proxy decode in
#: well under a minute; a hung process is killed).
FILMSTRIP_TIMEOUT_S = 600.0


@dataclass(frozen=True)
class FilmstripPlan:
    """The geometry of one clip's sprite, from its duration and displayed shape."""

    #: Seconds between tiles (whole seconds, at least 1).
    interval: int
    tiles: int
    tile_width: int
    tile_height: int
    columns: int
    rows: int

    @property
    def width(self) -> int:
        """The sprite's width in pixels."""
        return self.columns * self.tile_width

    @property
    def height(self) -> int:
        """The sprite's height in pixels."""
        return self.rows * self.tile_height


@dataclass(frozen=True)
class Filmstrip:  # pylint: disable=too-many-instance-attributes
    """A recorded filmstrip: the ``filmstrip`` object of ``facts.json`` and where its image is."""

    version: int
    tiles: int
    interval: int
    columns: int
    rows: int
    tile_width: int
    tile_height: int
    #: The JPEG's size in pixels.
    width: int
    height: int
    #: The JPEG's size in bytes.
    bytes: int
    path: Path
    #: True when the call that returned this record built the sprite; False for a recorded one.
    generated: bool = False

    def to_json(self) -> dict[str, int]:
        """The ``filmstrip`` object as ``facts.json`` holds it."""
        return {
            "version": self.version,
            "tiles": self.tiles,
            "interval": self.interval,
            "columns": self.columns,
            "rows": self.rows,
            "tile_width": self.tile_width,
            "tile_height": self.tile_height,
            "width": self.width,
            "height": self.height,
            "bytes": self.bytes,
        }

    @classmethod
    def from_json(cls, document: object, path: Path) -> Optional[Filmstrip]:
        """The record in ``document``, or ``None`` when it is not a complete, well-typed object.

        Strict, as for the proxy's facts: a missing member, a wrong type (a bool is not a
        number) or a non-positive number is absence, never a default.
        """
        if not isinstance(document, dict):
            return None
        try:
            values = {name: document[name] for name in _MEMBERS}
        except KeyError:
            return None
        for value in values.values():
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                return None
        return cls(path=path, **values)


#: The members of the ``filmstrip`` object, in the order ``to_json`` writes them.
_MEMBERS = (
    "version",
    "tiles",
    "interval",
    "columns",
    "rows",
    "tile_width",
    "tile_height",
    "width",
    "height",
    "bytes",
)


def plan(duration: float, width: int, height: int) -> FilmstripPlan:
    """The sprite's geometry for a proxy of ``duration`` seconds and ``width`` x ``height``.

    ``interval = max(1, ceil(duration / 120))`` whole seconds, ``tiles = ceil(duration /
    interval)`` and never fewer than 1 (a clip of one second or less is one tile), tiles 90 px
    high and as wide as the shape gives at that height, rounded to an even width.

    Raises:
        ValueError: ``duration`` is not a positive finite number, or a side is not positive.
    """
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError(f"the proxy has no usable duration ({duration})")
    if width <= 0 or height <= 0:
        raise ValueError(f"the proxy has no usable size ({width}x{height})")
    interval = max(1, math.ceil(duration / MAX_TILES))
    tiles = max(1, math.ceil(duration / interval))
    tile_width = max(2, round(TILE_HEIGHT * width / height / 2) * 2)
    columns = min(COLUMNS, tiles)
    return FilmstripPlan(
        interval=interval,
        tiles=tiles,
        tile_width=tile_width,
        tile_height=TILE_HEIGHT,
        columns=columns,
        rows=math.ceil(tiles / columns),
    )


def keyframe_ordinals(times: Sequence[float], layout: FilmstripPlan) -> List[int]:
    """For each tile, the position among the proxy's keyframes of the frame it shows.

    ``times`` are the keyframes' presentation times in order. Tile ``k`` is the latest
    keyframe at or before ``k x interval`` seconds, or the first keyframe when none is (which
    only the first tile can meet, for a stream that starts late).

    Raises:
        ValueError: there is no keyframe, the times do not increase, or two tiles would need
            the same keyframe (the keyframes are further apart than the interval), so a tile
            would have to be padded or repeated.
    """
    if not times:
        raise ValueError("the proxy has no keyframe")
    if any(later < earlier for earlier, later in zip(times, times[1:])):
        raise ValueError("the proxy's keyframes are not in time order")
    ordinals: List[int] = []
    for tile in range(layout.tiles):
        at = tile * layout.interval
        ordinal = max(0, bisect.bisect_right(times, at) - 1)
        if ordinals and ordinal <= ordinals[-1]:
            raise ValueError(
                f"tile {tile} would show the same keyframe as tile {tile - 1}: the proxy's "
                f"keyframes are further apart than the {layout.interval} s between tiles"
            )
        ordinals.append(ordinal)
    return ordinals


def filmstrip_args(
    proxy: Path, layout: FilmstripPlan, ordinals: Sequence[int], output: Path
) -> List[str]:
    """The ffmpeg arguments that write the sprite of ``proxy`` to ``output``.

    Only keyframes are decoded (``-skip_frame nokey``), so ``n`` in ``select`` counts the
    proxy's keyframes in order, and ``ordinals`` (from :func:`keyframe_ordinals`) name the
    ones that become tiles (see :func:`_any_of` for how they are written). ``tile`` closes the
    grid at the planned count. ``-update 1`` makes ``image2`` write ``output`` literally, so a
    ``%`` in the cache path is never a pattern.
    """
    chosen = _any_of(ordinals)
    filters = (
        f"select={chosen},"
        f"scale={layout.tile_width}:{layout.tile_height}:flags=bicubic,"
        f"tile={layout.columns}x{layout.rows}:nb_frames={layout.tiles}"
    )
    return [
        "-hide_banner",
        "-nostdin",
        "-v",
        "error",
        "-y",
        "-skip_frame",
        "nokey",
        "-i",
        str(proxy),
        "-map",
        "0:v:0",
        "-an",
        "-sn",
        "-dn",
        "-vf",
        filters,
        "-frames:v",
        "1",
        "-c:v",
        "mjpeg",
        "-q:v",
        str(JPEG_QSCALE),
        "-f",
        "image2",
        "-update",
        "1",
        str(output),
    ]


def _any_of(ordinals: Sequence[int]) -> str:
    """The ``select`` expression that is true for the frames numbered ``ordinals``.

    ffmpeg's expression parser nests one level per term of a flat sum and gives up
    (``Cannot allocate memory``) after about a hundred, which a clip of 100 tiles or more
    would reach. So at most :data:`SUM_TERMS` terms are summed at one level, in parentheses
    when there are more groups than that: two levels cover 256 tiles, :data:`MAX_TILES` is 120.
    """
    terms = [f"eq(n\\,{ordinal})" for ordinal in ordinals]
    while len(terms) > SUM_TERMS:
        terms = [
            "(" + "+".join(terms[i : i + SUM_TERMS]) + ")" for i in range(0, len(terms), SUM_TERMS)
        ]
    return "+".join(terms)


def lookup_filmstrip(entry: ProxyEntry) -> Optional[Filmstrip]:
    """The entry's recorded filmstrip, or ``None``; one ``stat`` and one JSON read, no process.

    The record counts only when its ``version`` is the engine's current
    :data:`FILMSTRIP_VERSION` and ``filmstrip.jpg`` exists with the recorded size: a record
    without its file, or a file the record does not describe, is an absent filmstrip.
    """
    path = entry.directory / spec.FILMSTRIP_FILENAME
    try:
        document = json.loads(entry.facts_path.read_text(encoding="utf-8"))
        recorded = Filmstrip.from_json(document.get("filmstrip"), path)
        if recorded is None or recorded.version != FILMSTRIP_VERSION:
            return None
        if not path.is_file() or path.stat().st_size != recorded.bytes:
            return None
    except (OSError, ValueError, AttributeError):  # unreadable, not JSON, or not an object
        return None
    return recorded


def ensure_filmstrip(  # pylint: disable=too-many-locals
    clip_path: Path, entry: ProxyEntry, *, runtime: FfmpegRuntime
) -> Filmstrip:
    """The clip's filmstrip, building and recording it first when it is not recorded.

    A recorded filmstrip returns without ffprobe or ffmpeg. Otherwise the finished proxy is
    probed (video-stream duration, size, keyframe times), the sprite is cut into the cache's
    hidden build directory, verified against its plan, renamed into ``entry`` as
    ``filmstrip.jpg``, and only then recorded in ``facts.json``. ``clip_path`` only names the
    clip in a failure: the source is never read.

    Raises:
        FilmstripError: the proxy cannot be probed or planned, ffmpeg fails, the image is not
            the planned size, or ``facts.json`` is not a JSON object. The proxy and
            ``facts.json`` are left as they were and nothing is left behind.
        ProxyCacheError: the cache directory cannot be written, or is full.
    """
    recorded = lookup_filmstrip(entry)
    if recorded is not None:
        return recorded
    clip = str(clip_path)
    _facts_object(entry, clip)  # fail before the work when the record could not be written
    duration, width, height, keyframes = _probe_proxy(
        entry.proxy_path, runtime.with_timeout(spec.PROXY_PROBE_TIMEOUT_S), clip
    )
    try:
        layout = plan(duration, width, height)
        ordinals = keyframe_ordinals(keyframes, layout)
    except ValueError as exc:
        raise FilmstripError(clip, str(exc)) from exc

    cache_dir = entry.directory.parent
    part = cache.new_part_dir(cache_dir, entry.key)
    try:
        sprite = part / spec.FILMSTRIP_FILENAME
        _cut(
            filmstrip_args(entry.proxy_path, layout, ordinals, sprite),
            runtime.with_timeout(FILMSTRIP_TIMEOUT_S),
            sprite,
            clip,
        )
        _verify(sprite, layout, clip)
        return _publish(entry, part, sprite, layout, clip)
    finally:
        cache.discard(part)


def _publish(
    entry: ProxyEntry, part: Path, sprite: Path, layout: FilmstripPlan, clip: str
) -> Filmstrip:
    """Rename the verified sprite into the entry, then record it in ``facts.json``."""
    target = entry.directory / spec.FILMSTRIP_FILENAME
    size = sprite.stat().st_size
    film = Filmstrip(
        version=FILMSTRIP_VERSION,
        tiles=layout.tiles,
        interval=layout.interval,
        columns=layout.columns,
        rows=layout.rows,
        tile_width=layout.tile_width,
        tile_height=layout.tile_height,
        width=layout.width,
        height=layout.height,
        bytes=size,
        path=target,
        generated=True,
    )
    cache_dir = entry.directory.parent
    try:
        # Read afresh: the record is read-modify-write, and the facts may have been replaced.
        document = _facts_object(entry, clip)
        document["filmstrip"] = film.to_json()
        staged = part / spec.FACTS_FILENAME
        _write_json(staged, document)
        cache.fsync(sprite)
        os.replace(sprite, target)
        try:
            os.replace(staged, entry.facts_path)
        except OSError:
            _remove(target)  # a sprite that nothing records is an unfinished one
            raise
        cache.fsync(entry.directory)
    except OSError as exc:
        raise ProxyCacheError(f"{cache_dir}: cannot write proxies: {exc}") from exc
    logger.debug("Filmstrip of %s: %d tiles, %d bytes", clip, film.tiles, size)
    return film


def _facts_object(entry: ProxyEntry, clip: str) -> dict[str, Any]:
    """The entry's ``facts.json`` as a JSON object; anything else is a :class:`FilmstripError`."""
    try:
        document = json.loads(entry.facts_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise FilmstripError(clip, f"cannot read the proxy's facts: {exc}") from exc
    if not isinstance(document, dict):
        raise FilmstripError(clip, "the proxy's facts are not a JSON object")
    return document


def _write_json(path: Path, document: dict[str, Any]) -> None:
    """Write ``document`` as sorted-key JSON, like the proxy's facts, and ``fsync`` it."""
    text = json.dumps(document, sort_keys=True, indent=2) + "\n"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o666)  # umask applies
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())


def _remove(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def _probe_proxy(
    proxy: Path, runtime: FfmpegRuntime, clip: str
) -> tuple[float, int, int, List[float]]:
    """The proxy's first video stream and its keyframes: ``(duration, width, height, times)``.

    One ``ffprobe`` run reads the stream header and the packet index (no decode: the keyframes
    are the packets flagged ``K``, 0.17 s for 900 s of 540p). The duration is the video
    stream's: the container's runs up to 21 ms longer (AAC priming) and would give a clip of
    exactly 25 s a 26th tile.
    """
    try:
        out = runtime.run_ffprobe(
            [
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height,duration:packet=pts_time,flags",
                "-of",
                "compact=p=0",
                str(proxy),
            ]
        ).stdout
    except FfmpegError as exc:
        raise FilmstripError(clip, f"ffprobe could not read the proxy: {exc}") from exc
    stream: dict[str, str] = {}
    keyframes: List[float] = []
    for line in out.splitlines():
        fields = dict(part.partition("=")[::2] for part in line.strip().split("|") if part)
        if "flags" in fields:
            if "K" in fields["flags"]:
                try:
                    keyframes.append(float(fields.get("pts_time", "")))
                except ValueError as exc:
                    raise FilmstripError(
                        clip, f"a keyframe of the proxy has no time ({fields.get('pts_time')!r})"
                    ) from exc
        elif "width" in fields:
            stream = fields
    try:
        width, height, duration = (
            int(stream["width"]),
            int(stream["height"]),
            float(stream["duration"]),
        )
    except (KeyError, ValueError) as exc:
        raise FilmstripError(
            clip, f"ffprobe gave no usable video stream of the proxy: {exc!r}"
        ) from exc
    return duration, width, height, keyframes


def _cut(args: Sequence[str], runtime: FfmpegRuntime, sprite: Path, clip: str) -> None:
    """Run the sprite's ffmpeg command; it must leave a non-empty file."""
    try:
        runtime.run(args)
    except FfmpegError as exc:
        full = cache.is_full_disk(str(exc))
        if full is not None:
            raise ProxyCacheError(f"{sprite.parent.parent}: cannot write proxies: {full}") from exc
        raise FilmstripError(clip, f"ffmpeg could not cut the filmstrip: {exc}") from exc
    if not sprite.is_file() or sprite.stat().st_size == 0:
        raise FilmstripError(clip, "ffmpeg exited 0 but wrote no filmstrip")


def _verify(sprite: Path, layout: FilmstripPlan, clip: str) -> None:
    """The sprite must be a JPEG of exactly the planned size."""
    try:
        found = jpeg_size(sprite.read_bytes())
    except OSError as exc:
        raise FilmstripError(clip, f"cannot read the filmstrip back: {exc}") from exc
    expected = (layout.width, layout.height)
    if found != expected:
        got = f"{found[0]}x{found[1]}" if found is not None else "not a JPEG"
        raise FilmstripError(clip, f"the filmstrip is {got}, expected {expected[0]}x{expected[1]}")


#: JPEG start-of-frame markers (those that carry the image size), without DHT, JPG and DAC.
_SOF = frozenset(range(0xC0, 0xD0)) - {0xC4, 0xC8, 0xCC}


def jpeg_size(data: bytes) -> Optional[tuple[int, int]]:
    """The ``(width, height)`` in a JPEG's start-of-frame header, or ``None`` when it has none."""
    if data[:2] != b"\xff\xd8":
        return None
    index = 2
    while index + 4 <= len(data):
        if data[index] != 0xFF:
            return None
        marker = data[index + 1]
        if marker == 0xFF:  # fill byte
            index += 1
            continue
        if marker in _SOF:
            if index + 9 > len(data):
                return None
            height = int.from_bytes(data[index + 5 : index + 7], "big")
            width = int.from_bytes(data[index + 7 : index + 9], "big")
            return width, height
        if marker in (0xDA, 0xD9):  # the scan or the end: no frame header before it
            return None
        index += 2 + int.from_bytes(data[index + 2 : index + 4], "big")
    return None


__all__ = [
    "COLUMNS",
    "FILMSTRIP_TIMEOUT_S",
    "FILMSTRIP_VERSION",
    "JPEG_QSCALE",
    "MAX_TILES",
    "SUM_TERMS",
    "TILE_HEIGHT",
    "Filmstrip",
    "FilmstripPlan",
    "ensure_filmstrip",
    "filmstrip_args",
    "jpeg_size",
    "keyframe_ordinals",
    "lookup_filmstrip",
    "plan",
]
