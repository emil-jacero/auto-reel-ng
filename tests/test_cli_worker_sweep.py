"""``auto-reel worker`` starts the automatic analysis sweep beside its claim loop
(analysis-auto-sweep 2.4): only while ``worker.auto_analyze`` is on, with the configured
interval and cap, sharing the worker's stop event, and joined when the loop returns.

Everything heavier than the wiring (capability detection, the database, the loop) is patched.
"""

from __future__ import annotations

import argparse
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import pytest

from auto_reel_ng.cli import commands
from auto_reel_ng.config.project import ConfigError
from auto_reel_ng.scheduler.analysis_sweep import AnalysisSweep


class FakeWorker:
    """Stands in for :class:`Worker`; ``run`` returns at once, as after a stop."""

    instances: List["FakeWorker"] = []

    def __init__(self, store: object, **kwargs: Any) -> None:
        del store
        self.stop_event: threading.Event = kwargs["stop_event"]
        self.ran = False
        self.sweep_alive_during_run: Optional[bool] = None
        FakeWorker.instances.append(self)

    def run(self) -> None:
        self.ran = True
        self.sweep_alive_during_run = any(
            t.name == "analysis-sweep" and t.is_alive() for t in threading.enumerate()
        )

    def stop(self) -> None:
        self.stop_event.set()


@pytest.fixture
def started(monkeypatch: pytest.MonkeyPatch) -> Dict[str, Any]:
    """Patch the worker's heavy collaborators; record what the sweep was started with."""
    record: Dict[str, Any] = {}
    FakeWorker.instances = []
    monkeypatch.setattr(commands, "Worker", FakeWorker)
    monkeypatch.setattr(commands, "FfmpegRuntime", lambda: object())
    monkeypatch.setattr(commands, "detect_capabilities", lambda runtime: object())
    profile = SimpleNamespace(vendor=SimpleNamespace(value="cpu"))
    monkeypatch.setattr(commands, "select_profile", lambda inventory, override=None: profile)
    monkeypatch.setattr(commands, "_selected_render_node", lambda profile: None)
    monkeypatch.setattr(
        commands.CapacityPools, "from_inventory", classmethod(lambda cls, *a, **k: object())
    )
    monkeypatch.setattr(commands, "_job_store", lambda root: "the-store")
    monkeypatch.setattr(commands, "ProxyJobHandler", lambda **kwargs: object())
    monkeypatch.setattr(commands, "AnalysisJobHandler", lambda **kwargs: object())
    monkeypatch.setattr(commands.signal, "signal", lambda *args: None)

    def fake_run(self: AnalysisSweep, stop_event: threading.Event, interval: float) -> None:
        record.update(
            sweep=self, stop_event=stop_event, interval=interval, max_events=self._max_events
        )
        stop_event.wait(5)  # like the real loop: until the worker stops

    monkeypatch.setattr(AnalysisSweep, "run", fake_run)
    return record


def _args(root: Path) -> argparse.Namespace:
    return argparse.Namespace(
        root=str(root),
        device=None,
        poll_interval=None,
        gpu_sessions_per_device=None,
        cpu_slots=None,
    )


def test_the_worker_starts_the_sweep_with_its_config_and_stop_event(
    tmp_path: Path, started: Dict[str, Any]
) -> None:
    (tmp_path / "config.yaml").write_text(
        "worker:\n  auto_analyze_interval: 20\n  auto_analyze_max_events: 3\n", encoding="utf-8"
    )
    assert commands.cmd_worker(_args(tmp_path)) == 0
    (worker,) = FakeWorker.instances
    assert worker.ran and worker.sweep_alive_during_run
    assert started["interval"] == 20.0 and started["max_events"] == 3
    assert started["stop_event"] is worker.stop_event and worker.stop_event.is_set()
    assert not any(t.name == "analysis-sweep" for t in threading.enumerate())  # joined


def test_the_sweep_is_on_by_default(tmp_path: Path, started: Dict[str, Any]) -> None:
    assert commands.cmd_worker(_args(tmp_path)) == 0
    assert started["interval"] == 300.0 and started["max_events"] == 2


def test_auto_analyze_off_starts_no_sweep(tmp_path: Path, started: Dict[str, Any]) -> None:
    (tmp_path / "config.yaml").write_text("worker:\n  auto_analyze: false\n", encoding="utf-8")
    assert commands.cmd_worker(_args(tmp_path)) == 0
    (worker,) = FakeWorker.instances
    assert worker.ran and worker.sweep_alive_during_run is False
    assert not started


def test_a_bad_value_stops_the_worker_before_it_starts(
    tmp_path: Path, started: Dict[str, Any]
) -> None:
    (tmp_path / "config.yaml").write_text("worker:\n  auto_analyze: yes-please\n", encoding="utf-8")
    with pytest.raises(ConfigError, match=r"worker\.auto_analyze"):
        commands.cmd_worker(_args(tmp_path))
    assert not FakeWorker.instances and not started
