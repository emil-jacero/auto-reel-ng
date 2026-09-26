"""The :class:`AccelProfile` interface and the frame-location transfer helper."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, Sequence, Union

from ..models import FrameLocation, OpClass, OpFragment, OpParams, TransferMarker, Vendor

#: A composed render chain is a sequence of op fragments interleaved with the
#: transfer markers :func:`insert_transfers` adds between mismatched frame locations.
ChainItem = Union[OpFragment, TransferMarker]


class AccelProfile(ABC):
    """A vendor's strategy for emitting ffmpeg fragments per logical operation.

    Implementations declare which ops they cover natively (:meth:`supported_ops`) and
    return an :class:`OpFragment` for any of the five logical ops (:meth:`fragment`).
    Vendor profiles delegate ops they cannot run on hardware to the CPU profile, so
    every profile can answer for every op — the guaranteed CPU fallback.
    """

    #: The vendor this profile emits for.
    vendor: Vendor

    @property
    @abstractmethod
    def supported_ops(self) -> frozenset[OpClass]:
        """The ops this profile runs on its own hardware (the rest fall back to CPU)."""

    @abstractmethod
    def fragment(self, op: OpClass, params: OpParams) -> OpFragment:
        """Return the ffmpeg fragment for ``op`` given ``params``.

        Raises:
            AccelError: if ``params`` lacks a value an op requires (e.g. a normalize
                without a target resolution).
        """

    def upload_device_flags(self, params: OpParams) -> tuple[str, ...]:
        """Global flags that give a filter graph a device to ``hwupload`` frames into.

        A chain whose frames start in system memory (a rendered card image, or a
        software decode) and end at a hardware-frame encoder must upload them, and
        ``hwupload`` needs a device to upload into. A hardware decode opens one as a
        side effect; without one the command must name it. Empty means the profile
        has no verified recipe: the caller then fails loud rather than emitting a
        command ffmpeg would reject.
        """
        del params
        return ()


def needs_transfer(out_loc: FrameLocation, in_loc: FrameLocation) -> Optional[str]:
    """Return the transfer filter needed between two frame locations, or ``None``.

    ``"hwdownload"`` when moving hardware frames to system memory, ``"hwupload"`` when
    moving the other way. Same-location (or unknown) transitions need nothing.
    """
    if out_loc is in_loc:
        return None
    if out_loc is not FrameLocation.SYSTEM and in_loc is FrameLocation.SYSTEM:
        return "hwdownload"
    if out_loc is FrameLocation.SYSTEM and in_loc is not FrameLocation.SYSTEM:
        return "hwupload"
    # hw -> different hw (e.g. vaapi -> cuda): a download then upload; model as a
    # download here and let the next boundary upload. Rare; flagged for #4.
    return "hwdownload"


def insert_transfers(fragments: Sequence[OpFragment]) -> list[ChainItem]:
    """Interleave ``hwupload``/``hwdownload`` markers where adjacent ops disagree.

    Walks the chain and, wherever one op's output frame location differs from the next
    op's input location, inserts a :class:`TransferMarker`. This makes every implicit
    GPU<->system round-trip explicit so the composer (#4) cannot silently fall back to
    a sub-realtime CPU copy.
    """
    if not fragments:
        return []
    chain: list[ChainItem] = [fragments[0]]
    for previous, current in zip(fragments, fragments[1:]):
        filter_name = needs_transfer(previous.frames_out, current.frames_in)
        if filter_name is not None:
            chain.append(
                TransferMarker(
                    filter=filter_name,
                    frames_in=previous.frames_out,
                    frames_out=current.frames_in,
                )
            )
        chain.append(current)
    return chain
