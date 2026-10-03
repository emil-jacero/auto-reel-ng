"""``prepare_clip``: a clip's proxy and its filmstrip as one operation (D-21).

The worker's proxy job (``proxy-job``) prepares every clip of an event; for each it needs the
proxy and then the sprite cut from it, under one progress fraction and one cancel check. The
two steps stay what they are (:func:`~.ensure.ensure_proxy`, :func:`~.filmstrip.ensure_filmstrip`);
this joins them and owns the arithmetic of the shared fraction. It reads no database and prints
nothing, like the steps it joins.

The fraction of one clip: the proxy encode is nearly all of the work, so it fills
``0 .. PROXY_SHARE``, and the sprite is the last slice. ``1.0`` is reported only once the
filmstrip is recorded.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from ..accel.profiles import AccelProfile
from ..ffmpeg.runtime import FfmpegRuntime
from .cache import ProxyEntry
from .ensure import ensure_proxy
from .filmstrip import Filmstrip, ensure_filmstrip, lookup_filmstrip
from .settings import ProxySettings

#: The share of a clip's progress that is the proxy encode; the filmstrip is the rest.
PROXY_SHARE = 0.97


@dataclass(frozen=True)
class PreparedClip:
    """A clip's complete cache entry and its recorded filmstrip."""

    entry: ProxyEntry
    filmstrip: Filmstrip


def prepare_clip(  # pylint: disable=too-many-arguments
    clip_path: Path,
    *,
    settings: ProxySettings,
    runtime: FfmpegRuntime,
    profile: AccelProfile,
    render_node: Optional[str] = None,
    on_progress: Optional[Callable[[float], None]] = None,
    should_cancel: Optional[Callable[[], bool]] = None,
) -> PreparedClip:
    """Make the clip's proxy when absent, then its filmstrip when not recorded.

    ``on_progress`` receives the fraction of this one clip done: non-decreasing, below ``1.0``
    until the filmstrip is recorded, and ``1.0`` at once (no process) when the proxy and the
    filmstrip were both complete. ``should_cancel`` goes to every ffmpeg run and is checked
    between the two steps.

    Raises:
        ProxyError: the proxy cannot be made (no filmstrip is attempted).
        ProxyCacheError: the cache directory cannot be created, read or written, or is full.
        FilmstripError: the filmstrip cannot be made; the finished proxy stays in the cache.
        FfmpegCancelledError: ``should_cancel`` reported true; nothing is left in the cache
            but entries that were complete.
    """
    clip = Path(clip_path)
    report = _Report(on_progress)
    entry = ensure_proxy(
        clip,
        settings=settings,
        runtime=runtime,
        profile=profile,
        render_node=render_node,
        on_progress=report.proxy,
        should_cancel=should_cancel,
    )
    recorded = lookup_filmstrip(entry)
    if recorded is None:
        report.proxy(1.0)
        recorded = ensure_filmstrip(clip, entry, runtime=runtime, should_cancel=should_cancel)
    report.done()
    return PreparedClip(entry=entry, filmstrip=recorded)


class _Report:
    """Maps the proxy's own fraction into the clip's, never reporting 1.0 before :meth:`done`."""

    def __init__(self, callback: Optional[Callable[[float], None]]) -> None:
        self._callback = callback
        self._highest = 0.0

    def proxy(self, fraction: float) -> None:
        """The proxy encode's fraction, scaled into the proxy's share of the clip."""
        self._send(min(max(fraction, 0.0), 1.0) * PROXY_SHARE)

    def done(self) -> None:
        """The filmstrip is recorded (or was): the clip is complete."""
        self._send(1.0)

    def _send(self, fraction: float) -> None:
        if self._callback is not None and fraction > self._highest:
            self._highest = fraction
            self._callback(fraction)


__all__ = ["PROXY_SHARE", "PreparedClip", "prepare_clip"]
