"""Proxies are a second artifact made beside the render, never a render or staleness input.

An AST walk fails if the packages that decide what is rendered, whether a render is stale or
what the database holds ever import :mod:`auto_reel_ng.proxies` (HLD D-21: no
``RENDER_GRAPH_VERSION`` bump, no fingerprint input, never Postgres). ``scheduler/`` and
``api/`` are not listed: the proxy job, the read model and the media routes are their own
changes and wrap the engine function by design.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[1] / "auto_reel_ng"
GUARDED = ("staleness", "render", "persistence")


def imports_proxies(source: str, module: str) -> list[str]:
    """The import statements in ``source`` (module ``module``) that reach the proxies package."""
    package = module.split(".")[:-1]
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found += [a.name for a in node.names if _is_proxies(a.name.split("."))]
        elif isinstance(node, ast.ImportFrom):
            base = (
                node.module.split(".")
                if node.level == 0 and node.module
                else package[: len(package) - node.level + 1] + (node.module or "").split(".")
            )
            if node.level == 0 and not (node.module or "").startswith("auto_reel_ng"):
                continue
            if _is_proxies([part for part in base if part]) or any(
                a.name == "proxies" and _ends_at_package(base) for a in node.names
            ):
                found.append(ast.unparse(node))
    return found


def _is_proxies(parts: list[str]) -> bool:
    return parts[:2] == ["auto_reel_ng", "proxies"]


def _ends_at_package(parts: list[str]) -> bool:
    return [part for part in parts if part] == ["auto_reel_ng"]


@pytest.mark.parametrize("name", GUARDED)
def test_the_guarded_packages_never_import_proxies(name: str) -> None:
    offenders = {}
    for path in sorted((PACKAGE / name).rglob("*.py")):
        module = ".".join(path.relative_to(PACKAGE.parent).with_suffix("").parts)
        found = imports_proxies(path.read_text(encoding="utf-8"), module)
        if found:
            offenders[str(path.relative_to(PACKAGE))] = found
    assert offenders == {}


@pytest.mark.parametrize(
    ("source", "module"),
    [
        ("from auto_reel_ng.proxies import ensure_proxy", "auto_reel_ng.render.x"),
        ("import auto_reel_ng.proxies.spec", "auto_reel_ng.render.x"),
        ("from ..proxies import ensure_proxy", "auto_reel_ng.render.x"),
        ("from ..proxies.spec import proxy_key", "auto_reel_ng.staleness.fingerprint"),
        ("from .. import proxies", "auto_reel_ng.persistence.x"),
        ("from auto_reel_ng import proxies", "auto_reel_ng.persistence.x"),
    ],
)
def test_the_walk_catches_every_spelling(source: str, module: str) -> None:
    assert imports_proxies(source, module) != []


def test_the_walk_ignores_unrelated_imports() -> None:
    source = "from ..thumbs import thumbnail_for\nimport json\nfrom . import proxies_not_here\n"
    assert imports_proxies(source, "auto_reel_ng.render.x") == []
