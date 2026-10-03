"""Experiment 007: is a GPU render slower while a proxy job runs beside it?

Drives a real ``auto-reel worker`` (real GPU, real ffmpeg) through the job queue. Arm A: one render of
event R alone. Arm B: three proxy jobs (events P1..P3, cache emptied first) are queued, and once the
first is running a render of R is queued; the render's wall time is ``finished_at - started_at`` of its
row. Arms alternate A,B,A,B,... so a drifting host load hits both. Run through ``run.sh``.
"""

from __future__ import annotations

import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

from auto_reel_ng.persistence.config import resolve_database_url
from auto_reel_ng.persistence.engine import make_engine, make_session_factory
from auto_reel_ng.persistence.job_store import JobStore
from auto_reel_ng.persistence.models import JobKind, JobStatus

LIB = Path(sys.argv[1])
CACHE = Path(sys.argv[2])
REPS = int(sys.argv[3])
RENDER_EVENT = "2024/2024-06-27 - Render"
PROXY_EVENTS = ["2024/2024-07-01 - ProxyA", "2024/2024-07-02 - ProxyB", "2024/2024-07-03 - ProxyC"]
TERMINAL = {JobStatus.DONE, JobStatus.FAILED, JobStatus.CANCELED}

store = JobStore(make_session_factory(make_engine(resolve_database_url(LIB))))


def wait(job_id, states, timeout=900.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        job = store.get(job_id)
        if job.status in states:
            return job
        time.sleep(0.05)
    raise SystemExit(f"timeout waiting for {job_id}")


def evict_page_cache() -> None:
    """Drop the sources from the page cache (no root needed: DONTNEED on a file we can open)."""
    for path in LIB.rglob("*"):
        if path.suffix.lower() in (".mp4", ".mov"):
            fd = os.open(path.resolve(), os.O_RDONLY)
            try:
                os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)
            finally:
                os.close(fd)


def clear_proxy_cache() -> None:
    subprocess.run(["rm", "-rf", str(CACHE)], check=True)


def render_alone(cold: bool) -> dict:
    if cold:
        evict_page_cache()
    job = wait(store.enqueue(str(LIB), RENDER_EVENT, force=True), TERMINAL)
    assert job.status == JobStatus.DONE, job.error
    return {
        "arm": "alone",
        "cold": cold,
        "render_s": (job.finished_at - job.started_at).total_seconds(),
    }


def render_beside_proxy(cold: bool) -> dict:
    clear_proxy_cache()
    if cold:
        evict_page_cache()
    proxies = [store.enqueue(str(LIB), event, kind=JobKind.PROXY) for event in PROXY_EVENTS]
    wait(proxies[0], {JobStatus.RUNNING, *TERMINAL})
    render_id = store.enqueue(str(LIB), RENDER_EVENT, force=True)
    render = wait(render_id, TERMINAL)
    assert render.status == JobStatus.DONE, render.error
    snapshot = [store.get(p) for p in proxies]
    # How much of the render's window the proxy work covered: running or finished after it began.
    beside = [(p.status.value, round(p.progress, 2)) for p in snapshot]
    for p in proxies:  # let the proxy jobs finish so the next run starts clean
        wait(p, TERMINAL)
    done = [store.get(p) for p in proxies]
    assert all(p.status == JobStatus.DONE for p in done), [p.error for p in done]
    first_started = min(p.started_at for p in done)
    overlap = (
        min(render.finished_at, max(p.finished_at for p in done))
        - max(render.started_at, first_started)
    ).total_seconds()
    return {
        "arm": "beside_proxy",
        "cold": cold,
        "render_s": (render.finished_at - render.started_at).total_seconds(),
        "overlap_s": round(overlap, 1),
        "proxies_at_render_end": beside,
        "proxy_total_s": round(
            (max(p.finished_at for p in done) - first_started).total_seconds(), 1
        ),
    }


results = []
render_alone(cold=False)  # warm-up: the first run pays for file caches and the self-test
for rep in range(REPS):
    results.append(render_alone(cold=False))
    results.append(render_beside_proxy(cold=False))
results.append(render_alone(cold=True))
results.append(render_beside_proxy(cold=True))
print(json.dumps(results, indent=1))
for arm in ("alone", "beside_proxy"):
    warm = [r["render_s"] for r in results if r["arm"] == arm and not r["cold"]]
    print(
        arm, "warm runs", [round(x, 1) for x in warm], "median", round(statistics.median(warm), 1)
    )
