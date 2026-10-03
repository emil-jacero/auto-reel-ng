"""The proxy contract (D-21): its fixed values, the proxy's geometry and its cache key.

Every value here is a constant of the contract, not a setting (Principle VII): changing
one is a code change plus a bump of :data:`PROXY_VERSION`, and :func:`spec_digest` is a
second guard, so a constant edited without a bump still re-keys every entry. The values
are the ones the v2 proxy research measured; the B-frame count and the keyframe interval
are the two that experiment E1 locked (``-bf 2``, one second).

Everything is pure except :func:`proxy_key`, which reads one ``stat``.
"""

from __future__ import annotations

import hashlib
import json
import math
from fractions import Fraction
from pathlib import Path
from typing import Optional

#: Bump whenever the encode arguments, the contract or the facts change their output for any
#: input class: it re-keys every entry, and a proxy made under an older version is never
#: read as current. 1: the first contract (``-bf 2``, one-second GOP, native AAC).
PROXY_VERSION = 1

#: The proxy's short side in pixels; a clip already at or below it keeps its display size.
PROXY_SHORT_SIDE = 540
#: libx264 constant rate factor and preset (``veryfast`` is as small as ``medium`` at a
#: quarter of the CPU, measured).
PROXY_CRF = 26
PROXY_PRESET = "veryfast"
#: Consecutive B-frames (E1: ``-bf 2`` is 0.83 of the ``-bf 0`` size and passes the seek,
#: step, accuracy and sync gate in Chrome 154 and Firefox 155).
PROXY_BFRAMES = 2
#: Seconds between keyframes: ``round(seconds * fps)`` frames (E1: one second passes G1).
PROXY_GOP_SECONDS = 1
#: ffmpeg's native AAC encoder; never ``libfdk_aac`` (HLD D-1: a non-free encoder).
PROXY_AUDIO_ENCODER = "aac"
PROXY_AUDIO_BITRATE = "128k"
PROXY_AUDIO_CHANNELS = 2

#: How far the proxy's video-stream duration may differ from the source's probed duration.
DURATION_TOLERANCE = 0.05
#: Seconds an encode's output time may stand still before ffmpeg is killed as stalled.
PROXY_STALL_TIMEOUT_S = 600.0
#: Seconds the probe, and each ffprobe run, of one clip are given.
PROXY_PROBE_TIMEOUT_S = 60.0

#: The files of a cache entry (``filmstrip.jpg`` is reserved for ``filmstrip-sprites``).
PROXY_FILENAME = "proxy.mp4"
FACTS_FILENAME = "facts.json"
FILMSTRIP_FILENAME = "filmstrip.jpg"


def spec_digest() -> str:
    """SHA-256 hex over the contract's current values.

    Computed on each call from the module's constants, so an edited constant changes the
    digest and therefore every key, with or without a :data:`PROXY_VERSION` bump.
    """
    contract = {
        "short_side": PROXY_SHORT_SIDE,
        "crf": PROXY_CRF,
        "preset": PROXY_PRESET,
        "bframes": PROXY_BFRAMES,
        "gop_seconds": PROXY_GOP_SECONDS,
        "audio_encoder": PROXY_AUDIO_ENCODER,
        "audio_bitrate": PROXY_AUDIO_BITRATE,
        "audio_channels": PROXY_AUDIO_CHANNELS,
    }
    return hashlib.sha256(json.dumps(contract, sort_keys=True).encode("ascii")).hexdigest()


def gop_frames(fps: float) -> int:
    """The keyframe interval in frames for a clip of ``fps``: one second's worth, at least 1."""
    return max(1, round(PROXY_GOP_SECONDS * fps))


def _pixel_aspect(sample_aspect_ratio: Optional[str]) -> Fraction:
    """The pixel aspect ratio as an exact fraction; absent or ``0:1``/``1:1`` is square.

    Raises:
        ValueError: the text is not ``num:den`` with a positive integer ``num`` and ``den``
            (the engine never assumes a pixel shape it could not read).
    """
    if sample_aspect_ratio is None or sample_aspect_ratio == "0:1":
        return Fraction(1)
    num_text, sep, den_text = sample_aspect_ratio.partition(":")
    try:
        num, den = int(num_text), int(den_text)
    except ValueError:
        num = den = 0
    if not sep or num <= 0 or den <= 0:
        raise ValueError(f"unusable sample aspect ratio {sample_aspect_ratio!r}")
    return Fraction(num, den)


def _even(value: Fraction) -> int:
    """The nearest even integer to ``value`` (halves round up), at least 2."""
    return max(2, math.floor(value / 2 + Fraction(1, 2)) * 2)


def proxy_dimensions(
    width: int, height: int, sample_aspect_ratio: Optional[str], rotation: Optional[int]
) -> tuple[int, int]:
    """The proxy's ``(width, height)`` for a clip with the given coded size and geometry.

    The picture is the display picture: the coded width scaled to square pixels by the
    sample aspect ratio, then turned upright (a 90 or 270 degree rotation swaps the sides).
    The short side is :data:`PROXY_SHORT_SIDE`, never upscaled; each side is rounded to the
    nearest even integer, in exact fractions so no float error moves a boundary.

    Raises:
        ValueError: the sample aspect ratio is unusable, or a side is not positive.
    """
    if width <= 0 or height <= 0:
        raise ValueError(f"unusable coded size {width}x{height}")
    display_w = Fraction(width) * _pixel_aspect(sample_aspect_ratio)
    display_h = Fraction(height)
    if (rotation or 0) % 360 in (90, 270):
        display_w, display_h = display_h, display_w
    short = min(display_w, display_h)
    scale = Fraction(PROXY_SHORT_SIDE) / short if short > PROXY_SHORT_SIDE else Fraction(1)
    return _even(display_w * scale), _even(display_h * scale)


def proxy_key(clip_path: Path) -> str:
    """The cache key: sha256 hex over the clip's file name, stat signal and the contract.

    Symlinks are followed, so every link to one file shares one key, and the name hashed is
    the file's own, not a link's. The directory is left out on purpose: a library that is
    moved, copied or remounted keeps its cache. The encode path is left out too, so a proxy
    made on a CPU is current for a host with a GPU. Two different files with the same name,
    size and ``mtime_ns`` would share a key (negligible for camera clips; deleting the entry
    repairs it). The stat's :class:`OSError` propagates unchanged (``FileNotFoundError`` for a
    vanished clip); each caller decides what it means.
    """
    resolved = Path(clip_path).resolve()
    stat = resolved.stat()
    # A JSON list is a canonical, unambiguous encoding; ensure_ascii keeps a non-UTF-8 file
    # name (surrogate escapes) encodable.
    payload = json.dumps(
        [resolved.name, stat.st_size, stat.st_mtime_ns, PROXY_VERSION, spec_digest()]
    )
    return hashlib.sha256(payload.encode("ascii")).hexdigest()


def entry_dir(clip_path: Path, cache_dir: Path) -> Path:
    """Where the clip's entry lives: ``<cache_dir>/<key>``. Computes only; creates nothing."""
    return Path(cache_dir) / proxy_key(clip_path)


__all__ = [
    "DURATION_TOLERANCE",
    "FACTS_FILENAME",
    "FILMSTRIP_FILENAME",
    "PROXY_AUDIO_BITRATE",
    "PROXY_AUDIO_CHANNELS",
    "PROXY_AUDIO_ENCODER",
    "PROXY_BFRAMES",
    "PROXY_CRF",
    "PROXY_FILENAME",
    "PROXY_GOP_SECONDS",
    "PROXY_PRESET",
    "PROXY_PROBE_TIMEOUT_S",
    "PROXY_SHORT_SIDE",
    "PROXY_STALL_TIMEOUT_S",
    "PROXY_VERSION",
    "entry_dir",
    "gop_frames",
    "proxy_dimensions",
    "proxy_key",
    "spec_digest",
]
