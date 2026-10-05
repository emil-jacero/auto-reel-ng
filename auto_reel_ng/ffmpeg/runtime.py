"""Binary-agnostic ffmpeg/ffprobe runtime (locked decision D-1).

A single :class:`FfmpegRuntime` resolves the ``ffmpeg`` and ``ffprobe`` binaries once,
asserts ffmpeg >= 7.1, and is then injected wherever commands run. This replaces
auto-reel's pattern of constructing a wrapper per ``Clip``/``Movie`` (re-running
``shutil.which`` constantly with no version gate).

Resolution precedence per binary: explicit constructor argument -> environment variable
(``AUTO_REEL_NG_FFMPEG`` / ``AUTO_REEL_NG_FFPROBE``) -> bundled jellyfin-ffmpeg ->
system ``PATH``.
"""

from __future__ import annotations

import contextlib
import copy
import logging
import math
import os
import queue
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import IO, Callable, List, Optional, Sequence

from ..errors import (
    FfmpegCancelledError,
    FfmpegError,
    FfmpegStalledError,
    FfmpegTimeoutError,
    FfmpegVersionError,
)

logger = logging.getLogger(__name__)

#: Minimum supported ffmpeg version. Later filter work (e.g. ``pad_vaapi``) is 7.1-only,
#: so the gate fails loud at startup rather than mid-render.
REQUIRED_FFMPEG_VERSION = (7, 1)

#: Default install directory for jellyfin-ffmpeg (D-1); checked before PATH.
JELLYFIN_FFMPEG_DIR = "/usr/lib/jellyfin-ffmpeg"

ENV_FFMPEG = "AUTO_REEL_NG_FFMPEG"
ENV_FFPROBE = "AUTO_REEL_NG_FFPROBE"

#: How long a bounded command is given, after it was killed, to be reaped and to hand back
#: its output. A child stuck in the kernel (a read from a stalled removable drive) ignores
#: ``SIGKILL`` until that I/O returns; the caller is released after this and the child
#: is abandoned to the kernel rather than waited for.
KILL_GRACE_SECONDS = 5.0

#: How much of a killed command's stderr (its tail) a timeout error keeps as evidence.
_TIMEOUT_STDERR_CHARS = 2000

#: Every command's output is decoded as UTF-8; a byte that is not (a Latin-1 file name
#: that ffmpeg echoes on stderr) shows as its backslash escape instead of raising.
_ENCODING = "utf-8"
_ERRORS = "backslashreplace"

#: How often a progress run wakes with no output to test its deadline and cancel check;
#: bounds how late a stall or a cancel is noticed.
_WAKE_SECONDS = 0.25

#: At most this often a progress run asks its cancel check whether to stop.
CANCEL_POLL_INTERVAL_S = 1.0

ProgressCallback = Callable[[float], None]
CancelCheck = Callable[[], bool]

#: Marks the end of ffmpeg's progress output on the line queue.
_END_OF_OUTPUT = object()


def parse_ffmpeg_version(version_output: str) -> tuple[int, int]:
    """Parse ``(major, minor)`` from ``ffmpeg -version`` output.

    Raises:
        FfmpegVersionError: if no ``major.minor`` version can be found (e.g. an
            ``N-…`` git build), echoing the raw text so the user can override.
    """
    match = re.search(r"ffmpeg version (\d+)\.(\d+)", version_output)
    if match is None:
        # Some distro builds drop the leading "ffmpeg"; accept a generic "version X.Y".
        match = re.search(r"version (\d+)\.(\d+)", version_output)
    if match is None:
        first_line = version_output.strip().splitlines()[0] if version_output.strip() else ""
        raise FfmpegVersionError(
            f"Could not parse an ffmpeg version from: {first_line!r}. "
            f"Required minimum is {REQUIRED_FFMPEG_VERSION[0]}.{REQUIRED_FFMPEG_VERSION[1]}; "
            f"set {ENV_FFMPEG} to a known-good build."
        )
    return int(match.group(1)), int(match.group(2))


def _resolve_binary(
    name: str,
    explicit: Optional[str],
    env_var: str,
) -> str:
    """Resolve one executable by precedence, raising :class:`FfmpegError` if missing.

    Order: explicit argument -> environment variable -> bundled jellyfin-ffmpeg -> PATH.
    An explicit/env path that does not point at an executable is itself an error.
    """
    # 1. Explicit constructor argument.
    if explicit:
        if _is_executable(explicit):
            return str(Path(explicit))
        raise FfmpegError(f"Configured {name} path is not an executable file: {explicit}")

    # 2. Environment variable.
    env_value = os.environ.get(env_var)
    if env_value:
        if _is_executable(env_value):
            return str(Path(env_value))
        raise FfmpegError(f"{env_var} does not point at an executable {name}: {env_value}")

    # 3. Bundled jellyfin-ffmpeg default.
    bundled = Path(JELLYFIN_FFMPEG_DIR) / name
    if _is_executable(str(bundled)):
        return str(bundled)

    # 4. System PATH.
    found = shutil.which(name)
    if found:
        return found

    raise FfmpegError(
        f"Could not locate the {name!r} binary. Looked at the explicit argument, "
        f"${env_var}, {JELLYFIN_FFMPEG_DIR}, and PATH."
    )


def _collect(stream: IO[str], chunks: List[str]) -> None:
    """Read ``stream`` to EOF into ``chunks`` (the stderr drain thread's body)."""
    chunks.append(stream.read())


def _pump(stream: IO[str], lines: "queue.Queue[object]") -> None:
    """Move ``stream``'s lines onto ``lines``, then the end marker (the reader thread's body)."""
    try:
        for line in stream:
            lines.put(line)
    finally:
        lines.put(_END_OF_OUTPUT)


def _out_time_us(line: str) -> Optional[int]:
    """The output time, in microseconds, of an ``out_time_us=``/``out_time_ms=`` line, else None."""
    line = line.strip()
    if not (line.startswith("out_time_us=") or line.startswith("out_time_ms=")):
        return None
    # out_time_us is microseconds; out_time_ms is (historically) also microseconds.
    try:
        return int(line.split("=", 1)[1])
    except ValueError:  # "N/A", empty or garbage
        return None


def _fraction(line: str, duration: float) -> Optional[float]:
    """A 0.0–1.0 fraction from a ``-progress`` ``key=value`` line, else None."""
    if duration <= 0:
        return None
    micros = _out_time_us(line)
    if micros is not None:
        return micros / 1_000_000.0 / duration
    if line.strip() == "progress=end":
        return 1.0
    return None


def _kill_and_reap(proc: subprocess.Popen[str], cmd: Sequence[str]) -> bool:
    """Kill ``proc`` and wait at most :data:`KILL_GRACE_SECONDS` for it to go.

    Returns whether it was reaped. A child stuck in the kernel ignores ``SIGKILL``; it is
    logged by pid and command and abandoned rather than waited for, so the caller's
    failure is not itself a hang.
    """
    proc.kill()
    try:
        proc.wait(timeout=KILL_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        logger.error(
            "Abandoning killed ffmpeg pid %s that did not exit within %gs: %s",
            proc.pid,
            KILL_GRACE_SECONDS,
            " ".join(cmd),
        )
        return False
    return True


class _ProgressWatch:  # pylint: disable=too-many-instance-attributes
    """One progress run's bookkeeping: the fraction, the stall clock and the cancel poll."""

    def __init__(
        self,
        duration: float,
        on_progress: Optional[ProgressCallback],
        stall_timeout: Optional[float],
        should_cancel: Optional[CancelCheck],
    ) -> None:
        self.last_fraction = 0.0
        self.silent_seconds = 0.0
        self._duration = duration
        self._on_progress = on_progress
        self._stall_timeout = stall_timeout
        self._should_cancel = should_cancel
        self._best_out_us: Optional[int] = None
        self._last_advance = time.monotonic()
        self._next_poll = self._last_advance + CANCEL_POLL_INTERVAL_S

    def run(self, lines: "queue.Queue[object]") -> Optional[str]:
        """Consume ``lines`` until the output ends (``None``) or a stop is due.

        Returns ``"cancel"`` or ``"stall"`` when the run must be killed, else ``None`` at the
        end of the output. A line already received is always handled before the clocks are
        tested, and a cancel wins over a simultaneous stall.
        """
        while True:
            try:
                item = lines.get(timeout=_WAKE_SECONDS)
            except queue.Empty:
                item = None
            if item is _END_OF_OUTPUT:
                return None
            if isinstance(item, str):
                self._handle(item)
            now = time.monotonic()
            if self._should_cancel is not None and now >= self._next_poll:
                self._next_poll = now + CANCEL_POLL_INTERVAL_S
                if self._should_cancel():
                    return "cancel"
            self.silent_seconds = now - self._last_advance
            if self._stall_timeout is not None and self.silent_seconds >= self._stall_timeout:
                return "stall"

    def _handle(self, line: str) -> None:
        """Advance the stall clock and report the fraction for one ``-progress`` line."""
        micros = _out_time_us(line)
        if micros is not None and (self._best_out_us is None or micros > self._best_out_us):
            self._best_out_us = micros
            self._last_advance = time.monotonic()
        elif line.strip() == "progress=end":
            self._last_advance = time.monotonic()
        fraction = _fraction(line, self._duration)
        if fraction is None:
            return
        fraction = max(self.last_fraction, min(1.0, fraction))
        if fraction > self.last_fraction or fraction >= 1.0:
            self.last_fraction = fraction
            if self._on_progress is not None:
                self._on_progress(fraction)


def _is_executable(path: str) -> bool:
    """Return True if ``path`` is an existing, executable regular file."""
    p = Path(path)
    return p.is_file() and os.access(path, os.X_OK)


class FfmpegRuntime:
    """Resolves ffmpeg/ffprobe, gates the version, and runs commands."""

    def __init__(
        self,
        ffmpeg_path: Optional[str] = None,
        ffprobe_path: Optional[str] = None,
    ) -> None:
        """Resolve both binaries and assert ffmpeg >= 7.1.

        Args:
            ffmpeg_path: Explicit ffmpeg path overriding env/bundled/PATH.
            ffprobe_path: Explicit ffprobe path overriding env/bundled/PATH.

        Raises:
            FfmpegError: if either binary cannot be resolved.
            FfmpegVersionError: if the resolved ffmpeg is older than 7.1 or unparseable.
        """
        self._ffmpeg_path = _resolve_binary("ffmpeg", ffmpeg_path, ENV_FFMPEG)
        self._ffprobe_path = _resolve_binary("ffprobe", ffprobe_path, ENV_FFPROBE)
        logger.debug("Resolved ffmpeg=%s ffprobe=%s", self._ffmpeg_path, self._ffprobe_path)

        self._timeout: Optional[float] = None
        self._version = self._assert_version()

    @property
    def ffmpeg_path(self) -> str:
        """Resolved path to the ffmpeg executable."""
        return self._ffmpeg_path

    @property
    def ffprobe_path(self) -> str:
        """Resolved path to the ffprobe executable."""
        return self._ffprobe_path

    @property
    def version(self) -> tuple[int, int]:
        """Detected ffmpeg ``(major, minor)`` version."""
        return self._version

    @property
    def timeout(self) -> Optional[float]:
        """The bound, in seconds, that :meth:`run` and :meth:`run_ffprobe` apply (None: none)."""
        return self._timeout

    def with_timeout(self, seconds: float) -> FfmpegRuntime:
        """A view of this runtime whose ``run`` and ``run_ffprobe`` are bounded to ``seconds``.

        The view shares the resolved binaries and the detected version; this runtime, which
        other threads use, is not changed. A command that overruns is killed and raises
        :class:`FfmpegTimeoutError`. ``run_with_progress`` is not bounded.

        Raises:
            ValueError: ``seconds`` is not a positive, finite number.
        """
        if not math.isfinite(seconds) or seconds <= 0:
            raise ValueError(f"A timeout must be a positive, finite number of seconds: {seconds}")
        bounded = copy.copy(self)
        bounded._timeout = float(seconds)  # pylint: disable=protected-access
        return bounded

    # -- version gate --------------------------------------------------------

    def _query_version_text(self) -> str:
        """Return raw ``ffmpeg -version`` text (separate seam so tests can mock it)."""
        result = subprocess.run(
            [self._ffmpeg_path, "-version"],
            capture_output=True,
            check=False,
            text=True,
            encoding=_ENCODING,
            errors=_ERRORS,
        )
        return result.stdout or result.stderr

    def _assert_version(self) -> tuple[int, int]:
        """Detect the version and fail loud if it is below the required minimum."""
        detected = parse_ffmpeg_version(self._query_version_text())
        if detected < REQUIRED_FFMPEG_VERSION:
            raise FfmpegVersionError(
                f"ffmpeg {detected[0]}.{detected[1]} is too old; "
                f"auto-reel-ng requires >= {REQUIRED_FFMPEG_VERSION[0]}."
                f"{REQUIRED_FFMPEG_VERSION[1]}."
            )
        return detected

    # -- command execution ---------------------------------------------------

    def run(self, args: Sequence[str]) -> subprocess.CompletedProcess[str]:
        """Run ``ffmpeg <args>`` with captured output and no shell.

        Raises:
            FfmpegError: on non-zero exit, carrying exit code, command, and stderr.
        """
        return self._run(self._ffmpeg_path, args)

    def run_ffprobe(self, args: Sequence[str]) -> subprocess.CompletedProcess[str]:
        """Run ``ffprobe <args>`` with captured output and no shell.

        Raises:
            FfmpegError: on non-zero exit, carrying exit code, command, and stderr.
        """
        return self._run(self._ffprobe_path, args)

    def _run(self, executable: str, args: Sequence[str]) -> subprocess.CompletedProcess[str]:
        cmd = [executable, *args]
        # Not ``subprocess.run`` (nor a ``with Popen`` block): both ``wait()`` on the child
        # after killing it, which never returns while it is stuck in the kernel.
        proc = subprocess.Popen(  # pylint: disable=consider-using-with
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding=_ENCODING,
            errors=_ERRORS,
        )
        try:
            stdout, stderr = proc.communicate(timeout=self._timeout)
        except subprocess.TimeoutExpired as exc:
            raise self._timed_out(proc, cmd) from exc
        except BaseException:
            proc.kill()  # never leave ffmpeg running behind a failed caller
            with contextlib.suppress(subprocess.TimeoutExpired):
                proc.wait(timeout=KILL_GRACE_SECONDS)
            raise
        if proc.returncode != 0:
            raise FfmpegError(
                f"Command exited {proc.returncode}: {' '.join(cmd)}\nstderr:\n{stderr.strip()}"
            )
        return subprocess.CompletedProcess(cmd, proc.returncode, stdout, stderr)

    def _timed_out(self, proc: subprocess.Popen[str], cmd: Sequence[str]) -> FfmpegTimeoutError:
        """Kill the overrunning ``proc``, wait a bounded time for it to go, and build the error."""
        proc.kill()
        stderr = ""
        try:
            _, stderr = proc.communicate(timeout=KILL_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            logger.warning(
                "Abandoning a killed command that did not exit within %gs: %s",
                KILL_GRACE_SECONDS,
                " ".join(cmd),
            )
            for pipe in (proc.stdout, proc.stderr):
                if pipe is not None:
                    pipe.close()
        message = f"Command timed out after {self._timeout:g}s: {' '.join(cmd)}"
        evidence = (stderr or "").strip()
        if evidence:
            message += f"\nstderr:\n{evidence[-_TIMEOUT_STDERR_CHARS:]}"
        return FfmpegTimeoutError(message)

    def run_with_progress(  # pylint: disable=too-many-locals
        self,
        args: Sequence[str],
        *,
        duration: float,
        on_progress: Optional[ProgressCallback] = None,
        stall_timeout: Optional[float] = None,
        should_cancel: Optional[CancelCheck] = None,
    ) -> str:
        """Run ``ffmpeg <args>`` streaming ``-progress`` to compute a 0.0–1.0 fraction.

        Returns the stderr text collected while the output was streamed (the detection
        filters' log lines land there).

        The optional ``on_progress`` callback is invoked with a non-decreasing fraction
        derived from ``out_time`` / ``duration``. Its absence does not change behavior.

        ``stall_timeout`` (seconds) kills ffmpeg when its reported output time has not
        advanced for that long, counted from launch; ``should_cancel`` is polled about
        once a second (:data:`CANCEL_POLL_INTERVAL_S`) and kills ffmpeg when it returns
        true. Both are opt-in; the bound below on a process that closed its output but has not
        exited is not. A killed process is waited for at most
        :data:`KILL_GRACE_SECONDS`, then abandoned (logged), so the error still surfaces.

        Raises:
            FfmpegStalledError: ffmpeg made no progress for ``stall_timeout`` seconds, or
                closed its progress output and then did not exit.
            FfmpegCancelledError: ``should_cancel`` returned true.
            FfmpegError: on non-zero exit, carrying the exit code and stderr.
            Exception: whatever ``on_progress`` or ``should_cancel`` raised; ffmpeg is killed.
        """
        cmd = [self._ffmpeg_path, "-nostats", "-progress", "pipe:1", *args]
        # Not a ``with`` block: its exit ``wait()``s on the child, which never returns for
        # one stuck in the kernel after it was killed.
        proc = subprocess.Popen(  # pylint: disable=consider-using-with
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding=_ENCODING,
            errors=_ERRORS,
        )
        assert proc.stdout is not None and proc.stderr is not None
        # Drain stderr while stdout is streamed: reading it only after stdout's EOF
        # deadlocks as soon as ffmpeg's stderr fills its pipe, which can be as small
        # as one page when the user is over the kernel's pipe-user-pages-soft limit.
        stderr_chunks: List[str] = []
        drain = threading.Thread(target=_collect, args=(proc.stderr, stderr_chunks), daemon=True)
        # stdout is read on a thread too, so this one can wake on a clock while ffmpeg is silent.
        lines: "queue.Queue[object]" = queue.Queue()
        reader = threading.Thread(target=_pump, args=(proc.stdout, lines), daemon=True)
        drain.start()
        reader.start()
        try:
            watch = _ProgressWatch(duration, on_progress, stall_timeout, should_cancel)
            try:
                verdict = watch.run(lines)
                if verdict is None:
                    try:
                        proc.wait(timeout=KILL_GRACE_SECONDS)
                    except subprocess.TimeoutExpired:
                        verdict = "unexited"
            except BaseException:
                _kill_and_reap(proc, cmd)  # never leave ffmpeg running behind a failed caller
                raise
            if verdict is not None:
                _kill_and_reap(proc, cmd)
            drain.join(timeout=KILL_GRACE_SECONDS)
            stderr = "".join(stderr_chunks)
            if verdict == "cancel":
                raise FfmpegCancelledError(f"ffmpeg canceled: {' '.join(cmd)}")
            if verdict is not None:
                if verdict == "unexited":
                    what = f"closed its progress output but did not exit within {KILL_GRACE_SECONDS:g}s"
                else:
                    what = f"no progress for {watch.silent_seconds:.0f}s (limit {stall_timeout:g}s)"
                message = f"ffmpeg stalled: {what}: {' '.join(cmd)}"
                if stderr.strip():
                    message += f"\nstderr:\n{stderr.strip()[-_TIMEOUT_STDERR_CHARS:]}"
                raise FfmpegStalledError(message)
            if proc.returncode != 0:
                raise FfmpegError(
                    f"Command exited {proc.returncode}: {' '.join(cmd)}\nstderr:\n{stderr.strip()}"
                )
            if on_progress is not None and watch.last_fraction < 1.0:
                on_progress(1.0)
            return stderr
        finally:
            # Close a pipe only once its thread is done with it: closing one under a blocked
            # reader would wait on the reader (an abandoned child keeps it blocked).
            for thread, pipe in ((reader, proc.stdout), (drain, proc.stderr)):
                thread.join(timeout=0.2)
                if not thread.is_alive():
                    pipe.close()

    # -- raw capability text (interpretation is a later change) --------------

    def hwaccels(self) -> str:
        """Raw text of ``ffmpeg -hwaccels``."""
        return self.run(["-hide_banner", "-hwaccels"]).stdout

    def encoders(self) -> str:
        """Raw text of ``ffmpeg -encoders``."""
        return self.run(["-hide_banner", "-encoders"]).stdout

    def decoders(self) -> str:
        """Raw text of ``ffmpeg -decoders``."""
        return self.run(["-hide_banner", "-decoders"]).stdout

    def filters(self) -> str:
        """Raw text of ``ffmpeg -filters``."""
        return self.run(["-hide_banner", "-filters"]).stdout
