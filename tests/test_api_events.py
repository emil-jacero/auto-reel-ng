"""Tests for the events + analysis read routes (tasks 2.2-2.4)."""

from __future__ import annotations

import dataclasses
import os
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from auto_reel_ng.api.app import create_app
from auto_reel_ng.api.events_read import EventNotFoundError, listed_event_dir
from auto_reel_ng.api.settings import resolve_api_settings
from auto_reel_ng.config import default_output_dir
from auto_reel_ng.event import DEFAULT_CLIP_ORDER

pytestmark = pytest.mark.requires_db


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    _touch(root / "2024" / "2024-06-21 - Midsommar i Dalarna Åäö" / "00400.mp4")
    _touch(root / "2024" / "2024-07-04 - Barbecue" / "00500.mp4")
    _touch(root / "2024" / "2024-07-04 - Barbecue" / "clips" / "00600.mp4")
    return root


@pytest.fixture
def client(project: Path, postgres_container: str, jobs_schema_engine):
    settings = resolve_api_settings(project, env={"DATABASE_URL": postgres_container})
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client


def test_list_events_matches_scan(client: TestClient) -> None:
    response = client.get("/api/v1/events")
    assert response.status_code == 200
    body = response.json()
    ids = {event["event_id"] for event in body}
    assert ids == {
        "2024/2024-06-21 - Midsommar i Dalarna Åäö",
        "2024/2024-07-04 - Barbecue",
    }
    barbecue = next(e for e in body if e["event_id"] == "2024/2024-07-04 - Barbecue")
    assert barbecue["clip_count"] == 2
    assert barbecue["new_count"] == 2
    assert barbecue["missing_count"] == 0


def test_list_events_excludes_reelignored_event(client: TestClient, project: Path) -> None:
    _touch(project / "2024" / "2024-06-21 - Midsommar i Dalarna Åäö" / ".reelignore")
    response = client.get("/api/v1/events")
    assert response.status_code == 200
    assert {event["event_id"] for event in response.json()} == {"2024/2024-07-04 - Barbecue"}


def test_disk_edit_is_visible_on_next_request(client: TestClient, project: Path) -> None:
    event_dir = project / "2024" / "2024-06-21 - Midsommar i Dalarna Åäö"
    (event_dir / "reel.yaml").write_text(
        "version: 0\nmetadata:\n  title: Original Title\n", encoding="utf-8"
    )
    event_id = quote("2024/2024-06-21 - Midsommar i Dalarna Åäö", safe="/")

    first = client.get(f"/api/v1/events/{event_id}")
    assert first.json()["title"] == "Original Title"

    (event_dir / "reel.yaml").write_text(
        "version: 0\nmetadata:\n  title: Updated Title\n", encoding="utf-8"
    )
    second = client.get(f"/api/v1/events/{event_id}")
    assert second.json()["title"] == "Updated Title"


def test_event_identity_round_trips_with_spaces_and_unicode(client: TestClient) -> None:
    listed = client.get("/api/v1/events").json()
    raw_id = next(e["event_id"] for e in listed if "Midsommar" in e["event_id"])
    assert raw_id == "2024/2024-06-21 - Midsommar i Dalarna Åäö"

    encoded = quote(raw_id, safe="/")
    detail = client.get(f"/api/v1/events/{encoded}")
    assert detail.status_code == 200
    assert detail.json()["event_id"] == raw_id


def test_event_detail_reports_staleness_when_stale(client: TestClient) -> None:
    event_id = quote("2024/2024-07-04 - Barbecue", safe="/")
    response = client.get(f"/api/v1/events/{event_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["staleness"]["stale"] is True
    assert "no_manifest" in body["staleness"]["reasons"]


def test_event_detail_reports_staleness_when_fresh(client: TestClient, project: Path) -> None:
    from auto_reel_ng.cli.adoption import persist, prepare_event
    from auto_reel_ng.config.project import load_project_config, resolve_look_defaults
    from auto_reel_ng.ffmpeg.runtime import FfmpegRuntime
    from auto_reel_ng.render import output_relpath
    from auto_reel_ng.staleness.fingerprint import compute_fingerprint, engine_identity
    from auto_reel_ng.staleness.manifest import write_manifest

    event_dir = project / "2024" / "2024-07-04 - Barbecue"
    event = prepare_event(event_dir, order=DEFAULT_CLIP_ORDER, adopt=True)
    persist(event)
    runtime = FfmpegRuntime()
    fingerprint = compute_fingerprint(
        event.document,
        event_dir=event_dir,
        look_defaults=resolve_look_defaults(load_project_config(project)),
        ffmpeg_version=runtime.version,
    )
    output_path = default_output_dir(project) / output_relpath(event.document.metadata)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(b"already-rendered")
    write_manifest(
        event_dir,
        fingerprint,
        output=output_path.name,
        engine_identity=engine_identity(runtime.version),
    )

    event_id = quote("2024/2024-07-04 - Barbecue", safe="/")
    response = client.get(f"/api/v1/events/{event_id}")
    body = response.json()
    assert body["staleness"] == {
        "stale": False,
        "reasons": [],
        "renamed_from": None,
        "output_name": None,
    }


def test_getting_event_detail_never_writes_a_manifest(client: TestClient, project: Path) -> None:
    event_id = quote("2024/2024-07-04 - Barbecue", safe="/")
    client.get(f"/api/v1/events/{event_id}")
    event_dir = project / "2024" / "2024-07-04 - Barbecue"
    assert not (event_dir / ".auto-reel" / "cache" / "render-manifest.json").exists()


def test_symlinked_alias_is_not_listed_and_its_id_is_not_found(
    client: TestClient, project: Path
) -> None:
    real = project / "2024" / "2024-07-04 - Barbecue"
    (project / "2024" / "2024-07-01 - Alias").symlink_to(real, target_is_directory=True)

    ids = [event["event_id"] for event in client.get("/api/v1/events").json()]
    assert ids.count("2024/2024-07-04 - Barbecue") == 1
    assert "2024/2024-07-01 - Alias" not in ids
    with pytest.raises(EventNotFoundError):
        listed_event_dir(client.app.state.settings, "2024/2024-07-01 - Alias")


def test_unknown_event_yields_404(client: TestClient) -> None:
    response = client.get("/api/v1/events/2024/does-not-exist")
    assert response.status_code == 404
    assert "title" in response.json()


def test_path_traversal_is_rejected_as_not_found(client: TestClient) -> None:
    response = client.get("/api/v1/events/..%2F..%2Fetc")
    assert response.status_code == 404


def test_unparseable_reel_yaml_is_a_loud_error(client: TestClient, project: Path) -> None:
    event_dir = project / "2024" / "2024-07-04 - Barbecue"
    (event_dir / "reel.yaml").write_text(
        "version: 0\nchapters: [this is not valid: :\n", encoding="utf-8"
    )
    event_id = quote("2024/2024-07-04 - Barbecue", safe="/")

    response = client.get(f"/api/v1/events/{event_id}")
    assert response.status_code == 502
    body = response.json()
    assert "2024/2024-07-04 - Barbecue" in body["detail"]


def test_event_detail_chapters_from_disk_listing_without_document(client: TestClient) -> None:
    event_id = quote("2024/2024-07-04 - Barbecue", safe="/")
    response = client.get(f"/api/v1/events/{event_id}")
    assert response.status_code == 200
    body = response.json()
    chapter_names = {c["name"] for c in body["chapters"]}
    assert chapter_names == {"", "clips"}
    for chapter in body["chapters"]:
        for clip in chapter["clips"]:
            assert clip["status"] == "new"


def test_analysis_absent_is_not_an_empty_result(client: TestClient) -> None:
    event_id = quote("2024/2024-06-21 - Midsommar i Dalarna Åäö", safe="/")
    response = client.get(f"/api/v1/events/{event_id}/analysis")
    assert response.status_code == 200
    body = response.json()
    assert body["analyzed"] is False
    assert body["segments"] == {}


def test_analysis_populated_returns_segments(client: TestClient, project: Path) -> None:
    from auto_reel_ng.analysis.cache import clip_signal, write_entry
    from auto_reel_ng.analysis.models import Segment, SegmentKind

    event_dir = project / "2024" / "2024-06-21 - Midsommar i Dalarna Åäö"
    clip_path = event_dir / "00400.mp4"
    signal = clip_signal(clip_path)
    write_entry(
        event_dir,
        "00400.mp4",
        signal,
        [Segment(start=0.0, end=1.0, kind=SegmentKind.BLACK, confidence=0.9)],
    )

    event_id = quote("2024/2024-06-21 - Midsommar i Dalarna Åäö", safe="/")
    response = client.get(f"/api/v1/events/{event_id}/analysis")
    assert response.status_code == 200
    body = response.json()
    assert body["analyzed"] is True
    assert body["segments"]["00400.mp4"][0]["kind"] == "black"


def test_unknown_event_analysis_yields_404(client: TestClient) -> None:
    response = client.get("/api/v1/events/2024/does-not-exist/analysis")
    assert response.status_code == 404


MIDSOMMAR = "2024/2024-06-21 - Midsommar i Dalarna Åäö"


def _assert_analysis_problem(response, status: int, event_id: str) -> dict:
    assert response.status_code == status
    assert response.headers["content-type"] == "application/json"
    body = response.json()
    assert body["status"] == status
    assert body["event_id"] == event_id
    return body


def _cache_one_segment(event_dir: Path, identity: str) -> None:
    from auto_reel_ng.analysis.cache import clip_signal, write_entry
    from auto_reel_ng.analysis.models import Segment, SegmentKind

    write_entry(
        event_dir,
        identity,
        clip_signal(event_dir / identity),
        [Segment(start=0.0, end=1.0, kind=SegmentKind.BLACK, confidence=0.9)],
    )


def test_analysis_of_a_year_folder_is_not_found(client: TestClient) -> None:
    body = _assert_analysis_problem(client.get("/api/v1/events/2024/analysis"), 404, "2024")
    assert "2024" in body["detail"]


def test_analysis_of_an_events_original_folder_is_not_found(
    client: TestClient, project: Path
) -> None:
    (project / MIDSOMMAR / "original").mkdir()
    folder = f"{MIDSOMMAR}/original"

    analysis = client.get(f"/api/v1/events/{quote(folder, safe='/')}/analysis")

    _assert_analysis_problem(analysis, 404, folder)


def test_analysis_of_a_chapter_folder_is_not_found(client: TestClient) -> None:
    folder = "2024/2024-07-04 - Barbecue/clips"

    analysis = client.get(f"/api/v1/events/{quote(folder, safe='/')}/analysis")

    _assert_analysis_problem(analysis, 404, folder)


def test_analysis_of_a_reelignored_event_is_not_found(client: TestClient, project: Path) -> None:
    event_dir = project / MIDSOMMAR
    _cache_one_segment(event_dir, "00400.mp4")
    _touch(event_dir / ".reelignore")

    analysis = client.get(f"/api/v1/events/{quote(MIDSOMMAR, safe='/')}/analysis")

    _assert_analysis_problem(analysis, 404, MIDSOMMAR)


def test_analysis_never_reads_the_document(client: TestClient, project: Path) -> None:
    event_dir = project / MIDSOMMAR
    _cache_one_segment(event_dir, "00400.mp4")
    (event_dir / "reel.yaml").write_text("chapters: [unterminated\n", encoding="utf-8")

    analysis = client.get(f"/api/v1/events/{quote(MIDSOMMAR, safe='/')}/analysis")

    assert analysis.status_code == 200
    body = analysis.json()
    assert body["analyzed"] is True
    assert body["segments"]["00400.mp4"][0]["kind"] == "black"


def test_analysis_of_an_unlistable_event_is_a_502_unreadable_disk(
    client: TestClient, project: Path
) -> None:
    if os.geteuid() == 0:
        pytest.skip("root ignores file permissions")
    event_dir = project / MIDSOMMAR
    event_dir.chmod(0)
    try:
        analysis = client.get(f"/api/v1/events/{quote(MIDSOMMAR, safe='/')}/analysis")
    finally:
        event_dir.chmod(0o755)

    body = _assert_analysis_problem(analysis, 502, MIDSOMMAR)
    assert body["failure"] == "unreadable_disk"


def test_analysis_with_an_unknown_layout_is_a_502_without_a_kind(
    project: Path, postgres_container: str, jobs_schema_engine
) -> None:
    settings = resolve_api_settings(project, env={"DATABASE_URL": postgres_container})
    broken = dataclasses.replace(settings, layout_name="no-such-layout")
    with TestClient(create_app(broken)) as client:
        analysis = client.get(f"/api/v1/events/{quote(MIDSOMMAR, safe='/')}/analysis")

    body = _assert_analysis_problem(analysis, 502, MIDSOMMAR)
    assert body.get("failure") is None
    assert "no-such-layout" in body["detail"]


FACTS_REEL_YAML = """\
version: 0
metadata:
  title: Barbecue
chapters:
  - name: ""
    clips:
      - 00500.mp4
      - gone.mp4
"""


def _utc_datetime(raw: str):
    from datetime import datetime, timedelta

    parsed = datetime.fromisoformat(raw)
    assert parsed.utcoffset() == timedelta(0), raw
    return parsed


def _clips_by_identity(body: dict) -> dict:
    return {clip["identity"]: clip for chapter in body["chapters"] for clip in chapter["clips"]}


def test_clips_carry_file_facts(client: TestClient, project: Path) -> None:
    event_dir = project / "2024" / "2024-07-04 - Barbecue"
    (event_dir / "00500.mp4").write_bytes(b"\x00" * 11)  # active: in the document and on disk
    (event_dir / "clips" / "00600.mp4").write_bytes(b"\x00" * 22)  # disk-only: NEW
    (event_dir / "reel.yaml").write_text(FACTS_REEL_YAML, encoding="utf-8")

    event_id = quote("2024/2024-07-04 - Barbecue", safe="/")
    body = client.get(f"/api/v1/events/{event_id}").json()
    clips = _clips_by_identity(body)

    assert clips["00500.mp4"]["status"] == "active"
    assert clips["00500.mp4"]["size"] == 11
    _utc_datetime(clips["00500.mp4"]["mtime"])

    assert clips["clips/00600.mp4"]["status"] == "new"
    assert clips["clips/00600.mp4"]["size"] == 22
    _utc_datetime(clips["clips/00600.mp4"]["mtime"])


def test_missing_clip_reports_no_file_facts(client: TestClient, project: Path) -> None:
    event_dir = project / "2024" / "2024-07-04 - Barbecue"
    (event_dir / "reel.yaml").write_text(FACTS_REEL_YAML, encoding="utf-8")

    event_id = quote("2024/2024-07-04 - Barbecue", safe="/")
    body = client.get(f"/api/v1/events/{event_id}").json()
    clips = _clips_by_identity(body)

    assert clips["gone.mp4"]["status"] == "missing"
    assert clips["gone.mp4"]["size"] is None
    assert clips["gone.mp4"]["mtime"] is None
    assert body["missing"] == ["gone.mp4"]


def test_clip_in_a_named_chapter_is_statted_at_its_identity_path(
    client: TestClient, project: Path
) -> None:
    event_dir = project / "2024" / "2024-07-04 - Barbecue"
    # Same basename at the event root and inside the chapter, different sizes: a
    # stat resolved against the event root instead of the identity would report 3.
    (event_dir / "00600.mp4").write_bytes(b"\x00" * 3)
    (event_dir / "clips" / "00600.mp4").write_bytes(b"\x00" * 44)

    event_id = quote("2024/2024-07-04 - Barbecue", safe="/")
    clips = _clips_by_identity(client.get(f"/api/v1/events/{event_id}").json())

    assert clips["clips/00600.mp4"]["size"] == 44
    assert clips["00600.mp4"]["size"] == 3


def test_stat_failure_after_the_scan_reports_nulls_not_a_failed_event(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from auto_reel_ng.api import events_read

    event_dir = project / "2024" / "2024-07-04 - Barbecue"
    document, listing, result = events_read._load_for_reconcile(event_dir, DEFAULT_CLIP_ORDER)

    # The scan has happened; the clip vanishes before the read model stats it.
    real_stat = Path.stat

    def vanished(self: Path, *args: object, **kwargs: object):
        if self.name == "00500.mp4":
            raise OSError("clip vanished mid-request")
        return real_stat(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "stat", vanished)

    chapters = events_read._build_chapters(document, listing, result, event_dir, DEFAULT_CLIP_ORDER)
    clips = {clip.identity: clip for chapter in chapters for clip in chapter.clips}
    assert clips["00500.mp4"].size is None
    assert clips["00500.mp4"].mtime is None
    assert clips["00500.mp4"].status == "new"  # the event's detail still built


def test_file_facts_cost_no_probe(client: TestClient, project: Path) -> None:
    event_dir = project / "2024" / "2024-07-04 - Barbecue"
    # Header-damaged bytes: ffprobe would fail on these, a stat does not care.
    (event_dir / "00500.mp4").write_bytes(b"not a container at all")

    event_id = quote("2024/2024-07-04 - Barbecue", safe="/")
    response = client.get(f"/api/v1/events/{event_id}")
    assert response.status_code == 200
    clips = _clips_by_identity(response.json())
    assert clips["00500.mp4"]["size"] == 22
    _utc_datetime(clips["00500.mp4"]["mtime"])


def test_events_list_carries_no_per_clip_facts(client: TestClient) -> None:
    body = client.get("/api/v1/events").json()
    barbecue = next(e for e in body if e["event_id"] == "2024/2024-07-04 - Barbecue")
    assert "chapters" not in barbecue
    assert barbecue["clip_count"] == 2


def _make_fresh(project: Path, event_dir: Path) -> None:
    """Render-adopt ``event_dir``: write the output file and a matching manifest.

    Leaves the event fresh under the project's *current* ``config.yaml``, so a
    later edit to the project look is the only thing that can turn it stale.
    """
    from auto_reel_ng.cli.adoption import persist, prepare_event
    from auto_reel_ng.config.project import load_project_config, resolve_look_defaults
    from auto_reel_ng.ffmpeg.runtime import FfmpegRuntime
    from auto_reel_ng.render import output_relpath
    from auto_reel_ng.staleness.fingerprint import compute_fingerprint, engine_identity
    from auto_reel_ng.staleness.manifest import write_manifest

    event = prepare_event(event_dir, order=DEFAULT_CLIP_ORDER, adopt=True)
    persist(event)
    runtime = FfmpegRuntime()
    fingerprint = compute_fingerprint(
        event.document,
        event_dir=event_dir,
        look_defaults=resolve_look_defaults(load_project_config(project)),
        ffmpeg_version=runtime.version,
    )
    output_path = default_output_dir(project) / output_relpath(event.document.metadata)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(b"already-rendered")
    write_manifest(
        event_dir,
        fingerprint,
        output=output_path.name,
        engine_identity=engine_identity(runtime.version),
    )


def test_config_look_edit_changes_the_verdict_on_the_next_request(
    client: TestClient, project: Path
) -> None:
    """The resolved look defaults are per-request, never cached across them (D-A3)."""
    event_dir = project / "2024" / "2024-07-04 - Barbecue"
    _make_fresh(project, event_dir)
    event_id = quote("2024/2024-07-04 - Barbecue", safe="/")

    first = client.get(f"/api/v1/events/{event_id}").json()
    assert first["staleness"] == {
        "stale": False,
        "reasons": [],
        "renamed_from": None,
        "output_name": None,
    }

    (project / "config.yaml").write_text("look:\n  title_seconds: 7\n", encoding="utf-8")

    second = client.get(f"/api/v1/events/{event_id}").json()
    assert second["staleness"]["stale"] is True
    assert second["staleness"]["reasons"] == ["defaults"]


def _by_id(body: list) -> dict:
    return {event["event_id"]: event for event in body}


def test_list_reports_fresh_stale_and_never_rendered_in_one_request(
    client: TestClient, project: Path
) -> None:
    """The list answers "what needs rendering?" without a per-event detail request."""
    fresh_dir = project / "2024" / "2024-07-04 - Barbecue"
    changed_dir = project / "2024" / "2024-06-21 - Midsommar i Dalarna Åäö"
    never_dir = project / "2024" / "2024-08-01 - Kräftskiva"

    _make_fresh(project, fresh_dir)
    _make_fresh(project, changed_dir)
    _touch(changed_dir / "00401.mp4")  # clips changed since that render
    _touch(never_dir / "00700.mp4")  # never rendered: no manifest at all

    events = _by_id(client.get("/api/v1/events").json())

    assert events["2024/2024-07-04 - Barbecue"]["staleness"] == {
        "stale": False,
        "reasons": [],
        "renamed_from": None,
        "output_name": None,
    }
    changed = events["2024/2024-06-21 - Midsommar i Dalarna Åäö"]["staleness"]
    assert changed["stale"] is True
    assert changed["reasons"] == ["clip_set"]
    never = events["2024/2024-08-01 - Kräftskiva"]["staleness"]
    assert never["stale"] is True
    assert never["reasons"] == ["no_manifest"]


def test_list_and_detail_agree_on_the_same_event(client: TestClient, project: Path) -> None:
    event_dir = project / "2024" / "2024-07-04 - Barbecue"
    _make_fresh(project, event_dir)
    _touch(event_dir / "00501.mp4")

    listed = _by_id(client.get("/api/v1/events").json())["2024/2024-07-04 - Barbecue"]
    event_id = quote("2024/2024-07-04 - Barbecue", safe="/")
    detail = client.get(f"/api/v1/events/{event_id}").json()

    assert listed["staleness"] == detail["staleness"]
    assert listed["staleness"]["stale"] is True
    assert listed["staleness"]["reasons"] == ["clip_set"]


def _edit_title(event_dir: Path, title: str) -> None:
    """Round-trip ``reel.yaml`` with a new title, as ``scripts/make_dev_library.py`` does."""
    from ruamel.yaml import YAML

    reel = event_dir / "reel.yaml"
    yaml = YAML()
    document = yaml.load(reel.read_text(encoding="utf-8"))
    document["metadata"]["title"] = title
    with reel.open("w", encoding="utf-8") as handle:
        yaml.dump(document, handle)


def _edit_location(event_dir: Path, location: str) -> None:
    from ruamel.yaml import YAML

    reel = event_dir / "reel.yaml"
    yaml = YAML()
    document = yaml.load(reel.read_text(encoding="utf-8"))
    document["metadata"]["location"] = location
    with reel.open("w", encoding="utf-8") as handle:
        yaml.dump(document, handle)


def _list_and_detail_staleness(client: TestClient, event_id: str) -> tuple[dict, dict]:
    listed = _by_id(client.get("/api/v1/events").json())[event_id]["staleness"]
    detail = client.get(f"/api/v1/events/{quote(event_id, safe='/')}").json()["staleness"]
    return listed, detail


def test_renamed_event_reads_output_renamed_on_list_and_detail(
    client: TestClient, project: Path
) -> None:
    """A retitle reads as a renamed movie while the old one is on disk, as missing once gone."""
    event_dir = project / "2024" / "2024-07-04 - Barbecue"
    _make_fresh(project, event_dir)
    old_movie = default_output_dir(project) / "2024" / "2024-07-04 - Barbecue.mp4"
    assert old_movie.read_bytes() == b"already-rendered"

    _edit_title(event_dir, "Grillkväll")

    renamed = {
        "stale": True,
        "reasons": ["editorial", "output_renamed"],
        "renamed_from": "2024-07-04 - Barbecue.mp4",
        "output_name": "2024-07-04 - Grillkväll.mp4",
    }
    assert _list_and_detail_staleness(client, "2024/2024-07-04 - Barbecue") == (renamed, renamed)
    assert old_movie.read_bytes() == b"already-rendered"  # a read never touches the old movie

    old_movie.unlink()

    missing = {
        "stale": True,
        "reasons": ["editorial", "output"],
        "renamed_from": None,
        "output_name": None,
    }
    assert _list_and_detail_staleness(client, "2024/2024-07-04 - Barbecue") == (missing, missing)


def test_deleted_movie_still_reads_output(client: TestClient, project: Path) -> None:
    event_dir = project / "2024" / "2024-07-04 - Barbecue"
    _make_fresh(project, event_dir)
    (default_output_dir(project) / "2024" / "2024-07-04 - Barbecue.mp4").unlink()

    missing = {"stale": True, "reasons": ["output"], "renamed_from": None, "output_name": None}
    assert _list_and_detail_staleness(client, "2024/2024-07-04 - Barbecue") == (missing, missing)


def test_a_location_only_change_names_both_movie_files(client: TestClient, project: Path) -> None:
    """The names are the gate's: the old file as rendered, the new one as the next render writes it."""
    event_dir = project / "2024" / "2024-06-21 - Midsommar i Dalarna Åäö"
    _make_fresh(project, event_dir)
    _edit_location(event_dir, "Leksand")

    listed, detail = _list_and_detail_staleness(client, "2024/2024-06-21 - Midsommar i Dalarna Åäö")

    assert listed == detail
    assert listed["reasons"] == ["editorial", "output_renamed"]
    assert listed["renamed_from"] == "2024-06-21 - Midsommar i Dalarna Åäö.mp4"
    assert listed["output_name"] == "2024-06-21 - Midsommar i Dalarna Åäö - Leksand.mp4"
    assert "/" not in listed["renamed_from"] and "/" not in listed["output_name"]


def test_a_verdict_without_output_renamed_names_no_file(client: TestClient, project: Path) -> None:
    """Both keys are present and null unless the reason is cited: a changed clip set names none."""
    event_dir = project / "2024" / "2024-07-04 - Barbecue"
    _make_fresh(project, event_dir)
    _touch(event_dir / "00501.mp4")

    listed, detail = _list_and_detail_staleness(client, "2024/2024-07-04 - Barbecue")

    expected = {
        "stale": True,
        "reasons": ["clip_set"],
        "renamed_from": None,
        "output_name": None,
    }
    assert listed == detail == expected


def test_a_completed_job_is_not_freshness(
    client: TestClient, project: Path, job_store, jobs_schema_engine
) -> None:
    """A job that finished before the clips changed describes a render, not freshness."""
    from auto_reel_ng.persistence.models import JobStatus

    event_dir = project / "2024" / "2024-07-04 - Barbecue"
    _make_fresh(project, event_dir)

    job_id = job_store.enqueue(str(project), "2024/2024-07-04 - Barbecue")
    job_store.claim_next("worker-1")
    job_store.transition(job_id, JobStatus.DONE)

    _touch(event_dir / "00501.mp4")  # a clip added after that job completed

    listed = _by_id(client.get("/api/v1/events").json())["2024/2024-07-04 - Barbecue"]
    assert listed["latest_job"]["status"] == "done"
    assert listed["staleness"]["stale"] is True
    assert listed["staleness"]["reasons"] == ["clip_set"]


_BARBECUE = "2024/2024-07-04 - Barbecue"
_JOB_TIMES = ("created_at", "started_at", "finished_at")


def _latest_job_reads(client: TestClient, job_id) -> tuple[dict, dict, dict]:
    """The event's ``latest_job`` from the list and from the detail, and the job's own detail."""
    listed = _by_id(client.get("/api/v1/events").json())[_BARBECUE]["latest_job"]
    detail = client.get(f"/api/v1/events/{quote(_BARBECUE, safe='/')}").json()["latest_job"]
    job = client.get(f"/api/v1/jobs/{job_id}").json()
    assert listed["id"] == detail["id"] == job["id"] == str(job_id)
    return listed, detail, job


@pytest.mark.parametrize("terminal", ["done", "failed"])
def test_an_ended_latest_job_reports_the_job_details_times(
    client: TestClient, project: Path, job_store, terminal: str
) -> None:
    """The latest job is a projection of the job's detail: the same time strings on both reads."""
    from auto_reel_ng.persistence.models import JobStatus

    job_id = job_store.enqueue(str(project), _BARBECUE)
    job_store.claim_next("worker-1")
    error = "probe failed" if terminal == "failed" else None
    job_store.transition(job_id, JobStatus(terminal), error=error)

    listed, detail, job = _latest_job_reads(client, job_id)
    assert job["started_at"] is not None and job["finished_at"] is not None
    for summary in (listed, detail):
        assert summary["status"] == terminal
        assert {key: summary[key] for key in _JOB_TIMES} == {key: job[key] for key in _JOB_TIMES}
    created, started, finished = (_utc_datetime(job[key]) for key in _JOB_TIMES)
    assert created <= started <= finished


def test_a_queued_latest_job_has_no_start_or_finish_time(
    client: TestClient, project: Path, job_store
) -> None:
    """Both keys are present and null until the store stamps them — never substituted."""
    job_id = job_store.enqueue(str(project), _BARBECUE)

    listed, detail, job = _latest_job_reads(client, job_id)
    for summary in (listed, detail):
        assert summary["status"] == "queued"
        assert summary["created_at"] == job["created_at"]
        assert "started_at" in summary and summary["started_at"] is None
        assert "finished_at" in summary and summary["finished_at"] is None


def test_a_job_cancelled_while_queued_has_a_finish_time_but_no_start_time(
    client: TestClient, project: Path, job_store
) -> None:
    job_id = job_store.enqueue(str(project), _BARBECUE)
    cancel = client.post(f"/api/v1/jobs/{job_id}/cancel")
    assert cancel.status_code == 200
    assert cancel.json()["outcome"] == "canceled-queued"

    listed, detail, job = _latest_job_reads(client, job_id)
    assert job["finished_at"] is not None
    for summary in (listed, detail):
        assert summary["status"] == "canceled"
        assert summary["started_at"] is None
        assert summary["finished_at"] == job["finished_at"]


def test_a_running_latest_job_loses_its_start_time_when_requeued(
    client: TestClient, project: Path, job_store
) -> None:
    """``requeue`` is what a graceful stop and the startup reconcile call (D-S5, D-S8)."""
    job_id = job_store.enqueue(str(project), _BARBECUE)
    job_store.claim_next("worker-1")

    listed, detail, job = _latest_job_reads(client, job_id)
    assert job["started_at"] is not None
    for summary in (listed, detail):
        assert summary["status"] == "running"
        assert summary["started_at"] == job["started_at"]
        assert summary["finished_at"] is None

    job_store.requeue(job_id)

    listed, detail, job = _latest_job_reads(client, job_id)
    for summary in (listed, detail):
        assert summary["status"] == "queued"
        assert summary["started_at"] is None
        assert summary["finished_at"] is None


def _assert_summary_matches_job(
    listed: dict, detail: dict, job: dict, *, requeues: int, cancel: bool
):
    for summary in (listed, detail):
        assert summary["requeue_count"] == job["requeue_count"] == requeues
        assert summary["cancel_requested"] is job["cancel_requested"] is cancel


def test_a_latest_job_never_requeued_or_cancelled_reports_the_defaults(
    client: TestClient, project: Path, job_store
) -> None:
    job_id = job_store.enqueue(str(project), _BARBECUE)

    listed, detail, job = _latest_job_reads(client, job_id)

    _assert_summary_matches_job(listed, detail, job, requeues=0, cancel=False)


def test_a_requeued_latest_job_reports_its_requeue_count(
    client: TestClient, project: Path, job_store
) -> None:
    """A requeue is invisible in the status alone (it is queued again): the count tells."""
    job_id = job_store.enqueue(str(project), _BARBECUE)
    job_store.claim_next("worker-1")
    job_store.requeue(job_id)

    listed, detail, job = _latest_job_reads(client, job_id)

    assert job["status"] == "queued" and job["started_at"] is None
    _assert_summary_matches_job(listed, detail, job, requeues=1, cancel=False)
    for summary in (listed, detail):
        assert summary["status"] == "queued"


def test_a_cancel_requested_while_running_is_visible_in_the_latest_job(
    client: TestClient, project: Path, job_store
) -> None:
    job_id = job_store.enqueue(str(project), _BARBECUE)
    job_store.claim_next("worker-1")
    assert client.post(f"/api/v1/jobs/{job_id}/cancel").status_code == 200

    listed, detail, job = _latest_job_reads(client, job_id)

    assert job["status"] == "running"
    _assert_summary_matches_job(listed, detail, job, requeues=0, cancel=True)

    job_store.requeue(job_id)  # a requeue leaves a pending cancel in place

    listed, detail, job = _latest_job_reads(client, job_id)
    _assert_summary_matches_job(listed, detail, job, requeues=1, cancel=True)


def test_serving_the_list_writes_nothing(client: TestClient, project: Path) -> None:
    """A GET creates no reel.yaml, no manifest, no output — and a malformed manifest
    is a stale verdict, not an error."""
    from auto_reel_ng.staleness.manifest import manifest_path

    broken_dir = project / "2024" / "2024-07-04 - Barbecue"
    broken_manifest = manifest_path(broken_dir)
    broken_manifest.parent.mkdir(parents=True, exist_ok=True)
    broken_manifest.write_text("{not json", encoding="utf-8")

    before = {p for p in project.rglob("*") if p.is_file()}
    response = client.get("/api/v1/events")
    assert response.status_code == 200
    after = {p for p in project.rglob("*") if p.is_file()}
    assert after == before

    events = _by_id(response.json())
    assert not any((project / event_id / "reel.yaml").exists() for event_id in events)
    assert not (default_output_dir(project)).exists()
    broken = events["2024/2024-07-04 - Barbecue"]["staleness"]
    assert broken["stale"] is True
    assert broken["reasons"] == ["no_manifest"]


def test_list_loads_the_project_config_once_and_never_hashes_clip_content(
    client: TestClient, project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Per-request work stays per-request, and a list request reads no clip bytes."""
    from auto_reel_ng.api import events_read

    _touch(project / "2024" / "2024-08-01 - Kräftskiva" / "00700.mp4")
    (project / "config.yaml").write_text("look:\n  title_seconds: 4\n", encoding="utf-8")

    config_loads: list[Path] = []
    real_load = events_read.load_project_config

    def counting_load(root: Path):
        config_loads.append(root)
        return real_load(root)

    hash_flags: list[bool] = []
    real_fingerprint = events_read.compute_fingerprint

    def recording_fingerprint(document, **kwargs):
        hash_flags.append(bool(kwargs.get("use_hash", False)))
        return real_fingerprint(document, **kwargs)

    monkeypatch.setattr(events_read, "load_project_config", counting_load)
    monkeypatch.setattr(events_read, "compute_fingerprint", recording_fingerprint)

    body = client.get("/api/v1/events").json()

    assert len(body) == 3  # several events, one shared resolved value
    assert config_loads == [project]
    assert hash_flags == [False, False, False]


# Names in filename order, with mtimes that run the other way (clip-order).
_BY_NAME = ("clip2.mp4", "clip10.mp4", "img_4863.mp4", "IMG_4933.mp4")


@pytest.mark.parametrize(
    ("config_text", "expected"),
    [
        ("sort:\n  method: filename\n", list(_BY_NAME)),
        (None, list(reversed(_BY_NAME))),
    ],
    ids=["filename", "default-datetime"],
)
def test_event_detail_lists_clips_in_configured_order(
    tmp_path: Path,
    postgres_container: str,
    jobs_schema_engine,
    config_text: str | None,
    expected: list[str],
) -> None:
    root = tmp_path / "proj"
    event_dir = root / "2024" / "2024-06-21 - A"
    for index, name in enumerate(_BY_NAME):
        _touch(event_dir / name)
        stamp = datetime(2024, 6, 21, 18 - index).timestamp()
        os.utime(event_dir / name, (stamp, stamp))
    if config_text is not None:
        (root / "config.yaml").write_text(config_text, encoding="utf-8")
    settings = resolve_api_settings(root, env={"DATABASE_URL": postgres_container})

    with TestClient(create_app(settings)) as test_client:
        response = test_client.get(f"/api/v1/events/{quote('2024/2024-06-21 - A', safe='/')}")

    assert response.status_code == 200
    (chapter,) = response.json()["chapters"]
    assert [clip["identity"] for clip in chapter["clips"]] == expected
    assert not (event_dir / "reel.yaml").exists()  # a GET never seeds to disk


# --------------------------------------------------------------------------- #
# The detail places clips reel.yaml does not list by the render's rule (D-12)
# --------------------------------------------------------------------------- #

_TVA_KAPITEL = "2024/2024-08-20 - Två kapitel - Tjörn"

# The `2024-08-20 - Två kapitel - Tjörn` reel.yaml the spec scenarios start from.
_TVA_KAPITEL_REEL = """version: 0
chapters:
- name: ''
  clips:
  - s1710001.mp4
- name: Kvällen
  clips:
  - Kvällen/s1710002.mp4
  - Kvällen/s1710003.mp4
"""

_DEFAULT_ONLY_REEL = "version: 0\nchapters:\n- name: ''\n  clips:\n  - s1710001.mp4\n"
_NO_CHAPTERS_REEL = "version: 0\nmetadata:\n  title: Utan Kapitel\n"


def _placed_event(project: Path, reel: str, clips: dict[str, int]) -> Path:
    """The Två kapitel event holding ``clips`` (identity -> mtime minute) and a literal reel.yaml."""
    event_dir = project / _TVA_KAPITEL
    for identity, minute in clips.items():
        _touch(event_dir / identity)
        stamp = datetime(2024, 8, 20, 18, minute).timestamp()
        os.utime(event_dir / identity, (stamp, stamp))
    (event_dir / "reel.yaml").write_text(reel, encoding="utf-8")
    return event_dir


def _detail_chapters(client: TestClient) -> list[tuple[str, list[tuple[str, str]]]]:
    response = client.get(f"/api/v1/events/{quote(_TVA_KAPITEL, safe='/')}")
    assert response.status_code == 200
    return [
        (chapter["name"], [(clip["identity"], clip["status"]) for clip in chapter["clips"]])
        for chapter in response.json()["chapters"]
    ]


def _listed(chapters: list[tuple[str, list[tuple[str, str]]]]) -> list[tuple[str, list[str]]]:
    """The chapters as reel.yaml would list them: ignored clips left out."""
    return [
        (name, [identity for identity, status in clips if status != "ignored"])
        for name, clips in chapters
    ]


def _document_chapters(event_dir: Path) -> list[tuple[str, list[str]]]:
    from auto_reel_ng.reel import load_document

    document = load_document(event_dir / "reel.yaml")
    return [
        (chapter.name, [ref.identity for ref in chapter.clips]) for chapter in document.chapters
    ]


def _adopt(event_dir: Path) -> None:
    """What a render's prepare step does to reel.yaml, without rendering."""
    from auto_reel_ng.cli.adoption import persist, prepare_event

    persist(prepare_event(event_dir, order=DEFAULT_CLIP_ORDER))


def test_detail_shows_a_new_clip_in_its_folders_chapter(client: TestClient, project: Path) -> None:
    clips = {"s1710001.mp4": 1, "Kvällen/s1710002.mp4": 2, "Kvällen/s1710003.mp4": 3}
    _placed_event(project, _TVA_KAPITEL_REEL, {**clips, "Kvällen/s1710004.mp4": 4})

    assert _detail_chapters(client) == [
        ("", [("s1710001.mp4", "active")]),
        (
            "Kvällen",
            [
                ("Kvällen/s1710002.mp4", "active"),
                ("Kvällen/s1710003.mp4", "active"),
                ("Kvällen/s1710004.mp4", "new"),
            ],
        ),
    ]


def test_detail_shows_a_folder_without_a_chapter_in_the_default_chapter(
    client: TestClient, project: Path
) -> None:
    clips = {"s1710001.mp4": 1, "Dag 2/s1710003.mp4": 2, "Dag 2/s1710002.mp4": 3}
    _placed_event(project, _DEFAULT_ONLY_REEL, clips)

    assert _detail_chapters(client) == [
        (
            "",
            [
                ("s1710001.mp4", "active"),
                ("Dag 2/s1710003.mp4", "new"),
                ("Dag 2/s1710002.mp4", "new"),
            ],
        ),
    ]


def test_detail_of_a_document_naming_no_chapters_is_its_folder_seed(
    client: TestClient, project: Path
) -> None:
    clips = {"s1710001.mp4": 1, "Kvällen/s1710003.mp4": 2, "Kvällen/s1710002.mp4": 3}
    event_dir = _placed_event(project, _NO_CHAPTERS_REEL, clips)

    first = _detail_chapters(client)
    _adopt(event_dir)
    second = _detail_chapters(client)

    assert first == [
        ("", [("s1710001.mp4", "new")]),
        ("Kvällen", [("Kvällen/s1710003.mp4", "new"), ("Kvällen/s1710002.mp4", "new")]),
    ]
    assert _document_chapters(event_dir) == _listed(first)
    assert second == [
        (name, [(identity, "active") for identity, _ in clips]) for name, clips in first
    ]


def test_detail_places_an_ignored_clip_like_a_new_one(client: TestClient, project: Path) -> None:
    reel = _DEFAULT_ONLY_REEL + "ignore:\n- Dag 2/s1710002.mp4\n"
    _placed_event(project, reel, {"s1710001.mp4": 1, "Dag 2/s1710002.mp4": 2})

    assert _detail_chapters(client) == [
        ("", [("s1710001.mp4", "active"), ("Dag 2/s1710002.mp4", "ignored")]),
    ]


def test_detail_chapters_are_the_chapters_render_adopts(client: TestClient, project: Path) -> None:
    reel = _TVA_KAPITEL_REEL + "ignore:\n- s1710009.mp4\n"
    clips = {
        "s1710001.mp4": 1,
        "Kvällen/s1710002.mp4": 2,
        "Kvällen/s1710003.mp4": 3,
        "Kvällen/s1710004.mp4": 4,  # NEW, in a folder whose chapter reel.yaml names
        "Dag 2/s1710005.mp4": 5,  # NEW, in a folder whose chapter it does not name
        "s1710009.mp4": 6,  # ignored; sorts between the two entering the default chapter
        "s1710006.mp4": 7,  # NEW, in the event folder
    }
    event_dir = _placed_event(project, reel, clips)

    first = _detail_chapters(client)
    _adopt(event_dir)
    second = _detail_chapters(client)

    assert _listed(first) == [
        ("", ["s1710001.mp4", "Dag 2/s1710005.mp4", "s1710006.mp4"]),
        ("Kvällen", ["Kvällen/s1710002.mp4", "Kvällen/s1710003.mp4", "Kvällen/s1710004.mp4"]),
    ]
    assert _listed(second) == _listed(first)
    assert _document_chapters(event_dir) == _listed(first)
    new_first = {identity for _, clips in first for identity, status in clips if status == "new"}
    second_status = {identity: status for _, clips in second for identity, status in clips}
    assert new_first == {"Kvällen/s1710004.mp4", "Dag 2/s1710005.mp4", "s1710006.mp4"}
    assert all(second_status[identity] == "active" for identity in new_first)
    assert second_status["s1710009.mp4"] == "ignored"


def test_detail_orders_entering_clips_by_the_current_config_sort(
    client: TestClient, project: Path
) -> None:
    # The service started with no config.yaml (datetime). A render re-reads config.yaml
    # for every job, so the detail must place entering clips by the sort rule on disk
    # now, re-read per request, not the one `serve` started with.
    from auto_reel_ng.cli.adoption import prepare_event
    from auto_reel_ng.config.project import load_project_config

    # Entering clips whose datetime order (b, c, a) is neither name order nor its reverse.
    clips = {"s1710001.mp4": 1, "a.mp4": 4, "Dag 2/b.mp4": 2, "c.mp4": 3}
    event_dir = _placed_event(project, _DEFAULT_ONLY_REEL, clips)
    config = project / "config.yaml"

    config.write_text("sort:\n  method: filename\n  reverse: true\n", encoding="utf-8")
    reversed_order = _listed(_detail_chapters(client))
    config.write_text("sort:\n  method: filename\n", encoding="utf-8")
    by_name = _listed(_detail_chapters(client))

    assert reversed_order == [("", ["s1710001.mp4", "c.mp4", "Dag 2/b.mp4", "a.mp4"])]
    assert by_name == [("", ["s1710001.mp4", "a.mp4", "Dag 2/b.mp4", "c.mp4"])]
    render_order = prepare_event(event_dir, order=load_project_config(project).sort).authored
    assert [
        (chapter.name, [ref.identity for ref in chapter.clips]) for chapter in render_order.chapters
    ] == by_name


# --- excluded clips and the missing clips that block a render ----------------------------

_BBQ = "2024/2024-07-04 - Barbecue"


def _write_reel(event_dir: Path, clips: list[str], *, props: str = "", ignore: str = "") -> None:
    listed = "".join(f"      - {identity}\n" for identity in clips)
    (event_dir / "reel.yaml").write_text(
        f"version: 0\nmetadata:\n  title: Barbecue\nchapters:\n  - name: ''\n    clips:\n{listed}"
        f"{props}{ignore}",
        encoding="utf-8",
    )


def _detail(client: TestClient, event_id: str = _BBQ) -> dict:
    response = client.get(f"/api/v1/events/{quote(event_id, safe='/')}")
    assert response.status_code == 200
    return response.json()


def _row(client: TestClient, event_id: str = _BBQ) -> dict:
    return _by_id(client.get("/api/v1/events").json())[event_id]


def test_an_excluded_clip_is_flagged_and_its_neighbours_are_not(
    client: TestClient, project: Path
) -> None:
    event_dir = project / "2024" / "2024-07-04 - Barbecue"
    for name in ("a.mp4", "b.mp4", "c.mp4"):
        _touch(event_dir / name)
    _write_reel(
        event_dir, ["a.mp4", "b.mp4", "c.mp4"], props="clips:\n  b.mp4:\n    exclude: true\n"
    )

    chapter = _detail(client)["chapters"][0]["clips"]

    assert [(c["identity"], c["status"], c["excluded"]) for c in chapter[:3]] == [
        ("a.mp4", "active", False),
        ("b.mp4", "active", True),
        ("c.mp4", "active", False),
    ]


def test_new_ignored_and_undocumented_clips_are_not_excluded(
    client: TestClient, project: Path
) -> None:
    event_dir = project / "2024" / "2024-07-04 - Barbecue"
    _touch(event_dir / "00501.mp4")  # NEW
    _write_reel(event_dir, ["00500.mp4"], ignore="ignore:\n- 00600.mp4\n")
    _touch(event_dir / "00600.mp4")
    clips = _clips_by_identity(_detail(client))
    assert clips["00501.mp4"]["status"] == "new"
    assert clips["00600.mp4"]["status"] == "ignored"
    assert [c["excluded"] for c in clips.values()] == [False] * len(clips)

    # An event without a reel.yaml at all.
    other = _detail(client, "2024/2024-06-21 - Midsommar i Dalarna Åäö")
    assert all(not c["excluded"] for c in _clips_by_identity(other).values())


def test_an_excluded_missing_clip_does_not_block(client: TestClient, project: Path) -> None:
    event_dir = project / "2024" / "2024-07-04 - Barbecue"
    _write_reel(
        event_dir,
        ["00500.mp4", "gone.mp4"],
        props="clips:\n  gone.mp4:\n    exclude: true\n",
    )

    body = _detail(client)

    assert body["missing"] == ["gone.mp4"]
    assert body["blocking_missing"] == []
    gone = _clips_by_identity(body)["gone.mp4"]
    assert (gone["status"], gone["excluded"]) == ("missing", True)


def test_only_the_non_excluded_missing_clip_blocks(client: TestClient, project: Path) -> None:
    event_dir = project / "2024" / "2024-07-04 - Barbecue"
    _write_reel(
        event_dir,
        ["00500.mp4", "gone.mp4", "gone2.mp4"],
        props="clips:\n  gone.mp4:\n    exclude: true\n",
    )

    body = _detail(client)

    assert body["missing"] == ["gone.mp4", "gone2.mp4"]
    assert body["blocking_missing"] == ["gone2.mp4"]
    assert not _clips_by_identity(body)["gone2.mp4"]["excluded"]


def test_an_event_without_exclusions_blocks_on_every_missing_clip(
    client: TestClient, project: Path
) -> None:
    _write_reel(project / "2024" / "2024-07-04 - Barbecue", ["00500.mp4", "gone.mp4"])
    body = _detail(client)
    assert body["blocking_missing"] == body["missing"] == ["gone.mp4"]


# --- played_missing_clips: the enqueue refusal's one definition of "played and missing" ----


def _played_missing(event_dir: Path) -> list[str]:
    from auto_reel_ng.api.events_read import played_missing_clips
    from auto_reel_ng.event.metadata import load_event_document

    document, _seeded = load_event_document(event_dir, order=DEFAULT_CLIP_ORDER)
    return played_missing_clips(event_dir, document)


def test_played_missing_clips_is_the_details_blocking_list(
    client: TestClient, project: Path
) -> None:
    event_dir = project / "2024" / "2024-07-04 - Barbecue"
    _write_reel(
        event_dir,
        ["00500.mp4", "gone.mp4", "gone2.mp4"],
        props="clips:\n  gone.mp4:\n    exclude: true\n",
    )

    body = _detail(client)

    assert _played_missing(event_dir) == ["gone2.mp4"]
    assert body["blocking_missing"] == _played_missing(event_dir)
    assert body["missing"] == ["gone.mp4", "gone2.mp4"]


def test_played_missing_clips_are_sorted_across_chapters(project: Path) -> None:
    event_dir = project / "2024" / "2024-07-04 - Barbecue"
    (event_dir / "reel.yaml").write_text(
        "version: 0\nmetadata:\n  title: Barbecue\nchapters:\n"
        "  - name: ''\n    clips:\n      - 00500.mp4\n      - gone-b.mp4\n"
        "  - name: Kväll\n    clips:\n      - Kväll/gone-a.mp4\n",
        encoding="utf-8",
    )

    assert _played_missing(event_dir) == ["Kväll/gone-a.mp4", "gone-b.mp4"]


def test_a_new_ignored_or_unlisted_event_has_no_played_missing_clip(project: Path) -> None:
    event_dir = project / "2024" / "2024-07-04 - Barbecue"
    _touch(event_dir / "00501.mp4")  # NEW
    _touch(event_dir / "00600.mp4")  # IGNORED
    _write_reel(event_dir, ["00500.mp4"], ignore="ignore:\n- 00600.mp4\n")
    assert _played_missing(event_dir) == []

    (event_dir / "reel.yaml").unlink()  # seeded from the listing: nothing can be absent
    assert _played_missing(event_dir) == []


def test_an_unlistable_folder_propagates_rather_than_reading_as_nothing_missing(
    project: Path,
) -> None:
    from auto_reel_ng.api.events_read import played_missing_clips
    from auto_reel_ng.event.metadata import load_event_document

    event_dir = project / "2024" / "2024-07-04 - Barbecue"
    document, _seeded = load_event_document(event_dir, order=DEFAULT_CLIP_ORDER)

    with pytest.raises(OSError):
        played_missing_clips(project / "2024" / "no such event", document)


def test_list_clip_count_is_the_pages_and_ignored_clips_are_counted_apart(
    client: TestClient, project: Path
) -> None:
    event_dir = project / "2024" / "2024-07-05 - Ignorerat"
    for name in ("00400.mp4", "00401.mp4", "00402.mp4"):
        _touch(event_dir / name)
    _write_reel(event_dir, ["00400.mp4", "00401.mp4"], ignore="ignore:\n- 00402.mp4\n")
    event_id = "2024/2024-07-05 - Ignorerat"

    row = _row(client, event_id)
    clips = list(_clips_by_identity(_detail(client, event_id)).values())

    assert (row["clip_count"], row["ignored_count"]) == (2, 1)
    assert len(clips) == 3
    assert sum(c["status"] != "ignored" for c in clips) == row["clip_count"]
    assert sum(c["status"] == "ignored" for c in clips) == row["ignored_count"]


def test_list_clip_count_includes_new_and_missing_clips(client: TestClient, project: Path) -> None:
    event_dir = project / "2024" / "2024-07-04 - Barbecue"
    _write_reel(event_dir, ["00500.mp4", "gone.mp4"])  # 00600 is NEW, gone is MISSING

    row = _row(client)

    assert (row["clip_count"], row["new_count"], row["missing_count"]) == (3, 1, 1)
    assert row["ignored_count"] == 0


def test_list_counts_blocking_missing_clips_apart(client: TestClient, project: Path) -> None:
    event_dir = project / "2024" / "2024-07-04 - Barbecue"
    _write_reel(
        event_dir,
        ["00500.mp4", "gone.mp4", "gone2.mp4"],
        props="clips:\n  gone.mp4:\n    exclude: true\n",
    )

    row = _row(client)

    assert (row["missing_count"], row["blocking_missing_count"]) == (2, 1)
    assert row["blocking_missing_count"] == len(_detail(client)["blocking_missing"])


def test_staleness_clip_set_ignores_whether_the_absent_clip_is_excluded(
    project: Path,
) -> None:
    from auto_reel_ng.config.project import load_project_config, resolve_look_defaults
    from auto_reel_ng.reel import load_document
    from auto_reel_ng.staleness.fingerprint import compute_fingerprint

    event_dir = project / "2024" / "2024-07-04 - Barbecue"
    defaults = resolve_look_defaults(load_project_config(project))

    def components() -> dict:
        document = load_document(event_dir / "reel.yaml")
        assert document is not None
        fingerprint = compute_fingerprint(
            document, event_dir=event_dir, look_defaults=defaults, ffmpeg_version="x"
        )
        return fingerprint.to_dict()["components"]  # type: ignore[return-value]

    _write_reel(event_dir, ["00500.mp4", "gone.mp4"])
    plain = components()
    _write_reel(
        event_dir, ["00500.mp4", "gone.mp4"], props="clips:\n  gone.mp4:\n    exclude: true\n"
    )
    excluded = components()

    moved = {key for key in plain if plain[key] != excluded[key]}
    assert moved == {"editorial"}


def test_reading_excluded_flags_probes_and_writes_nothing(
    client: TestClient, project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    marker = tmp_path / "ffprobe-ran"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake = fake_bin / "ffprobe"
    fake.write_text(f"#!/bin/sh\ntouch '{marker}'\nexit 1\n", encoding="utf-8")
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{fake_bin}{os.pathsep}{os.environ['PATH']}")
    event_dir = project / "2024" / "2024-07-04 - Barbecue"
    _write_reel(
        event_dir, ["00500.mp4", "gone.mp4"], props="clips:\n  gone.mp4:\n    exclude: true\n"
    )
    before = {p: p.read_bytes() for p in project.rglob("*") if p.is_file()}

    listed = client.get("/api/v1/events")
    detail = _detail(client)

    assert listed.status_code == 200
    assert detail["blocking_missing"] == []
    assert not marker.exists()
    assert {p: p.read_bytes() for p in project.rglob("*") if p.is_file()} == before
