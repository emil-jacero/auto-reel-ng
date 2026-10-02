"""``enqueue`` reports from the insertion's own verdict (headless-cli: ``enqueue`` records jobs).

A fake store stands in for Postgres so the test can make the job store's ``submit`` disagree
with an earlier ``active_job`` read, which is what a concurrent ``enqueue`` does.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, List, Optional
from unittest.mock import Mock

import pytest

from auto_reel_ng.cli import commands
from auto_reel_ng.cli.main import main
from auto_reel_ng.persistence.job_store import Submission

JOB_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")


class _FakeStore:
    """Answers ``active_job`` with nothing and ``submit`` with a fixed verdict."""

    def __init__(self, *, created: bool) -> None:
        self._created = created
        self.submitted: List[str] = []

    def active_job(self, project_root: str, event_dir: str) -> Optional[Any]:
        return None  # nothing visible to a pre-read, whatever the insert finds

    def submit(self, project_root: str, event_dir: str, **kwargs: Any) -> Submission:
        self.submitted.append(event_dir)
        return Submission(job_id=JOB_ID, created=self._created)

    def enqueue(self, project_root: str, event_dir: str, **kwargs: Any) -> uuid.UUID:
        return self.submit(project_root, event_dir, **kwargs).job_id


def _project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    clip = root / "2024" / "2024-06-21 - A" / "00400.mp4"
    clip.parent.mkdir(parents=True)
    clip.write_bytes(b"")
    return root


def _enqueue(monkeypatch: pytest.MonkeyPatch, root: Path, *, created: bool) -> "_FakeStore":
    store = _FakeStore(created=created)
    monkeypatch.setattr(
        commands, "FfmpegRuntime", lambda *a, **k: Mock(name="runtime", version=(7, 1))
    )
    monkeypatch.setattr(commands, "_job_store", lambda project_root: store)
    assert main(["enqueue", str(root)]) == 0
    return store


def test_an_insert_that_found_an_active_job_is_reported_as_existing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    store = _enqueue(monkeypatch, _project(tmp_path), created=False)

    out = capsys.readouterr().out
    assert f"=  2024-06-21 - A: already queued/running ({JOB_ID})" in out
    assert "+  " not in out
    assert "0/1 event(s) newly queued" in out
    assert store.submitted == ["2024/2024-06-21 - A"]


def test_an_insert_that_created_a_row_is_reported_and_counted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _enqueue(monkeypatch, _project(tmp_path), created=True)

    out = capsys.readouterr().out
    assert f"+  2024-06-21 - A: queued ({JOB_ID})" in out
    assert "=  " not in out
    assert "1/1 event(s) newly queued" in out
