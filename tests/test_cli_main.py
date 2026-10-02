"""Tests for the CLI entry point: help, unknown subcommand, error exit codes."""

from __future__ import annotations

from pathlib import Path

import pytest

from auto_reel_ng.cli.main import main


def test_help_lists_the_eleven_subcommands(capsys: pytest.CaptureFixture[str]) -> None:
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
        "prune-renamed",
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


def test_a_bad_config_yaml_is_a_one_line_error_not_a_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "config.yaml").write_text("look: {a: 2024-02-30}\n", encoding="utf-8")
    assert main(["scan", str(tmp_path)]) == 1
    err = capsys.readouterr().err
    assert "malformed YAML" in err
    assert str(tmp_path / "config.yaml") in err
    assert "Traceback" not in err
