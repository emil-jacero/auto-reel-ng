"""Hand-built proxy cache trees for the state-reader tests (no ffmpeg).

``write_entry`` lays down exactly what ``ensure_proxy`` followed by ``ensure_filmstrip`` leave
(``proxy.mp4``, ``facts.json`` with its ``filmstrip`` record, ``filmstrip.jpg``), from a
:class:`~auto_reel_ng.proxies.facts.ProxyFacts` the caller may change one member of, so a test
can damage one fact at a time.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from auto_reel_ng.proxies import FILMSTRIP_VERSION, PROXY_VERSION, proxy_key
from auto_reel_ng.proxies.facts import ProxyFacts

SPRITE = b"\xff\xd8 sprite bytes \xff\xd9"


def sony_facts(**changes: Any) -> ProxyFacts:
    """The facts of a 1080p25 Sony clip with PCM audio (``clip-proxies``, "Facts for a Sony clip")."""
    values: Dict[str, Any] = {
        "proxy_version": PROXY_VERSION,
        "duration": 24.96,
        "fps_num": 25,
        "fps_den": 1,
        "vfr": False,
        "frames": 624,
        "width": 960,
        "height": 540,
        "source_width": 1920,
        "source_height": 1080,
        "rotation": None,
        "audio_codec": "pcm_s16be",
        "encode_path": "cpu",
        "fallback_reason": None,
    }
    values.update(changes)
    return ProxyFacts(**values)


def filmstrip_record(**changes: Any) -> Dict[str, int]:
    """The ``filmstrip`` object of a 25 s landscape clip, for an image of ``len(SPRITE)`` bytes."""
    record = {
        "version": FILMSTRIP_VERSION,
        "tiles": 25,
        "interval": 1,
        "columns": 10,
        "rows": 3,
        "tile_width": 160,
        "tile_height": 90,
        "width": 1600,
        "height": 270,
        "bytes": len(SPRITE),
    }
    record.update(changes)
    return record


def write_entry(
    cache_dir: Path,
    clip: Path,
    *,
    facts: Optional[ProxyFacts] = None,
    document: Optional[Callable[[Dict[str, Any]], None]] = None,
    facts_text: Optional[str] = None,
    proxy: Optional[bytes] = b"proxy bytes",
    sprite: Optional[bytes] = SPRITE,
    filmstrip: Optional[Dict[str, int]] = None,
    with_filmstrip: bool = True,
) -> Path:
    """Write the entry directory of ``clip`` and return it.

    ``document`` edits the ``facts.json`` object before it is written; ``facts_text`` replaces
    the whole file; ``proxy`` and ``sprite`` of ``None`` leave that file out.
    """
    entry = cache_dir / proxy_key(clip)
    entry.mkdir(parents=True)
    if proxy is not None:
        (entry / "proxy.mp4").write_bytes(proxy)
    body: Dict[str, Any] = (facts or sony_facts()).to_json()
    if with_filmstrip:
        body["filmstrip"] = filmstrip if filmstrip is not None else filmstrip_record()
    if document is not None:
        document(body)
    text = facts_text if facts_text is not None else json.dumps(body, sort_keys=True, indent=2)
    (entry / "facts.json").write_text(text, encoding="utf-8")
    if sprite is not None:
        (entry / "filmstrip.jpg").write_bytes(sprite)
    return entry


def write_marker(cache_dir: Path, clip: Path, payload: object) -> Path:
    """Write ``<key>.fail`` with ``payload`` (a string is written as is) and return it."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    marker = cache_dir / f"{proxy_key(clip)}.fail"
    marker.write_text(
        payload if isinstance(payload, str) else json.dumps(payload), encoding="utf-8"
    )
    return marker


def tree(root: Path) -> List[Tuple[str, int, int]]:
    """Every name under ``root`` with its size and mtime: equal before and after = untouched."""
    out = []
    for path in sorted(root.rglob("*")):
        info = os.stat(path)
        out.append((str(path.relative_to(root)), info.st_size, info.st_mtime_ns))
    return out
