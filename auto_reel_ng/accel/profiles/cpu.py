"""The CPU profile: complete, always usable, and the fallback for every vendor.

These are software-only fragments — frames stay in system memory throughout — so the
profile can satisfy any op on any host. Vendor profiles delegate their non-usable ops
here (notably AMD tonemap and overlay, per ``experiments/003-004``).
"""

from __future__ import annotations

from ...errors import AccelError
from ..models import OpClass, OpFragment, OpParams, Vendor
from .base import AccelProfile

#: codec name -> CPU encoder. ``av1`` maps to SVT-AV1 (``libsvtav1``).
CPU_ENCODERS = {"h264": "libx264", "hevc": "libx265", "av1": "libsvtav1"}

#: CPU HDR->SDR tonemap, the only path that worked on AMD (exp 004): linearize,
#: tonemap with the hable operator, convert back to bt709 SDR.
CPU_TONEMAP_FILTER = (
    "zscale=t=linear:npl=100,tonemap=hable,zscale=t=bt709:m=bt709:r=tv,format=yuv420p"
)


def cpu_normalize_filter(width: int, height: int, fill_color: str) -> str:
    """Scale preserving aspect ratio then letterbox/pillarbox-pad to ``width``x``height``."""
    return (
        f"scale=w={width}:h={height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:{fill_color},setsar=1"
    )


class CPUProfile(AccelProfile):
    """Software fragments for every logical op; usable on any host."""

    vendor = Vendor.CPU

    @property
    def supported_ops(self) -> frozenset[OpClass]:
        """The CPU covers every logical op."""
        return frozenset(OpClass)

    def fragment(self, op: OpClass, params: OpParams) -> OpFragment:
        """Return the software fragment for ``op``; all frames stay in system memory."""
        if op is OpClass.DECODE:
            return OpFragment(op=op)
        if op is OpClass.NORMALIZE:
            width, height = require_resolution(params)
            return OpFragment(op=op, filter=cpu_normalize_filter(width, height, params.fill_color))
        if op is OpClass.OVERLAY:
            return OpFragment(op=op, filter="overlay")
        if op is OpClass.TONEMAP:
            return OpFragment(op=op, filter=CPU_TONEMAP_FILTER)
        if op is OpClass.ENCODE:
            encoder = _require_encoder(params)
            return OpFragment(op=op, output_flags=("-c:v", encoder))
        raise AccelError(f"Unknown operation: {op}")  # pragma: no cover


def require_resolution(params: OpParams) -> tuple[int, int]:
    """Return ``(width, height)`` from params, raising if either is missing."""
    if params.width is None or params.height is None:
        raise AccelError("normalize requires both width and height in OpParams")
    return params.width, params.height


def _require_encoder(params: OpParams) -> str:
    """Map ``params.codec`` to a CPU encoder, raising on missing/unknown codec."""
    if params.codec is None:
        raise AccelError("encode requires a codec in OpParams")
    encoder = CPU_ENCODERS.get(params.codec)
    if encoder is None:
        raise AccelError(
            f"No CPU encoder for codec {params.codec!r}; known: {sorted(CPU_ENCODERS)}"
        )
    return encoder
