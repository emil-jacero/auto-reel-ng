"""Which events claim an output path (D-9): the one claim-selection rule.

The CLI's batch commands, ``POST /api/v1/jobs`` and the worker each need to know
whether an event claims the output path its metadata gives it. An event claims one
only when it can be loaded and is processable (a real date and a title, not in the
future). Any other outcome is a *reason*, never an exception and never a claim:
one bad event MUST NOT kill a batch, but it MUST be reported (Principle I).

Read-only: a folder seed lives in memory, no ``reel.yaml`` is written. The layout-aware
"who else claims my path?" check is :mod:`..render.claims`, which sits above this layer.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Optional, Tuple

from ..errors import EventMetadataError, ReelError
from ..reel import ReelDocument
from .discovery import ClipOrder
from .metadata import load_event_document, require_processable


def checked_claim(
    event_dir: Path, *, order: ClipOrder, today: date
) -> Tuple[Optional[ReelDocument], Optional[str]]:
    """``(document, None)`` for a processable event, or ``(None, reason)``; exactly one is ``None``.

    ``ReelError`` (an unparseable ``reel.yaml``, an ``EventMetadataError``), ``OSError``
    (a folder or file that cannot be listed or read) and ``ValueError`` (a guard: the
    loader reports every ``reel.yaml`` problem as a ``ReelError``) become the reason.
    Any other exception is a bug, not an event's problem, and propagates.
    """
    try:
        document, _seeded = load_event_document(event_dir, order=order)
        require_processable(event_dir, document.metadata, today=today)
    except EventMetadataError as exc:
        return None, exc.reason
    except ReelError as exc:
        return None, str(exc)
    except OSError as exc:
        return None, f"cannot read the event: {exc.strerror or exc}"
    except ValueError as exc:
        return None, f"cannot read the event: {exc}"
    return document, None


__all__ = ["checked_claim"]
