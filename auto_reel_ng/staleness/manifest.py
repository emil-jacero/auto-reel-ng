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
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Optional, Union

from ..analysis.cache import cache_dir
from .fingerprint import COMPONENTS, Fingerprint

logger = logging.getLogger(__name__)

PathLike = Union[str, Path]

MANIFEST_FILENAME = "render-manifest.json"
_MANIFEST_VERSION = 1

#: A D-9 movie name's ISO date prefix; its year names the folder the movie lives in.
_DATE_PREFIX = re.compile(r"([0-9]{4})-[0-9]{2}-[0-9]{2} - ")


@dataclass(frozen=True)
class RenderManifest:
    """The last successful render's recorded state."""

    fingerprint: str
    components: Mapping[str, str]
    output: str
    engine_identity: str
    written_at: str


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
    """
    path = manifest_path(event_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": _MANIFEST_VERSION,
        "fingerprint": fingerprint.combined,
        "components": {name: fingerprint.component(name) for name in COMPONENTS},
        "output": output,
        "engine_identity": engine_identity,
        "written_at": datetime.now(timezone.utc).isoformat(),
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
        )
    except (KeyError, TypeError, ValueError) as exc:
        logger.debug("Render manifest %s unreadable: %s", path, exc)
        return None


def recorded_output_path(recorded: str, expected_output: PathLike) -> Path:
    """Where the naming rule (D-9) put a movie named ``recorded``, beside ``expected_output``.

    ``expected_output`` is the event's current expected path: ``<output>/<YYYY>/<name>`` for a
    dated name, ``<output>/<name>`` for an undated one. It supplies ``<output>``. A dated
    ``recorded`` name lives in its own date's year folder, an undated one directly in
    ``<output>``. ``recorded`` is a bare file name; the gate checks that before calling. Pure:
    no filesystem access. An undated title that itself starts with ``YYYY-MM-DD - `` is placed
    in that year's folder, where it is not (gate: ``output``).
    """
    expected = Path(expected_output)
    expected_year = _year_folder(expected.name)
    in_year_folder = expected_year is not None and expected.parent.name == expected_year
    output_dir = expected.parent.parent if in_year_folder else expected.parent
    recorded_year = _year_folder(recorded)
    if recorded_year is None:
        return output_dir / recorded
    return output_dir / recorded_year / recorded


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
    "recorded_output_path",
]
