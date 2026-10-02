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
from auto_reel_ng.errors import ClaimedMovieError, EngineError
from auto_reel_ng.event import DEFAULT_CLIP_ORDER
from auto_reel_ng.ingest import EventRef, LayoutError, get_layout
from auto_reel_ng.reel.document import Metadata, ReelDocument
from auto_reel_ng.render import claims as claims_module
from auto_reel_ng.render.claims import (
    ClaimedMovie,
    OutputCollision,
    claimed_movie,
    claimed_movie_message,
    output_collision,
    output_collision_message,
)
from auto_reel_ng.staleness.fingerprint import compute_fingerprint, engine_identity
from auto_reel_ng.staleness.manifest import manifest_path, write_manifest

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


def test_a_walked_symlinked_alias_is_not_a_claimant(root: Path) -> None:
    """The layout drops an alias of an event directory, so it claims nothing of its own."""
    original = _event(root, MIDSOMMAR, _titled("Midsommar"))
    alias = root / "2024/2024-06-21 - Midsommar copy"
    alias.symlink_to(original, target_is_directory=True)

    assert alias not in [ref.event_dir for ref in _walk(root)]
    assert _collision(root, original) is None


def test_a_named_symlinked_alias_still_collides_with_its_target(root: Path) -> None:
    """A caller that names the alias itself is not walked past it: it claims its own path."""
    original = _event(root, MIDSOMMAR, _titled("Midsommar"))
    alias = root / "2024/2024-06-21 - Midsommar copy"
    alias.symlink_to(original, target_is_directory=True)

    collision = _collision(root, alias)

    assert collision is not None
    assert collision.claimed_by == (original,)


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


# --- claimed_movie: a recorded, no-longer-current path (render-refuses-claimed-movie) ---


OLD_NAME = "2024-06-27 - Grillning med grannar.mp4"


def _record(event_dir: Path, output: str) -> None:
    """Write a render manifest for ``event_dir`` that records ``output`` as its movie."""
    fingerprint = compute_fingerprint(
        ReelDocument(metadata=Metadata(title="x")),
        event_dir=event_dir,
        look_defaults={},
        ffmpeg_version=(7, 1),
    )
    write_manifest(event_dir, fingerprint, output=output, engine_identity=engine_identity((7, 1)))


def _movie(tmp_path: Path, name: str = OLD_NAME) -> Path:
    """An existing movie at ``<out>/<year>/<name>``."""
    movie = tmp_path / "out" / name[:4] / name
    movie.parent.mkdir(parents=True, exist_ok=True)
    movie.write_bytes(b"movie")
    return movie


def _claim(event_dir: Path, movie: Path, root: Path) -> ClaimedMovie | None:
    return claimed_movie(event_dir, movie, events=[ref.event_dir for ref in _walk(root)])


def test_a_file_another_event_records_is_claimed(root: Path, tmp_path: Path) -> None:
    renamed = _event(root, "2024/2024-06-27 - Grillkvall")
    taker = _event(root, "2024/2024-06-27 - Grillning")
    _record(renamed, OLD_NAME)
    movie = _movie(tmp_path)

    assert _claim(taker, movie, root) == ClaimedMovie(movie, (renamed,))


def test_every_claimant_is_listed_sorted_by_path(root: Path, tmp_path: Path) -> None:
    taker = _event(root, "2024/2024-06-27 - C")
    second = _event(root, "2024/2024-06-27 - B")
    first = _event(root, "2024/2024-06-27 - A")
    _record(second, OLD_NAME)
    _record(first, OLD_NAME)
    movie = _movie(tmp_path)

    found = _claim(taker, movie, root)

    assert found is not None and found.recorded_by == (first, second)


def test_nothing_is_claimed_when_the_file_does_not_exist(root: Path, tmp_path: Path) -> None:
    renamed = _event(root, "2024/2024-06-27 - Grillkvall")
    taker = _event(root, "2024/2024-06-27 - Grillning")
    _record(renamed, OLD_NAME)

    assert _claim(taker, tmp_path / "out" / "2024" / OLD_NAME, root) is None


def test_the_event_itself_is_never_its_own_claimant(root: Path, tmp_path: Path) -> None:
    own = _event(root, "2024/2024-06-27 - Grillning")
    _record(own, OLD_NAME)

    assert _claim(own, _movie(tmp_path), root) is None
    # lexically the same directory spelled from another base
    other_spelling = Path(os.path.relpath(own, Path.cwd()))
    assert claimed_movie(other_spelling, _movie(tmp_path), events=[own]) is None


def test_the_owner_is_not_refused_while_another_manifest_also_records_the_file(
    root: Path, tmp_path: Path
) -> None:
    # a forced takeover: `taker` owns the movie, `renamed` still records it too
    renamed = _event(root, "2024/2024-06-27 - Grillkvall")
    taker = _event(root, "2024/2024-06-27 - Grillning")
    _record(renamed, OLD_NAME)
    _record(taker, OLD_NAME)
    movie = _movie(tmp_path)

    assert _claim(taker, movie, root) is None
    # each of them records the file, so neither is refused on the other's account
    assert _claim(renamed, movie, root) is None


def test_a_file_nobody_records_is_not_claimed(root: Path, tmp_path: Path) -> None:
    renamed = _event(root, "2024/2024-06-27 - Grillkvall")
    taker = _event(root, "2024/2024-06-27 - Grillning")
    _record(renamed, "2024-06-27 - Something else.mp4")
    bare = _event(root, "2024/2024-06-27 - No manifest")

    assert bare.is_dir()
    assert _claim(taker, _movie(tmp_path), root) is None


def test_the_claim_ends_once_the_renamed_event_records_its_new_name(
    root: Path, tmp_path: Path
) -> None:
    renamed = _event(root, "2024/2024-06-27 - Grillkvall")
    taker = _event(root, "2024/2024-06-27 - Grillning")
    _record(renamed, OLD_NAME)
    movie = _movie(tmp_path)
    assert _claim(taker, movie, root) is not None

    _record(renamed, "2024-06-27 - Grillkvall.mp4")  # it re-rendered under its new name

    assert _claim(taker, movie, root) is None


def test_a_corrupt_manifest_claims_nothing(root: Path, tmp_path: Path) -> None:
    renamed = _event(root, "2024/2024-06-27 - Grillkvall")
    taker = _event(root, "2024/2024-06-27 - Grillning")
    _record(renamed, OLD_NAME)
    manifest_path(renamed).write_text("{not json", encoding="utf-8")

    assert _claim(taker, _movie(tmp_path), root) is None


@pytest.mark.parametrize("recorded", ["..", ".", "", "2024/" + OLD_NAME])
def test_a_recorded_value_that_is_not_a_file_name_claims_nothing(
    root: Path, tmp_path: Path, recorded: str
) -> None:
    renamed = _event(root, "2024/2024-06-27 - Grillkvall")
    taker = _event(root, "2024/2024-06-27 - Grillning")
    _record(renamed, recorded)

    assert _claim(taker, _movie(tmp_path), root) is None


def test_a_claimant_whose_reel_yaml_does_not_parse_still_claims(root: Path, tmp_path: Path) -> None:
    renamed = _event(root, "2024/2024-06-27 - Grillkvall", "version: 0\nmetadata: [unclosed\n")
    taker = _event(root, "2024/2024-06-27 - Grillning")
    _record(renamed, OLD_NAME)

    found = _claim(taker, _movie(tmp_path), root)

    assert found is not None and found.recorded_by == (renamed,)


def test_a_case_different_name_is_a_claim(root: Path, tmp_path: Path) -> None:
    renamed = _event(root, "2024/2024-06-27 - Grillkvall")
    taker = _event(root, "2024/2024-06-27 - Grillning")
    _record(renamed, OLD_NAME.lower())

    assert _claim(taker, _movie(tmp_path), root) is not None


def test_the_message_names_the_file_every_claimant_and_the_way_past() -> None:
    message = claimed_movie_message(PurePosixPath("2024") / OLD_NAME, ["Grillkvall", "proj/B"])

    assert f"2024/{OLD_NAME}" in message
    assert "Grillkvall, proj/B" in message
    assert "force" in message


def test_the_error_is_a_typed_engine_error() -> None:
    assert issubclass(ClaimedMovieError, EngineError)
