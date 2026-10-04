"""The probe-free, host-independent render fingerprint (§4.13/§8.14, decision D-C1).

A fingerprint is a hash over exactly four components, each with its own sub-hash so
staleness can name what changed: **editorial** (the event's document in canonical
form — its typed fields, not its on-disk bytes, so a comment/formatting-only edit is
not a change), **defaults** (the resolved D-2 project look defaults), **clip_set**
(the sorted on-disk clip identities, each with its content signal — size + mtime_ns
by default, sha256 under the existing hash opt-in), and **engine** (the hand-bumped
:data:`RENDER_GRAPH_VERSION` constant plus the ffmpeg version string). Computing a
fingerprint never invokes ffprobe and never depends on the acceleration profile or
device, so the same event state yields the same fingerprint wherever it is computed
(CLI, worker, or API, on CPU or GPU).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Union

from ..analysis.cache import clip_signal
from ..event.discovery import scan_event
from ..reel.document import ReelDocument

PathLike = Union[str, Path]

#: Bumped by hand whenever a change alters produced output for identical inputs
#: (command-graph changes, filter changes, encoder flag changes). Under-bumping
#: risks a missed re-render (mitigated by ``--force``); over-bumping costs one
#: archive re-render — accepted trade-off (D-C8).
#: 2: render-target-format (1920x1080 / highest-clip-fps canvas, not the first clip's).
#: 3: vaapi-pad-fill (padded clips render black bars, not pad_vaapi's green, on Mesa).
#: 4: title-card-whole-clip-cut (a chapter whose title clip is wholly cut keeps its title card).
#: 5: title-card-fonts (the title card is drawn from bundled fonts under the engine's
#:    fontconfig, not the host's).
#: 6: clip-rotate-engine (a display rotation is applied by the engine on every profile and adds to
#:    rotate; a display-rotated clip is never stream-copied).
#: 7: title-card-model (the opening card shows the event title and a free-text subtitle only;
#:    each card takes its own length and style).
#: 8: title-cards-default-on (an event with no ``look.decorators`` now renders its opening and
#:    chapter cards).
#: 9: video-card-bridge-window (an anchor segment under a video card is encoded as a
#:    card-window head and a tail, so its bytes change for the same inputs).
RENDER_GRAPH_VERSION = 9

#: The four fingerprint components, in the fixed order the combined hash uses.
COMPONENTS = ("editorial", "defaults", "clip_set", "engine")


@dataclass(frozen=True)
class Fingerprint:
    """A render fingerprint: one sub-hash per component, plus their combination."""

    editorial: str
    defaults: str
    clip_set: str
    engine: str
    combined: str

    def component(self, name: str) -> str:
        """The sub-hash for one of :data:`COMPONENTS`."""
        return getattr(self, name)  # type: ignore[no-any-return]

    def to_dict(self) -> dict[str, object]:
        """Convert to a plain, JSON-serializable dict (manifest storage shape)."""
        return {
            "combined": self.combined,
            "components": {name: self.component(name) for name in COMPONENTS},
        }


def editorial_hash(document: ReelDocument) -> str:
    """The fingerprint's ``editorial`` component: a hash over the document's canonical fields.

    Canonical over the document's *typed* fields, never its on-disk bytes, so a
    comment-only or formatting-only edit to ``reel.yaml`` leaves it unchanged while
    any editorial change moves it. Shared with ``api/`` as the editorial-read ETag
    (D-R1), which makes it structurally impossible for a held ETag and a staleness
    verdict to disagree about whether the editorial state changed.
    """
    return _hash_json(document.to_dict())


def engine_identity(ffmpeg_version: tuple[int, int]) -> str:
    """A human-readable engine identity for the manifest (D-C2)."""
    return f"render_graph_version={RENDER_GRAPH_VERSION} ffmpeg={ffmpeg_version[0]}.{ffmpeg_version[1]}"


def compute_fingerprint(
    document: ReelDocument,
    *,
    event_dir: PathLike,
    look_defaults: Mapping[str, object],
    ffmpeg_version: tuple[int, int],
    use_hash: bool = False,
) -> Fingerprint:
    """Compute the fingerprint of ``document`` + ``event_dir``'s current disk state.

    ``document`` is the caller's editorial view (loaded, seeded, or adopted —
    whichever is appropriate at that call site); ``look_defaults`` is the resolved
    D-2 project defaults; ``event_dir`` is scanned fresh for the clip-set component.
    No ffprobe call is made and no media content is read (beyond the opt-in hash).
    """
    editorial = editorial_hash(document)
    defaults = _hash_json(dict(look_defaults))
    clip_set = _hash_clip_set(event_dir, use_hash=use_hash)
    engine = _hash_json(
        {"render_graph_version": RENDER_GRAPH_VERSION, "ffmpeg_version": list(ffmpeg_version)}
    )
    combined = _hash_json(
        {"editorial": editorial, "defaults": defaults, "clip_set": clip_set, "engine": engine}
    )
    return Fingerprint(
        editorial=editorial, defaults=defaults, clip_set=clip_set, engine=engine, combined=combined
    )


def _hash_clip_set(event_dir: PathLike, *, use_hash: bool) -> str:
    """Hash the sorted on-disk clip identities, each with its content signal."""
    event_path = Path(event_dir)
    listing = scan_event(event_path)
    entries = [
        {"identity": identity, "signal": clip_signal(event_path / identity, use_hash=use_hash)}
        for identity in listing.identities  # already deterministically sorted
    ]
    return _hash_json(entries)


def _hash_json(value: object) -> str:
    """SHA-256 of ``value``'s canonical JSON form (stable key order, JSON-native types).

    Content whose mapping keys JSON can order and write hashes exactly as it always has.
    Where that raises ``TypeError`` (a ``date`` key, ``int`` and ``str`` keys together), the
    value is hashed with every key tagged by its type instead, so a hash is always available
    and ``{1: x}`` is never conflated with ``{"1": x}``. The fallback runs only where the
    plain form could not, so no hash that could be computed before changes.
    """
    try:
        canonical = json.dumps(value, sort_keys=True, default=str)
    except TypeError:  # a key JSON cannot order or serialise
        canonical = json.dumps(_tag_keys(value), sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _tag_keys(value: object) -> object:
    """``value`` with every mapping key replaced by ``"<type>:<key>"``, at any depth."""
    if isinstance(value, Mapping):
        return {f"{type(key).__name__}:{key}": _tag_keys(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_tag_keys(item) for item in value]
    return value


__all__ = [
    "RENDER_GRAPH_VERSION",
    "COMPONENTS",
    "Fingerprint",
    "editorial_hash",
    "engine_identity",
    "compute_fingerprint",
]
