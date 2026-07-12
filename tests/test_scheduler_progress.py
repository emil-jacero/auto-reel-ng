"""Tests for throttled progress reporting into the job store (task 3.5)."""

from __future__ import annotations

import uuid
from typing import List, Tuple

from auto_reel_ng.scheduler.progress import ThrottledProgress


class _FakeStore:
    """Records ``set_progress`` calls; stands in for :class:`JobStore` in tests."""

    def __init__(self) -> None:
        self.writes: List[Tuple[uuid.UUID, float]] = []

    def set_progress(self, job_id: uuid.UUID, fraction: float) -> None:
        self.writes.append((job_id, fraction))


def _clock(sequence: List[float]):
    it = iter(sequence)

    def _next() -> float:
        return next(it)

    return _next


def test_first_call_always_writes() -> None:
    store = _FakeStore()
    job_id = uuid.uuid4()
    progress = ThrottledProgress(store, job_id, clock=_clock([0.0]))
    progress(0.1)
    assert store.writes == [(job_id, 0.1)]


def test_small_delta_within_interval_is_skipped() -> None:
    store = _FakeStore()
    job_id = uuid.uuid4()
    # Same instant (interval never elapses), tiny delta (< default min_delta=0.01).
    progress = ThrottledProgress(store, job_id, clock=_clock([0.0, 0.0, 0.0]))
    progress(0.50)
    progress(0.505)
    assert store.writes == [(job_id, 0.50)]


def test_delta_beyond_threshold_writes_even_within_interval() -> None:
    store = _FakeStore()
    job_id = uuid.uuid4()
    progress = ThrottledProgress(store, job_id, clock=_clock([0.0, 0.0]))
    progress(0.10)
    progress(0.20)  # +0.10 delta, well past the default 0.01 threshold
    assert store.writes == [(job_id, 0.10), (job_id, 0.20)]


def test_interval_elapsed_writes_even_with_tiny_delta() -> None:
    store = _FakeStore()
    job_id = uuid.uuid4()
    progress = ThrottledProgress(
        store, job_id, min_delta=0.5, min_interval_s=1.0, clock=_clock([0.0, 2.0])
    )
    progress(0.10)
    progress(0.101)  # tiny delta, but 2s elapsed >= the 1s interval
    assert store.writes == [(job_id, 0.10), (job_id, 0.101)]


def test_terminal_fraction_always_writes_despite_throttle() -> None:
    store = _FakeStore()
    job_id = uuid.uuid4()
    progress = ThrottledProgress(
        store, job_id, min_delta=0.5, min_interval_s=100.0, clock=_clock([0.0, 0.0])
    )
    progress(0.10)
    progress(1.0)  # neither delta nor interval threshold met, but terminal
    assert store.writes == [(job_id, 0.10), (job_id, 1.0)]
