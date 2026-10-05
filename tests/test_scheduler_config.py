"""Tests for worker identity and ``worker.*`` config resolution (D-S1/D-S5/D-2)."""

from __future__ import annotations

import pytest

from auto_reel_ng.config.project import ConfigError, ProjectConfig
from auto_reel_ng.scheduler.config import (
    DEFAULT_ANALYSIS_SLOTS,
    DEFAULT_AUTO_ANALYZE,
    DEFAULT_AUTO_ANALYZE_INTERVAL_S,
    DEFAULT_AUTO_ANALYZE_MAX_EVENTS,
    DEFAULT_CPU_SLOTS,
    DEFAULT_GPU_SESSIONS_PER_DEVICE,
    DEFAULT_POLL_INTERVAL_S,
    DEFAULT_PROXY_SLOTS,
    resolve_worker_config,
    worker_identity,
)

# --------------------------------------------------------------------------- #
# worker_identity
# --------------------------------------------------------------------------- #


def test_worker_identity_has_three_colon_separated_parts() -> None:
    identity = worker_identity()
    parts = identity.split(":")
    assert len(parts) == 3
    host, pid, nonce = parts
    assert host and pid.isdigit() and nonce


def test_worker_identity_is_fresh_each_call() -> None:
    assert worker_identity() != worker_identity()


# --------------------------------------------------------------------------- #
# resolve_worker_config precedence (D-2)
# --------------------------------------------------------------------------- #


def test_defaults_apply_when_nothing_overrides() -> None:
    config = resolve_worker_config(ProjectConfig())
    assert config.poll_interval == DEFAULT_POLL_INTERVAL_S
    assert config.gpu_sessions_per_device == DEFAULT_GPU_SESSIONS_PER_DEVICE
    assert config.cpu_slots == DEFAULT_CPU_SLOTS


def test_config_yaml_overrides_defaults() -> None:
    project_config = ProjectConfig(
        worker={"poll_interval": 5.0, "gpu_sessions_per_device": 2, "cpu_slots": 3}
    )
    config = resolve_worker_config(project_config)
    assert config.poll_interval == 5.0
    assert config.gpu_sessions_per_device == 2
    assert config.cpu_slots == 3


def test_cli_flag_overrides_config_yaml() -> None:
    project_config = ProjectConfig(worker={"poll_interval": 5.0, "cpu_slots": 3})
    config = resolve_worker_config(
        project_config, poll_interval=1.0, gpu_sessions_per_device=4, cpu_slots=8
    )
    assert config.poll_interval == 1.0
    assert config.gpu_sessions_per_device == 4
    assert config.cpu_slots == 8


def test_wrong_typed_worker_setting_fails_loud() -> None:
    project_config = ProjectConfig(worker={"cpu_slots": "lots"})
    with pytest.raises(ConfigError):
        resolve_worker_config(project_config)


# --------------------------------------------------------------------------- #
# worker.proxy_slots (proxy-job)
# --------------------------------------------------------------------------- #


def test_proxy_slots_default_to_one() -> None:
    assert DEFAULT_PROXY_SLOTS == 1
    assert resolve_worker_config(ProjectConfig()).proxy_slots == 1


def test_proxy_slots_come_from_config_yaml() -> None:
    config = resolve_worker_config(ProjectConfig(worker={"proxy_slots": 2}))
    assert config.proxy_slots == 2


@pytest.mark.parametrize("value", [0, -1, "two", 1.5, True])
def test_a_bad_proxy_slots_fails_loud_naming_the_key(value: object) -> None:
    with pytest.raises(ConfigError, match=r"worker\.proxy_slots"):
        resolve_worker_config(ProjectConfig(worker={"proxy_slots": value}))


# --------------------------------------------------------------------------- #
# worker.analysis_slots (analysis-job)
# --------------------------------------------------------------------------- #


def test_analysis_slots_default_to_one() -> None:
    assert DEFAULT_ANALYSIS_SLOTS == 1
    assert resolve_worker_config(ProjectConfig()).analysis_slots == 1


def test_analysis_slots_come_from_config_yaml() -> None:
    config = resolve_worker_config(ProjectConfig(worker={"analysis_slots": 3}))
    assert config.analysis_slots == 3


@pytest.mark.parametrize("value", [0, -1, "two", 1.5, True])
def test_a_bad_analysis_slots_fails_loud_naming_the_key(value: object) -> None:
    with pytest.raises(ConfigError, match=r"worker\.analysis_slots"):
        resolve_worker_config(ProjectConfig(worker={"analysis_slots": value}))


# --------------------------------------------------------------------------- #
# worker.auto_analyze* (analysis-auto-sweep)
# --------------------------------------------------------------------------- #


def test_the_auto_analysis_sweep_defaults_on_every_300_s_two_events() -> None:
    assert (DEFAULT_AUTO_ANALYZE, DEFAULT_AUTO_ANALYZE_INTERVAL_S) == (True, 300.0)
    assert DEFAULT_AUTO_ANALYZE_MAX_EVENTS == 2
    config = resolve_worker_config(ProjectConfig())
    assert config.auto_analyze is True
    assert config.auto_analyze_interval == 300.0
    assert config.auto_analyze_max_events == 2


def test_the_auto_analysis_keys_come_from_config_yaml() -> None:
    config = resolve_worker_config(
        ProjectConfig(
            worker={
                "auto_analyze": False,
                "auto_analyze_interval": 20,
                "auto_analyze_max_events": 5,
            }
        )
    )
    assert config.auto_analyze is False
    assert config.auto_analyze_interval == 20.0
    assert config.auto_analyze_max_events == 5


def test_a_fractional_interval_is_accepted() -> None:
    config = resolve_worker_config(ProjectConfig(worker={"auto_analyze_interval": 0.5}))
    assert config.auto_analyze_interval == 0.5


@pytest.mark.parametrize("value", ["yes", 1, 0, "true", "on"])
def test_a_non_bool_auto_analyze_fails_loud_naming_the_key(value: object) -> None:
    with pytest.raises(ConfigError, match=r"worker\.auto_analyze\b"):
        resolve_worker_config(ProjectConfig(worker={"auto_analyze": value}))


@pytest.mark.parametrize("value", [0, -1, -0.5, True, "300", float("inf"), float("nan")])
def test_a_bad_auto_analyze_interval_fails_loud_naming_the_key(value: object) -> None:
    with pytest.raises(ConfigError, match=r"worker\.auto_analyze_interval"):
        resolve_worker_config(ProjectConfig(worker={"auto_analyze_interval": value}))


@pytest.mark.parametrize("value", [0, -1, 1.5, True, "2"])
def test_a_bad_auto_analyze_max_events_fails_loud_naming_the_key(value: object) -> None:
    with pytest.raises(ConfigError, match=r"worker\.auto_analyze_max_events"):
        resolve_worker_config(ProjectConfig(worker={"auto_analyze_max_events": value}))
