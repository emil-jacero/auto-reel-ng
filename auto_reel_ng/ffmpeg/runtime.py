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

import logging
import os
import re
import shutil
import subprocess
import threading
from pathlib import Path
from typing import IO, Callable, List, Optional, Sequence

from ..errors import FfmpegError, FfmpegVersionError

logger = logging.getLogger(__name__)

#: Minimum supported ffmpeg version. Later filter work (e.g. ``pad_vaapi``) is 7.1-only,
#: so the gate fails loud at startup rather than mid-render.
REQUIRED_FFMPEG_VERSION = (7, 1)

#: Default install directory for jellyfin-ffmpeg (D-1); checked before PATH.
JELLYFIN_FFMPEG_DIR = "/usr/lib/jellyfin-ffmpeg"

ENV_FFMPEG = "AUTO_REEL_NG_FFMPEG"
ENV_FFPROBE = "AUTO_REEL_NG_FFPROBE"

ProgressCallback = Callable[[float], None]


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

    # -- version gate --------------------------------------------------------

    def _query_version_text(self) -> str:
        """Return raw ``ffmpeg -version`` text (separate seam so tests can mock it)."""
        result = subprocess.run(
            [self._ffmpeg_path, "-version"],
            capture_output=True,
            text=True,
            check=False,
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

    @staticmethod
    def _run(executable: str, args: Sequence[str]) -> subprocess.CompletedProcess[str]:
        cmd = [executable, *args]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise FfmpegError(
                f"Command exited {result.returncode}: {' '.join(cmd)}\n"
                f"stderr:\n{result.stderr.strip()}"
            )
        return result

    def run_with_progress(
        self,
        args: Sequence[str],
        *,
        duration: float,
        on_progress: Optional[ProgressCallback] = None,
    ) -> None:
        """Run ``ffmpeg <args>`` streaming ``-progress`` to compute a 0.0–1.0 fraction.

        The optional ``on_progress`` callback is invoked with a non-decreasing fraction
        derived from ``out_time`` / ``duration``. Its absence does not change behavior.

        Raises:
            FfmpegError: on non-zero exit, carrying the exit code and stderr.
        """
        cmd = [self._ffmpeg_path, "-nostats", "-progress", "pipe:1", *args]
        with subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        ) as proc:
            last_fraction = 0.0
            assert proc.stdout is not None and proc.stderr is not None
            # Drain stderr while stdout is streamed: reading it only after stdout's EOF
            # deadlocks as soon as ffmpeg's stderr fills its pipe, which can be as small
            # as one page when the user is over the kernel's pipe-user-pages-soft limit.
            stderr_chunks: List[str] = []
            drain = threading.Thread(
                target=_collect, args=(proc.stderr, stderr_chunks), daemon=True
            )
            drain.start()
            try:
                for line in proc.stdout:
                    fraction = self._parse_progress_line(line, duration)
                    if fraction is None:
                        continue
                    fraction = max(last_fraction, min(1.0, fraction))
                    if fraction > last_fraction or fraction >= 1.0:
                        last_fraction = fraction
                        if on_progress is not None:
                            on_progress(fraction)
            except BaseException:
                proc.kill()  # never leave ffmpeg running behind a failed caller
                raise
            finally:
                drain.join()
            stderr = "".join(stderr_chunks)
            returncode = proc.wait()
        if returncode != 0:
            raise FfmpegError(
                f"Command exited {returncode}: {' '.join(cmd)}\nstderr:\n{stderr.strip()}"
            )
        if on_progress is not None and last_fraction < 1.0:
            on_progress(1.0)

    @staticmethod
    def _parse_progress_line(line: str, duration: float) -> Optional[float]:
        """Return a 0.0–1.0 fraction from a ``-progress`` ``key=value`` line, else None."""
        line = line.strip()
        if duration <= 0:
            return None
        if line.startswith("out_time_us=") or line.startswith("out_time_ms="):
            # out_time_us is microseconds; out_time_ms is (historically) also microseconds.
            raw = line.split("=", 1)[1]
            if raw in ("N/A", ""):
                return None
            try:
                micros = int(raw)
            except ValueError:
                return None
            return micros / 1_000_000.0 / duration
        if line == "progress=end":
            return 1.0
        return None

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
