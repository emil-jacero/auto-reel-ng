"""AMD VAAPI profile, grounded in the verified spike results (exp 003/004).

Confirmed on the dev host (RX 9070 XT, Mesa/radv): hardware decode and the single-API
``scale_vaapi,pad_vaapi`` normalize run and are the fastest path, but ``pad_vaapi`` ignores
its fill colour on Mesa (exp 006), so a clip that needs bars pads on the CPU unless the
self-test measured a correct fill (``pad_fill_ok``); the VAAPI encoders for
h264/hevc/av1 work. ``overlay_vaapi`` is unsupported and every GPU HDR tonemap path
faults — so overlay and tonemap delegate to the CPU profile.
"""

from __future__ import annotations

from typing import Optional

from ..models import FrameLocation, OpClass, OpFragment, OpParams
from .cpu import require_resolution
from .hardware import HardwareProfile


def vaapi_scale_filter(width: int, height: int) -> str:
    """AR-preserving ``scale_vaapi``; fills the canvas alone for an exact-aspect clip."""
    return f"scale_vaapi=w={width}:h={height}:force_original_aspect_ratio=decrease"


def vaapi_normalize_filter(width: int, height: int, fill_color: str) -> str:
    """The verified AMD normalize: AR-preserving ``scale_vaapi`` then centered ``pad_vaapi``."""
    return (
        f"{vaapi_scale_filter(width, height)},"
        f"pad_vaapi=w={width}:h={height}:x=(ow-iw)/2:y=(oh-ih)/2:color={fill_color}"
    )


class VaapiProfile(HardwareProfile):
    """Emits VAAPI fragments for decode/normalize/encode; overlay+tonemap fall back."""

    def _decode(self, params: OpParams) -> Optional[OpFragment]:
        if not self.capabilities.decode_method:
            return None
        # One named device serves decode *and* the filter graph, so a CPU stage between
        # this decode and a VAAPI encode (pad, transpose, tonemap, overlay bridge) can
        # hwupload back; a bare ``-hwaccel_device`` is invisible to filters (exp 006).
        return OpFragment(
            op=OpClass.DECODE,
            input_flags=(
                *self.upload_device_flags(params),
                "-hwaccel",
                "vaapi",
                "-hwaccel_device",
                "va",
                "-hwaccel_output_format",
                "vaapi",
            ),
            frames_in=FrameLocation.SYSTEM,
            frames_out=FrameLocation.VAAPI,
        )

    def upload_device_flags(self, params: OpParams) -> tuple[str, ...]:
        # The exact recipe the startup self-test runs every VAAPI encode probe with
        # (accel/selftest.py), so a usable encoder is one proven to accept it.
        node = self._render_node(params)
        device = f"vaapi=va:{node}" if node else "vaapi=va"
        return ("-init_hw_device", device, "-filter_hw_device", "va")

    def _normalize(self, params: OpParams) -> Optional[OpFragment]:
        if not self.capabilities.pad_filter:
            return None
        if params.needs_pad and not self.capabilities.pad_fill_ok:
            # pad_vaapi ignores its colour on Mesa (exp 006) -> CPU scale+pad this clip.
            return None
        width, height = require_resolution(params)
        if params.needs_pad:
            vf = vaapi_normalize_filter(width, height, params.fill_color)
        else:
            vf = vaapi_scale_filter(width, height)
        # Square pixels explicitly, like every other profile's normalize: scale_vaapi passes
        # the source SAR through, so an unset (N/A) SAR would otherwise survive into the
        # segment. setsar is metadata-only and runs on VAAPI frames without a transfer.
        return OpFragment(
            op=OpClass.NORMALIZE,
            filter=f"{vf},setsar=1",
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
