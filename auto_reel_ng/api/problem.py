"""RFC-ish "problem JSON" error bodies shared across the API (decision D-A6).

Every non-2xx response the service returns deliberately (404/409/502, ``/healthz``
failure) uses this shape rather than a bespoke one per route, so a client parses
errors uniformly. FastAPI's own 422 validation-error body is left as-is (its shape
is already structured and documented by the OpenAPI schema).
"""

from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse


def problem_response(
    status_code: int,
    title: str,
    detail: str,
    **extra: Any,
) -> JSONResponse:
    """Build a problem-JSON body: ``{title, status, detail, **extra}``.

    ``extra`` carries route-specific fields (e.g. the active job's ``job_id`` on the
    enqueue's 409, or the ``event_id`` an events failure is about), each declared on
    :class:`~auto_reel_ng.api.schemas.ProblemOut`, so a client reads one named field
    without branching on which error it received.
    """
    body: dict[str, Any] = {"title": title, "status": status_code, "detail": detail}
    body.update(extra)
    return JSONResponse(status_code=status_code, content=body)


def bad_request(detail: str, **extra: Any) -> JSONResponse:
    """A 400 problem response: a semantically invalid request body.

    Used for a failed editorial-write validation — distinct from FastAPI's own
    422, which is reserved for a structurally malformed body.
    """
    return problem_response(400, "Bad Request", detail, **extra)


def not_found(detail: str, **extra: Any) -> JSONResponse:
    """A 404 problem response."""
    return problem_response(404, "Not Found", detail, **extra)


def conflict(detail: str, **extra: Any) -> JSONResponse:
    """A 409 problem response (D-A6: the visible-conflict case, e.g. duplicate enqueue)."""
    return problem_response(409, "Conflict", detail, **extra)


def precondition_failed(detail: str, **extra: Any) -> JSONResponse:
    """A 412 problem response: an ``If-Match`` tag that does not match current state."""
    return problem_response(412, "Precondition Failed", detail, **extra)


def bad_gateway(detail: str, **extra: Any) -> JSONResponse:
    """A 502-style problem response for an upstream engine failure (scan/probe)."""
    return problem_response(502, "Bad Gateway", detail, **extra)


def service_unavailable(detail: str, **extra: Any) -> JSONResponse:
    """A 503 problem response (``/healthz`` reporting an unreachable dependency)."""
    return problem_response(503, "Service Unavailable", detail, **extra)


__all__ = [
    "problem_response",
    "bad_request",
    "not_found",
    "conflict",
    "precondition_failed",
    "bad_gateway",
    "service_unavailable",
]
