"""What the proxy enqueue reads: the clips an event's proxy job prepares, and their proxy states.

Split from :mod:`events_read` (which is at its size limit) and used by
``POST /api/v1/events/{event_id}/proxies``. Read-only: ``stat`` and JSON, no process, no write.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Sequence

from ..config.project import load_project_config
from ..event import scan_event
from ..proxies import ProxyStatus, read_proxy_state, resolve_proxy_settings
from .settings import ApiSettings


def proxy_clips(event_dir: Path) -> List[str]:
    """The clips an event's proxy job prepares: every clip file the event folder lists.

    The listing :class:`~auto_reel_ng.scheduler.proxy_job.ProxyJobHandler` walks
    (:func:`~auto_reel_ng.event.scan_event`), in its order. ``reel.yaml`` is never read, so a
    clip it ignores or excludes is prepared and one it lists that is not on disk is not.

    Raises:
        OSError: the event folder cannot be listed.
    """
    return list(scan_event(event_dir).identities)


def proxies_fresh(settings: ApiSettings, event_dir: Path, clips: Sequence[str]) -> bool:
    """Whether every one of ``clips`` of the event has a ``ready`` proxy.

    Each clip's state is :func:`~auto_reel_ng.proxies.read_proxy_state`'s, the function the
    event detail reports in a clip's ``proxy`` field: ``stat`` and one small JSON read, no
    process, no write. Only ``ready`` counts; ``absent``, ``stale`` and ``failed`` each mean the
    job has work. No clips is vacuously ``True``: the caller reports the count it passed.

    Unlike the detail's hint, an unreadable state is not softened to "unknown": a cache that
    cannot be read, a clip that cannot be statted for its key and unusable ``proxies`` settings
    raise, and the caller refuses the request rather than read them as ``absent`` or ``ready``.

    Raises:
        ConfigError: ``config.yaml`` or its ``proxies`` section is unusable.
        ProxyCacheError: the proxy cache cannot be read.
        ProxyError: a clip cannot be statted for its cache key.
    """
    proxies = resolve_proxy_settings(
        load_project_config(settings.project_root), settings.project_root
    )
    return all(
        read_proxy_state(event_dir / identity, settings=proxies).status is ProxyStatus.READY
        for identity in clips
    )


__all__ = ["proxy_clips", "proxies_fresh"]
