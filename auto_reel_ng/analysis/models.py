"""Value types for the analysis pass: the detection output and its thresholds.

These are the pure data the rest of the layer is built around — :class:`Segment`
(what a detector found) and :class:`AnalysisConfig` (how sensitive the detectors
are). Both are immutable; ``Segment`` enforces ``end > start`` at construction so a
zero- or negative-length span can never enter the pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

#: Coarse confidence stamped on every v1 segment. ``blackdetect``/``freezedetect``
#: emit spans, not scores, so the detector firing *is* the signal (decision D-AN5).
#: A richer ``signalstats``-derived value is reserved; the field stays in the type.
COARSE_CONFIDENCE = 0.5


class SegmentKind(str, Enum):
    """The kind of dead footage a :class:`Segment` represents.

    A ``str`` enum so the value round-trips cleanly through the JSON cache sidecar.
    """

    BLACK = "black"
    WHITE = "white"
    FREEZE = "freeze"


@dataclass(frozen=True)
class Segment:
    """One detected dead-footage span: ``[start, end)`` seconds of a single ``kind``.

    ``confidence`` is a ``0.0``–``1.0`` value; v1 populates it coarsely (D-AN5).
    """

    start: float
    end: float
    kind: SegmentKind
    confidence: float

    def __post_init__(self) -> None:
        if self.end <= self.start:
            raise ValueError(f"Segment end ({self.end}) must be greater than start ({self.start})")

    @property
    def duration(self) -> float:
        """Length of the span in seconds."""
        return self.end - self.start


@dataclass(frozen=True)
class AnalysisConfig:
    """Detection thresholds, defaulting to the experiment-005 calibrated values.

    All four are overridable. ``pic_th``/``pix_th`` drive ``blackdetect`` (and, on the
    inverted pass, white); ``freeze_noise`` is ``freezedetect``'s normalized noise
    tolerance; ``min_duration`` is the shortest span (seconds) any detector reports.
    """

    pic_th: float = 0.98
    pix_th: float = 0.10
    freeze_noise: float = 0.003
    min_duration: float = 2.0
