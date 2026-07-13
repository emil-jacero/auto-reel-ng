"""Change detection (§4.13/§8.14): render fingerprint, manifest sidecar, staleness gate.

A probe-free, host-independent fingerprint (:mod:`.fingerprint`) is recorded in a
per-event sidecar manifest (:mod:`.manifest`) after a successful render; the gate
(:mod:`.gate`) compares the two to decide whether an event needs rendering, at three
call sites: the CLI ``render`` filter, ``enqueue`` (CLI + API), and the worker's
claim-time recheck.
"""

from __future__ import annotations

from .fingerprint import (
    COMPONENTS,
    RENDER_GRAPH_VERSION,
    Fingerprint,
    compute_fingerprint,
    engine_identity,
)
from .gate import MISSING_OUTPUT, NO_MANIFEST, Verdict, evaluate
from .manifest import (
    MANIFEST_FILENAME,
    RenderManifest,
    manifest_path,
    read_manifest,
    write_manifest,
)

__all__ = [
    # fingerprint
    "RENDER_GRAPH_VERSION",
    "COMPONENTS",
    "Fingerprint",
    "compute_fingerprint",
    "engine_identity",
    # manifest
    "MANIFEST_FILENAME",
    "RenderManifest",
    "manifest_path",
    "read_manifest",
    "write_manifest",
    # gate
    "Verdict",
    "evaluate",
    "NO_MANIFEST",
    "MISSING_OUTPUT",
]
