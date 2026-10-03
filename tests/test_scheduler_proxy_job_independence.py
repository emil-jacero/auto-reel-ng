"""A ``proxy`` job is invisible to the staleness contract and coexists with a render of the same
event (proxy-job): no verdict, manifest, fingerprint or event file changes, the render graph
version is untouched, and a failed proxy job does not disturb a running render (real Postgres).
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any, Dict, Tuple

import pytest
from test_scheduler_proxy_worker import Fixture, wait_until

from auto_reel_ng.config import default_output_dir, load_project_config
from auto_reel_ng.errors import ProxyError
from auto_reel_ng.event.metadata import load_event_document
from auto_reel_ng.persistence.job_store import JobStore
from auto_reel_ng.persistence.models import JobStatus
from auto_reel_ng.render import RenderJob, RenderResult, output_relpath
from auto_reel_ng.staleness.fingerprint import (
    RENDER_GRAPH_VERSION,
    Fingerprint,
    compute_fingerprint,
    engine_identity,
)
from auto_reel_ng.staleness.gate import Verdict, evaluate
from auto_reel_ng.staleness.manifest import manifest_path, write_manifest

pytestmark = pytest.mark.requires_db

FFMPEG = (7, 1)


def fingerprint_of(root: Path, rel: str) -> Tuple[Fingerprint, Path]:
    """The event's current fingerprint and the movie path its metadata names."""
    config = load_project_config(root)
    event_dir = root / rel
    document, _ = load_event_document(event_dir, order=config.sort)
    movie = default_output_dir(root) / output_relpath(document.metadata)
    return (
        compute_fingerprint(document, event_dir=event_dir, look_defaults={}, ffmpeg_version=FFMPEG),
        movie,
    )


def render_it(root: Path, rel: str) -> None:
    """Make the event fresh: a manifest of its fingerprint and its movie on disk."""
    fingerprint, movie = fingerprint_of(root, rel)
    write_manifest(
        root / rel,
        fingerprint,
        output=movie.name,
        engine_identity=engine_identity(FFMPEG),
    )
    movie.parent.mkdir(parents=True, exist_ok=True)
    movie.write_bytes(b"rendered")


def verdict(root: Path, rel: str) -> Verdict:
    fingerprint, movie = fingerprint_of(root, rel)
    return evaluate(root / rel, movie, fingerprint)


def snapshot(directory: Path) -> Dict[str, Any]:
    return {
        str(p.relative_to(directory)): (p.stat().st_mtime_ns, p.stat().st_size)
        for p in sorted(directory.rglob("*"))
    }


@pytest.fixture
def fx(job_store: JobStore, tmp_path: Path) -> Fixture:
    return Fixture(job_store, tmp_path)


def test_the_render_graph_version_is_the_one_before_this_change() -> None:
    """Proxies are derived state no render reads: they bumped nothing (4, 5 for fonts, then 6 for clip-rotate-engine)."""
    assert RENDER_GRAPH_VERSION == 7


def test_a_proxy_job_changes_neither_the_verdict_nor_the_manifest_nor_the_event(
    fx: Fixture,
) -> None:
    rel = fx.event("fresh", clips=("a.mp4", "b.mp4"))
    render_it(fx.root, rel)
    assert verdict(fx.root, rel).stale is False
    manifest_before = manifest_path(fx.root / rel).read_bytes()
    event_before = snapshot(fx.root / rel)
    fingerprint_before, _ = fingerprint_of(fx.root, rel)
    job_id = fx.proxy(rel)

    def prepare(clip: Path, **kwargs: Any) -> Any:  # writes into the cache like the real one
        entry = fx.cache / f"entry-{clip.name}"
        entry.mkdir(parents=True, exist_ok=True)
        (entry / "proxy.mp4").write_bytes(b"proxy")
        kwargs["on_progress"](1.0)
        return object()

    assert fx.worker(prepare=prepare).process_next() is True

    assert fx.status(job_id) == JobStatus.DONE
    assert sorted(p.name for p in fx.cache.iterdir()) == ["entry-a.mp4", "entry-b.mp4"]
    fingerprint_after, _ = fingerprint_of(fx.root, rel)
    assert fingerprint_after == fingerprint_before  # identical with and without a proxy cache
    assert verdict(fx.root, rel).stale is False
    assert manifest_path(fx.root / rel).read_bytes() == manifest_before
    assert snapshot(fx.root / rel) == event_before


def test_a_proxy_job_for_a_stale_event_leaves_it_stale_and_is_not_completed_early(
    fx: Fixture,
) -> None:
    rel = fx.event("stale")
    assert verdict(fx.root, rel).stale is True
    job_id = fx.proxy(rel)

    assert fx.worker().process_next() is True

    assert fx.status(job_id) == JobStatus.DONE
    assert fx.prepared == ["stale/a.mp4"]  # the clips were prepared, not skipped as fresh
    assert verdict(fx.root, rel).stale is True


def test_a_proxy_job_for_a_fresh_event_still_prepares_its_clips(fx: Fixture) -> None:
    rel = fx.event("fresh")
    render_it(fx.root, rel)
    job_id = fx.proxy(rel)

    assert fx.worker().process_next() is True

    assert fx.status(job_id) == JobStatus.DONE
    assert fx.prepared == ["fresh/a.mp4"]  # not completed as "fresh at claim time"


def test_a_render_and_a_proxy_job_of_one_event_are_both_accepted_and_both_end_done(
    fx: Fixture,
) -> None:
    rel = fx.event("both")
    render_id = fx.render(rel)
    proxy_id = fx.proxy(rel)
    assert render_id != proxy_id
    worker = fx.worker()

    assert worker.process_next() and worker.process_next()

    assert (fx.status(render_id), fx.status(proxy_id)) == (JobStatus.DONE, JobStatus.DONE)
    assert fx.renders == [rel] and fx.prepared == ["both/a.mp4"]


def test_a_proxy_job_waits_for_a_running_render_and_its_failure_leaves_the_render_untouched(
    fx: Fixture,
) -> None:
    rel = fx.event("busy")
    render_release = threading.Event()
    render_started = threading.Event()
    rendered: list[str] = []

    def prepare(clip: Path, **kwargs: Any) -> Any:
        raise ProxyError(str(clip), "no video stream")

    def slow_render(render_job: RenderJob) -> RenderResult:
        render_started.set()
        render_release.wait(timeout=20)
        rendered.append(render_job.plan.metadata.title or "")
        return RenderResult(output_path=fx.tmp_path / "o.mp4")

    worker = fx.worker(prepare=prepare, render_fn=slow_render)
    render_id = fx.render(rel)
    thread = fx.start(worker)
    assert render_started.wait(timeout=10)
    proxy_id = fx.proxy(rel)

    wait_until(lambda: fx.status(proxy_id) == JobStatus.RUNNING)  # claimed, and yielding
    time.sleep(1.5)  # longer than the yield's poll

    assert fx.status(proxy_id) == JobStatus.RUNNING  # no clip was started while the render runs
    assert fx.status(render_id) == JobStatus.RUNNING
    render_release.set()
    wait_until(lambda: fx.status(render_id) == JobStatus.DONE)
    wait_until(lambda: fx.status(proxy_id) == JobStatus.FAILED, timeout=15)  # then it fails alone
    fx.stop.set()
    thread.join(timeout=5)
    assert rendered == [rel]
