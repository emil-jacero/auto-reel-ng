"""The dev environment must carry the client Starlette's ``TestClient`` prefers.

Starlette's ``TestClient`` imports ``httpx2`` and, when it is absent, falls back to ``httpx`` with
a ``StarletteDeprecationWarning`` (a later release may drop the fallback). The warning fires once,
at import, and pytest has already imported ``starlette.testclient`` by the time a test runs, so
the check imports it in a fresh interpreter instead. The warning is a ``UserWarning`` subclass in
Starlette 1.7, so a ``-W error::DeprecationWarning`` flag would not catch it: the filter is
installed by class inside the child interpreter.
"""

from __future__ import annotations

import subprocess
import sys

STRICT_TESTCLIENT_IMPORT = """
import warnings
from starlette.exceptions import StarletteDeprecationWarning

warnings.simplefilter("error", StarletteDeprecationWarning)
import starlette.testclient
"""


def _run(code: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)


def test_testclient_imports_without_the_httpx_fallback_warning() -> None:
    result = _run(STRICT_TESTCLIENT_IMPORT)
    assert result.returncode == 0, (
        "starlette.testclient fell back to httpx; install httpx2 "
        '(`pip install -e ".[dev]"`):\n' + result.stderr
    )


def test_httpx_stays_available_for_the_live_server_tests() -> None:
    result = _run("import httpx")
    assert result.returncode == 0, result.stderr
