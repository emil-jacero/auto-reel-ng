"""Pure scans for lone surrogates and non-string mapping keys (reel/values.py)."""

from __future__ import annotations

from datetime import date

import pytest
from ruamel.yaml import YAML

from auto_reel_ng.reel.values import NonStrKey, find_lone_surrogate, find_non_str_key

LONE = "x\ud800"


def test_a_clean_tree_has_neither_problem() -> None:
    tree = {"a": ["b", {"c": "d", "e": 1.5}], "f": None, "g": "Fest \U0001f386 Kräftskiva"}

    assert find_lone_surrogate(tree) is None
    assert find_non_str_key(tree) is None


@pytest.mark.parametrize(
    ("tree", "path"),
    [
        ({"title": LONE}, "title"),
        ({"look": {"font": LONE}}, "look.font"),
        ({"chapters": [{"name": "", "clips": ["ok.mp4", LONE]}]}, "chapters[0].clips[1]"),
        ({"look": {LONE: 1}}, "look[" + repr(LONE) + "]"),
        ({"clips": {"a.mp4": {"title": LONE}}}, "clips['a.mp4'].title"),
        ([LONE], "[0]"),
        (LONE, ""),
    ],
)
def test_a_lone_surrogate_is_found_with_its_path(tree: object, path: str) -> None:
    assert find_lone_surrogate(tree) == path


def test_the_path_never_holds_the_raw_surrogate() -> None:
    path = find_lone_surrogate({"look": {LONE: 1}})

    assert path is not None
    path.encode("utf-8")


def test_the_root_prefixes_every_path() -> None:
    assert find_lone_surrogate({"font": LONE}, root="look") == "look.font"
    assert find_non_str_key({1: "a"}, root="look") == NonStrKey("look", 1, "integer")


@pytest.mark.parametrize(
    ("tree", "path", "key", "kind"),
    [
        ({1: "a", "b": "c"}, "look", 1, "integer"),
        ({date(2024, 1, 1): "x"}, "look", date(2024, 1, 1), "date"),
        ({"layers": [{"ok": 1}, {2.5: "x"}]}, "look.layers[1]", 2.5, "number"),
        ({"a": {"b": {True: 1}}}, "look.a.b", True, "boolean"),
        ({None: 1}, "look", None, "null"),
    ],
)
def test_a_non_string_key_is_found_with_the_path_of_its_mapping(
    tree: object, path: str, key: object, kind: str
) -> None:
    assert find_non_str_key(tree, root="look") == NonStrKey(path, key, kind)


def test_a_character_beyond_the_bmp_is_not_a_surrogate() -> None:
    assert find_lone_surrogate({"t": "Fest \U0001f386"}) is None


def test_ruamel_round_trip_containers_are_walked() -> None:
    yaml = YAML()
    tree = yaml.load('look:\n  layers:\n    - 1: x\n  font: "a\\ud800"\n')

    assert find_non_str_key(tree["look"], root="look") == NonStrKey("look.layers[0]", 1, "integer")
    assert find_lone_surrogate(tree) == "look.font"


def test_a_very_deep_structure_does_not_recurse() -> None:
    tree: object = {"leaf": LONE}
    for _ in range(5000):
        tree = {"n": [tree]}

    path = find_lone_surrogate(tree)

    assert path is not None and path.endswith(".leaf")
    assert find_non_str_key(tree) is None


def test_a_self_referencing_structure_terminates() -> None:
    loop: dict = {"a": 1}
    loop["self"] = [loop]

    assert find_lone_surrogate(loop) is None
    assert find_non_str_key(loop) is None


def test_a_container_aliased_many_times_is_visited_once() -> None:
    from auto_reel_ng.reel import values

    shared = {"k": "v"}
    tree = {"a": shared, "b": shared, "c": [shared, shared]}

    visited = [node for node, _ in values._walk(tree, None) if node is shared]

    assert len(visited) == 1
