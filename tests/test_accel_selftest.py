"""Self-test classification + the real-host AMD assertions (exp 002-004 findings)."""

from __future__ import annotations

import subprocess
from types import SimpleNamespace

import pytest

from auto_reel_ng.accel import detect_capabilities
from auto_reel_ng.accel import selftest as st
from auto_reel_ng.accel.models import OpClass, OpStatus, Vendor
from auto_reel_ng.accel.selftest import Probe, run_probe, run_selftest
from auto_reel_ng.ffmpeg.runtime import FfmpegRuntime


def _probe(key: str, *args: str) -> Probe:
    return Probe(key=key, vendor=Vendor.CPU, op=OpClass.ENCODE, args=args)


def test_working_probe_is_classified_working(runtime: FfmpegRuntime) -> None:
    """A clean trivial op (exit 0) is classified WORKING."""
    probe = _probe(
        "ok",
        "-f",
        "lavfi",
        "-i",
        "testsrc2=size=64x48:rate=1",
        "-frames:v",
        "1",
        "-f",
        "null",
        "-",
    )
    assert run_probe(runtime, probe) is OpStatus.WORKING


def test_rejected_probe_is_classified_unsupported(runtime: FfmpegRuntime) -> None:
    """A clean non-zero exit (bogus filter) is classified UNSUPPORTED, not faulting."""
    probe = _probe(
        "bad",
        "-f",
        "lavfi",
        "-i",
        "testsrc2=size=64x48:rate=1",
        "-frames:v",
        "1",
        "-vf",
        "definitely_not_a_real_filter",
        "-f",
        "null",
        "-",
    )
    assert run_probe(runtime, probe) is OpStatus.UNSUPPORTED


def test_hanging_probe_is_classified_faulting(runtime: FfmpegRuntime) -> None:
    """A probe that exceeds its timeout (a hang) is contained and classified FAULTING."""
    probe = _probe(
        "hang",
        "-re",
        "-f",
        "lavfi",
        "-i",
        "testsrc2=size=64x48:rate=30:duration=30",
        "-f",
        "null",
        "-",
    )
    assert run_probe(runtime, probe, timeout=1.0) is OpStatus.FAULTING


def test_signal_killed_probe_is_classified_faulting(monkeypatch: pytest.MonkeyPatch) -> None:
    """A probe killed by a signal (a GPU page-fault, exp 004) is classified FAULTING.

    A real GPU fault is unsafe/non-deterministic to induce, so the signal exit is
    simulated: ffmpeg terminated by SIGABRT reports a negative return code.
    """

    def fake_run(cmd: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=cmd, returncode=-6, stdout="", stderr="")

    monkeypatch.setattr(st.subprocess, "run", fake_run)
    probe = _probe("crash", "-f", "lavfi", "-i", "testsrc2=size=64x48:rate=1", "-f", "null", "-")
    runtime = SimpleNamespace(ffmpeg_path="ffmpeg")
    assert run_probe(runtime, probe) is OpStatus.FAULTING  # type: ignore[arg-type]


def test_deliberately_bad_op_does_not_crash_selftest(runtime: FfmpegRuntime) -> None:
    """An injected bad op is classified without taking down the rest of the self-test."""
    bad = _probe(
        "cpu.badop",
        "-f",
        "lavfi",
        "-i",
        "testsrc2=size=64x48:rate=1",
        "-frames:v",
        "1",
        "-vf",
        "definitely_not_a_real_filter",
        "-f",
        "null",
        "-",
    )
    # No devices -> no hardware probes; only the injected bad op runs.
    results = run_selftest(
        runtime, devices=(), encoders=frozenset(), filters=frozenset(), extra_probes=[bad]
    )
    assert results == {"cpu.badop": OpStatus.UNSUPPORTED}


def test_amd_host_reports_verified_capabilities() -> None:
    """On the real AMD VAAPI dev host, the self-test reproduces the spike findings.

    Skipped on any host without an AMD render node (e.g. CI), so the suite stays portable.
    """
    inventory = detect_capabilities(force_refresh=True)
    amd = inventory.accelerator(Vendor.AMD)
    if amd is None:
        pytest.skip("no AMD VAAPI device on this host")

    assert amd.pad_filter == "pad_vaapi"
    assert amd.can_overlay_hw is False
    assert amd.can_tonemap_hw is False
    # All three hardware encoders work on this card. hevc_vaapi in particular requires
    # width >= 384, so the self-test must probe above that floor (see _PROBE_SIZE);
    # a smaller probe used to exclude HEVC even though the card supports it.
    assert amd.usable_encoders == {
        "h264": "h264_vaapi",
        "hevc": "hevc_vaapi",
        "av1": "av1_vaapi",
    }
    assert amd.decode_method == "vaapi"
