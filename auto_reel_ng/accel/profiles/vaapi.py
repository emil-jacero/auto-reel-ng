"""AMD VAAPI profile, grounded in the verified spike results (exp 003/004).

Confirmed on the dev host (RX 9070 XT, Mesa/radv): hardware decode and the single-API
``scale_vaapi,pad_vaapi`` normalize work and are the fastest path; the VAAPI encoders for
h264/hevc/av1 work. ``overlay_vaapi`` is unsupported and every GPU HDR tonemap path
faults — so overlay and tonemap delegate to the CPU profile.
"""

from __future__ import annotations

from typing import Optional

from ..models import FrameLocation, OpClass, OpFragment, OpParams
from .cpu import require_resolution
from .hardware import HardwareProfile


def vaapi_normalize_filter(width: int, height: int, fill_color: str) -> str:
    """The verified AMD normalize: AR-preserving ``scale_vaapi`` then centered ``pad_vaapi``."""
    return (
        f"scale_vaapi=w={width}:h={height}:force_original_aspect_ratio=decrease,"
        f"pad_vaapi=w={width}:h={height}:x=(ow-iw)/2:y=(oh-ih)/2:color={fill_color}"
    )


class VaapiProfile(HardwareProfile):
    """Emits VAAPI fragments for decode/normalize/encode; overlay+tonemap fall back."""

    def _decode(self, params: OpParams) -> Optional[OpFragment]:
        if not self.capabilities.decode_method:
            return None
        node = self._render_node(params)
        device_flags = ("-hwaccel_device", node) if node else ()
        return OpFragment(
            op=OpClass.DECODE,
            input_flags=("-hwaccel", "vaapi", *device_flags, "-hwaccel_output_format", "vaapi"),
            frames_in=FrameLocation.SYSTEM,
            frames_out=FrameLocation.VAAPI,
        )

    def _normalize(self, params: OpParams) -> Optional[OpFragment]:
        if not self.capabilities.pad_filter:
            return None
        width, height = require_resolution(params)
        return OpFragment(
            op=OpClass.NORMALIZE,
            filter=vaapi_normalize_filter(width, height, params.fill_color),
            frames_in=FrameLocation.VAAPI,
            frames_out=FrameLocation.VAAPI,
        )

    def _overlay(self, params: OpParams) -> Optional[OpFragment]:
        # overlay_vaapi is unsupported on AMD Mesa (exp 003) -> CPU fallback.
        return None

    def _tonemap(self, params: OpParams) -> Optional[OpFragment]:
        # No working GPU HDR path on AMD (exp 004) -> CPU zscale,tonemap fallback.
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
            frames_in=FrameLocation.VAAPI,
            frames_out=FrameLocation.SYSTEM,
        )
