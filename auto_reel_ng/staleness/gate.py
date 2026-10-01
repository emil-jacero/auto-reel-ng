"""The staleness gate: one function, three call sites (decision D-C3).

Stale ⇔ no manifest, or the current fingerprint differs from the manifest's, or the
event's expected output file is missing (with the rename told apart: a movie the last
render wrote under the event's old name is cited as ``output_renamed``, never deleted).
The verdict names which components changed (by comparing sub-hashes) so ``scan``/the
API can explain *why* an event is stale. A force request bypasses this gate entirely — that is a
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
from .manifest import RenderManifest, read_manifest, recorded_output_path

PathLike = Union[str, Path]


class StalenessReason(StrEnum):
    """The closed set of reasons a stale verdict may cite.

    - ``no_manifest``: no readable record of a last render exists to compare against.
    - ``output``: the event's movie is missing from its expected path, and the last
      render's movie is not on disk under another name either.
    - ``output_renamed``: the event's movie name (its title, date or location) changed
      since the last render, whose movie is still on disk under its old name. The next
      render writes the movie under the new name and leaves the old file where it is.
    - ``editorial``, ``defaults``, ``clip_set``, ``engine``: that fingerprint component
      changed since the last render (the ``reel.yaml`` document, the project's look
      defaults, the clips on disk, the render engine).

    A :class:`~enum.StrEnum` member *is* a ``str``, so a reason compares, joins,
    formats and serializes exactly as the bare string it replaces — the wire
    values are unchanged by construction. The component members mirror
    :data:`~auto_reel_ng.staleness.fingerprint.COMPONENTS`, in that order (asserted
    by the gate's tests, so a new component cannot ship without its reason).
    """

    NO_MANIFEST = "no_manifest"  # no manifest to compare sub-hashes against
    OUTPUT = "output"  # the event's movie is not on disk
    OUTPUT_RENAMED = "output_renamed"  # its name changed; the last render's movie is still on disk
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
    and the output file to exist. An absent output file cites exactly one reason,
    ``output_renamed`` or ``output`` (:func:`_absent_output_reason`); which one never
    changes whether the event is stale.

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
    expected = Path(output_path)
    if not expected.exists():
        reasons.append(_absent_output_reason(manifest, expected))

    return Verdict(stale=bool(reasons), reasons=tuple(reasons))


def _absent_output_reason(manifest: RenderManifest, expected: Path) -> StalenessReason:
    """Explain an absent expected movie: renamed since the last render, or gone."""
    recorded = manifest.output
    if (
        recorded != expected.name
        and Path(recorded).name == recorded  # a bare file name, never a path
        and recorded_output_path(recorded, expected).is_file()  # a movie, never a folder
    ):
        return StalenessReason.OUTPUT_RENAMED
    return StalenessReason.OUTPUT


__all__ = ["StalenessReason", "Verdict", "evaluate"]
