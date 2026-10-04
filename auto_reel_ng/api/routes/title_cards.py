"""Title-card routes: the font registry and the draft-card preview.

Neither route decides anything about a card. The font list is the registry module's own list;
the preview resolves a draft with the engine's resolution (the one the event detail and a
render use) and draws it with the engine's renderer, then returns the bytes. Registered before
the events router: its detail route ``/events/{event_id:path}`` is greedy over ``/``.
"""

from __future__ import annotations

import dataclasses
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool

from ...config.project import ConfigError
from ...errors import (
    FontResolutionError,
    ReelError,
    RenderError,
    TitleCardBackendError,
    TitleCardError,
)
from ...event.metadata import with_resolved_metadata
from ...event.plan import RenderPlan, ResolvedChapter
from ...event.resolution import resolve
from ...reel.card import ChapterCard
from ...reel.document import ReelDocument
from ...reel.schema import build_document
from ...render.target import look_resolution
from ...render.title import (
    BUNDLED_FONTS,
    DEFAULT_FONT_FAMILY,
    TitleCardConfig,
    TitleCardContent,
    check_card_styles,
    overlay_config,
    render_card_png,
    resolve_card,
)
from .. import events_read
from ..preview_gate import PreviewBusyError, PreviewGate
from ..problem import bad_gateway, bad_request, not_found, service_unavailable
from ..schemas import FontOut, ProblemOut, TitleCardPreviewBody

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["title-cards"])

#: The seconds a busy client is told to wait before asking again.
RETRY_AFTER_SECONDS = 2

_DRAFT_CARD_LOC = re.compile(r"chapters\[0\]\.card\.")

_PNG_RESPONSE: Dict[Union[int, str], Dict[str, Any]] = {
    200: {
        "description": "The card as an RGBA PNG at the event's target resolution",
        "content": {"image/png": {"schema": {"type": "string", "format": "binary"}}},
        "headers": {"Cache-Control": {"schema": {"type": "string"}, "description": "no-store"}},
    },
    400: {"model": ProblemOut},
    404: {"model": ProblemOut},
    502: {"model": ProblemOut},
    503: {"model": ProblemOut},
}


@router.get("/fonts", response_model=List[FontOut])
def list_fonts() -> List[FontOut]:
    """``GET /api/v1/fonts``: the bundled title-card fonts, in the registry's order.

    A read of the registry module only: no project, disk or database. ``family`` is the name
    ``card.font_family`` and ``look.title_card.font_family`` accept; exactly one font is the
    ``default`` the engine uses when none is named.
    """
    return [
        FontOut(
            family=font.family,
            display_name=font.display_name,
            weights=list(font.weights),
            default=font.family == DEFAULT_FONT_FAMILY,
        )
        for font in BUNDLED_FONTS
    ]


@dataclasses.dataclass(frozen=True)
class _Draft:
    """A resolved draft, ready to draw."""

    config: TitleCardConfig
    content: TitleCardContent
    width: int
    height: int


class _Refused(Exception):
    """A draft the preview answers with a problem response."""

    def __init__(self, response: JSONResponse) -> None:
        super().__init__()
        self.response = response


def _saved_document(request: Request, event_dir: Path, event_id: str) -> ReelDocument:
    """The event's saved document with resolved metadata, or a scan-failure refusal."""
    settings = request.app.state.settings
    try:
        document = events_read.get_reel(settings, event_id)
        return with_resolved_metadata(document, event_dir)
    except events_read.EventReadError as exc:
        failure = exc.failure.value if exc.failure is not None else None
        raise _Refused(bad_gateway(exc.detail, event_id=event_id, failure=failure)) from exc
    except (ReelError, OSError) as exc:
        failure = events_read.classify_event_failure(exc)
        raise _Refused(
            bad_gateway(
                str(exc), event_id=event_id, failure=failure.value if failure is not None else None
            )
        ) from exc


def _draft_card(body: TitleCardPreviewBody) -> Optional[ChapterCard]:
    """The draft's card as the loader validates a document's (same rules, same messages)."""
    if body.card is None:
        return None
    values = {key: value for key, value in body.card.model_dump().items() if value is not None}
    chapter = build_document(
        {"version": 0, "chapters": [{"name": body.chapter, "clips": [], "card": values}]},
        source="draft title card",
    ).chapters[0]
    return chapter.card


def _prepare(request: Request, event_id: str, body: TitleCardPreviewBody) -> _Draft:
    """Resolve the draft like a render would; raise :class:`_Refused` for each failure cause."""
    settings = request.app.state.settings
    try:
        event_dir = events_read.resolve_event_dir(settings, event_id)
    except events_read.EventNotFoundError as exc:
        raise _Refused(
            not_found(f"no event {event_id!r} under the configured project root", event_id=event_id)
        ) from exc
    document = _saved_document(request, event_dir, event_id)
    try:
        look_defaults = events_read.project_look_defaults(settings)
    except (ConfigError, OSError) as exc:
        raise _Refused(bad_gateway(f"project config unreadable: {exc}", event_id=event_id)) from exc

    try:
        card = _draft_card(body)
        plan = resolve(document, look_defaults=look_defaults)
        look = dict(plan.look)
        if body.style is not None:
            look["title_card"] = body.style
        metadata = plan.metadata
        if body.event_title is not None:
            metadata = dataclasses.replace(metadata, title=body.event_title)
        draft = RenderPlan(metadata=metadata, look=look, chapters=plan.chapters)
        check_card_styles(look.get("title_card"), {body.chapter: card})
        request_ = resolve_card(draft, ResolvedChapter(name=body.chapter, card=card))
    except (ReelError, TitleCardError) as exc:
        message = _DRAFT_CARD_LOC.sub("card.", str(exc)).replace("draft title card: ", "")
        raise _Refused(bad_request(message, event_id=event_id)) from exc
    try:
        width, height = look_resolution(look)
    except RenderError as exc:  # the saved look, not the draft
        raise _Refused(bad_gateway(str(exc), event_id=event_id)) from exc
    return _Draft(overlay_config(request_.config), request_.content, width, height)


@router.post(
    "/events/{event_id:path}/title-card/preview",
    response_class=Response,
    responses=_PNG_RESPONSE,
)
async def preview_title_card(
    event_id: str, body: TitleCardPreviewBody, request: Request
) -> Response:
    """``POST /api/v1/events/{event_id}/title-card/preview``: draw one draft card as a PNG.

    The draft (chapter, card, optionally the event style and title) is resolved by the same
    engine function as the event detail and drawn by the renderer a render uses, at the
    event's target resolution. A ``video`` card is the text on a transparent background, for
    the client to lay over the clip's picture. Read-only and light: no file, cache, ffmpeg,
    probe or database is touched. At most two draws run at once; a request that cannot start
    within the wait limit is answered 503 with ``Retry-After``.
    """
    try:
        draft = await run_in_threadpool(_prepare, request, event_id, body)
    except _Refused as refused:
        return refused.response
    gate: PreviewGate = request.app.state.title_card_gate
    try:
        png = await gate.run(
            lambda: render_card_png(draft.config, draft.content, draft.width, draft.height)
        )
    except PreviewBusyError as exc:
        return JSONResponse(
            status_code=503,
            content={
                "title": "Service Unavailable",
                "status": 503,
                "detail": str(exc),
                "event_id": event_id,
            },
            headers={"Retry-After": str(RETRY_AFTER_SECONDS)},
        )
    except TitleCardBackendError as exc:
        return service_unavailable(str(exc), event_id=event_id, check="drawing backend")
    except FontResolutionError as exc:
        return bad_gateway(str(exc), event_id=event_id)
    except TitleCardError as exc:  # a style value only the drawing refuses (e.g. a colour)
        return bad_request(str(exc), event_id=event_id)
    return Response(content=png, media_type="image/png", headers={"Cache-Control": "no-store"})


__all__ = ["router", "list_fonts", "preview_title_card"]
