"""The failure marker (clip-proxies, "A failed proxy attempt is recorded for the clip's key").

A fake ffmpeg runtime (the one ``test_proxies_ensure`` uses) makes ``ensure_proxy`` fail in the
ways a real run does; the state reader then says ``failed`` with the recorded cause.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, List

import pytest
from proxy_cache_trees import SPRITE, filmstrip_record
from test_proxies_ensure import (  # noqa: F401  (enabled_loggers is an autouse fixture)
    Env,
    FakeRuntime,
    enabled_loggers,
    fail_with,
)

from auto_reel_ng.errors import (
    FfmpegCancelledError,
    FfmpegError,
    FilmstripError,
    ProbeError,
    ProxyCacheError,
    ProxyError,
)
from auto_reel_ng.proxies import (
    ProxyEntry,
    ProxyStatus,
    ensure_filmstrip,
    marker_path,
    proxy_key,
    read_proxy_state,
    record_failure,
)


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Env:
    return Env(tmp_path, monkeypatch)


def reason_of(env: Env) -> Any:
    reading = read_proxy_state(env.clip, settings=env.settings)
    assert reading.status is ProxyStatus.FAILED
    return reading.reason


def add_filmstrip(entry: ProxyEntry) -> None:
    """Complete a fake-made entry with a sprite and its record, as ``ensure_filmstrip`` does."""
    (entry.directory / "filmstrip.jpg").write_bytes(SPRITE)
    document = json.loads(entry.facts_path.read_text(encoding="utf-8"))
    document["filmstrip"] = filmstrip_record()
    entry.facts_path.write_text(json.dumps(document), encoding="utf-8")


def encode_failure(clip: Path) -> FfmpegError:
    return FfmpegError(
        f"Command exited 1: /usr/bin/ffmpeg -i {clip.resolve()} -c:v libx264 /cache/.k.part/proxy.mp4\n"
        f"stderr:\n[mov,mp4 @ 0x55d] {clip.resolve()}: moov atom not found"
    )


def test_a_failed_encode_leaves_a_marker_and_no_entry_and_no_build(env: Env) -> None:
    env.runtime.behaviours = [fail_with(encode_failure(env.clip))]

    with pytest.raises(ProxyError, match="ffmpeg failed on the cpu path"):
        env.ensure()

    assert env.markers() == [marker_path(env.cache, proxy_key(env.clip))]
    assert env.entries() == []
    assert env.builds() == []
    assert json.loads(env.markers()[0].read_text(encoding="utf-8")) == {
        "reason": "ffmpeg failed on the cpu path: moov atom not found"
    }
    assert reason_of(env) == "ffmpeg failed on the cpu path: moov atom not found"


def test_the_recorded_cause_names_the_file_never_its_path(env: Env) -> None:
    env.runtime.behaviours = [fail_with(encode_failure(env.clip))]
    with pytest.raises(ProxyError):
        env.ensure()

    text = env.markers()[0].read_text(encoding="utf-8")
    assert str(env.clip.parent) not in text
    assert str(env.cache) not in text

    direct = env.cache / "other.fail"
    assert direct  # (silences unused warnings; the call below is the one under test)
    record_failure(
        env.cache, "k" * 64, env.clip, f"cannot read /var/home/x/lib/{env.clip.name} here"
    )
    recorded = json.loads((env.cache / f"{'k' * 64}.fail").read_text(encoding="utf-8"))
    assert "/var/home" not in recorded["reason"]


def test_the_recorded_cause_is_one_line(env: Env) -> None:
    env.runtime.behaviours = [fail_with(encode_failure(env.clip))]
    with pytest.raises(ProxyError):
        env.ensure()
    assert "\n" not in reason_of(env)


def test_a_probe_failure_is_recorded(env: Env) -> None:
    env.probe_error = ProbeError(f"File is empty (zero bytes): {env.clip.resolve()}")

    with pytest.raises(ProxyError, match="empty"):
        env.ensure()

    assert "empty" in reason_of(env)
    assert str(env.clip.parent) not in reason_of(env)


def test_a_verification_failure_is_recorded(env: Env) -> None:
    # The fake output is not a playable proxy: its probe says it has no audio (the clip has some).
    env.runtime.proxy_probes = [
        {"streams": [{"codec_type": "video", "width": 960, "height": 540}], "format": {}}
    ]
    with pytest.raises(ProxyError):
        env.ensure()
    assert reason_of(env)


def test_a_retry_that_succeeds_reads_ready_with_the_marker_still_on_disk(env: Env) -> None:
    env.runtime.behaviours = [fail_with(encode_failure(env.clip))]
    with pytest.raises(ProxyError):
        env.ensure()
    assert read_proxy_state(env.clip, settings=env.settings).status is ProxyStatus.FAILED

    entry = env.ensure()  # the retry is attempted although a marker exists
    assert entry.generated is True
    # The proxy is made, its sprite is not yet: the old failure no longer describes the clip.
    assert read_proxy_state(env.clip, settings=env.settings).status is ProxyStatus.ABSENT
    add_filmstrip(entry)

    reading = read_proxy_state(env.clip, settings=env.settings)
    assert reading.status is ProxyStatus.READY
    assert env.markers() != []  # nothing removed it: a ready entry outranks it


def test_a_changed_file_does_not_inherit_the_marker(env: Env) -> None:
    env.runtime.behaviours = [fail_with(encode_failure(env.clip))]
    with pytest.raises(ProxyError):
        env.ensure()
    assert read_proxy_state(env.clip, settings=env.settings).status is ProxyStatus.FAILED

    os.utime(env.clip, ns=(1_800_000_000_000_000_000,) * 2)

    assert read_proxy_state(env.clip, settings=env.settings).status is ProxyStatus.ABSENT


def test_a_marker_has_no_expiry(env: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    env.runtime.behaviours = [fail_with(encode_failure(env.clip))]
    with pytest.raises(ProxyError):
        env.ensure()
    marker = env.markers()[0]
    long_ago = marker.stat().st_mtime - 30 * 24 * 3600
    os.utime(marker, (long_ago, long_ago))
    assert read_proxy_state(env.clip, settings=env.settings).status is ProxyStatus.FAILED


@pytest.mark.skipif(os.geteuid() == 0, reason="root writes anywhere")
def test_an_unwritable_cache_gives_the_attempts_own_error_and_a_warning(
    env: Env, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    # An Alembic ``fileConfig`` run by an earlier test disables loggers that already exist.
    monkeypatch.setattr(logging.getLogger("auto_reel_ng.proxies.failure"), "disabled", False)
    env.cache.mkdir(parents=True)
    env.cache.chmod(0o555)
    env.probe_error = ProbeError("File is empty (zero bytes)")
    try:
        with caplog.at_level(logging.WARNING, logger="auto_reel_ng.proxies.failure"):
            with pytest.raises(ProxyError, match="empty"):  # the attempt's own error, only
                env.ensure()
    finally:
        env.cache.chmod(0o755)

    warnings: List[str] = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1 and str(env.cache) in warnings[0]
    assert env.markers() == []


def test_a_cache_error_and_a_cancel_record_nothing(env: Env) -> None:
    env.runtime.behaviours = [
        fail_with(FfmpegError("Command exited 1: x\nstderr:\nNo space left on device"))
    ]
    with pytest.raises(ProxyCacheError):
        env.ensure()
    assert env.markers() == []

    env.runtime.behaviours = [fail_with(FfmpegCancelledError("ffmpeg canceled"))]
    with pytest.raises(FfmpegCancelledError):
        env.ensure()
    assert env.markers() == []


def test_a_clip_that_cannot_be_statted_records_nothing(env: Env) -> None:
    with pytest.raises(ProxyError, match="cannot stat"):
        env.ensure(clip=env.clip.parent / "gone.mp4")
    assert env.markers() == []
    assert not env.cache.exists()


def test_a_hit_and_a_success_write_no_marker(env: Env) -> None:
    env.ensure()
    env.ensure()
    assert env.markers() == []


def test_a_failed_filmstrip_is_not_remembered(env: Env) -> None:
    """``clip-filmstrips``: a sprite failure is not remembered, so the clip reads absent."""
    entry = env.ensure()
    entry.facts_path.write_text("[]", encoding="utf-8")  # not a JSON object: the sprite fails

    with pytest.raises(FilmstripError):
        ensure_filmstrip(env.clip, entry, runtime=env.runtime)  # type: ignore[arg-type]

    assert env.markers() == []
