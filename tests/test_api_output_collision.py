"""Tests for the enqueue's read model: the listed target and the output-collision read.

``events_read.enqueue_target`` is the lookup an enqueue starts from (api-jobs-create-validation
2.1): the id the events list shows, and that event's processable document.

``events_read.output_collision`` applies the batch commands' rule (D-9) over every
event of the served project: the layout walk's events — the events list's rows —
plus the named event itself, each keyed by its own id as ``auto-reel enqueue`` keys
its walk. No database: the read touches only the disk.
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path, PurePosixPath

import pytest

from auto_reel_ng.api import events_read
from auto_reel_ng.api.settings import ApiSettings, resolve_api_settings
from auto_reel_ng.cli import commands
from auto_reel_ng.event import DEFAULT_CLIP_ORDER
from auto_reel_ng.ingest import LayoutError, year_event_layout
from auto_reel_ng.reel import ReelDocument

#: Never connected to: the read under test runs no query.
UNUSED_DATABASE_URL = "postgresql+psycopg://nobody:nobody@127.0.0.1:1/nothing"

TODAY = date(2026, 9, 30)

#: The dev library's case-only twins (``scripts/make_dev_library.py``).
KALAS = "2024/2024-07-14 - Kalas"
KALAS_LOWER = "2024/2024-07-14 - kalas"

#: An in-project symlinked alias of the Kalas folder, and a real folder named like it.
FEST = "2024/2024-07-20 - Fest"
FEST_LOWER = "2024/2024-07-20 - fest"

#: A reel.yaml the loader cannot load: a ReelParseError each (once a bare ValueError).
IMPOSSIBLE_YAML_DATE = b"version: 0\nmetadata:\n  title: Kalas\n  date: 2024-02-30\n"
NOT_UTF_8 = b"version: 0\nmetadata:\n  title: Kalas \xff\n"


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")


def _event(root: Path, event_id: str, reel_yaml: str | bytes | None = None) -> Path:
    """An event folder with one clip, and ``reel_yaml`` as its document when given."""
    event_dir = root / event_id
    _touch(event_dir / "00400.mp4")
    if reel_yaml is not None:
        raw = reel_yaml.encode("utf-8") if isinstance(reel_yaml, str) else reel_yaml
        (event_dir / "reel.yaml").write_bytes(raw)
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
    event_dir = events_read.named_event_dir(settings, event_id)
    return events_read.output_collision(settings, event_dir, today=TODAY)


def _refusals(root: Path) -> dict[str, tuple[str, ...]]:
    """Every listed event the service refuses, with the claimants it names."""
    refusals = {}
    for ref in year_event_layout(root):
        event_id = ref.event_dir.relative_to(root).as_posix()
        collision = _collision(root, event_id)
        if collision is not None:
            refusals[event_id] = collision.claimed_by
    return refusals


def _cli_refused(root: Path) -> set[str]:
    """The events ``auto-reel enqueue <root>`` refuses for an output collision.

    Computed by the selection and the rule ``cmd_enqueue`` itself runs, so a test
    asserts the CLI's actual answer rather than a restatement of it.
    """
    refs = list(year_event_layout(root))
    documents, _failures = commands._checked_documents(  # pylint: disable=protected-access
        refs, TODAY, DEFAULT_CLIP_ORDER
    )
    refused = commands._output_collisions(  # pylint: disable=protected-access
        {event_dir: document.metadata for event_dir, document in documents.items()}
    )
    return {event_dir.relative_to(root).as_posix() for event_dir in refused}


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
        # Each of these would collide, if its reel.yaml could be read:
        ("2024/2024-07-14 - KALAS", ": ["),
        ("2024/2024-07-14 - KALAS", IMPOSSIBLE_YAML_DATE),
        ("2024/2024-07-14 - KALAS", NOT_UTF_8),
    ],
    ids=["unusable-metadata", "unparseable-reel-yaml", "impossible-yaml-date", "not-utf-8"],
)
def test_a_sibling_that_fails_on_its_own_claims_nothing(
    root: Path, sibling: str, reel_yaml: str | bytes | None
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


def test_a_symlinked_twin_outside_the_root_is_named_by_its_in_root_id(
    root: Path, tmp_path: Path
) -> None:
    _event(root, KALAS)
    elsewhere = _event(tmp_path, "elsewhere/kalas-footage")
    (root / KALAS_LOWER).symlink_to(elsewhere)  # its folder name is the link's

    collision = _collision(root, KALAS)

    assert collision is not None
    assert collision.claimed_by == (KALAS_LOWER,)


@pytest.mark.parametrize(
    ("real", "authored", "refusals"),
    [
        # The alias is dropped from the walk (layout-alias-dedupe), so it claims no path:
        # the real fest is not refused for it.
        ((KALAS, FEST_LOWER), False, {}),
        # Nothing else claims Kalas's path: only Kalas and its case-only twin collide.
        ((KALAS, KALAS_LOWER), False, {KALAS: (KALAS_LOWER,), KALAS_LOWER: (KALAS,)}),
        # The alias reads the folder's authored reel.yaml but is no row: Kalas claims
        # Kalas.mp4 alone.
        ((KALAS,), True, {}),
    ],
    ids=[
        "alias-beside-its-name-twin",
        "alias-of-a-colliding-folder",
        "alias-of-an-authored-folder",
    ],
)
def test_a_dropped_in_project_alias_is_a_claimant_of_nothing(
    root: Path,
    real: tuple[str, ...],
    authored: bool,
    refusals: dict[str, tuple[str, ...]],
) -> None:
    """A symlinked event folder is no row of the walk, so it claims no path."""
    for event_id in real:
        _event(root, event_id)
    if authored:
        (root / KALAS / "reel.yaml").write_text(
            "version: 0\nmetadata:\n  title: Kalas\n  date: 2024-07-14\n", encoding="utf-8"
        )
    (root / FEST).symlink_to(root / KALAS)

    assert _cli_refused(root) == set(refusals)  # the CLI's answer ...
    assert _refusals(root) == refusals  # ... is the service's, claimants included


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


# --------------------------------------------------------------------------- #
# The enqueue's target (api-jobs-create-validation 2.1)
# --------------------------------------------------------------------------- #

A_ID = "2024/2024-06-21 - A"
NO_DATE = "2024/NoDate"


def _target(root: Path, event_id: str) -> tuple[Path, ReelDocument]:
    return events_read.enqueue_target(_settings(root), event_id, today=TODAY)


def test_the_listed_id_gives_its_folder_and_a_document_with_resolved_metadata(root: Path) -> None:
    _event(root, A_ID)

    event_dir, document = _target(root, A_ID)

    assert event_dir == root / A_ID
    assert document.metadata.title == "A"
    assert document.metadata.date == date(2024, 6, 21)


@pytest.mark.parametrize(
    "event_id",
    [
        "2024/./2024-06-21 - A",
        "2024/2024-06-21 - A/",
        "2024/2024-06-21 - A/../2024-06-21 - A",
        "2024/2024-06-21 - A/original",
        "2024",
        "",
        "2024/missing/../2024-06-21 - A",
    ],
    ids=["dot", "trailing-slash", "dotdot", "original", "year-folder", "root", "missing-folder"],
)
def test_a_spelling_the_list_does_not_show_is_not_found(root: Path, event_id: str) -> None:
    _event(root, A_ID)
    (root / A_ID / "original").mkdir()

    with pytest.raises(events_read.EventNotFoundError):
        _target(root, event_id)


@pytest.mark.parametrize(
    ("event_id", "reel_yaml", "failure"),
    [
        (NO_DATE, None, "unusable_metadata"),
        (A_ID, "metadata: [unclosed", "unparseable_reel_yaml"),
        (A_ID, "version: 0\nmetadata:\n  date: 2999-01-01\n", "unusable_metadata"),
    ],
    ids=["no-date", "unparseable", "future-date"],
)
def test_an_event_it_cannot_process_is_a_read_error_with_the_lists_kind(
    root: Path, event_id: str, reel_yaml: str | None, failure: str
) -> None:
    _event(root, event_id, reel_yaml)

    with pytest.raises(events_read.EventReadError) as caught:
        _target(root, event_id)

    assert caught.value.failure is not None and caught.value.failure.value == failure
    assert caught.value.event_id == event_id


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
def test_an_event_folder_that_cannot_be_searched_is_unreadable_disk(root: Path) -> None:
    event_dir = _event(root, A_ID, _titled("Real"))
    event_dir.chmod(0o600)
    try:
        with pytest.raises(events_read.EventReadError) as caught:
            _target(root, A_ID)
    finally:
        event_dir.chmod(0o755)

    assert caught.value.failure is not None
    assert caught.value.failure.value == "unreadable_disk"


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
def test_a_year_folder_that_cannot_be_listed_is_the_walks_own_error(root: Path) -> None:
    _event(root, A_ID)
    (root / "2024").chmod(0o111)  # searchable (the id resolves) but not listable
    try:
        with pytest.raises(OSError):
            _target(root, A_ID)
    finally:
        (root / "2024").chmod(0o755)


def test_a_reelignored_event_and_one_outside_input_are_not_found(root: Path) -> None:
    _event(root, f"input/{A_ID}")
    _event(root, "input/2024/2024-06-22 - B")
    (root / "input/2024/2024-06-22 - B/.reelignore").write_bytes(b"")
    _event(root, KALAS)  # beside input/, not in it
    (root / "config.yaml").write_text("input: input\n", encoding="utf-8")

    assert _target(root, f"input/{A_ID}")[0] == root / "input" / A_ID
    for event_id in ("input/2024/2024-06-22 - B", KALAS):
        with pytest.raises(events_read.EventNotFoundError):
            _target(root, event_id)


def test_a_symbolic_link_to_an_event_resolves_under_its_own_id(root: Path) -> None:
    _event(root, KALAS)
    (root / FEST).symlink_to(root / KALAS)

    event_dir, document = _target(root, FEST)

    assert event_dir == root / FEST
    assert document.metadata.title == "Fest"  # its own folder name, not the target's
