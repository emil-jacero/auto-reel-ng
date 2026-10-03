"""``read_proxy_state``: classify one clip's proxy as absent, ready, stale or failed (D-21).

The read-only counterpart of :func:`~.ensure.ensure_proxy`, for a reader that must say what
the cache holds without making anything (the event detail). It looks only at the clip's own
entry directory ``<cache_dir>/<key>/`` and failure marker ``<cache_dir>/<key>.fail`` with
``stat`` and two small JSON reads: no process, no write, no directory listing. It is not
:func:`~.ensure.lookup_proxy`, which answers "is there a complete entry" and so cannot tell a
clip that was never prepared from an entry that is damaged.

The states, with the precedence ``ready > failed > stale > absent``:

* ``ready``: ``proxy.mp4`` and ``filmstrip.jpg`` are non-empty files and ``facts.json`` is a
  complete, well-typed record under the current :data:`~.spec.PROXY_VERSION`, with a
  ``filmstrip`` record of the current format that describes the image beside it.
* ``failed``: the entry is not ready, its proxy and facts are not both usable (a marker is
  about the proxy, and a published proxy supersedes it), and the clip's failure marker records
  a cause.
* ``stale``: the entry is not ready, there is no marker, and the entry is present but cannot
  be used: an unusable ``facts.json``, an empty file, a malformed or foreign ``filmstrip``
  record, an image the record does not describe.
* ``absent``: everything else, including an entry that is merely incomplete because a file is
  not there yet (the proxy is published before its sprite).

A clip whose file changed, or a bumped :data:`~.spec.PROXY_VERSION`, has another key and so
reads ``absent``; an entry made for the previous file is never looked for. A value is never
defaulted or repaired (Principle I); a cache that cannot be read is an error, not ``absent``.
"""

from __future__ import annotations

import json
import logging
import math
import stat
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Mapping, Optional, cast

from ..errors import ProxyCacheError, ProxyError
from . import spec
from .facts import ProxyFacts
from .failure import read_failure
from .filmstrip import FILMSTRIP_VERSION, Filmstrip
from .settings import ProxySettings

logger = logging.getLogger(__name__)

#: The only "not there" errors: anything else on the cache is a cache error.
_NOT_THERE = (FileNotFoundError, NotADirectoryError)


class ProxyStatus(StrEnum):
    """The closed vocabulary of a clip's proxy state (the API publishes the same four)."""

    ABSENT = "absent"
    READY = "ready"
    STALE = "stale"
    FAILED = "failed"


@dataclass(frozen=True)
class ProxyReading:
    """What the cache says about one clip: its state and what backs it.

    ``facts``, ``filmstrip`` and ``proxy_path`` are set only for ``ready``; ``reason`` only
    for ``failed`` (one line, no server path).
    """

    status: ProxyStatus
    facts: Optional[ProxyFacts] = None
    filmstrip: Optional[Filmstrip] = None
    proxy_path: Optional[Path] = None
    reason: Optional[str] = None


def read_proxy_state(clip_path: Path, *, settings: ProxySettings) -> ProxyReading:
    """The state of the proxy of ``clip_path`` in the cache of ``settings``.

    Raises:
        ProxyError: the clip cannot be statted, so it has no key.
        ProxyCacheError: the entry, the marker or the cache directory cannot be read for a
            reason other than not being there (permission denied, an I/O error).
    """
    try:
        key = spec.proxy_key(clip_path)
    except OSError as exc:
        raise ProxyError(str(clip_path), f"cannot stat the clip: {exc.strerror or exc}") from exc
    cache_dir = Path(settings.cache_dir)
    entry = _classify_entry(cache_dir / key)
    if entry.reading.status is ProxyStatus.READY or entry.proxy_usable:
        return entry.reading
    reason = read_failure(cache_dir, key, Path(clip_path))
    if reason is not None:
        return ProxyReading(ProxyStatus.FAILED, reason=reason)
    return entry.reading


@dataclass(frozen=True)
class _Classified:
    """An entry's reading, and whether its proxy and facts are usable whatever its filmstrip is."""

    reading: ProxyReading
    proxy_usable: bool = False


def _classify_entry(entry: Path) -> _Classified:
    """``ready``, ``stale`` or ``absent`` from the entry directory alone (no marker)."""
    proxy = entry / spec.PROXY_FILENAME
    proxy_size = _size(proxy)
    if proxy_size is None:
        return _Classified(ProxyReading(ProxyStatus.ABSENT))  # no entry, or an incomplete one
    try:
        text = (entry / spec.FACTS_FILENAME).read_text(encoding="utf-8")
    except _NOT_THERE:
        return _Classified(ProxyReading(ProxyStatus.ABSENT))
    except (IsADirectoryError, UnicodeDecodeError):
        return _stale(entry, "facts.json cannot be read as text")
    except OSError as exc:
        raise ProxyCacheError(f"{entry.parent}: cannot read proxies: {exc}") from exc
    try:
        document = json.loads(text)
    except ValueError as exc:
        return _stale(entry, f"facts.json is not JSON: {exc}")
    facts = _valid_facts(document)
    if facts is None:
        return _stale(entry, "facts.json is not a complete record")
    if proxy_size == 0:
        return _stale(entry, "proxy.mp4 is empty")
    reading = _with_filmstrip(entry, proxy, facts, cast(Mapping[str, object], document))
    return _Classified(reading, proxy_usable=True)


def _with_filmstrip(
    entry: Path, proxy: Path, facts: ProxyFacts, document: Mapping[str, object]
) -> ProxyReading:
    """Complete the reading with the filmstrip record and its image."""
    if "filmstrip" not in document:
        return ProxyReading(ProxyStatus.ABSENT)  # the sprite is still to be made
    image = entry / spec.FILMSTRIP_FILENAME
    record = Filmstrip.from_json(document["filmstrip"], image)
    if record is None or record.version != FILMSTRIP_VERSION:
        return _stale_reading(entry, "the filmstrip record is malformed or of another format")
    image_size = _size(image)
    if image_size is None:
        return ProxyReading(ProxyStatus.ABSENT)  # recorded, but the image is not there
    if image_size == 0 or image_size != record.bytes:
        return _stale_reading(entry, "filmstrip.jpg is not the image the record describes")
    return ProxyReading(ProxyStatus.READY, facts=facts, filmstrip=record, proxy_path=proxy)


def _stale_reading(entry: Path, why: str) -> ProxyReading:
    logger.debug("The proxy entry %s is unusable: %s", entry, why)
    return ProxyReading(ProxyStatus.STALE)


def _stale(entry: Path, why: str) -> _Classified:
    return _Classified(_stale_reading(entry, why))


def _size(path: Path) -> Optional[int]:
    """The size of the regular file ``path``; ``None`` when it is not there; a non-file is 0.

    A directory or other non-regular file under a file's name is an unusable entry, not an
    absent one, so it reads as empty (size 0).
    """
    try:
        info = path.stat()
    except _NOT_THERE:
        return None
    except OSError as exc:
        raise ProxyCacheError(f"{path.parent.parent}: cannot read proxies: {exc}") from exc
    return info.st_size if stat.S_ISREG(info.st_mode) else 0


def _valid_facts(document: object) -> Optional[ProxyFacts]:
    """The facts when ``document`` is a complete record this reader can pass on, else ``None``.

    :meth:`ProxyFacts.from_json` is strict about keys, types (a bool is not a number) and the
    proxy version; this adds what the wire shape needs of the values: a finite duration, positive
    sizes, and the probe's rotation range. Unknown extra members are ignored.
    """
    facts = ProxyFacts.from_json(document)
    if facts is None:
        return None
    if not math.isfinite(facts.duration) or facts.width <= 0 or facts.height <= 0:
        return None
    if facts.rotation is not None and not 0 <= facts.rotation < 360:
        return None
    return facts


__all__ = ["ProxyReading", "ProxyStatus", "read_proxy_state"]
