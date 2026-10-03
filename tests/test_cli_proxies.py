"""Tests for ``auto-reel proxies``: what it walks, what it prints, and that it never writes into
the library (D-21, headless-cli).

The unit tests replace ``FfmpegRuntime`` with a ``Mock``, ``ensure_proxy`` with a fake that
writes a complete entry at the real ``entry_dir`` (or raises ``ProxyError`` for a zero-byte clip),
and ``ensure_filmstrip`` with a fake that writes ``filmstrip.jpg`` and its record; ``lookup_proxy``
and ``lookup_filmstrip`` are the real ones, so a second run finds what the first wrote. The last
tests run the real encode and the real sprite over a read-only library.
"""

from __future__ import annotations

import json
import logging
import os
import stat
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from unittest.mock import Mock

import pytest
from test_cli_thumbs import (
    GRILLNING,
    KRAFTSKIVA,
    MIDSOMMAR,
    OMOJLIGT,
    SOMMARLOV,
    TJORN,
    TRASIG,
    _build_library,
    _error_lines,
    _snapshot,
    _write,
)

from auto_reel_ng.accel.profiles import CPUProfile
from auto_reel_ng.cli import proxies as proxies_cli
from auto_reel_ng.cli.main import main
from auto_reel_ng.errors import (
    AccelError,
    FfmpegCancelledError,
    FilmstripError,
    ProxyCacheError,
    ProxyError,
)
from auto_reel_ng.proxies import (
    FILMSTRIP_VERSION,
    Filmstrip,
    ProxyEntry,
    ProxySettings,
    entry_dir,
)
from auto_reel_ng.proxies.cache import read_entry
from auto_reel_ng.proxies.facts import ProxyFacts, write_facts
from auto_reel_ng.proxies.spec import PROXY_VERSION

FACTS = ProxyFacts(
    proxy_version=PROXY_VERSION,
    duration=1.0,
    fps_num=25,
    fps_den=1,
    vfr=False,
    frames=25,
    width=960,
    height=540,
    source_width=1920,
    source_height=1080,
    rotation=None,
    audio_codec="aac",
    encode_path="cpu",
    fallback_reason=None,
)


@pytest.fixture(autouse=True)
def enabled_loggers(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the proxy loggers enabled: an Alembic ``fileConfig`` run by an earlier test disables
    every logger that already exists (``disable_existing_loggers``)."""
    for name in ("auto_reel_ng.cli.proxies",):
        monkeypatch.setattr(logging.getLogger(name), "disabled", False)


@pytest.fixture(autouse=True)
def hermetic_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No test may reach the real home or cache: HOME and XDG_CACHE_HOME live under tmp_path."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg"))


@pytest.fixture
def library(tmp_path: Path) -> Path:
    """The library at ``tmp_path/library``; the cache defaults to its sibling ``xdg``."""
    root = tmp_path / "library"
    _build_library(root)
    return root


@pytest.fixture
def cache_dir(tmp_path: Path) -> Path:
    return tmp_path / "xdg" / "auto-reel" / "proxies"


class Recorder:
    """What the fakes saw."""

    def __init__(self) -> None:
        self.clips: List[Path] = []
        self.films: List[Path] = []
        self.cancels: List[Callable[[], bool]] = []
        self.profiles: List[object] = []
        self.overrides: List[Optional[str]] = []
        self.runtimes = 0


FakeInstall = Callable[..., Recorder]


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> FakeInstall:
    """Install a Mock runtime, a CPU profile and a fake ``ensure_proxy``; returns its recorder."""

    def install(
        error: Optional[BaseException] = None,
        select_error: Optional[BaseException] = None,
        film_fails: Optional[Callable[[Path], Optional[BaseException]]] = None,
    ) -> Recorder:
        seen = Recorder()

        def fake_runtime(*args: Any, **kwargs: Any) -> Mock:
            seen.runtimes += 1
            return Mock()

        def fake_select(inventory: object, override: Optional[str] = None) -> CPUProfile:
            seen.overrides.append(override)
            if select_error is not None:
                raise select_error
            return CPUProfile()

        def fake_ensure(
            clip: Path,
            *,
            settings: ProxySettings,
            runtime: object,
            profile: object,
            render_node: Optional[str] = None,
            on_progress: object = None,
            should_cancel: Optional[Callable[[], bool]] = None,
        ) -> ProxyEntry:
            seen.clips.append(clip)
            seen.profiles.append(profile)
            assert should_cancel is not None
            seen.cancels.append(should_cancel)
            if error is not None:
                raise error
            if clip.stat().st_size == 0:
                raise ProxyError(str(clip), "File is empty (zero bytes)")
            directory = entry_dir(clip, settings.cache_dir)
            directory.mkdir(parents=True, exist_ok=True)
            (directory / "proxy.mp4").write_bytes(b"\x00" * 1000)
            write_facts(directory, FACTS)
            entry = read_entry(directory)
            assert entry is not None
            return ProxyEntry(
                entry.key, entry.directory, entry.proxy_path, entry.facts_path, entry.facts, True
            )

        def fake_film(clip: Path, entry: ProxyEntry, *, runtime: object) -> Filmstrip:
            seen.films.append(clip)
            failure = film_fails(clip) if film_fails is not None else None
            if failure is not None:
                raise failure
            target = entry.directory / "filmstrip.jpg"
            target.write_bytes(b"\xff\xd8" * 250)
            record = {
                "version": FILMSTRIP_VERSION,
                "tiles": 1,
                "interval": 1,
                "columns": 1,
                "rows": 1,
                "tile_width": 160,
                "tile_height": 90,
                "width": 160,
                "height": 90,
                "bytes": target.stat().st_size,
            }
            document = json.loads(entry.facts_path.read_text(encoding="utf-8"))
            entry.facts_path.write_text(json.dumps({**document, "filmstrip": record}))
            film = Filmstrip.from_json(record, target)
            assert film is not None
            return Filmstrip(**{**film.__dict__, "generated": True})

        monkeypatch.setattr(proxies_cli, "FfmpegRuntime", fake_runtime)
        monkeypatch.setattr(proxies_cli, "ensure_filmstrip", fake_film)
        monkeypatch.setattr(proxies_cli, "detect_capabilities", lambda runtime: object())
        monkeypatch.setattr(proxies_cli, "select_profile", fake_select)
        monkeypatch.setattr(proxies_cli, "ensure_proxy", fake_ensure)
        return seen

    return install


def _identities(seen: Recorder, root: Path) -> set[str]:
    return {str(clip.relative_to(root)) for clip in seen.clips}


# --------------------------------------------------------------------------- #
# the walk, the output, the exit code
# --------------------------------------------------------------------------- #


def test_proxies_fill_the_cache_and_report_the_broken_clip(
    library: Path, cache_dir: Path, fake: FakeInstall, capsys: pytest.CaptureFixture[str]
) -> None:
    fake()

    assert main(["proxies", str(library)]) == 1

    out = capsys.readouterr().out
    assert _error_lines(out) == [
        "ERROR  2024-10-05 - Trasig/trasig.mp4: File is empty (zero bytes)"
    ]
    lines = out.splitlines()
    for event_line in (
        "2023-06-23 - Midsommar - Dalarna: 1 clip, 1 generated; filmstrips: 1 generated",
        "2024-02-30 - Omöjligt datum: 1 clip, 1 generated; filmstrips: 1 generated",
        "2024-06-27 - Grillning med grannar: 4 clips, 4 generated; filmstrips: 4 generated",
        "2024-08-20 - Två kapitel - Tjörn: 5 clips, 5 generated; filmstrips: 5 generated",
        "2024-09-01 - Sommarlov: 2 clips, 2 generated; filmstrips: 2 generated",
        "2024-10-05 - Trasig: 1 clip, 1 failed",  # no sprite attempt for a failed proxy
    ):
        assert event_line in lines
    assert lines.index(_error_lines(out)[0]) < lines.index("2024-10-05 - Trasig: 1 clip, 1 failed")
    # 13 entries of 1000 bytes of proxy plus the facts file each
    # the facts as the proxy was published (before the sprite's record was added to them)
    facts_size = len((json.dumps(FACTS.to_json(), sort_keys=True, indent=2) + "\n").encode())
    written = 13 * (1000 + facts_size)
    sprites = 13 * 500
    assert lines[-1] == (
        f"proxies: 14 clips in 6 events: 13 generated ({written / 1000:.1f} kB), 0 cached, "
        f"1 failed; filmstrips: 13 generated ({sprites / 1000:.1f} kB), 0 cached, 0 failed "
        f"(cache: {cache_dir})"
    )
    assert len(list(cache_dir.glob("*/proxy.mp4"))) == 13
    assert len(list(cache_dir.glob("*/filmstrip.jpg"))) == 13


def test_proxies_request_every_clip_on_disk_and_nothing_else(
    library: Path, fake: FakeInstall
) -> None:
    seen = fake()
    main(["proxies", str(library)])

    identities = _identities(seen, library)
    assert identities == {
        f"{MIDSOMMAR}/s1710001.mp4",
        f"{OMOJLIGT}/s1710001.mp4",
        *(f"{GRILLNING}/s171000{n}.mp4" for n in range(1, 5)),
        f"{TJORN}/s1710001.mp4",
        f"{TJORN}/s1710004.mp4",  # IGNORED in reel.yaml, still on disk
        f"{TJORN}/Kvällen/s1710002.mp4",
        f"{TJORN}/Kvällen/s1710003.mp4",
        f"{TJORN}/Kvällen/s1710004.mp4",
        f"{SOMMARLOV}/s1710002.mp4",
        f"{SOMMARLOV}/s1710004.mp4",
        f"{TRASIG}/trasig.mp4",
    }
    assert not any("borttagen" in i or "original" in i or "Verona" in i for i in identities)


def test_a_second_run_encodes_only_the_clip_that_failed(
    library: Path, cache_dir: Path, fake: FakeInstall, capsys: pytest.CaptureFixture[str]
) -> None:
    fake()
    main(["proxies", str(library)])
    capsys.readouterr()

    seen = fake()
    assert main(["proxies", str(library)]) == 1

    out = capsys.readouterr().out
    assert _identities(seen, library) == {f"{TRASIG}/trasig.mp4"}
    assert (
        "2024-06-27 - Grillning med grannar: 4 clips, 4 cached; filmstrips: 4 cached"
    ) in out.splitlines()
    assert out.splitlines()[-1].startswith(
        "proxies: 14 clips in 6 events: 0 generated (0 B), 13 cached, 1 failed; "
        "filmstrips: 0 generated (0 B), 13 cached, 0 failed"
    )
    assert seen.films == []  # every sprite was recorded: not one made again
    assert len(_error_lines(out)) == 1


def test_a_multi_line_reason_is_one_output_line_and_the_rest_is_logged(
    library: Path,
    fake: FakeInstall,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    fake()
    trasig = library / TRASIG / "trasig.mp4"
    reason = (
        "ffmpeg failed on the cpu path: Command exited 234: /usr/bin/ffmpeg "
        f"-hide_banner -i {trasig} -map 0:v:0 /cache/.k.x.part/proxy.mp4\nstderr:\n"
        "[libx264 @ 0x55d0] some warning\n"
        "[out#0/mp4 @ 0x55d1] Error opening output: Invalid argument"
    )

    def failing(clip: Path, **kwargs: object) -> ProxyEntry:
        raise ProxyError(str(clip), reason)

    monkeypatch.setattr(proxies_cli, "ensure_proxy", failing)

    with caplog.at_level(logging.DEBUG, logger="auto_reel_ng.cli.proxies"):
        assert main(["proxies", str(library), "--years", "2024", "-v"]) == 1

    out = capsys.readouterr().out
    assert (
        "ERROR  2024-10-05 - Trasig/trasig.mp4: ffmpeg failed on the cpu path: "
        "Error opening output: Invalid argument"
    ) in out.splitlines()
    assert len(_error_lines(out)) == 13
    assert not [line for line in out.splitlines() if "Command exited" in line or "0x55" in line]
    assert str(trasig) not in out
    assert f"2024-10-05 - Trasig/trasig.mp4: {reason}" in caplog.messages


def test_a_non_utf8_file_name_is_printed_with_its_raw_bytes(
    tmp_path: Path, fake: FakeInstall, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "latin"
    _write(root / TRASIG / os.fsdecode(b"tom\xe9.mp4"))  # zero bytes
    fake()

    assert main(["proxies", str(root)]) == 1

    assert _error_lines(capsys.readouterr().out) == [
        "ERROR  2024-10-05 - Trasig/tom\\xe9.mp4: File is empty (zero bytes)"
    ]


def test_the_library_is_left_untouched(library: Path, fake: FakeInstall) -> None:
    fake()
    before = _snapshot(library)
    main(["proxies", str(library)])
    assert _snapshot(library) == before


def test_a_clip_that_vanishes_before_its_stat_is_one_failure(
    library: Path,
    fake: FakeInstall,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    seen = fake()
    vanished = library / GRILLNING / "s1710003.mp4"

    def flaky_key(clip: Path) -> str:
        if clip == vanished:
            raise FileNotFoundError(2, "No such file or directory", str(clip))
        return proxies_key(clip)

    proxies_key = proxies_cli.proxy_key
    monkeypatch.setattr(proxies_cli, "proxy_key", flaky_key)

    assert main(["proxies", str(library)]) == 1

    out = capsys.readouterr().out
    assert (
        "ERROR  2024-06-27 - Grillning med grannar/s1710003.mp4: cannot stat the clip: "
        "No such file or directory"
    ) in _error_lines(out)
    assert (
        "2024-06-27 - Grillning med grannar: 4 clips, 3 generated, 1 failed; "
        "filmstrips: 3 generated"
    ) in out
    assert f"{SOMMARLOV}/s1710002.mp4" in _identities(seen, library)  # the run continued


def test_two_links_to_one_clip_are_encoded_once_and_counted_once(
    tmp_path: Path, cache_dir: Path, fake: FakeInstall, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "linked"
    clip = tmp_path / "clips" / "s1710004.mp4"
    _write(clip, b"one clip")
    event = root / KRAFTSKIVA
    event.mkdir(parents=True)
    for name in ("a.mp4", "b.mp4"):
        (event / name).symlink_to(clip)
    seen = fake()

    assert main(["proxies", str(root)]) == 0

    out = capsys.readouterr().out
    assert [c.name for c in seen.clips] == ["a.mp4"]  # the first of them in listing order
    assert [c.name for c in seen.films] == ["a.mp4"]  # one sprite for the one entry
    assert (
        "2024-09-14 - Kräftskiva: 2 clips, 1 generated, 1 cached; "
        "filmstrips: 1 generated, 1 cached"
    ) in out.splitlines()
    assert "2 clips in 1 event: 1 generated (1.3 kB), 1 cached, 0 failed" in out.splitlines()[-1]
    assert "filmstrips: 1 generated (500 B), 1 cached, 0 failed" in out.splitlines()[-1]
    assert len(list(cache_dir.glob("*/proxy.mp4"))) == 1

    seen = fake()
    assert main(["proxies", str(root)]) == 0
    assert seen.clips == [] and seen.films == []
    assert (
        "2024-09-14 - Kräftskiva: 2 clips, 2 cached; filmstrips: 2 cached"
    ) in capsys.readouterr().out.splitlines()


def test_a_clip_another_process_finished_first_is_cached_not_failed(
    library: Path,
    fake: FakeInstall,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake()
    real = proxies_cli.ensure_proxy

    def lost_the_race(clip: Path, **kwargs: Any) -> ProxyEntry:
        entry = real(clip, **kwargs)
        return ProxyEntry(  # the service renamed its build first: ours was discarded
            entry.key, entry.directory, entry.proxy_path, entry.facts_path, entry.facts, False
        )

    monkeypatch.setattr(proxies_cli, "ensure_proxy", lost_the_race)

    assert main(["proxies", str(library), "--years", "2024"]) == 1  # only trasig fails

    out = capsys.readouterr().out
    assert (
        "2024-06-27 - Grillning med grannar: 4 clips, 4 cached; filmstrips: 4 generated"
    ) in out.splitlines()
    assert "0 generated (0 B)" in out.splitlines()[-1] and "1 failed" in out.splitlines()[-1]


def test_two_links_to_a_broken_clip_fail_as_two_clips_from_one_attempt(
    tmp_path: Path, fake: FakeInstall, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "linked"
    clip = tmp_path / "clips" / "trasig.mp4"
    _write(clip)  # zero bytes
    event = root / KRAFTSKIVA
    event.mkdir(parents=True)
    for name in ("a.mp4", "b.mp4"):
        (event / name).symlink_to(clip)
    seen = fake()

    assert main(["proxies", str(root)]) == 1

    out = capsys.readouterr().out
    assert len(seen.clips) == 1  # one attempt for the one entry
    assert _error_lines(out) == [
        "ERROR  2024-09-14 - Kräftskiva/a.mp4: File is empty (zero bytes)",
        "ERROR  2024-09-14 - Kräftskiva/b.mp4: File is empty (zero bytes)",
    ]
    assert "2024-09-14 - Kräftskiva: 2 clips, 2 failed" in out.splitlines()


def test_an_unreadable_event_folder_is_reported_and_the_run_continues(
    library: Path,
    fake: FakeInstall,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    seen = fake()
    unreadable = library / GRILLNING
    real_scan_event = proxies_cli.scan_event

    def flaky_scan_event(event_dir: Path):  # type: ignore[no-untyped-def]
        if event_dir == unreadable:
            raise PermissionError(13, "Permission denied", str(event_dir))
        return real_scan_event(event_dir)

    monkeypatch.setattr(proxies_cli, "scan_event", flaky_scan_event)

    assert main(["proxies", str(library)]) == 1

    out = capsys.readouterr().out
    assert (
        "ERROR  2024-06-27 - Grillning med grannar: cannot list event folder: Permission denied"
    ) in out.splitlines()
    assert f"{SOMMARLOV}/s1710002.mp4" in _identities(seen, library)
    assert "1 event unreadable" in out.splitlines()[-1]


def test_no_events_is_not_an_error_and_starts_no_ffmpeg(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fake: FakeInstall,
    capsys: pytest.CaptureFixture[str],
) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    seen = fake()

    assert main(["proxies", str(empty)]) == 0

    assert "No events found under" in capsys.readouterr().out
    assert seen.clips == [] and seen.runtimes == 0


# --------------------------------------------------------------------------- #
# the filmstrip step
# --------------------------------------------------------------------------- #


def _fails(*names: str, error: Optional[BaseException] = None):  # type: ignore[no-untyped-def]
    """A ``film_fails`` hook that fails the clips called ``names`` with ``error``."""

    def hook(clip: Path) -> Optional[BaseException]:
        if clip.name not in names:
            return None
        return error or FilmstripError(str(clip), "ffmpeg could not cut the filmstrip")

    return hook


def test_a_failing_filmstrip_is_one_error_line_and_the_proxy_still_counts(
    library: Path, cache_dir: Path, fake: FakeInstall, capsys: pytest.CaptureFixture[str]
) -> None:
    seen = fake(film_fails=_fails("s1710002.mp4"))

    assert main(["proxies", str(library), "--years", "2024"]) == 1

    out = capsys.readouterr().out
    lines = out.splitlines()
    sprite_errors = [l for l in _error_lines(out) if "filmstrip" in l]
    # s1710002.mp4 is in three events: Grillning, Tjörn/Kvällen and Sommarlov
    assert sprite_errors == [
        "ERROR  2024-06-27 - Grillning med grannar/s1710002.mp4: ffmpeg could not cut the filmstrip",
        "ERROR  2024-08-20 - Två kapitel - Tjörn/Kvällen/s1710002.mp4: "
        "ffmpeg could not cut the filmstrip",
        "ERROR  2024-09-01 - Sommarlov/s1710002.mp4: ffmpeg could not cut the filmstrip",
    ]
    # the proxy is still generated and counted; only the sprite figure shows the failure
    assert (
        "2024-06-27 - Grillning med grannar: 4 clips, 4 generated; filmstrips: 3 generated, 1 failed"
    ) in lines
    assert lines[-1].count("failed") == 2 and "1 failed" in lines[-1].split("filmstrips:")[0]
    assert "3 failed" in lines[-1].split("filmstrips:")[1]
    assert (cache_dir / proxies_cli.proxy_key(library / GRILLNING / "s1710002.mp4")).is_dir()
    # the next event was processed
    assert any(l.startswith("2024-09-01 - Sommarlov: 2 clips, 2 generated;") for l in lines)


def test_a_failed_proxy_gets_no_filmstrip_attempt_and_no_filmstrip_count(
    library: Path, fake: FakeInstall, capsys: pytest.CaptureFixture[str]
) -> None:
    seen = fake()

    assert main(["proxies", str(library)]) == 1

    out = capsys.readouterr().out
    assert "trasig.mp4" not in {clip.name for clip in seen.films}
    assert len(seen.films) == len(seen.clips) - 1 == 13
    assert "2024-10-05 - Trasig: 1 clip, 1 failed" in out.splitlines()  # no filmstrips part
    assert len(_error_lines(out)) == 1


def test_a_proxy_without_a_filmstrip_gets_it_on_the_next_run_and_is_not_encoded_again(
    library: Path, cache_dir: Path, fake: FakeInstall, capsys: pytest.CaptureFixture[str]
) -> None:
    fake(film_fails=lambda clip: FilmstripError(str(clip), "the disk was full"))
    assert main(["proxies", str(library), "--years", "2024"]) == 1
    capsys.readouterr()
    proxies = sorted(cache_dir.glob("*/proxy.mp4"))
    stamps = {p: p.stat().st_mtime_ns for p in proxies}
    assert proxies and not list(cache_dir.glob("*/filmstrip.jpg"))

    seen = fake()  # the space is freed
    assert main(["proxies", str(library), "--years", "2024"]) == 1  # only the broken clip
    out = capsys.readouterr().out

    assert {p.name for p in seen.clips} == {"trasig.mp4"}  # no proxy was requested again
    assert len(seen.films) == len(proxies)
    assert {p: p.stat().st_mtime_ns for p in proxies} == stamps
    assert (
        "2024-06-27 - Grillning med grannar: 4 clips, 4 cached; filmstrips: 4 generated"
    ) in out.splitlines()
    assert out.splitlines()[-1].count(" 0 failed") == 1  # the sprite figure; the proxy one is 1


def test_two_links_to_a_clip_whose_filmstrip_fails_are_two_failures_from_one_attempt(
    tmp_path: Path, fake: FakeInstall, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "linked"
    clip = tmp_path / "clips" / "s1710004.mp4"
    _write(clip, b"one clip")
    event = root / KRAFTSKIVA
    event.mkdir(parents=True)
    for name in ("a.mp4", "b.mp4"):
        (event / name).symlink_to(clip)
    seen = fake(film_fails=lambda c: FilmstripError(str(c), "keyframes too far apart"))

    assert main(["proxies", str(root)]) == 1

    out = capsys.readouterr().out
    assert len(seen.films) == 1
    assert _error_lines(out) == [
        "ERROR  2024-09-14 - Kräftskiva/a.mp4: keyframes too far apart",
        "ERROR  2024-09-14 - Kräftskiva/b.mp4: keyframes too far apart",
    ]
    assert "2024-09-14 - Kräftskiva: 2 clips, 1 generated, 1 cached; filmstrips: 2 failed" in out


def test_a_multi_line_filmstrip_reason_is_one_output_line(
    library: Path, fake: FakeInstall, capsys: pytest.CaptureFixture[str]
) -> None:
    reason = (
        "ffmpeg could not cut the filmstrip: Command exited 234: /usr/bin/ffmpeg -hide_banner "
        "-i /cache/k/proxy.mp4 -vf select=eq(n\\,0) /cache/.k.x.part/filmstrip.jpg\nstderr:\n"
        "[mjpeg @ 0x55d0] ff_frame_thread_encoder_init failed"
    )
    fake(film_fails=_fails("s1710001.mp4", error=FilmstripError("x", reason)))

    main(["proxies", str(library), "--years", "2023"])

    out = capsys.readouterr().out
    assert _error_lines(out) == [
        "ERROR  2023-06-23 - Midsommar - Dalarna/s1710001.mp4: ffmpeg could not cut the filmstrip: "
        "ff_frame_thread_encoder_init failed"
    ]
    assert "Command exited" not in out and "0x55" not in out


def test_a_cache_error_in_the_filmstrip_step_stops_the_run_with_one_error(
    library: Path, tmp_path: Path, fake: FakeInstall, capsys: pytest.CaptureFixture[str]
) -> None:
    cache = tmp_path / "xdg" / "auto-reel" / "proxies"
    fake(film_fails=lambda c: ProxyCacheError(f"{cache}: cannot write proxies: No space left"))

    assert main(["proxies", str(library)]) == 1

    captured = capsys.readouterr()
    errors = [l for l in captured.err.splitlines() if l.startswith("error:")]
    assert errors == [f"error: {cache}: cannot write proxies: No space left"]
    assert _error_lines(captured.out) == []


def test_an_interrupt_during_the_filmstrip_cancels_the_queue(
    library: Path, fake: FakeInstall, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake(film_fails=lambda clip: KeyboardInterrupt())
    monkeypatch.setattr(_RecordingExecutor, "shutdowns", [])
    monkeypatch.setattr(proxies_cli, "ThreadPoolExecutor", _RecordingExecutor)

    with pytest.raises(KeyboardInterrupt):
        main(["proxies", str(library)])

    assert _RecordingExecutor.shutdowns[0]["cancel_futures"] is True


def test_a_cancel_between_the_proxy_and_the_filmstrip_starts_no_sprite(
    library: Path,
    fake: FakeInstall,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    seen = fake()
    real = proxies_cli.ensure_proxy

    def cancelled_meanwhile(clip: Path, **kwargs: Any) -> ProxyEntry:
        entry = real(clip, **kwargs)
        kwargs["should_cancel"].__self__.set()  # the interrupt arrives as the proxy finishes
        return entry

    monkeypatch.setattr(proxies_cli, "ensure_proxy", cancelled_meanwhile)

    assert main(["proxies", str(library)]) == 1

    assert seen.films == []
    assert "interrupted before the filmstrip was made" in capsys.readouterr().err


# --------------------------------------------------------------------------- #
# arguments, settings, and errors that stop the run
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("value", ["0", "-1", "two"])
def test_a_bad_job_count_is_a_usage_error(library: Path, fake: FakeInstall, value: str) -> None:
    seen = fake()
    with pytest.raises(SystemExit) as exc:
        main(["proxies", str(library), "--jobs", value])
    assert exc.value.code == 2
    assert seen.clips == []


def test_a_proxy_cache_inside_the_library_stops_the_run_before_any_ffmpeg(
    library: Path, fake: FakeInstall, capsys: pytest.CaptureFixture[str]
) -> None:
    (library / "config.yaml").write_text("proxies:\n  cache_dir: proxies\n", encoding="utf-8")
    seen = fake()

    assert main(["proxies", str(library)]) == 1

    assert "error: proxies.cache_dir" in capsys.readouterr().err
    assert seen.clips == [] and seen.runtimes == 0


def test_an_unwritable_cache_stops_the_run_with_one_error(
    library: Path, tmp_path: Path, fake: FakeInstall, capsys: pytest.CaptureFixture[str]
) -> None:
    cache = tmp_path / "read-only" / "proxies"
    fake(error=ProxyCacheError(f"{cache}: cannot write proxies: [Errno 30] Read-only"))

    assert main(["proxies", str(library)]) == 1

    captured = capsys.readouterr()
    errors = [line for line in captured.err.splitlines() if line.startswith("error:")]
    assert errors == [f"error: {cache}: cannot write proxies: [Errno 30] Read-only"]
    assert _error_lines(captured.out) == []


def test_an_unreadable_cache_stops_the_run_with_one_error(
    library: Path,
    cache_dir: Path,
    fake: FakeInstall,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    seen = fake()
    real_is_file = Path.is_file

    def is_file(self: Path) -> bool:  # Python 3.13 raises on an unsearchable directory
        if cache_dir in self.parents:
            raise PermissionError(13, "Permission denied", str(self))
        return real_is_file(self)

    monkeypatch.setattr(Path, "is_file", is_file)

    assert main(["proxies", str(library)]) == 1

    captured = capsys.readouterr()
    errors = [line for line in captured.err.splitlines() if line.startswith("error:")]
    assert len(errors) == 1 and errors[0].startswith(f"error: {cache_dir}: cannot read proxies")
    assert _error_lines(captured.out) == []
    assert seen.clips == []


def test_an_unsatisfiable_device_override_stops_before_any_encode(
    library: Path, fake: FakeInstall, capsys: pytest.CaptureFixture[str]
) -> None:
    seen = fake(select_error=AccelError("No usable nvidia accelerator"))

    assert main(["proxies", str(library), "--device", "nvidia"]) == 1

    captured = capsys.readouterr()
    assert [l for l in captured.err.splitlines() if l.startswith("error:")] == [
        "error: No usable nvidia accelerator"
    ]
    assert seen.overrides == ["nvidia"]
    assert seen.clips == []
    assert _error_lines(captured.out) == []


def test_the_profile_is_selected_once_and_handed_to_every_encode(
    library: Path, fake: FakeInstall
) -> None:
    seen = fake()
    main(["proxies", str(library), "--device", "cpu"])
    assert seen.overrides == ["cpu"]
    assert len({id(p) for p in seen.profiles}) == 1 and len(seen.profiles) == len(seen.clips) == 14


class _RecordingExecutor(ThreadPoolExecutor):
    """A real pool that records its ``max_workers`` and every ``shutdown`` call's arguments."""

    shutdowns: List[Dict[str, bool]] = []
    created_with: List[Optional[int]] = []

    def __init__(self, max_workers: Optional[int] = None, **kwargs: object) -> None:
        type(self).created_with.append(max_workers)
        super().__init__(max_workers, **kwargs)  # type: ignore[arg-type]

    def shutdown(self, wait: bool = True, *, cancel_futures: bool = False) -> None:
        type(self).shutdowns.append({"wait": wait, "cancel_futures": cancel_futures})
        super().shutdown(wait=wait, cancel_futures=cancel_futures)


@pytest.mark.parametrize(("argv", "workers"), [([], 1), (["--jobs", "3"], 3)])
def test_jobs_bounds_the_one_shared_pool(
    library: Path,
    fake: FakeInstall,
    monkeypatch: pytest.MonkeyPatch,
    argv: List[str],
    workers: int,
) -> None:
    fake()
    monkeypatch.setattr(_RecordingExecutor, "created_with", [])
    monkeypatch.setattr(proxies_cli, "ThreadPoolExecutor", _RecordingExecutor)

    main(["proxies", str(library), *argv])

    assert _RecordingExecutor.created_with == [workers]


def test_an_interrupt_sets_the_shared_cancel_flag_and_cancels_the_queue(
    library: Path, fake: FakeInstall, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen = fake(error=KeyboardInterrupt())
    monkeypatch.setattr(_RecordingExecutor, "shutdowns", [])
    monkeypatch.setattr(proxies_cli, "ThreadPoolExecutor", _RecordingExecutor)

    with pytest.raises(KeyboardInterrupt):
        main(["proxies", str(library)])

    assert _RecordingExecutor.shutdowns
    assert _RecordingExecutor.shutdowns[0]["cancel_futures"] is True
    assert seen.cancels and all(cancel() is True for cancel in seen.cancels)
    assert len({id(cancel.__self__) for cancel in seen.cancels}) == 1  # type: ignore[attr-defined]


def test_the_cancel_flag_is_clear_during_a_normal_run(library: Path, fake: FakeInstall) -> None:
    seen = fake()
    main(["proxies", str(library)])
    assert seen.cancels and not any(cancel() for cancel in seen.cancels)


def test_sizes_are_short_decimal_units() -> None:
    assert proxies_cli._size(0) == "0 B"  # pylint: disable=protected-access
    assert proxies_cli._size(999) == "999 B"  # pylint: disable=protected-access
    assert proxies_cli._size(1500) == "1.5 kB"  # pylint: disable=protected-access
    assert proxies_cli._size(3_400_000) == "3.4 MB"  # pylint: disable=protected-access
    assert proxies_cli._size(40_000_000_000) == "40.0 GB"  # pylint: disable=protected-access
    assert proxies_cli._size(40_000_000_000_000) == "40000.0 GB"  # pylint: disable=protected-access


# --------------------------------------------------------------------------- #
# end to end: the real encode over a read-only library
# --------------------------------------------------------------------------- #


@pytest.mark.has_ffmpeg
def test_proxies_end_to_end_over_a_read_only_library(
    tmp_path: Path,
    make_clip,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cache_dir = tmp_path / "xdg" / "auto-reel" / "proxies"
    (tmp_path / "clips").mkdir()
    first = make_clip("clips/s1710001.mp4", width=1920, height=1080, duration=1.5)
    second = make_clip("clips/s1710002.mp4", width=1920, height=1080, duration=1.5)
    broken = tmp_path / "clips" / "trasig.mp4"
    broken.write_bytes(b"")

    root = tmp_path / "library"
    links = {
        root / GRILLNING / "s1710001.mp4": first,
        root / GRILLNING / "s1710002.mp4": second,
        root / TJORN / "Kvällen" / "grillen, del 1.mp4": first,  # the same clip, second event
        root / TRASIG / "trasig.mp4": broken,
    }
    for link, target in links.items():
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(target)

    directories = [Path(d) for d, _dirs, _files in os.walk(root)]
    modes = {d: d.stat().st_mode for d in directories}
    for directory in directories:  # like the MOL drive mounted read-only
        directory.chmod(modes[directory] & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
    try:
        before = _snapshot(root)

        assert main(["proxies", str(root), "--device", "cpu"]) == 1
        out = capsys.readouterr().out
        assert _error_lines(out) == [
            "ERROR  2024-10-05 - Trasig/trasig.mp4: File is empty (zero bytes)"
        ]
        assert (
            "2024-08-20 - Två kapitel - Tjörn: 1 clip, 1 cached; filmstrips: 1 cached"
        ) in out.splitlines()
        entries = sorted(p for p in cache_dir.iterdir() if not p.name.startswith("."))
        assert len(entries) == 2  # one per distinct clip
        for entry in entries:
            assert sorted(p.name for p in entry.iterdir()) == [
                "facts.json",
                "filmstrip.jpg",
                "proxy.mp4",
            ]
        assert list(cache_dir.glob(".*.part")) == []

        assert main(["proxies", str(root), "--device", "cpu"]) == 1
        out = capsys.readouterr().out
        assert (
            "proxies: 4 clips in 3 events: 0 generated (0 B), 3 cached, 1 failed; "
            "filmstrips: 0 generated (0 B), 3 cached, 0 failed"
        ) in out
        assert _snapshot(root) == before
    finally:
        for directory in reversed(directories):
            directory.chmod(modes[directory])


def _records(cache_dir: Path) -> Dict[str, Dict[str, Any]]:
    """Every complete entry's ``filmstrip`` record by entry key."""
    found: Dict[str, Dict[str, Any]] = {}
    for facts in sorted(cache_dir.glob("*/facts.json")):
        document = json.loads(facts.read_text(encoding="utf-8"))
        found[facts.parent.name] = document["filmstrip"]
    return found


def _jpeg_size(runtime: Any, path: Path) -> tuple[int, int]:
    out = runtime.run_ffprobe(
        ["-v", "error", "-show_entries", "stream=width,height", "-of", "csv=p=0", str(path)]
    ).stdout
    width, height = out.strip().split(",")
    return int(width), int(height)


@pytest.mark.has_ffmpeg
def test_proxies_make_every_filmstrip_including_the_sub_second_clip_and_repeat_nothing(
    tmp_path: Path,
    make_clip,
    runtime,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cache_dir = tmp_path / "xdg" / "auto-reel" / "proxies"
    (tmp_path / "clips").mkdir()
    short = make_clip("clips/C0047.MP4", width=640, height=360, fps=25, duration=0.48)
    normal = make_clip("clips/C0048.MP4", width=640, height=360, fps=25, duration=3.0)
    event = tmp_path / "library" / "2020" / "2020-07-24 - M-A 80 år - Kungälv"
    event.mkdir(parents=True)
    (event / "C0047.MP4").symlink_to(short)
    (event / "C0048.MP4").symlink_to(normal)

    assert main(["proxies", str(tmp_path / "library"), "--device", "cpu"]) == 0
    out = capsys.readouterr().out
    assert "2 clips, 2 generated; filmstrips: 2 generated" in out
    assert "filmstrips: 2 generated" in out.splitlines()[-1] and "0 failed" in out.splitlines()[-1]
    records = _records(cache_dir)
    assert sorted(r["tiles"] for r in records.values()) == [1, 3]  # the 0.48 s clip is one tile
    for key, record in records.items():
        jpeg = cache_dir / key / "filmstrip.jpg"
        assert (record["width"], record["height"]) == _jpeg_size(runtime, jpeg)
        assert record["bytes"] == jpeg.stat().st_size

    # a second run starts neither ffprobe nor ffmpeg for any entry
    touched: List[List[str]] = []
    for method in ("run", "run_ffprobe", "run_with_progress"):
        original = getattr(proxies_cli.FfmpegRuntime, method)

        def spy(self: Any, args: Any, *a: Any, _o: Any = original, **kw: Any) -> Any:
            touched.append([str(x) for x in args])
            return _o(self, args, *a, **kw)

        monkeypatch.setattr(proxies_cli.FfmpegRuntime, method, spy)
    assert main(["proxies", str(tmp_path / "library"), "--device", "cpu"]) == 0
    assert "2 clips, 2 cached; filmstrips: 2 cached" in capsys.readouterr().out
    assert [args for args in touched if any(str(cache_dir) in a for a in args)] == []

    # an entry from before sprites existed gets its sprite, and its proxy is not rewritten
    key = next(iter(records))
    stamp = (cache_dir / key / "proxy.mp4").stat().st_mtime_ns
    (cache_dir / key / "filmstrip.jpg").unlink()
    facts_path = cache_dir / key / "facts.json"
    document = json.loads(facts_path.read_text(encoding="utf-8"))
    del document["filmstrip"]
    facts_path.write_text(json.dumps(document), encoding="utf-8")
    assert main(["proxies", str(tmp_path / "library"), "--device", "cpu"]) == 0
    out = capsys.readouterr().out
    assert "2 clips, 2 cached; filmstrips: 1 generated, 1 cached" in out
    assert (cache_dir / key / "proxy.mp4").stat().st_mtime_ns == stamp
    assert _records(cache_dir)[key] == records[key]


SAMPLES = Path(__file__).resolve().parents[2] / "auto-reel-media" / "samples"
DOGFOOD = (
    "legacy-render-mpeg4-mp3.mp4",  # the legacy MPEG-4 render
    "hevc-mov-rotate90-aac.mov",  # rotated HEVC
    "sony-xavc-1080p25-pcm.mp4",  # Sony with PCM audio
    "h264-portrait-1080x1920-aac.mp4",
)


@pytest.mark.has_ffmpeg
def test_the_sample_clips_all_get_a_filmstrip_whose_record_matches_the_image(
    tmp_path: Path, runtime, capsys: pytest.CaptureFixture[str]
) -> None:
    missing = [name for name in DOGFOOD if not (SAMPLES / name).is_file()]
    if missing:
        pytest.skip(f"samples not present: {missing}")
    event = tmp_path / "library" / "2025" / "2025-01-01 - Samples"
    event.mkdir(parents=True)
    for name in DOGFOOD:  # symlinks: the shared fixture is never copied or written
        (event / name).symlink_to(SAMPLES / name)
    cache_dir = tmp_path / "xdg" / "auto-reel" / "proxies"

    assert main(["proxies", str(tmp_path / "library"), "--device", "cpu"]) == 0

    out = capsys.readouterr().out
    assert (
        f"{len(DOGFOOD)} clips, {len(DOGFOOD)} generated; filmstrips: {len(DOGFOOD)} generated"
        in out
    )
    records = _records(cache_dir)
    assert len(records) == len(DOGFOOD)
    shapes = set()
    for key, record in records.items():
        jpeg = cache_dir / key / "filmstrip.jpg"
        assert (record["width"], record["height"]) == _jpeg_size(runtime, jpeg)
        assert record["width"] == record["columns"] * record["tile_width"]
        assert record["height"] == record["rows"] * record["tile_height"]
        assert record["tile_height"] == 90 and record["tiles"] <= 120 and record["bytes"] > 0
        shapes.add(record["tile_width"])
    assert shapes == {160, 50}  # landscape and the two portrait (rotated) sources
