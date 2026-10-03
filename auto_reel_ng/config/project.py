"""Project ``config.yaml``: shared defaults and the D-2 layering.

A project root may carry a ``config.yaml`` declaring a default ``look`` map, the
ingest ``layout`` name, default ``input``/``output`` paths, the clip ``sort`` rule
(:class:`~auto_reel_ng.reel.document.ClipOrder`), a ``database.url``
override consumed by :mod:`auto_reel_ng.persistence.config`, a ``worker`` map
consumed by :mod:`auto_reel_ng.scheduler.config`, an ``api`` map consumed by
:mod:`auto_reel_ng.api.settings`, a ``thumbnails`` map consumed by
:mod:`auto_reel_ng.thumbs.settings`, and a ``proxies`` map consumed by
:mod:`auto_reel_ng.proxies.settings`. Every field is optional: a
missing file yields all-defaults (tolerated), while malformed YAML or a
wrong-typed field fails loud (engine convention). The loader raises only
:class:`ConfigError` for file content: a failure of the YAML load itself, a string that cannot be
encoded as UTF-8, an integer too large to print, a structure that refers to itself and, under
``look``, a key that is not a string are all refused with the key path, before any field is read.

Layered resolution (decision **D-2 / D-CLI2**): folder/layout seed ->
``config.yaml`` -> event ``reel.yaml`` -> CLI overrides, each later layer winning.
The ``look`` map is composed here into the ``look_defaults`` passed to
:func:`~auto_reel_ng.event.resolution.resolve`, which then layers the event
``reel.yaml`` ``look`` over it opaquely (D-J) — so an event setting wins over the
project default while a project default with no event override carries through.
The map is treated opaquely; this layer never interprets its inner keys.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, Mapping, Optional

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from ..errors import EngineError
from ..event.discovery import DEFAULT_CLIP_ORDER, ClipOrder, SortMethod
from ..reel.values import find_lone_surrogate, find_non_str_key

logger = logging.getLogger(__name__)

#: The project config file name, read from the project root the layout walks.
CONFIG_FILENAME = "config.yaml"


class ConfigError(EngineError):
    """A project ``config.yaml`` was malformed or carried a wrong-typed field."""


@dataclass(frozen=True)
class ProjectConfig:
    """Project-level shared defaults (every field optional, D-2)."""

    look: Mapping[str, object] = field(default_factory=dict)
    layout: Optional[str] = None
    input_dir: Optional[Path] = None
    output_dir: Optional[Path] = None
    database_url: Optional[str] = None
    #: The job-scheduler worker's ``worker.*`` settings (opaque, like ``look``); see
    #: :func:`auto_reel_ng.scheduler.config.resolve_worker_config`.
    worker: Mapping[str, object] = field(default_factory=dict)
    #: The API service's ``api.*`` settings (opaque, like ``worker``); see
    #: :func:`auto_reel_ng.api.settings.resolve_api_settings`.
    api: Mapping[str, object] = field(default_factory=dict)
    #: The clip thumbnails' ``thumbnails.*`` settings (opaque, like ``worker``); see
    #: :func:`auto_reel_ng.thumbs.settings.resolve_thumbnail_settings`.
    thumbnails: Mapping[str, object] = field(default_factory=dict)
    #: The clip proxies' ``proxies.*`` settings (opaque, like ``thumbnails``); see
    #: :func:`auto_reel_ng.proxies.settings.resolve_proxy_settings`.
    proxies: Mapping[str, object] = field(default_factory=dict)
    #: The order clips enter a document in (seeding and NEW-clip adoption).
    sort: ClipOrder = DEFAULT_CLIP_ORDER


def load_project_config(root: Path) -> ProjectConfig:
    """Load ``<root>/config.yaml`` if present; tolerate absence, fail loud on malformed."""
    config_path = Path(root) / CONFIG_FILENAME
    if not config_path.exists():
        logger.debug("No %s at %s; using built-in defaults", CONFIG_FILENAME, root)
        return ProjectConfig()
    try:
        text = config_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"{config_path}: cannot read config: {exc}") from exc
    except UnicodeDecodeError as exc:
        raise ConfigError(f"{config_path}: config is not valid UTF-8: {exc}") from exc
    return loads_project_config(text, source=str(config_path))


def loads_project_config(text: str, *, source: str = "<string>") -> ProjectConfig:
    """Parse a ``config.yaml`` document from a string into a :class:`ProjectConfig`."""
    yaml = YAML(typ="safe")
    try:
        data = yaml.load(text)
    except YAMLError as exc:
        raise ConfigError(f"{source}: malformed YAML: {exc}") from exc
    except Exception as exc:  # pylint: disable=broad-exception-caught
        # ruamel's safe constructors leak builtin errors for a well-formed node they cannot
        # build (ValueError: 2024-02-30, KeyError: !!bool maybe), and RecursionError for a
        # document nested too deeply; none is a YAMLError, all are the file's fault.
        # A KeyError's text is only the quoted token, so the type name goes in front of it.
        reason = f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__
        raise ConfigError(f"{source}: malformed YAML: {reason}") from exc

    if data is None:
        return ProjectConfig()
    if not isinstance(data, Mapping):
        raise ConfigError(
            f"{source}: top-level config must be a mapping, got {type(data).__name__}"
        )

    _validate_tree(data, source)
    database = _require_mapping(data.get("database"), "database", source)
    return ProjectConfig(
        look=dict(_require_mapping(data.get("look"), "look", source)),
        layout=_require_str(data.get("layout"), "layout", source),
        input_dir=_require_path(data.get("input"), "input", source),
        output_dir=_require_path(data.get("output"), "output", source),
        database_url=_require_str(database.get("url"), "database.url", source),
        worker=dict(_require_mapping(data.get("worker"), "worker", source)),
        api=dict(_require_mapping(data.get("api"), "api", source)),
        thumbnails=dict(_require_mapping(data.get("thumbnails"), "thumbnails", source)),
        proxies=dict(_require_mapping(data.get("proxies"), "proxies", source)),
        sort=_parse_sort(_require_mapping(data.get("sort"), "sort", source), source),
    )


def _validate_tree(data: Mapping[str, object], source: str) -> None:
    """Refuse content that loads but breaks later, naming the key path (nothing else is read).

    A lone surrogate cannot be printed, logged or sent as JSON; a ``look`` key that is not a
    string (an unquoted date is one) cannot be fingerprinted; an integer past Python's digit
    limit cannot be printed; a structure that contains itself cannot be serialised. Values
    stay uninterpreted otherwise (D-I/D-J).
    """
    # First, because the scans below repr() every key and would raise a bare ValueError on an
    # integer key past the digit limit (the explicit-key syntax ``? 0xfff...`` writes one).
    problem = _find_unusable_structure(data)
    if problem is not None:
        what, path = problem
        raise ConfigError(f"{source}: {path}: {what}")
    surrogate = find_lone_surrogate(data)
    if surrogate is not None:
        raise ConfigError(
            f"{source}: {surrogate or 'document'}: text contains a lone surrogate, which "
            f"cannot be encoded as UTF-8"
        )
    bad_key = find_non_str_key(data.get("look"), root="look")
    if bad_key is not None:
        article = "an" if bad_key.kind[0] in "aeiou" else "a"
        # Safe to print: an integer key too large to print was refused above.
        raise ConfigError(
            f"{source}: {bad_key.path}: key {bad_key.key} is {article} {bad_key.kind}, not a "
            f"string (quote it to keep it as text)"
        )


def _find_unusable_structure(tree: object) -> Optional[tuple[str, str]]:
    """The first ``(problem, path)`` of an unprintable integer or a self-referencing container.

    An iterative depth-first walk, so a deep file cannot exhaust the stack: ``on_path`` holds the
    containers being walked (meeting one again is a cycle), ``done`` the finished ones (a shared
    alias that is not a cycle is walked once).
    """
    on_path: set[int] = set()
    done: set[int] = set()
    path: list[str] = []
    stack: list[tuple[object, Iterator[tuple[str, object]]]] = []

    def enter(node: object) -> None:
        on_path.add(id(node))
        stack.append((node, _children(node)))

    if not isinstance(tree, (Mapping, list)):
        return _check_scalar(tree, "document")
    found = _check_keys(tree, "")
    if found is not None:
        return found
    enter(tree)
    while stack:
        node, children = stack[-1]
        for segment, child in children:
            if isinstance(child, (Mapping, list)):
                if id(child) in on_path:
                    return "the structure refers to itself", _join(path, segment)
                if id(child) not in done:
                    found = _check_keys(child, _join(path, segment))
                    if found is not None:
                        return found
                    path.append(segment)
                    enter(child)
                    break
            else:
                found = _check_scalar(child, _join(path, segment))
                if found is not None:
                    return found
        else:
            stack.pop()
            on_path.discard(id(node))
            done.add(id(node))
            if path:
                path.pop()
    return None


def _check_keys(node: object, path: str) -> Optional[tuple[str, str]]:
    """The first mapping key of ``node`` that is an integer too large to print (tuple keys too)."""
    if not isinstance(node, Mapping):
        return None
    for key in node:
        if _unprintable_key(key):
            return "integer key is too large to print", _join([path], "[<int key>]")
    return None


def _unprintable_key(key: object) -> bool:
    if isinstance(key, (tuple, frozenset)):
        return any(_unprintable_key(item) for item in key)
    return _check_scalar(key, "") is not None


def _children(node: object) -> Iterator[tuple[str, object]]:
    if isinstance(node, Mapping):
        for key, value in node.items():
            yield _segment(key), value
    elif isinstance(node, list):
        for index, item in enumerate(node):
            yield f"[{index}]", item


def _segment(key: object) -> str:
    """A path segment for a mapping key: ``.name``, or ``['odd key']`` (repr-escaped)."""
    if isinstance(key, str):
        return f".{key}" if key.isidentifier() else f"[{key!r}]"
    return f"[<{type(key).__name__} key>]"  # never repr an int key: it may be the unprintable one


def _join(path: list[str], segment: str) -> str:
    text = "".join(path) + segment
    return text[1:] if text.startswith(".") else text


def _check_scalar(value: object, path: str) -> Optional[tuple[str, str]]:
    if isinstance(value, int) and not isinstance(value, bool):
        try:
            str(value)
        except ValueError:
            return "integer is too large to print", path
    return None


def _parse_sort(sort: Mapping[str, object], source: str) -> ClipOrder:
    """The ``sort: {method, reverse}`` rule; absent fields take auto-reel's default."""
    method_value = _require_str(sort.get("method"), "sort.method", source)
    reverse = sort.get("reverse", DEFAULT_CLIP_ORDER.reverse)
    if method_value is None:
        method = DEFAULT_CLIP_ORDER.method
    else:
        # ``custom`` names specific files, so it is an event's own rule, never the library's.
        allowed_methods = [m for m in SortMethod if m is not SortMethod.CUSTOM]
        if method_value not in allowed_methods:
            allowed = ", ".join(m.value for m in allowed_methods)
            raise ConfigError(
                f"{source}: 'sort.method' must be one of {allowed}, got {method_value!r}"
            )
        method = SortMethod(method_value)
    if not isinstance(reverse, bool):
        raise ConfigError(
            f"{source}: 'sort.reverse' must be a boolean, got {type(reverse).__name__}"
        )
    return ClipOrder(method=method, reverse=reverse)


def resolve_look_defaults(config: ProjectConfig) -> dict[str, object]:
    """The ``look_defaults`` map for :func:`resolve`: the project ``look`` (D-2).

    ``resolve()`` layers the event ``reel.yaml`` ``look`` over this opaquely (D-J):
    an event setting wins over the project default, and a project default with no
    event override carries through unchanged.
    """
    return dict(config.look)


def default_output_dir(project_root: Path) -> Path:
    """The output directory used when neither ``-o`` nor ``config.yaml`` sets one.

    ``<parent>/<root-name>-output``: a sibling of the project root, outside every
    ingest layout's walk, so rendered movies filed into year folders are never
    scanned back in as events. The root is resolved first so ``.`` still yields a
    named sibling.
    """
    root = Path(project_root).resolve()
    return root.parent / f"{root.name}-output"


def _require_mapping(value: object, key: str, source: str) -> Mapping[str, object]:
    """Return ``value`` as a mapping, defaulting missing to empty; else fail loud."""
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ConfigError(f"{source}: {key!r} must be a mapping, got {type(value).__name__}")
    return value


def _require_str(value: object, key: str, source: str) -> Optional[str]:
    """Return ``value`` as a string (None passes through); else fail loud."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ConfigError(f"{source}: {key!r} must be a string, got {type(value).__name__}")
    return value


def _require_path(value: object, key: str, source: str) -> Optional[Path]:
    """Return ``value`` as a path (None passes through); else fail loud."""
    text = _require_str(value, key, source)
    return Path(text) if text is not None else None
