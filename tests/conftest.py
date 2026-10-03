"""Shared fixtures: a real :class:`FfmpegRuntime`, a synthetic-clip factory, and a
podman-launched Postgres container for the ``requires_db``-marked persistence suite.

Clips are generated on demand from ``ffmpeg lavfi`` sources (``testsrc`` + ``sine``),
so the test suite needs no checked-in media. Tests requiring ffmpeg are skipped if no
ffmpeg >= 7.1 is available. Tests requiring the database are skipped if podman is not
available on ``PATH``; tests that do not request the ``postgres_container`` fixture
never start or touch the container.
"""

from __future__ import annotations

import shutil
import subprocess
import time
import uuid
from pathlib import Path
from typing import Callable, Iterator, Optional

import psycopg
import pytest
from sqlalchemy.orm import sessionmaker

from auto_reel_ng.errors import FfmpegError, TitleCardError
from auto_reel_ng.ffmpeg.runtime import FfmpegRuntime
from auto_reel_ng.persistence.engine import make_engine, make_session_factory
from auto_reel_ng.persistence.job_store import JobStore
from auto_reel_ng.persistence.models import Base, Job
from auto_reel_ng.render.title.fonts import configure_fontconfig

MakeClip = Callable[..., Path]

#: Pinned so the schema/behavior under test does not shift under us.
_POSTGRES_IMAGE = "docker.io/library/postgres:16-alpine"
_POSTGRES_READY_TIMEOUT_S = 30.0


def fonts_available() -> bool:
    """True when Cairo + Pango and the bundled default font are usable on this host.

    Mirrors the "has GPU" gate: the renderer's image/render tests are skipped when
    the Cairo/Pango backend or the bundled DejaVu Sans family is unavailable, so the
    suite passes on a host (or venv) without the system libraries installed. The fonts
    come from the repository's ``fonts/`` (the engine's own fontconfig), not the host, so
    a host with no system font still runs the title-card tests.
    """
    try:
        # Before the first font map exists, as the renderer does it.
        configure_fontconfig()
        import gi  # noqa: PLC0415

        gi.require_version("Pango", "1.0")
        gi.require_version("PangoCairo", "1.0")
        import cairo  # noqa: F401,PLC0415
        from gi.repository import Pango, PangoCairo  # noqa: PLC0415
    except (ImportError, ValueError, TitleCardError):
        return False
    context = PangoCairo.FontMap.get_default().create_context()
    desc = Pango.FontDescription()
    desc.set_family("DejaVu Sans")
    font = context.load_font(desc)
    if font is None:
        return False
    return font.describe().get_family().strip().lower() == "dejavu sans"


@pytest.fixture
def has_fonts() -> None:
    """Skip a test unless Cairo/Pango and the bundled default font are available."""
    if not fonts_available():
        pytest.skip("Cairo/Pango or the bundled default font (DejaVu Sans) not available")


@pytest.fixture(scope="session")
def runtime() -> FfmpegRuntime:
    """A real runtime backed by the system ffmpeg; skip the test if none is usable."""
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        pytest.skip("ffmpeg/ffprobe not available on PATH")
    try:
        return FfmpegRuntime()
    except FfmpegError as exc:
        pytest.skip(f"usable ffmpeg >= 7.1 not available: {exc}")


@pytest.fixture
def make_clip(tmp_path: Path, runtime: FfmpegRuntime) -> MakeClip:
    """Return a factory that renders a synthetic clip with the requested properties."""

    def _make(
        name: str = "clip.mp4",
        *,
        duration: float = 1.0,
        width: int = 320,
        height: int = 240,
        fps: int = 30,
        audio: bool = True,
        setsar: Optional[str] = None,
        rotate: Optional[int] = None,
        color_trc: Optional[str] = None,
        creation_time: Optional[str] = None,
    ) -> Path:
        out = tmp_path / name
        cmd: list[str] = [runtime.ffmpeg_path, "-y"]
        cmd += [
            "-f",
            "lavfi",
            "-i",
            f"testsrc=size={width}x{height}:rate={fps}:duration={duration}",
        ]
        if audio:
            cmd += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}"]
        # Build a single -vf chain for SAR and color-transfer tagging.
        filters: list[str] = []
        if setsar is not None:
            filters.append(f"setsar={setsar}")
        if color_trc is not None:
            filters.append(f"setparams=color_trc={color_trc}")
        if filters:
            cmd += ["-vf", ",".join(filters)]
        cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p"]
        if audio:
            cmd += ["-c:a", "aac", "-shortest"]
        if creation_time is not None:
            cmd += ["-metadata", f"creation_time={creation_time}"]
        # Rotation is a display-matrix property. ffmpeg >= 8 drops the matrix across a
        # decode/encode, so tagging the encode input does not survive. Instead encode
        # first, then attach the matrix in a stream-copy pass via the input-side
        # -display_rotation, which ffprobe then reports as Display Matrix side data.
        encode_target = out if rotate is None else tmp_path / f"prerot-{name}"
        cmd += [str(encode_target)]
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        if rotate is not None:
            subprocess.run(
                [
                    runtime.ffmpeg_path,
                    "-y",
                    "-display_rotation:v:0",
                    str(rotate),
                    "-i",
                    str(encode_target),
                    "-map",
                    "0",
                    "-c",
                    "copy",
                    str(out),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        return out

    return _make


def _mapped_port(container_name: str) -> int:
    """The host port podman bound to the container's ``5432/tcp``."""
    result = subprocess.run(
        ["podman", "port", container_name, "5432/tcp"],
        check=True,
        capture_output=True,
        text=True,
    )
    # e.g. "0.0.0.0:34567\n"
    return int(result.stdout.strip().rsplit(":", 1)[-1])


def _wait_until_ready(url: str, *, timeout_s: float) -> None:
    """Poll ``url`` with real connection attempts until Postgres accepts one."""
    # psycopg speaks plain ``postgresql://``; the SQLAlchemy ``+psycopg`` driver
    # suffix is only meaningful to ``create_engine``.
    raw_url = url.replace("postgresql+psycopg://", "postgresql://", 1)
    deadline = time.monotonic() + timeout_s
    last_exc: Optional[Exception] = None
    while time.monotonic() < deadline:
        try:
            with psycopg.connect(raw_url, connect_timeout=2) as conn:
                conn.execute("SELECT 1")
            return
        except psycopg.OperationalError as exc:
            last_exc = exc
            time.sleep(0.2)
    raise TimeoutError(f"Postgres at {url} not ready after {timeout_s}s") from last_exc


@pytest.fixture(scope="session")
def postgres_container() -> Iterator[str]:
    """Start a throwaway podman Postgres container; yield its ``DATABASE_URL``.

    Session-scoped: one container serves every ``requires_db``-marked test. Skips
    (rather than fails) the requesting test if podman is unavailable or the
    container cannot be started, so the persistence suite degrades gracefully on a
    host without podman rather than blocking the rest of the run.
    """
    if shutil.which("podman") is None:
        pytest.skip("podman not available on PATH")

    name = f"auto-reel-ng-test-pg-{uuid.uuid4().hex[:8]}"
    password = "test"
    database = "auto_reel_ng_test"
    user = "postgres"
    try:
        subprocess.run(
            [
                "podman",
                "run",
                "-d",
                "--rm",
                "--name",
                name,
                "-e",
                f"POSTGRES_PASSWORD={password}",
                "-e",
                f"POSTGRES_DB={database}",
                "-p",
                "127.0.0.1::5432",
                _POSTGRES_IMAGE,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        pytest.skip(f"could not start podman Postgres container: {exc}")

    try:
        port = _mapped_port(name)
        url = f"postgresql+psycopg://{user}:{password}@127.0.0.1:{port}/{database}"
        _wait_until_ready(url, timeout_s=_POSTGRES_READY_TIMEOUT_S)
        yield url
    finally:
        subprocess.run(["podman", "stop", "-t", "2", name], capture_output=True, text=True)


@pytest.fixture
def fresh_database_url(postgres_container: str) -> Iterator[str]:
    """A uniquely named, guaranteed-empty database on the shared test container.

    For tests (migrations, drift) that must run schema DDL from a clean slate
    without colliding with tables other fixtures build on the container's default
    database (e.g. a ``create_all``-provisioned ``jobs`` table).
    """
    admin_url = postgres_container.replace("postgresql+psycopg://", "postgresql://", 1)
    db_name = f"test_{uuid.uuid4().hex[:12]}"
    with psycopg.connect(admin_url, autocommit=True) as conn:
        conn.execute(f'CREATE DATABASE "{db_name}"')
    try:
        base_url = postgres_container.rsplit("/", 1)[0]
        yield f"{base_url}/{db_name}"
    finally:
        with psycopg.connect(admin_url, autocommit=True) as conn:
            conn.execute(f'DROP DATABASE IF EXISTS "{db_name}" WITH (FORCE)')


@pytest.fixture(scope="session")
def jobs_schema_engine(postgres_container: str) -> Iterator:
    """Session-scoped engine with the ``jobs`` schema built via ``create_all`` (D-P7).

    The podman test fixture provisions schema this way for speed; production/dev
    provisioning goes through Alembic migrations instead (see
    ``test_persistence_migrations.py``, which asserts the two agree).
    """
    engine = make_engine(postgres_container)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def jobs_session_factory(jobs_schema_engine) -> sessionmaker:
    """A session factory bound to the shared schema, with an empty ``jobs`` table.

    Function-scoped so every job-store test starts from a clean table without
    paying the container/schema startup cost more than once per session.
    """
    with jobs_schema_engine.begin() as conn:
        conn.execute(Job.__table__.delete())
    return make_session_factory(jobs_schema_engine)


@pytest.fixture
def job_store(jobs_session_factory: sessionmaker) -> JobStore:
    """A :class:`JobStore` bound to a fresh, empty ``jobs`` table."""
    return JobStore(jobs_session_factory)
