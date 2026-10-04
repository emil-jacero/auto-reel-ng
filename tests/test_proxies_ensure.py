"""Tests for ``ensure_proxy`` / ``lookup_proxy``: the cache entry, the CPU retry, cancel, the sweep.

A fake runtime records the argument list of every ``run_with_progress`` and writes a canned
output to its last argument; ``probe_media`` is replaced in ``proxies.ensure``. Real encodes
are in ``test_proxies_ffmpeg.py``.
"""

from __future__ import annotations

import errno
import json
import logging
import os
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Callable, List, Optional, Sequence

import pytest
from test_proxies_command import make_meta, vaapi_profile
from test_proxies_facts import good_probe

from auto_reel_ng.accel.profiles import AccelProfile, CPUProfile
from auto_reel_ng.errors import (
    FfmpegCancelledError,
    FfmpegError,
    FfmpegStalledError,
    ProbeError,
    ProxyCacheError,
    ProxyError,
)
from auto_reel_ng.probe.metadata import ClipMetadata
from auto_reel_ng.proxies import (
    ProxyEntry,
    ProxySettings,
    ProxyStatus,
)
from auto_reel_ng.proxies import cache as cache_module
from auto_reel_ng.proxies import ensure as ensure_module
from auto_reel_ng.proxies import (
    ensure_proxy,
    lookup_proxy,
    proxy_key,
    read_proxy_state,
    sweep_stale_parts,
)

Behaviour = Callable[["FakeRuntime", List[str], Optional[Callable[[float], None]], Any], None]

HYBRID_FAILURE = (
    "Command exited 218: /usr/bin/ffmpeg -nostats -progress pipe:1 -hwaccel vaapi -i /lib/C.MP4\n"
    "stderr:\n[vaapi @ 0x5581] Failed setup for format vaapi: hwaccel initialisation returned error."
)


def write_output(runtime: "FakeRuntime", args: List[str], progress: Any, cancel: Any) -> None:
    """The default behaviour: write the output and report two progress points."""
    del runtime, cancel
    if progress is not None:
        progress(0.5)
    Path(args[-1]).write_bytes(b"proxy bytes")
    if progress is not None:
        progress(1.0)


def fail_with(error: BaseException, *, progress_before: float = 0.0) -> Behaviour:
    def behaviour(runtime: "FakeRuntime", args: List[str], progress: Any, cancel: Any) -> None:
        del runtime, args, cancel
        if progress is not None and progress_before:
            progress(progress_before)
        raise error

    return behaviour


@pytest.fixture(autouse=True)
def enabled_loggers(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the proxy loggers enabled: an Alembic ``fileConfig`` run by an earlier test disables
    every logger that already exists (``disable_existing_loggers``)."""
    for name in (
        "auto_reel_ng.proxies.ensure",
        "auto_reel_ng.proxies.cache",
        "auto_reel_ng.proxies.verify",
    ):
        monkeypatch.setattr(logging.getLogger(name), "disabled", False)


class FakeRuntime:
    """Stands in for :class:`FfmpegRuntime`: records encodes, answers ffprobe with canned JSON."""

    def __init__(self) -> None:
        self.runs: List[List[str]] = []
        self.kwargs: List[dict[str, Any]] = []
        self.behaviours: List[Behaviour] = []
        self.timeouts: List[float] = []
        self.source_probe: dict[str, Any] = {
            "streams": [{"r_frame_rate": "25/1", "avg_frame_rate": "25/1", "nb_frames": "624"}]
        }
        self.proxy_probes: List[dict[str, Any]] = []
        self.verify_calls = 0
        self._lock = threading.Lock()

    def with_timeout(self, seconds: float) -> "FakeRuntime":
        self.timeouts.append(seconds)
        return self

    def run_ffprobe(self, args: List[str]) -> subprocess.CompletedProcess[str]:
        if "-count_packets" in args:
            with self._lock:
                index = (
                    min(self.verify_calls, len(self.proxy_probes) - 1) if self.proxy_probes else -1
                )
                self.verify_calls += 1
            document = self.proxy_probes[index] if index >= 0 else good_probe()
        else:
            document = self.source_probe
        return subprocess.CompletedProcess(args, 0, json.dumps(document), "")

    def run_with_progress(self, args: List[str], **kwargs: Any) -> None:
        with self._lock:
            self.runs.append(list(args))
            self.kwargs.append(kwargs)
            behaviour = self.behaviours.pop(0) if self.behaviours else write_output
        behaviour(self, list(args), kwargs.get("on_progress"), kwargs.get("should_cancel"))


class Env:
    """One clip, one cache, one fake runtime, and the replaced probe."""

    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self.cache = tmp_path / "xdg" / "auto-reel" / "proxies"
        self.settings = ProxySettings(self.cache)
        self.clip = tmp_path / "lib" / "C0123.MP4"
        self.clip.parent.mkdir(parents=True)
        self.clip.write_bytes(b"source clip bytes")
        os.utime(self.clip, ns=(1_700_000_000_000_000_000,) * 2)
        self.runtime = FakeRuntime()
        self.meta: ClipMetadata = make_meta(path=self.clip)
        self.probe_error: Optional[Exception] = None
        self.probed: List[Path] = []
        monkeypatch.setattr(ensure_module, "probe_media", self._probe)
        monkeypatch.setattr(cache_module, "_swept", set())

    def _probe(self, path: Path, **kwargs: Any) -> ClipMetadata:
        del kwargs
        self.probed.append(Path(path))
        if self.probe_error is not None:
            raise self.probe_error
        return self.meta

    def ensure(
        self, profile: Optional[AccelProfile] = None, clip: Optional[Path] = None, **kwargs: Any
    ) -> ProxyEntry:
        return ensure_proxy(
            clip or self.clip,
            settings=self.settings,
            runtime=self.runtime,  # type: ignore[arg-type]
            profile=profile or CPUProfile(),
            render_node="/dev/dri/renderD128",
            **kwargs,
        )

    def builds(self) -> List[Path]:
        return sorted(self.cache.glob(".*.part")) if self.cache.exists() else []

    def entries(self) -> List[Path]:
        """The entry directories (a ``<key>.fail`` marker is a file, and hidden names are builds)."""
        return (
            sorted(p for p in self.cache.iterdir() if p.is_dir() and not p.name.startswith("."))
            if self.cache.exists()
            else []
        )

    def markers(self) -> List[Path]:
        return sorted(self.cache.glob("*.fail")) if self.cache.exists() else []


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Env:
    return Env(tmp_path, monkeypatch)


# --------------------------------------------------------------------------- #
# hit and miss
# --------------------------------------------------------------------------- #


def test_a_miss_publishes_the_entry_and_leaves_no_build_directory(env: Env) -> None:
    entry = env.ensure()

    assert entry.generated is True
    assert entry.key == proxy_key(env.clip)
    assert entry.directory == env.cache / entry.key
    assert entry.proxy_path.read_bytes() == b"proxy bytes"
    assert entry.facts_path.is_file()
    assert (entry.facts.width, entry.facts.height, entry.facts.frames) == (960, 540, 624)
    assert entry.facts.encode_path == "cpu"
    assert sorted(p.name for p in entry.directory.iterdir()) == ["facts.json", "proxy.mp4"]
    assert env.builds() == []
    assert len(env.runtime.runs) == 1


def test_a_hit_runs_neither_the_probe_nor_the_runtime(env: Env) -> None:
    env.ensure()
    env.probed.clear()
    env.runtime.runs.clear()
    env.runtime.verify_calls = 0

    for call in (
        lambda: env.ensure(),
        lambda: lookup_proxy(env.clip, settings=env.settings),
    ):
        entry = call()
        assert entry is not None and entry.generated is False and entry.facts.frames == 624

    assert env.probed == []
    assert env.runtime.runs == []
    assert env.runtime.verify_calls == 0


def test_a_miss_is_probed_and_bounded_and_the_encode_gets_the_stall_limit(env: Env) -> None:
    cancel = lambda: False  # noqa: E731
    env.ensure(should_cancel=cancel)

    assert env.probed == [env.clip.resolve()]
    assert env.runtime.timeouts == [60.0]
    assert env.runtime.kwargs[0]["stall_timeout"] == 600.0
    assert env.runtime.kwargs[0]["should_cancel"] is cancel
    assert env.runtime.kwargs[0]["duration"] == 24.96


def test_lookup_of_a_vanished_clip_or_an_unbuilt_one_is_none(env: Env) -> None:
    assert lookup_proxy(env.clip, settings=env.settings) is None
    assert lookup_proxy(env.clip.parent / "gone.mp4", settings=env.settings) is None


def test_lookup_treats_damaged_facts_as_absent(env: Env) -> None:
    entry = env.ensure()
    entry.facts_path.write_text("{", encoding="utf-8")
    assert lookup_proxy(env.clip, settings=env.settings) is None


def test_an_incomplete_entry_directory_is_replaced_by_a_complete_one(env: Env) -> None:
    stale = env.cache / proxy_key(env.clip)
    stale.mkdir(parents=True)
    (stale / "proxy.mp4").write_bytes(b"half")  # no facts.json

    assert lookup_proxy(env.clip, settings=env.settings) is None
    entry = env.ensure()

    assert entry.generated is True
    assert entry.proxy_path.read_bytes() == b"proxy bytes"
    assert entry.facts_path.is_file()


def test_an_empty_proxy_is_not_a_hit_and_is_rebuilt(env: Env) -> None:
    first = env.ensure()
    first.proxy_path.write_bytes(b"")  # a disk-full write or a cut-short copy

    assert lookup_proxy(env.clip, settings=env.settings) is None
    entry = env.ensure()

    assert entry.generated is True
    assert entry.proxy_path.read_bytes() == b"proxy bytes"
    assert read_proxy_state(env.clip, settings=env.settings).status is ProxyStatus.ABSENT
    assert env.builds() == []


def test_facts_the_read_model_refuses_are_not_a_hit_either(env: Env) -> None:
    first = env.ensure()
    document = json.loads(first.facts_path.read_text(encoding="utf-8"))
    document["width"] = 0
    first.facts_path.write_text(json.dumps(document), encoding="utf-8")

    assert lookup_proxy(env.clip, settings=env.settings) is None
    assert env.ensure().generated is True
    assert lookup_proxy(env.clip, settings=env.settings) is not None


def test_the_source_clip_is_only_read(env: Env) -> None:
    before = (env.clip.read_bytes(), env.clip.stat().st_mtime_ns, env.clip.stat().st_size)
    env.ensure()
    assert (env.clip.read_bytes(), env.clip.stat().st_mtime_ns, env.clip.stat().st_size) == before


def test_the_hybrid_command_is_built_for_a_hardware_profile(env: Env) -> None:
    env.ensure(profile=vaapi_profile())
    assert "-hwaccel" in env.runtime.runs[0]
    assert env.ensure().facts.encode_path == "hybrid"


# --------------------------------------------------------------------------- #
# clips that cannot give a proxy
# --------------------------------------------------------------------------- #


def test_a_vanished_clip_is_a_proxy_error_and_nothing_runs(env: Env) -> None:
    with pytest.raises(ProxyError, match="cannot stat the clip: No such file"):
        env.ensure(clip=env.clip.parent / "gone.mp4")
    assert env.runtime.runs == [] and env.probed == []


@pytest.mark.parametrize("duration", [0.0, -1.0, float("nan")])
def test_a_clip_with_no_positive_duration_is_a_proxy_error_and_no_encode_starts(
    env: Env, duration: float
) -> None:
    env.meta = make_meta(path=env.clip, duration=duration)
    with pytest.raises(ProxyError, match="no usable duration"):
        env.ensure()
    assert env.runtime.runs == []
    assert env.entries() == [] and env.builds() == []


def test_a_probe_error_becomes_a_proxy_error_naming_the_clip(env: Env) -> None:
    env.probe_error = ProbeError(f"File is empty (zero bytes): {env.clip.resolve()}")
    with pytest.raises(ProxyError) as error:
        env.ensure()
    assert error.value.clip == str(env.clip)
    assert error.value.reason == "File is empty (zero bytes)"
    assert env.runtime.runs == []


def test_an_unusable_pixel_ratio_is_a_proxy_error(env: Env) -> None:
    env.meta = make_meta(path=env.clip, sample_aspect_ratio="1:0")
    with pytest.raises(ProxyError, match="cannot plan the proxy size"):
        env.ensure()
    assert env.runtime.runs == []


# --------------------------------------------------------------------------- #
# the CPU retry
# --------------------------------------------------------------------------- #


def test_a_hybrid_failure_is_redone_on_the_cpu_and_the_facts_say_so(
    env: Env, caplog: pytest.LogCaptureFixture
) -> None:
    env.runtime.behaviours = [fail_with(FfmpegError(HYBRID_FAILURE))]

    entry = env.ensure(profile=vaapi_profile())

    assert len(env.runtime.runs) == 2
    assert "-hwaccel" in env.runtime.runs[0]
    assert "-hwaccel" not in env.runtime.runs[1]
    assert entry.facts.encode_path == "cpu"
    assert entry.facts.fallback_reason is not None
    assert "Failed setup for format vaapi" in entry.facts.fallback_reason
    assert "\n" not in entry.facts.fallback_reason and "/usr/bin" not in entry.facts.fallback_reason
    assert "Failed setup for format vaapi" in caplog.text
    assert env.builds() == []


def test_the_proxy_video_is_checked_against_the_source_video_not_the_container(env: Env) -> None:
    # audio outruns the video: the container (the probe's duration) is 25.2 s, the video 24.96 s
    env.meta = make_meta(path=env.clip, duration=25.2)
    env.runtime.source_probe["streams"][0]["duration"] = "24.960000"

    entry = env.ensure()

    assert entry.facts.encode_path == "cpu" and len(env.runtime.runs) == 1
    assert entry.facts.duration == 25.2  # the facts keep the probed container duration


def test_without_a_video_stream_duration_the_container_duration_is_the_expectation(
    env: Env,
) -> None:
    env.meta = make_meta(path=env.clip, duration=25.2)  # no stream duration in the source probe

    with pytest.raises(ProxyError, match=r"video duration check: found 24.960s, expected 25.200s"):
        env.ensure()


def test_a_hybrid_output_of_the_wrong_size_is_discarded_and_redone_on_the_cpu(env: Env) -> None:
    env.runtime.proxy_probes = [good_probe(width=540, height=960), good_probe()]

    entry = env.ensure(profile=vaapi_profile())

    assert len(env.runtime.runs) == 2
    assert entry.facts.encode_path == "cpu"
    assert "dimensions check: found 540x960, expected 960x540" in (
        entry.facts.fallback_reason or ""
    )
    assert entry.proxy_path.is_file()


def test_when_the_cpu_output_fails_too_the_clip_fails_and_nothing_remains(env: Env) -> None:
    env.runtime.proxy_probes = [good_probe(width=540, height=960)]

    with pytest.raises(
        ProxyError, match=r"dimensions check: found 540x960, expected 960x540 \(cpu path\)"
    ):
        env.ensure(profile=vaapi_profile())

    assert len(env.runtime.runs) == 2  # hybrid, then the one CPU retry
    assert env.entries() == [] and env.builds() == []


def test_a_cpu_failure_is_not_retried(env: Env) -> None:
    env.runtime.behaviours = [
        fail_with(FfmpegError("Command exited 1: ffmpeg\nstderr:\nbad input"))
    ]

    with pytest.raises(ProxyError, match="ffmpeg failed on the cpu path"):
        env.ensure(profile=CPUProfile())

    assert len(env.runtime.runs) == 1
    assert env.entries() == [] and env.builds() == []


def test_a_stall_is_not_retried(env: Env) -> None:
    env.runtime.behaviours = [fail_with(FfmpegStalledError("ffmpeg stalled: no progress for 600s"))]

    with pytest.raises(ProxyError, match="stalled"):
        env.ensure(profile=vaapi_profile())

    assert len(env.runtime.runs) == 1
    assert env.entries() == [] and env.builds() == []


def test_an_encode_that_wrote_nothing_is_a_failure(env: Env) -> None:
    env.runtime.behaviours = [lambda *_: None]
    with pytest.raises(ProxyError, match="wrote no proxy"):
        env.ensure()
    assert env.entries() == []


# --------------------------------------------------------------------------- #
# cancel, interrupt, progress
# --------------------------------------------------------------------------- #


def test_a_cancel_propagates_and_leaves_nothing(env: Env) -> None:
    def cancelled(runtime: FakeRuntime, args: List[str], progress: Any, cancel: Any) -> None:
        del runtime, progress
        Path(args[-1]).write_bytes(b"partial")
        assert cancel() is True
        raise FfmpegCancelledError("ffmpeg canceled")

    env.runtime.behaviours = [cancelled]

    with pytest.raises(FfmpegCancelledError):
        env.ensure(should_cancel=lambda: True)

    assert env.builds() == [] and env.entries() == []
    assert not (env.cache / proxy_key(env.clip)).exists()


def test_a_keyboard_interrupt_propagates_and_leaves_nothing(env: Env) -> None:
    env.runtime.behaviours = [fail_with(KeyboardInterrupt())]
    with pytest.raises(KeyboardInterrupt):
        env.ensure()
    assert env.builds() == [] and env.entries() == []


def test_progress_never_goes_back_after_a_retry_and_ends_at_one(env: Env) -> None:
    reported: List[float] = []
    env.runtime.behaviours = [fail_with(FfmpegError(HYBRID_FAILURE), progress_before=0.8)]

    env.ensure(profile=vaapi_profile(), on_progress=reported.append)

    assert reported[0] == 0.8
    assert all(b >= a for a, b in zip(reported, reported[1:]))
    assert min(reported) >= 0.8
    assert reported[-1] == 1.0


def test_a_hybrid_exit_zero_that_fails_verification_does_not_pin_progress_at_one(env: Env) -> None:
    reported: List[float] = []
    env.runtime.proxy_probes = [good_probe(width=540, height=960), good_probe()]

    def cpu_retry(runtime: FakeRuntime, args: List[str], progress: Any, cancel: Any) -> None:
        for fraction in (0.25, 0.5, 0.75, 1.0):
            progress(fraction)
        write_output(runtime, args, None, cancel)

    env.runtime.behaviours = [write_output, cpu_retry]  # the hybrid ends on 1.0, then fails

    entry = env.ensure(profile=vaapi_profile(), on_progress=reported.append)

    assert entry.facts.encode_path == "cpu"
    assert all(b > a for a, b in zip(reported, reported[1:]))
    assert reported[-1] == 1.0
    hybrid_end = max(f for f in reported if f <= ensure_module._MonotonicProgress.ATTEMPT_CEILING)
    assert hybrid_end < 1.0  # ffmpeg's 1.0 is not "published"
    # the retry kept moving, in steps, before the proxy was published
    assert len([f for f in reported if hybrid_end < f < 1.0]) >= 3


def test_progress_ends_at_one_even_when_the_encode_reported_less(env: Env) -> None:
    reported: List[float] = []
    env.runtime.behaviours = [
        lambda r, args, progress, cancel: (progress(0.4), Path(args[-1]).write_bytes(b"x"))
    ]
    env.ensure(on_progress=reported.append)
    assert reported == [0.4, 1.0]


# --------------------------------------------------------------------------- #
# two builds of one clip
# --------------------------------------------------------------------------- #


def test_two_threads_building_one_clip_get_the_same_entry_and_no_part_remains(env: Env) -> None:
    barrier = threading.Barrier(2, timeout=10)

    def meet(runtime: FakeRuntime, args: List[str], progress: Any, cancel: Any) -> None:
        Path(args[-1]).write_bytes(b"proxy bytes")
        barrier.wait()  # both encodes are finished before either publishes

    env.runtime.behaviours = [meet, meet]
    results: List[ProxyEntry] = []
    errors: List[BaseException] = []

    def work() -> None:
        try:
            results.append(env.ensure())
        except BaseException as exc:  # pylint: disable=broad-exception-caught
            errors.append(exc)

    threads = [threading.Thread(target=work) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=20)

    assert errors == []
    assert len(results) == 2
    assert results[0].directory == results[1].directory
    assert sorted(r.generated for r in results) == [False, True]  # one build was discarded
    assert len(env.runtime.runs) == 2
    assert env.builds() == []
    assert len(env.entries()) == 1


def test_losing_the_rename_to_another_process_returns_the_winner(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_rename = os.rename

    def lose(src: Any, dst: Any) -> None:
        if str(src).endswith(".part"):
            shutil.copytree(src, dst)  # the other process won
            raise FileExistsError(errno.EEXIST, "File exists", str(dst))
        real_rename(src, dst)

    monkeypatch.setattr(cache_module.os, "rename", lose)

    entry = env.ensure()

    assert entry.generated is False
    assert entry.proxy_path.read_bytes() == b"proxy bytes"
    assert env.builds() == []
    assert len(env.entries()) == 1


def test_a_complete_entry_that_appears_after_the_first_look_is_not_removed(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    winner = env.ensure()
    original = winner.proxy_path.read_bytes()
    part = cache_module.new_part_dir(env.cache, winner.key)
    shutil.copy(winner.proxy_path, part / "proxy.mp4")
    shutil.copy(winner.facts_path, part / "facts.json")
    (part / "proxy.mp4").write_bytes(b"the slower build")
    real_read = cache_module.read_entry
    looks: List[int] = []

    def late(directory: Path) -> Any:
        looks.append(1)
        # the first look happens before the other process's rename: it sees nothing
        return None if len(looks) == 1 else real_read(directory)

    monkeypatch.setattr(cache_module, "read_entry", late)

    entry = cache_module.publish(part, winner.directory)

    assert entry.generated is False
    assert entry.proxy_path.read_bytes() == original
    assert not part.exists()
    assert len(looks) >= 2


def test_a_rename_error_that_is_not_a_lost_race_is_a_cache_error(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(src: Any, dst: Any) -> None:
        raise PermissionError(errno.EACCES, "Permission denied", str(dst))

    monkeypatch.setattr(cache_module.os, "rename", broken)
    with pytest.raises(ProxyCacheError, match="cannot write proxies"):
        env.ensure()
    assert env.builds() == [] and env.entries() == []


# --------------------------------------------------------------------------- #
# the cache directory's own faults
# --------------------------------------------------------------------------- #


def test_a_cache_under_a_regular_file_is_a_cache_error_not_a_proxy_error(
    env: Env, tmp_path: Path
) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_bytes(b"i am a file")
    env.settings = ProxySettings(blocker / "proxies")

    with pytest.raises(ProxyCacheError) as error:
        env.ensure()

    assert not isinstance(error.value, ProxyError)
    assert str(blocker / "proxies") in str(error.value)
    assert env.runtime.runs == []


def test_a_full_cache_disk_is_a_cache_error_and_leaves_nothing(env: Env) -> None:
    env.runtime.behaviours = [
        fail_with(
            FfmpegError(
                "Command exited 234: ffmpeg -i x\nstderr:\n"
                "[out#0/mp4 @ 0x1] Error writing trailer: No space left on device"
            )
        )
    ]
    with pytest.raises(ProxyCacheError, match="No space left on device") as error:
        env.ensure(profile=vaapi_profile())
    assert not isinstance(error.value, ProxyError)
    assert str(env.cache) in str(error.value)
    assert len(env.runtime.runs) == 1  # a full disk is not retried on the CPU
    assert env.builds() == [] and env.entries() == []


def test_a_clip_whose_name_says_no_space_left_is_not_a_full_disk(env: Env) -> None:
    command_with_name = "Command exited 1: ffmpeg -i /lib/No space left on device.mp4\nstderr:\nbad"
    env.runtime.behaviours = [fail_with(FfmpegError(command_with_name))]
    with pytest.raises(ProxyError):
        env.ensure()


# --------------------------------------------------------------------------- #
# the sweep
# --------------------------------------------------------------------------- #


def _part(cache: Path, age_seconds: float, key: str = "a" * 64) -> Path:
    path = cache / f".{key}.{os.urandom(16).hex()}.part"
    path.mkdir(parents=True)
    (path / "proxy.mp4").write_bytes(b"x")
    stamp = time.time() - age_seconds
    os.utime(path, (stamp, stamp))
    return path


def test_a_build_directory_two_days_old_is_swept_and_a_young_one_kept(env: Env) -> None:
    old = _part(env.cache, 2 * 24 * 3600)
    young = _part(env.cache, 60)

    env.ensure()

    assert not old.exists()
    assert young.exists()


def test_the_sweep_leaves_entries_and_foreign_names_alone(env: Env) -> None:
    env.cache.mkdir(parents=True)
    entry = env.cache / ("b" * 64)
    entry.mkdir()
    foreign = env.cache / ".notes.part"
    foreign.mkdir()
    for path in (entry, foreign):
        os.utime(path, (1, 1))
    link_target = env.cache.parent / "elsewhere"
    link_target.mkdir()
    link = env.cache / f".{'c' * 64}.{'d' * 32}.part"
    link.symlink_to(link_target)
    os.utime(link_target, (1, 1))

    assert sweep_stale_parts(env.cache) == 0
    assert entry.exists() and foreign.exists() and link_target.exists()


def test_a_removal_that_fails_is_logged_and_does_not_fail_the_request(
    env: Env, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    old = _part(env.cache, 2 * 24 * 3600)
    real_rmtree = shutil.rmtree

    def refuse(path: Any, *args: Any, **kwargs: Any) -> None:
        if Path(path) == old:
            raise PermissionError(errno.EACCES, "Permission denied", str(path))
        real_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(cache_module.shutil, "rmtree", refuse)

    entry = env.ensure()

    assert entry.generated is True
    assert old.exists()
    assert "Cannot sweep" in caplog.text


def test_a_second_build_in_the_same_process_does_not_sweep_again(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    sweeps: List[Path] = []
    real = cache_module.sweep_stale_parts
    monkeypatch.setattr(
        cache_module,
        "sweep_stale_parts",
        lambda cache_dir, **kw: (sweeps.append(cache_dir), real(cache_dir, **kw))[1],
    )
    other = env.clip.parent / "C0124.MP4"
    other.write_bytes(b"another clip")

    env.ensure()
    env.ensure(clip=other)

    assert len(sweeps) == 1


def test_a_hit_never_sweeps(env: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    env.ensure()
    monkeypatch.setattr(cache_module, "_swept", set())
    old = _part(env.cache, 2 * 24 * 3600)
    env.ensure()
    assert old.exists()


# --------------------------------------------------------------------------- #
# keys: what re-uses an entry and what does not
# --------------------------------------------------------------------------- #


def test_a_changed_clip_gets_a_new_entry_and_the_old_one_stays(env: Env) -> None:
    first = env.ensure()
    os.utime(env.clip, ns=(1_700_000_000_000_000_000, 1_700_000_000_000_000_999))

    second = env.ensure()

    assert second.generated is True and second.key != first.key
    assert first.directory.is_dir() and second.directory.is_dir()
    assert len(env.runtime.runs) == 2


def test_a_proxy_made_under_an_earlier_version_is_not_read(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    from auto_reel_ng.proxies import spec

    old = env.ensure()
    monkeypatch.setattr(spec, "PROXY_VERSION", spec.PROXY_VERSION + 1)

    assert lookup_proxy(env.clip, settings=env.settings) is None
    new = env.ensure()

    assert new.generated is True and new.key != old.key
    assert old.directory.is_dir()  # left in the cache, unread
    assert len(env.runtime.runs) == 2


def test_two_links_to_one_clip_share_one_entry_and_one_encode(env: Env, tmp_path: Path) -> None:
    other_event = tmp_path / "lib" / "other"
    other_event.mkdir()
    link_a, link_b = tmp_path / "lib" / "a.mp4", other_event / "b.mp4"
    link_a.symlink_to(env.clip)
    link_b.symlink_to(env.clip)

    first = env.ensure(clip=link_a)
    second = env.ensure(clip=link_b)

    assert first.directory == second.directory
    assert second.generated is False
    assert len(env.runtime.runs) == 1


def test_a_copied_library_keeps_its_proxies(env: Env, tmp_path: Path) -> None:
    first = env.ensure()
    moved = tmp_path / "mnt" / "other-host" / "lib"
    moved.mkdir(parents=True)
    copy = moved / env.clip.name
    shutil.copy2(env.clip, copy)  # like ``cp -a``: size and mtime_ns survive

    again = lookup_proxy(copy, settings=env.settings)

    assert again is not None and again.directory == first.directory
    env.probed.clear()
    assert env.ensure(clip=copy).generated is False
    assert env.probed == [] and len(env.runtime.runs) == 1


def test_an_editorial_edit_never_invalidates_a_proxy(env: Env) -> None:
    """The reel.yaml is not an input: a ``rotate`` set (or changed) beside the clip changes nothing."""
    reel = env.clip.parent / "reel.yaml"
    first = env.ensure()
    reel.write_text("version: 0\nchapters:\n  - name: ''\n    clips:\n      - C0123.MP4\n", "utf-8")
    second = env.ensure()
    reel.write_text(
        "version: 0\nchapters:\n  - name: ''\n    clips:\n      - clip: C0123.MP4\n        rotate: 90\n",
        "utf-8",
    )
    third = env.ensure()

    assert first.directory == second.directory == third.directory
    assert [e.generated for e in (second, third)] == [False, False]
    assert len(env.runtime.runs) == 1
    assert not any(applies_rotation(run) for run in env.runtime.runs)


def applies_rotation(run: Sequence[str]) -> bool:
    """True when an ffmpeg command rotates: the flag, or a transpose/rotate filter in a graph.

    Only filter-graph tokens count, never a path: a clip or cache directory may be named anything.
    """
    graph_flags = ("-vf", "-af", "-lavfi", "-filter_complex", "-filter_complex_script")
    graphs = [run[i + 1] for i, arg in enumerate(run[:-1]) if arg in graph_flags]
    return "-noautorotate" in run or any(
        re.search(r"(?:^|[,;\]\s])(?:transpose|rotate)=", graph) for graph in graphs
    )


@pytest.mark.parametrize(
    "run",
    [
        ["ffmpeg", "-vf", "transpose=1,scale=-2:540"],
        ["ffmpeg", "-vf", "scale=-2:540,rotate=PI/2"],
        ["ffmpeg", "-filter_complex", "[0:v]scale=1:1[a];[a]transpose=2[v]"],
        ["ffmpeg", "-noautorotate", "-i", "in.mp4"],
    ],
)
def test_the_rotation_matcher_sees_rotation_graphs(run: List[str]) -> None:
    assert applies_rotation(run)


def test_the_rotation_matcher_ignores_paths_named_rotate() -> None:
    run = ["ffmpeg", "-i", "/tmp/rotate-me/C0123.MP4", "-vf", "scale=-2:540", "/c/rotate/proxy.mp4"]
    assert not applies_rotation(run)


def test_an_editorial_edit_never_invalidates_a_proxy_under_a_rotate_path(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The path of the library and cache contains ``rotate``: the original test's check still holds."""
    root = tmp_path_factory.mktemp("rotate-")
    assert "rotate" in str(root)
    env = Env(root, monkeypatch)
    first = env.ensure()
    (env.clip.parent / "reel.yaml").write_text("version: 0\nchapters: []\n", "utf-8")
    assert env.ensure().directory == first.directory
    assert len(env.runtime.runs) == 1
    assert any("rotate" in " ".join(run) for run in env.runtime.runs)  # the path is in the argv
    assert not any(applies_rotation(run) for run in env.runtime.runs)


def test_a_read_only_cache_directory_is_a_cache_error(env: Env, tmp_path: Path) -> None:
    parent = tmp_path / "ro"
    parent.mkdir()
    env.settings = ProxySettings(parent / "proxies")
    parent.chmod(0o500)
    try:
        if os.access(parent, os.W_OK):
            pytest.skip("directory permissions are not enforced (running as root?)")
        with pytest.raises(ProxyCacheError, match=str(parent / "proxies")):
            env.ensure()
    finally:
        parent.chmod(0o700)
    assert env.runtime.runs == []
