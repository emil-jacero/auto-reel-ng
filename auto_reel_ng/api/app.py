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
from typing import AsyncIterator, Awaitable, Callable, Optional

from fastapi import FastAPI, Request
from fastapi.responses import Response
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ..persistence.engine import make_engine, make_session_factory
from ..persistence.job_store import JobStore
from .problem import service_unavailable
from .routes.events import router as events_router
from .routes.jobs import router as jobs_router
from .settings import ApiSettings
from .ws import JobsHub
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


def create_app(settings: ApiSettings, *, auth_checker: Optional[AuthChecker] = None) -> FastAPI:
    """Build the FastAPI application for ``settings`` (D-A1).

    ``auth_checker`` is the single middleware hook point (D-A8): pass a custom
    checker (as tests do) to reject requests without touching any route.
    """
    engine = make_engine(settings.database_url)
    session_factory = make_session_factory(engine)
    job_store = JobStore(session_factory)
    jobs_hub = JobsHub(job_store, poll_interval=settings.poll_interval)

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

    app.include_router(events_router)
    app.include_router(jobs_router)
    app.include_router(ws_router)

    return app


__all__ = ["create_app", "AuthChecker"]
