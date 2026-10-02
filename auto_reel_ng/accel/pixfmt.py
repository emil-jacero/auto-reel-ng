"""Pixel-format facts the hardware-decode decision needs: bit depth and chroma subsampling.

Pure and table-free where ffmpeg's naming is regular. A format this module does not
recognise is reported as unknown rather than guessed (Principle I): the caller then
decodes in software, which is correct for every format.
"""

from __future__ import annotations

import re
from typing import Optional

#: ``yuv420p``, ``yuvj420p``, ``yuv422p10le``, ``yuv444p12be``, ... -> chroma + optional depth.
_PLANAR_YUV = re.compile(r"^yuvj?(?P<chroma>\d{3})p(?P<depth>\d+)?(?:le|be)?$")

#: Semi-planar 4:2:0 formats -> bit depth (``nv12``/``nv21`` are 8-bit, ``pNNN`` NN-bit).
_SEMI_PLANAR_420 = {"nv12": 8, "nv21": 8, "p010le": 10, "p010be": 10, "p012le": 12, "p016le": 16}


def pix_fmt_traits(pix_fmt: str) -> Optional[tuple[int, bool]]:
    """Return ``(bit_depth, is_420)`` for an ffmpeg pixel format, or ``None`` if unrecognised.

    ``yuv420p``/``yuvj420p``/``nv12`` are 8-bit 4:2:0, ``yuv420p10le``/``p010le`` 10-bit
    4:2:0, ``yuv422p`` 8-bit and ``yuv444p10le`` 10-bit, neither 4:2:0.
    """
    if pix_fmt in _SEMI_PLANAR_420:
        return _SEMI_PLANAR_420[pix_fmt], True
    match = _PLANAR_YUV.match(pix_fmt)
    if match is None:
        return None
    depth = int(match.group("depth")) if match.group("depth") else 8
    return depth, match.group("chroma") == "420"
