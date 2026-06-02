"""Per-vendor acceleration profiles that emit ffmpeg fragments per logical op.

A profile is *pure*: given an :class:`OpClass` and :class:`OpParams` it returns an
:class:`OpFragment` (argument fragments + frame-location tags); it never runs ffmpeg.
That keeps the vendor argument strings unit-testable via golden assertions with no GPU
present, while the self-test (separately) gates which ops a vendor profile will actually
emit on hardware versus delegate to the always-complete CPU profile.
"""

from __future__ import annotations

from .base import AccelProfile, insert_transfers, needs_transfer
from .cpu import CPUProfile
from .nvenc import NvencProfile
from .qsv import QsvProfile
from .vaapi import VaapiProfile

__all__ = [
    "AccelProfile",
    "CPUProfile",
    "VaapiProfile",
    "NvencProfile",
    "QsvProfile",
    "insert_transfers",
    "needs_transfer",
]
