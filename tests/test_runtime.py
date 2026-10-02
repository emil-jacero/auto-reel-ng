"""Tests for FfmpegRuntime: discovery, version gate, execution, progress, capabilities."""

from __future__ import annotations

import os
import shutil
import signal
import stat
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from auto_reel_ng.errors import (
    FfmpegCancelledError,
    FfmpegError,
    FfmpegStalledError,
    FfmpegTimeoutError,
    FfmpegVersionError,
)
from auto_reel_ng.ffmpeg import runtime as runtime_module
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


# -- lossless decoding: a non-UTF-8 byte never raises -------------------------

#: A stand-in binary acting by its last argument. Written to a plain (non-f) string so
#: the byte escapes below reach the child verbatim. ``FAKE_PIDFILE`` receives the pid.
FAKE_BINARY = """
import os, sys, time
args = sys.argv[1:]
pidfile = os.environ.get("FAKE_PIDFILE")
if pidfile:
    with open(pidfile, "w") as handle:
        handle.write(str(os.getpid()))
if "-version" in args:
    sys.stdout.buffer.write(os.environb.get(b"FAKE_VERSION", b"ffmpeg version 8.1 fake") + b"\\n")
    sys.exit(0)
mode = args[-1]
if mode == "latin1-fail":
    sys.stderr.buffer.write(b"Error opening /lib/caf\\xe9.mp4\\nInvalid data\\n")
    sys.stderr.flush()
    sys.exit(1)
if mode == "latin1-ok":
    sys.stdout.buffer.write(b"caf\\xe9\\n")
    sys.stdout.flush()
    sys.exit(0)
if mode == "latin1-progress-fail":
    print("out_time_us=100000", flush=True)
    sys.stderr.buffer.write(b"Error opening /lib/caf\\xe9.mp4\\n")
    sys.stderr.flush()
    sys.exit(1)
if mode == "fail":
    sys.stderr.write("boom\\n")
    sys.exit(7)
if mode == "fast":
    time.sleep(0.1)
    print("done")
    sys.exit(0)
if mode == "one-second":
    time.sleep(1)
    print("done")
    sys.exit(0)
if mode == "sleep":
    time.sleep(60)
if mode == "log-then-sleep":
    sys.stderr.write("Error reading /lib/clip.mp4: Input/output error\\n")
    sys.stderr.flush()
    time.sleep(60)
if mode == "progress-then-sleep":
    print("out_time_us=100000", flush=True)
    time.sleep(60)
if mode == "repeat":
    while True:
        print("out_time_us=2000000", flush=True)
        print("progress=continue", flush=True)
        time.sleep(0.1)
if mode in ("steady", "steady-long"):
    for step in range(1, 16 if mode == "steady" else 26):
        print(f"out_time_us={step * 100000}", flush=True)
        print("progress=continue", flush=True)
        time.sleep(0.1)
    print("progress=end", flush=True)
    sys.exit(0)
if mode == "close-stdout-then-sleep":
    os.close(1)
    time.sleep(60)
"""


@pytest.fixture
def fake_binary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "fakebin"
    path.write_text(f"#!{sys.executable}\n{FAKE_BINARY}", encoding="utf-8")
    path.chmod(0o755)
    monkeypatch.setenv("FAKE_PIDFILE", str(tmp_path / "pid"))
    return path


@pytest.fixture
def bin_runtime(fake_binary: Path) -> FfmpegRuntime:
    return FfmpegRuntime(ffmpeg_path=str(fake_binary), ffprobe_path=str(fake_binary))


def _child_pid(tmp_path: Path) -> int:
    return int((tmp_path / "pid").read_text())


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def test_non_utf8_stderr_is_escaped_in_the_typed_error(bin_runtime: FfmpegRuntime) -> None:
    for call in (bin_runtime.run, bin_runtime.run_ffprobe):
        with pytest.raises(FfmpegError) as excinfo:
            call(["latin1-fail"])
        assert "exited 1" in str(excinfo.value)
        assert "caf\\xe9.mp4" in str(excinfo.value)
        assert "Invalid data" in str(excinfo.value)


def test_non_utf8_stdout_is_returned_escaped(bin_runtime: FfmpegRuntime) -> None:
    assert bin_runtime.run(["latin1-ok"]).stdout == "caf\\xe9\n"


def test_progress_run_with_non_utf8_stderr_keeps_it_and_kills_no_reader(
    bin_runtime: FfmpegRuntime, monkeypatch: pytest.MonkeyPatch
) -> None:
    thread_failures: list[object] = []
    monkeypatch.setattr(threading, "excepthook", thread_failures.append)
    with pytest.raises(FfmpegError) as excinfo:
        bin_runtime.run_with_progress(["latin1-progress-fail"], duration=1.0)
    assert "exited 1" in str(excinfo.value)
    assert str(excinfo.value).rstrip().endswith("Error opening /lib/caf\\xe9.mp4")
    assert not thread_failures


def test_version_reply_with_a_non_utf8_byte_still_parses(
    fake_binary: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_VERSION", "ffmpeg version 8.1 caf\udce9")  # the raw byte 0xE9
    built = FfmpegRuntime(ffmpeg_path=str(fake_binary), ffprobe_path=str(fake_binary))
    assert built.version == (8, 1)


def test_real_ffprobe_on_a_latin1_named_file_is_a_typed_error(
    runtime: FfmpegRuntime, tmp_path: Path
) -> None:
    clip = tmp_path / os.fsdecode(b"caf\xe9.mp4")
    clip.write_text("not a video")
    with pytest.raises(FfmpegError) as excinfo:
        runtime.run_ffprobe(["-v", "error", str(clip)])
    assert not isinstance(excinfo.value, UnicodeDecodeError)
    assert "caf\\xe9.mp4" in str(excinfo.value)


# -- the opt-in time bound ------------------------------------------------------


def test_with_timeout_is_a_view_that_leaves_the_original_unbounded(
    bin_runtime: FfmpegRuntime,
) -> None:
    bounded = bin_runtime.with_timeout(5.0)
    assert bounded is not bin_runtime
    assert bounded.timeout == 5.0
    assert bin_runtime.timeout is None
    assert bounded.ffmpeg_path == bin_runtime.ffmpeg_path
    assert bounded.ffprobe_path == bin_runtime.ffprobe_path
    assert bounded.version == bin_runtime.version


@pytest.mark.parametrize("seconds", [0, -1, float("nan"), float("inf")])
def test_with_timeout_rejects_a_non_positive_or_non_finite_bound(
    bin_runtime: FfmpegRuntime, seconds: float
) -> None:
    with pytest.raises(ValueError):
        bin_runtime.with_timeout(seconds)


@pytest.mark.parametrize("method", ["run", "run_ffprobe"])
def test_a_hung_command_is_killed_and_reported(
    bin_runtime: FfmpegRuntime, tmp_path: Path, method: str
) -> None:
    bounded = bin_runtime.with_timeout(0.5)
    started = time.monotonic()
    with pytest.raises(FfmpegTimeoutError) as excinfo:
        getattr(bounded, method)(["sleep"])
    assert time.monotonic() - started < 10
    assert isinstance(excinfo.value, FfmpegError)
    assert "timed out after 0.5s" in str(excinfo.value)
    assert "fakebin" in str(excinfo.value)
    assert not _alive(_child_pid(tmp_path))


def test_a_timeout_keeps_what_the_hung_command_logged(bin_runtime: FfmpegRuntime) -> None:
    with pytest.raises(FfmpegTimeoutError) as excinfo:
        bin_runtime.with_timeout(1.0).run(["log-then-sleep"])
    message = str(excinfo.value)
    assert "timed out after 1s" in message
    assert message.rstrip().endswith("Error reading /lib/clip.mp4: Input/output error")
    assert "\nstderr:\n" in message


def test_a_command_within_its_bound_is_unaffected(bin_runtime: FfmpegRuntime) -> None:
    result = bin_runtime.with_timeout(30).run(["fast"])
    assert result.returncode == 0 and result.stdout == "done\n"


def test_an_unbounded_runtime_waits_for_the_child(bin_runtime: FfmpegRuntime) -> None:
    started = time.monotonic()
    assert bin_runtime.run(["one-second"]).stdout == "done\n"
    assert time.monotonic() - started >= 1.0


def test_a_failure_under_a_bound_is_the_ordinary_error(bin_runtime: FfmpegRuntime) -> None:
    with pytest.raises(FfmpegError) as excinfo:
        bin_runtime.with_timeout(30).run(["fail"])
    assert type(excinfo.value) is FfmpegError
    assert "exited 7" in str(excinfo.value) and "boom" in str(excinfo.value)


def test_a_child_that_cannot_be_killed_does_not_hold_the_caller(
    bin_runtime: FfmpegRuntime, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(subprocess.Popen, "kill", lambda self: None)
    monkeypatch.setattr(runtime_module, "KILL_GRACE_SECONDS", 0.5)
    started = time.monotonic()
    try:
        with pytest.raises(FfmpegTimeoutError):
            bin_runtime.with_timeout(0.5).run(["sleep"])
        assert 1.0 <= time.monotonic() - started < 10
    finally:
        os.kill(_child_pid(tmp_path), signal.SIGKILL)


# -- stall watchdog, cancel poll, bounded kill --------------------------------


def _progress(runtime: FfmpegRuntime, mode: str, **kwargs):  # type: ignore[no-untyped-def]
    """``run_with_progress`` on the fake binary in ``mode``, bounded so a hang fails the test."""
    kwargs.setdefault("duration", 1.0)
    outcome = _within(30, lambda: runtime.run_with_progress([mode], **kwargs))
    return outcome[0]


@pytest.mark.parametrize("mode", ["progress-then-sleep", "sleep", "repeat"])
def test_a_run_whose_output_time_stops_advancing_is_killed_as_stalled(
    bin_runtime: FfmpegRuntime, tmp_path: Path, mode: str
) -> None:
    """One line then silence, no output at all, and an unchanged output time all stall."""
    fractions: list[float] = []
    started = time.monotonic()
    kind, exc = _progress(
        bin_runtime, mode, duration=10.0, on_progress=fractions.append, stall_timeout=0.5
    )
    assert time.monotonic() - started < 10
    assert kind == "raised" and isinstance(exc, FfmpegStalledError)
    assert isinstance(exc, FfmpegError)
    message = str(exc)
    assert "ffmpeg stalled: no progress for" in message and "(limit 0.5s)" in message
    assert "fakebin" in message and "-progress" in message
    assert fractions == {"sleep": [], "progress-then-sleep": [0.01], "repeat": [0.2]}[mode]
    assert not _alive(_child_pid(tmp_path))


def test_a_steady_encode_is_never_stalled(bin_runtime: FfmpegRuntime) -> None:
    """Output time advancing every 0.1 s for 3x the limit ends normally."""
    fractions: list[float] = []
    started = time.monotonic()
    outcome = _progress(
        bin_runtime, "steady", duration=1.5, on_progress=fractions.append, stall_timeout=0.5
    )
    assert outcome == ("ok", None)
    assert time.monotonic() - started >= 1.0
    assert fractions == sorted(fractions) and fractions[-1] == 1.0


def test_the_stall_clock_does_not_need_a_duration(bin_runtime: FfmpegRuntime) -> None:
    """A zero-duration request yields no fraction, yet an advancing output time is progress."""
    fractions: list[float] = []
    outcome = _progress(
        bin_runtime, "steady", duration=0, on_progress=fractions.append, stall_timeout=0.5
    )
    assert outcome == ("ok", None)
    assert fractions == [1.0]  # only the final completion callback


def test_a_failure_with_a_stall_limit_is_the_ordinary_error(bin_runtime: FfmpegRuntime) -> None:
    kind, exc = _progress(bin_runtime, "fail", stall_timeout=30)
    assert kind == "raised" and type(exc) is FfmpegError
    assert "exited 7" in str(exc) and "boom" in str(exc)


def test_a_cancel_check_that_turns_true_kills_the_run(
    bin_runtime: FfmpegRuntime, tmp_path: Path
) -> None:
    began = time.monotonic()
    started = time.monotonic()

    def check() -> bool:
        return time.monotonic() - began > 0.3

    kind, exc = _progress(bin_runtime, "progress-then-sleep", should_cancel=check)
    assert time.monotonic() - started < 3
    assert kind == "raised" and isinstance(exc, FfmpegCancelledError)
    assert not isinstance(exc, FfmpegStalledError) and "canceled" in str(exc)
    assert not _alive(_child_pid(tmp_path))


def test_a_cancel_check_is_polled_about_once_a_second(bin_runtime: FfmpegRuntime) -> None:
    calls: list[float] = []

    def check() -> bool:
        calls.append(time.monotonic())
        return False

    outcome = _progress(bin_runtime, "steady-long", duration=3.0, should_cancel=check)
    assert outcome == ("ok", None)
    assert 1 <= len(calls) <= 4


def test_a_raising_cancel_check_kills_the_run_and_propagates(
    bin_runtime: FfmpegRuntime, tmp_path: Path
) -> None:
    def check() -> bool:
        raise RuntimeError("database unreachable")

    kind, exc = _progress(bin_runtime, "sleep", should_cancel=check)
    assert kind == "raised" and isinstance(exc, RuntimeError)
    assert "database unreachable" in str(exc)
    assert not _alive(_child_pid(tmp_path))


def test_a_cancel_wins_over_a_simultaneous_stall(
    bin_runtime: FfmpegRuntime, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Both deadlines fall due on the same wake: the operator's request is the reported cause."""
    monkeypatch.setattr(runtime_module, "CANCEL_POLL_INTERVAL_S", 0.5)
    kind, exc = _progress(bin_runtime, "sleep", stall_timeout=0.5, should_cancel=lambda: True)
    assert kind == "raised" and isinstance(exc, FfmpegCancelledError)


class _StuckProcess:
    """A stand-in ``Popen`` that cannot be killed and never produces output."""

    pid = 424242

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        self.stdout = os.fdopen(os.pipe()[0], "r")
        self.stderr = os.fdopen(os.pipe()[0], "r")
        self.returncode = None

    def kill(self) -> None:
        """Ignore SIGKILL, as a process in uninterruptible sleep does."""

    def wait(self, timeout: float | None = None) -> int:
        raise subprocess.TimeoutExpired("stuck", timeout or 0)


def test_an_unkillable_process_is_abandoned_and_the_stall_still_raised(
    bin_runtime: FfmpegRuntime, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    # An Alembic ``fileConfig`` run by an earlier test disables every logger that already exists.
    monkeypatch.setattr(runtime_module.logger, "disabled", False)
    monkeypatch.setattr(subprocess, "Popen", _StuckProcess)
    monkeypatch.setattr(runtime_module, "KILL_GRACE_SECONDS", 0.2)
    started = time.monotonic()
    with caplog.at_level("ERROR", logger=runtime_module.logger.name):
        kind, exc = _progress(bin_runtime, "anything", stall_timeout=0.3)
    assert time.monotonic() - started < 10
    assert kind == "raised" and isinstance(exc, FfmpegStalledError)
    assert any("424242" in record.getMessage() for record in caplog.records)


def test_a_process_that_closes_its_output_but_never_exits_is_stalled(
    bin_runtime: FfmpegRuntime, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(runtime_module, "KILL_GRACE_SECONDS", 0.5)
    started = time.monotonic()
    kind, exc = _progress(bin_runtime, "close-stdout-then-sleep")
    assert time.monotonic() - started < 10
    assert kind == "raised" and isinstance(exc, FfmpegStalledError)
    assert "closed its progress output but did not exit" in str(exc)
    assert not _alive(_child_pid(tmp_path))
