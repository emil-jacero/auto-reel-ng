"""``ClipOut.proxy`` in the event detail (api-service, "The event detail reports each clip's proxy state").

Cache entries are hand-built (``proxy_cache_trees``): the detail reads them with ``stat`` and
one JSON read, so no ffmpeg is needed and any process the read starts is a failure.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient
from proxy_cache_trees import sony_facts, tree, write_entry, write_marker
from test_api_events import _BBQ, _clips_by_identity, _detail, _make_fresh

from auto_reel_ng.api.app import create_app
from auto_reel_ng.api.media import MediaFile
from auto_reel_ng.api.settings import resolve_api_settings

pytestmark = pytest.mark.requires_db

EVENT = Path("2024") / "2024-07-04 - Barbecue"


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    for relative in ("00500.mp4", "clips/00600.mp4"):
        clip = root / EVENT / relative
        clip.parent.mkdir(parents=True, exist_ok=True)
        clip.write_bytes(b"clip " + relative.encode())
    return root


@pytest.fixture
def cache(tmp_path: Path, project: Path) -> Path:
    path = tmp_path / "pcache"
    write_config(project, {"cache_dir": str(path)})
    return path


@pytest.fixture
def client(project: Path, postgres_container: str, jobs_schema_engine):  # type: ignore[no-untyped-def]
    settings = resolve_api_settings(project, env={"DATABASE_URL": postgres_container})
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def write_config(project: Path, proxies: Dict[str, object]) -> None:
    (project / "config.yaml").write_text(json.dumps({"proxies": proxies}), encoding="utf-8")


def clip_path(project: Path, identity: str = "00500.mp4") -> Path:
    return project / EVENT / identity


def proxies(client: TestClient) -> Dict[str, Any]:
    return {k: v["proxy"] for k, v in _clips_by_identity(_detail(client)).items()}


# --------------------------------------------------------------------------- #
# the states and the facts
# --------------------------------------------------------------------------- #


def test_a_prepared_pcm_clip_reports_its_recorded_facts_and_the_proxys_entity_tag(
    client: TestClient, project: Path, cache: Path
) -> None:
    clip = clip_path(project)
    entry = write_entry(cache, clip, facts=sony_facts(duration=24.96))

    proxy = proxies(client)["00500.mp4"]

    assert proxy["state"] == "ready"
    assert proxy["reason"] is None
    assert proxy["facts"] == {
        "duration": 24.96,
        "fps_num": 25,
        "fps_den": 1,
        "vfr": False,
        "width": 960,
        "height": 540,
        "rotation": None,
        "audio_codec": "pcm_s16be",
        "filmstrip": {
            "tile_width": 160,
            "tile_height": 90,
            "columns": 10,
            "tiles": 25,
            "interval": 1,
        },
    }
    media = MediaFile(entry / "proxy.mp4", (entry / "proxy.mp4").stat())
    assert proxy["version"] == media.etag.strip('"')  # byte for byte the media routes' tag


def test_a_rotated_portrait_clip_reports_its_rotation_and_displayed_size(
    client: TestClient, project: Path, cache: Path
) -> None:
    write_entry(
        cache,
        clip_path(project, "clips/00600.mp4"),
        facts=sony_facts(rotation=90, width=540, height=960, audio_codec="aac", duration=6.5),
    )

    facts = proxies(client)["clips/00600.mp4"]["facts"]

    assert (facts["rotation"], facts["width"], facts["height"]) == (90, 540, 960)
    assert facts["audio_codec"] == "aac" and facts["duration"] == 6.5


def test_a_variable_frame_rate_clip_keeps_its_fraction_and_a_silent_one_a_null_codec(
    client: TestClient, project: Path, cache: Path
) -> None:
    write_entry(
        cache,
        clip_path(project),
        facts=sony_facts(fps_num=30000, fps_den=1001, vfr=True, audio_codec=None),
    )

    facts = proxies(client)["00500.mp4"]["facts"]

    assert (facts["fps_num"], facts["fps_den"], facts["vfr"]) == (30000, 1001, True)
    assert facts["audio_codec"] is None


def test_an_unprepared_clip_is_absent_and_the_cache_is_untouched(
    client: TestClient, project: Path, cache: Path
) -> None:
    write_entry(cache, clip_path(project), facts=sony_facts())
    before = tree(cache)

    proxy = proxies(client)["clips/00600.mp4"]

    assert proxy == {"state": "absent", "facts": None, "version": None, "reason": None}
    assert tree(cache) == before


def test_a_cache_directory_that_does_not_exist_is_not_created_by_a_read(
    client: TestClient, cache: Path
) -> None:
    assert {p["state"] for p in proxies(client).values()} == {"absent"}
    assert not cache.exists()


def test_a_failed_clip_reports_a_cause_that_names_no_path(
    client: TestClient, project: Path, cache: Path
) -> None:
    clip = clip_path(project)
    write_marker(cache, clip, {"reason": f"moov atom not found in {clip.resolve()}"})

    proxy = proxies(client)["00500.mp4"]

    assert proxy["state"] == "failed"
    assert proxy["reason"] == "moov atom not found in 00500.mp4"
    assert proxy["facts"] is None and proxy["version"] is None
    assert str(project) not in json.dumps(proxy)


def test_a_damaged_entry_is_stale(client: TestClient, project: Path, cache: Path) -> None:
    write_entry(cache, clip_path(project), facts_text='{"duration": 2')
    proxy = proxies(client)["00500.mp4"]
    assert proxy == {"state": "stale", "facts": None, "version": None, "reason": None}


def test_a_replaced_file_reads_absent_not_the_old_facts(
    client: TestClient, project: Path, cache: Path
) -> None:
    clip = clip_path(project)
    write_entry(cache, clip)
    assert proxies(client)["00500.mp4"]["state"] == "ready"

    clip.write_bytes(b"replaced by a larger file")
    assert proxies(client)["00500.mp4"] == {
        "state": "absent",
        "facts": None,
        "version": None,
        "reason": None,
    }


def test_the_version_follows_the_proxy_file(client: TestClient, project: Path, cache: Path) -> None:
    entry = write_entry(cache, clip_path(project))
    first = proxies(client)["00500.mp4"]["version"]
    os.utime(entry / "proxy.mp4", ns=(1_000_000_000, 1_000_000_000))
    second = proxies(client)["00500.mp4"]["version"]
    assert first and second and first != second


# --------------------------------------------------------------------------- #
# unknown is null, never absent
# --------------------------------------------------------------------------- #


FACTS_REEL = """\
version: 0
metadata:
  title: Barbecue
chapters:
  - name: ""
    clips:
      - 00500.mp4
      - gone.mp4
"""


def test_a_missing_clip_has_no_proxy_state(client: TestClient, project: Path, cache: Path) -> None:
    write_entry(cache, clip_path(project))
    (project / EVENT / "reel.yaml").write_text(FACTS_REEL, encoding="utf-8")

    clips = _clips_by_identity(_detail(client))

    assert clips["gone.mp4"]["status"] == "missing"
    assert clips["gone.mp4"]["proxy"] is None
    assert clips["gone.mp4"]["size"] is None
    assert clips["00500.mp4"]["proxy"]["state"] == "ready"


def test_a_missing_clip_is_never_looked_up(
    client: TestClient, project: Path, cache: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from auto_reel_ng.api import events_read

    (project / EVENT / "reel.yaml").write_text(FACTS_REEL, encoding="utf-8")
    looked_up = []
    real = events_read.read_proxy_state

    def spy(path: Path, **kwargs: Any) -> Any:
        looked_up.append(path.name)
        return real(path, **kwargs)

    monkeypatch.setattr(events_read, "read_proxy_state", spy)

    _detail(client)

    assert "gone.mp4" not in looked_up
    assert sorted(looked_up) == ["00500.mp4", "00600.mp4"]


def test_an_event_without_a_document_reports_proxy_states_too(
    client: TestClient, project: Path, cache: Path
) -> None:
    assert not (project / EVENT / "reel.yaml").exists()  # seeding: no document yet
    write_entry(cache, clip_path(project))
    assert proxies(client)["00500.mp4"]["state"] == "ready"


def test_an_unresolvable_proxies_configuration_leaves_every_state_unknown(
    client: TestClient,
    project: Path,
    cache: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    write_entry(cache, clip_path(project))
    before = _detail(client)
    write_config(project, {"cache_dir": "relative/path"})

    with caplog.at_level("WARNING", logger="auto_reel_ng.api.events_read"):
        response = client.get(f"/api/v1/events/{quote(_BBQ, safe='/')}")

    assert response.status_code == 200
    clips = _clips_by_identity(response.json())
    assert [clip["proxy"] for clip in clips.values()] == [None] * len(clips)
    warnings = [r.getMessage() for r in caplog.records if "proxies.cache_dir" in r.getMessage()]
    assert len(warnings) == 1  # one per request, not one per clip
    other = {k: {f: v for f, v in c.items() if f != "proxy"} for k, c in clips.items()}
    reference = {
        k: {f: v for f, v in c.items() if f != "proxy"}
        for k, c in _clips_by_identity(before).items()
    }
    assert other == reference


@pytest.mark.skipif(os.geteuid() == 0, reason="root searches any directory")
def test_an_unsearchable_entry_is_unknown_for_that_clip_only(
    client: TestClient, project: Path, cache: Path
) -> None:
    broken = write_entry(cache, clip_path(project))
    write_entry(cache, clip_path(project, "clips/00600.mp4"))
    broken.chmod(0o000)
    try:
        states = proxies(client)
    finally:
        broken.chmod(0o755)

    assert states["00500.mp4"] is None
    assert states["clips/00600.mp4"]["state"] == "ready"


@pytest.mark.skipif(os.geteuid() == 0, reason="root searches any directory")
def test_an_unreadable_cache_directory_is_unknown_not_an_error(
    client: TestClient, project: Path, cache: Path
) -> None:
    write_entry(cache, clip_path(project))
    cache.chmod(0o000)
    try:
        response = client.get(f"/api/v1/events/{quote(_BBQ, safe='/')}")
    finally:
        cache.chmod(0o755)

    assert response.status_code == 200
    assert {clip["proxy"] for clip in _clips_by_identity(response.json()).values()} == {None}


# --------------------------------------------------------------------------- #
# not a staleness input, not in the list, not a probe
# --------------------------------------------------------------------------- #


def test_the_proxy_state_is_not_part_of_the_staleness_verdict(
    client: TestClient, project: Path, cache: Path
) -> None:
    event_dir = project / EVENT
    _make_fresh(project, event_dir)
    before = _detail(client)["staleness"]
    assert before["stale"] is False

    for identity in ("00500.mp4", "clips/00600.mp4"):
        write_entry(cache, clip_path(project, identity))
    after = _detail(client)

    assert {c["proxy"]["state"] for c in _clips_by_identity(after).values()} == {"ready"}
    assert after["staleness"] == before


def test_the_events_list_carries_no_proxy(client: TestClient, project: Path, cache: Path) -> None:
    write_entry(cache, clip_path(project))
    body = client.get("/api/v1/events")
    assert body.status_code == 200
    assert "proxy" not in body.text
    assert "chapters" not in body.text


def test_reading_a_25_clip_event_starts_no_process_and_leaves_duration_alone(
    client: TestClient, project: Path, cache: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    event_dir = project / EVENT
    identities = []
    for number in range(25):
        identity = f"clips/c{number:02d}.mp4"
        (event_dir / identity).write_bytes(b"clip %d" % number)
        identities.append(identity)
        if number % 2 == 0:
            write_entry(cache, event_dir / identity)
    before = tree(cache)
    reference = {k: c["duration"] for k, c in _clips_by_identity(_detail(client)).items()}

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("a process was started")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_shell", forbidden)
    monkeypatch.setattr(os, "system", forbidden)
    monkeypatch.setattr(os, "posix_spawn", forbidden)

    response = client.get(f"/api/v1/events/{quote(_BBQ, safe='/')}")

    assert response.status_code == 200
    clips = _clips_by_identity(response.json())
    assert len(clips) >= 25
    states = [clips[i]["proxy"]["state"] for i in identities]
    assert states.count("ready") == 13 and states.count("absent") == 12
    assert {k: c["duration"] for k, c in clips.items()} == reference  # ClipOut.duration unchanged
    assert tree(cache) == before
