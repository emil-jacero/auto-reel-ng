"""The target spec: the common canvas every segment conforms to (decision **D-E**).

Derived from the resolved ``look`` + the probe facts of every clip in the plan + the
selected acceleration profile's usable encoders. No canvas property is taken from a
clip because of its position in the plan: resolution defaults to 1920x1080 and fps to
the highest probed clip fps. It is the single explicit object the
equivalence check and post-render verification compare every segment/output
against, and it grounds the chosen codec in an encoder the host can actually run
(AV1 a first-class option, D-5): an unencodable codec fails loud rather than
silently substituting a different one.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from ..accel.models import OpClass, OpParams
from ..accel.profiles.base import AccelProfile
from ..errors import AccelError, RenderError
from ..probe.metadata import ClipMetadata

#: Defaults applied when the resolved ``look`` is silent on a parameter.
DEFAULT_TARGET_RESOLUTION = (1920, 1080)
DEFAULT_VIDEO_CODEC = "h264"
DEFAULT_PIX_FMT = "yuv420p"
DEFAULT_FILL_COLOR = "black"
DEFAULT_AUDIO_CODEC = "aac"
DEFAULT_AUDIO_SAMPLE_RATE = 48000
DEFAULT_AUDIO_CHANNELS = 2


@dataclass(frozen=True)
class TargetSpec:  # pylint: disable=too-many-instance-attributes
    """The fully-explicit canvas every segment is normalized/compared to."""

    width: int
    height: int
    fps: float
    video_codec: str
    video_encoder: str
    pix_fmt: str
    sample_aspect_ratio: str
    fill_color: str
    audio_codec: str
    audio_sample_rate: int
    audio_channels: int

    def to_dict(self) -> dict[str, Any]:
        """Convert to a plain dict for debug logging and golden tests."""
        return {
            "width": self.width,
            "height": self.height,
            "fps": self.fps,
            "video_codec": self.video_codec,
            "video_encoder": self.video_encoder,
            "pix_fmt": self.pix_fmt,
            "sample_aspect_ratio": self.sample_aspect_ratio,
            "fill_color": self.fill_color,
            "audio_codec": self.audio_codec,
            "audio_sample_rate": self.audio_sample_rate,
            "audio_channels": self.audio_channels,
        }


def _resolution(look: Mapping[str, Any]) -> tuple[int, int]:
    """``look.target_resolution`` (a pair of positive ints) or 1920x1080."""
    raw = look.get("target_resolution")
    if raw is None:
        return DEFAULT_TARGET_RESOLUTION
    if (
        not isinstance(raw, (list, tuple))
        or len(raw) != 2
        or not all(isinstance(v, int) and not isinstance(v, bool) and v > 0 for v in raw)
    ):
        raise RenderError(
            f"look.target_resolution must be a [width, height] pair of positive integers, "
            f"got {raw!r}"
        )
    return raw[0], raw[1]


def _fps(look: Mapping[str, Any], clips: Sequence[ClipMetadata]) -> float:
    """``look.fps`` (a positive number) or the highest probed fps among ``clips``."""
    raw = look.get("fps")
    if raw is not None:
        if isinstance(raw, bool) or not isinstance(raw, (int, float)) or raw <= 0:
            raise RenderError(f"look.fps must be a positive number, got {raw!r}")
        return float(raw)
    if not clips:
        raise RenderError("render plan has no clips to derive the target fps from")
    return max(clip.fps for clip in clips)


def _resolve_encoder(profile: AccelProfile, codec: str) -> str:
    """Return the ffmpeg encoder the profile will use for ``codec``.

    The profile answers with a hardware encoder when usable, else the guaranteed
    CPU fallback. A codec neither the hardware nor the CPU can encode raises
    :class:`AccelError` inside the profile, which we surface as a loud
    :class:`RenderError` rather than substituting a different codec.
    """
    try:
        fragment = profile.fragment(OpClass.ENCODE, OpParams(codec=codec))
    except AccelError as exc:
        raise RenderError(
            f"requested video codec {codec!r} has no usable hardware or CPU encoder: {exc}"
        ) from exc
    # The encode fragment's output flags are ("-c:v", "<encoder>").
    flags = fragment.output_flags
    if len(flags) != 2 or flags[0] != "-c:v":
        raise RenderError(
            f"profile returned an unexpected encode fragment for {codec!r}: {flags!r}"
        )
    return flags[1]


def derive_target(
    plan_look: Mapping[str, Any],
    clips: Sequence[ClipMetadata],
    profile: AccelProfile,
) -> TargetSpec:
    """Derive the :class:`TargetSpec` from look + all plan clips + profile.

    Resolution comes from ``look.target_resolution`` (default 1920x1080); fps from
    ``look.fps`` (default: the highest probed fps among ``clips``); codec/pix_fmt/fill
    from the look; SAR is 1:1; audio params from the look (with sane defaults).
    The chosen codec is validated against the profile's usable encoders.
    """
    width, height = _resolution(plan_look)
    codec = str(plan_look.get("video_codec", DEFAULT_VIDEO_CODEC))
    encoder = _resolve_encoder(profile, codec)

    return TargetSpec(
        width=width,
        height=height,
        fps=_fps(plan_look, clips),
        video_codec=codec,
        video_encoder=encoder,
        pix_fmt=str(plan_look.get("pix_fmt", DEFAULT_PIX_FMT)),
        sample_aspect_ratio="1:1",
        fill_color=str(plan_look.get("fill_color", DEFAULT_FILL_COLOR)),
        audio_codec=str(plan_look.get("audio_codec", DEFAULT_AUDIO_CODEC)),
        audio_sample_rate=int(plan_look.get("audio_sample_rate", DEFAULT_AUDIO_SAMPLE_RATE)),
        audio_channels=int(plan_look.get("audio_channels", DEFAULT_AUDIO_CHANNELS)),
    )


__all__ = ["TargetSpec", "derive_target"]
