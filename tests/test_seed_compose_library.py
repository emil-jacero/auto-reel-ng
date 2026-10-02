"""The compose stack's seed: a writable scratch library over a read-only fixture.

``scripts/seed_compose_library.py`` is not part of the package (it is baked into the image and
run by the ``seed`` service), so it is loaded from its file. Every case builds a fake
``auto-reel-media`` under ``tmp_path`` and checks that the seed only ever reads it.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "seed_compose_library.py"

GRILL = Path("2024") / "2024-06-27 - grillning med grannar"
TWO_CHAPTERS = Path("2024") / "2024-08-20 - Två kapitel"
PROVKLIPP = Path("2025") / "2025-01-15 - Provklipp"
GAMMAL = Path("2025") / "2025-01-16 - Gammal rendering"
REEL = "title: Grillning\n"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("seed_compose_library", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(name="seeder")
def _seeder() -> ModuleType:
    return _load()


@pytest.fixture(name="media")
def _media(tmp_path: Path) -> Path:
    media = tmp_path / "auto-reel-media"
    grill = media / "input" / GRILL
    (grill / ".auto-reel" / "cache").mkdir(parents=True)
    (grill / ".auto-reel" / "cache" / "x").write_text("cache")
    (grill / "s1710001.mp4").write_bytes(b"one")
    (grill / "s1710002.mp4").write_bytes(b"two")
    (grill / "reel.yaml").write_text(REEL)
    two = media / "input" / TWO_CHAPTERS
    (two / "Kvällen").mkdir(parents=True)
    (two / "s1.mp4").write_bytes(b"s1")
    (two / "Kvällen" / "s2.mp4").write_bytes(b"s2")
    (two / "Kvällen" / ".auto-reel" / "cache").mkdir(parents=True)
    (two / "Kvällen" / ".auto-reel" / "cache" / "x").write_text("nested cache")
    samples = media / "samples"
    samples.mkdir()
    for name in ("a.mp4", "b.mov", "legacy-x.mp4"):
        (samples / name).write_bytes(name.encode())
    (media / "output").mkdir()
    return media


def _listing(root: Path) -> list[tuple[str, int, int]]:
    """Sorted (path, size, mtime_ns) of every entry, never following a link."""
    rows = []
    for dirpath, dirnames, filenames in os.walk(root):
        for name in dirnames + filenames:
            path = Path(dirpath) / name
            stat = path.lstat()
            rows.append((str(path), stat.st_size, stat.st_mtime_ns))
    return sorted(rows)


def _run(seeder: ModuleType, media: Path, tmp_path: Path, *, reset: bool = False) -> object:
    return seeder.seed(
        media, tmp_path / "library", tmp_path / "library-output", reset=reset, tmp=tmp_path / "tmp"
    )


def test_layout_links_clips_copies_reel_and_drops_the_cache(
    seeder: ModuleType, media: Path, tmp_path: Path
) -> None:
    before = _listing(media)
    counts = _run(seeder, media, tmp_path)
    library = tmp_path / "library"

    grill = library / GRILL
    for name in ("s1710001.mp4", "s1710002.mp4"):
        link = grill / name
        assert link.is_symlink()
        assert Path(os.readlink(link)) == media / "input" / GRILL / name
        assert Path(os.readlink(link)).is_absolute()
    reel = grill / "reel.yaml"
    assert reel.is_file() and not reel.is_symlink()
    assert reel.read_bytes() == (media / "input" / GRILL / "reel.yaml").read_bytes()
    assert not any(p.name == ".auto-reel" for p in library.rglob("*"))
    assert sorted(p.name for p in (library / TWO_CHAPTERS / "Kvällen").iterdir()) == ["s2.mp4"]

    chapter = library / TWO_CHAPTERS / "Kvällen"
    assert chapter.is_dir() and not chapter.is_symlink()
    assert (
        Path(os.readlink(chapter / "s2.mp4"))
        == media / "input" / TWO_CHAPTERS / "Kvällen" / "s2.mp4"
    )
    assert (library / TWO_CHAPTERS / "s1.mp4").is_symlink()

    assert sorted(p.name for p in (library / PROVKLIPP).iterdir()) == ["a.mp4", "b.mov"]
    assert [p.name for p in (library / GAMMAL).iterdir()] == ["legacy-x.mp4"]
    assert (tmp_path / "library-output").is_dir()

    assert counts == seeder.SeedCounts(
        events=4, reel_copied=1, reel_kept=0, link_new=7, link_kept=0
    )
    assert _listing(media) == before


def test_reseeding_keeps_edits_and_engine_files(
    seeder: ModuleType, media: Path, tmp_path: Path
) -> None:
    before = _listing(media)
    _run(seeder, media, tmp_path)
    grill = tmp_path / "library" / GRILL
    (grill / "reel.yaml").write_text("title: Grillning (GUI-sparad)\n")
    manifest = grill / ".auto-reel" / "cache" / "render-manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text("{}")
    # A render in flight while `up` re-seeds: its scratch must survive a plain re-seed.
    scratch = tmp_path / "tmp" / "auto-reel-render-abc" / "seg_000.mp4"
    scratch.parent.mkdir(parents=True)
    scratch.write_bytes(b"segment")

    counts = _run(seeder, media, tmp_path)

    assert counts.reel_copied == 0 and counts.link_new == 0
    assert counts.reel_kept == 1 and counts.link_kept == 7
    assert (grill / "reel.yaml").read_text() == "title: Grillning (GUI-sparad)\n"
    assert manifest.read_text() == "{}"
    assert scratch.read_bytes() == b"segment"
    assert _listing(media) == before


def test_reset_empties_library_output_and_tmp_and_restores_the_fixture_reel(
    seeder: ModuleType, media: Path, tmp_path: Path
) -> None:
    before = _listing(media)
    _run(seeder, media, tmp_path)
    grill = tmp_path / "library" / GRILL
    (grill / "reel.yaml").write_text("title: edited\n")
    (grill / "stray.txt").write_text("engine wrote this")
    (tmp_path / "library-output" / "movie.mp4").write_bytes(b"rendered")
    killed = tmp_path / "tmp" / "auto-reel-render-killed"
    killed.mkdir(parents=True)
    (killed / "seg_000.mp4").write_bytes(b"left behind by a killed render")

    counts = _run(seeder, media, tmp_path, reset=True)

    assert (grill / "reel.yaml").read_text() == REEL
    assert not (grill / "stray.txt").exists()
    assert list((tmp_path / "library-output").iterdir()) == []
    assert list((tmp_path / "tmp").iterdir()) == []
    assert counts.reel_copied == 1 and counts.link_new == 7
    # Removing a clip symlink never follows it: the fixture is byte-identical.
    assert _listing(media) == before
    assert (media / "input" / GRILL / "s1710001.mp4").read_bytes() == b"one"


def test_missing_fixture_fails_loud_naming_input(
    seeder: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    media = tmp_path / "empty-media"
    media.mkdir()
    code = seeder.main(
        [
            "--media",
            str(media),
            "--library",
            str(tmp_path / "library"),
            "--output",
            str(tmp_path / "library-output"),
        ]
    )
    assert code == 1
    assert f"{media}/input" in capsys.readouterr().err
    assert not (tmp_path / "library").exists()


def test_main_prints_one_counts_line(
    seeder: ModuleType, media: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    library = tmp_path / "library"
    args = ["--media", str(media), "--library", str(library), "--output", str(tmp_path / "out")]
    assert seeder.main(args) == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert out == [
        f"seed: 4 events under {library}: reel_copied=1 reel_kept=0 link_new=7 link_kept=0"
    ]
