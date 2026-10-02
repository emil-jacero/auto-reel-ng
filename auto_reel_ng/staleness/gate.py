"""The staleness gate: one function, three call sites (decision D-C3).

Stale ⇔ no manifest, or the current fingerprint differs from the manifest's, or the
event's expected output is not a regular file (with the rename told apart: a movie the last
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
from typing import Optional, Union

from .fingerprint import COMPONENTS, Fingerprint
from .manifest import RenderManifest, read_manifest, recorded_output_path

PathLike = Union[str, Path]

#: Recorded values that pass as a bare name but name a folder, never a movie: never looked up.
_NOT_A_FILE_NAME = ("", ".", "..")


class StalenessReason(StrEnum):
    """The closed set of reasons a stale verdict may cite.

    - ``no_manifest``: no readable record of a last render exists to compare against.
    - ``output``: the event's movie is missing from its expected path, and the last
      render's movie was not found under its old name either.
    - ``output_renamed``: the event's movie name (its title, date or location) changed
      since the last render, and a movie is still on disk under the old name. The next
      render writes the movie under the new name and leaves the old file where it is;
      only a render of another event that now has the old name replaces that file. The
      verdict then also carries ``renamed_from`` and ``output_name``, the two file names.
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
    OUTPUT = "output"  # the event's movie is not at its expected path
    OUTPUT_RENAMED = "output_renamed"  # its name changed; a movie is still under the old name
    EDITORIAL = "editorial"  # ─┐
    DEFAULTS = "defaults"  #    │ one per fingerprint component,
    CLIP_SET = "clip_set"  #    │ in COMPONENTS order
    ENGINE = "engine"  # ──────┘


@dataclass(frozen=True)
class Verdict:
    """A staleness decision: whether the event is stale, and why.

    ``renamed_from`` and ``output_name`` name the two movie files an ``output_renamed``
    verdict refers to, so a reader need not work them out again from the event's metadata.
    Both are bare file names (no folder part) and both are set exactly when
    :attr:`StalenessReason.OUTPUT_RENAMED` is cited, ``None`` otherwise: ``renamed_from`` is
    the file the gate found for the last render's recorded name (it exists, and is not the
    manifest's raw string), ``output_name`` is the expected output's name, which the next
    render writes. They never affect ``stale`` or ``reasons``.
    """

    stale: bool
    reasons: tuple[StalenessReason, ...] = ()
    renamed_from: Optional[str] = None
    output_name: Optional[str] = None


def evaluate(event_dir: PathLike, output_path: PathLike, fingerprint: Fingerprint) -> Verdict:
    """Evaluate the staleness gate for ``event_dir`` against its current ``fingerprint``.

    ``output_path`` is the event's expected rendered output file. A fresh verdict
    (no reasons) requires the manifest to exist, every component sub-hash to match,
    and the output to be a regular file. An output that is not a file (absent, or a folder
    or other non-file in its place) cites exactly one reason, ``output_renamed`` or
    ``output``; which one never changes whether the event is stale. The old movie is looked
    up once (:func:`_renamed_output`); when it is found the verdict also names it and the
    expected output (``renamed_from``, ``output_name``), and carries neither name otherwise.

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
    renamed_from: Optional[str] = None
    output_name: Optional[str] = None
    if not expected.is_file():
        old_movie = _renamed_output(manifest, expected)
        if old_movie is None:
            reasons.append(StalenessReason.OUTPUT)
        else:
            reasons.append(StalenessReason.OUTPUT_RENAMED)
            renamed_from, output_name = old_movie.name, expected.name

    return Verdict(
        stale=bool(reasons),
        reasons=tuple(reasons),
        renamed_from=renamed_from,
        output_name=output_name,
    )


def rendered_output(event_dir: PathLike, output_path: PathLike) -> Optional[Path]:
    """The event's rendered movie as the gate counts it, or ``None``.

    ``None`` without a readable manifest: no render record, no movie. Otherwise the
    expected output when it is a file, else the file the last render recorded under the
    event's old name (the ``output_renamed`` case, :func:`_renamed_output`). This is the
    gate's own rule made callable, so a reader of "the movie" (the API's movie route)
    cannot disagree with a verdict. Reads the filesystem; never raises for a missing file.
    A folder (or any non-file) at the expected path is no movie, here and in the verdict.
    """
    manifest = read_manifest(event_dir)
    if manifest is None:
        return None
    expected = Path(output_path)
    if expected.is_file():
        return expected
    return _renamed_output(manifest, expected)


def _renamed_output(manifest: RenderManifest, expected: Path) -> Optional[Path]:
    """The recorded movie under its old name, when the gate would cite ``output_renamed``.

    Only the output directory in use is searched: a movie the last render wrote into
    another output directory is not looked for (the verdict then cites ``output``). A movie
    an older engine wrote into a nested folder (a title with a path separator) is recorded
    by its last component only, so it reads ``output`` as a missing movie does.
    """
    recorded = manifest.output
    if (
        recorded != expected.name
        and recorded not in _NOT_A_FILE_NAME  # never the output root or its parent
        and Path(recorded).name == recorded  # a bare file name, never a path
    ):
        candidate = recorded_output_path(recorded, expected)
        if candidate.is_file():  # a movie, never a folder
            return candidate
    return None


__all__ = ["StalenessReason", "Verdict", "evaluate", "rendered_output"]
