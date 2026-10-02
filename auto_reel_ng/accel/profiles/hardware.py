"""Shared base for hardware (vendor) profiles with guaranteed CPU fallback.

A vendor profile provides hardware fragment *builders* for the ops it can run; each
builder returns an :class:`OpFragment` when the op is usable on this host (per the
self-tested :class:`AcceleratorCapabilities`) or ``None`` to fall back. The base routes
every op: usable hardware op -> the vendor fragment; otherwise -> the CPU profile. This
is the structural guarantee that every op always has a working fragment.
"""

from __future__ import annotations

from typing import Optional

from ..models import AcceleratorCapabilities, OpClass, OpFragment, OpParams
from ..pixfmt import pix_fmt_traits
from .base import AccelProfile
from .cpu import CPUProfile


class HardwareProfile(AccelProfile):
    """Routes ops to vendor fragments, delegating the rest to the CPU profile."""

    def __init__(
        self, capabilities: AcceleratorCapabilities, cpu: Optional[CPUProfile] = None
    ) -> None:
        self.capabilities = capabilities
        self.vendor = capabilities.vendor
        self._cpu = cpu or CPUProfile()

    @property
    def supported_ops(self) -> frozenset[OpClass]:
        """Ops this accelerator runs on hardware, derived from the self-tested flags."""
        ops: set[OpClass] = set()
        caps = self.capabilities
        if caps.decode_method:
            ops.add(OpClass.DECODE)
        if caps.pad_filter:
            ops.add(OpClass.NORMALIZE)
        if caps.can_overlay_hw:
            ops.add(OpClass.OVERLAY)
        if caps.can_tonemap_hw:
            ops.add(OpClass.TONEMAP)
        if caps.usable_encoders:
            ops.add(OpClass.ENCODE)
        return frozenset(ops)

    def can_hw_decode(self, codec: str, pix_fmt: Optional[str]) -> bool:
        """Whether the self-tested hardware decoder handles ``codec`` in ``pix_fmt``.

        Requires a passing decode self-test, a codec in ``hw_decode``, and, when the probe
        reported a pixel format, 4:2:0 chroma within the codec's bit-depth limit. An absent
        pixel format is decided by the codec alone; an unrecognised one is not hardware
        decodable (software decode is correct for every format).
        """
        caps = self.capabilities
        if not caps.decode_method:
            return False
        max_depth = caps.hw_decode.get(codec)
        if max_depth is None:
            return False
        if pix_fmt is None:
            return True
        traits = pix_fmt_traits(pix_fmt)
        if traits is None:
            return False
        depth, is_420 = traits
        return is_420 and depth <= max_depth

    def fragment(self, op: OpClass, params: OpParams) -> OpFragment:
        """Return the hardware fragment for ``op``, or the CPU fallback if unusable."""
        if op is OpClass.DECODE and params.software_decode:
            return self._cpu.fragment(op, params)
        builders = {
            OpClass.DECODE: self._decode,
            OpClass.NORMALIZE: self._normalize,
            OpClass.OVERLAY: self._overlay,
            OpClass.TONEMAP: self._tonemap,
            OpClass.ENCODE: self._encode,
        }
        hardware = builders[op](params)
        if hardware is not None:
            return hardware
        return self._cpu.fragment(op, params)

    def _render_node(self, params: OpParams) -> Optional[str]:
        """The render node to target: explicit param wins, else the device's node."""
        if params.render_node:
            return params.render_node
        if self.capabilities.device:
            return self.capabilities.device.render_node
        return None

    # -- hardware builders: return a fragment when usable, else None to fall back --

    def _decode(self, params: OpParams) -> Optional[OpFragment]:
        raise NotImplementedError  # pragma: no cover

    def _normalize(self, params: OpParams) -> Optional[OpFragment]:
        raise NotImplementedError  # pragma: no cover

    def _overlay(self, params: OpParams) -> Optional[OpFragment]:
        raise NotImplementedError  # pragma: no cover

    def _tonemap(self, params: OpParams) -> Optional[OpFragment]:
        raise NotImplementedError  # pragma: no cover

    def _encode(self, params: OpParams) -> Optional[OpFragment]:
        raise NotImplementedError  # pragma: no cover
