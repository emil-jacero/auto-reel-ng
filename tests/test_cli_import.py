"""``import`` isolates failures per event (headless-cli: ``import`` adopts legacy metadata).

One event with unreadable, non-UTF-8, malformed or non-mapping metadata is reported as
``ERROR`` and the batch carries on; the command exits non-zero and still prints its count.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from auto_reel_ng.cli import commands
from auto_reel_ng.cli.main import main
from auto_reel_ng.errors import ReelParseError
from auto_reel_ng.reel import load_document

GOOD_METADATA = "metadata:\n  title: {title}\n"
BAD = "2024-05-02 - Bad"


def _event(root: Path, name: str, metadata: bytes) -> Path:
    event_dir = root / "2024" / name
    event_dir.mkdir(parents=True)
    (event_dir / "metadata.yaml").write_bytes(metadata)
    return event_dir


def _good(title: str) -> bytes:
    return GOOD_METADATA.format(title=title).encode()


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return tmp_path / "proj"


# --------------------------------------------------------------------------- #
# the reader
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "content",
    [b"\xff\xfe\xfa", b"a: [unclosed\n", b"- one\n- two\n", b"", b"just text\n"],
    ids=["not-utf8", "malformed", "list-root", "empty", "scalar-root"],
)
def test_reader_raises_a_parse_error_naming_the_path(tmp_path: Path, content: bytes) -> None:
    path = tmp_path / "metadata.yaml"
    path.write_bytes(content)

    with pytest.raises(ReelParseError, match="metadata.yaml"):
        commands._read_legacy_mapping(path)


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores file permissions")
def test_reader_raises_a_parse_error_for_an_unreadable_file(tmp_path: Path) -> None:
    path = tmp_path / "metadata.yaml"
    path.write_bytes(b"a: 1\n")
    path.chmod(0o000)
    try:
        with pytest.raises(ReelParseError, match="metadata.yaml"):
            commands._read_legacy_mapping(path)
    finally:
        path.chmod(0o644)


def test_has_version_is_true_only_for_a_key_in_a_mapping(tmp_path: Path) -> None:
    v2 = tmp_path / "v2.yaml"
    v2.write_text("version: 1\n", encoding="utf-8")
    legacy = tmp_path / "legacy.yaml"
    legacy.write_text("metadata:\n  title: X\n", encoding="utf-8")

    assert commands._has_version(v2) is True
    assert commands._has_version(legacy) is False


@pytest.mark.parametrize(
    "content", [b"", b"- a\n", b"just text\n"], ids=["empty", "list", "scalar"]
)
def test_has_version_is_false_for_an_empty_or_non_mapping_root(
    tmp_path: Path, content: bytes
) -> None:
    path = tmp_path / "reel.yaml"
    path.write_bytes(content)

    assert commands._has_version(path) is False


@pytest.mark.parametrize(
    "content", [b"\xff\xfe\xfa", b"a: [unclosed\n"], ids=["not-utf8", "malformed"]
)
def test_has_version_still_raises_for_an_unparseable_file(tmp_path: Path, content: bytes) -> None:
    path = tmp_path / "reel.yaml"
    path.write_bytes(content)

    with pytest.raises(ReelParseError, match="reel.yaml"):
        commands._has_version(path)


def test_a_malformed_yaml_reason_is_one_line_naming_the_file_only(tmp_path: Path) -> None:
    path = tmp_path / "metadata.yaml"
    path.write_bytes(b"a: [unclosed\nb: 1\n")

    with pytest.raises(ReelParseError) as info:
        commands._read_legacy_mapping(path)

    message = str(info.value)
    assert "\n" not in message
    assert message.startswith("metadata.yaml: malformed YAML")
    assert str(tmp_path) not in message


# --------------------------------------------------------------------------- #
# the batch
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("bad", "reason"),
    [
        (b"\xff\xfe\xfa", "UTF-8"),
        (b"a: [unclosed\n", "malformed"),
        (b"- one\n- two\n", "must be a mapping"),
    ],
    ids=["not-utf8", "malformed", "list-root"],
)
def test_a_bad_metadata_file_fails_only_its_event(
    root: Path, capsys: pytest.CaptureFixture[str], bad: bytes, reason: str
) -> None:
    first = _event(root, "2024-05-01 - First", _good("First"))
    middle = _event(root, BAD, bad)
    last = _event(root, "2024-05-03 - Last", _good("Last"))

    assert main(["import", str(root)]) == 1

    out = capsys.readouterr().out
    assert out.count("ERROR") == 1
    assert f"ERROR  {BAD}:" in out
    assert reason in out
    assert "OK     2024-05-01 - First" in out
    assert "OK     2024-05-03 - Last" in out
    assert "imported 2 event(s), 1 failed" in out
    assert load_document(first / "reel.yaml").metadata.title == "First"
    assert load_document(last / "reel.yaml").metadata.title == "Last"
    assert not (middle / "reel.yaml").exists()


def test_a_malformed_reel_yaml_without_metadata_is_that_events_error(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    broken = root / "2024" / BAD
    broken.mkdir(parents=True)
    (broken / "reel.yaml").write_text("a: [unclosed\n", encoding="utf-8")
    last = _event(root, "2024-05-03 - Last", _good("Last"))

    assert main(["import", str(root)]) == 1

    out = capsys.readouterr().out
    assert f"ERROR  {BAD}:" in out
    assert "imported 1 event(s), 1 failed" in out
    assert (broken / "reel.yaml").read_text(encoding="utf-8") == "a: [unclosed\n"
    assert load_document(last / "reel.yaml").metadata.title == "Last"


@pytest.mark.parametrize("overwrite", [False, True], ids=["plain", "overwrite"])
@pytest.mark.parametrize("reel_content", ["", "- a\n"], ids=["empty", "list"])
def test_an_empty_or_non_mapping_reel_yaml_beside_metadata_is_still_imported(
    root: Path, capsys: pytest.CaptureFixture[str], reel_content: str, overwrite: bool
) -> None:
    event = _event(root, "2024-05-01 - First", _good("New"))
    (event / "reel.yaml").write_text(reel_content, encoding="utf-8")

    assert main(["import", str(root), *(["--overwrite"] if overwrite else [])]) == 0

    out = capsys.readouterr().out
    assert "OK     2024-05-01 - First" in out
    assert load_document(event / "reel.yaml").metadata.title == "New"


def test_overwrite_heals_a_malformed_reel_yaml_beside_metadata(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    event = _event(root, "2024-05-01 - First", _good("New"))
    (event / "reel.yaml").write_text("a: [unclosed\n", encoding="utf-8")

    assert main(["import", str(root), "--overwrite"]) == 0

    assert load_document(event / "reel.yaml").metadata.title == "New"


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
def test_an_event_folder_that_cannot_be_searched_is_that_events_error(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    locked = _event(root, BAD, _good("Locked"))
    last = _event(root, "2024-05-03 - Last", _good("Last"))
    locked.chmod(0o600)
    try:
        code = main(["import", str(root)])
    finally:
        locked.chmod(0o755)

    out = capsys.readouterr().out
    assert code == 1
    assert f"ERROR  {BAD}:" in out
    assert "imported 1 event(s), 1 failed" in out
    assert not (locked / "reel.yaml").exists()
    assert load_document(last / "reel.yaml").metadata.title == "Last"


def test_a_skipped_event_does_not_fail_the_command(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    legacy = _event(root, "2024-05-01 - Legacy", _good("Legacy"))
    v2 = _event(root, "2024-05-02 - Already", _good("Other"))
    (v2 / "reel.yaml").write_text("version: 1\nmetadata:\n  title: Already\n", encoding="utf-8")

    assert main(["import", str(root)]) == 0

    out = capsys.readouterr().out
    assert "SKIP   2024-05-02 - Already" in out
    assert "imported 1 event(s)" in out
    assert "failed" not in out
    assert (legacy / "reel.yaml").exists()


def test_a_failed_write_keeps_the_events_old_reel_yaml(
    root: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    event = _event(root, "2024-05-01 - First", _good("First"))
    (event / "reel.yaml").write_text("metadata:\n  title: Old\n", encoding="utf-8")
    last = _event(root, "2024-05-03 - Last", _good("Last"))
    real_write = commands.write_document

    def failing_write(document: object, path: Path) -> None:
        if path.parent == event:
            raise PermissionError(13, "Permission denied", str(path))
        real_write(document, path)  # type: ignore[arg-type]

    monkeypatch.setattr(commands, "write_document", failing_write)

    assert main(["import", str(root)]) == 1

    out = capsys.readouterr().out
    assert "ERROR  2024-05-01 - First:" in out
    assert (event / "reel.yaml").read_text(encoding="utf-8") == "metadata:\n  title: Old\n"
    assert load_document(last / "reel.yaml").metadata.title == "Last"
