"""The render manifest sidecar: ``<event>/.auto-reel/cache/render-manifest.json`` (D-C2).

The manifest is the *sole* persistent record of an event's last successful render —
no Postgres mirror. It lives beside the analysis cache (D-AN4) and is written by the
engine only after the atomic finalize succeeds (never on skip/dry-run/failure). An
unreadable or schema-incompatible manifest is treated as absent: fail open to stale,
never fail closed to skip — the same convention :mod:`..analysis.cache` uses for its
own sidecar entries.
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Mapping, Optional, Tuple, Union

from ..analysis.cache import cache_dir
from .fingerprint import COMPONENTS, Fingerprint

logger = logging.getLogger(__name__)

PathLike = Union[str, Path]

MANIFEST_FILENAME = "render-manifest.json"
_MANIFEST_VERSION = 1

#: A D-9 movie name's ISO date prefix; its year names the folder the movie lives in.
_DATE_PREFIX = re.compile(r"([0-9]{4})-[0-9]{2}-[0-9]{2} - ")

#: Recorded values that are never a movie's file name (the output root or its parent).
_NOT_A_FILE_NAME = ("", ".", "..")


@dataclass(frozen=True)
class RenderManifest:
    """The last successful render's recorded state."""

    fingerprint: str
    components: Mapping[str, str]
    output: str
    engine_identity: str
    written_at: str
    #: Bare movie file names this event's earlier renders recorded as ``output`` and a rename since
    #: superseded, oldest first. Not a fingerprint component and not a claim on any file; only
    #: ``prune-renamed`` reads it.
    superseded: Tuple[str, ...] = ()


def manifest_path(event_dir: PathLike) -> Path:
    """The ``render-manifest.json`` path for ``event_dir`` (not created here)."""
    return cache_dir(event_dir) / MANIFEST_FILENAME


def write_manifest(
    event_dir: PathLike,
    fingerprint: Fingerprint,
    *,
    output: str,
    engine_identity: str,
) -> Path:
    """Write the render manifest for ``event_dir`` and return its path.

    Creates the ``.auto-reel/cache/`` directory if absent. Callers are responsible
    for only calling this on an actual, verified render success (D-C5).

    The previous manifest's ``output`` is carried into ``superseded`` when it differs from the new
    ``output`` (the movie a rename left behind, which nothing else remembers), after the names it
    already listed, without duplicates and without ``output`` itself. An unreadable previous
    manifest contributes nothing. No movie is touched.
    """
    path = manifest_path(event_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    previous = read_manifest(event_dir)
    carried = [*previous.superseded, previous.output] if previous is not None else []
    superseded = [name for name in dict.fromkeys(carried) if name != output]
    payload = {
        "version": _MANIFEST_VERSION,
        "fingerprint": fingerprint.combined,
        "components": {name: fingerprint.component(name) for name in COMPONENTS},
        "output": output,
        "engine_identity": engine_identity,
        "written_at": datetime.now(timezone.utc).isoformat(),
        "superseded": superseded,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def read_manifest(event_dir: PathLike) -> Optional[RenderManifest]:
    """Read the render manifest for ``event_dir``, or ``None`` if absent/unreadable.

    Returns ``None`` (treat as absent, evaluate stale) when the file is missing,
    unreadable, unparseable, of an unknown version, or structurally incomplete —
    never raises.
    """
    path = manifest_path(event_dir)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or payload.get("version") != _MANIFEST_VERSION:
        return None
    try:
        components = {name: str(payload["components"][name]) for name in COMPONENTS}
        return RenderManifest(
            fingerprint=str(payload["fingerprint"]),
            components=components,
            output=str(payload["output"]),
            engine_identity=str(payload["engine_identity"]),
            written_at=str(payload["written_at"]),
            superseded=_superseded_names(payload.get("superseded")),
        )
    except (KeyError, TypeError, ValueError) as exc:
        logger.debug("Render manifest %s unreadable: %s", path, exc)
        return None


def _superseded_names(value: object) -> Tuple[str, ...]:
    """The ``superseded`` field as names; empty for an absent or malformed field.

    Tolerant on purpose: the field decides no verdict, so ignoring a malformed one cannot turn a
    stale event fresh, and it must not make an otherwise valid manifest unreadable.
    """
    if not isinstance(value, list) or not all(isinstance(name, str) for name in value):
        return ()
    names: List[str] = list(value)
    return tuple(names)


def recorded_output_in(recorded: str, output_dir: PathLike) -> Path:
    """Where the naming rule (D-9) put a movie named ``recorded`` under ``output_dir``.

    A dated name lives in its own date's year folder, ``<output_dir>/<YYYY>/<name>``; an undated
    one directly in ``output_dir``. ``recorded`` is a bare file name; callers check that
    (:func:`recorded_movie_path`). Pure: no filesystem access, and no event document needed.
    """
    year = _year_folder(recorded)
    base = Path(output_dir)
    return base / recorded if year is None else base / year / recorded


def recorded_output_path(recorded: str, expected_output: PathLike) -> Path:
    """Where the naming rule (D-9) put a movie named ``recorded``, beside ``expected_output``.

    ``expected_output`` is the event's current expected path: ``<output>/<YYYY>/<name>`` for a
    dated name, ``<output>/<name>`` for an undated one. It supplies ``<output>``. A dated
    ``recorded`` name lives in its own date's year folder, an undated one directly in
    ``<output>``. ``recorded`` is a bare file name; the gate checks that before calling. Pure:
    no filesystem access. An undated title that itself starts with ``YYYY-MM-DD - `` is placed
    in that year's folder, where it is not (gate: ``output``). That case is unreachable through
    the CLI, the worker and the API: ``require_processable`` refuses an event without a real date
    before any render or verdict, so only direct library use meets it.
    """
    expected = Path(expected_output)
    expected_year = _year_folder(expected.name)
    in_year_folder = expected_year is not None and expected.parent.name == expected_year
    output_dir = expected.parent.parent if in_year_folder else expected.parent
    return recorded_output_in(recorded, output_dir)


def recorded_movie_path(recorded: str, expected_output: PathLike) -> Optional[Path]:
    """Where a render recorded as ``recorded`` put its movie, beside ``expected_output``.

    :func:`recorded_output_path` for a ``recorded`` that is a bare file name; ``None`` for one
    that is not (empty, ``.``, ``..`` or anything with a path separator), so a manifest can never
    name the output root, its parent or a file elsewhere. Pure: no filesystem access. The gate's
    ``output_renamed`` lookup and the render claim check (:func:`records_output`) both read a
    recorded name through this one function, so they cannot disagree on what it means.
    """
    if recorded in _NOT_A_FILE_NAME or Path(recorded).name != recorded:
        return None
    return recorded_output_path(recorded, expected_output)


def records_output(event_dir: PathLike, output_path: PathLike) -> bool:
    """True when ``event_dir``'s readable render manifest records exactly ``output_path``.

    The recorded name is placed by :func:`recorded_movie_path` beside ``output_path`` and the two
    full paths are compared NFC-normalised and case-insensitively (the output-collision rule's
    comparison, so a case-insensitive archive filesystem cannot slip a clash through). An absent,
    malformed or wrong-version manifest records nothing, the module's fail-open convention.
    Reads the manifest only; never touches the movie.
    """
    manifest = read_manifest(event_dir)
    if manifest is None:
        return False
    recorded = recorded_movie_path(manifest.output, output_path)
    return recorded is not None and _path_key(recorded) == _path_key(Path(output_path))


def _path_key(path: Path) -> str:
    return unicodedata.normalize("NFC", str(path)).casefold()


def _year_folder(name: str) -> Optional[str]:
    """The year folder D-9 puts a movie of this name in, or ``None`` for an undated name."""
    match = _DATE_PREFIX.match(name)
    return match.group(1) if match else None


__all__ = [
    "MANIFEST_FILENAME",
    "RenderManifest",
    "manifest_path",
    "write_manifest",
    "read_manifest",
    "recorded_output_in",
    "recorded_output_path",
    "recorded_movie_path",
    "records_output",
]
