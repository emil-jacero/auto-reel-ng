"""Unit tests for clip thumbnails: the cache key, the golden ffmpeg arguments, and
``thumbnail_for``'s cache, failure and atomic-write behaviour (D-11).

No real ffmpeg runs here: a fake runtime records its argument lists and writes JPEG
bytes to the last argument (or raises), and ``thumbs.thumbnail.probe_media`` is
monkeypatched. The real extraction is covered by ``test_thumbs_ffmpeg.py``.
"""

from __future__ import annotations

import os
import subprocess
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Callable, List, Optional, Sequence

import pytest

from auto_reel_ng.errors import (
    FfmpegError,
    FfmpegTimeoutError,
    ProbeError,
    ThumbnailCacheError,
    ThumbnailError,
)
from auto_reel_ng.thumbs import (
    one_line_cause,
)
from auto_reel_ng.thumbs import thumbnail as thumbnail_module
from auto_reel_ng.thumbs import thumbnail_args, thumbnail_for, thumbnail_key, thumbnail_path

#: A stand-in for the bytes ffmpeg would write (SOI ... EOI).
FAKE_JPEG = b"\xff\xd8\xff\xe0" + b"fake-jpeg-payload" * 64 + b"\xff\xd9"


class FakeRuntime:
    """Records every ``run`` and writes ``FAKE_JPEG`` to the output path, or raises."""

    def __init__(
        self,
        *,
        error: Optional[BaseException] = None,
        payload: bytes = FAKE_JPEG,
        barrier: Optional[threading.Barrier] = None,
    ) -> None:
        self.calls: List[List[str]] = []
        self.timeouts: List[float] = []
        self._error = error
        self._payload = payload
        self._barrier = barrier
        self._lock = threading.Lock()

    def with_timeout(self, seconds: float) -> "FakeRuntime":
        self.timeouts.append(seconds)
        return self

    def run(self, args: Sequence[str]) -> subprocess.CompletedProcess[str]:
        with self._lock:
            self.calls.append(list(args))
        if self._barrier is not None:
            self._barrier.wait(timeout=10)
        if self._error is not None:
            raise self._error
        Path(args[-1]).write_bytes(self._payload)
        return subprocess.CompletedProcess(list(args), 0, "", "")


ProbeCalls = List[Path]


@pytest.fixture
def probe_calls(monkeypatch: pytest.MonkeyPatch) -> Callable[..., ProbeCalls]:
    """Install a fake ``probe_media`` reporting ``duration`` (or raising); returns its calls."""

    def install(duration: float = 61.44, error: Optional[Exception] = None) -> ProbeCalls:
        calls: ProbeCalls = []

        def fake_probe(path: Path, *, runtime: object = None) -> SimpleNamespace:
            calls.append(Path(path))
            if error is not None:
                raise error
            return SimpleNamespace(duration=duration)

        monkeypatch.setattr(thumbnail_module, "probe_media", fake_probe)
        return calls

    return install


def _clip(directory: Path, name: str = "s1710001.mp4", data: bytes = b"clip-bytes") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_bytes(data)
    return path


def _leftovers(cache_dir: Path) -> List[str]:
    return sorted(p.name for p in cache_dir.iterdir()) if cache_dir.exists() else []


# --------------------------------------------------------------------------- #
# 3.1 — the golden arguments, the key, the path
# --------------------------------------------------------------------------- #


def test_thumbnail_args_are_the_golden_list() -> None:
    args = thumbnail_args(Path("s1710001.mp4"), at=15.36, output=Path("/c/.k.x.tmp"))
    assert args == [
        "-hide_banner",
        "-nostdin",
        "-v",
        "error",
        "-ss",
        "15.360",
        "-i",
        "s1710001.mp4",
        "-map",
        "0:v:0",
        "-frames:v",
        "1",
        "-vf",
        "scale=trunc(iw*sar/2)*2:ih,scale=320:180:force_original_aspect_ratio=decrease,setsar=1",
        "-c:v",
        "mjpeg",
        "-q:v",
        "5",
        "-f",
        "image2",
        "-update",
        "1",
        "-y",
        "/c/.k.x.tmp",
    ]
    assert args.index("-ss") < args.index("-i")  # input seeking
    assert args.index("-update") < args.index("-y")
    assert not any("hwaccel" in arg for arg in args)


def test_the_key_is_stable_across_calls(tmp_path: Path) -> None:
    clip = _clip(tmp_path)
    assert thumbnail_key(clip, position=0.25) == thumbnail_key(clip, position=0.25)
    assert len(thumbnail_key(clip, position=0.25)) == 64


def test_the_key_changes_when_a_byte_is_appended(tmp_path: Path) -> None:
    clip = _clip(tmp_path)
    before = thumbnail_key(clip, position=0.25)
    stat = clip.stat()
    with clip.open("ab") as handle:
        handle.write(b"x")
    os.utime(clip, ns=(stat.st_atime_ns, stat.st_mtime_ns))  # only the size differs
    assert thumbnail_key(clip, position=0.25) != before


def test_the_key_changes_with_the_mtime(tmp_path: Path) -> None:
    clip = _clip(tmp_path)
    before = thumbnail_key(clip, position=0.25)
    stat = clip.stat()
    os.utime(clip, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000))
    assert thumbnail_key(clip, position=0.25) != before


def test_the_key_changes_with_the_position(tmp_path: Path) -> None:
    clip = _clip(tmp_path)
    assert thumbnail_key(clip, position=0.25) != thumbnail_key(clip, position=0.5)


def test_the_key_changes_with_the_thumbnail_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clip = _clip(tmp_path)
    before = thumbnail_key(clip, position=0.25)
    monkeypatch.setattr(
        thumbnail_module, "THUMBNAIL_VERSION", thumbnail_module.THUMBNAIL_VERSION + 1
    )
    assert thumbnail_key(clip, position=0.25) != before


def test_two_symlinks_to_one_file_share_a_key(tmp_path: Path) -> None:
    clip = _clip(tmp_path / "clips")
    first = tmp_path / "2024-06-27 - Grillning med grannar" / "s1710001.mp4"
    second = tmp_path / "2024-08-20 - Två kapitel - Tjörn" / "s1710001.mp4"
    for link in (first, second):
        link.parent.mkdir()
        link.symlink_to(clip)
    assert thumbnail_key(first, position=0.25) == thumbnail_key(second, position=0.25)


def test_a_missing_clip_raises_file_not_found_unchanged(tmp_path: Path) -> None:
    missing = tmp_path / "borttagen.mp4"
    with pytest.raises(FileNotFoundError):
        thumbnail_key(missing, position=0.25)
    with pytest.raises(FileNotFoundError):
        thumbnail_path(missing, position=0.25, cache_dir=tmp_path / "cache")


def test_thumbnail_path_creates_nothing(tmp_path: Path) -> None:
    clip = _clip(tmp_path)
    cache_dir = tmp_path / "cache"
    path = thumbnail_path(clip, position=0.25, cache_dir=cache_dir)
    assert path == cache_dir / f"{thumbnail_key(clip, position=0.25)}.jpg"
    assert not cache_dir.exists()


# --------------------------------------------------------------------------- #
# 3.2 — thumbnail_for
# --------------------------------------------------------------------------- #


def test_a_cache_hit_runs_neither_probe_nor_ffmpeg(
    tmp_path: Path, probe_calls: Callable[..., ProbeCalls]
) -> None:
    clip = _clip(tmp_path)
    cache_dir = tmp_path / "cache"
    cached = thumbnail_path(clip, position=0.25, cache_dir=cache_dir)
    cache_dir.mkdir()
    cached.write_bytes(FAKE_JPEG)
    calls = probe_calls()
    runtime = FakeRuntime()

    assert thumbnail_for(clip, position=0.25, cache_dir=cache_dir, runtime=runtime) == cached
    assert calls == []
    assert runtime.calls == []


def test_a_missing_clip_is_a_thumbnail_error_naming_it(
    tmp_path: Path, probe_calls: Callable[..., ProbeCalls]
) -> None:
    missing = tmp_path / "borttagen.mp4"
    probe_calls()
    with pytest.raises(ThumbnailError) as exc:
        thumbnail_for(missing, position=0.25, cache_dir=tmp_path / "cache", runtime=FakeRuntime())
    assert str(exc.value).startswith(f"{missing}: cannot stat the clip")
    assert exc.value.reason == "cannot stat the clip: No such file or directory"


def test_a_miss_extracts_once_at_a_quarter_of_the_duration(
    tmp_path: Path, probe_calls: Callable[..., ProbeCalls]
) -> None:
    clip = _clip(tmp_path)
    cache_dir = tmp_path / "cache"
    probe_calls(duration=61.44)
    runtime = FakeRuntime()

    result = thumbnail_for(clip, position=0.25, cache_dir=cache_dir, runtime=runtime)

    assert len(runtime.calls) == 1
    args = runtime.calls[0]
    assert args[args.index("-ss") + 1] == "15.360"
    assert result == thumbnail_path(clip, position=0.25, cache_dir=cache_dir)
    assert result.read_bytes() == FAKE_JPEG
    assert _leftovers(cache_dir) == [result.name]  # no .tmp remains


def test_a_configured_position_moves_the_frame(
    tmp_path: Path, probe_calls: Callable[..., ProbeCalls]
) -> None:
    clip = _clip(tmp_path)
    probe_calls(duration=27.84)
    runtime = FakeRuntime()
    thumbnail_for(clip, position=0.5, cache_dir=tmp_path / "cache", runtime=runtime)
    args = runtime.calls[0]
    assert args[args.index("-ss") + 1] == "13.920"


def test_a_relative_symlink_is_probed_and_read_at_its_resolved_path(
    tmp_path: Path, probe_calls: Callable[..., ProbeCalls]
) -> None:
    target = _clip(tmp_path / "clips")
    event = tmp_path / "library" / "2024" / "2024-06-27 - Grillning med grannar"
    event.mkdir(parents=True)
    link = event / "s1710001.mp4"
    link.symlink_to(os.path.relpath(target, event))
    calls = probe_calls()
    runtime = FakeRuntime()

    thumbnail_for(link, position=0.25, cache_dir=tmp_path / "cache", runtime=runtime)

    resolved = target.resolve()
    assert calls == [resolved]
    args = runtime.calls[0]
    assert args[args.index("-i") + 1] == str(resolved)
    assert Path(args[args.index("-i") + 1]).is_absolute()


def test_no_usable_duration_is_never_guessed(
    tmp_path: Path, probe_calls: Callable[..., ProbeCalls]
) -> None:
    clip = _clip(tmp_path)
    probe_calls(duration=0.0)
    runtime = FakeRuntime()
    with pytest.raises(ThumbnailError, match="no usable duration") as exc:
        thumbnail_for(clip, position=0.25, cache_dir=tmp_path / "cache", runtime=runtime)
    assert str(exc.value).startswith(f"{clip}: ")
    assert runtime.calls == []


def test_a_probe_error_becomes_a_thumbnail_error_naming_the_clip(
    tmp_path: Path, probe_calls: Callable[..., ProbeCalls]
) -> None:
    clip = _clip(tmp_path, "trasig.mp4")
    probe_calls(error=ProbeError(f"File is empty (zero bytes): {clip.resolve()}"))
    runtime = FakeRuntime()
    with pytest.raises(ThumbnailError) as exc:
        thumbnail_for(clip, position=0.25, cache_dir=tmp_path / "cache", runtime=runtime)
    assert str(exc.value) == f"{clip}: File is empty (zero bytes)"
    assert exc.value.clip == str(clip)
    assert exc.value.reason == "File is empty (zero bytes)"
    assert not isinstance(exc.value, ThumbnailCacheError)
    assert runtime.calls == []


@pytest.mark.parametrize(
    ("template", "reason"),
    [
        ("File does not exist: {p}", "File does not exist"),
        ("No video stream found in {p}", "No video stream found"),
        (
            "Could not determine a plausible frame rate for {p} (avg_frame_rate='0/0')",
            "Could not determine a plausible frame rate (avg_frame_rate='0/0')",
        ),
        (
            "ffprobe could not read {p}: Command exited 1: ffprobe -v error {p}\nstderr:\nboom",
            "ffprobe could not read: Command exited 1: ffprobe -v error {p}\nstderr:\nboom",
        ),
        ("an unforeseen probe message", "an unforeseen probe message"),
    ],
)
def test_a_probe_reason_drops_the_first_mention_of_the_path(
    tmp_path: Path, probe_calls: Callable[..., ProbeCalls], template: str, reason: str
) -> None:
    clip = _clip(tmp_path)
    source = clip.resolve()
    probe_calls(error=ProbeError(template.format(p=source)))
    with pytest.raises(ThumbnailError) as exc:
        thumbnail_for(clip, position=0.25, cache_dir=tmp_path / "cache", runtime=FakeRuntime())
    # Only the path's first mention goes: a quoted ffprobe command keeps its argument.
    assert exc.value.reason == reason.format(p=source)


def test_the_probe_and_the_extraction_are_each_bounded_to_sixty_seconds(
    tmp_path: Path, probe_calls: Callable[..., ProbeCalls]
) -> None:
    clip = _clip(tmp_path)
    probe_calls()
    runtime = FakeRuntime()
    thumbnail_for(clip, position=0.25, cache_dir=tmp_path / "cache", runtime=runtime)
    assert thumbnail_module.THUMBNAIL_TIMEOUT == 60.0
    assert runtime.timeouts == [60.0]
    assert len(runtime.calls) == 1


def test_a_cache_hit_derives_no_bounded_runtime(
    tmp_path: Path, probe_calls: Callable[..., ProbeCalls]
) -> None:
    clip = _clip(tmp_path)
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    thumbnail_path(clip, position=0.25, cache_dir=cache_dir).write_bytes(FAKE_JPEG)
    runtime = FakeRuntime()
    thumbnail_for(clip, position=0.25, cache_dir=cache_dir, runtime=runtime)
    assert runtime.timeouts == []


def test_an_extraction_that_times_out_is_the_clips_failure_and_leaves_nothing(
    tmp_path: Path, probe_calls: Callable[..., ProbeCalls]
) -> None:
    clip = _clip(tmp_path)
    cache_dir = tmp_path / "cache"
    probe_calls(duration=27.84)
    runtime = FakeRuntime(error=FfmpegTimeoutError("Command timed out after 60s: ffmpeg -i x"))

    with pytest.raises(ThumbnailError) as exc:
        thumbnail_for(clip, position=0.25, cache_dir=cache_dir, runtime=runtime)

    assert exc.value.clip == str(clip)
    assert exc.value.reason.startswith("ffmpeg timed out extracting the frame at 6.960s: ")
    assert "timed out after 60s" in exc.value.reason
    assert "no frame" not in exc.value.reason
    assert len(runtime.calls) == 1  # no other timestamp
    assert _leftovers(cache_dir) == []


def test_a_probe_that_times_out_is_the_clips_failure_and_runs_no_ffmpeg(
    tmp_path: Path, probe_calls: Callable[..., ProbeCalls]
) -> None:
    clip = _clip(tmp_path)
    cache_dir = tmp_path / "cache"
    source = clip.resolve()
    probe_calls(
        error=ProbeError(f"ffprobe could not read {source}: Command timed out after 60s: ffprobe")
    )
    runtime = FakeRuntime()

    with pytest.raises(ThumbnailError) as exc:
        thumbnail_for(clip, position=0.25, cache_dir=cache_dir, runtime=runtime)

    assert exc.value.reason == "ffprobe could not read: Command timed out after 60s: ffprobe"
    assert runtime.calls == []
    assert _leftovers(cache_dir) == []


def test_an_ffmpeg_failure_is_no_frame_and_leaves_nothing(
    tmp_path: Path, probe_calls: Callable[..., ProbeCalls]
) -> None:
    clip = _clip(tmp_path, "s1710004.mp4")
    cache_dir = tmp_path / "cache"
    probe_calls(duration=27.84)
    stderr = "Could not open encoder before EOF"
    runtime = FakeRuntime(error=FfmpegError(f"Command exited 234: ffmpeg ...\nstderr:\n{stderr}"))

    with pytest.raises(ThumbnailError) as exc:
        thumbnail_for(clip, position=0.25, cache_dir=cache_dir, runtime=runtime)

    message = str(exc.value)
    assert message.startswith(f"{clip}: no frame extracted at 6.960s of 27.840s")
    assert stderr in message
    assert len(runtime.calls) == 1  # one attempt, no other timestamp
    assert _leftovers(cache_dir) == []


def test_exit_zero_with_an_empty_output_is_no_frame(
    tmp_path: Path, probe_calls: Callable[..., ProbeCalls]
) -> None:
    clip = _clip(tmp_path, "s1710004.mp4")
    cache_dir = tmp_path / "cache"
    probe_calls(duration=27.84)
    with pytest.raises(ThumbnailError) as exc:
        thumbnail_for(clip, position=0.25, cache_dir=cache_dir, runtime=FakeRuntime(payload=b""))
    assert str(exc.value).startswith(f"{clip}: no frame extracted at 6.960s of 27.840s")
    assert _leftovers(cache_dir) == []


def test_an_uncreatable_cache_is_a_cache_error_not_a_clip_error(
    tmp_path: Path, probe_calls: Callable[..., ProbeCalls]
) -> None:
    clip = _clip(tmp_path)
    blocker = tmp_path / "not-a-directory"
    blocker.write_bytes(b"")
    cache_dir = blocker / "thumbnails"
    probe_calls()
    runtime = FakeRuntime()

    with pytest.raises(ThumbnailCacheError) as exc:
        thumbnail_for(clip, position=0.25, cache_dir=cache_dir, runtime=runtime)

    assert not isinstance(exc.value, ThumbnailError)
    assert str(exc.value).startswith(f"{cache_dir}: cannot write thumbnails")
    assert runtime.calls == []  # classified before ffmpeg runs


def test_a_read_only_cache_directory_is_a_cache_error(
    tmp_path: Path, probe_calls: Callable[..., ProbeCalls]
) -> None:
    if os.geteuid() == 0:
        pytest.skip("root ignores directory write permissions")
    clip = _clip(tmp_path)
    cache_dir = tmp_path / "read-only"
    cache_dir.mkdir()
    cache_dir.chmod(0o555)
    probe_calls()
    runtime = FakeRuntime()
    try:
        with pytest.raises(ThumbnailCacheError) as exc:
            thumbnail_for(clip, position=0.25, cache_dir=cache_dir, runtime=runtime)
    finally:
        cache_dir.chmod(0o755)
    assert str(exc.value).startswith(f"{cache_dir}: cannot write thumbnails")
    assert runtime.calls == []
    assert _leftovers(cache_dir) == []


def test_an_unreadable_cache_is_a_cache_error_before_any_probe(
    tmp_path: Path, probe_calls: Callable[..., ProbeCalls], monkeypatch: pytest.MonkeyPatch
) -> None:
    clip = _clip(tmp_path)
    cache_dir = tmp_path / "cache"
    calls = probe_calls()
    real_is_file = Path.is_file

    def is_file(self: Path) -> bool:  # Python 3.13 raises on an unsearchable directory
        if self.parent == cache_dir:
            raise PermissionError(13, "Permission denied", str(self))
        return real_is_file(self)

    monkeypatch.setattr(Path, "is_file", is_file)
    with pytest.raises(ThumbnailCacheError) as exc:
        thumbnail_for(clip, position=0.25, cache_dir=cache_dir, runtime=FakeRuntime())
    assert not isinstance(exc.value, ThumbnailError)
    assert str(exc.value).startswith(f"{cache_dir}: cannot read thumbnails")
    assert calls == []


def test_a_failed_rename_is_a_cache_error_and_leaves_nothing(
    tmp_path: Path, probe_calls: Callable[..., ProbeCalls], monkeypatch: pytest.MonkeyPatch
) -> None:
    clip = _clip(tmp_path)
    cache_dir = tmp_path / "cache"
    probe_calls()

    def failing_replace(src: object, dst: object) -> None:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(thumbnail_module.os, "replace", failing_replace)
    with pytest.raises(ThumbnailCacheError) as exc:
        thumbnail_for(clip, position=0.25, cache_dir=cache_dir, runtime=FakeRuntime())
    assert str(exc.value).startswith(f"{cache_dir}: cannot write thumbnails")
    assert _leftovers(cache_dir) == []


def test_an_interrupt_propagates_and_leaves_nothing(
    tmp_path: Path, probe_calls: Callable[..., ProbeCalls]
) -> None:
    clip = _clip(tmp_path)
    cache_dir = tmp_path / "cache"
    probe_calls()
    with pytest.raises(KeyboardInterrupt):
        thumbnail_for(
            clip,
            position=0.25,
            cache_dir=cache_dir,
            runtime=FakeRuntime(error=KeyboardInterrupt()),
        )
    assert _leftovers(cache_dir) == []


def test_a_changed_clip_gets_a_new_thumbnail(
    tmp_path: Path, probe_calls: Callable[..., ProbeCalls]
) -> None:
    clip = _clip(tmp_path)
    cache_dir = tmp_path / "cache"
    probe_calls()
    runtime = FakeRuntime()
    first = thumbnail_for(clip, position=0.25, cache_dir=cache_dir, runtime=runtime)
    stat = clip.stat()
    os.utime(clip, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))

    second = thumbnail_for(clip, position=0.25, cache_dir=cache_dir, runtime=runtime)

    assert second != first
    assert first.is_file() and second.is_file()  # the earlier file is left in place
    assert len(runtime.calls) == 2


def test_symlinks_in_two_events_share_one_thumbnail(
    tmp_path: Path, probe_calls: Callable[..., ProbeCalls]
) -> None:
    clip = _clip(tmp_path / "clips")
    links = []
    for event in ("2024-06-27 - Grillning med grannar", "2024-08-20 - Två kapitel - Tjörn"):
        link = tmp_path / "library" / event / "s1710001.mp4"
        link.parent.mkdir(parents=True)
        link.symlink_to(clip)
        links.append(link)
    probe_calls()
    runtime = FakeRuntime()
    cache_dir = tmp_path / "cache"

    results = [
        thumbnail_for(link, position=0.25, cache_dir=cache_dir, runtime=runtime) for link in links
    ]

    assert results[0] == results[1]
    assert len(runtime.calls) == 1  # ffmpeg runs only for the first


def test_two_concurrent_generations_of_one_thumbnail(
    tmp_path: Path, probe_calls: Callable[..., ProbeCalls]
) -> None:
    clip = _clip(tmp_path)
    cache_dir = tmp_path / "cache"
    probe_calls()
    # Both callers miss the cache, then write at the same moment.
    runtime = FakeRuntime(barrier=threading.Barrier(2))
    results: List[Path] = []
    errors: List[BaseException] = []

    def generate() -> None:
        try:
            results.append(thumbnail_for(clip, position=0.25, cache_dir=cache_dir, runtime=runtime))
        except BaseException as exc:  # pylint: disable=broad-except
            errors.append(exc)

    threads = [threading.Thread(target=generate) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=20)

    assert errors == []
    assert len(runtime.calls) == 2
    assert results[0] == results[1]
    assert results[0].read_bytes() == FAKE_JPEG
    assert _leftovers(cache_dir) == [results[0].name]


# --- one_line_cause: the ERROR line's and the problem detail's cause ------------


def test_one_line_cause_keeps_ffmpegs_last_stderr_line_without_tags_or_the_clip(
    tmp_path: Path,
) -> None:
    clip = tmp_path / "clip.mp4"
    reason = (
        f"ffprobe could not read: Command exited 1: /usr/bin/ffprobe -v error {clip}\n"
        f"stderr:\n[mov,mp4 @ 0x56] moov atom not found\n{clip}: Invalid data found"
    )
    assert one_line_cause(reason, clip) == "ffprobe could not read: Invalid data found"


def test_one_line_cause_cuts_any_other_server_path(tmp_path: Path) -> None:
    """A cache file ffmpeg names is cut, with the separator before it."""
    reason = (
        f"no frame extracted at 0.500s of 2.000s: Command exited 1: ffmpeg -i {tmp_path}/c.mp4\n"
        "stderr:\n[image2 @ 0x1] Could not open file : /var/cache/auto reel/.k.tmp"
    )
    cause = one_line_cause(reason, tmp_path / "c.mp4")
    assert cause == "no frame extracted at 0.500s of 2.000s: Could not open file"


def test_one_line_cause_keeps_a_plain_reason_and_rationals(tmp_path: Path) -> None:
    clip = tmp_path / "c.mp4"
    rate = "Could not determine a plausible frame rate (avg_frame_rate='0/0', r_frame_rate='0/0')"
    assert one_line_cause(rate, clip) == rate
    assert one_line_cause("File is empty (zero bytes)", clip) == "File is empty (zero bytes)"
    assert one_line_cause("first line\nsecond line", clip) == "first line"


def test_one_line_cause_shortens_the_backslash_escaped_spelling_of_a_non_utf8_name(
    tmp_path: Path,
) -> None:
    """ffmpeg's stderr, decoded by the runtime, spells the name ``caf\\xe9.mp4``."""
    clip = tmp_path / os.fsdecode(b"caf\xe9.mp4")
    escaped = f"{tmp_path}/caf\\xe9.mp4"
    reason = (
        f"ffprobe could not read: Command exited 1: /usr/bin/ffprobe -v error {clip}\n"
        f"stderr:\n[mov,mp4 @ 0x56] moov atom not found\n"
        f"{escaped}: Invalid data found when processing input"
    )
    assert (
        one_line_cause(reason, clip) == "ffprobe could not read: "
        "Invalid data found when processing input"
    )


def test_one_line_cause_of_a_timeout_names_no_server_path(tmp_path: Path) -> None:
    clip = tmp_path / "clip.mp4"
    reason = (
        f"ffmpeg timed out extracting the frame at 15.360s: Command timed out after 60s: "
        f"/usr/bin/ffmpeg -ss 15.360 -i {clip}"
    )
    assert (
        one_line_cause(reason, clip)
        == "ffmpeg timed out extracting the frame at 15.360s: Command timed out after 60s"
    )
