"""The staleness gate: one function, three call sites (decision D-C3).

Stale ⇔ no manifest, or the current fingerprint differs from the manifest's, or the
manifest's recorded output file is missing from disk. The verdict names which
components changed (by comparing sub-hashes) so ``scan``/the API can explain
*why* an event is stale. A force request bypasses this gate entirely — that is a
caller-side decision (CLI/API/worker), not something this function knows about.

The reasons a verdict may cite are a **closed vocabulary** owned here
(:class:`StalenessReason`): every consumer that publishes reasons — the CLI's
output, the API's schema — takes the set from this module rather than restating
it, so adding, removing or renaming a reason is a change made in one place.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Union

from .fingerprint import COMPONENTS, Fingerprint
from .manifest import read_manifest

PathLike = Union[str, Path]


class StalenessReason(StrEnum):
    """The closed set of reasons a stale verdict may cite.

    A :class:`~enum.StrEnum` member *is* a ``str``, so a reason compares, joins,
    formats and serializes exactly as the bare string it replaces — the wire
    values are unchanged by construction. The component members mirror
    :data:`~auto_reel_ng.staleness.fingerprint.COMPONENTS`, in that order (asserted
    by the gate's tests, so a new component cannot ship without its reason).
    """

    NO_MANIFEST = "no_manifest"  # no manifest to compare sub-hashes against
    OUTPUT = "output"  # the manifest's recorded output file is gone
    EDITORIAL = "editorial"  # ─┐
    DEFAULTS = "defaults"  #    │ one per fingerprint component,
    CLIP_SET = "clip_set"  #    │ in COMPONENTS order
    ENGINE = "engine"  # ──────┘


@dataclass(frozen=True)
class Verdict:
    """A staleness decision: whether the event is stale, and why."""

    stale: bool
    reasons: tuple[StalenessReason, ...] = ()


def evaluate(event_dir: PathLike, output_path: PathLike, fingerprint: Fingerprint) -> Verdict:
    """Evaluate the staleness gate for ``event_dir`` against its current ``fingerprint``.

    ``output_path`` is the event's expected rendered output file. A fresh verdict
    (no reasons) requires the manifest to exist, every component sub-hash to match,
    and the output file to exist.

    A changed component is mapped through :class:`StalenessReason`, so a component
    with no reason member raises :class:`ValueError` here rather than reaching a
    client as an untyped reason.
    """
    manifest = read_manifest(event_dir)
    if manifest is None:
        return Verdict(stale=True, reasons=(StalenessReason.NO_MANIFEST,))

    reasons = [
        StalenessReason(name)
        for name in COMPONENTS
        if fingerprint.component(name) != manifest.components.get(name)
    ]
    if not Path(output_path).exists():
        reasons.append(StalenessReason.OUTPUT)

    return Verdict(stale=bool(reasons), reasons=tuple(reasons))


__all__ = ["StalenessReason", "Verdict", "evaluate"]
