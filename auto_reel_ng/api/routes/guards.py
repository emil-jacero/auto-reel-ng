"""Route decorators shared by more than one routes module."""

from __future__ import annotations

import functools
import logging
from typing import Callable, ParamSpec, TypeVar, Union

from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from ..problem import service_unavailable

logger = logging.getLogger(__name__)

_P = ParamSpec("_P")
_R = TypeVar("_R")


def job_store_unreachable(handler: Callable[_P, _R]) -> Callable[_P, Union[_R, JSONResponse]]:
    """Answer a route's unreachable job store in the shared 503 problem shape (D-A6).

    The events reads map the same failure to the same body (``check="database"``, the
    predicate ``/healthz`` uses), so a client has one test for "the service cannot
    reach its database". The request is never softened into a partial answer: a job
    list without the unreadable jobs, a job reported absent, or a cancel outcome that
    was not applied would each fabricate a fact out of "unknown" (Principle I).
    """

    @functools.wraps(handler)
    def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> Union[_R, JSONResponse]:
        try:
            return handler(*args, **kwargs)
        except SQLAlchemyError as exc:
            logger.warning("jobs: job store unreachable: %s", exc)
            return service_unavailable(f"job store unreachable: {exc}", check="database")

    return wrapper


__all__ = ["job_store_unreachable"]
