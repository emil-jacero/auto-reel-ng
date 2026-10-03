"""Fail-loud, single-pass media probing.

``probe_media`` runs exactly one ``ffprobe -show_format -show_streams -print_format json``
per file and maps the result into a :class:`ClipMetadata`. On any problem — missing file,
empty file, no video stream, unparseable output, implausible frame rate — it raises
:class:`ProbeError` rather than substituting an assumed value. This is the behavioral
break from auto-reel, which fabricated 1920x1080/25fps on probe failure.
"""

from __future__ import annotations

import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional, Union

from ..errors import FfmpegError, ProbeError
from ..ffmpeg.runtime import FfmpegRuntime
from .metadata import HDR_TRANSFERS, AudioStream, ClipMetadata

logger = logging.getLogger(__name__)

PathLike = Union[str, Path]

# Lazily-built shared runtime so ``probe_media(path)`` works without an explicit one.
_DEFAULT_RUNTIME: Optional[FfmpegRuntime] = None

# Frame rates outside this range are treated as corrupt metadata, not real values.
_MIN_FPS = 0.0
_MAX_FPS = 1000.0


def get_default_runtime() -> FfmpegRuntime:
    """Return a process-wide :class:`FfmpegRuntime`, building it once on first use."""
    global _DEFAULT_RUNTIME  # pylint: disable=global-statement
    if _DEFAULT_RUNTIME is None:
        _DEFAULT_RUNTIME = FfmpegRuntime()
    return _DEFAULT_RUNTIME


def probe_media(
    path: PathLike,
    *,
    runtime: Optional[FfmpegRuntime] = None,
    use_exiftool: bool = False,
) -> ClipMetadata:
    """Probe one media file into a :class:`ClipMetadata`, failing loud on any problem.

    Args:
        path: The media file to probe.
        runtime: The ffmpeg/ffprobe runtime to use; a shared default is built if omitted.
        use_exiftool: When True, fall back to exiftool for creation time if ffprobe tags
            carry none. Off by default so no exiftool process is spawned per clip.

    Raises:
        ProbeError: if the file is missing/empty, has no video stream, cannot be parsed,
            or reports an implausible frame rate.
    """
    media_path = Path(path)
    runtime = runtime or get_default_runtime()

    if not media_path.exists():
        raise ProbeError(f"File does not exist: {media_path}")
    if not media_path.is_file():
        raise ProbeError(f"Not a regular file: {media_path}")
    if media_path.stat().st_size == 0:
        raise ProbeError(f"File is empty (zero bytes): {media_path}")

    probe_json = _run_ffprobe(runtime, media_path)

    streams = probe_json.get("streams", [])
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    if video_stream is None:
        raise ProbeError(f"No video stream found in {media_path}")

    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)
    fmt = probe_json.get("format", {})

    width = _require_int(video_stream, "width", media_path)
    height = _require_int(video_stream, "height", media_path)
    fps = _resolve_fps(video_stream, media_path)
    color_transfer = video_stream.get("color_transfer")

    return ClipMetadata(
        path=media_path,
        duration=_parse_duration(fmt, video_stream),
        fps=fps,
        video_codec=video_stream.get("codec_name", "unknown"),
        profile=video_stream.get("profile"),
        width=width,
        height=height,
        sample_aspect_ratio=_clean_ratio(video_stream.get("sample_aspect_ratio")),
        display_aspect_ratio=_clean_ratio(video_stream.get("display_aspect_ratio")),
        pix_fmt=video_stream.get("pix_fmt"),
        video_bitrate=_optional_int(video_stream.get("bit_rate"))
        or _optional_int(fmt.get("bit_rate")),
        rotation=_extract_rotation(video_stream),
        color_transfer=color_transfer,
        is_hdr=color_transfer in HDR_TRANSFERS if color_transfer else False,
        audio=_build_audio(audio_stream),
        creation_time=_extract_creation_time(fmt, video_stream, media_path, use_exiftool),
    )


def probe_many(
    paths: Iterable[PathLike],
    *,
    runtime: Optional[FfmpegRuntime] = None,
    use_exiftool: bool = False,
) -> tuple[list[ClipMetadata], list[tuple[Path, ProbeError]]]:
    """Probe many files, continuing past failures.

    Returns:
        A ``(metadata, failures)`` pair. ``metadata`` holds the successful results in
        input order; ``failures`` holds ``(path, error)`` for each file that failed.
    """
    runtime = runtime or get_default_runtime()
    results: list[ClipMetadata] = []
    failures: list[tuple[Path, ProbeError]] = []
    for path in paths:
        try:
            results.append(probe_media(path, runtime=runtime, use_exiftool=use_exiftool))
        except ProbeError as exc:
            logger.warning("Skipping unprobeable file %s: %s", path, exc)
            failures.append((Path(path), exc))
    return results, failures


def _run_ffprobe(runtime: FfmpegRuntime, media_path: Path) -> dict[str, Any]:
    """Run the single ffprobe pass and parse its JSON, raising ProbeError on failure."""
    args = [
        "-v",
        "error",
        "-show_format",
        "-show_streams",
        "-print_format",
        "json",
        str(media_path),
    ]
    try:
        result = runtime.run_ffprobe(args)
    except FfmpegError as exc:
        raise ProbeError(f"ffprobe could not read {media_path}: {exc}") from exc
    try:
        parsed = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ProbeError(f"ffprobe produced unparseable output for {media_path}: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ProbeError(f"ffprobe produced unexpected output for {media_path}")
    return parsed


def _resolve_fps(video_stream: dict[str, Any], media_path: Path) -> float:
    """Resolve fps preferring avg_frame_rate, then r_frame_rate; bounds-check or raise."""
    for key in ("avg_frame_rate", "r_frame_rate"):
        fps = _parse_rational(video_stream.get(key))
        if fps is not None and _MIN_FPS < fps <= _MAX_FPS:
            return fps
    raise ProbeError(
        f"Could not determine a plausible frame rate for {media_path} "
        f"(avg_frame_rate={video_stream.get('avg_frame_rate')!r}, "
        f"r_frame_rate={video_stream.get('r_frame_rate')!r})"
    )


def _parse_rational(value: Optional[str]) -> Optional[float]:
    """Parse an ``"num/den"`` rational into a float, or None if invalid/zero-denominator."""
    if not value or "/" not in value:
        return None
    num_str, den_str = value.split("/", 1)
    try:
        num = float(num_str)
        den = float(den_str)
    except ValueError:
        return None
    if den == 0:
        return None
    return num / den


def _parse_duration(fmt: dict[str, Any], video_stream: dict[str, Any]) -> float:
    """Duration from the format block, falling back to the video stream; 0.0 if absent."""
    for source in (fmt, video_stream):
        raw = source.get("duration")
        if raw is None or raw in ("", "N/A"):
            continue
        try:
            return float(raw)
        except (ValueError, TypeError):
            continue
    return 0.0


def _extract_rotation(video_stream: dict[str, Any]) -> Optional[int]:
    """Rotation in degrees from the ``rotate`` tag or Display Matrix side data, else None.

    ffprobe exposes the rotation under the Display Matrix side data (and, on older
    containers, a ``rotate`` tag). Both are normalized into ``[0, 360)`` so a clip
    rotated a quarter turn reports 90 rather than a signed or out-of-range value.
    """
    tags = video_stream.get("tags", {})
    rotate_tag = tags.get("rotate")
    if rotate_tag is not None:
        try:
            # The legacy tag is clockwise; ``rotation`` is the (counter-clockwise) matrix angle.
            return (-int(round(float(rotate_tag)))) % 360
        except (ValueError, TypeError):
            pass
    for side_data in video_stream.get("side_data_list", []):
        if side_data.get("side_data_type") == "Display Matrix" and "rotation" in side_data:
            try:
                raw = float(side_data["rotation"])
            except (ValueError, TypeError):
                continue
            return int(round(raw)) % 360
    return None


def _build_audio(audio_stream: Optional[dict[str, Any]]) -> Optional[AudioStream]:
    """Build an :class:`AudioStream`, or None when the clip has no audio."""
    if audio_stream is None:
        return None
    return AudioStream(
        codec=audio_stream.get("codec_name", "unknown"),
        sample_rate=_optional_int(audio_stream.get("sample_rate")),
        channels=_optional_int(audio_stream.get("channels")),
        channel_layout=audio_stream.get("channel_layout"),
    )


def _extract_creation_time(
    fmt: dict[str, Any],
    video_stream: dict[str, Any],
    media_path: Path,
    use_exiftool: bool,
) -> Optional[datetime]:
    """Creation time from ffprobe tags, with an optional, explicit exiftool fallback."""
    for source in (fmt, video_stream):
        raw = source.get("tags", {}).get("creation_time")
        parsed = _parse_timestamp(raw)
        if parsed is not None:
            return parsed
    if use_exiftool:
        return _exiftool_creation_time(media_path)
    return None


def _parse_timestamp(raw: Optional[str]) -> Optional[datetime]:
    """Parse an ISO-8601 creation-time tag (tolerating a trailing ``Z``), else None."""
    if not raw:
        return None
    text = raw.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _exiftool_creation_time(media_path: Path) -> Optional[datetime]:
    """Best-effort creation time via exiftool; only called when explicitly enabled."""
    exiftool = "exiftool"
    try:
        result = subprocess.run(
            [exiftool, "-json", "-CreateDate", str(media_path)],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        logger.warning("exiftool fallback requested but exiftool is not installed")
        return None
    if result.returncode != 0:
        return None
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    if not payload:
        return None
    raw = payload[0].get("CreateDate")
    if not raw:
        return None
    # exiftool emits "YYYY:MM:DD HH:MM:SS"; normalize the date separators.
    normalized = raw.replace(":", "-", 2)
    return _parse_timestamp(normalized)


def _clean_ratio(value: Optional[str]) -> Optional[str]:
    """Return a ratio string, dropping ffprobe's ``"0:1"`` / ``"N/A"`` non-values."""
    if not value or value in ("0:1", "N/A"):
        return None
    return value


def _require_int(stream: dict[str, Any], key: str, media_path: Path) -> int:
    """Read a required integer field, raising ProbeError if absent or non-numeric."""
    value = _optional_int(stream.get(key))
    if value is None:
        raise ProbeError(f"Missing required {key!r} for the video stream in {media_path}")
    return value


def _optional_int(value: Any) -> Optional[int]:
    """Coerce a value to int, returning None for missing/non-numeric inputs."""
    if value in (None, "", "N/A"):
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None
