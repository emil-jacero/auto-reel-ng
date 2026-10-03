"""Tests for the proxy and filmstrip endpoints (change ``proxy-media-endpoints``, api-service
"Clip proxy endpoint" and "Clip filmstrip endpoint", D-21).

Three layers, as the routes are built:

- ``events_read.proxy_source``: which cache entry a listed clip's proxy would be in. The
  lookup computes a path from the clip's stat and the configured cache; it opens, creates
  and probes nothing.
- ``api.media.proxy_media`` / ``filmstrip_media``: the stat-and-open of the entry's file, and
  the translation of "no file" into :class:`ProxyAbsentError` (a 404, never bytes).
- the routes, on an app whose database URL points at a closed port. Entries are fabricated
  with the ``proxies`` package's own ``entry_dir`` (files of a repeating counter, so ranges
  compare exactly); a real ``ensure_proxy`` entry is served in the ``has_ffmpeg`` tests.
"""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple
from urllib.parse import quote

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fastapi.testclient import TestClient

from auto_reel_ng.accel.profiles import CPUProfile
from auto_reel_ng.api import events_read
from auto_reel_ng.api import media as media_module
from auto_reel_ng.api.app import create_app
from auto_reel_ng.api.media import (
    MEDIA_TYPES,
    MediaGoneError,
    MediaReadError,
    ProxyAbsentError,
    clip_media,
    filmstrip_media,
    proxy_media,
)
from auto_reel_ng.api.schemas import EventFailure
from auto_reel_ng.api.settings import ApiSettings, resolve_api_settings
from auto_reel_ng.config.project import ConfigError
from auto_reel_ng.event.discovery import VIDEO_EXTENSIONS, DiskListing
from auto_reel_ng.ffmpeg.runtime import FfmpegRuntime
from auto_reel_ng.proxies import (
    PROXY_VERSION,
    ProxySettings,
    ensure_filmstrip,
    ensure_proxy,
    entry_dir,
    spec,
)

#: A closed port: the proxy routes must never need the database.
UNREACHABLE_DATABASE_URL = "postgresql+psycopg://media:media@127.0.0.1:1/media"

GRILLNING = "2024/2024-06-27 - Grillning med grannar"
KALAS = "2024/2024-07-14 - Kalas"
TJORN = "2024/2024-08-20 - Två kapitel - Tjörn"
SOMMARLOV = "2024/2024-09-01 - Sommarlov"
SKILJETECKEN = "2024/2024-09-10 - Skiljetecken"
TRASIG_YAML = "2024/2024-09-15 - Trasig yaml"
IGNORED_EVENT = "2024/2024-09-20 - Aldrig"  # holds .reelignore: not an event of the list

PUNCTUATED = "Kväll, del 2/a+b & c #1.mp4"

#: Each cache file's size: big enough for ranges, small enough to compare whole.
FILE_SIZE = 300 * 1024

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

SOMMARLOV_REEL = """\
version: 0
metadata:
  title: Sommarlov
  date: 2024-09-01
chapters:
  - name: ''
    clips:
      - s1710002.mp4
      - borttagen.mp4  # MISSING
"""


def _content(tag: str, size: int = FILE_SIZE) -> bytes:
    """``size`` distinct bytes: the tag, then a 0..255 counter, repeated."""
    unit = f"{tag}|".encode() + bytes(range(256))
    return (unit * (size // len(unit) + 1))[:size]


def _write(path: Path, data: bytes = b"") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _skip_as_root() -> None:
    if os.geteuid() == 0:
        pytest.skip("root ignores file permissions")


@pytest.fixture
def cache_dir(tmp_path: Path) -> Path:
    """The proxy cache the project's ``config.yaml`` names: outside the library, not created."""
    return tmp_path / "proxy-cache"


@pytest.fixture
def project(tmp_path: Path, cache_dir: Path) -> Path:
    """A year-event library shaped like the clip-media tests', plus a ``config.yaml``."""
    root = tmp_path / "proj"
    for name in ("s1710001.mp4", "s1710002.mp4", "s1710003.mp4"):
        _write(root / GRILLNING / name, _content(f"grill {name}"))
    _write(root / GRILLNING / "original" / "x.mp4", _content("original of grill"))
    _write(tmp_path / "samples" / "extern.mp4", _content("outside the library"))
    (root / GRILLNING / "länk.mp4").symlink_to(tmp_path / "samples" / "extern.mp4")

    _write(root / KALAS / "s1710001.mp4", _content("kalas"))
    (root / KALAS / "länk.mp4").symlink_to(tmp_path / "samples" / "extern.mp4")
    _write(root / IGNORED_EVENT / "s1710001.mp4", _content("never rendered"))
    _write(root / IGNORED_EVENT / ".reelignore")

    tjorn = root / TJORN
    for identity in ("s1710001.mp4", "s1710004.mp4", "Kvällen/s1710002.mp4"):
        _write(tjorn / identity, _content(f"tjorn {identity}"))
    _write(tjorn / "Kvällen" / "s1710003.mp4", _content("tjorn kvällen 3"))
    (tjorn / "reel.yaml").write_text(TJORN_REEL, encoding="utf-8")

    sommarlov = root / SOMMARLOV
    _write(sommarlov / "s1710002.mp4", _content("sommar 2"))
    (sommarlov / "reel.yaml").write_text(SOMMARLOV_REEL, encoding="utf-8")

    _write(root / SKILJETECKEN / PUNCTUATED, _content("punctuated"))

    _write(root / TRASIG_YAML / "s1710001.mp4", _content("broken yaml"))
    (root / TRASIG_YAML / "reel.yaml").write_text("version: 0\nchapters: [\n", encoding="utf-8")

    (root / "config.yaml").write_text(f'proxies:\n  cache_dir: "{cache_dir}"\n', encoding="utf-8")
    return root


@pytest.fixture
def settings(project: Path) -> ApiSettings:
    return resolve_api_settings(project, env={"DATABASE_URL": UNREACHABLE_DATABASE_URL})


def _entry(project: Path, cache_dir: Path, event: str, clip: str) -> Path:
    """The entry directory the ``proxies`` package computes for the clip, not created."""
    return entry_dir(project / event / clip, cache_dir)


def _prepare(
    project: Path, cache_dir: Path, event: str, clip: str, *, filmstrip: bool = True
) -> Path:
    """Fabricate a published entry for the clip: ``proxy.mp4``, ``facts.json``, a sprite."""
    entry = _entry(project, cache_dir, event, clip)
    _write(entry / spec.PROXY_FILENAME, _content(f"proxy {event}/{clip}"))
    _write(entry / spec.FACTS_FILENAME, b"{}")
    if filmstrip:
        _write(
            entry / spec.FILMSTRIP_FILENAME, b"\xff\xd8" + _content(f"strip {clip}") + b"\xff\xd9"
        )
    return entry


def _tree(root: Path) -> Dict[str, Tuple[int, int]]:
    """Every path under ``root`` with its size and ``st_mtime_ns``: a snapshot to compare."""
    snapshot: Dict[str, Tuple[int, int]] = {}
    if not root.exists():
        return snapshot
    for current, dirs, files in os.walk(root):
        for name in dirs + files:
            path = Path(current) / name
            info = path.lstat()
            snapshot[str(path)] = (info.st_size, info.st_mtime_ns)
    return snapshot


def _vanish_after_listing(monkeypatch: pytest.MonkeyPatch, event_dir: Path, clip: str) -> None:
    """Delete ``clip`` between discovery's listing and the stat: a real race, replayed."""
    real_scan_event = events_read.scan_event

    def scan_then_delete(directory: Path) -> DiskListing:
        listing = real_scan_event(directory)
        (event_dir / clip).unlink()
        return listing

    monkeypatch.setattr(events_read, "scan_event", scan_then_delete)


def _no_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: Any, **kwargs: Any) -> None:
        raise AssertionError(f"a subprocess was started: {args!r}")

    monkeypatch.setattr(subprocess, "Popen", refuse)


# --- task 2.1: which entry a listed clip has ----------------------------------------------


@pytest.mark.parametrize(
    ("event", "clip"),
    [
        (GRILLNING, "s1710001.mp4"),
        (TJORN, "Kvällen/s1710002.mp4"),  # a chapter folder
        (TJORN, "s1710004.mp4"),  # IGNORED by the document, still on disk
        (SKILJETECKEN, PUNCTUATED),
        (GRILLNING, "länk.mp4"),  # a symlink to a file outside the project
    ],
)
def test_a_listed_clip_resolves_to_the_entry_the_proxies_package_names(
    settings: ApiSettings, project: Path, cache_dir: Path, event: str, clip: str
) -> None:
    source = events_read.proxy_source(settings, event, clip)

    assert source.clip_path == project / event / clip
    assert source.entry_dir == entry_dir(project / event / clip, cache_dir)
    assert source.entry_dir.parent == cache_dir
    assert source.proxy_path == source.entry_dir / "proxy.mp4"
    assert source.filmstrip_path == source.entry_dir / "filmstrip.jpg"


def test_two_events_that_link_one_file_share_an_entry(settings: ApiSettings) -> None:
    first = events_read.proxy_source(settings, GRILLNING, "länk.mp4")
    second = events_read.proxy_source(settings, KALAS, "länk.mp4")

    assert first.entry_dir == second.entry_dir


def test_a_rewritten_clip_or_other_settings_or_version_give_another_entry(
    settings: ApiSettings,
    project: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = events_read.proxy_source(settings, GRILLNING, "s1710001.mp4").entry_dir

    # a new PROXY_VERSION re-keys every entry
    monkeypatch.setattr(spec, "PROXY_VERSION", PROXY_VERSION + 1)
    assert events_read.proxy_source(settings, GRILLNING, "s1710001.mp4").entry_dir != before
    monkeypatch.undo()

    # so do other contract values (the settings hash)
    monkeypatch.setattr(spec, "PROXY_CRF", spec.PROXY_CRF + 1)
    assert events_read.proxy_source(settings, GRILLNING, "s1710001.mp4").entry_dir != before
    monkeypatch.undo()

    # and a rewritten clip: new bytes and a later mtime
    clip = project / GRILLNING / "s1710001.mp4"
    clip.write_bytes(_content("replaced", FILE_SIZE + 1))
    os.utime(clip, ns=(2_000_000_000_000_000_000, 2_000_000_000_000_000_000))
    assert events_read.proxy_source(settings, GRILLNING, "s1710001.mp4").entry_dir != before


@pytest.mark.parametrize(
    ("event", "clip"),
    [
        (SOMMARLOV, "borttagen.mp4"),  # MISSING
        (GRILLNING, "original/x.mp4"),
        (TJORN, "Kvällen/../s1710001.mp4"),  # normalizes to a clip, but is not its identity
        (GRILLNING, "../2024-07-14 - Kalas/s1710001.mp4"),
        (TJORN, ""),
    ],
)
def test_an_identity_discovery_does_not_list_is_not_found(
    settings: ApiSettings, event: str, clip: str
) -> None:
    with pytest.raises(events_read.ClipNotFoundError):
        events_read.proxy_source(settings, event, clip)


def test_an_absolute_path_is_not_an_identity(settings: ApiSettings, project: Path) -> None:
    with pytest.raises(events_read.ClipNotFoundError):
        events_read.proxy_source(settings, TJORN, str(project / TJORN / "s1710001.mp4"))


@pytest.mark.parametrize(
    "event_id", ["2024/2024-12-24 - Finns inte", "2024", f"{GRILLNING}/original", IGNORED_EVENT]
)
def test_a_folder_that_is_not_an_event_is_not_found(settings: ApiSettings, event_id: str) -> None:
    with pytest.raises(events_read.EventNotFoundError):
        events_read.proxy_source(settings, event_id, "s1710001.mp4")


def test_an_unlistable_event_folder_is_unreadable_disk(
    settings: ApiSettings, project: Path
) -> None:
    _skip_as_root()
    folder = project / GRILLNING
    folder.chmod(0o000)
    try:
        with pytest.raises(events_read.EventReadError) as caught:
            events_read.proxy_source(settings, GRILLNING, "s1710001.mp4")
    finally:
        folder.chmod(0o755)
    assert caught.value.failure is EventFailure.UNREADABLE_DISK


def test_an_unparseable_config_or_a_cache_inside_the_library_is_a_config_error(
    settings: ApiSettings, project: Path
) -> None:
    (project / "config.yaml").write_text("proxies: [\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        events_read.proxy_source(settings, GRILLNING, "s1710001.mp4")

    (project / "config.yaml").write_text(
        f'proxies:\n  cache_dir: "{project / "cache"}"\n', encoding="utf-8"
    )
    with pytest.raises(ConfigError, match="proxies.cache_dir"):
        events_read.proxy_source(settings, GRILLNING, "s1710001.mp4")


def test_the_default_cache_is_used_when_the_config_names_none(
    settings: ApiSettings, project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (project / "config.yaml").unlink()
    xdg = tmp_path / "xdg"
    monkeypatch.setenv("XDG_CACHE_HOME", str(xdg))

    source = events_read.proxy_source(settings, GRILLNING, "s1710001.mp4")

    assert source.entry_dir.parent == xdg / "auto-reel" / "proxies"


def test_the_document_is_never_read(settings: ApiSettings) -> None:
    """The unparseable ``reel.yaml`` of an event does not stop its clip."""
    source = events_read.proxy_source(settings, TRASIG_YAML, "s1710001.mp4")
    assert source.clip_path.name == "s1710001.mp4"


def test_a_clip_that_vanishes_after_the_listing_raises_file_not_found(
    settings: ApiSettings, project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _vanish_after_listing(monkeypatch, project / GRILLNING, "s1710002.mp4")
    with pytest.raises(FileNotFoundError):
        events_read.proxy_source(settings, GRILLNING, "s1710002.mp4")


def test_a_stat_refused_after_the_listing_propagates(
    settings: ApiSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(_clip: Path, _cache: Path) -> Path:
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(events_read, "entry_dir", refuse)
    with pytest.raises(PermissionError):
        events_read.proxy_source(settings, GRILLNING, "s1710001.mp4")


def test_the_lookup_writes_nothing_and_starts_nothing(
    settings: ApiSettings,
    project: Path,
    tmp_path: Path,
    cache_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _no_subprocess(monkeypatch)
    before = _tree(tmp_path)

    for event, clip in ((GRILLNING, "s1710001.mp4"), (TJORN, "Kvällen/s1710002.mp4")):
        events_read.proxy_source(settings, event, clip)
        with pytest.raises(ProxyAbsentError):
            proxy_media(settings, event, clip)

    assert _tree(tmp_path) == before
    assert not cache_dir.exists()


# --- task 2.2: the file in the entry ------------------------------------------------------


def test_a_prepared_clip_opens_its_proxy_and_its_filmstrip(
    settings: ApiSettings, project: Path, cache_dir: Path
) -> None:
    entry = _prepare(project, cache_dir, GRILLNING, "s1710001.mp4")

    proxy = proxy_media(settings, GRILLNING, "s1710001.mp4")
    strip = filmstrip_media(settings, GRILLNING, "s1710001.mp4")

    proxy_stat = (entry / "proxy.mp4").stat()
    assert proxy.media_type == "video/mp4"
    assert proxy.name == "proxy.mp4"
    assert proxy.etag == '"%x-%x"' % (proxy_stat.st_size, proxy_stat.st_mtime_ns)
    clip_stat = (project / GRILLNING / "s1710001.mp4").stat()
    assert proxy.etag != '"%x-%x"' % (clip_stat.st_size, clip_stat.st_mtime_ns)
    assert (strip.media_type, strip.name) == ("image/jpeg", "filmstrip.jpg")


def test_the_type_table_is_still_the_video_extensions_and_clips_declare_no_type(
    settings: ApiSettings,
) -> None:
    assert set(MEDIA_TYPES) == VIDEO_EXTENSIONS
    assert clip_media(settings, GRILLNING, "s1710001.mp4").declared_type is None
    assert clip_media(settings, GRILLNING, "s1710001.mp4").media_type == "video/mp4"
    assert media_module.MediaFile.__dataclass_fields__["declared_type"].default is None


def test_a_declared_type_wins_over_the_extension(tmp_path: Path) -> None:
    path = tmp_path / "x.jpg"
    path.write_bytes(b"abc")
    assert media_module.open_media(path, label="x").media_type == "application/octet-stream"
    assert media_module.open_media(path, label="x", media_type="image/jpeg").media_type == (
        "image/jpeg"
    )


@pytest.mark.parametrize("what", ["proxy", "filmstrip"])
def test_no_entry_and_no_cache_directory_are_absent(
    settings: ApiSettings, cache_dir: Path, what: str
) -> None:
    lookup = proxy_media if what == "proxy" else filmstrip_media
    assert not cache_dir.exists()

    with pytest.raises(ProxyAbsentError) as caught:
        lookup(settings, GRILLNING, "s1710001.mp4")

    assert str(caught.value) == f"s1710001.mp4: no {what}"
    assert not cache_dir.exists()


def test_a_cache_that_is_a_regular_file_is_absent_not_unreadable(
    settings: ApiSettings, cache_dir: Path
) -> None:
    _write(cache_dir, b"not a directory")
    with pytest.raises(ProxyAbsentError):
        proxy_media(settings, GRILLNING, "s1710001.mp4")


def test_a_build_directory_and_an_entry_without_a_proxy_are_absent(
    settings: ApiSettings, project: Path, cache_dir: Path
) -> None:
    entry = _entry(project, cache_dir, GRILLNING, "s1710001.mp4")
    part = cache_dir / f".{entry.name}.{'0' * 32}.part"
    _write(part / "proxy.mp4", _content("half written"))
    with pytest.raises(ProxyAbsentError):
        proxy_media(settings, GRILLNING, "s1710001.mp4")

    _write(entry / "facts.json", b"{}")  # an entry directory, still no proxy.mp4
    with pytest.raises(ProxyAbsentError):
        proxy_media(settings, GRILLNING, "s1710001.mp4")


def test_a_directory_at_the_proxy_name_is_absent(
    settings: ApiSettings, project: Path, cache_dir: Path
) -> None:
    entry = _entry(project, cache_dir, GRILLNING, "s1710001.mp4")
    (entry / "proxy.mp4").mkdir(parents=True)
    with pytest.raises(ProxyAbsentError):
        proxy_media(settings, GRILLNING, "s1710001.mp4")


def test_a_proxy_of_the_clip_s_previous_bytes_is_absent(
    settings: ApiSettings, project: Path, cache_dir: Path
) -> None:
    _prepare(project, cache_dir, GRILLNING, "s1710001.mp4")
    clip = project / GRILLNING / "s1710001.mp4"
    clip.write_bytes(_content("replaced"))
    os.utime(clip, ns=(2_000_000_000_000_000_000, 2_000_000_000_000_000_000))

    with pytest.raises(ProxyAbsentError):
        proxy_media(settings, GRILLNING, "s1710001.mp4")
    with pytest.raises(ProxyAbsentError):
        filmstrip_media(settings, GRILLNING, "s1710001.mp4")


def test_a_proxy_without_a_filmstrip_serves_the_proxy_only(
    settings: ApiSettings, project: Path, cache_dir: Path
) -> None:
    _prepare(project, cache_dir, GRILLNING, "s1710001.mp4", filmstrip=False)

    assert proxy_media(settings, GRILLNING, "s1710001.mp4").name == "proxy.mp4"
    with pytest.raises(ProxyAbsentError):
        filmstrip_media(settings, GRILLNING, "s1710001.mp4")


def test_a_filmstrip_is_served_whether_or_not_the_proxy_is_there(
    settings: ApiSettings, project: Path, cache_dir: Path
) -> None:
    entry = _prepare(project, cache_dir, GRILLNING, "s1710001.mp4")
    (entry / "proxy.mp4").unlink()

    assert filmstrip_media(settings, GRILLNING, "s1710001.mp4").name == "filmstrip.jpg"


def test_a_proxy_the_process_cannot_read_is_a_path_free_read_error(
    settings: ApiSettings, project: Path, cache_dir: Path, tmp_path: Path
) -> None:
    _skip_as_root()
    entry = _prepare(project, cache_dir, GRILLNING, "s1710001.mp4")
    (entry / "proxy.mp4").chmod(0o000)
    try:
        with pytest.raises(MediaReadError) as caught:
            proxy_media(settings, GRILLNING, "s1710001.mp4")
    finally:
        (entry / "proxy.mp4").chmod(0o644)

    assert "s1710001.mp4" in str(caught.value)
    assert "Permission denied" in str(caught.value)
    assert str(tmp_path) not in str(caught.value)


def test_a_proxy_deleted_after_the_lookup_is_absent(
    settings: ApiSettings, project: Path, cache_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    entry = _prepare(project, cache_dir, GRILLNING, "s1710001.mp4")
    real = media_module.proxy_source

    def look_then_delete(*args: Any) -> events_read.ProxySource:
        found = real(*args)
        (entry / "proxy.mp4").unlink()
        return found

    monkeypatch.setattr(media_module, "proxy_source", look_then_delete)
    with pytest.raises(ProxyAbsentError):
        proxy_media(settings, GRILLNING, "s1710001.mp4")


def test_a_clip_deleted_after_the_listing_is_gone_and_a_refused_stat_is_a_read_error(
    settings: ApiSettings, project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _vanish_after_listing(monkeypatch, project / GRILLNING, "s1710002.mp4")
    with pytest.raises(MediaGoneError):
        proxy_media(settings, GRILLNING, "s1710002.mp4")
    monkeypatch.undo()

    def refuse(_clip: Path, _cache: Path) -> Path:
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(events_read, "entry_dir", refuse)
    with pytest.raises(MediaReadError) as caught:
        proxy_media(settings, GRILLNING, "s1710001.mp4")
    assert str(caught.value) == "s1710001.mp4: cannot read the file: Permission denied"


# --- task 3.1: the routes over HTTP -------------------------------------------------------


@pytest.fixture
def app(settings: ApiSettings) -> FastAPI:
    return create_app(settings)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


def _event_url(event: str) -> str:
    return f"/api/v1/events/{quote(event, safe='/')}"


def _proxy_url(event: str, clip: str, *, route: str = "proxy", **params: str) -> str:
    query = f"clip={quote(clip, safe='')}"
    for name, value in params.items():
        query += f"&{name}={quote(value, safe='')}"
    return f"{_event_url(event)}/{route}?{query}"


def _strip_url(event: str, clip: str, **params: str) -> str:
    return _proxy_url(event, clip, route="filmstrip", **params)


def _proxy_bytes(event: str, clip: str) -> bytes:
    return _content(f"proxy {event}/{clip}")


def _assert_problem(response: Any, status: int, event_id: str) -> Dict[str, Any]:
    assert response.status_code == status
    assert response.headers["content-type"] == "application/json"
    body: Dict[str, Any] = response.json()
    assert body["status"] == status
    assert body["event_id"] == event_id
    assert "cache-control" not in response.headers
    assert "etag" not in response.headers
    return body


def test_a_prepared_clip_s_proxy_is_streamed_with_its_validators(
    client: TestClient, project: Path, cache_dir: Path
) -> None:
    entry = _prepare(project, cache_dir, GRILLNING, "s1710001.mp4")
    media = client.get(f"{_event_url(GRILLNING)}/media?clip=s1710001.mp4")

    response = client.get(_proxy_url(GRILLNING, "s1710001.mp4"))

    info = (entry / "proxy.mp4").stat()
    assert response.status_code == 200
    assert response.content == _proxy_bytes(GRILLNING, "s1710001.mp4")
    assert response.headers["content-type"] == "video/mp4"
    assert response.headers["content-length"] == str(FILE_SIZE)
    assert response.headers["accept-ranges"] == "bytes"
    assert response.headers["etag"] == '"%x-%x"' % (info.st_size, info.st_mtime_ns)
    assert "last-modified" in response.headers
    assert response.headers["cache-control"] == "private, no-cache"
    assert response.headers["content-disposition"] == 'inline; filename="proxy.mp4"'
    assert response.headers["etag"] != media.headers["etag"]


def test_ranges_and_if_range_are_the_media_routes(
    client: TestClient, project: Path, cache_dir: Path
) -> None:
    _prepare(project, cache_dir, GRILLNING, "s1710001.mp4")
    url = _proxy_url(GRILLNING, "s1710001.mp4")
    data = _proxy_bytes(GRILLNING, "s1710001.mp4")

    for header, wanted in (
        ("bytes=0-99", data[:100]),
        ("bytes=1000-", data[1000:]),
        ("bytes=-500", data[-500:]),
    ):
        ranged = client.get(url, headers={"Range": header})
        assert (ranged.status_code, ranged.content) == (206, wanted)
    past = client.get(url, headers={"Range": f"bytes={FILE_SIZE}-"})
    assert past.status_code == 416
    assert past.headers["content-range"] == f"bytes */{FILE_SIZE}"
    malformed = client.get(url, headers={"Range": "bytes=abc"})
    assert malformed.status_code == 400
    assert malformed.headers["content-type"].startswith("text/plain")

    etag = client.head(url).headers["etag"]
    assert client.get(url, headers={"Range": "bytes=0-99", "If-Range": etag}).status_code == 206
    assert client.get(url, headers={"Range": "bytes=0-99", "If-Range": '"old"'}).status_code == 200


def test_validators_answer_304_and_a_replaced_proxy_gets_a_new_tag(
    client: TestClient, project: Path, cache_dir: Path
) -> None:
    entry = _prepare(project, cache_dir, GRILLNING, "s1710001.mp4")
    url = _proxy_url(GRILLNING, "s1710001.mp4")
    first = client.get(url)
    etag, modified = first.headers["etag"], first.headers["last-modified"]

    for headers in (
        {"If-None-Match": etag},
        {"If-None-Match": etag, "Range": "bytes=0-9"},
        {"If-Modified-Since": modified},
    ):
        response = client.get(url, headers=headers)
        assert response.status_code == 304
        assert response.content == b""
        assert response.headers["etag"] == etag
        assert response.headers["cache-control"] == "private, no-cache"

    _write(entry / "proxy.mp4", _content("re-encoded", FILE_SIZE + 17))
    os.utime(entry / "proxy.mp4", ns=(2_000_000_000_000_000_000, 2_000_000_000_000_000_000))
    replaced = client.get(url, headers={"If-None-Match": etag})
    assert replaced.status_code == 200
    assert replaced.content == _content("re-encoded", FILE_SIZE + 17)
    assert replaced.headers["etag"] != etag

    plain, with_a, with_b = (
        client.get(_proxy_url(GRILLNING, "s1710001.mp4", **params))
        for params in ({}, {"v": "a"}, {"v": "b"})
    )
    assert plain.content == with_a.content == with_b.content
    assert plain.headers["etag"] == with_a.headers["etag"] == with_b.headers["etag"]


def test_head_is_the_get_without_a_body_for_every_status(
    client: TestClient, project: Path, cache_dir: Path
) -> None:
    _prepare(project, cache_dir, GRILLNING, "s1710001.mp4")
    url = _proxy_url(GRILLNING, "s1710001.mp4")
    etag = client.get(url).headers["etag"]

    cases = [
        (url, {}, 200),
        (url, {"Range": "bytes=0-99"}, 206),
        (url, {"If-None-Match": etag}, 304),
        (_proxy_url(GRILLNING, "s1710002.mp4"), {}, 404),
    ]
    for target, headers, status in cases:
        got, head = client.get(target, headers=headers), client.head(target, headers=headers)
        assert got.status_code == head.status_code == status
        assert head.content == b""
        assert head.headers.get("etag") == got.headers.get("etag")
        assert head.headers.get("content-type") == got.headers.get("content-type")
    ranged = client.head(url, headers={"Range": "bytes=0-99"})
    assert ranged.headers["content-length"] == "100"
    assert client.head(url).headers["content-length"] == str(FILE_SIZE)


def test_the_filmstrip_is_a_jpeg_with_the_same_behaviour(
    client: TestClient, project: Path, cache_dir: Path
) -> None:
    entry = _prepare(project, cache_dir, GRILLNING, "s1710001.mp4")
    url = _strip_url(GRILLNING, "s1710001.mp4")
    data = (entry / "filmstrip.jpg").read_bytes()

    response = client.get(url)
    assert response.status_code == 200
    assert response.content == data
    assert response.headers["content-type"] == "image/jpeg"
    assert response.headers["content-disposition"] == 'inline; filename="filmstrip.jpg"'
    assert response.headers["cache-control"] == "private, no-cache"
    assert (
        response.headers["etag"]
        != client.get(_proxy_url(GRILLNING, "s1710001.mp4")).headers["etag"]
    )
    ranged = client.get(url, headers={"Range": "bytes=0-99"})
    assert (ranged.status_code, ranged.content) == (206, data[:100])
    assert client.get(url, headers={"If-None-Match": response.headers["etag"]}).status_code == 304


def test_an_entry_with_a_proxy_and_no_filmstrip_is_200_and_404(
    client: TestClient, project: Path, cache_dir: Path
) -> None:
    _prepare(project, cache_dir, GRILLNING, "s1710001.mp4", filmstrip=False)

    assert client.get(_proxy_url(GRILLNING, "s1710001.mp4")).status_code == 200
    body = _assert_problem(client.get(_strip_url(GRILLNING, "s1710001.mp4")), 404, GRILLNING)
    assert "no filmstrip" in body["detail"]


def test_absent_is_a_404_problem_and_never_bytes(
    client: TestClient,
    project: Path,
    cache_dir: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _prepare(project, cache_dir, GRILLNING, "s1710001.mp4")
    clip = project / GRILLNING / "s1710003.mp4"
    _prepare(project, cache_dir, GRILLNING, "s1710003.mp4")
    clip.write_bytes(_content("replaced"))  # the entry now belongs to the previous bytes
    os.utime(clip, ns=(2_000_000_000_000_000_000, 2_000_000_000_000_000_000))
    urls = [
        _proxy_url(GRILLNING, "s1710002.mp4"),  # never prepared
        _proxy_url(GRILLNING, "s1710003.mp4"),  # replaced since
    ]
    _write(
        cache_dir / f".{'a' * 64}.{'b' * 32}.part" / "proxy.mp4", _content("being written")
    )  # a build in progress is not an entry
    before = _tree(tmp_path)

    for url in urls:
        for method in (client.get, client.head):
            response = method(url)
            assert response.status_code == 404
            assert response.status_code not in (200, 202, 204)
            assert "location" not in response.headers
            assert "etag" not in response.headers
            assert "cache-control" not in response.headers
        body = _assert_problem(client.get(url), 404, GRILLNING)
        assert "no proxy" in body["detail"]
        assert body["detail"].startswith(f"event {GRILLNING!r}")
    assert "s1710002.mp4" in client.get(urls[0]).json()["detail"]
    assert _tree(tmp_path) == before

    # another proxy version: the entry made for the version before is not this clip's
    monkeypatch.setattr(spec, "PROXY_VERSION", PROXY_VERSION + 1)
    assert client.get(_proxy_url(GRILLNING, "s1710001.mp4")).status_code == 404


def test_no_cache_directory_is_a_404_and_stays_missing(client: TestClient, cache_dir: Path) -> None:
    for url in (_proxy_url(GRILLNING, "s1710001.mp4"), _strip_url(GRILLNING, "s1710001.mp4")):
        assert client.get(url).status_code == 404
    assert not cache_dir.exists()


def test_ignored_and_symlinked_clips_are_served_and_linked_events_share_bytes(
    client: TestClient, project: Path, cache_dir: Path
) -> None:
    _prepare(project, cache_dir, TJORN, "s1710004.mp4")  # IGNORED by the document
    _prepare(project, cache_dir, GRILLNING, "länk.mp4")  # a link to a file outside the library

    assert client.get(_proxy_url(TJORN, "s1710004.mp4")).status_code == 200
    first = client.get(_proxy_url(GRILLNING, "länk.mp4"))
    second = client.get(_proxy_url(KALAS, "länk.mp4"))
    assert (first.status_code, second.status_code) == (200, 200)
    assert first.content == second.content == _proxy_bytes(GRILLNING, "länk.mp4")


def test_the_punctuated_identity_and_a_chapter_clip_resolve(
    client: TestClient, project: Path, cache_dir: Path
) -> None:
    _prepare(project, cache_dir, SKILJETECKEN, PUNCTUATED)
    _prepare(project, cache_dir, TJORN, "Kvällen/s1710002.mp4")

    assert client.get(_proxy_url(SKILJETECKEN, PUNCTUATED)).status_code == 200
    assert client.get(_strip_url(TJORN, "Kvällen/s1710002.mp4")).status_code == 200


@pytest.mark.parametrize(
    ("event", "clip"),
    [
        (SOMMARLOV, "borttagen.mp4"),
        (GRILLNING, "../2024-07-14 - Kalas/s1710001.mp4"),
        (GRILLNING, "original/x.mp4"),
        (TJORN, "Kvällen/../s1710001.mp4"),
        ("2024", "2024-06-27 - Grillning med grannar/s1710001.mp4"),
        ("2024/2024-12-24 - Finns inte", "s1710001.mp4"),
        (IGNORED_EVENT, "s1710001.mp4"),
    ],
)
@pytest.mark.parametrize("route", ["proxy", "filmstrip"])
def test_identities_that_are_not_clips_of_the_event_are_404_even_with_a_cache(
    client: TestClient, project: Path, cache_dir: Path, route: str, event: str, clip: str
) -> None:
    for prepared_event, prepared_clip in ((GRILLNING, "s1710001.mp4"), (KALAS, "s1710001.mp4")):
        _prepare(project, cache_dir, prepared_event, prepared_clip)

    response = client.get(_proxy_url(event, clip, route=route))

    _assert_problem(response, 404, event)


def test_a_clip_that_vanishes_after_the_listing_is_404(
    client: TestClient, project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _vanish_after_listing(monkeypatch, project / GRILLNING, "s1710002.mp4")

    _assert_problem(client.get(_proxy_url(GRILLNING, "s1710002.mp4")), 404, GRILLNING)


def test_a_missing_clip_parameter_is_422(client: TestClient) -> None:
    for route in ("proxy", "filmstrip"):
        response = client.get(f"{_event_url(GRILLNING)}/{route}")
        assert response.status_code == 422
        assert "etag" not in response.headers
        assert "cache-control" not in response.headers


def test_an_unreadable_proxy_is_a_502_before_any_status_line(
    client: TestClient,
    project: Path,
    cache_dir: Path,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _skip_as_root()
    entry = _prepare(project, cache_dir, GRILLNING, "s1710001.mp4")
    (entry / "proxy.mp4").chmod(0o000)
    try:
        with caplog.at_level(logging.WARNING, logger="auto_reel_ng.api.routes.media"):
            response = client.get(_proxy_url(GRILLNING, "s1710001.mp4"))
    finally:
        (entry / "proxy.mp4").chmod(0o644)

    body = _assert_problem(response, 502, GRILLNING)
    assert "failure" not in body
    assert "s1710001.mp4" in body["detail"]
    assert "Permission denied" in body["detail"]
    assert str(tmp_path) not in response.text
    assert [r for r in caplog.records if r.levelno == logging.WARNING]


def test_a_broken_config_is_a_502_without_a_kind_and_is_read_again(
    client: TestClient, project: Path, cache_dir: Path
) -> None:
    good = (project / "config.yaml").read_text(encoding="utf-8")
    _prepare(project, cache_dir, GRILLNING, "s1710001.mp4")
    (project / "config.yaml").write_text("proxies: [\n", encoding="utf-8")

    body = _assert_problem(client.get(_proxy_url(GRILLNING, "s1710001.mp4")), 502, GRILLNING)
    assert "failure" not in body

    (project / "config.yaml").write_text(
        f'proxies:\n  cache_dir: "{project / "cache"}"\n', encoding="utf-8"
    )
    inside = _assert_problem(client.get(_strip_url(GRILLNING, "s1710001.mp4")), 502, GRILLNING)
    assert "proxies.cache_dir" in inside["detail"]

    (project / "config.yaml").write_text(good, encoding="utf-8")
    assert client.get(_proxy_url(GRILLNING, "s1710001.mp4")).status_code == 200


def test_an_unlistable_event_folder_is_unreadable_disk(client: TestClient, project: Path) -> None:
    _skip_as_root()
    folder = project / GRILLNING
    folder.chmod(0o000)
    try:
        response = client.get(_proxy_url(GRILLNING, "s1710001.mp4"))
    finally:
        folder.chmod(0o755)

    body = _assert_problem(response, 502, GRILLNING)
    assert body["failure"] == "unreadable_disk"


def test_the_routes_need_no_database_no_subprocess_and_write_nothing(
    client: TestClient,
    project: Path,
    cache_dir: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _prepare(project, cache_dir, GRILLNING, "s1710001.mp4")
    _no_subprocess(monkeypatch)
    before = _tree(tmp_path)

    statuses = [
        client.get(_proxy_url(GRILLNING, "s1710001.mp4")).status_code,
        client.get(_strip_url(GRILLNING, "s1710001.mp4")).status_code,
        client.get(_proxy_url(GRILLNING, "s1710002.mp4")).status_code,
        client.head(_proxy_url(GRILLNING, "s1710002.mp4")).status_code,
    ]

    assert statuses == [200, 200, 404, 404]  # never 503
    assert _tree(tmp_path) == before


def test_neighbouring_routes_still_reach_their_own_handlers(
    client: TestClient, project: Path, cache_dir: Path
) -> None:
    _prepare(project, cache_dir, TJORN, "s1710001.mp4")

    assert client.get(f"{_event_url(TJORN)}/media?clip=s1710001.mp4").status_code == 200
    assert client.get(f"{_event_url(TJORN)}/reel").status_code == 200
    assert client.get(f"{_event_url(TJORN)}/thumbnail?clip=s1710001.mp4").status_code != 503
    assert client.get(_event_url(TJORN)).status_code == 503  # the detail: the database
    assert client.get(_proxy_url(TJORN, "s1710001.mp4")).status_code == 200


def test_every_request_passes_the_auth_hook(
    settings: ApiSettings, project: Path, cache_dir: Path
) -> None:
    _prepare(project, cache_dir, GRILLNING, "s1710001.mp4")
    calls: List[str] = []

    def checker(request: Request) -> Optional[Response]:
        calls.append(request.headers.get("range", ""))
        if request.headers.get("x-test") != "1":
            return JSONResponse(status_code=401, content={"detail": "unauthorized"})
        return None

    url = _proxy_url(GRILLNING, "s1710001.mp4")
    with TestClient(create_app(settings, auth_checker=checker)) as client:
        statuses = [
            client.get(url, headers={"X-Test": "1"}).status_code,
            client.get(url, headers={"X-Test": "1", "Range": "bytes=0-9"}).status_code,
            client.get(url, headers={"X-Test": "1", "Range": "bytes=10-19"}).status_code,
        ]
        rejected = client.get(url, headers={"Range": "bytes=0-9"})
        strip_rejected = client.get(_strip_url(GRILLNING, "s1710001.mp4"))

    assert statuses == [200, 206, 206]
    assert calls == ["", "bytes=0-9", "bytes=10-19", "bytes=0-9", ""]
    assert rejected.status_code == strip_rejected.status_code == 401
    assert _proxy_bytes(GRILLNING, "s1710001.mp4")[:10] not in rejected.content


# --- task 3.2: a real proxy, end to end ---------------------------------------------------


def _synthetic_clip(runtime: FfmpegRuntime, path: Path, seconds: float) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [runtime.ffmpeg_path, "-y", "-v", "error", "-f", "lavfi"]
        + ["-i", f"testsrc2=s=640x360:r=25:d={seconds}"]
        + ["-f", "lavfi", "-i", f"sine=frequency=440:sample_rate=48000:d={seconds}"]
        + ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(path)],
        check=True,
        capture_output=True,
    )
    return path


def _ffprobe(runtime: FfmpegRuntime, path: Path) -> Dict[str, Any]:
    import json  # pylint: disable=import-outside-toplevel

    out = subprocess.run(
        [runtime.ffprobe_path, "-v", "error", "-show_streams", "-show_format"]
        + ["-of", "json", str(path)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    parsed: Dict[str, Any] = json.loads(out)
    return parsed


@pytest.mark.has_ffmpeg
def test_a_real_proxy_and_filmstrip_are_served_unchanged(
    runtime: FfmpegRuntime, project: Path, cache_dir: Path, tmp_path: Path, client: TestClient
) -> None:
    clip = _synthetic_clip(runtime, project / GRILLNING / "echt.mp4", 2.0)
    settings = ProxySettings(cache_dir)
    entry = ensure_proxy(clip, settings=settings, runtime=runtime, profile=CPUProfile())
    ensure_filmstrip(clip, entry, runtime=runtime)

    proxy = client.get(_proxy_url(GRILLNING, "echt.mp4"))
    strip = client.get(_strip_url(GRILLNING, "echt.mp4"))

    assert proxy.status_code == 200
    assert proxy.content == entry.proxy_path.read_bytes()
    served = tmp_path / "served.mp4"
    served.write_bytes(proxy.content)
    probed = _ffprobe(runtime, served)
    streams = {s["codec_type"]: s for s in probed["streams"]}
    assert (streams["video"]["codec_name"], streams["audio"]["codec_name"]) == ("h264", "aac")
    assert len(probed["streams"]) == 2
    assert abs(float(streams["video"]["duration"]) - 2.0) <= 0.05

    tail = client.get(_proxy_url(GRILLNING, "echt.mp4"), headers={"Range": "bytes=-1000"})
    assert (tail.status_code, tail.content) == (206, entry.proxy_path.read_bytes()[-1000:])
    # faststart: the moov box precedes mdat
    head = entry.proxy_path.read_bytes()[:4096]
    assert head.find(b"moov") != -1 and head.find(b"moov") < head.find(b"mdat")

    assert strip.status_code == 200
    assert strip.headers["content-type"] == "image/jpeg"
    assert strip.content[:2] == b"\xff\xd8" and strip.content[-2:] == b"\xff\xd9"


@pytest.mark.has_ffmpeg
def test_a_sub_second_clip_has_a_proxy_and_a_one_tile_filmstrip(
    runtime: FfmpegRuntime, project: Path, cache_dir: Path, client: TestClient
) -> None:
    clip = _synthetic_clip(runtime, project / GRILLNING / "kort.mp4", 0.48)
    entry = ensure_proxy(
        clip, settings=ProxySettings(cache_dir), runtime=runtime, profile=CPUProfile()
    )
    ensure_filmstrip(clip, entry, runtime=runtime)

    assert client.get(_proxy_url(GRILLNING, "kort.mp4")).status_code == 200
    strip = client.get(_strip_url(GRILLNING, "kort.mp4"))
    assert strip.status_code == 200
    assert strip.content[:2] == b"\xff\xd8"
