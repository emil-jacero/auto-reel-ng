"""Tests for the clip thumbnail endpoint (D-11, api-service "Clip thumbnail endpoint").

Three layers, as the route is built:

- ``events_read.thumbnail_source``: which clips have a thumbnail (discovery's own
  listing, matched exactly) and where it is cached. No database, no ffmpeg: clips are
  plain files, and ``thumbs.thumbnail_path`` needs only a stat.
- ``api.thumbnails.ThumbnailGate``: at most two extractions, one per cache key,
  driven directly with a blocking fake extraction.
- the route itself, on an app whose database URL points at a closed port (the route
  never needs it), with ``thumbnail_for`` replaced by a fake that writes a fixed JPEG
  at the real cache path; the last test runs the real engine over a read-only library.
"""

from __future__ import annotations

import asyncio
import gc
import json
import logging
import os
import shutil
import stat
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Dict, Iterator, List, Optional, Tuple
from urllib.parse import quote

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from auto_reel_ng.api import events_read
from auto_reel_ng.api.app import create_app
from auto_reel_ng.api.routes import events as events_routes
from auto_reel_ng.api.schemas import EventFailure
from auto_reel_ng.api.settings import ApiSettings, resolve_api_settings
from auto_reel_ng.api.thumbnails import MAX_CONCURRENT_EXTRACTIONS, ThumbnailGate
from auto_reel_ng.config.project import ConfigError
from auto_reel_ng.errors import ProbeError, ThumbnailCacheError, ThumbnailError
from auto_reel_ng.event.discovery import DiskListing
from auto_reel_ng.ffmpeg.runtime import FfmpegRuntime
from auto_reel_ng.thumbs import thumbnail as thumbnail_module
from auto_reel_ng.thumbs import thumbnail_for as engine_thumbnail_for
from auto_reel_ng.thumbs import thumbnail_path

#: A closed port, as the schema dump uses: the thumbnail route must never need it.
UNREACHABLE_DATABASE_URL = "postgresql+psycopg://thumbs:thumbs@127.0.0.1:1/thumbs"

GRILLNING = "2024/2024-06-27 - Grillning med grannar"
# Constant bytes that are no media container: ffprobe exits non-zero on them every time, unlike
# random bytes, about 1 in 300 of which some demuxer accepts.
NOT_MEDIA = b"This is not a media file.\n" * 800
KALAS = "2024/2024-07-14 - Kalas"
TJORN = "2024/2024-08-20 - Två kapitel - Tjörn"
SOMMARLOV = "2024/2024-09-01 - Sommarlov"
SKILJETECKEN = "2024/2024-09-10 - Skiljetecken"
TRASIG_YAML = "2024/2024-09-15 - Trasig yaml"
IGNORED_EVENT = "2024/2024-09-20 - Aldrig"  # holds .reelignore: not an event of the list

#: A chapter-folder identity with spaces, punctuation, a ``+`` and Swedish letters.
PUNCTUATED = "Kväll, del 2/a+b & c #1.mp4"

#: The Sommarlov document of ``tests/test_cli_thumbs.py``: one MISSING clip.
SOMMARLOV_REEL = """\
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

#: Tjörn: a root chapter and ``Kvällen/``, with the root ``s1710004.mp4`` IGNORED.
TJORN_REEL = """\
version: 0
metadata:
  title: Två kapitel
  date: 2024-08-20
  location: Tjörn
chapters:
  - name: ''
    clips:
      - s1710001.mp4
  - name: Kvällen
    clips:
      - Kvällen/s1710002.mp4
      - Kvällen/s1710003.mp4
ignore:
  - s1710004.mp4
"""

#: The fake extraction's output: a JPEG's start and end markers around a payload.
FAKE_JPEG = b"\xff\xd8\xff\xe0fake thumbnail\xff\xd9"

CACHE_CONTROL = "private, max-age=86400"


def _write(path: Path, data: bytes = b"") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _write_config(root: Path, cache_dir: Path, *, position: Optional[object] = None) -> None:
    """``config.yaml`` with ``thumbnails.cache_dir`` outside the project (JSON is YAML)."""
    thumbnails: Dict[str, object] = {"cache_dir": str(cache_dir)}
    if position is not None:
        thumbnails["position"] = position
    (root / "config.yaml").write_text(json.dumps({"thumbnails": thumbnails}), encoding="utf-8")


def _skip_as_root() -> None:
    if os.geteuid() == 0:
        pytest.skip("root ignores directory permissions")


@pytest.fixture
def cache_dir(tmp_path: Path) -> Path:
    """Outside the project: ``clip-thumbnails`` refuses a cache inside the project root."""
    return tmp_path / "cache"


@pytest.fixture
def project(tmp_path: Path, cache_dir: Path) -> Path:
    """A year-event library shaped like the dev library, plus the lookup's edge cases."""
    root = tmp_path / "proj"
    for name in ("s1710001.mp4", "s1710002.mp4", "s1710003.mp4", "s1710004.mp4"):
        _write(root / GRILLNING / name, f"grill {name}".encode())

    _write(root / KALAS / "s1710001.mp4", b"kalas")
    _write(root / GRILLNING / "original" / "x.mp4", b"original of grill")
    _write(root / IGNORED_EVENT / "s1710001.mp4", b"never rendered")
    _write(root / IGNORED_EVENT / ".reelignore")

    tjorn = root / TJORN
    for identity in (
        "s1710001.mp4",
        "s1710004.mp4",
        "Kvällen/s1710002.mp4",
        "Kvällen/s1710003.mp4",
    ):
        _write(tjorn / identity, f"tjorn {identity}".encode())
    (tjorn / "reel.yaml").write_text(TJORN_REEL, encoding="utf-8")
    _write(tjorn / "original" / "x.mp4", b"original")
    _write(tjorn / "Original" / "x.mp4", b"Original")
    _write(tjorn / "Utelämnad" / "y.mp4", b"ignored folder")
    _write(tjorn / "Utelämnad" / ".reelignore")
    (tjorn / "dangling.mp4").symlink_to(tmp_path / "nowhere.mp4")

    sommarlov = root / SOMMARLOV
    _write(sommarlov / "s1710002.mp4", b"sommar 2")
    _write(sommarlov / "s1710004.mp4", b"sommar 4")
    (sommarlov / "reel.yaml").write_text(SOMMARLOV_REEL, encoding="utf-8")

    _write(root / SKILJETECKEN / PUNCTUATED, b"punctuated")

    _write(root / TRASIG_YAML / "s1710001.mp4", b"broken yaml")
    (root / TRASIG_YAML / "reel.yaml").write_text("version: 0\nchapters: [\n", encoding="utf-8")

    _write_config(root, cache_dir)
    return root


@pytest.fixture
def settings(project: Path) -> ApiSettings:
    return resolve_api_settings(project, env={"DATABASE_URL": UNREACHABLE_DATABASE_URL})


def _event_dir(project: Path, event: str) -> Path:
    """The event folder as the events list names it (``listed_event_dir``)."""
    return project / event


# --- task 2.2: which clips have a thumbnail ---------------------------------


@pytest.mark.parametrize(
    ("event", "clip"),
    [
        (GRILLNING, "s1710001.mp4"),
        (TJORN, "Kvällen/s1710002.mp4"),
        (TJORN, "s1710004.mp4"),  # IGNORED by the document, still on disk
        (SKILJETECKEN, PUNCTUATED),
    ],
)
def test_a_listed_clip_resolves_to_its_cache_entry(
    settings: ApiSettings, project: Path, cache_dir: Path, event: str, clip: str
) -> None:
    source = events_read.thumbnail_source(settings, event, clip)

    assert source.clip_path == _event_dir(project, event) / clip
    assert source.position == 0.25
    assert source.cache_dir == cache_dir
    assert source.cache_path == thumbnail_path(source.clip_path, position=0.25, cache_dir=cache_dir)
    assert source.cache_path.parent == cache_dir
    assert source.etag == f'"{source.cache_path.stem}"'
    assert not cache_dir.exists()  # computed only: nothing created or generated


@pytest.mark.parametrize(
    ("event", "clip"),
    [
        (SOMMARLOV, "borttagen.mp4"),  # MISSING: the document names it, disk lacks it
        (TJORN, "original/x.mp4"),
        (TJORN, "Original/x.mp4"),
        (TJORN, "Utelämnad/y.mp4"),  # a chapter folder holding .reelignore
        (TJORN, "dangling.mp4"),
        (TJORN, "Kvällen/../s1710001.mp4"),  # normalizes to a clip, but is not its identity
        (KALAS, "../other/x.mp4"),
        (KALAS, "../2024-06-27 - Grillning med grannar/s1710001.mp4"),
        (TJORN, ""),
    ],
)
def test_an_identity_discovery_does_not_list_is_not_found(
    settings: ApiSettings, event: str, clip: str
) -> None:
    with pytest.raises(events_read.ClipNotFoundError):
        events_read.thumbnail_source(settings, event, clip)


def test_an_absolute_path_is_not_an_identity(settings: ApiSettings, project: Path) -> None:
    absolute = str(_event_dir(project, TJORN) / "s1710001.mp4")
    with pytest.raises(events_read.ClipNotFoundError):
        events_read.thumbnail_source(settings, TJORN, absolute)


def test_an_unknown_event_is_not_found(settings: ApiSettings) -> None:
    with pytest.raises(events_read.EventNotFoundError):
        events_read.thumbnail_source(settings, "2024/2024-12-24 - Finns inte", "s1710001.mp4")


@pytest.mark.parametrize(
    ("event_id", "clip"),
    [
        ("", "2024/2024-06-27 - Grillning med grannar/s1710001.mp4"),  # the project root
        ("2024", "2024-06-27 - Grillning med grannar/s1710001.mp4"),  # a year folder
        (f"{GRILLNING}/original", "x.mp4"),  # an event's originals
        (f"{TJORN}/Kvällen", "s1710002.mp4"),  # a chapter folder
        (IGNORED_EVENT, "s1710001.mp4"),  # .reelignore: the layout skips it
        (f"{GRILLNING}/", "s1710001.mp4"),  # not the list's spelling of the id
        (f"2024/../{GRILLNING}", "s1710001.mp4"),
    ],
)
def test_a_directory_the_events_list_does_not_show_is_not_an_event(
    settings: ApiSettings, event_id: str, clip: str
) -> None:
    with pytest.raises(events_read.EventNotFoundError):
        events_read.thumbnail_source(settings, event_id, clip)


def test_an_unlistable_event_folder_is_unreadable_disk(
    settings: ApiSettings, project: Path
) -> None:
    _skip_as_root()
    event_dir = project / GRILLNING
    event_dir.chmod(0)
    try:
        with pytest.raises(events_read.EventReadError) as caught:
            events_read.thumbnail_source(settings, GRILLNING, "s1710001.mp4")
    finally:
        event_dir.chmod(0o755)
    assert caught.value.failure is EventFailure.UNREADABLE_DISK


def test_config_is_read_only_for_a_request_that_can_be_answered(
    settings: ApiSettings, project: Path, cache_dir: Path
) -> None:
    """A bad ``thumbnails.position`` fails a listed clip; an unlisted one stays a 404."""
    _write_config(project, cache_dir, position=1.5)
    with pytest.raises(ConfigError, match="thumbnails.position"):
        events_read.thumbnail_source(settings, GRILLNING, "s1710001.mp4")
    with pytest.raises(events_read.ClipNotFoundError):
        events_read.thumbnail_source(settings, SOMMARLOV, "borttagen.mp4")


def _vanish_after_listing(monkeypatch: pytest.MonkeyPatch, event_dir: Path, clip: str) -> None:
    """Delete ``clip`` between discovery's listing and the stat: a real race, replayed."""
    real_scan_event = events_read.scan_event

    def scan_then_delete(directory: Path) -> DiskListing:
        listing = real_scan_event(directory)
        (event_dir / clip).unlink()
        return listing

    monkeypatch.setattr(events_read, "scan_event", scan_then_delete)


def test_a_clip_that_vanishes_after_the_listing_is_a_thumbnail_error(
    settings: ApiSettings, project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    event_dir = _event_dir(project, GRILLNING)
    _vanish_after_listing(monkeypatch, event_dir, "s1710002.mp4")

    with pytest.raises(ThumbnailError) as caught:
        events_read.thumbnail_source(settings, GRILLNING, "s1710002.mp4")

    assert str(caught.value).startswith(str(event_dir / "s1710002.mp4"))
    assert "cannot stat the clip" in str(caught.value)
    assert caught.value.reason == "cannot stat the clip: No such file or directory"
    assert isinstance(caught.value.__cause__, FileNotFoundError)


def test_an_unparseable_reel_yaml_does_not_stop_a_clip(settings: ApiSettings) -> None:
    """A thumbnail is a fact of the clip file: ``reel.yaml`` is never read."""
    source = events_read.thumbnail_source(settings, TRASIG_YAML, "s1710001.mp4")
    assert source.clip_path.name == "s1710001.mp4"


# --- task 2.3: the gate ------------------------------------------------------


class BlockingExtract:
    """Fake extractions that block until released and record how many ran at once."""

    def __init__(self) -> None:
        self.release = threading.Event()
        self.calls = 0
        self.running = 0
        self.max_running = 0
        self._lock = threading.Lock()

    def make(self, result: Path, error: Optional[Exception] = None) -> Callable[[], Path]:
        def extract() -> Path:
            with self._lock:
                self.calls += 1
                self.running += 1
                self.max_running = max(self.max_running, self.running)
            try:
                if not self.release.wait(timeout=10):
                    raise TimeoutError("the fake extraction was never released")
                if error is not None:
                    raise error
                return result
            finally:
                with self._lock:
                    self.running -= 1

        return extract


async def _until(predicate: Callable[[], bool], timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while not predicate():
        assert time.monotonic() < deadline, "condition not reached in time"
        await asyncio.sleep(0.005)


def _in_flight(gate: ThumbnailGate) -> Dict[str, "asyncio.Task[Path]"]:
    return gate._in_flight  # pylint: disable=protected-access


async def test_at_most_two_extractions_run_at_once() -> None:
    gate = ThumbnailGate()
    fake = BlockingExtract()
    keys = [f"key{i}" for i in range(6)]
    waiters = [
        asyncio.create_task(gate.produce(key, fake.make(Path(f"{key}.jpg")))) for key in keys
    ]

    await _until(lambda: fake.running == 2)
    await asyncio.sleep(0.05)  # room for a third to start, which it must not
    assert fake.running == 2
    fake.release.set()

    assert await asyncio.gather(*waiters) == [Path(f"{key}.jpg") for key in keys]
    assert fake.max_running == MAX_CONCURRENT_EXTRACTIONS == 2
    assert fake.calls == 6
    assert _in_flight(gate) == {}


async def test_concurrent_waiters_for_one_key_share_one_extraction() -> None:
    gate = ThumbnailGate()
    fake = BlockingExtract()
    waiters = [
        asyncio.create_task(gate.produce("same", fake.make(Path("same.jpg")))) for _ in range(5)
    ]
    await _until(lambda: fake.running == 1)
    await asyncio.sleep(0.02)
    fake.release.set()

    assert await asyncio.gather(*waiters) == [Path("same.jpg")] * 5
    assert fake.calls == 1
    assert _in_flight(gate) == {}


async def test_a_failed_extraction_fails_every_waiter_and_is_retried() -> None:
    gate = ThumbnailGate()
    fake = BlockingExtract()
    boom = RuntimeError("no frame")
    waiters = [
        asyncio.create_task(gate.produce("bad", fake.make(Path("bad.jpg"), error=boom)))
        for _ in range(3)
    ]
    await _until(lambda: fake.running == 1)
    fake.release.set()

    outcomes = await asyncio.gather(*waiters, return_exceptions=True)
    assert outcomes == [boom, boom, boom]
    assert fake.calls == 1
    assert _in_flight(gate) == {}

    assert await gate.produce("bad", fake.make(Path("bad.jpg"))) == Path("bad.jpg")
    assert fake.calls == 2
    assert _in_flight(gate) == {}


async def test_a_cancelled_waiter_leaves_the_shared_extraction_running() -> None:
    gate = ThumbnailGate()
    fake = BlockingExtract()
    first = asyncio.create_task(gate.produce("clip", fake.make(Path("clip.jpg"))))
    await _until(lambda: fake.running == 1)
    second = asyncio.create_task(gate.produce("clip", fake.make(Path("other.jpg"))))
    await asyncio.sleep(0.02)

    first.cancel()
    await asyncio.gather(first, return_exceptions=True)
    assert first.cancelled()
    extraction = _in_flight(gate)["clip"]
    assert not extraction.cancelled()

    fake.release.set()
    assert await second == Path("clip.jpg")
    assert fake.calls == 1
    assert _in_flight(gate) == {}


async def test_an_abandoned_failing_extraction_logs_no_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """No "exception was never retrieved" and no "exception in shielded future"."""
    caplog.set_level(logging.DEBUG)
    gate = ThumbnailGate()
    fake = BlockingExtract()
    only = asyncio.create_task(
        gate.produce("gone", fake.make(Path("gone.jpg"), error=RuntimeError("no frame")))
    )
    await _until(lambda: fake.running == 1)
    only.cancel()
    await asyncio.gather(only, return_exceptions=True)
    # The waiter's CancelledError traceback holds ``produce``'s frame, and with it the
    # extraction task: drop it, so the task is collected (and would log) within the test.
    del only

    fake.release.set()
    await _until(lambda: _in_flight(gate) == {})
    await asyncio.sleep(0.02)
    gc.collect()
    await asyncio.sleep(0.02)

    assert [record for record in caplog.records if record.levelno >= logging.ERROR] == []


# --- tasks 3.1-3.2: the route ------------------------------------------------


class FakeThumbnailFor:
    """Stands in for ``thumbs.thumbnail_for``: writes ``FAKE_JPEG`` at the real cache path.

    ``release`` holds an extraction until set (set by default); ``error`` makes every
    call raise it; ``redirect_key`` writes and returns ``<key>.jpg`` for another key,
    as when the clip changed between the lookup and the extraction.
    """

    def __init__(self) -> None:
        self.calls: List[Path] = []
        self.runtimes: List[Optional[FfmpegRuntime]] = []
        self.error: Optional[Exception] = None
        self.redirect_key: Optional[str] = None
        self.release = threading.Event()
        self.release.set()
        self.running = 0
        self.max_running = 0
        self._lock = threading.Lock()

    def __call__(
        self,
        clip_path: Path,
        *,
        position: float,
        cache_dir: Path,
        runtime: Optional[FfmpegRuntime] = None,
    ) -> Path:
        with self._lock:
            self.calls.append(clip_path)
            self.runtimes.append(runtime)
            self.running += 1
            self.max_running = max(self.max_running, self.running)
        try:
            if not self.release.wait(timeout=10):
                raise TimeoutError("the fake extraction was never released")
            if self.error is not None:
                raise self.error
            target = thumbnail_path(clip_path, position=position, cache_dir=cache_dir)
            if self.redirect_key is not None:
                target = target.with_name(f"{self.redirect_key}.jpg")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(FAKE_JPEG)
            return target
        finally:
            with self._lock:
                self.running -= 1


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> FakeThumbnailFor:
    fake_thumbnail_for = FakeThumbnailFor()
    monkeypatch.setattr(events_routes, "thumbnail_for", fake_thumbnail_for)
    return fake_thumbnail_for


@pytest.fixture
def app(settings: ApiSettings) -> FastAPI:
    return create_app(settings)


@pytest.fixture
def client(app: FastAPI, fake: FakeThumbnailFor) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


def _url(event: str, clip: str, *, safe: str = "", **params: str) -> str:
    """The route's URL: the event id per-segment encoded, ``clip`` as a query value."""
    query = f"clip={quote(clip, safe=safe)}"
    for name, value in params.items():
        query += f"&{name}={quote(value, safe='')}"
    return f"/api/v1/events/{quote(event, safe='/')}/thumbnail?{query}"


def _cache_path(project: Path, cache_dir: Path, event: str, clip: str) -> Path:
    return thumbnail_path(_event_dir(project, event) / clip, position=0.25, cache_dir=cache_dir)


def _assert_no_caching_headers(response: object) -> None:
    headers = response.headers  # type: ignore[attr-defined]
    assert "cache-control" not in headers
    assert "etag" not in headers


def test_a_thumbnail_is_served_then_read_from_the_cache(
    client: TestClient, fake: FakeThumbnailFor
) -> None:
    first = client.get(_url(GRILLNING, "s1710001.mp4"))
    assert first.status_code == 200
    assert first.headers["content-type"] == "image/jpeg"
    assert first.content == FAKE_JPEG
    assert len(fake.calls) == 1

    second = client.get(_url(GRILLNING, "s1710001.mp4"))
    assert second.status_code == 200
    assert second.content == first.content
    assert second.headers["etag"] == first.headers["etag"]
    assert len(fake.calls) == 1


def test_the_version_parameter_changes_nothing(client: TestClient, fake: FakeThumbnailFor) -> None:
    plain = client.get(_url(GRILLNING, "s1710001.mp4"))
    dated = client.get(_url(GRILLNING, "s1710001.mp4", v="2024-06-27T14:03:11.123456Z"))
    other = client.get(_url(GRILLNING, "s1710001.mp4", v="other"))
    for response in (dated, other):
        assert response.status_code == 200
        assert response.content == plain.content
        assert response.headers["etag"] == plain.headers["etag"]
    assert len(fake.calls) == 1  # the first request; no second extraction


def test_the_extraction_uses_the_services_runtime(
    client: TestClient, app: FastAPI, fake: FakeThumbnailFor
) -> None:
    assert client.get(_url(GRILLNING, "s1710001.mp4")).status_code == 200
    assert fake.runtimes == [app.state.runtime]


def test_identities_arrive_as_the_detail_lists_them(client: TestClient) -> None:
    assert client.get(_url(TJORN, "Kvällen/s1710002.mp4")).status_code == 200
    assert client.get(_url(TJORN, "s1710004.mp4")).status_code == 200  # IGNORED, on disk
    assert client.get(_url(SKILJETECKEN, PUNCTUATED)).status_code == 200
    # A literal ``+`` in a query value reads as a space: ``a b & c #1.mp4`` is not listed.
    plus = client.get(_url(SKILJETECKEN, PUNCTUATED, safe="+"))
    assert plus.status_code == 404
    assert plus.json()["event_id"] == SKILJETECKEN


def test_not_found_and_a_missing_clip_parameter(client: TestClient, fake: FakeThumbnailFor) -> None:
    missing = client.get(_url(SOMMARLOV, "borttagen.mp4"))
    assert missing.status_code == 404
    assert missing.json()["event_id"] == SOMMARLOV
    assert "borttagen.mp4" in missing.json()["detail"]

    unknown = "2024/2024-12-24 - Finns inte"
    gone = client.get(_url(unknown, "s1710001.mp4"))
    assert gone.status_code == 404
    assert gone.json()["event_id"] == unknown

    no_clip = client.get(f"/api/v1/events/{quote(GRILLNING, safe='/')}/thumbnail")
    assert no_clip.status_code == 422
    for response in (missing, gone, no_clip):
        _assert_no_caching_headers(response)
    assert fake.calls == []


def test_folders_that_are_not_events_answer_404(client: TestClient, fake: FakeThumbnailFor) -> None:
    year = client.get(_url("2024", "2024-06-27 - Grillning med grannar/s1710001.mp4"))
    originals = client.get(_url(f"{GRILLNING}/original", "x.mp4"))
    for response, event_id in ((year, "2024"), (originals, f"{GRILLNING}/original")):
        assert response.status_code == 404
        assert response.json()["event_id"] == event_id
        _assert_no_caching_headers(response)
    assert fake.calls == []


def test_an_engine_failure_is_the_thumbnail_kind(
    client: TestClient, fake: FakeThumbnailFor, project: Path, caplog: pytest.LogCaptureFixture
) -> None:
    clip_path = _event_dir(project, GRILLNING) / "s1710001.mp4"
    fake.error = ThumbnailError(str(clip_path), "no frame extracted at 0.250s of 1.000s")

    response = client.get(_url(GRILLNING, "s1710001.mp4"))

    assert response.status_code == 502
    body = response.json()
    assert body["thumbnail_failure"] == "thumbnail_failed"
    assert "failure" not in body
    assert body["event_id"] == GRILLNING
    # The identity and the path-free reason: no server path in the detail.
    assert body["detail"] == "s1710001.mp4: no frame extracted at 0.250s of 1.000s"
    assert str(project) not in body["detail"]
    _assert_no_caching_headers(response)
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert f"thumbnail: {GRILLNING}: {body['detail']}" in warnings


def test_a_clip_that_vanishes_mid_request_is_the_thumbnail_kind(
    client: TestClient, fake: FakeThumbnailFor, project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _vanish_after_listing(monkeypatch, _event_dir(project, GRILLNING), "s1710002.mp4")

    response = client.get(_url(GRILLNING, "s1710002.mp4"))

    assert response.status_code == 502
    body = response.json()
    assert body["thumbnail_failure"] == "thumbnail_failed"
    assert "failure" not in body
    assert body["detail"] == "s1710002.mp4: cannot stat the clip: No such file or directory"
    assert fake.calls == []


def test_a_cache_failure_has_no_kind(
    client: TestClient, fake: FakeThumbnailFor, cache_dir: Path, caplog: pytest.LogCaptureFixture
) -> None:
    fake.error = ThumbnailCacheError(
        f"{cache_dir}: cannot write thumbnails: [Errno 30] Read-only file system"
    )

    response = client.get(_url(GRILLNING, "s1710001.mp4"))

    assert response.status_code == 502
    body = response.json()
    assert str(cache_dir) in body["detail"]
    assert "Read-only file system" in body["detail"]
    assert "failure" not in body
    assert "thumbnail_failure" not in body
    _assert_no_caching_headers(response)
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert f"thumbnail: {GRILLNING}: s1710001.mp4: {body['detail']}" in warnings


def test_an_unlistable_event_folder_is_unreadable_disk_over_http(
    client: TestClient, project: Path
) -> None:
    _skip_as_root()
    event_dir = project / GRILLNING
    event_dir.chmod(0)
    try:
        response = client.get(_url(GRILLNING, "s1710001.mp4"))
    finally:
        event_dir.chmod(0o755)
    assert response.status_code == 502
    assert response.json()["failure"] == "unreadable_disk"
    assert "thumbnail_failure" not in response.json()


def test_a_bad_thumbnail_setting_has_no_kind(
    client: TestClient, project: Path, cache_dir: Path, fake: FakeThumbnailFor
) -> None:
    _write_config(project, cache_dir, position=1.5)

    response = client.get(_url(GRILLNING, "s1710001.mp4"))

    assert response.status_code == 502
    body = response.json()
    assert "thumbnails.position" in body["detail"]
    assert "failure" not in body
    assert "thumbnail_failure" not in body
    assert fake.calls == []


def test_a_config_that_is_not_utf8_has_no_kind(
    client: TestClient, project: Path, fake: FakeThumbnailFor
) -> None:
    (project / "config.yaml").write_bytes(b"# kommentar p\xe5 latin-1\n")

    response = client.get(_url(GRILLNING, "s1710001.mp4"))

    assert response.status_code == 502
    body = response.json()
    assert "not valid UTF-8" in body["detail"]
    assert "failure" not in body
    assert "thumbnail_failure" not in body
    _assert_no_caching_headers(response)
    assert fake.calls == []


# --- the engine's failure marker: a failed clip is answered again without an attempt ----


class _CountingProbe:
    """Stands in for ``probe_media`` in the engine: counts calls, optionally fails them."""

    def __init__(self, error: Optional[Exception] = None) -> None:
        self.calls: List[Path] = []
        self.error = error

    def __call__(self, path: Path, **_kwargs: object) -> object:
        self.calls.append(Path(path))
        if self.error is not None:
            raise self.error
        return type("Probed", (), {"duration": 1.0, "is_hdr": False})()


class _WritingRuntime:
    """An FfmpegRuntime stand-in whose ffmpeg writes a JPEG at the output path."""

    def __init__(self) -> None:
        self.calls: List[List[str]] = []

    def with_timeout(self, _seconds: float) -> "_WritingRuntime":
        return self

    def run(self, args: List[str]) -> None:
        self.calls.append(list(args))
        Path(args[-1]).write_bytes(FAKE_JPEG)


@pytest.fixture
def failing_probe(monkeypatch: pytest.MonkeyPatch) -> _CountingProbe:
    """The engine's probe fails with an empty-file error and counts its calls."""
    probe = _CountingProbe(ProbeError("File is empty (zero bytes)"))
    monkeypatch.setattr(thumbnail_module, "probe_media", probe)
    return probe


@pytest.fixture
def real_client(app: FastAPI) -> Iterator[TestClient]:
    """A client on the real engine (no fake ``thumbnail_for``), with a fake ffmpeg runtime."""
    app.state.runtime = _WritingRuntime()
    thumbnail_module._swept.clear()  # pylint: disable=protected-access
    with TestClient(app) as test_client:
        yield test_client


def _engine_attempt(clip_path: Path, cache_dir: Path) -> None:
    """One engine attempt, as the route's extraction makes it: records a failure it raises."""
    engine_thumbnail_for(
        clip_path,
        position=0.25,
        cache_dir=cache_dir,
        runtime=_WritingRuntime(),  # type: ignore[arg-type]
    )


def _marker_of(project: Path, cache_dir: Path, event: str, clip: str) -> Path:
    return _cache_path(project, cache_dir, event, clip).with_suffix(".fail")


def test_a_failing_clip_is_answered_again_without_an_attempt(
    real_client: TestClient, failing_probe: _CountingProbe, project: Path, cache_dir: Path
) -> None:
    first = real_client.get(_url(GRILLNING, "s1710001.mp4"))
    second = real_client.get(_url(GRILLNING, "s1710001.mp4"))

    assert first.status_code == second.status_code == 502
    assert second.json() == first.json()
    assert first.json()["thumbnail_failure"] == "thumbnail_failed"
    assert first.json()["detail"] == "s1710001.mp4: File is empty (zero bytes)"
    _assert_no_caching_headers(second)
    assert len(failing_probe.calls) == 1  # the second request ran no probe
    assert _marker_of(project, cache_dir, GRILLNING, "s1710001.mp4").is_file()
    assert not _cache_path(project, cache_dir, GRILLNING, "s1710001.mp4").exists()


def test_a_recorded_failure_is_answered_at_once_while_both_slots_are_held(
    client: TestClient,
    fake: FakeThumbnailFor,
    failing_probe: _CountingProbe,
    project: Path,
    cache_dir: Path,
) -> None:
    clip_path = _event_dir(project, GRILLNING) / "s1710004.mp4"
    with pytest.raises(ThumbnailError):  # the engine records the failure, as the route would
        _engine_attempt(clip_path, cache_dir)
    assert len(failing_probe.calls) == 1
    fake.release.clear()
    with ThreadPoolExecutor(max_workers=2) as pool:
        slow = [
            pool.submit(client.get, _url(GRILLNING, clip))
            for clip in ("s1710001.mp4", "s1710002.mp4")
        ]
        deadline = time.monotonic() + 5
        while fake.running < 2:
            assert time.monotonic() < deadline, "the extractions never started"
            time.sleep(0.005)

        recorded = client.get(_url(GRILLNING, "s1710004.mp4"))
        still_held = fake.running == 2 and not any(future.done() for future in slow)
        fake.release.set()
        for future in slow:
            future.result(timeout=10)

    assert still_held
    assert recorded.status_code == 502
    assert recorded.json()["thumbnail_failure"] == "thumbnail_failed"
    assert recorded.json()["detail"] == "s1710004.mp4: File is empty (zero bytes)"
    assert len(failing_probe.calls) == 1  # no ffprobe for the recorded clip
    assert clip_path not in fake.calls  # and it never took a slot


def test_a_recorded_failure_expires_after_sixty_seconds(
    client: TestClient,
    fake: FakeThumbnailFor,
    failing_probe: _CountingProbe,
    project: Path,
    cache_dir: Path,
) -> None:
    clip_path = _event_dir(project, GRILLNING) / "s1710001.mp4"
    with pytest.raises(ThumbnailError):
        _engine_attempt(clip_path, cache_dir)
    marker = _marker_of(project, cache_dir, GRILLNING, "s1710001.mp4")
    when = time.time() - 5
    os.utime(marker, (when, when))
    assert client.get(_url(GRILLNING, "s1710001.mp4")).status_code == 502
    assert fake.calls == []

    when = time.time() - 61
    os.utime(marker, (when, when))
    response = client.get(_url(GRILLNING, "s1710001.mp4"))

    assert response.status_code == 200  # tried again: the fake extraction ran
    assert fake.calls == [clip_path]


def test_a_cached_thumbnail_wins_over_a_recorded_failure(
    client: TestClient, fake: FakeThumbnailFor, project: Path, cache_dir: Path
) -> None:
    assert client.get(_url(GRILLNING, "s1710001.mp4")).status_code == 200
    marker = _marker_of(project, cache_dir, GRILLNING, "s1710001.mp4")
    marker.write_text(json.dumps({"reason": "no frame extracted"}))

    again = client.get(_url(GRILLNING, "s1710001.mp4"))

    assert again.status_code == 200
    assert again.content == FAKE_JPEG
    assert len(fake.calls) == 1


def test_revalidation_is_decided_before_a_recorded_failure(
    client: TestClient, fake: FakeThumbnailFor, project: Path, cache_dir: Path
) -> None:
    key = _cache_path(project, cache_dir, GRILLNING, "s1710001.mp4").stem
    cache_dir.mkdir(parents=True, exist_ok=True)
    _marker_of(project, cache_dir, GRILLNING, "s1710001.mp4").write_text('{"reason": "x"}')

    response = client.get(_url(GRILLNING, "s1710001.mp4"), headers={"If-None-Match": f'"{key}"'})

    assert response.status_code == 304
    assert fake.calls == []


def test_a_cache_fault_is_never_remembered_over_http(
    real_client: TestClient,
    app: FastAPI,
    project: Path,
    cache_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _skip_as_root()
    probe = _CountingProbe()
    monkeypatch.setattr(thumbnail_module, "probe_media", probe)
    cache_dir.mkdir()
    cache_dir.chmod(0o555)
    try:
        first = real_client.get(_url(GRILLNING, "s1710001.mp4"))
        second = real_client.get(_url(GRILLNING, "s1710001.mp4"))
    finally:
        cache_dir.chmod(0o755)

    for response in (first, second):
        assert response.status_code == 502
        assert "thumbnail_failure" not in response.json()
        assert str(cache_dir) in response.json()["detail"]
    assert len(probe.calls) == 2  # tried again: nothing was remembered
    assert not _marker_of(project, cache_dir, GRILLNING, "s1710001.mp4").exists()


def test_the_thumbnail_failure_kinds_are_unchanged() -> None:
    from auto_reel_ng.api.schemas import ThumbnailFailure  # pylint: disable=import-outside-toplevel

    assert [kind.value for kind in ThumbnailFailure] == ["thumbnail_failed"]


def test_the_other_events_routes_keep_their_order(client: TestClient) -> None:
    """The suffix route shadows nothing: the detail and ``/reel`` still reach their own."""
    event = quote(GRILLNING, safe="/")
    detail = client.get(f"/api/v1/events/{event}")
    assert detail.status_code == 503  # its own route, on this app's unreachable database
    assert detail.json()["check"] == "database"
    assert client.get(f"/api/v1/events/{event}/reel").status_code == 200


def test_cached_thumbnails_and_other_routes_answer_while_both_slots_are_held(
    client: TestClient, fake: FakeThumbnailFor
) -> None:
    assert client.get(_url(GRILLNING, "s1710004.mp4")).status_code == 200  # now cached
    fake.release.clear()
    with ThreadPoolExecutor(max_workers=3) as pool:
        slow = [
            pool.submit(client.get, _url(GRILLNING, clip))
            for clip in ("s1710001.mp4", "s1710002.mp4", "s1710003.mp4")
        ]
        deadline = time.monotonic() + 5
        while fake.running < 2:
            assert time.monotonic() < deadline, "the extractions never started"
            time.sleep(0.005)

        cached = client.get(_url(GRILLNING, "s1710004.mp4"))
        events = client.get("/api/v1/events")
        reel = client.get(f"/api/v1/events/{quote(GRILLNING, safe='/')}/reel")
        still_held = fake.running == 2 and not any(future.done() for future in slow)
        fake.release.set()
        results = [future.result(timeout=10) for future in slow]

    assert still_held
    assert cached.status_code == 200
    assert events.status_code == 503  # answered (this app's database is unreachable)
    assert reel.status_code == 200
    assert [response.status_code for response in results] == [200, 200, 200]
    assert fake.max_running == 2


def test_concurrent_requests_for_one_clip_share_one_extraction(
    client: TestClient, fake: FakeThumbnailFor
) -> None:
    fake.release.clear()
    with ThreadPoolExecutor(max_workers=5) as pool:
        requests = [pool.submit(client.get, _url(GRILLNING, "s1710001.mp4")) for _ in range(5)]
        deadline = time.monotonic() + 5
        while fake.running < 1:
            assert time.monotonic() < deadline, "the extraction never started"
            time.sleep(0.005)
        time.sleep(0.1)  # every request has joined the one in flight by now
        fake.release.set()
        responses = [future.result(timeout=10) for future in requests]

    assert [response.status_code for response in responses] == [200] * 5
    assert len({response.content for response in responses}) == 1
    assert len({response.headers["etag"] for response in responses}) == 1
    assert len(fake.calls) == 1


# --- task 3.2: validators and caching headers --------------------------------


def test_a_200_carries_the_cache_key_and_cache_control(
    client: TestClient, project: Path, cache_dir: Path
) -> None:
    response = client.get(_url(GRILLNING, "s1710001.mp4"))
    key = _cache_path(project, cache_dir, GRILLNING, "s1710001.mp4").stem
    assert response.headers["etag"] == f'"{key}"'
    assert response.headers["cache-control"] == CACHE_CONTROL


def test_a_miss_is_tagged_with_the_key_of_the_bytes_served(
    client: TestClient, fake: FakeThumbnailFor, project: Path, cache_dir: Path
) -> None:
    fake.redirect_key = "f" * 64  # the clip changed between the lookup and the extraction
    response = client.get(_url(GRILLNING, "s1710001.mp4"))
    assert response.status_code == 200
    assert response.headers["etag"] == f'"{"f" * 64}"'
    assert response.headers["etag"] != (
        f'"{_cache_path(project, cache_dir, GRILLNING, "s1710001.mp4").stem}"'
    )


def test_revalidation_is_a_304_without_extraction(
    client: TestClient, fake: FakeThumbnailFor, cache_dir: Path
) -> None:
    etag = client.get(_url(GRILLNING, "s1710001.mp4")).headers["etag"]
    shutil.rmtree(cache_dir)  # a 304 never needs the file
    for header in (etag, f"W/{etag}", f'"unrelated", {etag}', f'W/"x" , W/{etag}'):
        response = client.get(_url(GRILLNING, "s1710001.mp4"), headers={"If-None-Match": header})
        assert response.status_code == 304, header
        assert response.headers["etag"] == etag
        assert response.headers["cache-control"] == CACHE_CONTROL
        assert response.content == b""
    assert len(fake.calls) == 1


def test_a_changed_clip_gets_a_new_entity_tag(
    client: TestClient, fake: FakeThumbnailFor, project: Path
) -> None:
    old = client.get(_url(GRILLNING, "s1710001.mp4")).headers["etag"]
    clip = project / GRILLNING / "s1710001.mp4"
    clip.write_bytes(b"another recording, longer than the first")
    os.utime(clip, ns=(clip.stat().st_atime_ns, clip.stat().st_mtime_ns + 10**9))

    response = client.get(_url(GRILLNING, "s1710001.mp4"), headers={"If-None-Match": old})

    assert response.status_code == 200
    assert response.headers["etag"] != old
    assert len(fake.calls) == 2


def test_if_none_match_on_several_header_lines_is_one_list(
    client: TestClient, fake: FakeThumbnailFor
) -> None:
    url = _url(GRILLNING, "s1710001.mp4")
    etag = client.get(url).headers["etag"]
    for lines in (
        [("If-None-Match", '"zzz"'), ("If-None-Match", etag)],
        [("If-None-Match", etag), ("If-None-Match", '"zzz"')],
    ):
        response = client.get(url, headers=lines)
        assert response.status_code == 304, lines
        assert response.headers["etag"] == etag
    assert len(fake.calls) == 1


def test_a_non_matching_tag_is_a_200(client: TestClient) -> None:
    response = client.get(
        _url(GRILLNING, "s1710001.mp4"), headers={"If-None-Match": '"not-the-key"'}
    )
    assert response.status_code == 200
    assert response.content == FAKE_JPEG


def test_a_star_matches_only_a_cached_thumbnail(client: TestClient, fake: FakeThumbnailFor) -> None:
    url = _url(GRILLNING, "s1710001.mp4")
    uncached = client.get(url, headers={"If-None-Match": "*"})
    assert uncached.status_code == 200
    assert len(fake.calls) == 1

    cached = client.get(url, headers={"If-None-Match": "*"})
    assert cached.status_code == 304
    assert cached.headers["etag"] == uncached.headers["etag"]
    assert len(fake.calls) == 1


# --- task 3.3: the real engine through the route -----------------------------


def _tree_snapshot(root: Path) -> List[Tuple[str, int, int]]:
    entries = [root, *sorted(root.rglob("*"))]
    return [(str(path), path.lstat().st_size, path.lstat().st_mtime_ns) for path in entries]


def _dimensions(runtime: FfmpegRuntime, image: Path) -> str:
    result = subprocess.run(
        [
            runtime.ffprobe_path,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-of",
            "csv=p=0",
            str(image),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _truncate_media_data(clip: Path, *, keep: int = 300) -> None:
    """Cut ``clip`` ``keep`` bytes into its ``mdat`` box: the ``moov`` index stays intact."""
    data = clip.read_bytes()
    offset = 0
    while offset + 8 <= len(data):
        size = int.from_bytes(data[offset : offset + 4], "big")
        if data[offset + 4 : offset + 8] == b"mdat":
            clip.write_bytes(data[: offset + 8 + keep])
            return
        offset += size
    raise AssertionError(f"no mdat box in {clip}")


@pytest.mark.has_ffmpeg
def test_an_undecodable_clip_gets_a_one_line_detail_without_server_paths(
    tmp_path: Path,
    runtime: FfmpegRuntime,
    make_clip: Callable[..., Path],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Fixed non-media bytes fail the probe and a truncated media box fails ffmpeg; neither detail
    carries the command, a path or stderr, and the log keeps the full reason."""
    root = tmp_path / "proj"
    event_dir = root / GRILLNING
    event_dir.mkdir(parents=True)
    _write(event_dir / "not-media.mp4", NOT_MEDIA)
    whole = make_clip("whole.mp4", duration=2.0)
    subprocess.run(
        [
            runtime.ffmpeg_path,
            "-v",
            "error",
            "-i",
            str(whole),
            "-c",
            "copy",
            "-movflags",
            "+faststart",  # moov before mdat, so the cut keeps the index
            str(event_dir / "truncated.mp4"),
        ],
        check=True,
        capture_output=True,
    )
    _truncate_media_data(event_dir / "truncated.mp4")
    _write_config(root, tmp_path / "cache")

    app = create_app(resolve_api_settings(root, env={"DATABASE_URL": UNREACHABLE_DATABASE_URL}))
    with TestClient(app) as client:
        responses = {
            clip: client.get(_url(GRILLNING, clip)) for clip in ("not-media.mp4", "truncated.mp4")
        }

    for clip, response in responses.items():
        assert response.status_code == 502, clip
        body = response.json()
        assert body["thumbnail_failure"] == "thumbnail_failed"
        detail = body["detail"]
        assert detail.startswith(f"{clip}: "), detail
        cause = detail.removeprefix(f"{clip}: ")
        assert cause and "/" not in cause and "\n" not in detail, detail
    assert (
        responses["not-media.mp4"]
        .json()["detail"]
        .startswith("not-media.mp4: ffprobe could not read")
    )
    assert (
        responses["truncated.mp4"]
        .json()["detail"]
        .startswith("truncated.mp4: no frame extracted at ")
    )
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    for clip in responses:
        (logged,) = [message for message in warnings if f": {clip}: " in message]
        assert "Command exited" in logged and "stderr:" in logged  # the full reason


@pytest.mark.has_ffmpeg
def test_real_thumbnails_from_a_read_only_library(
    tmp_path: Path, runtime: FfmpegRuntime, make_clip: Callable[..., Path]
) -> None:
    _skip_as_root()
    root = tmp_path / "proj"
    cache = tmp_path / "cache"
    event_dir = root / GRILLNING
    event_dir.mkdir(parents=True)  # make_clip writes to tmp_path / name; ffmpeg makes no folders
    make_clip(f"proj/{GRILLNING}/wide.mp4", width=640, height=360, duration=1.0)
    make_clip(f"proj/{GRILLNING}/portrait.mp4", width=360, height=640, duration=1.0)
    _write(event_dir / "trasig.mp4")
    _write_config(root, cache)

    modes = {path: path.lstat().st_mode for path in [root, *root.rglob("*")]}
    for path, mode in modes.items():
        path.chmod(stat.S_IMODE(mode) & ~0o222)
    try:
        before = _tree_snapshot(root)
        app = create_app(resolve_api_settings(root, env={"DATABASE_URL": UNREACHABLE_DATABASE_URL}))
        with TestClient(app) as client:
            wide = client.get(_url(GRILLNING, "wide.mp4"))
            portrait = client.get(_url(GRILLNING, "portrait.mp4"))
            trasig = client.get(_url(GRILLNING, "trasig.mp4"))
            retried = client.get(_url(GRILLNING, "trasig.mp4"))  # answered from the failure marker
        after = _tree_snapshot(root)
    finally:
        for path, mode in sorted(modes.items(), key=lambda item: len(item[0].parts)):
            path.chmod(stat.S_IMODE(mode))

    assert (wide.status_code, portrait.status_code) == (200, 200)
    assert wide.content[:2] == portrait.content[:2] == b"\xff\xd8"
    wide_jpeg = cache / f"{wide.headers['etag'].strip(chr(34))}.jpg"
    portrait_jpeg = cache / f"{portrait.headers['etag'].strip(chr(34))}.jpg"
    assert _dimensions(runtime, wide_jpeg) == "320,180"
    assert _dimensions(runtime, portrait_jpeg) == "101,180"
    assert after == before

    assert trasig.status_code == retried.status_code == 502
    body = trasig.json()
    assert body["thumbnail_failure"] == "thumbnail_failed"
    assert "failure" not in body
    assert body["detail"].startswith("trasig.mp4: ")
    assert "empty" in body["detail"]
    assert retried.json() == body
    # The cache holds the two JPEGs, the two duration files beside them, and the one failure
    # marker of the empty clip (the probe failed, so it has no duration file).
    assert sorted(path.suffix for path in cache.iterdir()) == [
        ".fail",
        ".jpg",
        ".jpg",
        ".json",
        ".json",
    ]
    assert (cache / wide_jpeg.with_suffix(".json").name).is_file()
    assert (cache / portrait_jpeg.with_suffix(".json").name).is_file()
