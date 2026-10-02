"""Tests for ``auto-reel prune-renamed``: superseded movies, dry run first, never a claimed file."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Callable

import pytest

from auto_reel_ng.cli.main import main
from auto_reel_ng.config import default_output_dir
from auto_reel_ng.reel.document import Metadata, ReelDocument
from auto_reel_ng.staleness.fingerprint import compute_fingerprint
from auto_reel_ng.staleness.manifest import manifest_path, read_manifest, write_manifest

OLD = "2024-06-21 - Old Party.mp4"
NEW = "2024-06-21 - New Party.mp4"
EVENT = "2024-06-21 - New Party"


def _touch(path: Path, data: bytes = b"") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _event(root: Path, name: str, year: str = "2024") -> Path:
    event_dir = root / year / name
    _touch(event_dir / "00400.mp4")
    return event_dir


def _record(event_dir: Path, *names: str) -> None:
    """Write one manifest per name in order, as consecutive renders under those names would."""
    event_dir.mkdir(parents=True, exist_ok=True)
    fingerprint = compute_fingerprint(
        ReelDocument(metadata=Metadata(title="x")),
        event_dir=event_dir,
        look_defaults={},
        ffmpeg_version=(7, 1),
    )
    for name in names:
        write_manifest(event_dir, fingerprint, output=name, engine_identity="x")


def _movie(output_dir: Path, name: str, data: bytes = b"movie") -> Path:
    year = name[:4] if name[:4].isdigit() else ""
    return _touch(output_dir / year / name if year else output_dir / name, data)


def _renamed(root: Path, old: str = OLD, new: str = NEW, event: str = EVENT) -> Path:
    """An event rendered as ``old``, retitled and rendered as ``new``; both movies on disk."""
    event_dir = _event(root, event)
    _record(event_dir, old, new)
    output_dir = default_output_dir(root)
    _movie(output_dir, old, b"old")
    _movie(output_dir, new, b"new")
    return event_dir


def _edit_manifest(event_dir: Path, **fields: object) -> None:
    payload = json.loads(manifest_path(event_dir).read_text(encoding="utf-8"))
    payload.update(fields)
    manifest_path(event_dir).write_text(json.dumps(payload), encoding="utf-8")


def _root(tmp_path: Path) -> Path:
    return tmp_path / "proj"


def test_dry_run_lists_the_superseded_movie_and_deletes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _root(tmp_path)
    event_dir = _renamed(root)
    output_dir = default_output_dir(root)
    manifest_before = manifest_path(event_dir).read_bytes()

    assert main(["prune-renamed", str(root)]) == 0

    out = capsys.readouterr().out
    assert OLD in out and NEW in out and EVENT in out
    assert "dry run" in out
    assert (output_dir / "2024" / OLD).read_bytes() == b"old"
    assert (output_dir / "2024" / NEW).read_bytes() == b"new"
    assert manifest_path(event_dir).read_bytes() == manifest_before


def test_yes_deletes_only_the_old_movie(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = _root(tmp_path)
    event_dir = _renamed(root)
    output_dir = default_output_dir(root)
    manifest_before = manifest_path(event_dir).read_bytes()

    assert main(["prune-renamed", str(root), "--yes"]) == 0

    out = capsys.readouterr().out
    assert OLD in out and "1 deleted, 0 failed" in out
    assert not (output_dir / "2024" / OLD).exists()
    assert (output_dir / "2024" / NEW).read_bytes() == b"new"
    assert manifest_path(event_dir).read_bytes() == manifest_before


def test_a_second_run_finds_nothing(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = _root(tmp_path)
    _renamed(root)
    assert main(["prune-renamed", str(root), "--yes"]) == 0
    capsys.readouterr()

    assert main(["prune-renamed", str(root), "--yes"]) == 0

    out = capsys.readouterr().out
    assert "No superseded movies" in out
    assert OLD not in out


def test_an_event_retitled_but_not_rerendered_lists_nothing(tmp_path: Path) -> None:
    root = _root(tmp_path)
    event_dir = _event(root, EVENT)
    _record(event_dir, OLD)  # the manifest still records the old movie as the current one
    old = _movie(default_output_dir(root), OLD)

    assert main(["prune-renamed", str(root), "--yes"]) == 0

    assert old.exists()


@pytest.mark.parametrize("replacement", ["missing", "folder"])
def test_the_replacing_movie_must_be_a_regular_file(tmp_path: Path, replacement: str) -> None:
    root = _root(tmp_path)
    event_dir = _event(root, EVENT)
    _record(event_dir, OLD, NEW)
    output_dir = default_output_dir(root)
    old = _movie(output_dir, OLD)
    if replacement == "folder":
        _touch(output_dir / "2024" / NEW / "inside.txt")

    assert main(["prune-renamed", str(root), "--yes"]) == 0

    assert old.exists()


def test_events_without_a_list_or_with_an_unreadable_manifest_list_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _root(tmp_path)
    output_dir = default_output_dir(root)
    no_list = _event(root, "2024-06-21 - Plain")
    _record(no_list, "2024-06-21 - Plain.mp4")
    _movie(output_dir, "2024-06-21 - Plain.mp4")
    stray = _movie(output_dir, "2024-06-21 - Stray.mp4")  # in no manifest: never guessed
    broken = _event(root, "2024-06-22 - Broken")
    _record(broken, "2024-06-22 - Was.mp4", "2024-06-22 - Broken.mp4")
    was = _movie(output_dir, "2024-06-22 - Was.mp4")
    _movie(output_dir, "2024-06-22 - Broken.mp4")
    manifest_path(broken).write_text("{ not json", encoding="utf-8")

    assert main(["prune-renamed", str(root), "--yes"]) == 0

    assert "No superseded movies" in capsys.readouterr().out
    assert stray.exists() and was.exists()


def test_a_movie_another_event_records_is_kept(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _root(tmp_path)
    _renamed(root)
    owner = _event(root, "2024-06-21 - Old Party Retitled")  # records the old name, retitled since
    _record(owner, OLD)
    old = default_output_dir(root) / "2024" / OLD

    assert main(["prune-renamed", str(root), "--yes"]) == 0

    assert old.read_bytes() == b"old"
    assert "No superseded movies" in capsys.readouterr().out


def test_a_pending_takeover_of_the_old_name_keeps_the_file(tmp_path: Path) -> None:
    root = _root(tmp_path)
    _renamed(root)
    _event(root, "2024-06-21 - Old Party")  # not rendered yet; its expected path is the old name
    old = default_output_dir(root) / "2024" / OLD

    assert main(["prune-renamed", str(root), "--yes"]) == 0

    assert old.exists()


def test_an_owner_outside_years_still_protects_the_file(tmp_path: Path) -> None:
    root = _root(tmp_path)
    _renamed(root)
    other = _event(root, "2023-05-05 - Other", year="2023")
    _record(other, OLD)  # filed under 2023, records the 2024 movie as its own
    old = default_output_dir(root) / "2024" / OLD

    assert main(["prune-renamed", str(root), "--years", "2024", "--yes"]) == 0

    assert old.exists()


def test_years_restricts_the_candidates(tmp_path: Path) -> None:
    root = _root(tmp_path)
    _renamed(root)
    other_old = "2023-05-05 - Was.mp4"
    other_new = "2023-05-05 - Is.mp4"
    other = _event(root, "2023-05-05 - Is", year="2023")
    _record(other, other_old, other_new)
    output_dir = default_output_dir(root)
    _movie(output_dir, other_old)
    _movie(output_dir, other_new)

    assert main(["prune-renamed", str(root), "--years", "2024", "--yes"]) == 0

    assert not (output_dir / "2024" / OLD).exists()
    assert (output_dir / "2023" / other_old).exists()


def test_a_renamed_back_event_keeps_its_movie(tmp_path: Path) -> None:
    root = _root(tmp_path)
    event_dir = _event(root, EVENT)
    _record(event_dir, NEW)
    _edit_manifest(event_dir, superseded=[NEW, OLD])  # a stale list naming the current movie
    output_dir = default_output_dir(root)
    current = _movie(output_dir, NEW)
    old = _movie(output_dir, OLD)

    assert main(["prune-renamed", str(root), "--yes"]) == 0

    assert current.exists()
    assert not old.exists()


def test_a_case_only_rename_lists_nothing(tmp_path: Path) -> None:
    root = _root(tmp_path)
    event_dir = _event(root, EVENT)
    _record(event_dir, "2024-06-21 - New party.mp4", NEW)
    output_dir = default_output_dir(root)
    current = _movie(output_dir, NEW)
    other_case = output_dir / "2024" / "2024-06-21 - New party.mp4"
    if not other_case.exists():  # a case-sensitive filesystem holds two files
        _touch(other_case)

    assert main(["prune-renamed", str(root), "--yes"]) == 0

    assert current.exists() and other_case.exists()


def test_the_same_file_under_another_name_is_kept(tmp_path: Path) -> None:
    root = _root(tmp_path)
    event_dir = _event(root, EVENT)
    _record(event_dir, OLD, NEW)
    output_dir = default_output_dir(root)
    current = _movie(output_dir, NEW)
    os.link(current, output_dir / "2024" / OLD)  # the same file by two names

    assert main(["prune-renamed", str(root), "--yes"]) == 0

    assert (output_dir / "2024" / OLD).exists() and current.exists()


@pytest.mark.parametrize("recorded", ["../victim.mp4", "a/b.mp4", "..", ".", ""])
def test_a_name_that_is_not_a_bare_file_name_is_ignored(tmp_path: Path, recorded: str) -> None:
    root = _root(tmp_path)
    event_dir = _renamed(root)
    output_dir = default_output_dir(root)
    victim = _touch(output_dir.parent / "victim.mp4", b"victim")
    _touch(output_dir / "a" / "b.mp4", b"nested")
    _edit_manifest(event_dir, superseded=[recorded])

    assert main(["prune-renamed", str(root), "--yes"]) == 0

    assert victim.read_bytes() == b"victim"
    assert (output_dir / "a" / "b.mp4").exists()
    assert (output_dir / "2024" / OLD).exists()  # not in the list any more: nothing to prune


def test_a_symlinked_year_folder_pointing_outside_is_not_followed(tmp_path: Path) -> None:
    root = _root(tmp_path)
    event_dir = _event(root, EVENT)
    _record(event_dir, OLD, NEW)
    output_dir = default_output_dir(root)
    outside = tmp_path / "elsewhere"
    victim = _touch(outside / OLD, b"victim")
    _touch(outside / NEW, b"new")
    output_dir.mkdir(parents=True)
    (output_dir / "2024").symlink_to(outside, target_is_directory=True)

    assert main(["prune-renamed", str(root), "--yes"]) == 0

    assert victim.read_bytes() == b"victim"


def test_a_symlink_or_a_folder_at_the_old_name_is_not_deleted(tmp_path: Path) -> None:
    root = _root(tmp_path)
    output_dir = default_output_dir(root)
    link_event = _event(root, "2024-06-21 - Link")
    _record(link_event, "2024-06-21 - Was Link.mp4", "2024-06-21 - Link.mp4")
    _movie(output_dir, "2024-06-21 - Link.mp4")
    target = _touch(tmp_path / "target.mp4", b"target")
    link = output_dir / "2024" / "2024-06-21 - Was Link.mp4"
    link.symlink_to(target)
    folder_event = _event(root, "2024-06-22 - Dir")
    _record(folder_event, "2024-06-22 - Was Dir.mp4", "2024-06-22 - Dir.mp4")
    _movie(output_dir, "2024-06-22 - Dir.mp4")
    folder = output_dir / "2024" / "2024-06-22 - Was Dir.mp4"
    _touch(folder / "inside.txt")

    assert main(["prune-renamed", str(root), "--yes"]) == 0

    assert link.is_symlink() and target.read_bytes() == b"target"
    assert (folder / "inside.txt").exists()


def test_a_failed_delete_is_reported_and_the_run_continues(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _root(tmp_path)
    _renamed(root)
    second_old = "2024-06-22 - Was Two.mp4"
    second = _event(root, "2024-06-22 - Two")
    _record(second, second_old, "2024-06-22 - Two.mp4")
    output_dir = default_output_dir(root)
    _movie(output_dir, second_old)
    _movie(output_dir, "2024-06-22 - Two.mp4")
    real_unlink = Path.unlink

    def flaky(self: Path, *args: object, **kwargs: object) -> None:
        if self.name == OLD:
            raise PermissionError(13, "Permission denied", str(self))
        real_unlink(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "unlink", flaky)

    assert main(["prune-renamed", str(root), "--yes"]) == 1

    out = capsys.readouterr().out
    assert "ERROR" in out and "Permission denied" in out
    assert "1 deleted, 1 failed" in out
    assert (output_dir / "2024" / OLD).exists()
    assert not (output_dir / "2024" / second_old).exists()


@pytest.mark.parametrize("patched", ["auto_reel_ng.cli.prune.get_layout", "context"])
def test_a_layout_walk_failure_deletes_nothing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    patched: str,
) -> None:
    root = _root(tmp_path)
    _renamed(root)
    old = default_output_dir(root) / "2024" / OLD

    def broken(_name: str) -> Callable[..., object]:
        def walk(*_args: object, **_kwargs: object) -> object:
            raise PermissionError(13, "Permission denied", str(root))

        return walk

    target = "auto_reel_ng.cli.context.get_layout" if patched == "context" else patched
    monkeypatch.setattr(target, broken)

    assert main(["prune-renamed", str(root), "--yes"]) == 1

    assert "Permission denied" in capsys.readouterr().err
    assert old.exists()


def test_output_selects_the_output_directory(tmp_path: Path) -> None:
    root = _root(tmp_path)
    event_dir = _event(root, EVENT)
    _record(event_dir, OLD, NEW)
    chosen = tmp_path / "chosen"
    _movie(chosen, OLD)
    _movie(chosen, NEW)
    default_old = _movie(default_output_dir(root), OLD)
    _movie(default_output_dir(root), NEW)

    assert main(["prune-renamed", str(root), "-o", str(chosen), "--yes"]) == 0

    assert not (chosen / "2024" / OLD).exists()
    assert default_old.exists()


def test_two_events_that_left_the_same_name_list_it_once(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _root(tmp_path)
    _renamed(root)
    other = _event(root, "2024-06-21 - Other Party")
    _record(other, OLD, "2024-06-21 - Other Party.mp4")
    _movie(default_output_dir(root), "2024-06-21 - Other Party.mp4")

    assert main(["prune-renamed", str(root), "--yes"]) == 0

    assert "1 deleted, 0 failed" in capsys.readouterr().out


def test_a_project_without_events_exits_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _root(tmp_path)
    root.mkdir()

    assert main(["prune-renamed", str(root), "--yes"]) == 0

    assert "No events found" in capsys.readouterr().out


def test_prune_writes_no_manifest_and_leaves_an_event_without_one_alone(tmp_path: Path) -> None:
    root = _root(tmp_path)
    event_dir = _event(root, EVENT)
    stray = _movie(default_output_dir(root), OLD)

    assert main(["prune-renamed", str(root), "--yes"]) == 0

    assert read_manifest(event_dir) is None and stray.exists()


def test_adopt_renders_keeps_the_superseded_list(tmp_path: Path) -> None:
    root = _root(tmp_path)
    event_dir = _renamed(root)
    _edit_manifest(event_dir, fingerprint="stale")  # make the adoption write a new manifest

    assert main(["adopt-renders", str(root)]) == 0

    manifest = read_manifest(event_dir)
    assert manifest is not None
    assert manifest.fingerprint != "stale"  # it was rewritten
    assert manifest.output == NEW and manifest.superseded == (OLD,)
