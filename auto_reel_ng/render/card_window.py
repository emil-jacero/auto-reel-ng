"""Split a source segment at the end of its timed overlay's window (video-card-bridge-window).

A timed overlay (the title card over the chapter's first clip) is composited with the CPU
``overlay`` filter, which on a hardware profile means a download and an upload of every frame of
the segment it is attached to. The card covers only its first few seconds, so the rest of a long
anchor clip paid that bridge for nothing. Here the segment becomes a **head** (the window, which
keeps the overlay) and a **tail** (the remainder, an ordinary overlay-free segment on the
hardware path). Both are re-encoded, so no keyframe is needed at the boundary.

The boundary is a whole number of *target* frames, so the joined pieces hold exactly the frames
the unsplit segment had: the tail's tick ``k`` falls on the source instant the unsplit segment's
tick ``N + k`` did. The functions are pure; the card is materialized before the split because the
window is only known after the producer has been asked. The pieces are video-only; the join
carries the segment's audio once (a sidecar of the tail's command), so no audio seam exists.
"""

from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path

from .normalize import NormalizeCommand
from .segments import Segment

#: A tail shorter than this is not split off: the saving is smaller than the extra ffmpeg start
#: and join it costs.
MIN_TAIL_S = 1.0

#: Absorbs float noise when a window is an exact multiple of the frame period.
_FRAME_EPSILON = 1e-6


def split_segment(segment: Segment, fps: float, length: float) -> tuple[Segment, ...]:
    """``(head, tail)`` for a source segment whose timed overlays are materialized, else ``(segment,)``.

    ``length`` is the segment's length in seconds. The segment is split only when it is a source
    segment, every overlay is timed with a known window, and at least :data:`MIN_TAIL_S` of footage
    would remain after the head; otherwise it is returned whole, exactly as before.
    """
    if segment.is_synthetic or not segment.overlays or fps <= 0.0:
        return (segment,)
    if not all(overlay.is_timed and overlay.end is not None for overlay in segment.overlays):
        return (segment,)
    window = min(max(overlay.end or 0.0 for overlay in segment.overlays), length)
    frames = math.ceil(window * fps - _FRAME_EPSILON)
    if frames <= 0:
        return (segment,)
    head_length = frames / fps
    if length - head_length < MIN_TAIL_S:
        return (segment,)
    first = segment.start or 0.0
    head = replace(
        segment,
        start=first,
        end=first + head_length,
        is_full_clip=False,
        copy_eligible=False,
    )
    tail = replace(
        segment,
        start=first + head_length,
        end=first + length,
        is_full_clip=False,
        overlays=(),
        copy_eligible=False,
    )
    return (head, tail)


def build_join_command(
    list_file: Path, audio_path: Path, output_path: Path, *, duration: float
) -> NormalizeCommand:
    """The command that joins a split segment's video-only pieces with its one audio track.

    ``list_file`` is the concat-demuxer list of the head and the tail; ``audio_path`` the audio of
    the whole segment, written by the tail's command (:class:`~auto_reel_ng.render.normalize.AudioSidecar`).
    Everything is stream-copied. One AAC stream has no seam: two streams joined in a copy would
    leave the second one's encoder delay as a gap of silence inside continuous footage.
    """
    args = (
        "-y",
        *("-f", "concat", "-safe", "0", "-i", str(list_file)),
        *("-i", str(audio_path)),
        *("-map", "0:v:0", "-map", "1:a:0", "-c", "copy"),
        str(output_path),
    )
    return NormalizeCommand(args=args, output_path=Path(output_path), duration=duration)


__all__ = ["MIN_TAIL_S", "build_join_command", "split_segment"]
