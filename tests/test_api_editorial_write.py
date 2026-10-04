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
    renamed = {
        "stale": True,
        "reasons": ["editorial", "output_renamed"],
        "renamed_from": "2024-07-04 - Original Title - Somewhere.mp4",
        "output_name": "2024-07-04 - Changed - Somewhere.mp4",
    }
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


# --------------------------------------------------------------------------- #
# title-card-write-api: a chapter's card in the editorial body                #
# --------------------------------------------------------------------------- #

CARD_REEL_YAML = """\
version: 0
metadata:
  title: Original Title
  date: 2024-07-04
  location: Somewhere
# the whole movie
chapters:
  # first chapter
  - name: ""
    card:
      subtitle: Sommaren # keep me
    clips:
      - 00500.mp4
  - name: Dag 2
    clips:
      - clips/00600.mp4
"""

CARD_BODY = {
    "metadata": {"title": "Original Title", "date": "2024-07-04", "location": "Somewhere"},
    "chapters": [
        {"name": "", "clips": ["00500.mp4"]},
        {"name": "Dag 2", "clips": ["clips/00600.mp4"]},
    ],
}


def _with_card(card: object, *, name: str = "Dag 2", look: object = None) -> dict:
    body = {**CARD_BODY, "chapters": [dict(chapter) for chapter in CARD_BODY["chapters"]]}
    for chapter in body["chapters"]:
        if chapter["name"] == name:
            chapter["card"] = card
    if look is not None:
        body["look"] = look
    return body


def _reel_text(project: Path) -> str:
    return (_event_dir(project) / "reel.yaml").read_text(encoding="utf-8")


def _put(client: TestClient, body: dict):
    return client.put(f"/api/v1/events/{_event_id()}/reel", json=body)


def _assert_nothing_written(project: Path, before: str) -> None:
    assert _reel_text(project) == before
    assert sorted(path.name for path in _event_dir(project).iterdir() if path.is_file()) == [
        "00500.mp4",
        "reel.yaml",
    ]


def test_a_card_is_saved_echoed_and_read_back(client: TestClient, project: Path) -> None:
    card = {
        "title": "Dag två",
        "subtitle": "Stranden",
        "duration": 5,
        "background": "video",
        "font_family": "Inter",
    }
    response = _put(client, _with_card(card))
    assert response.status_code == 200, response.text
    echoed = response.json()["document"]["chapters"][1]
    assert echoed["name"] == "Dag 2"  # the title override does not rename the chapter
    assert echoed["card"]["title"] == "Dag två"
    assert echoed["card"]["duration"] == 5
    assert echoed["card"]["position"] is None  # unset fields are null
    assert echoed["card"]["text_color"] is None
    read = client.get(f"/api/v1/events/{_event_id()}/reel").json()["chapters"][1]
    assert read == echoed

    import yaml

    chapter = yaml.safe_load(_reel_text(project))["chapters"][1]
    assert chapter["clips"] == ["clips/00600.mp4"]
    assert chapter["card"] == {**card, "duration": 5}  # exactly those five keys
    assert list(chapter["card"]) == list(card)
    assert "card" not in yaml.safe_load(_reel_text(project))["chapters"][0]


def test_the_opening_card_lives_on_the_default_chapter_only(
    client: TestClient, project: Path
) -> None:
    response = _put(client, _with_card({"subtitle": "Sommaren 2024"}, name=""))
    assert response.status_code == 200, response.text
    import yaml

    chapters = yaml.safe_load(_reel_text(project))["chapters"]
    assert chapters[0]["card"] == {"subtitle": "Sommaren 2024"}
    assert "card" not in chapters[1]


def test_an_unmodified_get_written_back_is_a_byte_for_byte_no_op(
    client: TestClient, project: Path
) -> None:
    (_event_dir(project) / "reel.yaml").write_text(CARD_REEL_YAML, encoding="utf-8")
    body = client.get(f"/api/v1/events/{_event_id()}/reel").json()
    assert body["chapters"][0]["card"]["subtitle"] == "Sommaren"
    assert body["chapters"][1]["card"] is None
    stat_before = (_event_dir(project) / "reel.yaml").stat().st_mtime_ns
    assert _put(client, body).status_code == 200
    assert _reel_text(project) == CARD_REEL_YAML  # comments, including "# keep me", intact
    assert (_event_dir(project) / "reel.yaml").stat().st_mtime_ns == stat_before


def test_renaming_a_chapter_with_its_card_moves_the_card(client: TestClient, project: Path) -> None:
    body = _with_card({"title": "Dag två", "duration": 4})
    body["chapters"][1]["name"] = "Dag två"
    response = _put(client, body)
    assert response.status_code == 200, response.text
    import yaml

    chapters = yaml.safe_load(_reel_text(project))["chapters"]
    assert [chapter["name"] for chapter in chapters] == ["", "Dag två"]
    assert chapters[1]["card"] == {"title": "Dag två", "duration": 4}


def test_an_empty_card_removes_it_and_a_missing_card_keeps_it(
    client: TestClient, project: Path
) -> None:
    (_event_dir(project) / "reel.yaml").write_text(CARD_REEL_YAML, encoding="utf-8")
    kept = _put(client, CARD_BODY)  # no "card" key at all on either chapter
    assert kept.status_code == 200
    assert "subtitle: Sommaren # keep me" in _reel_text(project)
    removed = _put(client, _with_card({}, name=""))
    assert removed.status_code == 200
    assert "subtitle: Sommaren" not in _reel_text(project)
    assert removed.json()["document"]["chapters"][0]["card"] is None
    nulls = _put(client, _with_card({"title": None, "duration": None}))
    assert nulls.status_code == 200
    assert "card" not in _reel_text(project).split("Dag 2")[1]


@pytest.mark.parametrize(
    ("card", "needles"),
    [
        ({"duration": -3}, ["Dag 2", "card.duration"]),
        ({"font_family": "Comic Sans"}, ["Dag 2", "card.font_family", "Comic Sans"]),
        ({"background": "gradient"}, ["Dag 2", "card.background"]),
        ({"position": "left"}, ["Dag 2", "card.position"]),
        ({"text_color": "#fff"}, ["Dag 2", "card.text_color"]),
        ({"title_font_size": 2}, ["Dag 2", "card.title_font_size"]),
        ({"title": "  "}, ["Dag 2", "card.title"]),
    ],
)
def test_an_invalid_card_is_a_400_naming_the_chapter_and_field(
    client: TestClient, project: Path, card: dict, needles: list
) -> None:
    before = _reel_text(project)
    response = _put(client, _with_card(card))
    assert response.status_code == 400, response.text
    for needle in needles:
        assert needle in response.json()["detail"]
    _assert_nothing_written(project, before)


def test_an_unknown_card_key_is_rejected_naming_it(client: TestClient, project: Path) -> None:
    before = _reel_text(project)
    response = _put(client, _with_card({"colour": "#fff"}))
    assert response.status_code == 422
    assert "colour" in response.text
    _assert_nothing_written(project, before)


@pytest.mark.parametrize("card", [{"duration": True}, {"duration": "5"}, {"title_font_size": 1.5}])
def test_card_values_of_the_wrong_json_type_are_rejected(
    client: TestClient, project: Path, card: dict
) -> None:
    before = _reel_text(project)
    assert _put(client, _with_card(card)).status_code == 422
    _assert_nothing_written(project, before)


def test_an_invalid_event_wide_card_style_is_refused_naming_the_field(
    client: TestClient, project: Path
) -> None:
    before = _reel_text(project)
    response = _put(client, _with_card(None, look={"title_card": {"title_font_size": "big"}}))
    assert response.status_code == 400
    assert "look.title_card.title_font_size" in response.json()["detail"]
    _assert_nothing_written(project, before)
    ok = _put(client, _with_card(None, look={"title_card": {"title_font_size": 80}}))
    assert ok.status_code == 200


@pytest.mark.parametrize(
    ("style", "field"),
    [
        ({"titel_font_size": 80}, "titel_font_size"),
        ({"duration": 900}, "duration"),
        ({"title_font_size": 4000}, "title_font_size"),
        ({"subtitle_font_size": 2}, "subtitle_font_size"),
    ],
)
def test_a_lax_event_wide_style_is_a_400_naming_the_field(
    client: TestClient, project: Path, style: dict, field: str
) -> None:
    before = _reel_text(project)
    response = _put(client, _with_card(None, look={"title_card": style}))
    assert response.status_code == 400, response.text
    assert f"look.title_card.{field}" in response.json()["detail"]
    _assert_nothing_written(project, before)


def test_a_long_title_is_accepted_by_the_write(client: TestClient, project: Path) -> None:
    assert _put(client, _with_card({"title": "x" * 300})).status_code == 200


def test_every_registry_family_is_accepted_as_a_card_font(
    client: TestClient, project: Path
) -> None:
    from auto_reel_ng.render.title import registered_families

    for family in registered_families():
        assert _put(client, _with_card({"font_family": family})).status_code == 200, family


def test_a_detail_shaped_body_is_still_rejected(client: TestClient, project: Path) -> None:
    detail = client.get(f"/api/v1/events/{_event_id()}").json()
    assert _put(client, detail).status_code == 422


def test_a_card_edit_on_a_fresh_event_is_stale_through_the_editorial_component(
    client: TestClient, project: Path
) -> None:
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
    settings = resolve_api_settings(project, env={})
    output = default_output_dir(settings.project_root) / output_relpath(event.document.metadata)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(b"already-rendered")
    write_manifest(
        event_dir,
        fingerprint,
        output=output.name,
        engine_identity=engine_identity(runtime.version),
    )
    assert client.get(f"/api/v1/events/{_event_id()}").json()["staleness"]["stale"] is False

    response = _put(client, {**_body_of(client), "chapters": _with_title(client)})
    assert response.status_code == 200, response.text
    staleness = response.json()["staleness"]
    assert staleness["stale"] is True
    assert any("editorial" in reason for reason in staleness["reasons"]), staleness
    assert client.get("/api/v1/jobs").json() == []


def _body_of(client: TestClient) -> dict:
    body = client.get(f"/api/v1/events/{_event_id()}/reel").json()
    return {key: value for key, value in body.items() if key != "chapters"}


def _with_title(client: TestClient) -> list:
    chapters = client.get(f"/api/v1/events/{_event_id()}/reel").json()["chapters"]
    chapters[0]["card"] = {"title": "A new heading"}
    return chapters
