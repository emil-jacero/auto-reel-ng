"""``read_proxy_state`` (clip-proxies, "A clip's proxy state is read from its cache entry").

Hand-built cache trees, one damage at a time; a real ``ensure_proxy`` round trip at the end
(``has_ffmpeg``) so the writer and the reader cannot drift apart unseen.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Callable, Dict

import pytest
from proxy_cache_trees import SPRITE, filmstrip_record, sony_facts, tree, write_entry, write_marker

from auto_reel_ng.errors import ProxyCacheError, ProxyError
from auto_reel_ng.proxies import (
    PROXY_VERSION,
    ProxySettings,
    ProxyStatus,
    proxy_key,
    read_proxy_state,
)
from auto_reel_ng.proxies import spec as spec_module


@pytest.fixture
def clip(tmp_path: Path) -> Path:
    path = tmp_path / "lib" / "C0047.MP4"
    path.parent.mkdir()
    path.write_bytes(b"source clip bytes")
    os.utime(path, ns=(1_700_000_000_000_000_000,) * 2)
    return path


@pytest.fixture
def cache(tmp_path: Path) -> Path:
    return tmp_path / "xdg" / "auto-reel" / "proxies"


def state(clip: Path, cache: Path) -> Any:
    return read_proxy_state(clip, settings=ProxySettings(cache))


# --------------------------------------------------------------------------- #
# the four states
# --------------------------------------------------------------------------- #


def test_a_complete_entry_is_ready_with_the_facts_as_recorded(clip: Path, cache: Path) -> None:
    entry = write_entry(cache, clip)

    reading = state(clip, cache)

    assert reading.status is ProxyStatus.READY
    assert reading.proxy_path == entry / "proxy.mp4"
    assert reading.reason is None
    facts = reading.facts
    assert (facts.duration, facts.fps_num, facts.fps_den, facts.vfr) == (24.96, 25, 1, False)
    assert (facts.width, facts.height, facts.rotation) == (960, 540, None)
    assert facts.audio_codec == "pcm_s16be"
    film = reading.filmstrip
    assert (film.tile_width, film.tile_height, film.columns, film.tiles, film.interval) == (
        160,
        90,
        10,
        25,
        1,
    )


def test_a_clip_with_nothing_cached_is_absent_and_the_cache_is_not_created(
    clip: Path, cache: Path
) -> None:
    assert state(clip, cache).status is ProxyStatus.ABSENT
    assert not cache.exists()  # a read creates nothing, not even the cache directory


def test_an_empty_entry_directory_is_absent(clip: Path, cache: Path) -> None:
    (cache / proxy_key(clip)).mkdir(parents=True)
    assert state(clip, cache).status is ProxyStatus.ABSENT


def test_a_proxy_awaiting_its_filmstrip_is_absent_not_stale(clip: Path, cache: Path) -> None:
    write_entry(cache, clip, with_filmstrip=False, sprite=None)
    assert state(clip, cache).status is ProxyStatus.ABSENT


def test_a_filmstrip_record_whose_image_is_gone_is_absent(clip: Path, cache: Path) -> None:
    write_entry(cache, clip, sprite=None)
    assert state(clip, cache).status is ProxyStatus.ABSENT


def test_an_image_without_its_record_is_absent(clip: Path, cache: Path) -> None:
    """A killed run between the image and the record: the filmstrip counts as absent."""
    write_entry(cache, clip, with_filmstrip=False)
    assert state(clip, cache).status is ProxyStatus.ABSENT


@pytest.mark.parametrize("missing", ["proxy", "facts"])
def test_an_entry_lacking_a_file_is_absent(clip: Path, cache: Path, missing: str) -> None:
    entry = write_entry(cache, clip)
    (entry / ("proxy.mp4" if missing == "proxy" else "facts.json")).unlink()
    assert state(clip, cache).status is ProxyStatus.ABSENT


def _drop(member: str) -> Callable[[Dict[str, Any]], None]:
    return lambda document: document.pop(member)


def _set(member: str, value: object) -> Callable[[Dict[str, Any]], None]:
    return lambda document: document.__setitem__(member, value)


def _film(**changes: object) -> Callable[[Dict[str, Any]], None]:
    return lambda document: document["filmstrip"].update(changes)


DAMAGED_FACTS = {
    "missing-duration": _drop("duration"),
    "zero-duration": _set("duration", 0),
    "negative-duration": _set("duration", -1.5),
    "string-duration": _set("duration", "24.96"),
    "bool-duration": _set("duration", True),
    "infinite-duration": _set("duration", float("inf")),
    "missing-fps": _drop("fps"),
    "bool-fps-num": _set("fps", {"num": True, "den": 1}),
    "zero-fps-den": _set("fps", {"num": 25, "den": 0}),
    "float-width": _set("width", 960.0),
    "negative-width": _set("width", -960),
    "zero-height": _set("height", 0),
    "string-vfr": _set("vfr", "no"),
    "rotation-360": _set("rotation", 360),
    "rotation-negative": _set("rotation", -90),
    "rotation-string": _set("rotation", "90"),
    "numeric-audio-codec": _set("audio_codec", 7),
    "other-proxy-version": _set("proxy_version", PROXY_VERSION + 1),
    "malformed-filmstrip": _set("filmstrip", "tiles"),
    "filmstrip-missing-tiles": lambda document: document["filmstrip"].pop("tiles"),
    "filmstrip-zero-columns": _film(columns=0),
    "filmstrip-bool-interval": _film(interval=True),
    "filmstrip-float-tile": _film(tile_width=160.5),
    "filmstrip-other-format": _film(version=99),
    "filmstrip-bytes-do-not-match": _film(bytes=41200),
}


@pytest.mark.parametrize("damage", sorted(DAMAGED_FACTS))
def test_an_entry_with_damaged_facts_is_stale_and_nothing_is_written(
    clip: Path, cache: Path, damage: str
) -> None:
    write_entry(cache, clip, document=DAMAGED_FACTS[damage])
    before = tree(cache)

    reading = state(clip, cache)

    assert reading.status is ProxyStatus.STALE
    assert reading.facts is None and reading.filmstrip is None and reading.reason is None
    assert tree(cache) == before


@pytest.mark.parametrize(
    "text",
    ['{"proxy_version": 1, "duration": 24.', "[]", "null", "", "�\x00"],
    ids=["truncated", "array", "null", "empty", "garbage"],
)
def test_unusable_facts_text_is_stale(clip: Path, cache: Path, text: str) -> None:
    write_entry(cache, clip, facts_text=text)
    assert state(clip, cache).status is ProxyStatus.STALE


def test_facts_that_are_not_text_are_stale(clip: Path, cache: Path) -> None:
    entry = write_entry(cache, clip)
    (entry / "facts.json").write_bytes(b"\xff\xfe\x00 not utf-8")
    assert state(clip, cache).status is ProxyStatus.STALE


def test_facts_that_are_a_directory_are_stale(clip: Path, cache: Path) -> None:
    entry = write_entry(cache, clip)
    (entry / "facts.json").unlink()
    (entry / "facts.json").mkdir()
    assert state(clip, cache).status is ProxyStatus.STALE


@pytest.mark.parametrize("which", ["proxy.mp4", "filmstrip.jpg"])
def test_an_empty_media_file_makes_the_entry_stale(clip: Path, cache: Path, which: str) -> None:
    entry = write_entry(cache, clip, document=_film(bytes=1) if which == "filmstrip.jpg" else None)
    (entry / which).write_bytes(b"")
    assert state(clip, cache).status is ProxyStatus.STALE


def test_a_filmstrip_image_of_another_size_than_recorded_is_stale(clip: Path, cache: Path) -> None:
    write_entry(cache, clip, sprite=SPRITE + b"extra")
    assert state(clip, cache).status is ProxyStatus.STALE


def test_a_proxy_that_is_a_directory_is_stale(clip: Path, cache: Path) -> None:
    entry = write_entry(cache, clip)
    (entry / "proxy.mp4").unlink()
    (entry / "proxy.mp4").mkdir()
    assert state(clip, cache).status is ProxyStatus.STALE


def test_extra_unknown_facts_are_ignored(clip: Path, cache: Path) -> None:
    def extend(document: Dict[str, Any]) -> None:
        document.update(codec_notes="x", loudness={"lufs": -23})
        document["filmstrip"].update(extra=1)

    write_entry(cache, clip, document=extend)
    reading = state(clip, cache)
    assert reading.status is ProxyStatus.READY
    assert reading.facts.duration == 24.96


def test_facts_the_probe_could_not_give_are_null_not_damage(clip: Path, cache: Path) -> None:
    write_entry(cache, clip, facts=sony_facts(vfr=None, rotation=None, audio_codec=None))
    reading = state(clip, cache)
    assert reading.status is ProxyStatus.READY
    assert (reading.facts.vfr, reading.facts.rotation, reading.facts.audio_codec) == (
        None,
        None,
        None,
    )


def test_a_variable_frame_rate_keeps_its_two_integers(clip: Path, cache: Path) -> None:
    write_entry(cache, clip, facts=sony_facts(fps_num=30000, fps_den=1001, vfr=True))
    facts = state(clip, cache).facts
    assert (facts.fps_num, facts.fps_den, facts.vfr) == (30000, 1001, True)


def test_a_rotated_clip_keeps_its_rotation(clip: Path, cache: Path) -> None:
    write_entry(cache, clip, facts=sony_facts(rotation=90, width=540, height=960))
    facts = state(clip, cache).facts
    assert (facts.rotation, facts.width, facts.height) == (90, 540, 960)


# --------------------------------------------------------------------------- #
# the failure marker and the precedence
# --------------------------------------------------------------------------- #


def test_a_marker_alone_is_failed_with_its_cause(clip: Path, cache: Path) -> None:
    write_marker(cache, clip, {"reason": "Output has no audio stream"})
    reading = state(clip, cache)
    assert (reading.status, reading.reason) == (ProxyStatus.FAILED, "Output has no audio stream")
    assert reading.facts is None and reading.proxy_path is None


def test_a_complete_entry_outranks_a_marker(clip: Path, cache: Path) -> None:
    write_entry(cache, clip)
    write_marker(cache, clip, {"reason": "an older failure"})
    reading = state(clip, cache)
    assert reading.status is ProxyStatus.READY and reading.reason is None


def test_a_marker_outranks_damaged_facts(clip: Path, cache: Path) -> None:
    write_entry(cache, clip, facts_text="{not json")
    write_marker(cache, clip, {"reason": "the encode failed"})
    assert state(clip, cache).status is ProxyStatus.FAILED


def test_a_published_proxy_supersedes_an_older_marker(clip: Path, cache: Path) -> None:
    """The marker is about the proxy: once the proxy is made, a failure before it is history."""
    write_entry(cache, clip, with_filmstrip=False, sprite=None)
    write_marker(cache, clip, {"reason": "the encode failed"})
    assert state(clip, cache).status is ProxyStatus.ABSENT  # awaiting its filmstrip

    write_entry(cache.parent / "other", clip, document=_film(version=99))
    write_marker(cache.parent / "other", clip, {"reason": "the encode failed"})
    assert state(clip, cache.parent / "other").status is ProxyStatus.STALE


@pytest.mark.parametrize(
    "payload",
    ["{not json", "[]", {"reason": 3}, {"reason": ""}, {"reason": "   "}, {"cause": "x"}],
    ids=["invalid", "array", "number", "empty", "blank", "other-member"],
)
def test_a_damaged_marker_is_not_a_cause(clip: Path, cache: Path, payload: object) -> None:
    write_marker(cache, clip, payload)
    assert state(clip, cache).status is ProxyStatus.ABSENT


def test_a_damaged_marker_beside_damaged_facts_leaves_the_entry_stale(
    clip: Path, cache: Path
) -> None:
    write_entry(cache, clip, facts_text="{not json")
    write_marker(cache, clip, "{not json")
    assert state(clip, cache).status is ProxyStatus.STALE


def test_a_marker_with_a_path_is_read_without_it(clip: Path, cache: Path) -> None:
    """The file is data a person could edit: the reader strips a path again."""
    write_marker(cache, clip, {"reason": f"moov atom not found in {clip}"})
    reading = state(clip, cache)
    assert reading.status is ProxyStatus.FAILED
    assert str(clip.parent) not in (reading.reason or "")
    assert reading.reason == "moov atom not found in C0047.MP4"


def test_a_marker_is_not_a_file_of_the_entry_listing(clip: Path, cache: Path) -> None:
    """The marker sits beside the entry directory, so it never makes the entry look complete."""
    write_marker(cache, clip, {"reason": "x"})
    assert not (cache / proxy_key(clip)).exists()


# --------------------------------------------------------------------------- #
# the key moves with the file and the version
# --------------------------------------------------------------------------- #


def test_a_replaced_file_reads_absent_and_the_old_entry_is_untouched(
    clip: Path, cache: Path
) -> None:
    write_entry(cache, clip)
    write_marker(cache, clip, {"reason": "an older failure"})
    assert state(clip, cache).status is ProxyStatus.READY
    before = tree(cache)

    clip.write_bytes(b"replaced by a larger file")
    assert state(clip, cache).status is ProxyStatus.ABSENT
    os.utime(clip, ns=(1_000_000_000, 1_000_000_000))  # and a new mtime alone moves it too
    assert state(clip, cache).status is ProxyStatus.ABSENT
    assert tree(cache) == before


def test_a_version_bump_moves_every_clip_to_absent(
    clip: Path, cache: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_entry(cache, clip)
    before = tree(cache)

    monkeypatch.setattr(spec_module, "PROXY_VERSION", PROXY_VERSION + 1)

    assert state(clip, cache).status is ProxyStatus.ABSENT
    assert tree(cache) == before


def test_a_clip_that_cannot_be_statted_has_no_key(tmp_path: Path, cache: Path) -> None:
    with pytest.raises(ProxyError, match="cannot stat the clip"):
        state(tmp_path / "gone.mp4", cache)


def test_a_symlinked_clip_shares_its_targets_entry(clip: Path, cache: Path, tmp_path: Path) -> None:
    write_entry(cache, clip)
    link = tmp_path / "linked" / "C0047.MP4"
    link.parent.mkdir()
    link.symlink_to(clip)
    assert state(link, cache).status is ProxyStatus.READY


# --------------------------------------------------------------------------- #
# an unreadable cache is an error, not absence
# --------------------------------------------------------------------------- #


@pytest.mark.skipif(os.geteuid() == 0, reason="root searches any directory")
def test_an_unsearchable_entry_directory_raises_the_typed_error(clip: Path, cache: Path) -> None:
    entry = write_entry(cache, clip)
    entry.chmod(0o000)
    try:
        with pytest.raises(ProxyCacheError, match="cannot read proxies"):
            state(clip, cache)
    finally:
        entry.chmod(0o755)


@pytest.mark.skipif(os.geteuid() == 0, reason="root searches any directory")
def test_an_unsearchable_cache_directory_raises_the_typed_error(clip: Path, cache: Path) -> None:
    write_entry(cache, clip)
    cache.chmod(0o000)
    try:
        with pytest.raises(ProxyCacheError):
            state(clip, cache)
    finally:
        cache.chmod(0o755)


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads any file")
def test_an_unreadable_marker_raises_the_typed_error(clip: Path, cache: Path) -> None:
    marker = write_marker(cache, clip, {"reason": "x"})
    marker.chmod(0o000)
    try:
        with pytest.raises(ProxyCacheError, match="cannot read proxies"):
            state(clip, cache)
    finally:
        marker.chmod(0o644)


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads any file")
def test_an_unreadable_facts_file_raises_the_typed_error(clip: Path, cache: Path) -> None:
    entry = write_entry(cache, clip)
    (entry / "facts.json").chmod(0o000)
    try:
        with pytest.raises(ProxyCacheError, match="cannot read proxies"):
            state(clip, cache)
    finally:
        (entry / "facts.json").chmod(0o644)


def test_a_cache_path_through_a_file_is_absent(clip: Path, tmp_path: Path) -> None:
    """``NotADirectoryError`` means "not there", like a missing directory."""
    blocker = tmp_path / "blocker"
    blocker.write_text("a file where the cache directory should be")
    assert state(clip, blocker / "proxies").status is ProxyStatus.ABSENT


# --------------------------------------------------------------------------- #
# no process, no write
# --------------------------------------------------------------------------- #


def test_reading_runs_no_process_and_writes_nothing(
    clip: Path, cache: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_entry(cache, clip)
    write_marker(cache, clip, {"reason": "x"})
    other = clip.with_name("C0048.MP4")
    other.write_bytes(b"another")
    write_entry(cache, other, facts_text="{not json")
    before = tree(cache)

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("a process was started")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_shell", forbidden)
    monkeypatch.setattr(os, "system", forbidden)
    monkeypatch.setattr(os, "posix_spawn", forbidden)

    assert state(clip, cache).status is ProxyStatus.READY
    assert state(other, cache).status is ProxyStatus.STALE
    assert tree(cache) == before


def test_the_reader_does_not_list_the_cache_directory(
    clip: Path, cache: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_entry(cache, clip)

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("the cache directory was listed")

    monkeypatch.setattr(os, "scandir", forbidden)
    monkeypatch.setattr(os, "listdir", forbidden)
    monkeypatch.setattr(Path, "iterdir", forbidden)
    monkeypatch.setattr(Path, "glob", forbidden)
    monkeypatch.setattr(Path, "rglob", forbidden)

    assert state(clip, cache).status is ProxyStatus.READY


def test_the_facts_json_is_the_only_json_the_reader_parses_for_ready(
    clip: Path, cache: Path
) -> None:
    """Sanity: the recorded numbers come from the file, not from a probe or a default."""
    write_entry(cache, clip, facts=sony_facts(duration=3.5, frames=87))
    assert state(clip, cache).facts.duration == 3.5
    entry = cache / proxy_key(clip)
    assert json.loads((entry / "facts.json").read_text())["duration"] == 3.5
    assert filmstrip_record()["bytes"] == len(SPRITE)


# --------------------------------------------------------------------------- #
# writer and reader cannot drift apart unseen
# --------------------------------------------------------------------------- #


@pytest.mark.has_ffmpeg
def test_a_real_entry_reads_ready_with_the_facts_it_wrote(
    runtime: Any, make_clip: Callable[..., Path], cache: Path
) -> None:
    """``ensure_proxy`` then ``ensure_filmstrip`` on a synthesized clip: the reader says ready."""
    from auto_reel_ng.accel.profiles import CPUProfile
    from auto_reel_ng.proxies import ensure_filmstrip, ensure_proxy

    clip = make_clip("c.mp4", width=1920, height=1080, fps=25, duration=2.0)
    settings = ProxySettings(cache)
    assert read_proxy_state(clip, settings=settings).status is ProxyStatus.ABSENT

    entry = ensure_proxy(clip, settings=settings, runtime=runtime, profile=CPUProfile())
    assert read_proxy_state(clip, settings=settings).status is ProxyStatus.ABSENT  # no sprite yet
    film = ensure_filmstrip(clip, entry, runtime=runtime)
    reading = read_proxy_state(clip, settings=settings)

    assert reading.status is ProxyStatus.READY
    assert reading.proxy_path == entry.proxy_path
    assert reading.facts == entry.facts
    assert (reading.facts.width, reading.facts.height) == (960, 540)
    assert (reading.facts.fps_num, reading.facts.fps_den) == (25, 1)
    assert reading.facts.audio_codec is not None
    assert reading.filmstrip is not None
    assert (reading.filmstrip.tiles, reading.filmstrip.interval) == (film.tiles, film.interval)
    assert (reading.filmstrip.tile_width, reading.filmstrip.tile_height) == (160, 90)
