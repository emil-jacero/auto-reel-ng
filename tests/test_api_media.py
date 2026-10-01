"""Tests for the media endpoints (change ``media-endpoints``, api-service "Media files are
streamed with ranges and validators", "Clip media endpoint", "Rendered movie endpoint").

Three layers, as the routes are built:

- ``api.media``'s lookups: which clip (the thumbnail's own lookup, ``listed_clip``) and
  which movie (the gate's rule, ``staleness.rendered_output``) a route serves, and the
  stat-and-open that proves a file readable before any status line is sent.
- ``api.media.media_response``: the 304 or the streamed ``FileResponse``.
- the routes themselves, on an app whose database URL points at a closed port (the
  routes never need it). Clips are plain files of distinct, known bytes, so a byte range
  is compared exactly; nothing here runs ffmpeg.
"""

from __future__ import annotations

import dataclasses
import json
import logging
import os
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Callable, Dict, Iterator, List, Optional, Tuple
from urllib.parse import quote

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fastapi.testclient import TestClient
from starlette.responses import FileResponse

from auto_reel_ng.api import events_read
from auto_reel_ng.api import media as media_module
from auto_reel_ng.api.app import create_app
from auto_reel_ng.api.media import (
    MEDIA_CACHE_CONTROL,
    MEDIA_TYPES,
    MediaFile,
    MediaGoneError,
    MediaReadError,
    MovieNotFoundError,
    clip_media,
    etag_matches,
    media_response,
    movie_media,
    open_media,
)
from auto_reel_ng.api.schemas import EventFailure
from auto_reel_ng.api.settings import ApiSettings, resolve_api_settings
from auto_reel_ng.event.discovery import VIDEO_EXTENSIONS, DiskListing
from auto_reel_ng.event.metadata import load_event_document
from auto_reel_ng.render import output_relpath
from auto_reel_ng.staleness import COMPONENTS, manifest_path, rendered_output

#: A closed port, as the schema dump uses: the media routes must never need it.
UNREACHABLE_DATABASE_URL = "postgresql+psycopg://media:media@127.0.0.1:1/media"

GRILLNING = "2024/2024-06-27 - Grillning med grannar"
KALAS = "2024/2024-07-14 - Kalas"
KALAS_LOWER = "2024/2024-07-14 - kalas"  # a case-only output collision with Kalas
UTBRYTNING = "2024/2024-07-15 - Utbrytning"
TJORN = "2024/2024-08-20 - Två kapitel - Tjörn"
SOMMARLOV = "2024/2024-09-01 - Sommarlov"
SKILJETECKEN = "2024/2024-09-10 - Skiljetecken"
TRASIG_YAML = "2024/2024-09-15 - Trasig yaml"
IGNORED_EVENT = "2024/2024-09-20 - Aldrig"  # holds .reelignore: not an event of the list
TRASIG = "2024/2024-10-05 - Trasig"  # a zero-byte clip
OMOJLIGT = "2024/2024-02-30 - Omöjligt datum"  # the folder date is not a real date

#: A chapter-folder identity with spaces, punctuation, a ``+`` and Swedish letters.
PUNCTUATED = "Kväll, del 2/a+b & c #1.mp4"
#: The ``Content-Disposition`` of the punctuated clip (RFC 5987).
PUNCTUATED_DISPOSITION = "inline; filename*=utf-8''a%2Bb%20%26%20c%20%231.mp4"

#: Each clip's size: big enough for ranges, small enough to compare whole.
CLIP_SIZE = 300 * 1024

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

#: Grillning retitled after its render: its movie is under the old name.
GRILLNING_RETITLED_REEL = """\
version: 0
metadata:
  title: Grillkväll
  date: 2024-06-27
chapters:
  - name: ''
    clips:
      - s1710001.mp4
"""
#: The name Grillning's last render recorded, before the retitle.
GRILLNING_OLD_MOVIE = "2024-06-27 - Grillning med grannar.mp4"
KALAS_MOVIE = "2024-07-14 - Kalas.mp4"

#: A title that climbs out of the output directory through the naming rule.
UTBRYTNING_REEL = """\
version: 0
metadata:
  title: x/../../../outside
  date: 2024-07-15
"""


def _content(tag: str, size: int = CLIP_SIZE) -> bytes:
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
def project(tmp_path: Path) -> Path:
    """A year-event library shaped like the thumbnail tests', with real-sized clips."""
    root = tmp_path / "proj"
    for name in ("s1710001.mp4", "s1710002.mp4", "s1710003.mp4", "s1710004.mp4"):
        _write(root / GRILLNING / name, _content(f"grill {name}"))
    _write(root / GRILLNING / "CLIP.MP4", _content("upper"))
    _write(root / GRILLNING / "s1710005.mov", _content("mov"))
    _write(root / GRILLNING / "original" / "x.mp4", _content("original of grill"))
    _write(tmp_path / "samples" / "extern.mp4", _content("outside the library"))
    (root / GRILLNING / "länk.mp4").symlink_to(tmp_path / "samples" / "extern.mp4")

    _write(root / KALAS / "s1710001.mp4", _content("kalas"))
    _write(root / KALAS_LOWER / "s1710004.mp4", _content("kalas lower"))
    _write(root / IGNORED_EVENT / "s1710001.mp4", _content("never rendered"))
    _write(root / IGNORED_EVENT / ".reelignore")

    tjorn = root / TJORN
    for identity in ("s1710001.mp4", "s1710004.mp4", "Kvällen/s1710002.mp4"):
        _write(tjorn / identity, _content(f"tjorn {identity}"))
    _write(tjorn / "Kvällen" / "s1710003.mp4", _content("tjorn kvällen 3"))
    (tjorn / "reel.yaml").write_text(TJORN_REEL, encoding="utf-8")
    (tjorn / "dangling.mp4").symlink_to(tmp_path / "nowhere.mp4")

    sommarlov = root / SOMMARLOV
    _write(sommarlov / "s1710002.mp4", _content("sommar 2"))
    _write(sommarlov / "s1710004.mp4", _content("sommar 4"))
    (sommarlov / "reel.yaml").write_text(SOMMARLOV_REEL, encoding="utf-8")

    _write(root / SKILJETECKEN / PUNCTUATED, _content("punctuated"))

    _write(root / TRASIG_YAML / "s1710001.mp4", _content("broken yaml"))
    (root / TRASIG_YAML / "reel.yaml").write_text("version: 0\nchapters: [\n", encoding="utf-8")

    _write(root / TRASIG / "trasig.mp4", b"")
    _write(root / OMOJLIGT / "s1710001.mp4", _content("omöjligt"))
    return root


@pytest.fixture
def settings(project: Path) -> ApiSettings:
    return resolve_api_settings(project, env={"DATABASE_URL": UNREACHABLE_DATABASE_URL})


@pytest.fixture
def output_dir(settings: ApiSettings, tmp_path: Path) -> Path:
    """The default output directory, a sibling of the project: ``proj-output``."""
    assert settings.output_dir == tmp_path.resolve() / "proj-output"
    return settings.output_dir


def _write_manifest(event_dir: Path, output: str) -> None:
    """A version-1 render manifest recording ``output``, written as the engine writes it."""
    path = manifest_path(event_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "fingerprint": "f",
        "components": {name: "c" for name in COMPONENTS},
        "output": output,
        "engine_identity": "e",
        "written_at": "2024-07-14T20:00:00+00:00",
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _expected_movie(settings: ApiSettings, event: str) -> Path:
    """The event's expected output path, as its staleness verdict computes it."""
    document, _seeded = load_event_document(
        settings.project_root / event, order=settings.clip_order
    )
    return settings.output_dir / output_relpath(document.metadata)


@pytest.fixture
def movies(project: Path, settings: ApiSettings, output_dir: Path) -> Dict[str, Path]:
    """Kalas rendered; Grillning rendered, then retitled. Returns each movie file."""
    kalas = output_dir / "2024" / KALAS_MOVIE
    _write(kalas, _content("kalas movie"))
    _write_manifest(project / KALAS, KALAS_MOVIE)

    grillning = output_dir / "2024" / GRILLNING_OLD_MOVIE
    _write(grillning, _content("grillning movie"))
    _write_manifest(project / GRILLNING, GRILLNING_OLD_MOVIE)
    (project / GRILLNING / "reel.yaml").write_text(GRILLNING_RETITLED_REEL, encoding="utf-8")
    return {KALAS: kalas, GRILLNING: grillning}


# --- task 3.1: which clip is served -------------------------------------------------------


def test_the_type_table_covers_every_extension_discovery_lists() -> None:
    assert set(MEDIA_TYPES) == VIDEO_EXTENSIONS
    assert all(value.startswith("video/") for value in MEDIA_TYPES.values())


@pytest.mark.parametrize(
    ("event", "clip"),
    [
        (GRILLNING, "s1710001.mp4"),
        (TJORN, "Kvällen/s1710002.mp4"),
        (TJORN, "s1710004.mp4"),  # IGNORED by the document, still on disk
        (SKILJETECKEN, PUNCTUATED),
        (GRILLNING, "länk.mp4"),  # a symlink to a file outside the project
    ],
)
def test_a_listed_clip_resolves(
    settings: ApiSettings, project: Path, event: str, clip: str
) -> None:
    media = clip_media(settings, event, clip)

    target = os.stat(project / event / clip)  # follows the link
    assert media.path == project / event / clip
    assert media.name == Path(clip).name
    assert (media.stat.st_size, media.stat.st_mtime_ns) == (target.st_size, target.st_mtime_ns)
    assert media.etag == '"%x-%x"' % (target.st_size, target.st_mtime_ns)
    assert media.media_type == "video/mp4"


def test_a_symlinked_clip_carries_its_target_s_facts(
    settings: ApiSettings, project: Path, tmp_path: Path
) -> None:
    target = tmp_path / "samples" / "extern.mp4"
    os.utime(target, ns=(1_700_000_000_000_000_000, 1_700_000_000_123_456_789))

    media = clip_media(settings, GRILLNING, "länk.mp4")

    assert media.stat.st_size == target.stat().st_size == CLIP_SIZE
    assert media.stat.st_mtime_ns == 1_700_000_000_123_456_789
    assert media.etag == '"%x-%x"' % (CLIP_SIZE, 1_700_000_000_123_456_789)
    assert (project / GRILLNING / "länk.mp4").lstat().st_mtime_ns != media.stat.st_mtime_ns


@pytest.mark.parametrize(
    ("clip", "media_type"), [("CLIP.MP4", "video/mp4"), ("s1710005.mov", "video/quicktime")]
)
def test_the_type_follows_the_extension_case_insensitively(
    settings: ApiSettings, clip: str, media_type: str
) -> None:
    assert clip_media(settings, GRILLNING, clip).media_type == media_type


@pytest.mark.parametrize(
    ("event", "clip"),
    [
        (SOMMARLOV, "borttagen.mp4"),  # MISSING: the document names it, disk lacks it
        (GRILLNING, "original/x.mp4"),
        (TJORN, "Kvällen/../s1710001.mp4"),  # normalizes to a clip, but is not its identity
        (GRILLNING, "../2024-07-14 - Kalas/s1710001.mp4"),
        (TJORN, "dangling.mp4"),
        (TJORN, ""),
    ],
)
def test_an_identity_discovery_does_not_list_is_not_found(
    settings: ApiSettings, event: str, clip: str
) -> None:
    with pytest.raises(events_read.ClipNotFoundError):
        clip_media(settings, event, clip)


def test_an_absolute_path_is_not_an_identity(settings: ApiSettings, project: Path) -> None:
    with pytest.raises(events_read.ClipNotFoundError):
        clip_media(settings, TJORN, str(project / TJORN / "s1710001.mp4"))


@pytest.mark.parametrize(
    ("event_id", "clip"),
    [
        ("2024/2024-12-24 - Finns inte", "s1710001.mp4"),
        ("2024", "2024-06-27 - Grillning med grannar/s1710001.mp4"),
        (f"{GRILLNING}/original", "x.mp4"),
        (IGNORED_EVENT, "s1710001.mp4"),
    ],
)
def test_a_folder_that_is_not_an_event_is_not_found(
    settings: ApiSettings, event_id: str, clip: str
) -> None:
    with pytest.raises(events_read.EventNotFoundError):
        clip_media(settings, event_id, clip)


def test_an_unlistable_event_folder_is_unreadable_disk(
    settings: ApiSettings, project: Path
) -> None:
    _skip_as_root()
    event_dir = project / GRILLNING
    event_dir.chmod(0)
    try:
        with pytest.raises(events_read.EventReadError) as caught:
            clip_media(settings, GRILLNING, "s1710001.mp4")
    finally:
        event_dir.chmod(0o755)
    assert caught.value.failure is EventFailure.UNREADABLE_DISK


def test_an_unparseable_reel_yaml_does_not_stop_a_clip(settings: ApiSettings) -> None:
    assert clip_media(settings, TRASIG_YAML, "s1710001.mp4").path.name == "s1710001.mp4"


def test_open_media_answers_a_dangling_link_and_a_directory_as_gone(
    project: Path,
) -> None:
    with pytest.raises(MediaGoneError):
        open_media(project / TJORN / "dangling.mp4", label="dangling.mp4")
    with pytest.raises(MediaGoneError):
        open_media(project / TJORN / "Kvällen", label="Kvällen")


def test_an_unreadable_clip_is_a_read_error_without_server_paths(
    settings: ApiSettings, project: Path, tmp_path: Path
) -> None:
    _skip_as_root()
    clip = project / GRILLNING / "s1710002.mp4"
    clip.chmod(0)
    try:
        with pytest.raises(MediaReadError) as caught:
            clip_media(settings, GRILLNING, "s1710002.mp4")
    finally:
        clip.chmod(0o644)
    assert "s1710002.mp4" in str(caught.value)
    assert "Permission denied" in str(caught.value)
    assert str(caught.value) == "s1710002.mp4: cannot read the file: Permission denied"
    assert str(tmp_path) not in str(caught.value)


def _vanish_after_listing(monkeypatch: pytest.MonkeyPatch, event_dir: Path, clip: str) -> None:
    """Delete ``clip`` between discovery's listing and the open: a real race, replayed."""
    real_scan_event = events_read.scan_event

    def scan_then_delete(directory: Path) -> DiskListing:
        listing = real_scan_event(directory)
        (event_dir / clip).unlink()
        return listing

    monkeypatch.setattr(events_read, "scan_event", scan_then_delete)


def test_a_clip_that_vanishes_after_the_listing_is_gone(
    settings: ApiSettings, project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _vanish_after_listing(monkeypatch, project / GRILLNING, "s1710002.mp4")

    with pytest.raises(MediaGoneError) as caught:
        clip_media(settings, GRILLNING, "s1710002.mp4")

    assert caught.value.label == "s1710002.mp4"


# --- task 3.2: which file is the movie ----------------------------------------------------


def test_a_rendered_event_s_movie_is_its_expected_file(
    settings: ApiSettings, movies: Dict[str, Path]
) -> None:
    media = movie_media(settings, KALAS)

    assert media.path == movies[KALAS]
    assert media.name == KALAS_MOVIE
    assert media.media_type == "video/mp4"


def test_a_retitled_event_s_movie_is_the_one_under_its_old_name(
    settings: ApiSettings, movies: Dict[str, Path]
) -> None:
    assert movie_media(settings, GRILLNING).path == movies[GRILLNING]


def test_a_file_at_the_expected_path_without_a_render_record_is_not_the_movie(
    settings: ApiSettings, movies: Dict[str, Path]
) -> None:
    """kalas names Kalas's file (a case-only collision): the hard link plays a
    case-insensitive disk, so kalas's expected path holds Kalas's movie."""
    expected = _expected_movie(settings, KALAS_LOWER)
    if not expected.exists():
        os.link(movies[KALAS], expected)
    assert expected.is_file()

    with pytest.raises(MovieNotFoundError):
        movie_media(settings, KALAS_LOWER)


def test_a_directory_at_the_expected_path_is_not_the_movie(
    settings: ApiSettings,
    movies: Dict[str, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    movies[KALAS].rename(tmp_path / "aside.mp4")
    movies[KALAS].mkdir()
    _write(movies[KALAS] / "inside.mp4", _content("inside"))
    opened: List[Path] = []
    real_open_media = media_module.open_media

    def spy(path: Path, *, label: str) -> MediaFile:
        opened.append(path)
        return real_open_media(path, label=label)

    monkeypatch.setattr(media_module, "open_media", spy)

    with pytest.raises(MovieNotFoundError):
        movie_media(settings, KALAS)
    assert opened == []


def test_a_deleted_movie_is_not_found(settings: ApiSettings, movies: Dict[str, Path]) -> None:
    movies[KALAS].unlink()
    with pytest.raises(MovieNotFoundError):
        movie_media(settings, KALAS)


@pytest.mark.parametrize("recorded", ["../x.mp4", "absolute", ""])
def test_a_recorded_name_that_is_not_a_bare_file_name_is_never_served(
    settings: ApiSettings,
    project: Path,
    movies: Dict[str, Path],
    output_dir: Path,
    tmp_path: Path,
    recorded: str,
) -> None:
    movies[KALAS].unlink()
    for place in (tmp_path / "x.mp4", output_dir / "x.mp4", output_dir / "2024" / "x.mp4"):
        _write(place, _content("bait"))
    _write_manifest(
        project / KALAS, str(tmp_path / "x.mp4") if recorded == "absolute" else recorded
    )

    with pytest.raises(MovieNotFoundError):
        movie_media(settings, KALAS)


@pytest.fixture
def utbrytning(project: Path, output_dir: Path, tmp_path: Path) -> Path:
    """An event whose title climbs out of the output directory to ``outside.mp4``.

    The folder ``2024/2024-07-15 - x/`` exists, so the OS resolves the ``..`` segments of
    the expected path ``proj-output/2024/2024-07-15 - x/../../../outside.mp4``.
    """
    event_dir = project / UTBRYTNING
    _write(event_dir / "s1710001.mp4", _content("utbrytning"))
    (event_dir / "reel.yaml").write_text(UTBRYTNING_REEL, encoding="utf-8")
    _write_manifest(event_dir, "2024-07-15 - Utbrytning.mp4")
    (output_dir / "2024" / "2024-07-15 - x").mkdir(parents=True)
    _write(tmp_path / "outside.mp4", _content("outside the output directory"))
    return tmp_path / "outside.mp4"


def test_a_title_cannot_climb_out_of_the_output_directory(
    settings: ApiSettings, project: Path, utbrytning: Path
) -> None:
    expected = _expected_movie(settings, UTBRYTNING)
    found = rendered_output(project / UTBRYTNING, expected)
    assert found is not None  # the gate counts it: the guard, not the gate, refuses it
    assert os.path.samefile(found, utbrytning)

    with pytest.raises(MovieNotFoundError):
        movie_media(settings, UTBRYTNING)


def test_a_symlinked_year_folder_in_the_output_directory_is_followed(
    settings: ApiSettings, project: Path, tmp_path: Path
) -> None:
    other = tmp_path / "other-disk" / "2024" / KALAS_MOVIE
    _write(other, _content("kalas on another disk"))
    (tmp_path / "proj-output-2").mkdir()
    (tmp_path / "proj-output-2" / "2024").symlink_to(tmp_path / "other-disk" / "2024")
    _write_manifest(project / KALAS, KALAS_MOVIE)
    linked = dataclasses.replace(settings, output_dir=tmp_path / "proj-output-2")

    media = movie_media(linked, KALAS)

    assert media.path == tmp_path / "proj-output-2" / "2024" / KALAS_MOVIE
    assert media.stat.st_size == other.stat().st_size
    assert rendered_output(project / KALAS, _expected_movie(linked, KALAS)) == media.path


def test_an_unparseable_reel_yaml_is_an_event_read_error(settings: ApiSettings) -> None:
    with pytest.raises(events_read.EventReadError) as caught:
        movie_media(settings, TRASIG_YAML)
    assert caught.value.failure is EventFailure.UNPARSEABLE_REEL_YAML


def test_unusable_metadata_is_the_event_detail_s_failure(settings: ApiSettings) -> None:
    with pytest.raises(events_read.EventReadError) as caught:
        movie_media(settings, OMOJLIGT)
    # The detail raises before it reads the job store or needs a runtime.
    with pytest.raises(events_read.EventReadError) as detail:
        events_read.get_event(settings, OMOJLIGT, None, None)  # type: ignore[arg-type]

    assert caught.value.failure is EventFailure.UNUSABLE_METADATA
    assert caught.value.detail == detail.value.detail


@pytest.mark.parametrize("event_id", ["2024/2024-12-24 - Finns inte", "2024"])
def test_a_movie_of_a_folder_that_is_not_an_event_is_event_not_found(
    settings: ApiSettings, event_id: str
) -> None:
    with pytest.raises(events_read.EventNotFoundError):
        movie_media(settings, event_id)


def test_an_unreadable_movie_names_its_file_not_its_path(
    settings: ApiSettings, movies: Dict[str, Path], tmp_path: Path
) -> None:
    _skip_as_root()
    movies[KALAS].chmod(0)
    try:
        with pytest.raises(MediaReadError) as caught:
            movie_media(settings, KALAS)
    finally:
        movies[KALAS].chmod(0o644)
    assert str(caught.value) == f"{KALAS_MOVIE}: cannot read the file: Permission denied"
    assert str(tmp_path) not in str(caught.value)


def _snapshot(root: Path) -> Dict[str, Tuple[int, int]]:
    """Every path under ``root`` (links not followed) with its size and ``st_mtime_ns``."""
    facts: Dict[str, Tuple[int, int]] = {}
    for directory, dirnames, filenames in os.walk(root):
        for name in dirnames + filenames:
            path = Path(directory) / name
            info = path.lstat()
            facts[str(path)] = (info.st_size, info.st_mtime_ns)
    return facts


def test_the_lookups_change_nothing_on_disk(
    settings: ApiSettings, movies: Dict[str, Path], utbrytning: Path, tmp_path: Path
) -> None:
    before = _snapshot(tmp_path)

    for event in (KALAS, GRILLNING):
        movie_media(settings, event)
    for event in (KALAS_LOWER, UTBRYTNING, SOMMARLOV, TJORN):
        with pytest.raises(MovieNotFoundError):
            movie_media(settings, event)
    for event in (TRASIG_YAML, OMOJLIGT):
        with pytest.raises(events_read.EventReadError):
            movie_media(settings, event)
    for event, clip in ((TJORN, "Kvällen/s1710002.mp4"), (TRASIG, "trasig.mp4")):
        clip_media(settings, event, clip)

    assert _snapshot(tmp_path) == before


# --- task 4.1: the response helper --------------------------------------------------------


@pytest.fixture
def clip_file(settings: ApiSettings) -> MediaFile:
    return clip_media(settings, GRILLNING, "s1710001.mp4")


def test_a_media_response_is_a_streamed_file_response(clip_file: MediaFile) -> None:
    """A ``FileResponse`` streams in chunks: the "never in memory" guard (the test client
    buffers bodies, so a test cannot observe streaming itself)."""
    response = media_response(clip_file, None)

    assert isinstance(response, FileResponse)
    assert response.stat_result is clip_file.stat
    assert response.headers["etag"] == clip_file.etag
    assert response.headers["cache-control"] == MEDIA_CACHE_CONTROL
    assert response.headers["content-type"] == "video/mp4"
    assert response.headers["content-disposition"].startswith("inline")


@pytest.mark.parametrize(
    "header",
    ["{tag}", "W/{tag}", '"other", {tag}', "*", '"other",W/{tag}'],
)
def test_a_matching_if_none_match_is_a_304(clip_file: MediaFile, header: str) -> None:
    response = media_response(clip_file, header.format(tag=clip_file.etag))

    assert not isinstance(response, FileResponse)
    assert response.status_code == 304
    assert response.body == b""
    assert dict(response.headers) == {
        "etag": clip_file.etag,
        "cache-control": MEDIA_CACHE_CONTROL,
    }


def test_a_non_matching_if_none_match_is_the_file(clip_file: MediaFile) -> None:
    assert isinstance(media_response(clip_file, '"other"'), FileResponse)


def test_etag_matches_has_no_star_rule() -> None:
    assert etag_matches('"a", W/"b"', '"b"')
    assert not etag_matches("*", '"b"')
    assert not etag_matches('"bb"', '"b"')


# --- task 4.1: the routes over HTTP -------------------------------------------------------


@pytest.fixture
def app(settings: ApiSettings) -> FastAPI:
    return create_app(settings)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


def _event_url(event: str) -> str:
    return f"/api/v1/events/{quote(event, safe='/')}"


def _clip_url(event: str, clip: str, *, safe: str = "", **params: str) -> str:
    """The route's URL: the event id per-segment encoded, ``clip`` as a query value."""
    query = f"clip={quote(clip, safe=safe)}"
    for name, value in params.items():
        query += f"&{name}={quote(value, safe='')}"
    return f"{_event_url(event)}/media?{query}"


def _movie_url(event: str) -> str:
    return f"{_event_url(event)}/movie"


def _assert_no_caching_headers(response: object) -> None:
    headers = response.headers  # type: ignore[attr-defined]
    assert "cache-control" not in headers
    assert "etag" not in headers


def _assert_problem(response: object, status: int, event_id: str) -> Dict[str, object]:
    assert response.status_code == status  # type: ignore[attr-defined]
    assert response.headers["content-type"] == "application/json"  # type: ignore[attr-defined]
    body: Dict[str, object] = response.json()  # type: ignore[attr-defined]
    assert body["status"] == status
    assert body["event_id"] == event_id
    _assert_no_caching_headers(response)
    return body


def _assert_media_headers(response: object, media_type: str = "video/mp4") -> None:
    headers = response.headers  # type: ignore[attr-defined]
    assert headers["content-type"] == media_type
    assert headers["accept-ranges"] == "bytes"
    assert headers["last-modified"]
    assert headers["etag"].startswith('"') and "-" in headers["etag"]
    assert headers["cache-control"] == MEDIA_CACHE_CONTROL
    assert headers["content-disposition"].startswith("inline; filename")


GRILL_1 = _content("grill s1710001.mp4")


def test_a_clip_without_range_is_the_whole_file(client: TestClient) -> None:
    response = client.get(_clip_url(GRILLNING, "s1710001.mp4"))

    assert response.status_code == 200
    assert response.content == GRILL_1
    assert response.headers["content-length"] == str(CLIP_SIZE)
    _assert_media_headers(response)
    assert response.headers["content-disposition"] == 'inline; filename="s1710001.mp4"'


@pytest.mark.parametrize(
    ("value", "first", "last"),
    [
        ("bytes=0-99", 0, 99),
        ("bytes=1000-", 1000, CLIP_SIZE - 1),
        ("bytes=-500", CLIP_SIZE - 500, CLIP_SIZE - 1),
        (f"bytes=-{CLIP_SIZE + 5}", 0, CLIP_SIZE - 1),  # a suffix longer than the file
        (f"bytes=0-{CLIP_SIZE * 10}", 0, CLIP_SIZE - 1),  # a last byte past the end
    ],
)
def test_one_satisfiable_range_is_a_206(
    client: TestClient, value: str, first: int, last: int
) -> None:
    response = client.get(_clip_url(GRILLNING, "s1710001.mp4"), headers={"Range": value})

    assert response.status_code == 206
    assert response.content == GRILL_1[first : last + 1]
    assert response.headers["content-range"] == f"bytes {first}-{last}/{CLIP_SIZE}"
    assert response.headers["content-length"] == str(last + 1 - first)
    _assert_media_headers(response)


@pytest.mark.parametrize("value", [f"bytes={CLIP_SIZE}-", "bytes=-0"])
def test_a_range_past_the_end_is_a_416(client: TestClient, value: str) -> None:
    response = client.get(_clip_url(GRILLNING, "s1710001.mp4"), headers={"Range": value})

    assert response.status_code == 416
    assert response.headers["content-range"] == f"bytes */{CLIP_SIZE}"
    assert response.content == b""


@pytest.mark.parametrize("value", ["lines=0-1", "bytes=abc", "bytes=5-3"])
def test_a_malformed_range_is_a_plain_text_400(client: TestClient, value: str) -> None:
    response = client.get(_clip_url(GRILLNING, "s1710001.mp4"), headers={"Range": value})

    assert response.status_code == 400
    assert response.headers["content-type"].startswith("text/plain")
    assert GRILL_1[:64] not in response.content


def test_ranges_browsers_never_send_stay_bounded(client: TestClient) -> None:
    """Ranges browsers never send get the framework's answer (design Risks), which never
    sends a byte the range does not name and is never a 5xx."""
    url = _clip_url(GRILLNING, "s1710001.mp4")

    multipart = client.get(url, headers={"Range": "bytes=0-0,2-2"})
    assert multipart.status_code == 206
    assert multipart.headers["content-type"].startswith("multipart/byteranges")
    parts = multipart.content
    assert f"Content-Range: bytes 0-0/{CLIP_SIZE}".encode() in parts
    assert f"Content-Range: bytes 2-2/{CLIP_SIZE}".encode() in parts
    assert GRILL_1[0:3] not in parts  # bytes 0 and 2 each, never the run 0..2

    # ``bytes=5-4`` (last byte = first byte - 1): Starlette 1.3.1 answers an empty 206 with
    # ``Content-Range: bytes 5-4/<size>``; Starlette 1.7.0 refuses it as malformed (400).
    # The spec allows 206, 400 or 416 here, so either version passes; any byte would not.
    empty = client.get(url, headers={"Range": "bytes=5-4"})
    assert empty.status_code in (206, 400, 416)
    if empty.status_code == 206:
        assert empty.content == b""
        assert empty.headers["content-range"] == f"bytes 5-4/{CLIP_SIZE}"
    else:  # a plain-text refusal, no file bytes
        assert empty.headers["content-type"].startswith("text/plain")
        assert GRILL_1[:64] not in empty.content


def test_if_range_serves_the_range_only_for_the_current_file(client: TestClient) -> None:
    url = _clip_url(GRILLNING, "s1710001.mp4")
    etag = client.get(url).headers["etag"]

    current = client.get(url, headers={"Range": "bytes=0-99", "If-Range": etag})
    stale = client.get(url, headers={"Range": "bytes=0-99", "If-Range": '"old"'})

    assert current.status_code == 206
    assert current.content == GRILL_1[:100]
    assert stale.status_code == 200
    assert stale.content == GRILL_1


@pytest.mark.parametrize(
    "headers",
    [
        lambda tag: [("If-None-Match", tag)],
        lambda tag: [("If-None-Match", tag), ("Range", "bytes=0-")],
        lambda tag: [("If-None-Match", '"other"'), ("If-None-Match", tag)],  # two lines
    ],
)
def test_a_matching_if_none_match_is_a_304_without_a_body(
    client: TestClient, headers: Callable[[str], List[Tuple[str, str]]]
) -> None:
    url = _clip_url(GRILLNING, "s1710001.mp4")
    etag = client.get(url).headers["etag"]

    response = client.get(url, headers=headers(etag))

    assert response.status_code == 304
    assert response.content == b""
    assert response.headers["etag"] == etag
    assert response.headers["cache-control"] == MEDIA_CACHE_CONTROL


def test_a_replaced_file_gets_a_new_entity_tag(client: TestClient, project: Path) -> None:
    url = _clip_url(GRILLNING, "s1710001.mp4")
    old_etag = client.get(url).headers["etag"]
    clip = project / GRILLNING / "s1710001.mp4"
    replacement = _content("another recording", CLIP_SIZE + 1000)
    clip.write_bytes(replacement)
    later = clip.stat().st_mtime_ns + 5_000_000_000
    os.utime(clip, ns=(later, later))

    response = client.get(url, headers={"If-None-Match": old_etag})

    assert response.status_code == 200
    assert response.content == replacement
    assert response.headers["etag"] != old_etag


def test_the_version_parameter_changes_nothing(client: TestClient) -> None:
    plain = client.get(_clip_url(GRILLNING, "s1710001.mp4"))
    first = client.get(_clip_url(GRILLNING, "s1710001.mp4", v="2024-06-27T14:03:11.123456Z"))
    second = client.get(_clip_url(GRILLNING, "s1710001.mp4", v="other"))

    for response in (first, second):
        assert response.status_code == 200
        assert response.content == plain.content
        assert response.headers["etag"] == plain.headers["etag"]


@pytest.mark.parametrize(
    ("clip", "media_type"), [("CLIP.MP4", "video/mp4"), ("s1710005.mov", "video/quicktime")]
)
def test_the_content_type_follows_the_extension(
    client: TestClient, clip: str, media_type: str
) -> None:
    response = client.get(_clip_url(GRILLNING, clip))

    assert response.status_code == 200
    _assert_media_headers(response, media_type)


def test_a_punctuated_identity_is_served_when_encoded(client: TestClient) -> None:
    response = client.get(_clip_url(SKILJETECKEN, PUNCTUATED))

    assert response.status_code == 200
    assert response.content == _content("punctuated")
    assert response.headers["content-disposition"] == PUNCTUATED_DISPOSITION
    _assert_media_headers(response)


def test_a_literal_plus_is_a_space_and_answers_404(client: TestClient) -> None:
    response = client.get(_clip_url(SKILJETECKEN, PUNCTUATED, safe="+"))

    body = _assert_problem(response, 404, SKILJETECKEN)
    assert "a b & c #1.mp4" in str(body["detail"])


def test_the_chapter_folder_clip_and_the_ignored_clip_are_served(client: TestClient) -> None:
    chapter = client.get(_clip_url(TJORN, "Kvällen/s1710002.mp4"))
    ignored = client.get(_clip_url(TJORN, "s1710004.mp4"))

    assert chapter.status_code == 200
    assert chapter.content == _content("tjorn Kvällen/s1710002.mp4")
    assert ignored.status_code == 200


def test_a_symlinked_clip_serves_its_target(client: TestClient, tmp_path: Path) -> None:
    target = tmp_path / "samples" / "extern.mp4"
    response = client.get(_clip_url(GRILLNING, "länk.mp4"))

    info = target.stat()
    assert response.status_code == 200
    assert response.content == target.read_bytes()
    assert response.headers["etag"] == '"%x-%x"' % (info.st_size, info.st_mtime_ns)
    assert parsedate_to_datetime(response.headers["last-modified"]).timestamp() == int(
        info.st_mtime
    )


def test_a_zero_byte_clip_is_served_as_it_is(client: TestClient) -> None:
    whole = client.get(_clip_url(TRASIG, "trasig.mp4"))
    ranged = client.get(_clip_url(TRASIG, "trasig.mp4"), headers={"Range": "bytes=0-"})

    assert whole.status_code == 200
    assert whole.content == b""
    assert ranged.status_code == 416
    assert ranged.headers["content-range"] == "bytes */0"


@pytest.mark.parametrize(
    ("event", "clip"),
    [
        (SOMMARLOV, "borttagen.mp4"),  # MISSING
        (SOMMARLOV, "../2024-06-27 - Grillning med grannar/s1710001.mp4"),  # outside
        (TJORN, "Kvällen/../s1710001.mp4"),  # normalizing
        (GRILLNING, "original/x.mp4"),
        ("2024", "2024-06-27 - Grillning med grannar/s1710001.mp4"),  # the year folder
        (f"{GRILLNING}/original", "x.mp4"),
        ("2024/2024-12-24 - Finns inte", "s1710001.mp4"),  # an unknown event
    ],
)
def test_a_clip_that_is_not_listed_is_a_404_problem(
    client: TestClient, event: str, clip: str
) -> None:
    _assert_problem(client.get(_clip_url(event, clip)), 404, event)


def test_a_clip_that_vanishes_after_the_listing_is_a_404(
    client: TestClient, project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _vanish_after_listing(monkeypatch, project / GRILLNING, "s1710002.mp4")

    body = _assert_problem(client.get(_clip_url(GRILLNING, "s1710002.mp4")), 404, GRILLNING)
    assert "s1710002.mp4" in str(body["detail"])


def test_a_request_without_clip_is_a_422(client: TestClient) -> None:
    response = client.get(f"{_event_url(GRILLNING)}/media")

    assert response.status_code == 422
    _assert_no_caching_headers(response)


def test_an_unreadable_clip_is_a_502_without_a_kind(
    client: TestClient, project: Path, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    _skip_as_root()
    clip = project / GRILLNING / "s1710002.mp4"
    clip.chmod(0)
    try:
        with caplog.at_level(logging.WARNING, logger="auto_reel_ng.api.routes.media"):
            response = client.get(_clip_url(GRILLNING, "s1710002.mp4"))
    finally:
        clip.chmod(0o644)

    body = _assert_problem(response, 502, GRILLNING)
    assert body.get("failure") is None
    assert body.get("thumbnail_failure") is None
    assert "Permission denied" in str(body["detail"])
    assert str(tmp_path) not in str(body["detail"])
    assert any(
        record.levelno == logging.WARNING and "s1710002.mp4" in record.getMessage()
        for record in caplog.records
    )


def test_an_unlistable_event_folder_is_a_502_unreadable_disk(
    client: TestClient, project: Path
) -> None:
    _skip_as_root()
    event_dir = project / GRILLNING
    event_dir.chmod(0)
    try:
        response = client.get(_clip_url(GRILLNING, "s1710001.mp4"))
    finally:
        event_dir.chmod(0o755)

    body = _assert_problem(response, 502, GRILLNING)
    assert body["failure"] == EventFailure.UNREADABLE_DISK.value


def test_a_broken_reel_yaml_does_not_stop_a_clip_over_http(client: TestClient) -> None:
    response = client.get(_clip_url(TRASIG_YAML, "s1710001.mp4"))

    assert response.status_code == 200
    assert response.content == _content("broken yaml")


def test_an_unknown_layout_is_a_502_without_a_kind(
    settings: ApiSettings, movies: Dict[str, Path]
) -> None:
    broken = dataclasses.replace(settings, layout_name="no-such-layout")
    with TestClient(create_app(broken)) as client:
        clip = client.get(_clip_url(GRILLNING, "s1710001.mp4"))
        movie = client.get(_movie_url(KALAS))

    for response, event in ((clip, GRILLNING), (movie, KALAS)):
        body = _assert_problem(response, 502, event)
        assert body.get("failure") is None
        assert "no-such-layout" in str(body["detail"])


# --- the movie over HTTP ------------------------------------------------------------------


def test_the_movie_is_served(client: TestClient, movies: Dict[str, Path]) -> None:
    response = client.get(_movie_url(KALAS))

    assert response.status_code == 200
    assert response.content == movies[KALAS].read_bytes()
    _assert_media_headers(response)
    assert response.headers["content-disposition"] == (
        f"inline; filename*=utf-8''{quote(KALAS_MOVIE)}"
    )


def test_a_renamed_event_s_movie_carries_its_old_name(
    client: TestClient, movies: Dict[str, Path]
) -> None:
    response = client.get(_movie_url(GRILLNING))

    assert response.status_code == 200
    assert response.content == movies[GRILLNING].read_bytes()
    assert quote(GRILLNING_OLD_MOVIE) in response.headers["content-disposition"]


def test_an_event_without_a_render_record_has_no_movie(
    client: TestClient, settings: ApiSettings, movies: Dict[str, Path]
) -> None:
    expected = _expected_movie(settings, KALAS_LOWER)
    if not expected.exists():
        os.link(movies[KALAS], expected)

    for event in (KALAS_LOWER, SOMMARLOV):
        body = _assert_problem(client.get(_movie_url(event)), 404, event)
        assert body["detail"] == f"event {event!r} has no rendered movie"


def test_a_directory_at_the_movie_s_path_is_a_404(
    client: TestClient, movies: Dict[str, Path], tmp_path: Path
) -> None:
    movies[KALAS].rename(tmp_path / "aside.mp4")
    movies[KALAS].mkdir()

    _assert_problem(client.get(_movie_url(KALAS)), 404, KALAS)


def test_a_title_climbing_out_is_a_404_without_the_file_s_bytes(
    client: TestClient, utbrytning: Path
) -> None:
    response = client.get(_movie_url(UTBRYTNING))

    _assert_problem(response, 404, UTBRYTNING)
    assert utbrytning.read_bytes()[:64] not in response.content


def test_an_event_the_detail_cannot_read_is_a_502_with_its_kind(
    client: TestClient, movies: Dict[str, Path]
) -> None:
    omojligt = _assert_problem(client.get(_movie_url(OMOJLIGT)), 502, OMOJLIGT)
    detail = client.get(_event_url(OMOJLIGT)).json()  # 502 before the database is read
    trasig_yaml = _assert_problem(client.get(_movie_url(TRASIG_YAML)), 502, TRASIG_YAML)

    assert omojligt["failure"] == EventFailure.UNUSABLE_METADATA.value
    assert omojligt["detail"] == detail["detail"]
    assert trasig_yaml["failure"] == EventFailure.UNPARSEABLE_REEL_YAML.value


def test_a_movie_revalidates_with_a_304(client: TestClient, movies: Dict[str, Path]) -> None:
    etag = client.get(_movie_url(KALAS)).headers["etag"]

    for tag in (etag, f"W/{etag}", f'"other", {etag}'):
        response = client.get(
            _movie_url(KALAS), headers={"If-None-Match": tag, "Range": "bytes=0-"}
        )
        assert response.status_code == 304
        assert response.content == b""
        assert response.headers["etag"] == etag
        assert response.headers["cache-control"] == MEDIA_CACHE_CONTROL


# --- routing and auth ---------------------------------------------------------------------


def test_the_media_router_does_not_shadow_the_events_routes(client: TestClient) -> None:
    assert client.get(f"{_event_url(TJORN)}/reel").status_code == 200
    thumbnail = client.get(f"{_event_url(TJORN)}/thumbnail?clip=s1710001.mp4")
    assert thumbnail.status_code != 503  # its own route, never the detail's
    assert client.get(_event_url(TJORN)).status_code == 503  # the detail: the database
    assert client.get(_clip_url(TJORN, "s1710001.mp4")).status_code == 200


def test_every_range_request_passes_the_auth_hook(settings: ApiSettings) -> None:
    calls: List[str] = []

    def checker(request: Request) -> Optional[Response]:
        calls.append(request.headers.get("range", ""))
        if request.headers.get("x-test") != "1":
            return JSONResponse(status_code=401, content={"detail": "unauthorized"})
        return None

    url = _clip_url(GRILLNING, "s1710001.mp4")
    with TestClient(create_app(settings, auth_checker=checker)) as client:
        statuses = [
            client.get(url, headers={"X-Test": "1"}).status_code,
            client.get(url, headers={"X-Test": "1", "Range": "bytes=0-9"}).status_code,
            client.get(url, headers={"X-Test": "1", "Range": "bytes=10-19"}).status_code,
        ]
        rejected = client.get(url, headers={"Range": "bytes=0-9"})

    assert statuses == [200, 206, 206]
    assert calls == ["", "bytes=0-9", "bytes=10-19", "bytes=0-9"]
    assert rejected.status_code == 401
    assert GRILL_1[:10] not in rejected.content


def test_the_media_routes_answer_while_the_database_is_down(
    client: TestClient, movies: Dict[str, Path]
) -> None:
    assert client.get(_clip_url(GRILLNING, "s1710001.mp4")).status_code == 200
    assert client.get(_movie_url(KALAS)).status_code == 200
