"""The dev-library builder rewrites ``reel.yaml`` in the engine's own block style.

``scripts/make_dev_library.py`` is not part of the package, so it is loaded from its file
(importing it touches neither the database nor ffmpeg). Its two round-trip edits must leave an
engine-written file engine-styled, so the first real engine write changes only edited lines.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

from auto_reel_ng.reel.parser import loads_document
from auto_reel_ng.reel.writer import dumps_document

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "make_dev_library.py"

ENGINE_REEL = """\
version: 0
metadata:
  title: Grillning   # event title
  date: 2024-06-27
chapters:
  - name: ""
    clips:
      - a.mp4
  - name: Kvällen
    clips:
      - b.mp4
"""


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("make_dev_library", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(name="script")
def _script() -> ModuleType:
    return _load()


@pytest.fixture(name="reel")
def _reel(tmp_path: Path) -> Path:
    path = tmp_path / "reel.yaml"
    path.write_text(ENGINE_REEL, encoding="utf-8")
    assert dumps_document(loads_document(ENGINE_REEL)) == ENGINE_REEL  # the fixture is canonical
    return path


def _lines(text: str) -> list[str]:
    return text.splitlines()


def test_edit_title_changes_only_the_title_line(script: ModuleType, reel: Path) -> None:
    script._edit_title(reel, "Grillning med grannar")

    out = reel.read_text(encoding="utf-8")
    assert "chapters:\n- name" not in out  # ruamel's flush default
    before, after = _lines(ENGINE_REEL), _lines(out)
    assert len(before) == len(after)
    assert [i for i, (a, b) in enumerate(zip(before, after)) if a != b] == [2]
    assert after[2].startswith("  title: Grillning med grannar")
    assert "# event title" in after[2]  # the comment is kept
    assert dumps_document(loads_document(out)) == out


def test_ignore_adds_exactly_an_ignore_list(script: ModuleType, reel: Path) -> None:
    script._ignore(reel, "x.mp4")

    out = reel.read_text(encoding="utf-8")
    assert "ignore:\n- x.mp4" not in out
    assert out == ENGINE_REEL + "ignore:\n  - x.mp4\n"
    assert loads_document(out).ignore == ("x.mp4",)
    assert dumps_document(loads_document(out)) == out


def test_the_dev_library_builder_never_writes_decorators(script: ModuleType) -> None:
    """title-cards-default-on: the sample library renders cards, so the script opts nobody out."""
    del script
    assert "decorators" not in SCRIPT.read_text(encoding="utf-8")
