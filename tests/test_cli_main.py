"""Tests for the CLI entry point: help, unknown subcommand, error exit codes."""

from __future__ import annotations

from pathlib import Path

import pytest

from auto_reel_ng.cli.main import main


def test_help_lists_the_ten_subcommands(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    for command in (
        "render",
        "scan",
        "analyze",
        "import",
        "enqueue",
        "worker",
        "jobs",
        "serve",
        "adopt-renders",
        "thumbs",
    ):
        assert command in out


def test_unknown_subcommand_exits_nonzero() -> None:
    with pytest.raises(SystemExit) as exc:
        main(["frobnicate"])
    assert exc.value.code != 0


def test_no_command_exits_nonzero() -> None:
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code != 0


def test_bad_root_returns_nonzero(tmp_path: Path) -> None:
    assert main(["scan", str(tmp_path / "does-not-exist")]) == 1
