"""The compose stack's worker prepares proxies into its mounted cache (proxy-job).

The default proxy cache is ``$XDG_CACHE_HOME/auto-reel/proxies``; the compose files must give
both ``server`` and ``worker`` ``XDG_CACHE_HOME=/data/cache`` and bind-mount that directory, or
the worker's proxies would land in the container's writable layer and the server (which reads
them) would look somewhere else.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from auto_reel_ng.proxies import default_cache_dir

ROOT = Path(__file__).resolve().parents[1]
CACHE = "/data/cache"


class _ComposeLoader(yaml.SafeLoader):
    """Safe YAML plus compose's ``!reset`` and ``!override`` tags (read as plain values)."""


def _plain(loader: yaml.SafeLoader, tag_suffix: str, node: yaml.Node) -> Any:
    """``!reset []`` and ``!override ...`` read as the plain value they wrap."""
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node, deep=True)
    if isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node, deep=True)
    return loader.construct_scalar(node)


_ComposeLoader.add_multi_constructor("!", _plain)


def load(name: str) -> dict[str, Any]:
    document = yaml.load((ROOT / name).read_text(encoding="utf-8"), Loader=_ComposeLoader)
    assert isinstance(document, dict)
    return document


def environment(service: dict[str, Any]) -> dict[str, str]:
    env = service.get("environment", {})
    if isinstance(env, list):
        return dict(item.split("=", 1) for item in env)
    return {key: str(value) for key, value in env.items()}


def mounts(service: dict[str, Any]) -> list[str]:
    """The container-side paths of the service's volumes (``${VAR:-default}`` has colons too)."""
    paths = (
        re.search(r":(/[^:]+)(?::\w+)?$", str(volume)) for volume in service.get("volumes", [])
    )
    return [found.group(1) for found in paths if found is not None]


@pytest.mark.parametrize("service", ["server", "worker"])
def test_the_base_compose_file_gives_the_service_the_cache_variable_and_mount(
    service: str,
) -> None:
    definition = load("compose.yaml")["services"][service]

    assert environment(definition)["XDG_CACHE_HOME"] == CACHE
    assert CACHE in mounts(definition)


def test_the_cpu_overlay_does_not_take_the_workers_cache_away() -> None:
    """``compose.cpu.yaml`` is merged over the base: it must not reset what carries the cache."""
    worker = load("compose.cpu.yaml")["services"]["worker"]

    assert "environment" not in worker and "volumes" not in worker
    assert "env_file" not in worker


def test_the_default_proxy_cache_under_that_variable_is_the_mounted_directory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    definition = load("compose.yaml")["services"]["worker"]
    monkeypatch.setenv("XDG_CACHE_HOME", environment(definition)["XDG_CACHE_HOME"])

    assert default_cache_dir() == Path("/data/cache/auto-reel/proxies")
    assert default_cache_dir().is_relative_to(
        Path(mounts(definition)[mounts(definition).index(CACHE)])
    )
