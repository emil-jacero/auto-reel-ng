"""Tests for the jobs lifecycle routes (tasks 3.1-3.3)."""

from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path
from typing import Optional

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from auto_reel_ng.api.app import create_app
from auto_reel_ng.api.settings import resolve_api_settings
from auto_reel_ng.cli.main import main
from auto_reel_ng.config import default_output_dir
from auto_reel_ng.event import DEFAULT_CLIP_ORDER
from auto_reel_ng.persistence.engine import session_scope
from auto_reel_ng.persistence.job_store import JobStore
from auto_reel_ng.persistence.models import Job, JobStatus
from auto_reel_ng.staleness.manifest import manifest_path

pytestmark = pytest.mark.requires_db

#: The dev library's case-only twins (``scripts/make_dev_library.py``).
KALAS = "2024/2024-07-14 - Kalas"
KALAS_LOWER = "2024/2024-07-14 - kalas"

#: An in-project symlinked alias of the Kalas folder, and a real folder named like it.
FEST = "2024/2024-07-20 - Fest"
FEST_LOWER = "2024/2024-07-20 - fest"


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    _touch(root / "2024" / "2024-06-21 - A" / "00400.mp4")
    _touch(root / "2024" / "2024-06-22 - B" / "00400.mp4")
    return root


@pytest.fixture
def store(jobs_session_factory) -> JobStore:
    """A store bound to the shared schema, table cleared (function-scoped fixture)."""
    return JobStore(jobs_session_factory)


@pytest.fixture
def client(project: Path, postgres_container: str, store: JobStore):
    # Depends on ``store`` so the ``jobs`` table is cleared before either the
    # app's own engine or this fixture's store queries run (both point at the
    # same Postgres database; only the table-clear ordering matters here).
    settings = resolve_api_settings(project, env={"DATABASE_URL": postgres_container})
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client


def test_enqueue_creates_queued_job(client: TestClient, store: JobStore) -> None:
    response = client.post("/api/v1/jobs", json={"event_id": "2024/2024-06-21 - A"})
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "queued"
    assert body["event_dir"] == "2024/2024-06-21 - A"
    job = store.get(uuid.UUID(body["id"]))
    assert job is not None
    assert job.status == JobStatus.QUEUED


def test_a_job_carries_the_events_routes_id_as_its_event_dir(client: TestClient) -> None:
    """The contract a client matches jobs to event rows by: ``event_dir == event_id``."""
    rows = client.get("/api/v1/events").json()
    event_id = next(row["event_id"] for row in rows if row["event_id"].endswith(" - A"))

    job = client.post("/api/v1/jobs", json={"event_id": event_id}).json()

    assert job["event_dir"] == event_id


def test_an_enqueue_that_loses_the_race_is_a_conflict(
    client: TestClient, store: JobStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = client.post("/api/v1/jobs", json={"event_id": "2024/2024-06-21 - A"})
    assert first.status_code == 201
    # Stands in for a concurrent request that inserts after this request's
    # pre-check found nothing: the store's insertion must decide, not the pre-check.
    monkeypatch.setattr(client.app.state.job_store, "active_job", lambda *_: None)

    second = client.post("/api/v1/jobs", json={"event_id": "2024/2024-06-21 - A"})

    assert second.status_code == 409
    assert second.json()["job_id"] == first.json()["id"]
    assert second.json()["conflict"] == "active_job"  # the same kind as the pre-check's
    assert len(store.list_by_status(JobStatus.QUEUED)) == 1


def test_duplicate_enqueue_is_a_visible_conflict(client: TestClient, store: JobStore) -> None:
    first = client.post("/api/v1/jobs", json={"event_id": "2024/2024-06-21 - A"})
    second = client.post("/api/v1/jobs", json={"event_id": "2024/2024-06-21 - A"})
    assert second.status_code == 409
    problem = second.json()
    assert problem["job_id"] == first.json()["id"]
    assert problem["conflict"] == "active_job"
    assert "claimed_by" not in problem
    assert "id" not in problem  # the untyped extra the typed ``job_id`` replaced
    assert len(store.list_by_status(JobStatus.QUEUED)) == 1


def test_terminal_job_does_not_block_new_enqueue(client: TestClient, store: JobStore) -> None:
    first = client.post("/api/v1/jobs", json={"event_id": "2024/2024-06-21 - A"})
    job_id = uuid.UUID(first.json()["id"])
    store.claim_next("worker-1")
    store.transition(job_id, JobStatus.DONE)

    second = client.post("/api/v1/jobs", json={"event_id": "2024/2024-06-21 - A"})
    assert second.status_code == 201
    assert second.json()["id"] != str(job_id)


def test_enqueue_unknown_event_is_404(client: TestClient) -> None:
    response = client.post("/api/v1/jobs", json={"event_id": "2024/2024-12-24 - Finns inte"})
    assert response.status_code == 404
    assert response.json()["event_id"] == "2024/2024-12-24 - Finns inte"


# --------------------------------------------------------------------------- #
# The id names a listed event; an event it cannot process is refused up front
# (api-jobs-create-validation 2.2)
# --------------------------------------------------------------------------- #

A_ID = "2024/2024-06-21 - A"


@pytest.mark.parametrize(
    "event_id",
    [
        "2024/./2024-06-21 - A",
        "2024/2024-06-21 - A/",
        "2024/2024-06-21 - A/../2024-06-21 - A",
        "2024/2024-06-21 - A/original",
        "2024",
        "",
    ],
    ids=["dot", "trailing-slash", "dotdot", "original", "year-folder", "root"],
)
def test_a_spelling_the_list_does_not_show_is_unknown(
    client: TestClient, store: JobStore, project: Path, event_id: str
) -> None:
    (project / A_ID / "original").mkdir()

    response = client.post("/api/v1/jobs", json={"event_id": event_id})

    assert response.status_code == 404
    assert response.json()["event_id"] == event_id
    assert _all_jobs(store) == []
    # while the listed id still enqueues, under that id
    listed = client.post("/api/v1/jobs", json={"event_id": A_ID})
    assert (listed.status_code, listed.json()["event_dir"]) == (201, A_ID)


def test_a_second_spelling_of_an_active_event_is_unknown_not_a_second_job(
    client: TestClient, store: JobStore
) -> None:
    assert client.post("/api/v1/jobs", json={"event_id": A_ID}).status_code == 201

    again = client.post("/api/v1/jobs", json={"event_id": f"{A_ID}/"})

    assert again.status_code == 404
    assert len(_all_jobs(store)) == 1


def test_a_folder_outside_the_input_and_a_reelignored_event_are_unknown(
    client: TestClient, store: JobStore, project: Path
) -> None:
    _touch(project / "input" / A_ID / "00400.mp4")
    _touch(project / "input" / "2024" / "2024-06-22 - B" / "00400.mp4")
    (project / "input" / "2024" / "2024-06-22 - B" / ".reelignore").write_bytes(b"")
    (project / "config.yaml").write_text("input: input\n", encoding="utf-8")
    settings = resolve_api_settings(
        project, env={"DATABASE_URL": client.app.state.settings.database_url}
    )
    with TestClient(create_app(settings)) as inside_input:
        for event_id in (A_ID, "input/2024/2024-06-22 - B"):  # outside input/; ignored
            response = inside_input.post("/api/v1/jobs", json={"event_id": event_id})
            assert response.status_code == 404, event_id
        assert (
            inside_input.post("/api/v1/jobs", json={"event_id": f"input/{A_ID}"}).status_code == 201
        )
    assert [job.event_dir for job in _all_jobs(store)] == [f"input/{A_ID}"]


def test_an_unparseable_reel_yaml_is_a_502_not_a_500(
    client: TestClient, store: JobStore, project: Path
) -> None:
    (project / A_ID / "reel.yaml").write_text("metadata: [unclosed", encoding="utf-8")

    response = client.post("/api/v1/jobs", json={"event_id": A_ID})

    assert response.status_code == 502
    problem = response.json()
    assert (problem["event_id"], problem["failure"]) == (A_ID, "unparseable_reel_yaml")
    assert problem["detail"] == client.get(f"/api/v1/events/{A_ID}").json()["detail"]
    assert _all_jobs(store) == []
    assert not manifest_path(project / A_ID).exists()


@pytest.mark.parametrize(
    "reel_yaml",
    [None, "version: 0\nmetadata:\n  date: 2999-01-01\n"],
    ids=["no-date", "future-date"],
)
def test_an_event_without_a_usable_date_is_refused_up_front(
    client: TestClient, store: JobStore, project: Path, reel_yaml: Optional[str]
) -> None:
    event_id = "2024/NoDate" if reel_yaml is None else A_ID
    _touch(project / "2024" / "NoDate" / "00400.mp4")
    if reel_yaml is not None:
        (project / A_ID / "reel.yaml").write_text(reel_yaml, encoding="utf-8")

    response = client.post("/api/v1/jobs", json={"event_id": event_id})

    assert response.status_code == 502
    problem = response.json()
    assert (problem["event_id"], problem["failure"]) == (event_id, "unusable_metadata")
    assert _all_jobs(store) == []


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
def test_an_event_folder_that_cannot_be_searched_is_refused_up_front(
    client: TestClient, store: JobStore, project: Path
) -> None:
    (project / A_ID).chmod(0o600)
    try:
        response = client.post("/api/v1/jobs", json={"event_id": A_ID})
    finally:
        (project / A_ID).chmod(0o755)

    assert response.status_code == 502
    assert response.json()["failure"] == "unreadable_disk"
    assert _all_jobs(store) == []


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
def test_a_sibling_that_cannot_be_listed_claims_no_path(
    client: TestClient, store: JobStore, project: Path
) -> None:
    _add_case_only_twins(project)
    (project / KALAS_LOWER).chmod(0o000)  # would collide with Kalas, if it could be listed
    try:
        response = client.post("/api/v1/jobs", json={"event_id": KALAS})
    finally:
        (project / KALAS_LOWER).chmod(0o755)

    assert response.status_code == 201
    assert [job.event_dir for job in _all_jobs(store)] == [KALAS]


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
def test_a_year_folder_that_cannot_be_listed_is_the_scan_failure(
    client: TestClient, store: JobStore, project: Path
) -> None:
    (project / "2024").chmod(0o111)  # the id resolves; the lookup's listing is refused
    try:
        response = client.post("/api/v1/jobs", json={"event_id": A_ID})
    finally:
        (project / "2024").chmod(0o755)

    assert response.status_code == 502
    assert "event scan failed" in response.json()["detail"]
    assert "failure" not in response.json() or response.json()["failure"] is None
    assert _all_jobs(store) == []


def test_a_failing_event_outranks_an_active_job(
    client: TestClient, store: JobStore, project: Path
) -> None:
    queued = client.post("/api/v1/jobs", json={"event_id": A_ID})
    assert queued.status_code == 201
    (project / A_ID / "reel.yaml").write_text("metadata: [unclosed", encoding="utf-8")

    response = client.post("/api/v1/jobs", json={"event_id": A_ID})

    assert response.status_code == 502
    assert response.json()["failure"] == "unparseable_reel_yaml"
    assert [(job.id, job.status) for job in _all_jobs(store)] == [
        (uuid.UUID(queued.json()["id"]), JobStatus.QUEUED)
    ]


def test_enqueue_stamps_fingerprint_and_defaults_force_false(
    client: TestClient, store: JobStore
) -> None:
    response = client.post("/api/v1/jobs", json={"event_id": "2024/2024-06-21 - A"})
    body = response.json()
    assert body["fingerprint"]
    assert body["force"] is False


def _adopt_and_write_manifest(project: Path, event_id: str) -> None:
    from auto_reel_ng.cli.adoption import persist, prepare_event
    from auto_reel_ng.config.project import load_project_config, resolve_look_defaults
    from auto_reel_ng.ffmpeg.runtime import FfmpegRuntime
    from auto_reel_ng.render import output_relpath
    from auto_reel_ng.staleness.fingerprint import compute_fingerprint, engine_identity
    from auto_reel_ng.staleness.manifest import write_manifest

    event_dir = project / event_id
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


def test_fresh_event_is_not_enqueued(client: TestClient, store: JobStore, project: Path) -> None:
    _adopt_and_write_manifest(project, "2024/2024-06-21 - A")

    response = client.post("/api/v1/jobs", json={"event_id": "2024/2024-06-21 - A"})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "fresh"
    assert body["event_id"] == "2024/2024-06-21 - A"
    assert body["fingerprint"]
    assert body["manifest"].startswith("2024/2024-06-21 - A/")
    assert store.list_by_status(JobStatus.QUEUED) == []


def test_force_enqueues_a_fresh_event(client: TestClient, store: JobStore, project: Path) -> None:
    _adopt_and_write_manifest(project, "2024/2024-06-21 - A")

    response = client.post("/api/v1/jobs", json={"event_id": "2024/2024-06-21 - A", "force": True})

    assert response.status_code == 201
    body = response.json()
    assert body["force"] is True
    assert len(store.list_by_status(JobStatus.QUEUED)) == 1


# --------------------------------------------------------------------------- #
# Output collisions on enqueue (jobs-project-guards 3.3)
# --------------------------------------------------------------------------- #


def _add_case_only_twins(project: Path) -> None:
    """Add the dev library's two Kalas events to this test's project.

    ``kalas`` authors its title in lower case, so its output path differs from
    ``Kalas``'s only in letter case: the rule compares paths case-insensitively.
    """
    _touch(project / KALAS / "00400.mp4")
    _touch(project / KALAS_LOWER / "00500.mp4")
    (project / KALAS_LOWER / "reel.yaml").write_text(
        "version: 0\nmetadata:\n  title: kalas\n", encoding="utf-8"
    )


def _all_jobs(store: JobStore) -> list[Job]:
    return [job for status in JobStatus for job in store.list_by_status(status)]


@pytest.mark.parametrize("force", [False, True], ids=["unforced", "forced"])
def test_an_output_collision_is_refused(
    client: TestClient, store: JobStore, project: Path, force: bool
) -> None:
    _add_case_only_twins(project)

    response = client.post("/api/v1/jobs", json={"event_id": KALAS_LOWER, "force": force})

    assert response.status_code == 409
    problem = response.json()
    assert problem["conflict"] == "output_collision"
    assert problem["claimed_by"] == [KALAS]
    assert problem["event_id"] == KALAS_LOWER
    assert "job_id" not in problem
    assert "2024/2024-07-14 - kalas.mp4" in problem["detail"]
    assert f"also claimed by {KALAS};" in problem["detail"]
    assert "set a distinct title or location in reel.yaml" in problem["detail"]
    assert _all_jobs(store) == []


def test_a_fresh_events_movie_is_protected_from_its_twin(
    client: TestClient, store: JobStore, project: Path
) -> None:
    _add_case_only_twins(project)
    _adopt_and_write_manifest(project, KALAS)
    movie = default_output_dir(project) / "2024" / "2024-07-14 - Kalas.mp4"
    manifest = manifest_path(project / KALAS)
    before = (movie.read_bytes(), manifest.read_bytes())

    response = client.post("/api/v1/jobs", json={"event_id": KALAS})

    assert response.status_code == 409  # checked before the gate: not the 200 "fresh"
    assert response.json()["conflict"] == "output_collision"
    assert response.json()["claimed_by"] == [KALAS_LOWER]
    assert (movie.read_bytes(), manifest.read_bytes()) == before
    assert _all_jobs(store) == []
    # Without its twin the same event is simply fresh: the collision took precedence.
    shutil.rmtree(project / KALAS_LOWER)
    assert client.post("/api/v1/jobs", json={"event_id": KALAS}).status_code == 200


def test_a_collision_outranks_an_active_job(
    client: TestClient, store: JobStore, project: Path
) -> None:
    """Checked first: a job queued before its twin appeared is not the answer."""
    _add_case_only_twins(project)
    active = store.enqueue(str(project), KALAS_LOWER)

    response = client.post("/api/v1/jobs", json={"event_id": KALAS_LOWER})

    assert response.status_code == 409
    problem = response.json()
    assert problem["conflict"] == "output_collision"
    assert "job_id" not in problem
    assert [job.id for job in _all_jobs(store)] == [active]  # nothing new


def test_an_event_outside_any_collision_still_enqueues(client: TestClient, project: Path) -> None:
    _add_case_only_twins(project)

    response = client.post("/api/v1/jobs", json={"event_id": "2024/2024-06-21 - A"})

    assert response.status_code == 201


@pytest.mark.parametrize(
    "reel_yaml",
    [
        b": [",
        b"version: 0\nmetadata:\n  title: a\n  date: 2024-02-30\n",  # a ReelParseError
        b"version: 0\nmetadata:\n  title: a \xff\n",  # not UTF-8: a ReelParseError too
    ],
    ids=["unparseable-reel-yaml", "impossible-yaml-date", "not-utf-8"],
)
def test_events_that_fail_on_their_own_claim_no_path(
    client: TestClient, project: Path, reel_yaml: bytes
) -> None:
    _touch(project / "2024" / "2024-02-30 - Omöjligt datum" / "00400.mp4")
    unreadable = project / "2024" / "2024-06-21 - a"  # A's twin, if it could be read
    _touch(unreadable / "00400.mp4")
    (unreadable / "reel.yaml").write_bytes(reel_yaml)

    response = client.post("/api/v1/jobs", json={"event_id": "2024/2024-06-21 - A"})

    assert response.status_code == 201  # never a 500 for a sibling's document


@pytest.fixture
def cli_database(monkeypatch: pytest.MonkeyPatch, postgres_container: str) -> None:
    """Point the CLI's ``DATABASE_URL`` at the test container, as ``test_cli_jobs.py`` does."""
    monkeypatch.setenv("DATABASE_URL", postgres_container)


def _cli_refused(project: Path, capsys: pytest.CaptureFixture[str]) -> set[str]:
    """The folders ``auto-reel enqueue <project>`` refuses for an output collision."""
    capsys.readouterr()  # drop anything printed before
    main(["enqueue", str(project)])
    return {
        line.removeprefix("ERROR  ").split(": ", 1)[0]
        for line in capsys.readouterr().out.splitlines()
        if line.startswith("ERROR  ") and ": output path " in line
    }


@pytest.mark.parametrize(
    ("real", "authored", "answers"),
    [
        # The alias is dropped from the walk (layout-alias-dedupe), so it claims no path:
        # the real fest and Kalas collide with nothing, as the CLI's enqueue finds them.
        ((KALAS, FEST_LOWER), False, {FEST_LOWER: None, KALAS: None}),
        # Nothing else claims Kalas's path: its case-only twins refuse each other as before.
        ((KALAS, KALAS_LOWER), False, {KALAS: [KALAS_LOWER], KALAS_LOWER: [KALAS]}),
        # The alias reads the folder's authored reel.yaml but is no row, so it does not
        # claim Kalas.mp4 a second time: Kalas enqueues.
        ((KALAS,), True, {KALAS: None}),
    ],
    ids=[
        "alias-beside-its-name-twin",
        "alias-of-a-colliding-folder",
        "alias-of-an-authored-folder",
    ],
)
@pytest.mark.usefixtures("cli_database")
def test_a_dropped_in_project_alias_claims_nothing_as_the_cli_sees_it(
    client: TestClient,
    store: JobStore,
    project: Path,
    capsys: pytest.CaptureFixture[str],
    real: tuple[str, ...],
    authored: bool,
    answers: dict[str, Optional[list[str]]],
) -> None:
    for event_id in real:
        _touch(project / event_id / "00400.mp4")
    if authored:
        (project / KALAS / "reel.yaml").write_text(
            "version: 0\nmetadata:\n  title: Kalas\n  date: 2024-07-14\n", encoding="utf-8"
        )
    (project / FEST).symlink_to(project / KALAS)

    for event_id, claimed_by in answers.items():
        response = client.post("/api/v1/jobs", json={"event_id": event_id})
        if claimed_by is None:
            assert response.status_code == 201, event_id
        else:
            assert response.status_code == 409, event_id
            problem = response.json()
            assert (problem["conflict"], problem["claimed_by"]) == ("output_collision", claimed_by)
    enqueued = {event_id for event_id, claimed_by in answers.items() if claimed_by is None}
    assert {job.event_dir for job in _all_jobs(store)} == enqueued
    refused = {Path(event_id).name for event_id in answers if event_id not in enqueued}
    assert _cli_refused(project, capsys) == refused  # the CLI's own answer


def test_an_alias_is_gated_at_its_own_output(client: TestClient, project: Path) -> None:
    """The gate judges the path the job names, as the worker will: not the alias's target."""
    _touch(project / KALAS / "00400.mp4")
    # No authored metadata: each row takes its title and date from its own folder name.
    (project / KALAS / "reel.yaml").write_text("version: 0\n", encoding="utf-8")
    _adopt_and_write_manifest(project, KALAS)  # Kalas.mp4 rendered: Kalas is fresh
    (project / FEST).symlink_to(project / KALAS)

    assert client.post("/api/v1/jobs", json={"event_id": KALAS}).status_code == 200  # fresh
    # Fest.mp4 was never rendered: the alias is stale, not "fresh" by its target's movie.
    assert client.post("/api/v1/jobs", json={"event_id": FEST}).status_code == 201


def test_an_id_spelled_through_a_missing_folder_is_unknown(
    client: TestClient, store: JobStore
) -> None:
    """It resolves lexically to A, but the worker would open the path it spells."""
    event_id = "2024/missing/../2024-06-21 - A"

    response = client.post("/api/v1/jobs", json={"event_id": event_id})

    assert response.status_code == 404
    assert response.json()["event_id"] == event_id
    assert _all_jobs(store) == []


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
def test_a_walk_that_fails_refuses_to_enqueue(
    client: TestClient, store: JobStore, project: Path
) -> None:
    year_dir = project / "2023"
    _touch(year_dir / "2023-06-23 - Midsommar - Dalarna" / "00400.mp4")
    year_dir.chmod(0o000)
    try:
        response = client.post("/api/v1/jobs", json={"event_id": "2024/2024-06-21 - A"})
    finally:
        year_dir.chmod(0o755)

    assert response.status_code == 502
    problem = response.json()
    assert problem["title"] == "Bad Gateway"
    assert "event scan failed" in problem["detail"]
    assert _all_jobs(store) == []


def test_list_jobs_filters_by_status(client: TestClient, store: JobStore) -> None:
    client.post("/api/v1/jobs", json={"event_id": "2024/2024-06-21 - A"})
    client.post("/api/v1/jobs", json={"event_id": "2024/2024-06-22 - B"})
    running_id = store.claim_next("worker-1").id

    response = client.get("/api/v1/jobs", params={"status": "queued"})
    assert response.status_code == 200
    ids = {job["id"] for job in response.json()}
    assert str(running_id) not in ids
    assert len(ids) == 1


def test_get_job_detail(client: TestClient, store: JobStore) -> None:
    created = client.post("/api/v1/jobs", json={"event_id": "2024/2024-06-21 - A"})
    job_id = created.json()["id"]

    response = client.get(f"/api/v1/jobs/{job_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == job_id
    assert body["requeue_count"] == 0
    assert body["force"] is False
    assert body["fingerprint"]


def test_get_unknown_job_is_404(client: TestClient) -> None:
    job_id = uuid.uuid4()
    response = client.get(f"/api/v1/jobs/{job_id}")
    assert response.status_code == 404
    assert response.json()["job_id"] == str(job_id)


def test_cancel_running_job_flags_without_changing_status(
    client: TestClient, store: JobStore
) -> None:
    created = client.post("/api/v1/jobs", json={"event_id": "2024/2024-06-21 - A"})
    job_id = created.json()["id"]
    store.claim_next("worker-1")

    response = client.post(f"/api/v1/jobs/{job_id}/cancel")
    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "flagged-running"
    assert body["status"] == "running"

    job = store.get(uuid.UUID(job_id))
    assert job is not None
    assert job.cancel_requested is True
    assert job.status == JobStatus.RUNNING


def test_cancel_queued_job_cancels_immediately(client: TestClient, store: JobStore) -> None:
    created = client.post("/api/v1/jobs", json={"event_id": "2024/2024-06-21 - A"})
    job_id = created.json()["id"]

    response = client.post(f"/api/v1/jobs/{job_id}/cancel")
    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "canceled-queued"
    assert body["status"] == "canceled"


def test_cancel_reports_the_outcome_it_applied_not_an_earlier_read(
    client: TestClient, store: JobStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    created = client.post("/api/v1/jobs", json={"event_id": "2024/2024-06-21 - A"})
    job_id = uuid.UUID(created.json()["id"])
    queued_copy = store.get(job_id)  # read while the job is still queued ...
    store.claim_next("worker-1")  # ... before a worker claims it
    monkeypatch.setattr(client.app.state.job_store, "get", lambda _job_id: queued_copy)

    response = client.post(f"/api/v1/jobs/{job_id}/cancel")

    assert response.status_code == 200
    body = response.json()
    assert (body["outcome"], body["status"]) == ("flagged-running", "running")


@pytest.mark.parametrize("terminal", [JobStatus.DONE, JobStatus.FAILED, JobStatus.CANCELED])
def test_cancel_terminal_job_is_a_no_op(
    client: TestClient, store: JobStore, terminal: JobStatus
) -> None:
    created = client.post("/api/v1/jobs", json={"event_id": "2024/2024-06-21 - A"})
    job_id = uuid.UUID(created.json()["id"])
    store.claim_next("worker-1")
    store.transition(job_id, terminal)

    response = client.post(f"/api/v1/jobs/{job_id}/cancel")
    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "no-op-terminal"
    assert body["status"] == terminal.value


def test_cancel_unknown_job_is_404(client: TestClient, store: JobStore) -> None:
    queued = client.post("/api/v1/jobs", json={"event_id": "2024/2024-06-21 - A"}).json()
    job_id = uuid.uuid4()

    response = client.post(f"/api/v1/jobs/{job_id}/cancel")

    assert response.status_code == 404
    assert response.json()["job_id"] == str(job_id)
    job = store.get(uuid.UUID(queued["id"]))
    assert job is not None
    assert (job.status, job.cancel_requested) == (JobStatus.QUEUED, False)  # no row changed


# --------------------------------------------------------------------------- #
# The served project only (jobs-project-guards 4.1)
# --------------------------------------------------------------------------- #

#: Another library in the same database: its job is only a row, no folder exists.
FOREIGN_ROOT = "/elsewhere/library"


def _job_outside_the_project(
    store: JobStore, session_factory: sessionmaker, project_root: Optional[str]
) -> uuid.UUID:
    """A queued ``2024/Blandat`` job of another project, or with no recorded root."""
    if project_root is not None:
        return store.enqueue(project_root, "2024/Blandat")
    with session_scope(session_factory) as session:
        job = Job(project_root=None, event_dir="2024/Blandat")
        session.add(job)
        session.flush()
        return job.id


@pytest.mark.parametrize("project_root", [FOREIGN_ROOT, None], ids=["foreign", "rootless"])
def test_a_job_outside_the_project_is_not_listed(
    client: TestClient,
    store: JobStore,
    jobs_session_factory: sessionmaker,
    project_root: Optional[str],
) -> None:
    own = client.post("/api/v1/jobs", json={"event_id": "2024/2024-06-21 - A"}).json()
    outside = _job_outside_the_project(store, jobs_session_factory, project_root)

    for params in ({}, {"status": "queued"}):
        listed = client.get("/api/v1/jobs", params=params).json()
        assert [job["id"] for job in listed] == [own["id"]], params
    # The store itself still holds both: only the service's view is scoped.
    assert outside in {job.id for job in store.list_by_status(JobStatus.QUEUED)}


@pytest.mark.parametrize("project_root", [FOREIGN_ROOT, None], ids=["foreign", "rootless"])
def test_a_job_outside_the_project_is_an_unknown_id(
    client: TestClient,
    store: JobStore,
    jobs_session_factory: sessionmaker,
    project_root: Optional[str],
) -> None:
    outside = _job_outside_the_project(store, jobs_session_factory, project_root)
    unknown = client.get(f"/api/v1/jobs/{uuid.uuid4()}").json()

    shown = client.get(f"/api/v1/jobs/{outside}")
    canceled = client.post(f"/api/v1/jobs/{outside}/cancel")

    for response in (shown, canceled):
        assert response.status_code == 404
        problem = response.json()
        assert set(problem) == set(unknown)  # the very shape an unknown id gets
        assert (problem["title"], problem["status"]) == (unknown["title"], unknown["status"])
        assert problem["job_id"] == str(outside)
        assert problem["detail"] == f"no job with id {outside}"
    job = store.get(outside)
    assert job is not None
    assert (job.status, job.cancel_requested) == (JobStatus.QUEUED, False)  # untouched


def test_the_projects_own_jobs_are_served_beside_a_foreign_one(
    client: TestClient, store: JobStore
) -> None:
    store.enqueue(FOREIGN_ROOT, "2024/2024-06-21 - A")  # the same event id, another project
    own = client.post("/api/v1/jobs", json={"event_id": "2024/2024-06-21 - A"})
    assert own.status_code == 201  # the one-active-job rule is per project too
    job_id = own.json()["id"]

    assert client.get(f"/api/v1/jobs/{job_id}").json()["id"] == job_id
    canceled = client.post(f"/api/v1/jobs/{job_id}/cancel").json()
    assert (canceled["outcome"], canceled["status"]) == ("canceled-queued", "canceled")
    assert [job["id"] for job in client.get("/api/v1/jobs").json()] == [job_id]
