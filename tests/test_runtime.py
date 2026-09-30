"""Tests for FfmpegRuntime: discovery, version gate, execution, progress, capabilities."""

from __future__ import annotations

import shutil
import stat
import sys
import threading
from pathlib import Path

import pytest

from auto_reel_ng.errors import FfmpegError, FfmpegVersionError
from auto_reel_ng.ffmpeg.runtime import FfmpegRuntime, parse_ffmpeg_version

# -- 2.x discovery & version gate -------------------------------------------


def test_explicit_path_wins_over_path(runtime: FfmpegRuntime) -> None:
    """An explicitly configured ffmpeg path is used even though PATH also has one."""
    explicit = shutil.which("ffmpeg")
    assert explicit is not None
    built = FfmpegRuntime(ffmpeg_path=explicit)
    assert built.ffmpeg_path == str(Path(explicit))


def test_falls_back_to_path(runtime: FfmpegRuntime) -> None:
    """With no explicit config and no bundle present, both binaries resolve from PATH."""
    assert runtime.ffmpeg_path == shutil.which("ffmpeg")
    assert runtime.ffprobe_path == shutil.which("ffprobe")


def test_missing_binary_names_ffprobe() -> None:
    """A missing ffprobe fails loud and names ffprobe."""
    with pytest.raises(FfmpegError) as excinfo:
        FfmpegRuntime(ffprobe_path="/nonexistent/path/to/ffprobe")
    assert "ffprobe" in str(excinfo.value)


def test_accepts_71(runtime: FfmpegRuntime) -> None:
    """The real system ffmpeg (>= 7.1) is accepted and exposes its version."""
    assert runtime.version >= (7, 1)


def test_accepts_mocked_71(monkeypatch: pytest.MonkeyPatch) -> None:
    """A build reporting exactly 7.1 passes the gate."""
    monkeypatch.setattr(
        FfmpegRuntime,
        "_query_version_text",
        lambda self: "ffmpeg version 7.1 Copyright (c) 2000-2025",
    )
    built = FfmpegRuntime()
    assert built.version == (7, 1)


def test_rejects_old_version(monkeypatch: pytest.MonkeyPatch) -> None:
    """A build older than 7.1 raises, stating detected and required versions."""
    monkeypatch.setattr(
        FfmpegRuntime,
        "_query_version_text",
        lambda self: "ffmpeg version 6.0 Copyright (c) 2000-2023",
    )
    with pytest.raises(FfmpegVersionError) as excinfo:
        FfmpegRuntime()
    message = str(excinfo.value)
    assert "6.0" in message
    assert "7.1" in message


def test_rejects_unparseable_version(monkeypatch: pytest.MonkeyPatch) -> None:
    """An unparseable ``N-…`` git build raises rather than passing silently."""
    monkeypatch.setattr(
        FfmpegRuntime,
        "_query_version_text",
        lambda self: "ffmpeg version N-109130-gabcdef Copyright (c)",
    )
    with pytest.raises(FfmpegVersionError):
        FfmpegRuntime()


@pytest.mark.parametrize(
    "text,expected",
    [
        ("ffmpeg version 7.1.3 Copyright", (7, 1)),
        ("ffmpeg version 7.1 Copyright", (7, 1)),
        ("ffmpeg version 8.0-static https://", (8, 0)),
        ("ffmpeg version 7.1.1-1ubuntu1 Copyright", (7, 1)),
    ],
)
def test_parse_version(text: str, expected: tuple[int, int]) -> None:
    assert parse_ffmpeg_version(text) == expected


def test_parse_version_rejects_git_build() -> None:
    with pytest.raises(FfmpegVersionError):
        parse_ffmpeg_version("ffmpeg version N-109130-gabcdef")


# -- 3.x execution, progress, capability text -------------------------------


def test_failed_command_surfaces_details(runtime: FfmpegRuntime) -> None:
    """A non-zero ffprobe exit surfaces the exit code, command, and stderr."""
    with pytest.raises(FfmpegError) as excinfo:
        runtime.run_ffprobe(["/does/not/exist.mp4"])
    message = str(excinfo.value)
    assert "exited" in message
    assert "stderr" in message


def test_successful_command_returns_output(runtime: FfmpegRuntime) -> None:
    """A successful command returns its captured output."""
    result = runtime.run(["-hide_banner", "-version"])
    assert result.returncode == 0
    assert "ffmpeg version" in result.stdout


def test_progress_callback_is_monotonic(runtime: FfmpegRuntime, tmp_path: Path) -> None:
    """A real short lavfi encode invokes the callback with non-decreasing 0–1 fractions."""
    out = tmp_path / "encoded.mp4"
    fractions: list[float] = []
    runtime.run_with_progress(
        [
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=320x240:rate=30:duration=2",
            "-c:v",
            "libx264",
            str(out),
        ],
        duration=2.0,
        on_progress=fractions.append,
    )
    assert out.exists()
    assert fractions, "expected at least one progress update"
    assert all(0.0 <= f <= 1.0 for f in fractions)
    assert fractions == sorted(fractions)
    assert fractions[-1] == pytest.approx(1.0)


def test_progress_without_callback_still_runs(runtime: FfmpegRuntime, tmp_path: Path) -> None:
    """Absence of a callback does not change command behavior."""
    out = tmp_path / "encoded.mp4"
    runtime.run_with_progress(
        [
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=320x240:rate=30:duration=1",
            "-c:v",
            "libx264",
            str(out),
        ],
        duration=1.0,
    )
    assert out.exists()


def test_capability_accessors_return_text(runtime: FfmpegRuntime) -> None:
    """The raw capability accessors return non-empty text."""
    assert "Encoders:" in runtime.encoders() or runtime.encoders().strip()
    assert runtime.decoders().strip()
    assert runtime.filters().strip()
    assert runtime.hwaccels().strip()


def test_explicit_non_executable_path_fails(tmp_path: Path) -> None:
    """An explicit path that is not executable fails loud."""
    fake = tmp_path / "ffmpeg"
    fake.write_text("not a binary")
    fake.chmod(fake.stat().st_mode & ~stat.S_IXUSR)
    with pytest.raises(FfmpegError):
        FfmpegRuntime(ffmpeg_path=str(fake))


# -- stderr drain: no pipe deadlock ------------------------------------------

#: A stand-in ffmpeg: answers ``-version``, then acts by its last argument. One MB of
#: stderr is more than any pipe holds, so a runner that reads stderr only after
#: stdout's EOF deadlocks on it deterministically.
FAKE_FFMPEG = f"""#!{sys.executable}
import sys, time
args = sys.argv[1:]
if "-version" in args:
    print("ffmpeg version 8.1 fake")
    sys.exit(0)
mode = args[-1]
if mode == "flood":
    sys.stderr.write("x" * 1_000_000)
    sys.stderr.flush()
    print("out_time_us=500000", flush=True)
    print("progress=end", flush=True)
    sys.exit(0)
if mode == "flood-fail":
    sys.stderr.write("y" * 1_000_000 + "\\nboom\\n")
    sys.exit(3)
if mode == "slow":
    print("out_time_us=100000", flush=True)
    time.sleep(60)
"""


@pytest.fixture
def fake_runtime(tmp_path: Path) -> FfmpegRuntime:
    fake = tmp_path / "ffmpeg"
    fake.write_text(FAKE_FFMPEG, encoding="utf-8")
    fake.chmod(0o755)
    return FfmpegRuntime(ffmpeg_path=str(fake), ffprobe_path=str(fake))


def _within(seconds: float, call) -> list:  # type: ignore[no-untyped-def]
    """Run ``call`` on a thread; fail (rather than hang the suite) if it does not return."""
    outcome: list = []

    def target() -> None:
        try:
            outcome.append(("ok", call()))
        except BaseException as exc:  # pylint: disable=broad-except
            outcome.append(("raised", exc))

    worker = threading.Thread(target=target, daemon=True)
    worker.start()
    worker.join(seconds)
    assert not worker.is_alive(), f"run_with_progress did not return within {seconds}s"
    return outcome


def test_large_stderr_does_not_deadlock(fake_runtime: FfmpegRuntime) -> None:
    fractions: list[float] = []
    outcome = _within(
        20,
        lambda: fake_runtime.run_with_progress(
            ["flood"], duration=1.0, on_progress=fractions.append
        ),
    )
    assert outcome == [("ok", None)]
    assert fractions == [0.5, 1.0]


def test_failure_after_large_stderr_carries_its_tail(fake_runtime: FfmpegRuntime) -> None:
    outcome = _within(20, lambda: fake_runtime.run_with_progress(["flood-fail"], duration=1.0))
    kind, exc = outcome[0]
    assert kind == "raised" and isinstance(exc, FfmpegError)
    assert "exited 3" in str(exc)
    assert str(exc).rstrip().endswith("boom")


def test_failing_callback_kills_ffmpeg_and_propagates(fake_runtime: FfmpegRuntime) -> None:
    def explode(_fraction: float) -> None:
        raise RuntimeError("callback failed")

    outcome = _within(
        20, lambda: fake_runtime.run_with_progress(["slow"], duration=1.0, on_progress=explode)
    )
    kind, exc = outcome[0]
    assert kind == "raised" and isinstance(exc, RuntimeError)
