"""End-to-end test for the editorial write path (task 3.1, spec-driven change
``editorial-write-api``): save via ``PUT`` -> a subsequent read reports
``stale: editorial`` -> ``POST /jobs`` enqueues -> the worker renders the edited
state -> the event returns to fresh, with the rendered output reflecting the
edit (a new title -> a new output filename).

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
from auto_reel_ng.persistence.job_store import JobStore
from auto_reel_ng.scheduler.pools import CapacityPools
from auto_reel_ng.scheduler.worker import Worker, default_build_job

pytestmark = pytest.mark.requires_db

EVENT_ID = "2024/2024-06-21 - Trip"


def test_editorial_write_save_stale_render_cycle(
    tmp_path: Path,
    postgres_container: str,
    jobs_schema_engine,
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
        original_output = root / "output" / "Original Title.mp4"
        assert original_output.exists()

        # 3. Edit the title via a second save; the event goes stale citing editorial,
        #    and nothing was rendered or enqueued by the write itself.
        edited_body = {**initial_body, "metadata": {"title": "Renamed Trip"}}
        edit = client.put(f"/api/v1/events/{encoded_id}/reel", json=edited_body)
        assert edit.status_code == 200
        verdict = edit.json()["staleness"]
        assert verdict["stale"] is True
        assert "editorial" in verdict["reasons"]
        # The write itself never enqueues: no job is queued as a result of the save.
        jobs_after_edit = client.get("/api/v1/jobs").json()
        assert all(j["status"] != "queued" for j in jobs_after_edit)

        stale_check = client.get(f"/api/v1/events/{encoded_id}")
        assert stale_check.json()["staleness"]["stale"] is True

        # 4. Enqueue and render again; the output reflects the edited title.
        second_enqueue = client.post("/api/v1/jobs", json={"event_id": EVENT_ID, "device": "cpu"})
        assert second_enqueue.status_code == 201
        assert worker.process_next() is True

        final_check = client.get(f"/api/v1/events/{encoded_id}")
        assert final_check.json()["staleness"]["stale"] is False

        new_output = root / "output" / "Renamed Trip.mp4"
        assert new_output.exists()
