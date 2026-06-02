"""Immutable, typed media-metadata model.

Absent data (no audio stream, no rotation, no bitrate) is modeled with explicit
``None`` rather than fabricated defaults. This is the structural half of the
fail-loud guarantee: there is no way to express "I assumed 1920x1080/25fps".
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

# Color-transfer values that indicate HDR (PQ and HLG respectively).
HDR_TRANSFERS = frozenset({"smpte2084", "arib-std-b67"})


@dataclass(frozen=True)
class AudioStream:
    """Audio characteristics of a single clip; only present when audio exists."""

    codec: str
    sample_rate: Optional[int]
    channels: Optional[int]
    channel_layout: Optional[str]


@dataclass(frozen=True)
class ClipMetadata:  # pylint: disable=too-many-instance-attributes
    """Validated metadata for one media file, derived from a single ffprobe pass.

    The field count is intentionally wide: it mirrors the ``media-probe`` spec one-to-one.
    """

    path: Path
    duration: float
    fps: float
    video_codec: str
    profile: Optional[str]
    width: int
    height: int
    sample_aspect_ratio: Optional[str]
    display_aspect_ratio: Optional[str]
    pix_fmt: Optional[str]
    video_bitrate: Optional[int]
    rotation: Optional[int]
    color_transfer: Optional[str]
    is_hdr: bool
    audio: Optional[AudioStream]
    creation_time: Optional[datetime]

    @property
    def has_audio(self) -> bool:
        """True when the clip carries an audio stream."""
        return self.audio is not None
