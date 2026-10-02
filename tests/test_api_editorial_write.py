"""Tests for the editorial write route (tasks 2.2-2.4): PUT /api/v1/events/{id}/reel."""

from __future__ import annotations

import os
import stat
from pathlib import Path
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from auto_reel_ng.api.app import create_app
from auto_reel_ng.api.settings import resolve_api_settings
from auto_reel_ng.config import default_output_dir
from auto_reel_ng.event import DEFAULT_CLIP_ORDER

pytestmark = pytest.mark.requires_db


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")


REEL_YAML = """\
version: 0
metadata:
  title: Original Title
  date: 2024-07-04
  location: Somewhere
chapters:
  - name: ""
    clips:
      - 00500.mp4
      - clips/00600.mp4
"""

UNICODE_REEL_YAML = """\
version: 0
metadata:
  title: Midsommar
chapters:
  - name: ""
    clips:
      - 00400.mp4
"""

BASE_BODY = {
    "metadata": {"title": "Original Title", "date": "2024-07-04", "location": "Somewhere"},
    "chapters": [{"name": "", "clips": ["00500.mp4", "clips/00600.mp4"]}],
}


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"

    event_dir = root / "2024" / "2024-07-04 - Barbecue"
    _touch(event_dir / "00500.mp4")
    _touch(event_dir / "clips" / "00600.mp4")
    (event_dir / "reel.yaml").write_text(REEL_YAML, encoding="utf-8")

    unicode_dir = root / "2024" / "2024-06-21 - Midsommar i Dalarna Åäö"
    _touch(unicode_dir / "00400.mp4")
    (unicode_dir / "reel.yaml").write_text(UNICODE_REEL_YAML, encoding="utf-8")

    return root


@pytest.fixture
def client(project: Path, postgres_container: str, jobs_schema_engine):
    settings = resolve_api_settings(project, env={"DATABASE_URL": postgres_container})
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client


def _event_id() -> str:
    return quote("2024/2024-07-04 - Barbecue", safe="/")


def _event_dir(project: Path) -> Path:
    return project / "2024" / "2024-07-04 - Barbecue"


def test_save_persists_and_echoes(client: TestClient, project: Path) -> None:
    body = {
        **BASE_BODY,
        "metadata": {**BASE_BODY["metadata"], "title": "Renamed Barbecue"},
        "chapters": [{"name": "", "clips": ["clips/00600.mp4", "00500.mp4"]}],
    }
    response = client.put(f"/api/v1/events/{_event_id()}/reel", json=body)
    assert response.status_code == 200
    result = response.json()
    assert result["document"]["metadata"]["title"] == "Renamed Barbecue"
    assert result["document"]["chapters"][0]["clips"] == ["clips/00600.mp4", "00500.mp4"]
    assert result["staleness"]["stale"] is True  # no manifest exists yet

    text = (_event_dir(project) / "reel.yaml").read_text(encoding="utf-8")
    assert "Renamed Barbecue" in text


def test_save_makes_a_previously_fresh_event_stale(client: TestClient, project: Path) -> None:
    from auto_reel_ng.cli.adoption import persist, prepare_event
    from auto_reel_ng.config.project import load_project_config, resolve_look_defaults
    from auto_reel_ng.ffmpeg.runtime import FfmpegRuntime
    from auto_reel_ng.render import output_relpath
    from auto_reel_ng.staleness.fingerprint import compute_fingerprint, engine_identity
    from auto_reel_ng.staleness.manifest import write_manifest

    event_dir = _event_dir(project)
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

    fresh_check = client.get(f"/api/v1/events/{_event_id()}")
    assert fresh_check.json()["staleness"]["stale"] is False

    body = {**BASE_BODY, "metadata": {**BASE_BODY["metadata"], "title": "Changed"}}
    response = client.put(f"/api/v1/events/{_event_id()}/reel", json=body)
    assert response.status_code == 200
    # The title feeds the movie's name: the old movie is on disk under the old one.
    renamed = {"stale": True, "reasons": ["editorial", "output_renamed"]}
    assert response.json()["staleness"] == renamed

    follow_up = client.get(f"/api/v1/events/{_event_id()}")
    assert follow_up.json()["staleness"] == renamed

    assert output_path.read_bytes() == b"already-rendered"  # the write never touches the movie
    assert client.get("/api/v1/jobs").json() == []  # the write never enqueues


def test_invalid_state_is_rejected_and_file_unchanged(client: TestClient, project: Path) -> None:
    original = (_event_dir(project) / "reel.yaml").read_text(encoding="utf-8")
    body = {
        **BASE_BODY,
        # Dangling: a clip properties entry with no chapter reference at all.
        "clips": {"nowhere.mp4": {"exclude": False}},
    }
    response = client.put(f"/api/v1/events/{_event_id()}/reel", json=body)
    assert response.status_code == 400
    assert "dangling" in response.json()["detail"]
    assert (_event_dir(project) / "reel.yaml").read_text(encoding="utf-8") == original


def test_unknown_event_yields_404(client: TestClient) -> None:
    response = client.put("/api/v1/events/2024/does-not-exist/reel", json=BASE_BODY)
    assert response.status_code == 404
    assert "title" in response.json()


def test_unknown_field_is_rejected_structurally(client: TestClient) -> None:
    response = client.put(f"/api/v1/events/{_event_id()}/reel", json={**BASE_BODY, "bogus": True})
    assert response.status_code == 422


def test_url_round_trip_with_spaces_and_unicode(client: TestClient) -> None:
    event_id = quote("2024/2024-06-21 - Midsommar i Dalarna Åäö", safe="/")
    body = {
        "metadata": {"title": "Midsommar Reviderad"},
        "chapters": [{"name": "", "clips": ["00400.mp4"]}],
    }
    response = client.put(f"/api/v1/events/{event_id}/reel", json=body)
    assert response.status_code == 200
    assert response.json()["document"]["metadata"]["title"] == "Midsommar Reviderad"


def test_put_of_echoed_document_is_a_noop(client: TestClient, project: Path) -> None:
    first = client.put(f"/api/v1/events/{_event_id()}/reel", json=BASE_BODY)
    assert first.status_code == 200
    echoed = first.json()["document"]
    text_after_first = (_event_dir(project) / "reel.yaml").read_text(encoding="utf-8")

    second = client.put(f"/api/v1/events/{_event_id()}/reel", json=echoed)
    assert second.status_code == 200
    assert second.json()["document"] == echoed
    assert (_event_dir(project) / "reel.yaml").read_text(encoding="utf-8") == text_after_first


def test_write_etag_equals_the_tag_a_read_would_give(client: TestClient) -> None:
    body = {**BASE_BODY, "metadata": {**BASE_BODY["metadata"], "title": "Tagged Barbecue"}}
    written = client.put(f"/api/v1/events/{_event_id()}/reel", json=body)
    assert written.status_code == 200
    assert written.headers["ETag"]

    read = client.get(f"/api/v1/events/{_event_id()}/reel")
    assert read.headers["ETag"] == written.headers["ETag"]


def test_unmodified_save_returns_the_tag_it_was_given(client: TestClient) -> None:
    read = client.get(f"/api/v1/events/{_event_id()}/reel")
    etag = read.headers["ETag"]

    written = client.put(
        f"/api/v1/events/{_event_id()}/reel",
        json=read.json(),
        headers={"If-Match": etag},
    )
    assert written.status_code == 200
    assert written.headers["ETag"] == etag


def test_consecutive_conditional_writes_need_no_intervening_read(
    client: TestClient, project: Path
) -> None:
    read = client.get(f"/api/v1/events/{_event_id()}/reel")
    first = client.put(
        f"/api/v1/events/{_event_id()}/reel",
        json={**BASE_BODY, "chapters": [{"name": "", "clips": ["clips/00600.mp4", "00500.mp4"]}]},
        headers={"If-Match": read.headers["ETag"]},
    )
    assert first.status_code == 200

    # The tag the first write handed back is the only precondition used here: no
    # GET of /reel happens between the two writes.
    second = client.put(
        f"/api/v1/events/{_event_id()}/reel",
        json={**BASE_BODY, "chapters": [{"name": "", "clips": ["00500.mp4", "clips/00600.mp4"]}]},
        headers={"If-Match": first.headers["ETag"]},
    )
    assert second.status_code == 200
    assert second.json()["document"]["chapters"][0]["clips"] == ["00500.mp4", "clips/00600.mp4"]
    assert "00500.mp4" in (_event_dir(project) / "reel.yaml").read_text(encoding="utf-8")


def test_refused_write_hands_back_no_precondition(client: TestClient, project: Path) -> None:
    read = client.get(f"/api/v1/events/{_event_id()}/reel")
    stale_etag = read.headers["ETag"]

    # Another writer changes the editorial state under the client.
    client.put(
        f"/api/v1/events/{_event_id()}/reel",
        json={**BASE_BODY, "metadata": {**BASE_BODY["metadata"], "title": "Someone Else"}},
    )
    text_before = (_event_dir(project) / "reel.yaml").read_text(encoding="utf-8")

    refused = client.put(
        f"/api/v1/events/{_event_id()}/reel",
        json={**BASE_BODY, "metadata": {**BASE_BODY["metadata"], "title": "Lost Update"}},
        headers={"If-Match": stale_etag},
    )
    assert refused.status_code == 412
    assert "ETag" not in refused.headers
    assert (_event_dir(project) / "reel.yaml").read_text(encoding="utf-8") == text_before


# --- api-event-lookup-scope: If-Match across header lines --------------------


def _retitled(title: str) -> dict:
    return {**BASE_BODY, "metadata": {**BASE_BODY["metadata"], "title": title}}


def test_a_matching_tag_on_a_later_if_match_line_writes(client: TestClient, project: Path) -> None:
    etag = client.get(f"/api/v1/events/{_event_id()}/reel").headers["ETag"]

    response = client.put(
        f"/api/v1/events/{_event_id()}/reel",
        json=_retitled("Two Lines"),
        headers=[("If-Match", '"stale"'), ("If-Match", etag)],
    )

    assert response.status_code == 200
    assert "Two Lines" in (_event_dir(project) / "reel.yaml").read_text(encoding="utf-8")


def test_a_matching_tag_on_an_earlier_if_match_line_writes(client: TestClient) -> None:
    etag = client.get(f"/api/v1/events/{_event_id()}/reel").headers["ETag"]

    response = client.put(
        f"/api/v1/events/{_event_id()}/reel",
        json=_retitled("First Line"),
        headers=[("If-Match", etag), ("If-Match", '"stale"')],
    )

    assert response.status_code == 200


def test_repeated_lines_equal_the_same_tags_comma_joined(client: TestClient) -> None:
    etag = client.get(f"/api/v1/events/{_event_id()}/reel").headers["ETag"]

    joined = client.put(
        f"/api/v1/events/{_event_id()}/reel",
        json=BASE_BODY,
        headers={"If-Match": f'"stale", {etag}'},
    )
    lines = client.put(
        f"/api/v1/events/{_event_id()}/reel",
        json=BASE_BODY,
        headers=[("If-Match", '"stale"'), ("If-Match", etag)],
    )

    assert joined.status_code == lines.status_code == 200


def test_no_matching_if_match_line_is_refused_and_writes_nothing(
    client: TestClient, project: Path
) -> None:
    text_before = (_event_dir(project) / "reel.yaml").read_text(encoding="utf-8")

    response = client.put(
        f"/api/v1/events/{_event_id()}/reel",
        json=_retitled("Never Written"),
        headers=[("If-Match", '"stale"'), ("If-Match", '"other"')],
    )

    assert response.status_code == 412
    assert "ETag" not in response.headers
    assert (_event_dir(project) / "reel.yaml").read_text(encoding="utf-8") == text_before


def test_an_empty_if_match_is_still_a_precondition(client: TestClient, project: Path) -> None:
    text_before = (_event_dir(project) / "reel.yaml").read_text(encoding="utf-8")

    response = client.put(
        f"/api/v1/events/{_event_id()}/reel",
        json=_retitled("Never Written"),
        headers={"If-Match": ""},
    )

    assert response.status_code == 412
    assert (_event_dir(project) / "reel.yaml").read_text(encoding="utf-8") == text_before


# --- editorial-client-contract 2.2: status by cause --------------------------


def test_write_onto_a_broken_file_is_502_not_400(client: TestClient, project: Path) -> None:
    """Without If-Match too: the disk is at fault, and the kind is the reads' kind."""
    reel_path = _event_dir(project) / "reel.yaml"
    reel_path.write_text("version: 0\nchapters: not-a-list\n", encoding="utf-8")
    before = reel_path.read_bytes()

    response = client.put(f"/api/v1/events/{_event_id()}/reel", json=BASE_BODY)

    assert response.status_code == 502
    body = response.json()
    assert body["failure"] == "unparseable_reel_yaml"
    assert body["event_id"] == "2024/2024-07-04 - Barbecue"
    assert reel_path.read_bytes() == before


def test_clearing_the_only_date_is_400_unusable_metadata(client: TestClient, project: Path) -> None:
    event_dir = project / "2024" / "Blandat"
    _touch(event_dir / "00100.mp4")
    reel_path = event_dir / "reel.yaml"
    reel_path.write_text(
        "version: 0\nmetadata:\n  title: Blandat\n  date: 2024-05-01\n", encoding="utf-8"
    )
    before = reel_path.read_bytes()

    response = client.put(
        f"/api/v1/events/{quote('2024/Blandat', safe='/')}/reel",
        json={"metadata": {"title": "Blandat"}},
    )

    assert response.status_code == 400
    body = response.json()
    assert body["failure"] == "unusable_metadata"
    assert "no date" in body["detail"]
    assert reel_path.read_bytes() == before


def test_save_the_filesystem_refuses_is_502_naming_the_error(
    client: TestClient, project: Path
) -> None:
    if os.geteuid() == 0:
        pytest.skip("root ignores directory permissions")
    event_dir = _event_dir(project)
    before = (event_dir / "reel.yaml").read_bytes()
    body = {**BASE_BODY, "metadata": {**BASE_BODY["metadata"], "title": "Read Only"}}
    mode = event_dir.stat().st_mode
    event_dir.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        response = client.put(f"/api/v1/events/{_event_id()}/reel", json=body)
    finally:
        event_dir.chmod(mode)

    assert response.status_code == 502
    problem = response.json()
    assert "Permission denied" in problem["detail"]
    assert "failure" not in problem
    assert (event_dir / "reel.yaml").read_bytes() == before
    assert list(event_dir.glob(".reel.yaml.*.tmp")) == []


def test_omitting_ignore_clears_it_and_writing_back_the_read_preserves_it(
    client: TestClient, project: Path
) -> None:
    reel_path = _event_dir(project) / "reel.yaml"
    reel_path.write_text(REEL_YAML + "ignore:\n  - clips/00700.mp4\n", encoding="utf-8")
    read = client.get(f"/api/v1/events/{_event_id()}/reel").json()

    kept = {**read, "metadata": {**read["metadata"], "title": "Kept"}}
    response = client.put(f"/api/v1/events/{_event_id()}/reel", json=kept)
    assert response.status_code == 200
    assert response.json()["document"]["ignore"] == ["clips/00700.mp4"]

    cleared = {**BASE_BODY, "metadata": {**BASE_BODY["metadata"], "title": "Cleared"}}
    response = client.put(f"/api/v1/events/{_event_id()}/reel", json=cleared)
    assert response.status_code == 200
    assert response.json()["document"]["ignore"] == []
    assert "ignore" not in reel_path.read_text(encoding="utf-8")


# --- editorial-chapter-roundtrip 3.1: list-entry comments survive an unmodified save ---

#: The dev library's ``2024-09-01 - Sommarlov`` reel.yaml, byte for byte
#: (``scripts/make_dev_library.py``); ``borttagen.mp4`` is MISSING on disk.
SOMMARLOV_REEL_YAML = """\
version: 0
metadata:
  title: Sommarlov
  date: 2024-09-01
chapters:
  - name: ''
    clips:
      - s1710002.mp4
      - s1710004.mp4
      - borttagen.mp4  # MISSING
"""


def test_unmodified_save_keeps_a_comment_on_a_clip_entry(client: TestClient, project: Path) -> None:
    event_dir = project / "2024" / "2024-09-01 - Sommarlov"
    _touch(event_dir / "s1710002.mp4")
    _touch(event_dir / "s1710004.mp4")
    reel_path = event_dir / "reel.yaml"
    reel_path.write_text(SOMMARLOV_REEL_YAML, encoding="utf-8")
    event_id = quote("2024/2024-09-01 - Sommarlov", safe="/")

    read = client.get(f"/api/v1/events/{event_id}/reel")
    assert read.status_code == 200
    written = client.put(
        f"/api/v1/events/{event_id}/reel",
        json=read.json(),
        headers={"If-Match": read.headers["ETag"]},
    )

    assert written.status_code == 200
    assert reel_path.read_bytes() == SOMMARLOV_REEL_YAML.encode("utf-8")
    assert written.headers["ETag"] == read.headers["ETag"]


# --- editorial-chapter-comments 5.1: a chapter rename keeps its comments ---

RECEPTION_REEL_YAML = """\
version: 0
metadata:
  title: Party
  date: 2024-09-01
chapters:
  - name: Reception   # the first chapter
    clips:
      - a.mp4   # keep me: the best shot
      # before b
      - b.mp4
  # --- the dinner ---
  - name: Dinner
    clips: [c.mp4]   # dinner clip
"""


def test_renaming_a_chapter_changes_only_its_name_line(client: TestClient, project: Path) -> None:
    event_dir = project / "2024" / "2024-09-01 - Party"
    for clip in ("a.mp4", "b.mp4", "c.mp4"):
        _touch(event_dir / clip)
    reel_path = event_dir / "reel.yaml"
    reel_path.write_text(RECEPTION_REEL_YAML, encoding="utf-8")
    event_id = quote("2024/2024-09-01 - Party", safe="/")

    read = client.get(f"/api/v1/events/{event_id}/reel")
    assert read.status_code == 200
    body = read.json()
    body["chapters"][0]["name"] = "Welcome"
    written = client.put(
        f"/api/v1/events/{event_id}/reel", json=body, headers={"If-Match": read.headers["ETag"]}
    )

    assert written.status_code == 200
    chapter = written.json()["document"]["chapters"][0]
    assert (chapter["name"], chapter["clips"]) == ("Welcome", ["a.mp4", "b.mp4"])
    assert reel_path.read_text(encoding="utf-8") == RECEPTION_REEL_YAML.replace(
        "name: Reception ", "name: Welcome   "
    )


# --- editorial-trims-and-noop 1.2: a PUT of the document just read changes nothing on disk ---

FOREIGN_REEL_YAML = """\
version: 0
metadata:
    title: Midsommar   # keep
    date: 2024-06-21
chapters:
-   name: ''
    clips:
    - 00400.mp4
"""


def test_put_of_the_document_just_read_leaves_a_foreign_indented_file_untouched(
    client: TestClient, project: Path
) -> None:
    event_dir = project / "2024" / "2024-06-21 - Midsommar i Dalarna Åäö"
    reel_path = event_dir / "reel.yaml"
    reel_path.write_text(FOREIGN_REEL_YAML, encoding="utf-8")
    event_id = quote("2024/2024-06-21 - Midsommar i Dalarna Åäö", safe="/")

    read = client.get(f"/api/v1/events/{event_id}/reel")
    assert read.status_code == 200
    written = client.put(
        f"/api/v1/events/{event_id}/reel",
        json=read.json(),
        headers={"If-Match": read.headers["ETag"]},
    )

    assert written.status_code == 200
    assert written.json()["document"] == read.json()
    assert written.headers["ETag"] == read.headers["ETag"]
    assert reel_path.read_text(encoding="utf-8") == FOREIGN_REEL_YAML


TRIMMED_REEL_YAML = """\
version: 0
metadata:
  title: Midsommar
chapters:
  - name: ""
    clips:
      - 00400.mp4
clips:
  00400.mp4:
    trims:
      - {in: 0, out: 3.2, reason: black}   # black start
      - {in: 10, out: 12}   # shake
"""


def test_changing_one_cut_over_the_api_leaves_the_other_cuts_as_authored(
    client: TestClient, project: Path
) -> None:
    reel_path = project / "2024" / "2024-06-21 - Midsommar i Dalarna Åäö" / "reel.yaml"
    reel_path.write_text(TRIMMED_REEL_YAML, encoding="utf-8")
    event_id = quote("2024/2024-06-21 - Midsommar i Dalarna Åäö", safe="/")

    read = client.get(f"/api/v1/events/{event_id}/reel")
    assert read.status_code == 200
    body = read.json()
    body["clips"]["00400.mp4"]["trims"][1]["out"] = 13  # JSON: the other numbers arrive as floats
    written = client.put(
        f"/api/v1/events/{event_id}/reel", json=body, headers={"If-Match": read.headers["ETag"]}
    )

    assert written.status_code == 200
    lines = reel_path.read_text(encoding="utf-8").splitlines()
    assert "      - {in: 0, out: 3.2, reason: black}   # black start" in lines
    assert any(
        line.startswith("      - {in: 10, out: 13") and line.endswith("# shake") for line in lines
    )


UNEMITTABLE_REEL_YAML = """\
version: 0
metadata:
  title: Midsommar
chapters:
  - name: ""
    clips:
      - 00400.mp4
clips:
  00400.mp4:
    trims:
      # header
      - {in: 10, out: 13}   # eol
      - in: 0
        out: 3
"""


def test_a_file_ruamel_cannot_write_back_is_400_and_stays_as_authored(
    client: TestClient, project: Path
) -> None:
    """A header, a flow span with a comment, a block span: ruamel writes that unreadably."""
    reel_path = project / "2024" / "2024-06-21 - Midsommar i Dalarna Åäö" / "reel.yaml"
    reel_path.write_text(UNEMITTABLE_REEL_YAML, encoding="utf-8")
    event_id = quote("2024/2024-06-21 - Midsommar i Dalarna Åäö", safe="/")
    read = client.get(f"/api/v1/events/{event_id}/reel")
    assert read.status_code == 200
    body = read.json()
    body["metadata"]["title"] = "Midsommar 2"

    response = client.put(f"/api/v1/events/{event_id}/reel", json=body)

    assert response.status_code == 400
    assert "cannot be re-written" in response.json()["detail"]
    assert reel_path.read_text(encoding="utf-8") == UNEMITTABLE_REEL_YAML
