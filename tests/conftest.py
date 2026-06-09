"""Shared fixtures: a real :class:`FfmpegRuntime` and a synthetic-clip factory.

Clips are generated on demand from ``ffmpeg lavfi`` sources (``testsrc`` + ``sine``),
so the test suite needs no checked-in media. Tests requiring ffmpeg are skipped if no
ffmpeg >= 7.1 is available.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Callable, Optional

import pytest

from auto_reel_ng.errors import FfmpegError
from auto_reel_ng.ffmpeg.runtime import FfmpegRuntime

MakeClip = Callable[..., Path]


def fonts_available() -> bool:
    """True when Cairo + Pango and the bundled default font are usable on this host.

    Mirrors the "has GPU" gate: the renderer's image/render tests are skipped when
    the Cairo/Pango backend or the bundled DejaVu Sans family is unavailable, so the
    suite passes on a host (or venv) without the system libraries installed.
    """
    try:
        import gi  # noqa: PLC0415

        gi.require_version("Pango", "1.0")
        gi.require_version("PangoCairo", "1.0")
        import cairo  # noqa: F401,PLC0415
        from gi.repository import Pango, PangoCairo  # noqa: PLC0415
    except (ImportError, ValueError):
        return False
    context = PangoCairo.FontMap.get_default().create_context()
    desc = Pango.FontDescription()
    desc.set_family("DejaVu Sans")
    font = context.load_font(desc)
    if font is None:
        return False
    return font.describe().get_family().strip().lower() == "dejavu sans"


@pytest.fixture
def has_fonts() -> None:
    """Skip a test unless Cairo/Pango and the bundled default font are available."""
    if not fonts_available():
        pytest.skip("Cairo/Pango or the bundled default font (DejaVu Sans) not available")


@pytest.fixture(scope="session")
def runtime() -> FfmpegRuntime:
    """A real runtime backed by the system ffmpeg; skip the test if none is usable."""
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        pytest.skip("ffmpeg/ffprobe not available on PATH")
    try:
        return FfmpegRuntime()
    except FfmpegError as exc:
        pytest.skip(f"usable ffmpeg >= 7.1 not available: {exc}")


@pytest.fixture
def make_clip(tmp_path: Path, runtime: FfmpegRuntime) -> MakeClip:
    """Return a factory that renders a synthetic clip with the requested properties."""

    def _make(
        name: str = "clip.mp4",
        *,
        duration: float = 1.0,
        width: int = 320,
        height: int = 240,
        fps: int = 30,
        audio: bool = True,
        setsar: Optional[str] = None,
        rotate: Optional[int] = None,
        color_trc: Optional[str] = None,
        creation_time: Optional[str] = None,
    ) -> Path:
        out = tmp_path / name
        cmd: list[str] = [runtime.ffmpeg_path, "-y"]
        # Rotation is a display-matrix property: tag it via the input-side
        # -display_rotation and keep -noautorotate so the matrix survives re-encode.
        if rotate is not None:
            cmd += ["-noautorotate", "-display_rotation", str(rotate)]
        cmd += [
            "-f",
            "lavfi",
            "-i",
            f"testsrc=size={width}x{height}:rate={fps}:duration={duration}",
        ]
        if audio:
            cmd += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}"]
        # Build a single -vf chain for SAR and color-transfer tagging.
        filters: list[str] = []
        if setsar is not None:
            filters.append(f"setsar={setsar}")
        if color_trc is not None:
            filters.append(f"setparams=color_trc={color_trc}")
        if filters:
            cmd += ["-vf", ",".join(filters)]
        cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p"]
        if audio:
            cmd += ["-c:a", "aac", "-shortest"]
        if creation_time is not None:
            cmd += ["-metadata", f"creation_time={creation_time}"]
        cmd += [str(out)]
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        return out

    return _make
