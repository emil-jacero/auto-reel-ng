"""Equivalence-guarded stream-copy concat (movie-assembly, decision **D-D**).

The spikes proved a resolution/SAR mismatch muxes at exit 0 while breaking
playback (exp 001), so copy safety is decided from **probe data before** running
concat, never from the concat command's exit code. This module probes the
copy-critical parameters over the whole set, decides uniformity, and builds the
concat-demuxer command (always ``-c copy`` over a set already made uniform).
"""

from __future__ import annotations

import json
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

from ..errors import RenderError
from ..ffmpeg.runtime import FfmpegRuntime


@dataclass(frozen=True)
class CopyFields:
    """Probed parameters that must match across the set for a safe ``-c copy``.

    The values are compared only for equality across the set, so each is held as
    the raw ffprobe scalar (``object``); their *names* document the copy-critical
    fields the spike (exp 001) proved must agree.
    """

    video_codec: object
    profile: object
    width: object
    height: object
    sample_aspect_ratio: object
    pix_fmt: object
    time_base: object
    audio_codec: object
    audio_sample_rate: object
    audio_channels: object
    audio_channel_layout: object


def probe_copy_fields(runtime: FfmpegRuntime, path: Path) -> CopyFields:
    """Probe ``path`` for the copy-critical video and audio parameters."""
    result = runtime.run_ffprobe(
        ["-v", "error", "-show_streams", "-print_format", "json", str(path)]
    )
    try:
        streams = json.loads(result.stdout).get("streams", [])
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise RenderError(f"could not parse ffprobe streams for {path}: {exc}") from exc

    video: dict[str, object] = next((s for s in streams if s.get("codec_type") == "video"), {})
    audio: dict[str, object] = next((s for s in streams if s.get("codec_type") == "audio"), {})
    return CopyFields(
        video_codec=video.get("codec_name"),
        profile=video.get("profile"),
        width=video.get("width"),
        height=video.get("height"),
        sample_aspect_ratio=video.get("sample_aspect_ratio"),
        pix_fmt=video.get("pix_fmt"),
        time_base=video.get("time_base"),
        audio_codec=audio.get("codec_name"),
        audio_sample_rate=audio.get("sample_rate"),
        audio_channels=audio.get("channels"),
        audio_channel_layout=audio.get("channel_layout"),
    )


def is_copy_uniform(runtime: FfmpegRuntime, paths: Sequence[Path]) -> bool:
    """Return True only when every path shares the copy-critical parameters.

    An empty or single-element set is trivially uniform. The decision is made
    entirely from probe data, never from an ffmpeg exit code.
    """
    if len(paths) <= 1:
        return True
    fields = [probe_copy_fields(runtime, Path(p)) for p in paths]
    first = fields[0]
    return all(other == first for other in fields[1:])


def build_concat_list(paths: Sequence[Path]) -> str:
    """Build the concat-demuxer list file content for ``paths``."""
    lines = [f"file {shlex.quote(str(Path(p).resolve()))}" for p in paths]
    return "\n".join(lines) + "\n"


def build_concat_command(
    list_file: Path,
    output_path: Path,
    *,
    metadata_file: Optional[Path] = None,
) -> tuple[str, ...]:
    """Build the concat-demuxer ``-c copy`` command, optionally muxing chapters.

    The segment set is assumed already uniform (made so by re-normalizing on a
    failed pre-flight), so the join only ever stream-copies. When a chapter
    ``metadata_file`` is given, it is muxed in via ``-map_metadata``.
    """
    args: list[str] = ["-y", "-f", "concat", "-safe", "0", "-i", str(list_file)]
    if metadata_file is not None:
        # -map_chapters (not just -map_metadata) is what pulls the [CHAPTER]
        # markers out of the ffmetadata input and into the container.
        args += ["-i", str(metadata_file), "-map", "0", "-map_metadata", "1", "-map_chapters", "1"]
    args += ["-c", "copy", "-movflags", "+faststart", str(output_path)]
    return tuple(args)


__all__ = [
    "CopyFields",
    "probe_copy_fields",
    "is_copy_uniform",
    "build_concat_list",
    "build_concat_command",
]
