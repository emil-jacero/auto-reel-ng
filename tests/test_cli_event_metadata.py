"""Batch commands isolate per-event document errors (headless-cli: an event without a
real date and title fails on its own).

``render`` runs with the heavy engine seams patched (as in ``test_cli_render.py``), so
these tests cover the CLI's per-event reporting, not ffmpeg.
"""

from __future__ import annotations

from pathlib import Path
from typing import List
from unittest.mock import Mock

import pytest

from auto_reel_ng.accel.profiles.cpu import CPUProfile
from auto_reel_ng.cli import build as build_module
from auto_reel_ng.cli import commands
from auto_reel_ng.cli.main import main
from auto_reel_ng.config import default_output_dir
from auto_reel_ng.render import BatchOutcome, RenderJob, RenderResult

GOLF = "2019-04-31 - Golfträning med Emil - Tjörn"
YNGVE = "2004 - Yngve berättar om skövde"
KENT = "2016 - Kents film - Gran Canaria"


def _touch(path: Path, content: bytes = b"") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _add_event(root: Path, year: str, name: str) -> Path:
    event_dir = root / year / name
    _touch(event_dir / "00400.mp4")
    return event_dir


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return tmp_path / "proj"


@pytest.fixture
def rendered(monkeypatch: pytest.MonkeyPatch) -> List[RenderJob]:
    """Patch the engine seams; collect every job that reaches ``render_batch``."""
    monkeypatch.setattr(
        commands, "FfmpegRuntime", lambda *a, **k: Mock(name="runtime", version=(7, 1))
    )
    monkeypatch.setattr(commands, "detect_capabilities", lambda *a, **k: Mock(name="inventory"))
    monkeypatch.setattr(commands, "select_profile", lambda *a, **k: CPUProfile())
    monkeypatch.setattr(build_module, "probe_media", lambda *a, **k: Mock(name="clip_meta"))
    seen: List[RenderJob] = []

    def fake_batch(jobs: List[RenderJob]) -> List[BatchOutcome]:
        seen.extend(jobs)
        return [
            BatchOutcome(job=job, result=RenderResult(output_path=job.options.output_dir / "m.mp4"))
            for job in jobs
        ]

    monkeypatch.setattr(commands, "render_batch", fake_batch)
    return seen


def test_render_isolates_an_impossible_folder_date(
    root: Path, rendered: List[RenderJob], capsys: pytest.CaptureFixture[str]
) -> None:
    golf = _add_event(root, "2019", GOLF)
    _add_event(root, "2019", "2019-04-30 - Golf")
    _add_event(root, "2019", "2019-05-01 - Tennis")

    assert main(["render", str(root)]) == 1

    out = capsys.readouterr().out
    assert f"ERROR  {GOLF}: no date: folder name date 2019-04-31 is not a real date" in out
    assert "metadata.date in reel.yaml" in out
    assert sorted(job.options.event_dir.name for job in rendered) == [
        "2019-04-30 - Golf",
        "2019-05-01 - Tennis",
    ]
    assert not (golf / "reel.yaml").exists()  # no seed persisted for a failing event


def test_scan_reports_a_year_only_event_until_reel_yaml_dates_it(
    root: Path, rendered: List[RenderJob], capsys: pytest.CaptureFixture[str]
) -> None:
    yngve = _add_event(root, "2004", YNGVE)

    assert main(["scan", str(root)]) == 1
    assert f"ERROR  {YNGVE}: no date: folder name has a year only (2004)" in capsys.readouterr().out

    (yngve / "reel.yaml").write_text("version: 0\nmetadata:\n  date: 2004-05-01\n", "utf-8")
    assert main(["scan", str(root)]) == 0
    out = capsys.readouterr().out
    assert "ERROR" not in out
    assert f"Yngve Berättar om Skövde  [{yngve}]" in out


def test_scan_lists_the_rest_when_one_reel_yaml_is_unparseable(
    root: Path, rendered: List[RenderJob], capsys: pytest.CaptureFixture[str]
) -> None:
    bad = _add_event(root, "2024", "2024-06-21 - Midsommar")
    (bad / "reel.yaml").write_text("version: 0\nmetadata: [unclosed\n", "utf-8")
    _add_event(root, "2024", "2024-07-01 - Bad")
    _add_event(root, "2024", "2024-08-01 - Fest")

    assert main(["scan", str(root)]) == 1

    out = capsys.readouterr().out
    assert "ERROR  2024-06-21 - Midsommar:" in out
    assert "malformed YAML" in out
    assert "Bad  [" in out
    assert "Fest  [" in out


@pytest.mark.parametrize(
    ("content", "named"),
    [
        pytest.param(
            b"version: 0\nmetadata:\n  title: Barbecue\n  date: 2024-02-30\n",
            "'2024-02-30'",
            id="impossible-date",
        ),
        pytest.param(
            "version: 0\nmetadata:\n  title: Grillkväll\n".encode("latin-1"),
            "not UTF-8 text",
            id="latin-1",
        ),
    ],
)
def test_scan_isolates_an_impossible_reel_yaml_date(
    root: Path,
    rendered: List[RenderJob],
    capsys: pytest.CaptureFixture[str],
    content: bytes,
    named: str,
) -> None:
    """A value or a byte the YAML reader cannot load costs one event, never the scan."""
    _add_event(root, "2024", "2024-06-21 - Midsommar")
    barbecue = _add_event(root, "2024", "2024-07-04 - Barbecue")
    (barbecue / "reel.yaml").write_bytes(content)
    _add_event(root, "2024", "2024-08-01 - Kräftskiva")

    assert main(["scan", str(root)]) == 1

    out = capsys.readouterr().out
    errors = [line for line in out.splitlines() if "ERROR" in line]
    assert len(errors) == 1
    assert errors[0].startswith("ERROR  2024-07-04 - Barbecue: ")
    assert named in errors[0]
    assert "Midsommar  [" in out
    assert "Kräftskiva  [" in out


def test_adopt_renders_reports_bad_names_not_untitled_claimants(
    root: Path, rendered: List[RenderJob], capsys: pytest.CaptureFixture[str]
) -> None:
    _add_event(root, "2004", YNGVE)
    _add_event(root, "2016", KENT)
    _add_event(root, "2019", GOLF)
    _add_event(root, "2024", "2024-06-21 - Midsommar")
    _touch(default_output_dir(root) / "2024" / "2024-06-21 - Midsommar.mp4")

    assert main(["adopt-renders", str(root), "--dry-run"]) == 1

    out = capsys.readouterr().out
    assert out.count("ERROR") == 3
    assert "Untitled" not in out
    assert "claimed by" not in out
    assert "+  2024-06-21 - Midsommar: would adopt at current fingerprint" in out
    assert "1 would adopt, 0 already fresh, 0 unrendered" in out
