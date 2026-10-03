"""Tests for ``prepare_clip``: a clip's proxy and filmstrip as one operation, one fraction.

The two steps are replaced (their own tests are ``test_proxies_ensure.py`` and
``test_proxies_filmstrip*.py``); this pins how they are joined. Real encodes are in
``test_proxies_prepare_ffmpeg.py``.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, List, Optional

import pytest

from auto_reel_ng.accel.profiles import CPUProfile
from auto_reel_ng.errors import FfmpegCancelledError, FilmstripError, ProxyError
from auto_reel_ng.proxies import PROXY_SHARE, ProxySettings
from auto_reel_ng.proxies import prepare as prepare_module
from auto_reel_ng.proxies import prepare_clip

ENTRY = SimpleNamespace(name="entry")
FILM = SimpleNamespace(name="film")


class Steps:
    """Fakes for the three calls ``prepare_clip`` makes, recording the order they ran in."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.calls: List[str] = []
        self.recorded: Optional[Any] = None  # what lookup_filmstrip answers
        self.proxy_progress: List[float] = [0.3, 0.7, 1.0]
        self.proxy_error: Optional[BaseException] = None
        self.film_error: Optional[BaseException] = None
        self.before_film: Optional[Callable[[], None]] = None
        self.kwargs: dict[str, Any] = {}
        monkeypatch.setattr(prepare_module, "ensure_proxy", self._proxy)
        monkeypatch.setattr(prepare_module, "ensure_filmstrip", self._film)
        monkeypatch.setattr(prepare_module, "lookup_filmstrip", self._lookup)

    def _proxy(self, clip: Path, **kwargs: Any) -> Any:
        self.calls.append("proxy")
        self.kwargs["proxy"] = kwargs
        if self.proxy_error is not None:
            raise self.proxy_error
        for fraction in self.proxy_progress:
            if kwargs["on_progress"] is not None:
                kwargs["on_progress"](fraction)
        return ENTRY

    def _lookup(self, entry: Any) -> Any:
        assert entry is ENTRY
        self.calls.append("lookup")
        return self.recorded

    def _film(self, clip: Path, entry: Any, **kwargs: Any) -> Any:
        assert entry is ENTRY
        self.calls.append("film")
        self.kwargs["film"] = kwargs
        if self.before_film is not None:
            self.before_film()
        if self.film_error is not None:
            raise self.film_error
        return FILM


@pytest.fixture
def steps(monkeypatch: pytest.MonkeyPatch) -> Steps:
    return Steps(monkeypatch)


def prepare(
    on_progress: Optional[Callable[[float], None]] = None,
    should_cancel: Optional[Callable[[], bool]] = None,
) -> Any:
    return prepare_clip(
        Path("/lib/C0001.MP4"),
        settings=ProxySettings(Path("/cache")),
        runtime=None,  # type: ignore[arg-type]
        profile=CPUProfile(),
        on_progress=on_progress,
        should_cancel=should_cancel,
    )


def test_progress_stays_below_one_until_the_filmstrip_is_recorded(steps: Steps) -> None:
    seen: List[float] = []
    steps.before_film = lambda: seen.append(-1.0) if 1.0 in seen else None

    result = prepare(seen.append)

    assert result.entry is ENTRY and result.filmstrip is FILM
    assert -1.0 not in seen  # 1.0 was not reported before the filmstrip ran
    assert seen[-1] == 1.0 and seen.count(1.0) == 1
    assert seen == sorted(seen)
    assert max(seen[:-1]) == pytest.approx(PROXY_SHARE)


def test_the_proxys_fraction_fills_its_share_of_the_clip(steps: Steps) -> None:
    seen: List[float] = []

    prepare(seen.append)

    assert seen[:3] == pytest.approx([0.3 * PROXY_SHARE, 0.7 * PROXY_SHARE, PROXY_SHARE])


def test_a_complete_clip_reports_one_and_runs_no_filmstrip(steps: Steps) -> None:
    steps.recorded = FILM
    steps.proxy_progress = []  # a cache hit reports nothing of its own
    seen: List[float] = []

    result = prepare(seen.append)

    assert seen == [1.0]
    assert result.filmstrip is FILM
    assert steps.calls == ["proxy", "lookup"]


def test_a_proxy_without_a_filmstrip_cuts_only_the_filmstrip(steps: Steps) -> None:
    steps.proxy_progress = []  # the proxy was a cache hit
    seen: List[float] = []

    prepare(seen.append)

    assert steps.calls == ["proxy", "lookup", "film"]
    assert seen == [PROXY_SHARE, 1.0]


def test_the_cancel_check_reaches_both_steps(steps: Steps) -> None:
    check = lambda: False  # noqa: E731

    prepare(should_cancel=check)

    assert steps.kwargs["proxy"]["should_cancel"] is check
    assert steps.kwargs["film"]["should_cancel"] is check


def test_a_cancel_between_the_steps_raises_and_the_proxy_is_not_lost(steps: Steps) -> None:
    steps.film_error = FfmpegCancelledError("the filmstrip was canceled before it started")
    seen: List[float] = []

    with pytest.raises(FfmpegCancelledError):
        prepare(seen.append, should_cancel=lambda: True)

    assert steps.calls == ["proxy", "lookup", "film"]
    assert 1.0 not in seen


def test_a_failed_proxy_attempts_no_filmstrip(steps: Steps) -> None:
    steps.proxy_error = ProxyError("/lib/C0001.MP4", "no video stream")

    with pytest.raises(ProxyError):
        prepare()

    assert steps.calls == ["proxy"]


def test_a_failed_filmstrip_is_its_own_error_and_never_reports_one(steps: Steps) -> None:
    steps.film_error = FilmstripError("/lib/C0001.MP4", "ffmpeg could not cut the filmstrip")
    seen: List[float] = []

    with pytest.raises(FilmstripError):
        prepare(seen.append)

    assert 1.0 not in seen


def test_without_a_callback_it_is_the_two_calls_one_after_the_other(steps: Steps) -> None:
    result = prepare()

    assert (result.entry, result.filmstrip) == (ENTRY, FILM)
    assert (
        steps.kwargs["proxy"]["on_progress"] is not None
    )  # always wired; the callback is optional
