"""Intel QSV profile — best-guess fragments, gated entirely by the self-test.

This host has no Intel GPU, so these strings are unverified (flagged for hardware
validation). ``vpp_qsv`` scales and crops but cannot pad (research §4), so normalize
scales on the GPU then pads on the CPU after an ``hwdownload``. The QSV encoder wants
QSV-surface input, so its fragment declares ``frames_in = QSV``; the frame-location
helper then inserts the ``hwupload`` from the system-memory pad output.
"""

from __future__ import annotations

from typing import Optional

from ..models import FrameLocation, OpClass, OpFragment, OpParams
from .cpu import require_resolution
from .hardware import HardwareProfile


def qsv_normalize_filter(width: int, height: int, fill_color: str) -> str:
    """GPU scale via ``vpp_qsv`` then CPU letterbox-pad (vpp_qsv cannot pad)."""
    return (
        f"vpp_qsv=w={width}:h={height},"
        f"hwdownload,format=nv12,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:{fill_color},setsar=1"
    )


class QsvProfile(HardwareProfile):
    """Emits QSV fragments for decode/normalize/overlay/encode; others fall back."""

    def _decode(self, params: OpParams) -> Optional[OpFragment]:
        if not self.capabilities.decode_method:
            return None
        return OpFragment(
            op=OpClass.DECODE,
            input_flags=("-hwaccel", "qsv", "-hwaccel_output_format", "qsv"),
            frames_in=FrameLocation.SYSTEM,
            frames_out=FrameLocation.QSV,
        )

    def _normalize(self, params: OpParams) -> Optional[OpFragment]:
        if not self.capabilities.pad_filter:
            return None
        width, height = require_resolution(params)
        return OpFragment(
            op=OpClass.NORMALIZE,
            filter=qsv_normalize_filter(width, height, params.fill_color),
            frames_in=FrameLocation.QSV,
            frames_out=FrameLocation.SYSTEM,
        )

    def _overlay(self, params: OpParams) -> Optional[OpFragment]:
        if not self.capabilities.can_overlay_hw:
            return None
        return OpFragment(
            op=OpClass.OVERLAY,
            filter="overlay_qsv",
            frames_in=FrameLocation.QSV,
            frames_out=FrameLocation.QSV,
        )

    def _tonemap(self, params: OpParams) -> Optional[OpFragment]:
        # QSV/VAAPI tonemap is unverified here; tonemap falls back to CPU.
        return None

    def _encode(self, params: OpParams) -> Optional[OpFragment]:
        if params.codec is None:
            return None
        encoder = self.capabilities.usable_encoders.get(params.codec)
        if encoder is None:
            return None
        return OpFragment(
            op=OpClass.ENCODE,
            output_flags=("-c:v", encoder),
            frames_in=FrameLocation.QSV,
            frames_out=FrameLocation.SYSTEM,
        )
