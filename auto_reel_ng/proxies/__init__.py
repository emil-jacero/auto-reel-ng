"""Clip proxies (D-21): one verified 540p H.264 + AAC MP4 per clip, outside the library.

``ensure_proxy`` turns a clip into a complete cache entry (``proxy.mp4`` and ``facts.json``),
``lookup_proxy`` answers from the cache with a ``stat`` and a JSON read only, and
``read_proxy_state`` classifies a clip's entry as absent, ready, stale or failed (the failure
marker ``<key>.fail`` is what a failed ``ensure_proxy`` leaves). Proxies are a
second artifact made beside the render: they are not a render input and not a staleness input.
``ensure_filmstrip`` adds the entry's ``filmstrip.jpg`` sprite, cut from the finished proxy.
"""

from __future__ import annotations

from ..errors import FilmstripError, ProxyCacheError, ProxyError
from .cache import STALE_PART_AGE, ProxyEntry, sweep_stale_parts
from .command import EncodePath, ProxyCommand, build_proxy_command, plan_encode
from .ensure import ensure_proxy, lookup_proxy
from .facts import ProxyFacts, SourceFacts, read_facts
from .failure import MARKER_SUFFIX, marker_path, read_failure, record_failure
from .filmstrip import (
    FILMSTRIP_VERSION,
    Filmstrip,
    FilmstripPlan,
    ensure_filmstrip,
    lookup_filmstrip,
)
from .settings import ProxySettings, default_cache_dir, resolve_proxy_settings
from .spec import (
    PROXY_AUDIO_ENCODER,
    PROXY_VERSION,
    entry_dir,
    proxy_dimensions,
    proxy_key,
    spec_digest,
)
from .state import ProxyReading, ProxyStatus, read_proxy_state

__all__ = [
    "FILMSTRIP_VERSION",
    "MARKER_SUFFIX",
    "PROXY_AUDIO_ENCODER",
    "PROXY_VERSION",
    "STALE_PART_AGE",
    "EncodePath",
    "Filmstrip",
    "FilmstripError",
    "FilmstripPlan",
    "ProxyCacheError",
    "ProxyCommand",
    "ProxyEntry",
    "ProxyError",
    "ProxyFacts",
    "ProxyReading",
    "ProxySettings",
    "ProxyStatus",
    "SourceFacts",
    "build_proxy_command",
    "default_cache_dir",
    "ensure_proxy",
    "ensure_filmstrip",
    "entry_dir",
    "lookup_filmstrip",
    "lookup_proxy",
    "marker_path",
    "plan_encode",
    "proxy_dimensions",
    "proxy_key",
    "read_facts",
    "read_failure",
    "read_proxy_state",
    "record_failure",
    "resolve_proxy_settings",
    "spec_digest",
    "sweep_stale_parts",
]
