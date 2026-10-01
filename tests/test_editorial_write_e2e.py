"""End-to-end test for the editorial write path (task 3.1, spec-driven change
``editorial-write-api``): save via ``PUT`` -> a subsequent read reports
``stale: editorial, output_renamed`` (the title feeds the movie's name) -> ``POST /jobs``
enqueues -> the worker renders the edited state -> the event returns to fresh, with
the rendered output reflecting the edit (a new title -> a new output filename) and
the previous movie kept, untouched (change ``output-renamed-reason``).

Real Postgres (podman fixture) and a real CPU render (a synthetic clip via
``make_clip``), mirroring ``test_cli_jobs.py``'s enqueue -> worker -> done smoke
test, driven here through the API instead of the CLI.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from auto_reel_ng.accel.detection import detect_capabilities
from auto_reel_ng.accel.selection import select_profile
from auto_reel_ng.api.app import create_app
from auto_reel_ng.api.settings import resolve_api_settings
from auto_reel_ng.config import default_output_dir
from auto_reel_ng.persistence.job_store import JobStore
from auto_reel_ng.persistence.models import Job
from auto_reel_ng.scheduler.pools import CapacityPools
from auto_reel_ng.scheduler.worker import Worker, default_build_job
from auto_reel_ng.staleness.manifest import read_manifest

pytestmark = pytest.mark.requires_db

EVENT_ID = "2024/2024-06-21 - Trip"


def test_editorial_write_save_stale_render_cycle(
    tmp_path: Path,
    postgres_container: str,
    jobs_session_factory,
    runtime,
    make_clip,
) -> None:
    root = tmp_path / "proj"
    (root / EVENT_ID).mkdir(parents=True)
    make_clip(f"proj/{EVENT_ID}/clip.mp4", width=320, height=240, duration=1.0)

    settings = resolve_api_settings(root, env={"DATABASE_URL": postgres_container})
    app = create_app(settings)
    encoded_id = quote(EVENT_ID, safe="/")

    inventory = detect_capabilities(runtime)
    profile = select_profile(inventory, override="cpu")
    pools = CapacityPools.from_inventory(inventory, gpu_cap=1, cpu_cap=1)

    with TestClient(app) as client:
        job_store: JobStore = app.state.job_store
        worker = Worker(
            job_store,
            worker_id="e2e-test-worker",
            pools=pools,
            poll_interval=0.01,
            build_job=lambda job: default_build_job(
                job, runtime=runtime, profile=profile, render_node=None
            ),
        )

        # 1. Save the initial editorial state (there is no reel.yaml yet).
        initial_body = {
            "metadata": {"title": "Original Title"},
            "chapters": [{"name": "", "clips": ["clip.mp4"]}],
        }
        save = client.put(f"/api/v1/events/{encoded_id}/reel", json=initial_body)
        assert save.status_code == 200
        assert save.json()["staleness"]["stale"] is True  # no manifest yet

        # 2. Enqueue and render.
        enqueue = client.post("/api/v1/jobs", json={"event_id": EVENT_ID, "device": "cpu"})
        assert enqueue.status_code == 201
        assert worker.process_next() is True

        fresh_check = client.get(f"/api/v1/events/{encoded_id}")
        assert fresh_check.json()["staleness"]["stale"] is False
        # The date-less PUT resolves the folder's date (reel.yaml over folder name, D-2).
        original_output = default_output_dir(root) / "2024" / "2024-06-21 - Original Title.mp4"
        assert original_output.exists()

        # 3. Edit the title via a second save; the event goes stale citing editorial and
        #    the renamed movie, and nothing was rendered or enqueued by the write itself.
        edited_body = {**initial_body, "metadata": {"title": "Renamed Trip"}}
        edit = client.put(f"/api/v1/events/{encoded_id}/reel", json=edited_body)
        assert edit.status_code == 200
        verdict = edit.json()["staleness"]
        assert verdict["stale"] is True
        assert verdict["reasons"] == ["editorial", "output_renamed"]
        # The write itself never enqueues: no job is queued as a result of the save.
        jobs_after_edit = client.get("/api/v1/jobs").json()
        assert all(j["status"] != "queued" for j in jobs_after_edit)

        stale_check = client.get(f"/api/v1/events/{encoded_id}")
        assert stale_check.json()["staleness"]["stale"] is True
        assert stale_check.json()["staleness"]["reasons"] == ["editorial", "output_renamed"]
        original_stat = original_output.stat()

        # 4. Enqueue and render again; the output reflects the edited title.
        second_enqueue = client.post("/api/v1/jobs", json={"event_id": EVENT_ID, "device": "cpu"})
        assert second_enqueue.status_code == 201
        assert worker.process_next() is True

        final_check = client.get(f"/api/v1/events/{encoded_id}")
        assert final_check.json()["staleness"]["stale"] is False

        new_output = default_output_dir(root) / "2024" / "2024-06-21 - Renamed Trip.mp4"
        assert new_output.exists()
        # The previous movie is kept, untouched; the manifest records the new name.
        assert original_output.exists()
        assert (original_output.stat().st_size, original_output.stat().st_mtime_ns) == (
            original_stat.st_size,
            original_stat.st_mtime_ns,
        )
        manifest = read_manifest(root / EVENT_ID)
        assert manifest is not None
        assert manifest.output == "2024-06-21 - Renamed Trip.mp4"


def test_a_cancelled_render_after_a_rename_changes_nothing(
    tmp_path: Path,
    postgres_container: str,
    jobs_session_factory,
    runtime,
    make_clip,
) -> None:
    """A rename's render job cancelled while running: old movie, manifest and reason unchanged.

    The cancel is requested right after the worker claims the job, so the worker's
    cooperative check stops the render at its first segment boundary (D-S6).
    """
    root = tmp_path / "proj"
    (root / EVENT_ID).mkdir(parents=True)
    make_clip(f"proj/{EVENT_ID}/clip.mp4", width=320, height=240, duration=1.0)

    settings = resolve_api_settings(root, env={"DATABASE_URL": postgres_container})
    app = create_app(settings)
    encoded_id = quote(EVENT_ID, safe="/")

    inventory = detect_capabilities(runtime)
    profile = select_profile(inventory, override="cpu")
    pools = CapacityPools.from_inventory(inventory, gpu_cap=1, cpu_cap=1)

    with TestClient(app) as client:
        job_store: JobStore = app.state.job_store
        cancel_on_claim = False

        def build_job(job: Job):
            if cancel_on_claim:
                job_store.request_cancel(job.id)  # the job is running: only flagged
            return default_build_job(job, runtime=runtime, profile=profile, render_node=None)

        worker = Worker(
            job_store,
            worker_id="e2e-cancel-worker",
            pools=pools,
            poll_interval=0.01,
            build_job=build_job,
        )

        body = {
            "metadata": {"title": "Original Title"},
            "chapters": [{"name": "", "clips": ["clip.mp4"]}],
        }
        assert client.put(f"/api/v1/events/{encoded_id}/reel", json=body).status_code == 200
        assert (
            client.post("/api/v1/jobs", json={"event_id": EVENT_ID, "device": "cpu"}).status_code
            == 201
        )
        assert worker.process_next() is True
        original_output = default_output_dir(root) / "2024" / "2024-06-21 - Original Title.mp4"
        original_stat = original_output.stat()
        manifest_before = read_manifest(root / EVENT_ID)
        assert manifest_before is not None

        renamed = {**body, "metadata": {"title": "Renamed Trip"}}
        assert client.put(f"/api/v1/events/{encoded_id}/reel", json=renamed).status_code == 200
        enqueue = client.post("/api/v1/jobs", json={"event_id": EVENT_ID, "device": "cpu"})
        assert enqueue.status_code == 201
        cancel_on_claim = True
        assert worker.process_next() is True

        assert client.get(f"/api/v1/jobs/{enqueue.json()['id']}").json()["status"] == "canceled"
        new_output = default_output_dir(root) / "2024" / "2024-06-21 - Renamed Trip.mp4"
        assert not new_output.exists()
        assert not list(new_output.parent.glob("*.part"))
        assert (original_output.stat().st_size, original_output.stat().st_mtime_ns) == (
            original_stat.st_size,
            original_stat.st_mtime_ns,
        )
        assert read_manifest(root / EVENT_ID) == manifest_before
        verdict = client.get(f"/api/v1/events/{encoded_id}").json()["staleness"]
        assert verdict == {"stale": True, "reasons": ["editorial", "output_renamed"]}
