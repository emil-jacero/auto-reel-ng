"""The application factory (decision D-A1): ``create_app(settings)``, no import-time globals.

Every dependency (engine, session factory, job store, WS hub) is built from an
explicit :class:`~auto_reel_ng.api.settings.ApiSettings` and stashed on
``app.state``, so tests build apps against fixture roots/containers without env
juggling, and ``auto-reel serve`` resolves settings through the same D-2 layering
as ``worker``.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator, Awaitable, Callable, Optional

from fastapi import FastAPI, Request
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ..ffmpeg.runtime import FfmpegRuntime
from ..persistence.engine import make_engine, make_session_factory
from ..persistence.job_store import JobStore
from .preview_gate import PreviewGate
from .problem import service_unavailable
from .routes.analysis import router as analysis_router
from .routes.events import router as events_router
from .routes.jobs import router as jobs_router
from .routes.media import router as media_router
from .routes.title_cards import router as title_cards_router
from .settings import ApiSettings
from .thumbnails import ThumbnailGate
from .ws import JobsHub, publish_ws_schema
from .ws import router as ws_router

logger = logging.getLogger(__name__)

#: A hook that inspects a request and may short-circuit it (e.g. reject an
#: untokened request); returning ``None`` lets the request proceed. No-op in v1
#: (D-A8) — a bearer-token check is a drop-in ``AuthChecker`` later, requiring no
#: route changes.
AuthChecker = Callable[[Request], Optional[Response]]


def _default_auth_checker(_request: Request) -> Optional[Response]:
    """The v1 no-op auth checker: every request is authorized (D-A8)."""
    return None


def web_dist_dir() -> Path:
    """The development checkout's ``web/dist`` — the built client, when it exists.

    One symbol rather than a settings key (Principle VII: there is exactly one
    correct answer per deployment and no operator ever chooses it), and the seam
    tests monkeypatch. §6 phase 11 — packaging the assets into the wheel/image —
    edits this function and nothing else; an installed wheel finds no directory
    here and simply serves no client, which is a supported state.
    """
    return Path(__file__).resolve().parent.parent.parent / "web" / "dist"


def create_app(settings: ApiSettings, *, auth_checker: Optional[AuthChecker] = None) -> FastAPI:
    """Build the FastAPI application for ``settings`` (D-A1).

    ``auth_checker`` is the single middleware hook point (D-A8): pass a custom
    checker (as tests do) to reject requests without touching any route.
    """
    engine = make_engine(settings.database_url)
    session_factory = make_session_factory(engine)
    job_store = JobStore(session_factory)
    # The hub reports the served project's jobs only, as the jobs routes list them.
    jobs_hub = JobsHub(
        job_store, project_root=str(settings.project_root), poll_interval=settings.poll_interval
    )
    # Built once (D-C1): the engine identity's ffmpeg-version component is
    # per-process, not per-request (change-detection, §8.14).
    runtime = FfmpegRuntime()
    # One per app: the thumbnail route's extraction bound is per service process (D-11).
    thumbnail_gate = ThumbnailGate()
    # One per app: the title-card preview's draw bound is per service process.
    title_card_gate = PreviewGate()

    @asynccontextmanager
    async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            await jobs_hub.stop()
            engine.dispose()

    app = FastAPI(title="auto-reel-ng API", version="1", lifespan=_lifespan)
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.job_store = job_store
    app.state.jobs_hub = jobs_hub
    app.state.runtime = runtime
    app.state.thumbnail_gate = thumbnail_gate
    app.state.title_card_gate = title_card_gate

    checker = auth_checker or _default_auth_checker

    @app.middleware("http")
    async def _auth_middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        rejection = checker(request)
        if rejection is not None:
            return rejection
        return await call_next(request)

    @app.get("/healthz")
    def healthz() -> Response:
        """Liveness + DB reachability (D-A6 open question, settled: yes)."""
        try:
            with app.state.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except SQLAlchemyError as exc:
            logger.warning("healthz: database unreachable: %s", exc)
            return service_unavailable(f"database check failed: {exc}", check="database")
        return Response(status_code=200, content='{"status":"ok"}', media_type="application/json")

    # Before the events router, deliberately: its detail route ``/events/{event_id:path}``
    # is greedy over ``/`` and Starlette tries routes in registration order, so the media
    # router's ``…/media`` and ``…/movie`` would otherwise be read as event ids.
    app.include_router(media_router)
    app.include_router(title_cards_router)
    app.include_router(analysis_router)  # before the events router's greedy detail route
    app.include_router(events_router)
    app.include_router(jobs_router)
    app.include_router(ws_router)

    # The WebSocket frame is part of the contract but not of any HTTP route, so its
    # models are merged into the schema here: the served /openapi.json and the
    # committed web/openapi.json (api/openapi.py) then describe the same frame.
    default_openapi = app.openapi

    def _openapi() -> dict[str, Any]:
        # No cache of its own: FastAPI's openapi() rebuilds its cached schema when
        # the routes change, and the merge is idempotent on the same dict.
        schema = default_openapi()
        publish_ws_schema(schema)
        return schema

    app.openapi = _openapi  # type: ignore[method-assign]

    # Mounted last, deliberately: Starlette matches in registration order, so every
    # API route, /healthz and the WS endpoint are resolved before the mount sees a
    # path. Moving this above the routers would answer /api/v1/events with the
    # client's index.html. A missing build is normal (dev runs and the test suite
    # never build the client), so the mount is simply skipped.
    dist = web_dist_dir()
    if dist.is_dir():
        logger.info("serving the built web client from %s", dist)
        app.mount("/", StaticFiles(directory=dist, html=True), name="web")

    return app


__all__ = ["create_app", "AuthChecker", "web_dist_dir"]
