"""Tests for the engine/session-factory commit/rollback/close behavior (real PG)."""

from __future__ import annotations

from typing import Iterator

import pytest
from sqlalchemy import Column, Integer, MetaData, String, Table, select
from sqlalchemy.orm import Session

from auto_reel_ng.persistence.engine import make_engine, make_session_factory, session_scope

pytestmark = pytest.mark.requires_db

_metadata = MetaData()
_widgets = Table(
    "widgets_engine_test",
    _metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String, nullable=False),
)


@pytest.fixture
def engine(postgres_container: str) -> Iterator:
    eng = make_engine(postgres_container)
    _metadata.create_all(eng)
    try:
        yield eng
    finally:
        _metadata.drop_all(eng)
        eng.dispose()


@pytest.fixture
def session_factory(engine):
    return make_session_factory(engine)


def test_commits_on_clean_exit(session_factory) -> None:
    with session_scope(session_factory) as session:
        session.execute(_widgets.insert().values(id=1, name="a"))

    with session_scope(session_factory) as session:
        row = session.execute(select(_widgets).where(_widgets.c.id == 1)).one_or_none()
    assert row is not None


def test_rolls_back_on_exception(session_factory) -> None:
    with pytest.raises(RuntimeError):
        with session_scope(session_factory) as session:
            session.execute(_widgets.insert().values(id=2, name="b"))
            raise RuntimeError("boom")

    with session_scope(session_factory) as session:
        row = session.execute(select(_widgets).where(_widgets.c.id == 2)).one_or_none()
    assert row is None


@pytest.mark.parametrize("raises", [False, True])
def test_session_is_always_closed(session_factory, monkeypatch, raises: bool) -> None:
    closed = []
    original_close = Session.close

    def spy_close(self: Session) -> None:
        closed.append(True)
        original_close(self)

    monkeypatch.setattr(Session, "close", spy_close)

    if raises:
        with pytest.raises(RuntimeError):
            with session_scope(session_factory):
                raise RuntimeError("boom")
    else:
        with session_scope(session_factory):
            pass

    assert closed == [True]
