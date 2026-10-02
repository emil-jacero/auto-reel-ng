"""Tests for the layout-aware output-collision rule, ``render.claims.output_collision``.

One rule for the CLI, the API and the worker (D-9): which other events of the project
claim the named event's output path. Real ``tmp_path`` project trees, ``year-event``
layout; no database.
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path, PurePosixPath

import pytest

from auto_reel_ng.api import events_read
from auto_reel_ng.api.settings import resolve_api_settings
from auto_reel_ng.event import DEFAULT_CLIP_ORDER
from auto_reel_ng.ingest import EventRef, LayoutError, get_layout
from auto_reel_ng.render import claims as claims_module
from auto_reel_ng.render.claims import OutputCollision, output_collision, output_collision_message

TODAY = date(2026, 9, 30)
LAYOUT = "year-event"

MIDSOMMAR = "2024/2024-06-21 - Midsommar"
MIDSOMMAR_2 = "2024/2024-06-21 - Midsommar 2"
MIDSOMMAR_LOWER = "2024/2024-06-21 - midsommar"
SHARED_PATH = PurePosixPath("2024/2024-06-21 - Midsommar.mp4")


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return tmp_path / "proj"


def _event(root: Path, event_id: str, reel_yaml: str | bytes | None = None) -> Path:
    event_dir = root / event_id
    event_dir.mkdir(parents=True, exist_ok=True)
    (event_dir / "00400.mp4").write_bytes(b"")
    if reel_yaml is not None:
        raw = reel_yaml.encode("utf-8") if isinstance(reel_yaml, str) else reel_yaml
        (event_dir / "reel.yaml").write_bytes(raw)
    return event_dir


def _titled(title: str) -> str:
    return f"version: 0\nmetadata:\n  title: {title}\n"


def _collision(root: Path, event_dir: Path, layout: str = LAYOUT) -> OutputCollision | None:
    return output_collision(
        event_dir, walk_root=root, layout=layout, order=DEFAULT_CLIP_ORDER, today=TODAY
    )


def test_same_date_and_title_collide_from_either_side(root: Path) -> None:
    first = _event(root, MIDSOMMAR)  # named by its folder
    second = _event(root, MIDSOMMAR_2, _titled("Midsommar"))  # named by its reel.yaml

    assert _collision(root, first) == OutputCollision(SHARED_PATH, (second,))
    assert _collision(root, second) == OutputCollision(SHARED_PATH, (first,))


def test_an_event_edited_into_a_collision_after_the_fact_collides(root: Path) -> None:
    """The worker scenario: distinct at enqueue, equal once the title is edited."""
    first = _event(root, MIDSOMMAR)
    second = _event(root, MIDSOMMAR_2)
    assert _collision(root, first) is None
    assert _collision(root, second) is None

    (second / "reel.yaml").write_text(_titled("Midsommar"), encoding="utf-8")

    assert _collision(root, first) == OutputCollision(SHARED_PATH, (second,))
    assert _collision(root, second) == OutputCollision(SHARED_PATH, (first,))


def test_a_case_only_difference_collides(root: Path) -> None:
    first = _event(root, MIDSOMMAR, _titled("Midsommar"))
    second = _event(root, MIDSOMMAR_LOWER, _titled("midsommar"))

    collision = _collision(root, first)
    assert collision is not None
    assert collision.claimed_by == (second,)
    reverse = _collision(root, second)
    assert reverse is not None
    assert reverse.output_path == PurePosixPath("2024/2024-06-21 - midsommar.mp4")
    assert reverse.claimed_by == (first,)


def test_a_normalization_only_difference_collides(root: Path) -> None:
    composed = _event(root, "2024/2024-08-20 - Tjörn")
    decomposed = _event(root, "2024/2024-08-20 - Tjörn")

    collision = _collision(root, composed)

    assert collision is not None
    assert collision.claimed_by == (decomposed,)


@pytest.mark.parametrize(
    "other", ["2024/2024-06-22 - Midsommar", "2023/2023-06-21 - Midsommar"], ids=["date", "year"]
)
def test_another_date_or_year_is_no_collision(root: Path, other: str) -> None:
    first = _event(root, MIDSOMMAR)
    _event(root, other)

    assert _collision(root, first) is None


def test_a_three_way_collision_lists_both_others_sorted(root: Path) -> None:
    named = _event(root, MIDSOMMAR_LOWER)
    zed = _event(root, "2024/2024-06-21 - ZZZ", _titled("Midsommar"))
    aaa = _event(root, "2024/2024-06-21 - AAA", _titled("Midsommar"))

    collision = _collision(root, named)

    assert collision is not None
    assert collision.claimed_by == (aaa, zed)  # sorted by path


def test_the_others_are_sorted_whatever_order_the_layout_walks(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    named = _event(root, MIDSOMMAR_LOWER)
    zed = _event(root, "2024/2024-06-21 - ZZZ", _titled("Midsommar"))
    aaa = _event(root, "2024/2024-06-21 - AAA", _titled("Midsommar"))
    forward = get_layout(LAYOUT)

    def reversed_walk(walk_root: Path) -> list[EventRef]:
        return list(reversed(list(forward(walk_root))))

    monkeypatch.setattr(claims_module, "get_layout", lambda _name: reversed_walk)

    collision = _collision(root, named)

    assert collision is not None
    assert collision.claimed_by == (aaa, zed)


def test_a_symlinked_alias_is_a_claimant_of_its_own(root: Path) -> None:
    """Aliases are never resolved: the alias claims its own folder-name path."""
    original = _event(root, MIDSOMMAR, _titled("Midsommar"))
    alias = root / "2024/2024-06-21 - Midsommar copy"
    alias.symlink_to(original, target_is_directory=True)
    # The alias carries the original's reel.yaml, so both claim the same output path.

    collision = _collision(root, original)

    assert collision == OutputCollision(SHARED_PATH, (alias,))


def test_the_named_event_spelled_from_another_base_is_not_its_own_claimant(
    root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    only = _event(root, MIDSOMMAR)
    monkeypatch.chdir(tmp_path)
    relative_root = Path("proj")
    spellings = [
        only,  # absolute event_dir, relative walk root
        tmp_path / "proj" / "2024" / ".." / "2024" / "2024-06-21 - Midsommar",
    ]

    for spelling in spellings:
        assert (
            output_collision(
                spelling,
                walk_root=relative_root,
                layout=LAYOUT,
                order=DEFAULT_CLIP_ORDER,
                today=TODAY,
            )
            is None
        ), spelling
    assert _collision(root, only) is None


def test_a_named_event_the_layout_does_not_walk_still_claims(root: Path) -> None:
    """``year-event`` walks ``<year>/<event>``; a folder one level up is not reached."""
    walked = _event(root, MIDSOMMAR)
    outside = _event(root, "2024-06-21 - Midsommar")  # directly under the root

    assert outside not in [ref.event_dir for ref in _walk(root)]
    assert _collision(root, outside) == OutputCollision(SHARED_PATH, (walked,))


def _walk(root: Path) -> list[EventRef]:
    return list(get_layout(LAYOUT)(root))


@pytest.mark.parametrize(
    ("sibling", "reel_yaml"),
    [
        ("2024/2024-06-21 - KALAS", ": ["),  # unparseable
        ("2024/2024-06-21 - Midsommar 3", "version: 0\nmetadata:\n  date: 2024-02-30\n"),
        ("2024/2024-02-30 - Omöjligt", None),  # no real date: fails on its own
    ],
    ids=["unparseable", "impossible-date", "no-date"],
)
def test_a_walked_event_that_fails_claims_nothing(
    root: Path, sibling: str, reel_yaml: str | None
) -> None:
    first = _event(root, MIDSOMMAR)
    twin = _event(root, MIDSOMMAR_LOWER)
    _event(root, sibling, reel_yaml)

    assert _collision(root, first) == OutputCollision(SHARED_PATH, (twin,))


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
def test_an_unlistable_sibling_claims_nothing_and_does_not_stop_the_check(root: Path) -> None:
    first = _event(root, MIDSOMMAR)
    twin = _event(root, MIDSOMMAR_LOWER)
    locked = _event(root, "2024/2024-06-21 - Fest")
    locked.chmod(0o000)
    try:
        collision = _collision(root, first)
    finally:
        locked.chmod(0o755)

    assert collision == OutputCollision(SHARED_PATH, (twin,))


def test_the_named_event_failing_claims_nothing_and_the_layout_is_not_walked(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    undated = _event(root, "2024/Blandat")

    def walk_must_not_run(_name: str) -> object:
        raise AssertionError("the layout was walked")

    monkeypatch.setattr(claims_module, "get_layout", walk_must_not_run)

    assert _collision(root, undated) is None


def test_an_unknown_layout_propagates(root: Path) -> None:
    first = _event(root, MIDSOMMAR)

    with pytest.raises(LayoutError):
        _collision(root, first, layout="no-such-layout")


def test_a_walk_root_that_cannot_be_listed_propagates(root: Path) -> None:
    first = _event(root, MIDSOMMAR)

    with pytest.raises(OSError):
        _collision(root / "gone", first)


def test_the_refusal_sentence_is_the_one_the_cli_and_the_api_print() -> None:
    assert (
        output_collision_message(PurePosixPath("2024/x.mp4"), ["a", "b"])
        == "output path 2024/x.mp4 is also claimed by a, b; "
        "set a distinct title or location in reel.yaml"
    )


# --------------------------------------------------------------------------- #
# Cross-check against the API's current private implementation (until it delegates)
# --------------------------------------------------------------------------- #


def test_the_engine_answer_equals_the_apis_for_every_event(root: Path) -> None:
    _event(root, MIDSOMMAR)
    _event(root, MIDSOMMAR_LOWER)
    _event(root, "2024/2024-08-20 - Tjörn")
    _event(root, "2024/2024-08-20 - Tjörn")
    _event(root, "2024/2024-09-01 - Ensam")
    _event(root, "2024/2024-09-02 - Trasig", ": [")
    locked = _event(root, "2024/2024-06-21 - Fest")
    if os.geteuid() != 0:
        locked.chmod(0o000)
    settings = resolve_api_settings(
        root, env={"DATABASE_URL": "postgresql+psycopg://nobody:nobody@127.0.0.1:1/nothing"}
    )
    try:
        for ref in _walk(root):
            event_dir = ref.event_dir
            api = events_read.output_collision(settings, event_dir, today=TODAY)
            engine = _collision(root, event_dir)
            if api is None:
                assert engine is None, event_dir
                continue
            assert engine is not None, event_dir
            assert engine.output_path == api.output_path
            assert tuple(events_read.event_id_for(settings, p) for p in engine.claimed_by) == (
                api.claimed_by
            )
    finally:
        locked.chmod(0o755)
