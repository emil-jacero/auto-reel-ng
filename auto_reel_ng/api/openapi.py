"""The OpenAPI schema as a build-time artifact (D-8, §4.10).

The client's TypeScript types are generated from ``web/openapi.json``, which is a
committed dump of this application's own schema. Producing it here — rather than
against a running service — keeps type generation free of Postgres and of a live
process: :func:`~auto_reel_ng.persistence.engine.make_engine` is lazy, so an app
can be built (and its schema derived from the routes' declared ``response_model``s)
without a reachable database.

The settings below are throwaway: no route is called, so the project root and the
database URL are never dereferenced. They are fixed rather than resolved so the
dump is byte-identical on every machine — which is what lets the drift test in
``tests/test_api_openapi.py`` be a comparison rather than a heuristic.

Regenerate the committed artifact with::

    .venv/bin/python -m auto_reel_ng.api.openapi > web/openapi.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict

from ..event.discovery import DEFAULT_CLIP_ORDER
from .app import create_app
from .settings import DEFAULT_HOST, DEFAULT_POLL_INTERVAL_S, DEFAULT_PORT, ApiSettings

#: The database URL the throwaway app is built with. Never connected to — it exists
#: only because ``create_app`` needs an engine, and the engine is lazy.
SCHEMA_DUMP_DATABASE_URL = "postgresql+psycopg://schema:schema@127.0.0.1:1/schema"

#: The project root the throwaway app is built with. Never walked — no route runs.
SCHEMA_DUMP_PROJECT_ROOT = Path("/nonexistent")


def schema_dump_settings() -> ApiSettings:
    """Fixed, machine-independent settings for building the schema-dump app."""
    return ApiSettings(
        project_root=SCHEMA_DUMP_PROJECT_ROOT,
        walk_root=SCHEMA_DUMP_PROJECT_ROOT,
        layout_name="year-event",
        output_dir=SCHEMA_DUMP_PROJECT_ROOT / "output",
        host=DEFAULT_HOST,
        port=DEFAULT_PORT,
        poll_interval=DEFAULT_POLL_INTERVAL_S,
        database_url=SCHEMA_DUMP_DATABASE_URL,
        clip_order=DEFAULT_CLIP_ORDER,
    )


def build_openapi_schema() -> Dict[str, Any]:
    """Return the application's OpenAPI schema, contacting nothing."""
    app = create_app(schema_dump_settings())
    return app.openapi()


def render_openapi_schema() -> str:
    """Return the schema serialized exactly as ``web/openapi.json`` stores it."""
    return json.dumps(build_openapi_schema(), indent=2, ensure_ascii=False) + "\n"


def main() -> None:
    """Write the schema to stdout (``python -m auto_reel_ng.api.openapi``)."""
    sys.stdout.write(render_openapi_schema())


if __name__ == "__main__":  # pragma: no cover
    main()


__all__ = [
    "build_openapi_schema",
    "render_openapi_schema",
    "schema_dump_settings",
    "main",
    "SCHEMA_DUMP_DATABASE_URL",
    "SCHEMA_DUMP_PROJECT_ROOT",
]
