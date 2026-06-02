"""NVIDIA CUDA/NVENC profile — best-guess fragments, gated entirely by the self-test.

This host has no NVIDIA GPU, so these strings are unverified (flagged for hardware
validation in the design's open questions). The golden tests pin the *strings*; the
self-test decides whether they are ever *used* — any op whose probe does not pass falls
back to the CPU profile via :class:`HardwareProfile`.

NVENC has no native pad filter, so normalize scales on the GPU (``scale_cuda``) then pads
on the CPU after an ``hwdownload`` — the frames end in system memory, where NVENC happily
accepts them, so no re-upload is forced.
"""

from __future__ import annotations

from typing import Optional

from ..models import FrameLocation, OpClass, OpFragment, OpParams
from .cpu import require_resolution
from .hardware import HardwareProfile


def cuda_normalize_filter(width: int, height: int, fill_color: str) -> str:
    """GPU scale (AR-preserving) then CPU letterbox-pad, per research (no native CUDA pad)."""
    return (
        f"scale_cuda=w={width}:h={height}:force_original_aspect_ratio=decrease,"
        f"hwdownload,format=nv12,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:{fill_color},setsar=1"
    )


class NvencProfile(HardwareProfile):
    """Emits CUDA/NVENC fragments for decode/normalize/overlay/encode; others fall back."""

    def _decode(self, params: OpParams) -> Optional[OpFragment]:
        if not self.capabilities.decode_method:
            return None
        return OpFragment(
            op=OpClass.DECODE,
            input_flags=("-hwaccel", "cuda", "-hwaccel_output_format", "cuda"),
            frames_in=FrameLocation.SYSTEM,
            frames_out=FrameLocation.CUDA,
        )

    def _normalize(self, params: OpParams) -> Optional[OpFragment]:
        if not self.capabilities.pad_filter:
            return None
        width, height = require_resolution(params)
        return OpFragment(
            op=OpClass.NORMALIZE,
            filter=cuda_normalize_filter(width, height, params.fill_color),
            frames_in=FrameLocation.CUDA,
            frames_out=FrameLocation.SYSTEM,
        )

    def _overlay(self, params: OpParams) -> Optional[OpFragment]:
        if not self.capabilities.can_overlay_hw:
            return None
        return OpFragment(
            op=OpClass.OVERLAY,
            filter="overlay_cuda",
            frames_in=FrameLocation.CUDA,
            frames_out=FrameLocation.CUDA,
        )

    def _tonemap(self, params: OpParams) -> Optional[OpFragment]:
        # No mainline CUDA tonemap filter; tonemap always falls back to CPU here.
        return None

    def _encode(self, params: OpParams) -> Optional[OpFragment]:
        if params.codec is None:
            return None
        encoder = self.capabilities.usable_encoders.get(params.codec)
        if encoder is None:
            return None
        # NVENC accepts system-memory frames directly, so no hwupload is forced.
        return OpFragment(
            op=OpClass.ENCODE,
            output_flags=("-c:v", encoder),
            frames_in=FrameLocation.SYSTEM,
            frames_out=FrameLocation.SYSTEM,
        )
