"""The SQLAlchemy engine and a commit/rollback/close session-factory context manager.

:func:`session_scope` is the one place transaction lifecycle is decided for the
persistence layer: every store operation (job-store repository, later the event
index) opens its session through it rather than managing commit/rollback itself.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

#: How long connecting to Postgres may take before the driver gives up (libpq's
#: ``connect_timeout``, in seconds). Without it a database host that drops packets holds
#: every caller for the operating system's own TCP timeout, minutes. It bounds connecting
#: only: a query on an established connection is not interrupted.
CONNECT_TIMEOUT_SECONDS = 5


def make_engine(database_url: str) -> Engine:
    """Build the SQLAlchemy engine for ``database_url`` (see :mod:`.config`).

    A Postgres engine connects with ``connect_timeout`` :data:`CONNECT_TIMEOUT_SECONDS`
    unless the URL sets its own (``?connect_timeout=30``), which wins. The failure is the
    driver's ``OperationalError``, raised to the caller as for any unreachable database.
    """
    url = make_url(database_url)
    connect_args: dict[str, Any] = {}
    if url.get_backend_name() == "postgresql" and "connect_timeout" not in url.query:
        connect_args["connect_timeout"] = CONNECT_TIMEOUT_SECONDS
    return create_engine(url, future=True, connect_args=connect_args)


def make_session_factory(engine: Engine) -> sessionmaker:
    """Build a session factory bound to ``engine``."""
    return sessionmaker(bind=engine, future=True, expire_on_commit=False)


@contextmanager
def session_scope(session_factory: sessionmaker) -> Iterator[Session]:
    """Yield a session: commit on clean exit, rollback on exception, always close."""
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
