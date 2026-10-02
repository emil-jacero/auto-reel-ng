"""Tests for the engine's claim-selection rule, ``event.claims.checked_claim``.

An event claims an output path only when it loads and is processable; any failure to
load it is a reason, never an exception and never a claim (headless-cli, "Batch
commands refuse colliding output paths"). Real ``tmp_path`` event folders; no database.
"""

from __future__ import annotations

import ast
import os
from datetime import date, timedelta
from pathlib import Path

import pytest

from auto_reel_ng.event import DEFAULT_CLIP_ORDER
from auto_reel_ng.event import claims as claims_module
from auto_reel_ng.event.claims import checked_claim

TODAY = date(2026, 9, 30)


def _event(root: Path, name: str, reel_yaml: str | bytes | None = None) -> Path:
    event_dir = root / name
    event_dir.mkdir(parents=True)
    (event_dir / "00400.mp4").write_bytes(b"")
    if reel_yaml is not None:
        raw = reel_yaml.encode("utf-8") if isinstance(reel_yaml, str) else reel_yaml
        (event_dir / "reel.yaml").write_bytes(raw)
    return event_dir


def _claim(event_dir: Path) -> tuple:
    return checked_claim(event_dir, order=DEFAULT_CLIP_ORDER, today=TODAY)


def test_a_folder_named_event_claims_and_nothing_is_written(tmp_path: Path) -> None:
    event_dir = _event(tmp_path, "2024-06-21 - Midsommar")

    document, reason = _claim(event_dir)

    assert reason is None
    assert document is not None
    assert document.metadata.title == "Midsommar"
    assert document.metadata.date == date(2024, 6, 21)
    assert not (event_dir / "reel.yaml").exists()


def test_reel_yaml_metadata_overrides_the_folder_name(tmp_path: Path) -> None:
    event_dir = _event(
        tmp_path, "2024-06-21 - Midsommar", "version: 0\nmetadata:\n  title: Majstång\n"
    )

    document, reason = _claim(event_dir)

    assert reason is None
    assert document is not None
    assert document.metadata.title == "Majstång"


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Blandat", "no date: folder name has no date"),
        ("2004 - Yngve berättar", "folder name has a year only"),
        ("2024-04-31 - Golf", "not a real date"),
        ((TODAY + timedelta(days=3)).isoformat() + " - Framtid", "in the future"),
    ],
    ids=["no-date", "year-only", "impossible-date", "future"],
)
def test_a_processable_rule_failure_is_the_event_metadata_reason(
    tmp_path: Path, name: str, expected: str
) -> None:
    event_dir = _event(tmp_path, name)

    document, reason = _claim(event_dir)

    assert document is None
    assert reason is not None
    assert expected in reason
    assert not reason.startswith(name)  # the caller prefixes the event name itself


@pytest.mark.parametrize(
    "reel_yaml",
    [": [", "version: 0\nmetadata:\n  title: Kalas\n  date: 2024-02-30\n", b"title: K\xff\n"],
    ids=["unparseable", "impossible-yaml-date", "not-utf-8"],
)
def test_an_unreadable_reel_yaml_claims_nothing(tmp_path: Path, reel_yaml: str | bytes) -> None:
    event_dir = _event(tmp_path, "2024-07-14 - Kalas", reel_yaml)

    document, reason = _claim(event_dir)

    assert document is None
    assert reason


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
def test_a_folder_that_cannot_be_listed_claims_nothing(tmp_path: Path) -> None:
    """The ``chmod 000`` sibling: a reason carrying the OS text, not a PermissionError."""
    event_dir = _event(tmp_path, "2024-07-14 - Kalas")
    event_dir.chmod(0o000)
    try:
        document, reason = _claim(event_dir)
    finally:
        event_dir.chmod(0o755)

    assert document is None
    assert reason is not None
    assert reason.startswith("cannot read the event: ")
    assert "Permission denied" in reason


def test_a_value_error_from_the_loader_claims_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    event_dir = _event(tmp_path, "2024-07-14 - Kalas")

    def boom(*_args: object, **_kwargs: object) -> tuple:
        raise ValueError("odd")

    monkeypatch.setattr(claims_module, "load_event_document", boom)

    assert _claim(event_dir) == (None, "cannot read the event: odd")


def test_any_other_exception_is_a_bug_and_propagates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    event_dir = _event(tmp_path, "2024-07-14 - Kalas")

    def boom(*_args: object, **_kwargs: object) -> tuple:
        raise RuntimeError("bug")

    monkeypatch.setattr(claims_module, "load_event_document", boom)

    with pytest.raises(RuntimeError):
        _claim(event_dir)


def test_the_claim_rule_imports_nothing_above_the_event_layer() -> None:
    """Layering (Principle VI): ``event/`` sits below ``ingest``-aware and ``render/`` code.

    A runtime check cannot see this: importing any ``auto_reel_ng`` module runs the package
    root, which imports the CLI and so everything. The module's own imports are what count.
    """
    tree = ast.parse(Path(claims_module.__file__).read_text(encoding="utf-8"))
    parents = {
        (node.module or "").split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.level == 2
    }
    assert parents == {"errors", "reel"}
    assert not [n for n in ast.walk(tree) if isinstance(n, ast.Import)]
