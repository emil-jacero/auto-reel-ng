"""Tests for the enqueue's output-collision read (jobs-project-guards 3.2).

``events_read.output_collision`` applies the batch commands' rule (D-9) over every
event of the served project: the layout walk's events — the events list's rows —
plus the named event itself. No database: the read touches only the disk.
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path, PurePosixPath

import pytest

from auto_reel_ng.api import events_read
from auto_reel_ng.api.settings import ApiSettings, resolve_api_settings
from auto_reel_ng.ingest import LayoutError

#: Never connected to: the read under test runs no query.
UNUSED_DATABASE_URL = "postgresql+psycopg://nobody:nobody@127.0.0.1:1/nothing"

TODAY = date(2026, 9, 30)

#: The dev library's case-only twins (``scripts/make_dev_library.py``).
KALAS = "2024/2024-07-14 - Kalas"
KALAS_LOWER = "2024/2024-07-14 - kalas"


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")


def _event(root: Path, event_id: str, reel_yaml: str | None = None) -> Path:
    """An event folder with one clip, and ``reel_yaml`` as its document when given."""
    event_dir = root / event_id
    _touch(event_dir / "00400.mp4")
    if reel_yaml is not None:
        (event_dir / "reel.yaml").write_text(reel_yaml, encoding="utf-8")
    return event_dir


def _titled(title: str) -> str:
    """A document authoring only the title: the date still comes from the folder name."""
    return f"version: 0\nmetadata:\n  title: {title}\n"


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return tmp_path / "proj"


def _settings(root: Path) -> ApiSettings:
    return resolve_api_settings(root, env={"DATABASE_URL": UNUSED_DATABASE_URL})


def _collision(root: Path, event_id: str) -> events_read.OutputCollision | None:
    settings = _settings(root)
    event_dir = events_read.resolve_event_dir(settings, event_id)
    return events_read.output_collision(settings, event_dir, today=TODAY)


@pytest.mark.parametrize(
    ("named", "output_path", "claimed_by"),
    [
        (KALAS_LOWER, "2024/2024-07-14 - kalas.mp4", (KALAS,)),
        (KALAS, "2024/2024-07-14 - Kalas.mp4", (KALAS_LOWER,)),
    ],
    ids=["kalas", "Kalas"],
)
def test_a_case_only_twin_collides_from_either_side(
    root: Path, named: str, output_path: str, claimed_by: tuple[str, ...]
) -> None:
    """Authored titles differing only in case: paths compare case-insensitively."""
    _event(root, KALAS, _titled("Kalas"))
    _event(root, KALAS_LOWER, _titled("kalas"))

    collision = _collision(root, named)

    assert collision == events_read.OutputCollision(
        output_path=PurePosixPath(output_path), claimed_by=claimed_by
    )


def test_a_twin_named_by_its_folder_alone_claims_the_same_path(root: Path) -> None:
    """The dev library's shape: a folder title is title-cased, so both paths are equal."""
    _event(root, KALAS, _titled("Kalas"))
    _event(root, KALAS_LOWER)  # no reel.yaml: seeded from the folder name

    collision = _collision(root, KALAS_LOWER)

    assert collision is not None
    assert collision.output_path == PurePosixPath("2024/2024-07-14 - Kalas.mp4")
    assert collision.claimed_by == (KALAS,)


def test_a_normalization_only_twin_collides(root: Path) -> None:
    """Composed and decomposed spellings of one name are one path (NFC, as the CLI)."""
    composed = "2024/2024-08-20 - Tj\u00f6rn"
    decomposed = "2024/2024-08-20 - Tjo\u0308rn"
    _event(root, composed)
    _event(root, decomposed)

    collision = _collision(root, composed)

    assert collision is not None
    assert collision.claimed_by == (decomposed,)


def test_three_same_named_events_give_two_sorted_claimants(root: Path) -> None:
    for event_id in (KALAS, KALAS_LOWER, "2024/2024-07-14 - KALAS"):
        _event(root, event_id)

    collision = _collision(root, KALAS_LOWER)

    assert collision is not None
    assert collision.claimed_by == ("2024/2024-07-14 - KALAS", KALAS)


def test_another_date_is_no_collision(root: Path) -> None:
    _event(root, KALAS)
    _event(root, "2024/2024-07-15 - Kalas")

    assert _collision(root, KALAS) is None


@pytest.mark.parametrize(
    ("sibling", "reel_yaml"),
    [
        ("2024/2024-02-30 - Omöjligt datum", None),  # an impossible folder date
        ("2024/2024-07-14 - KALAS", ": ["),  # would collide, if its reel.yaml parsed
    ],
    ids=["unusable-metadata", "unparseable-reel-yaml"],
)
def test_a_sibling_that_fails_on_its_own_claims_nothing(
    root: Path, sibling: str, reel_yaml: str | None
) -> None:
    _event(root, KALAS)
    _event(root, sibling, reel_yaml)

    assert _collision(root, KALAS) is None


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
def test_a_sibling_that_cannot_be_listed_claims_nothing(root: Path) -> None:
    """The events list's per-event isolation: one unreadable folder is skipped, not fatal."""
    _event(root, KALAS)
    twin = _event(root, KALAS_LOWER)  # would collide, if it could be listed
    twin.chmod(0o000)
    try:
        collision = _collision(root, KALAS)
    finally:
        twin.chmod(0o755)

    assert collision is None


@pytest.mark.parametrize(
    ("named", "reel_yaml"),
    [
        ("2024/2024-02-30 - Omöjligt datum", None),
        (KALAS_LOWER, ": ["),
    ],
    ids=["unusable-metadata", "unparseable-reel-yaml"],
)
def test_a_named_event_that_fails_on_its_own_claims_nothing(
    root: Path, named: str, reel_yaml: str | None
) -> None:
    _event(root, KALAS)
    _event(root, named, reel_yaml)

    assert _collision(root, named) is None


def test_a_named_event_the_walk_does_not_reach_still_collides(root: Path) -> None:
    """``input`` narrows the walk; a folder outside it still claims its own path."""
    _event(root, f"input/{KALAS}")
    _event(root, KALAS_LOWER)  # outside input: the walk never lists it
    (root / "config.yaml").write_text("input: input\n", encoding="utf-8")

    collision = _collision(root, KALAS_LOWER)

    assert collision is not None
    assert collision.claimed_by == (f"input/{KALAS}",)


def test_a_symlinked_twin_outside_the_root_is_named_by_its_in_root_id(
    root: Path, tmp_path: Path
) -> None:
    _event(root, KALAS)
    elsewhere = _event(tmp_path, "elsewhere/kalas-footage")
    (root / KALAS_LOWER).symlink_to(elsewhere)  # its folder name is the link's

    collision = _collision(root, KALAS)

    assert collision is not None
    assert collision.claimed_by == (KALAS_LOWER,)


def test_two_rows_aliasing_one_folder_keep_both_claims(root: Path) -> None:
    """An in-project alias walked after its folder must not replace the folder's claim."""
    _event(root, KALAS)
    _event(root, KALAS_LOWER)
    fest = root / "2024" / "2024-07-20 - Fest"  # listed as its own row; claims its own path
    fest.symlink_to(root / KALAS)

    assert _collision(root, KALAS_LOWER) == events_read.OutputCollision(
        output_path=PurePosixPath("2024/2024-07-14 - Kalas.mp4"), claimed_by=(KALAS,)
    )
    # A walked alias of the named event is the named event itself: never its own twin.
    kalas = _collision(root, KALAS)
    assert kalas is not None
    assert kalas.claimed_by == (KALAS_LOWER,)


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
def test_a_walk_that_fails_raises(root: Path) -> None:
    """The check could not run: the caller must not enqueue, so the error propagates."""
    _event(root, KALAS)
    year_dir = root / "2023"
    _event(root, "2023/2023-06-23 - Midsommar - Dalarna")
    year_dir.chmod(0o000)
    try:
        with pytest.raises(OSError):
            _collision(root, KALAS)
    finally:
        year_dir.chmod(0o755)


def test_an_unknown_layout_raises(root: Path) -> None:
    _event(root, KALAS)
    (root / "config.yaml").write_text("layout: nope\n", encoding="utf-8")

    with pytest.raises(LayoutError):
        _collision(root, KALAS)
