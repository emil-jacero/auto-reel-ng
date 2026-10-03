"""``EventDetailOut.movie`` (api-service, "The event detail reports the rendered movie's version
and chapter times").

The facts are read from the render manifest and the filesystem only, so the manifests here are
written with the engine's own ``write_manifest`` (and ``adopt-renders``) and the movies are stub
files; one ``has_ffmpeg`` test renders real clips through the engine. The library is the media
tests' (rendered, retitled, unrendered, case-colliding, climbing-title events), so the agreement
with ``GET …/movie`` is checked on the same events the route's tests use.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient
from test_api_media import (  # pylint: disable=unused-import
    GRILLNING,
    GRILLNING_OLD_MOVIE,
    KALAS,
    KALAS_MOVIE,
    SOMMARLOV,
    TJORN,
    UTBRYTNING,
    _snapshot,
    _write,
    movies,
    output_dir,
    project,
    utbrytning,
)

from auto_reel_ng.api import movie_read
from auto_reel_ng.api.app import create_app
from auto_reel_ng.api.settings import ApiSettings, resolve_api_settings
from auto_reel_ng.cli.main import main
from auto_reel_ng.config.project import load_project_config, resolve_look_defaults
from auto_reel_ng.event.metadata import load_event_document
from auto_reel_ng.ffmpeg.runtime import FfmpegRuntime
from auto_reel_ng.render import output_relpath
from auto_reel_ng.staleness import manifest_path
from auto_reel_ng.staleness.fingerprint import compute_fingerprint, engine_identity
from auto_reel_ng.staleness.manifest import ChapterTime, read_manifest, write_manifest

pytestmark = pytest.mark.requires_db

ANKOMST_TARTAN = (
    ChapterTime("Ankomst", 4_000, 71_500),
    ChapterTime("Tårtan", 71_500, 120_000),
)


@pytest.fixture
def settings(project: Path, postgres_container: str, jobs_schema_engine) -> ApiSettings:  # type: ignore[no-untyped-def]
    return resolve_api_settings(project, env={"DATABASE_URL": postgres_container})


@pytest.fixture
def client(settings: ApiSettings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def _url(event: str) -> str:
    return f"/api/v1/events/{quote(event, safe='/')}"


def detail(client: TestClient, event: str) -> Dict[str, Any]:
    response = client.get(_url(event))
    assert response.status_code == 200, response.text
    body: Dict[str, Any] = response.json()
    return body


def record(
    settings: ApiSettings,
    event: str,
    chapters: Optional[Sequence[ChapterTime]] = None,
    *,
    output: Optional[str] = None,
) -> Path:
    """Write the event's render record as a render would: the engine's own ``write_manifest``.

    The movie file is created at the expected path unless ``output`` names one. The fingerprint
    is the event's current one, so the event is fresh until something is edited.
    """
    event_dir = settings.project_root / event
    document, _seeded = load_event_document(event_dir, order=settings.clip_order)
    fingerprint = compute_fingerprint(
        document,
        event_dir=event_dir,
        look_defaults=resolve_look_defaults(load_project_config(settings.project_root)),
        ffmpeg_version=FfmpegRuntime().version,
    )
    expected = settings.output_dir / output_relpath(document.metadata)
    movie = expected if output is None else expected.with_name(output)
    if not movie.is_file():
        _write(movie, b"a movie")
    write_manifest(
        event_dir,
        fingerprint,
        output=movie.name,
        engine_identity=engine_identity(FfmpegRuntime().version),
        chapters=chapters,
    )
    return movie


def edit_manifest(event_dir: Path, **fields: Any) -> None:
    path = manifest_path(event_dir)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.update(fields)
    path.write_text(json.dumps(payload), encoding="utf-8")


# --------------------------------------------------------------------------- #
# what the movie object holds
# --------------------------------------------------------------------------- #


def test_a_rendered_event_reports_its_version_and_its_chapters_in_seconds(
    settings: ApiSettings, client: TestClient, movies: Dict[str, Path]
) -> None:
    record(settings, KALAS, ANKOMST_TARTAN)
    manifest = read_manifest(settings.project_root / KALAS)
    assert manifest is not None

    movie = detail(client, KALAS)["movie"]

    assert movie["chapters"] == [
        {"name": "Ankomst", "start": 4.0},
        {"name": "Tårtan", "start": 71.5},
    ]
    assert datetime.fromisoformat(movie["recorded_at"]) == datetime.fromisoformat(
        manifest.written_at
    )
    assert movie["recorded_at"].endswith("Z") or movie["recorded_at"].endswith("+00:00")
    assert movie["fingerprint"] == manifest.fingerprint[:12]
    assert len(movie["fingerprint"]) == 12
    assert set(movie) == {"recorded_at", "fingerprint", "chapters"}


def test_chapters_are_copied_in_recorded_order_without_sorting_or_dropping(
    settings: ApiSettings, client: TestClient, movies: Dict[str, Path]
) -> None:
    record(
        settings,
        KALAS,
        (
            ChapterTime("Sist", 9_000, 12_000),
            ChapterTime("", 0, 9_000),
            ChapterTime("Sist", 12_000, 12_000),
        ),
    )

    movie = detail(client, KALAS)["movie"]

    assert movie["chapters"] == [
        {"name": "Sist", "start": 9.0},
        {"name": "", "start": 0.0},
        {"name": "Sist", "start": 12.0},
    ]


def test_a_recorded_empty_list_is_empty_and_not_unknown(
    settings: ApiSettings, client: TestClient, movies: Dict[str, Path]
) -> None:
    record(settings, KALAS, ())

    assert detail(client, KALAS)["movie"]["chapters"] == []


def test_a_manifest_from_before_chapter_times_has_a_movie_and_no_chapter_list(
    settings: ApiSettings, client: TestClient, movies: Dict[str, Path]
) -> None:
    record(settings, GRILLNING, None, output=GRILLNING_OLD_MOVIE)
    manifest = json.loads(manifest_path(settings.project_root / GRILLNING).read_text("utf-8"))
    del manifest["chapters"]  # as a manifest written before the field existed
    manifest_path(settings.project_root / GRILLNING).write_text(json.dumps(manifest), "utf-8")

    movie = detail(client, GRILLNING)["movie"]

    assert movie is not None
    assert movie["chapters"] is None
    assert movie["chapters"] != []
    assert movie["fingerprint"] and movie["recorded_at"]


def test_a_malformed_chapter_list_is_unknown_not_partial(
    settings: ApiSettings, client: TestClient, movies: Dict[str, Path]
) -> None:
    record(settings, KALAS, ANKOMST_TARTAN)
    edit_manifest(
        settings.project_root / KALAS,
        chapters=[{"name": "Ankomst", "start_ms": 0, "end_ms": 5}, {"name": 7}],
    )

    movie = detail(client, KALAS)["movie"]

    assert movie is not None and movie["chapters"] is None


def test_a_movie_adopted_rather_than_rendered_reports_no_chapters(
    tmp_path: Path, postgres_container: str, jobs_schema_engine  # type: ignore[no-untyped-def]
) -> None:
    root = tmp_path / "adopted"
    event = "2024/2024-06-21 - Party"
    _write(root / event / "00400.mp4", b"clip")
    out = tmp_path / "adopted-output" / "2024" / "2024-06-21 - Party.mp4"
    _write(out, b"a movie rendered long ago")
    assert main(["adopt-renders", str(root)]) == 0
    manifest = read_manifest(root / event)
    assert manifest is not None and manifest.chapters is None
    settings = resolve_api_settings(root, env={"DATABASE_URL": postgres_container})

    with TestClient(create_app(settings)) as client:
        movie = detail(client, event)["movie"]

    assert movie["chapters"] is None
    assert datetime.fromisoformat(movie["recorded_at"]) == datetime.fromisoformat(
        manifest.written_at
    )


# --------------------------------------------------------------------------- #
# when there is no movie
# --------------------------------------------------------------------------- #


def test_an_unrendered_event_has_no_movie_and_the_key_is_present(
    client: TestClient, movies: Dict[str, Path]
) -> None:
    body = detail(client, SOMMARLOV)

    assert "movie" in body and body["movie"] is None


def test_a_deleted_movie_file_leaves_no_movie_facts(
    settings: ApiSettings, client: TestClient, movies: Dict[str, Path]
) -> None:
    record(settings, KALAS, ANKOMST_TARTAN)
    movies[KALAS].unlink()

    body = detail(client, KALAS)

    assert body["movie"] is None
    assert "output" in body["staleness"]["reasons"]


def test_a_directory_where_the_movie_belongs_is_no_movie(
    settings: ApiSettings, client: TestClient, movies: Dict[str, Path]
) -> None:
    record(settings, KALAS, ANKOMST_TARTAN)
    movies[KALAS].unlink()
    movies[KALAS].mkdir()

    assert detail(client, KALAS)["movie"] is None


@pytest.mark.parametrize(
    "garbage",
    ["{not json", json.dumps({"version": 99}), '{"version": 1, "fingerprint": "f"'],
    ids=["malformed", "unknown version", "truncated"],
)
def test_an_unreadable_manifest_is_treated_as_absent(
    settings: ApiSettings,
    client: TestClient,
    movies: Dict[str, Path],
    garbage: str,
) -> None:
    record(settings, KALAS, ANKOMST_TARTAN)
    manifest_path(settings.project_root / KALAS).write_text(garbage, encoding="utf-8")
    assert movies[KALAS].is_file()

    body = detail(client, KALAS)

    assert body["movie"] is None
    assert "no_manifest" in body["staleness"]["reasons"]


@pytest.mark.parametrize(
    "written_at",
    ["yesterday", "2024-07-14T20:00:00", ""],
    ids=["not a date", "no UTC offset", "empty"],
)
def test_a_record_without_a_usable_time_reports_no_movie(
    settings: ApiSettings,
    client: TestClient,
    movies: Dict[str, Path],
    written_at: str,
) -> None:
    record(settings, KALAS, ANKOMST_TARTAN)
    edit_manifest(settings.project_root / KALAS, written_at=written_at)

    response = client.get(_url(KALAS))

    assert response.status_code == 200
    assert response.json()["movie"] is None


def test_a_written_at_the_clock_cannot_hold_in_utc_reports_no_movie(
    settings: ApiSettings, client: TestClient, movies: Dict[str, Path]
) -> None:
    record(settings, KALAS, ANKOMST_TARTAN)
    edit_manifest(settings.project_root / KALAS, written_at="0001-01-01T00:00:00+05:00")

    response = client.get(_url(KALAS))

    assert response.status_code == 200
    assert response.json()["movie"] is None


def test_a_chapter_time_beyond_a_float_makes_the_chapters_unknown_not_the_detail_fail(
    settings: ApiSettings, client: TestClient, movies: Dict[str, Path]
) -> None:
    record(settings, KALAS, ANKOMST_TARTAN)
    edit_manifest(
        settings.project_root / KALAS,
        chapters=[{"name": "Ankomst", "start_ms": 10**400, "end_ms": 10**400 + 1}],
    )

    response = client.get(_url(KALAS))

    assert response.status_code == 200
    movie = response.json()["movie"]
    assert movie is not None and movie["chapters"] is None
    assert movie["fingerprint"] and movie["recorded_at"]


def test_a_title_cannot_make_the_detail_report_a_file_outside_the_output_directory(
    settings: ApiSettings, client: TestClient, utbrytning: Path
) -> None:
    record(settings, UTBRYTNING, ANKOMST_TARTAN, output="2024-07-15 - Utbrytning.mp4")
    assert utbrytning.is_file()

    assert detail(client, UTBRYTNING)["movie"] is None
    assert client.get(_url(UTBRYTNING) + "/movie").status_code == 404


# --------------------------------------------------------------------------- #
# the facts describe the movie on disk
# --------------------------------------------------------------------------- #


def test_a_stale_event_keeps_the_chapters_the_last_render_produced(
    settings: ApiSettings, client: TestClient, movies: Dict[str, Path], project: Path
) -> None:
    event_dir = project / TJORN
    record(settings, TJORN, (ChapterTime("", 0, 2_000), ChapterTime("Kvällen", 2_000, 5_000)))
    reel = event_dir / "reel.yaml"
    reel.write_text(
        reel.read_text(encoding="utf-8").replace("name: Kvällen", "name: Natten"),
        encoding="utf-8",
    )
    _write(event_dir / "s1710009.mp4", b"a new clip")
    reel.write_text(
        reel.read_text(encoding="utf-8").replace(
            "      - Kvällen/s1710003.mp4", "      - Kvällen/s1710003.mp4\n      - s1710009.mp4"
        ),
        encoding="utf-8",
    )

    body = detail(client, TJORN)

    assert {"editorial", "clip_set"} <= set(body["staleness"]["reasons"])
    assert [chapter["name"] for chapter in body["chapters"]] == ["", "Natten"]
    assert body["movie"]["chapters"] == [
        {"name": "", "start": 0.0},
        {"name": "Kvällen", "start": 2.0},
    ]


def test_a_renamed_event_reports_the_facts_of_the_movie_under_its_old_name(
    settings: ApiSettings, client: TestClient, movies: Dict[str, Path]
) -> None:
    record(settings, GRILLNING, ANKOMST_TARTAN, output=GRILLNING_OLD_MOVIE)
    manifest = read_manifest(settings.project_root / GRILLNING)
    assert manifest is not None

    body = detail(client, GRILLNING)

    assert "output_renamed" in body["staleness"]["reasons"]
    assert body["movie"]["fingerprint"] == manifest.fingerprint[:12]
    assert datetime.fromisoformat(body["movie"]["recorded_at"]) == datetime.fromisoformat(
        manifest.written_at
    )
    assert [chapter["name"] for chapter in body["movie"]["chapters"]] == ["Ankomst", "Tårtan"]


def test_a_re_render_with_no_edit_keeps_the_fingerprint_and_moves_recorded_at(
    settings: ApiSettings, client: TestClient, movies: Dict[str, Path]
) -> None:
    record(settings, KALAS, ANKOMST_TARTAN)
    first = detail(client, KALAS)["movie"]

    record(settings, KALAS, ANKOMST_TARTAN)  # --force: same inputs, written again
    second = detail(client, KALAS)["movie"]

    assert second["fingerprint"] == first["fingerprint"]
    assert datetime.fromisoformat(second["recorded_at"]) > datetime.fromisoformat(
        first["recorded_at"]
    )


def test_an_edit_before_the_next_render_changes_nothing_about_the_movie(
    settings: ApiSettings, client: TestClient, movies: Dict[str, Path], project: Path
) -> None:
    record(settings, KALAS, ANKOMST_TARTAN)
    before = detail(client, KALAS)["movie"]
    (project / KALAS / "reel.yaml").write_text(
        "version: 0\nmetadata:\n  title: Kalas\n  date: 2024-07-14\n  description: ny\n"
        "chapters:\n  - name: Ändrad\n    clips:\n      - s1710001.mp4\n",
        encoding="utf-8",
    )

    after = detail(client, KALAS)

    assert after["staleness"]["stale"] is True
    assert after["movie"] == before


# --------------------------------------------------------------------------- #
# the route, the list, the schema and the read-only guarantee
# --------------------------------------------------------------------------- #


def test_the_detail_and_the_movie_route_agree_for_every_event(
    settings: ApiSettings, client: TestClient, movies: Dict[str, Path], utbrytning: Path
) -> None:
    record(settings, KALAS, ANKOMST_TARTAN)
    record(settings, GRILLNING, ANKOMST_TARTAN, output=GRILLNING_OLD_MOVIE)
    record(settings, UTBRYTNING, None, output="2024-07-15 - Utbrytning.mp4")
    rows = client.get("/api/v1/events").json()
    summaries = [row for row in rows if row["kind"] == "event"]
    assert len(summaries) >= 8, rows  # the whole library, not a sample

    agreed: Dict[str, bool] = {}
    for row in summaries:
        event_id = row["event_id"]
        movie = detail(client, event_id)["movie"]
        status = client.get(_url(event_id) + "/movie").status_code
        assert status in (200, 404), (event_id, status)
        assert (movie is not None) == (status == 200), event_id
        agreed[event_id] = movie is not None
    assert agreed[KALAS] and agreed[GRILLNING]  # both answers occur in this library
    assert not agreed[SOMMARLOV] and not agreed[UTBRYTNING]


def test_the_list_rows_do_not_carry_the_movie(
    settings: ApiSettings, client: TestClient, movies: Dict[str, Path]
) -> None:
    record(settings, KALAS, ANKOMST_TARTAN)

    rows = client.get("/api/v1/events").json()

    assert rows and all("movie" not in row for row in rows)


def test_reading_the_movie_facts_probes_and_writes_nothing(
    settings: ApiSettings,
    client: TestClient,
    movies: Dict[str, Path],
    project: Path,
    output_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record(settings, KALAS, ANKOMST_TARTAN)
    before = (_snapshot(project), _snapshot(output_dir))

    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("the detail started a process")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    response = client.get(_url(KALAS))

    assert response.status_code == 200
    assert response.json()["movie"]["chapters"][0] == {"name": "Ankomst", "start": 4.0}
    assert (_snapshot(project), _snapshot(output_dir)) == before


def test_the_one_lookup_is_the_routes_own(settings: ApiSettings, movies: Dict[str, Path]) -> None:
    document, _seeded = load_event_document(
        settings.project_root / KALAS, order=settings.clip_order
    )

    found = movie_read.rendered_movie_path(
        settings, settings.project_root / KALAS, document.metadata
    )

    assert found == movies[KALAS] and found.name == KALAS_MOVIE


# --------------------------------------------------------------------------- #
# a real render
# --------------------------------------------------------------------------- #


@pytest.mark.has_ffmpeg
def test_a_real_small_render_feeds_the_detail(
    make_clip, tmp_path: Path, postgres_container: str, jobs_schema_engine  # type: ignore[no-untyped-def]
) -> None:
    clip = make_clip("source.mp4", width=320, height=240, fps=30, duration=1.0)
    root = tmp_path / "library"
    event = "2024/2024-08-20 - Två kapitel - Tjörn"
    for identity in ("s1710001.mp4", "Kvällen/s1710002.mp4"):
        target = root / event / identity
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(clip, target)
    assert main(["render", str(root), "--device", "cpu"]) == 0
    manifest = read_manifest(root / event)
    assert manifest is not None and manifest.chapters is not None
    settings = resolve_api_settings(root, env={"DATABASE_URL": postgres_container})

    with TestClient(create_app(settings)) as client:
        movie = detail(client, event)["movie"]
        after = datetime.now(timezone.utc)

    starts: List[float] = [chapter["start"] for chapter in movie["chapters"]]
    assert starts == [chapter.start_ms / 1000 for chapter in manifest.chapters]
    assert len(starts) == 2 and starts[0] < starts[1]
    assert datetime.fromisoformat(movie["recorded_at"]) <= after
