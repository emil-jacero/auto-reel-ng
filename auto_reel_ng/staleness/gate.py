"""The staleness gate: one function, three call sites (decision D-C3).

Stale ⇔ no manifest, or the current fingerprint differs from the manifest's, or the
manifest's recorded output file is missing from disk. The verdict names which
components changed (by comparing sub-hashes) so ``scan``/the API can explain
*why* an event is stale. A force request bypasses this gate entirely — that is a
caller-side decision (CLI/API/worker), not something this function knows about.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Union

from .fingerprint import COMPONENTS, Fingerprint
from .manifest import read_manifest

PathLike = Union[str, Path]

#: The reason cited when no manifest exists at all (nothing to compare sub-hashes to).
NO_MANIFEST = "no_manifest"

#: The reason cited when the manifest's recorded output file is missing from disk.
MISSING_OUTPUT = "output"


@dataclass(frozen=True)
class Verdict:
    """A staleness decision: whether the event is stale, and why."""

    stale: bool
    reasons: tuple[str, ...] = ()


def evaluate(event_dir: PathLike, output_path: PathLike, fingerprint: Fingerprint) -> Verdict:
    """Evaluate the staleness gate for ``event_dir`` against its current ``fingerprint``.

    ``output_path`` is the event's expected rendered output file. A fresh verdict
    (no reasons) requires the manifest to exist, every component sub-hash to match,
    and the output file to exist.
    """
    manifest = read_manifest(event_dir)
    if manifest is None:
        return Verdict(stale=True, reasons=(NO_MANIFEST,))

    reasons = [
        name for name in COMPONENTS if fingerprint.component(name) != manifest.components.get(name)
    ]
    if not Path(output_path).exists():
        reasons.append(MISSING_OUTPUT)

    return Verdict(stale=bool(reasons), reasons=tuple(reasons))


__all__ = ["Verdict", "evaluate", "NO_MANIFEST", "MISSING_OUTPUT"]
