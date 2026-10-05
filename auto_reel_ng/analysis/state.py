"""A clip's and an event's analysis state, read from the disk (``analysis-enqueue-api``).

The one rule for "which clips (and so which events) need analysis": the service's analysis
enqueues and the worker's automatic sweep select with it, and the analysis read reports it.
It reads nothing but the event folder's listing, one ``stat`` per clip and the clip's sidecar
entry (:func:`~auto_reel_ng.analysis.cache.inspect_entry`): no process, no decode, no write,
and ``reel.yaml`` is never read.

Per clip, for its current content-change signal, the first that holds: a result →
``current``; a failure marker → ``failed``; an entry or marker of another signal, version or
an unparseable one → ``stale``; no entry file → ``never``. A clip that cannot be statted and an
entry that exists but cannot be read raise :class:`~auto_reel_ng.errors.AnalysisStateError`:
their state is never guessed (Principle I). ``analyzing`` is not a disk state; the service
adds it from the job store.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from ..errors import AnalysisStateError
from ..event.discovery import scan_event
from .cache import EntryFileKind, clip_signal, inspect_entry
from .models import Segment


class ClipAnalysisState(StrEnum):
    """A clip's (or an event's) analysis state as the disk holds it."""

    NEVER = "never"
    STALE = "stale"
    CURRENT = "current"
    FAILED = "failed"


@dataclass(frozen=True)
class ClipAnalysis:
    """One clip's analysis state; its segments when ``current``, its cause when ``failed``."""

    identity: str
    state: ClipAnalysisState
    #: The failure marker's one-line cause, for a ``failed`` clip.
    detail: Optional[str] = None
    #: The cached segments, for a ``current`` clip (possibly none found); empty otherwise.
    segments: Tuple[Segment, ...] = field(default=())


_STATE_OF = {
    EntryFileKind.ABSENT: ClipAnalysisState.NEVER,
    EntryFileKind.RESULT: ClipAnalysisState.CURRENT,
    EntryFileKind.FAILURE: ClipAnalysisState.FAILED,
    EntryFileKind.OTHER: ClipAnalysisState.STALE,
}


def clip_analysis_states(event_dir: Path) -> List[ClipAnalysis]:
    """The analysis state of every clip file the event folder lists, in listing order.

    The clips the analysis job walks (:func:`~auto_reel_ng.event.scan_event`): ignored and
    excluded clips included. A clip that vanished between the listing and its ``stat`` is
    left out, as it is no longer listed.

    Raises:
        OSError: the event folder cannot be listed.
        AnalysisStateError: a clip cannot be statted, or its entry exists but cannot be read.
    """
    clips: List[ClipAnalysis] = []
    for identity in scan_event(event_dir).identities:
        clip_path = event_dir / identity
        try:
            signal = clip_signal(clip_path)
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise AnalysisStateError(f"{identity}: cannot stat the clip: {exc}") from exc
        try:
            record = inspect_entry(event_dir, identity, signal)
        except OSError as exc:
            raise AnalysisStateError(
                f"{identity}: cannot read its analysis cache entry: {exc}"
            ) from exc
        clips.append(
            ClipAnalysis(
                identity=identity,
                state=_STATE_OF[record.kind],
                detail=record.failure,
                segments=tuple(record.segments or ()),
            )
        )
    return clips


def event_disk_state(clips: Sequence[ClipAnalysis]) -> ClipAnalysisState:
    """The event's state from its clips' states: the first rule that holds.

    ``current`` when there are no clips or every clip is ``current``; ``never`` when every clip
    is ``never``; ``stale`` when any clip is ``never`` or ``stale``; otherwise ``failed`` (only
    ``current`` and ``failed`` clips).
    """
    states = {clip.state for clip in clips}
    if states <= {ClipAnalysisState.CURRENT}:
        return ClipAnalysisState.CURRENT
    if states == {ClipAnalysisState.NEVER}:
        return ClipAnalysisState.NEVER
    if states & {ClipAnalysisState.NEVER, ClipAnalysisState.STALE}:
        return ClipAnalysisState.STALE
    return ClipAnalysisState.FAILED


def needs_analysis(clips: Sequence[ClipAnalysis]) -> bool:
    """Whether an unforced analysis job has work: some clip is ``never`` or ``stale``.

    A ``failed`` clip does not count: the job would not retry it until the clip changes or a
    forced job runs.
    """
    return any(clip.state in (ClipAnalysisState.NEVER, ClipAnalysisState.STALE) for clip in clips)


__all__ = [
    "ClipAnalysis",
    "ClipAnalysisState",
    "clip_analysis_states",
    "event_disk_state",
    "needs_analysis",
]
