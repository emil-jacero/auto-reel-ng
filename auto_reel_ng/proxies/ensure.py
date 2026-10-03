"""``ensure_proxy``: turn one clip into a verified cache entry (D-21).

The function is pure in the engine's sense: it reads no database, prints nothing, holds no
global state other than the once-per-process sweep, and takes the runtime and the acceleration
profile as arguments, so a CLI thread, a service thread or a worker job can all call it. A
job wraps it later (``proxy-job``) and maps :class:`FfmpegCancelledError` to a canceled job.

The ladder (see :mod:`.command`): the planned path runs once. A hybrid encode that fails, or
whose output fails verification, is discarded and the clip is encoded once more on the CPU; a
stall and a cancel are never retried, and a CPU failure is final. The source clip is only read.
"""

from __future__ import annotations

import logging
import math
import re
from pathlib import Path
from typing import Callable, Optional

from ..accel.profiles import AccelProfile
from ..errors import (
    FfmpegCancelledError,
    FfmpegError,
    FfmpegStalledError,
    ProbeError,
    ProxyCacheError,
    ProxyError,
)
from ..ffmpeg.runtime import FfmpegRuntime
from ..probe.media import probe_media
from ..probe.metadata import ClipMetadata
from . import cache, spec
from .cache import ProxyEntry
from .command import EncodePath, ProxyCommand, build_proxy_command, plan_encode
from .facts import SourceFacts, make_facts, read_source_facts, write_facts
from .settings import ProxySettings
from .verify import ExpectedProxy, verify_proxy

logger = logging.getLogger(__name__)

#: Longest ``fallback_reason`` kept in the facts.
_REASON_CHARS = 300

#: ffmpeg's ``[component @ 0x…]`` prefixes on a stderr line.
_LOG_TAGS = re.compile(r"^(?:\[[^\]]*\]\s*)+")


def lookup_proxy(clip_path: Path, *, settings: ProxySettings) -> Optional[ProxyEntry]:
    """The clip's complete cache entry, or ``None``; one ``stat`` and one JSON read, no process.

    A clip that cannot be statted has no entry. An entry whose directory lacks a file, or
    whose facts are damaged or from another proxy version, is absent, never defaulted.

    Raises:
        ProxyCacheError: the cache directory cannot be read.
    """
    try:
        key = spec.proxy_key(clip_path)
    except OSError:
        return None
    return cache.read_entry(Path(settings.cache_dir) / key)


def ensure_proxy(  # pylint: disable=too-many-arguments,too-many-locals
    clip_path: Path,
    *,
    settings: ProxySettings,
    runtime: FfmpegRuntime,
    profile: AccelProfile,
    render_node: Optional[str] = None,
    on_progress: Optional[Callable[[float], None]] = None,
    should_cancel: Optional[Callable[[], bool]] = None,
) -> ProxyEntry:
    """The clip's cache entry, building and publishing it first when absent.

    A hit returns without ffprobe or ffmpeg. A miss probes the clip (bounded to
    :data:`~.spec.PROXY_PROBE_TIMEOUT_S`), plans the size and the encode path, encodes into a
    hidden build directory, verifies the result, writes ``facts.json`` and renames the
    directory to the entry. ``on_progress`` receives a fraction of the clip's duration that
    never decreases, also across a CPU retry, and ends at 1.0; ``should_cancel`` is polled
    while ffmpeg runs.

    Raises:
        ProxyError: the clip cannot be statted or probed, has no positive duration, or its
            encode or verification fails on every path (including a stall).
        ProxyCacheError: the cache directory cannot be created, read or written, or is full.
        FfmpegCancelledError: ``should_cancel`` reported true; the build directory is removed.
    """
    clip_path = Path(clip_path)
    cache_dir = Path(settings.cache_dir)
    clip = str(clip_path)
    try:
        key = spec.proxy_key(clip_path)
    except OSError as exc:
        raise ProxyError(clip, f"cannot stat the clip: {exc.strerror or exc}") from exc
    existing = cache.read_entry(cache_dir / key)
    if existing is not None:
        return existing

    # The resolved, absolute path: a relative ``file:x.mp4`` would be read as a protocol.
    source = clip_path.resolve()
    bounded = runtime.with_timeout(spec.PROXY_PROBE_TIMEOUT_S)
    meta = _probe_clip(clip, source, bounded)
    source_facts = read_source_facts(source, bounded, clip=clip)
    try:
        size = spec.proxy_dimensions(
            meta.width, meta.height, meta.sample_aspect_ratio, meta.rotation
        )
    except ValueError as exc:
        raise ProxyError(clip, f"cannot plan the proxy size: {exc}") from exc

    reporter = _MonotonicProgress(on_progress)
    part = cache.new_part_dir(cache_dir, key)
    try:
        entry = _build(
            clip=clip,
            source=source,
            part=part,
            entry_dir=cache_dir / key,
            meta=meta,
            source_facts=source_facts,
            size=size,
            runtime=runtime,
            bounded=bounded,
            profile=profile,
            render_node=render_node,
            reporter=reporter,
            should_cancel=should_cancel,
        )
    finally:
        cache.discard(part)  # a no-op after a successful rename
    reporter.finish()
    return entry


class _MonotonicProgress:
    """Forwards a progress fraction that never goes below the highest one reported.

    ffmpeg's own 1.0 means "the encode wrote its last frame", not "the proxy is published":
    verification and the rename still follow, and a failed hybrid output is encoded again. So
    the first attempt reports as ffmpeg does, capped at :data:`ATTEMPT_CEILING`; a retry (:meth:`begin_retry`)
    maps its 0..1 into the range between the highest fraction so far and
    :data:`RETRY_CEILING`, so it keeps moving; only :meth:`finish` reports 1.0.
    """

    #: The highest fraction an encode attempt reports before the proxy is published.
    ATTEMPT_CEILING = 0.95
    #: The highest fraction a CPU retry reports before the proxy is published.
    RETRY_CEILING = 0.99

    def __init__(self, callback: Optional[Callable[[float], None]]) -> None:
        self._callback = callback
        self._highest = 0.0
        self._floor = 0.0
        self._ceiling = self.ATTEMPT_CEILING
        self._retrying = False

    def __call__(self, fraction: float) -> None:
        fraction = max(0.0, min(1.0, fraction))
        if self._retrying:
            fraction = self._floor + fraction * (self._ceiling - self._floor)
        fraction = min(fraction, self._ceiling)
        if self._callback is not None and fraction > self._highest:
            self._highest = fraction
            self._callback(fraction)

    def begin_retry(self) -> None:
        """The next attempt re-encodes the clip from the start: map it above what was shown."""
        self._retrying = True
        self._floor = self._highest
        self._ceiling = max(self.RETRY_CEILING, self._floor)

    def finish(self) -> None:
        """Report 1.0: the proxy is verified and published."""
        if self._callback is not None and self._highest < 1.0:
            self._highest = 1.0
            self._callback(1.0)


def _probe_clip(clip: str, source: Path, runtime: FfmpegRuntime) -> ClipMetadata:
    """The clip's probe; a failure, or no positive duration, is a :class:`ProxyError`."""
    try:
        meta = probe_media(source, runtime=runtime)
    except ProbeError as exc:
        raise ProxyError(clip, _without(str(exc), source)) from exc
    if not math.isfinite(meta.duration) or meta.duration <= 0:
        raise ProxyError(clip, f"ffprobe reported no usable duration ({meta.duration})")
    return meta


def _without(message: str, source: Path) -> str:
    """``message`` without the probed path, which the error names already."""
    for mention in (f": {source}", f" for {source}", f" in {source}", f" {source}"):
        if mention in message:
            return message.replace(mention, "", 1)
    return message


def _build(  # pylint: disable=too-many-arguments,too-many-locals
    *,
    clip: str,
    source: Path,
    part: Path,
    entry_dir: Path,
    meta: ClipMetadata,
    source_facts: SourceFacts,
    size: tuple[int, int],
    runtime: FfmpegRuntime,
    bounded: FfmpegRuntime,
    profile: AccelProfile,
    render_node: Optional[str],
    reporter: _MonotonicProgress,
    should_cancel: Optional[Callable[[], bool]],
) -> ProxyEntry:
    """Run the ladder into ``part``, verify, write the facts and publish."""
    planned = plan_encode(meta, profile, render_node=render_node)
    fallback_reason: Optional[str] = None
    path = planned
    output = part / spec.PROXY_FILENAME
    while True:
        command = build_proxy_command(
            meta,
            source=source,
            output=output,
            path=path,
            profile=profile,
            render_node=render_node,
            size=size,
        )
        expected = ExpectedProxy(
            clip=clip,
            width=size[0],
            height=size[1],
            duration=_video_duration(meta, source_facts),
            has_audio=meta.has_audio,
            declared_frames=source_facts.declared_frames,
            path=path.value,
        )
        try:
            frames = _encode_and_verify(
                command,
                expected,
                output,
                runtime=runtime,
                bounded=bounded,
                reporter=reporter,
                should_cancel=should_cancel,
            )
            break
        except _AttemptFailed as failure:
            if path is not EncodePath.HYBRID or not failure.retry:
                raise ProxyError(clip, failure.reason) from failure
            fallback_reason = _one_line(failure, source, part)
            logger.warning(
                "Hybrid proxy of %s failed (%s); encoding on the CPU", clip, fallback_reason
            )
            _remove(output)
            reporter.begin_retry()
            path = EncodePath.CPU
    facts = make_facts(
        clip=meta,
        source=source_facts,
        frames=frames,
        size=size,
        encode_path=path.value,
        fallback_reason=fallback_reason,
    )
    try:
        write_facts(part, facts)
    except OSError as exc:
        raise ProxyCacheError(f"{part.parent}: cannot write proxies: {exc}") from exc
    published = cache.publish(part, entry_dir)
    logger.debug("Proxy of %s on the %s path: %s", clip, path.value, published.directory)
    return published


def _video_duration(meta: ClipMetadata, source_facts: SourceFacts) -> float:
    """The duration the proxy's video stream must have: the source's video stream's.

    The container duration is the fallback only when the container gives no stream duration
    (some Matroska files); it is then the only duration the probe has.
    """
    if source_facts.video_duration is not None:
        return source_facts.video_duration
    return meta.duration


class _AttemptFailed(Exception):
    """One encode attempt failed: ``reason`` is the cause, ``retry`` whether the CPU may serve."""

    def __init__(self, reason: str, *, retry: bool, stderr: str = "") -> None:
        super().__init__(reason)
        self.reason = reason
        self.retry = retry
        #: ffmpeg's stderr, when the attempt failed in ffmpeg itself.
        self.stderr = stderr


def _encode_and_verify(  # pylint: disable=too-many-arguments
    command: ProxyCommand,
    expected: ExpectedProxy,
    output: Path,
    *,
    runtime: FfmpegRuntime,
    bounded: FfmpegRuntime,
    reporter: _MonotonicProgress,
    should_cancel: Optional[Callable[[], bool]],
) -> int:
    """One encode and its verification; returns the proxy's frame count.

    Raises:
        _AttemptFailed: ffmpeg failed or the output failed verification (``retry`` true), or
            ffmpeg stalled (``retry`` false).
        ProxyCacheError: ffmpeg reported a full disk.
        FfmpegCancelledError: propagated unchanged.
    """
    try:
        runtime.run_with_progress(
            list(command.args),
            duration=command.duration,
            on_progress=reporter,
            stall_timeout=spec.PROXY_STALL_TIMEOUT_S,
            should_cancel=should_cancel,
        )
    except FfmpegCancelledError:
        raise
    except FfmpegStalledError as exc:
        reason = f"ffmpeg stalled on the {command.path.value} path: {_first_line(exc)}"
        raise _AttemptFailed(reason, retry=False) from exc
    except FfmpegError as exc:
        full = cache.is_full_disk(str(exc))
        if full is not None:
            raise ProxyCacheError(f"{output.parent.parent}: cannot write proxies: {full}") from exc
        reason = f"ffmpeg failed on the {command.path.value} path: {exc}"
        raise _AttemptFailed(reason, retry=True, stderr=str(exc)) from exc
    if not output.is_file() or output.stat().st_size == 0:
        reason = f"ffmpeg exited 0 but wrote no proxy ({command.path.value} path)"
        raise _AttemptFailed(reason, retry=True)
    try:
        return verify_proxy(output, expected=expected, runtime=bounded)
    except ProxyError as exc:
        raise _AttemptFailed(exc.reason, retry=True) from exc


def _first_line(exc: BaseException) -> str:
    text = str(exc).strip()
    return text.splitlines()[0] if text else type(exc).__name__


def _one_line(failure: _AttemptFailed, source: Path, part: Path) -> str:
    """The one-line cause of a failed attempt: ffmpeg's last stderr line, or the reason's first."""
    _, _, stderr = failure.stderr.partition("\nstderr:\n")
    last = next((line.strip() for line in reversed(stderr.splitlines()) if line.strip()), "")
    text = _LOG_TAGS.sub("", last) or failure.reason
    text = text.replace(str(source), source.name).replace(str(part), "<build>")
    return text.splitlines()[0][:_REASON_CHARS] if text else "unknown failure"


def _remove(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass


__all__ = ["ensure_proxy", "lookup_proxy"]
