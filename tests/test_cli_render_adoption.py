"""End-to-end NEW-clip adoption through ``render`` (D-12): real ffmpeg, no mocks.

A scratch library in ``tmp_path`` is rendered by the real CLI, clips are added,
and the next render must adopt each into its folder's chapter (or the default
chapter when ``reel.yaml`` names no such chapter), so the movie's chapters are
the ones ``reel.yaml`` lists. A ``reel.yaml`` that names no chapters is adopted
into as a new event is seeded.
"""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from pathlib import Path

import pytest

from auto_reel_ng.cli.adoption import REEL_FILENAME
from auto_reel_ng.cli.main import main
from auto_reel_ng.ffmpeg.runtime import FfmpegRuntime
from auto_reel_ng.reel import load_document

TVA_KAPITEL = "2024-08-20 - Två kapitel - Tjörn"
UTAN_KAPITEL = "2024-09-10 - Utan kapitel"
NO_CHAPTERS_REEL = "version: 0\nmetadata:\n  title: Utan Kapitel\n"


def _place_clip(source: Path, event_dir: Path, identity: str, minute: int) -> None:
    """Copy the synthetic clip to ``identity`` with a fixed mtime, so ``datetime`` order is known."""
    target = event_dir / identity
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(source, target)
    stamp = datetime(2024, 8, 20, 18, minute).timestamp()
    os.utime(target, (stamp, stamp))


def _chapters(event_dir: Path) -> list[tuple[str, list[str]]]:
    document = load_document(event_dir / REEL_FILENAME)
    return [
        (chapter.name, [ref.identity for ref in chapter.clips]) for chapter in document.chapters
    ]


def _movie_chapters(runtime: FfmpegRuntime, movie: Path) -> list[tuple[str, float]]:
    """``(title, span in seconds)`` per chapter the movie's container carries."""
    probe = runtime.run_ffprobe(
        ["-v", "error", "-show_chapters", "-print_format", "json", str(movie)]
    )
    return [
        (
            chapter.get("tags", {}).get("title", ""),
            float(chapter["end_time"]) - float(chapter["start_time"]),
        )
        for chapter in json.loads(probe.stdout)["chapters"]
    ]


def _movie(out: Path, prefix: str) -> Path:
    movies = list((out / "2024").glob(f"{prefix}*.mp4"))
    assert len(movies) == 1, movies
    return movies[0]


@pytest.mark.has_ffmpeg
def test_render_adopts_new_clips_into_their_folders_chapters(
    runtime: FfmpegRuntime, make_clip, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    clip = make_clip("source.mp4", width=320, height=240, fps=30, duration=1.0)
    root = tmp_path / "library"
    out = tmp_path / "library-output"
    tva = root / "2024" / TVA_KAPITEL
    utan = root / "2024" / UTAN_KAPITEL
    for identity, minute in (
        ("s1710001.mp4", 1),
        ("Kvällen/s1710002.mp4", 2),
        ("Kvällen/s1710003.mp4", 3),
    ):
        _place_clip(clip, tva, identity, minute)
        _place_clip(clip, utan, identity, minute)
    (utan / REEL_FILENAME).write_text(NO_CHAPTERS_REEL, encoding="utf-8")
    render = ["render", str(root), "-o", str(out), "--device", "cpu"]

    # 1. The first render seeds Två kapitel, and seeds the chapterless Utan kapitel too.
    assert main(render) == 0
    capsys.readouterr()
    assert _chapters(tva) == [
        ("", ["s1710001.mp4"]),
        ("Kvällen", ["Kvällen/s1710002.mp4", "Kvällen/s1710003.mp4"]),
    ]
    assert _chapters(utan) == _chapters(tva)
    assert (utan / REEL_FILENAME).read_text(encoding="utf-8").startswith(NO_CHAPTERS_REEL)
    utan_spans = _movie_chapters(runtime, _movie(out, "2024-09-10"))
    assert [title for title, _ in utan_spans] == ["", "Kvällen"]
    assert utan_spans[1][1] == pytest.approx(2.0, abs=0.3)

    # 2. A clip added to Kvällen joins Kvällen; one in a folder with no chapter joins Main.
    _place_clip(clip, tva, "Kvällen/s1710004.mp4", 4)
    _place_clip(clip, tva, "Dag 2/s1710005.mp4", 5)
    assert main(render) == 0
    assert "adopted 2 new clip(s)" in capsys.readouterr().out
    assert _chapters(tva) == [
        ("", ["s1710001.mp4", "Dag 2/s1710005.mp4"]),
        ("Kvällen", ["Kvällen/s1710002.mp4", "Kvällen/s1710003.mp4", "Kvällen/s1710004.mp4"]),
    ]
    spans = _movie_chapters(runtime, _movie(out, "2024-08-20"))
    assert len(spans) == 2
    assert spans[0][1] == pytest.approx(2.0, abs=0.3)
    assert spans[1][0] == "Kvällen"
    assert spans[1][1] == pytest.approx(3.0, abs=0.3)

    # 3. Nothing is NEW any more: the event is fresh, neither adopted into nor rendered,
    # and neither its reel.yaml nor its movie is rewritten.
    reel_before = (tva / REEL_FILENAME).read_bytes()
    movie = _movie(out, "2024-08-20")
    movie_before = (movie.stat().st_mtime_ns, movie.read_bytes())
    assert main(render) == 0
    third = capsys.readouterr().out
    tva_lines = [line for line in third.splitlines() if TVA_KAPITEL in line]
    assert tva_lines == [f"FRESH  {TVA_KAPITEL}: up to date, not rendered"], third
    assert (tva / REEL_FILENAME).read_bytes() == reel_before
    assert (movie.stat().st_mtime_ns, movie.read_bytes()) == movie_before
