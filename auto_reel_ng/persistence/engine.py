"""The SQLAlchemy engine and a commit/rollback/close session-factory context manager.

:func:`session_scope` is the one place transaction lifecycle is decided for the
persistence layer: every store operation (job-store repository, later the event
index) opens its session through it rather than managing commit/rollback itself.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


def make_engine(database_url: str) -> Engine:
    """Build the SQLAlchemy engine for ``database_url`` (see :mod:`.config`)."""
    return create_engine(database_url, future=True)


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
