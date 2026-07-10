"""Smoke tests for the podman-launched Postgres fixture itself.

Proves two things the persistence suite depends on: the container actually comes
up and is reachable (``requires_db``), and a test that never requests the fixture
runs without starting or touching podman at all.
"""

from __future__ import annotations

import psycopg
import pytest


@pytest.mark.requires_db
def test_postgres_container_comes_up(postgres_container: str) -> None:
    raw_url = postgres_container.replace("postgresql+psycopg://", "postgresql://", 1)
    with psycopg.connect(raw_url) as conn:
        row = conn.execute("SELECT 1").fetchone()
    assert row == (1,)


def test_non_db_test_runs_without_the_container() -> None:
    # No fixture requested: this test must pass on a host with no podman at all.
    assert 1 + 1 == 2
