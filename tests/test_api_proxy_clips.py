"""``proxy_read.proxy_clips`` and ``proxies_fresh`` (change ``proxy-enqueue-endpoint``).

The clip set the proxy enqueue counts is the one the proxy job prepares, and the freshness
read is ``stat`` and JSON only. No database: the functions take the settings and a folder.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Optional

import pytest
from proxy_cache_trees import sony_facts, write_entry, write_marker

from auto_reel_ng.api import proxy_read
from auto_reel_ng.api.settings import ApiSettings, resolve_api_settings
from auto_reel_ng.config.project import ConfigError
from auto_reel_ng.errors import ProxyCacheError, ProxyError
from auto_reel_ng.event import scan_event

EVENT = Path("2024") / "2024-07-04 - Barbecue"
IDENTITIES = ["00500.mp4", "chapter/00600.mp4", "chapter/00700.mp4"]


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    for identity in IDENTITIES:
        clip = root / EVENT / identity
        clip.parent.mkdir(parents=True, exist_ok=True)
        clip.write_bytes(b"clip " + identity.encode())
    return root


@pytest.fixture
def cache(tmp_path: Path, project: Path) -> Path:
    path = tmp_path / "pcache"
    path.mkdir()
    (project / "config.yaml").write_text(json.dumps({"proxies": {"cache_dir": str(path)}}))
    return path


@pytest.fixture
def settings(project: Path) -> ApiSettings:
    return resolve_api_settings(
        project, env={"DATABASE_URL": "postgresql+psycopg://x:x@127.0.0.1:1/x"}
    )


def _event(project: Path) -> Path:
    return project / EVENT


def _ready(project: Path, cache: Path, *identities: str) -> None:
    for identity in identities or IDENTITIES:
        write_entry(cache, _event(project) / identity, facts=sony_facts())


def _fresh(settings: ApiSettings, project: Path, clips: Optional[list] = None) -> bool:
    event = _event(project)
    return proxy_read.proxies_fresh(
        settings, event, clips if clips is not None else proxy_read.proxy_clips(event)
    )


def test_the_clip_set_is_every_clip_the_folder_lists_whatever_reel_yaml_says(
    project: Path,
) -> None:
    (_event(project) / "reel.yaml").write_text(
        "version: 0\nmetadata:\n  title: Barbecue\nchapters:\n- name: Main\n"
        "  clips: [00500.mp4, chapter/00600.mp4, gone.mp4]\n"
        "clips:\n  chapter/00600.mp4:\n    exclude: true\nignore: [chapter/00700.mp4]\n"
    )
    (_event(project) / "original").mkdir()
    (_event(project) / "original" / "raw.mp4").write_bytes(b"raw")

    clips = proxy_read.proxy_clips(_event(project))

    assert clips == list(scan_event(_event(project)).identities)  # what proxy-job walks
    assert sorted(clips) == sorted(
        IDENTITIES
    )  # ignored and excluded included; no gone.mp4, no original/


def test_every_clip_ready_is_fresh(settings: ApiSettings, project: Path, cache: Path) -> None:
    _ready(project, cache)
    assert _fresh(settings, project) is True


@pytest.mark.parametrize("damage", ["absent", "stale", "failed"])
def test_one_clip_that_is_not_ready_is_not_fresh(
    settings: ApiSettings, project: Path, cache: Path, damage: str
) -> None:
    _ready(project, cache, "00500.mp4", "chapter/00600.mp4")
    clip = _event(project) / "chapter/00700.mp4"
    if damage == "stale":
        write_entry(cache, clip, facts_text="not json")
    elif damage == "failed":
        write_marker(cache, clip, {"reason": "moov atom not found"})

    assert _fresh(settings, project) is False


def test_no_clips_is_vacuously_fresh(settings: ApiSettings, project: Path, cache: Path) -> None:
    assert _fresh(settings, project, clips=[]) is True
    empty = _event(project).parent / "2024-07-05 - Empty"
    empty.mkdir()
    assert proxy_read.proxy_clips(empty) == []


def test_an_unreadable_cache_raises_instead_of_reading_absent(
    settings: ApiSettings, project: Path, cache: Path
) -> None:
    cache.chmod(0o000)
    try:
        with pytest.raises(ProxyCacheError):
            _fresh(settings, project)
    finally:
        cache.chmod(0o755)


def test_a_clip_that_cannot_be_statted_raises(
    settings: ApiSettings, project: Path, cache: Path
) -> None:
    with pytest.raises(ProxyError):
        proxy_read.proxies_fresh(settings, _event(project), ["vanished.mp4"])


def test_unusable_proxies_settings_raise(settings: ApiSettings, project: Path) -> None:
    (project / "config.yaml").write_text(json.dumps({"proxies": {"cache_dir": "relative"}}))
    with pytest.raises(ConfigError):
        _fresh(settings, project)


def test_an_unlistable_folder_raises_os_error(project: Path) -> None:
    folder = _event(project)
    folder.chmod(0o000)
    try:
        with pytest.raises(OSError):
            proxy_read.proxy_clips(folder)
    finally:
        folder.chmod(0o755)


def test_the_read_starts_no_process_and_writes_nothing(
    settings: ApiSettings, project: Path, cache: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ready(project, cache, "00500.mp4")

    def refuse(*args: Any, **kwargs: Any) -> None:
        raise AssertionError(f"started a process: {args!r}")

    monkeypatch.setattr(subprocess, "Popen", refuse)
    monkeypatch.setattr(subprocess, "run", refuse)
    before = sorted(str(p.relative_to(cache)) for p in cache.rglob("*"))

    assert _fresh(settings, project) is False

    assert sorted(str(p.relative_to(cache)) for p in cache.rglob("*")) == before
