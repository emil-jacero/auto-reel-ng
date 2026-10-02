"""The project context shared by every CLI command that walks a project.

:func:`project_context` resolves the project root, ``config.yaml``, layout, walked
root and output directory for one invocation and enumerates its events. It lives
here, not in :mod:`.commands`, so ``scan``, ``render``, ``thumbs`` and the rest import
a public name, and so the output-directory check (``project-config``: the output never
lies inside the walked root) is made in one place, the same one the API settings call.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import List

from ..api.settings import require_output_outside_walk_root
from ..config import ProjectConfig, default_output_dir, load_project_config
from ..ingest import DEFAULT_LAYOUT, EventRef, get_layout


@dataclass(frozen=True)
class ProjectContext:
    """The resolved settings for one CLI invocation (layout, paths, events)."""

    project_root: Path
    walk_root: Path
    output_dir: Path
    layout_name: str
    config: ProjectConfig
    events: List[EventRef]


def resolve_project_root(args: argparse.Namespace) -> Path:
    """Resolve the project root positional arg (shared by every command, D-CLI2)."""
    project_root = Path(args.root).resolve() if args.root else Path.cwd()
    if not project_root.is_dir():
        raise FileNotFoundError(
            f"project root does not exist or is not a directory: {project_root}"
        )
    return project_root


def project_context(args: argparse.Namespace) -> ProjectContext:
    """Resolve the project root, config, layout, paths, and enumerate events.

    Precedence (D-CLI2): a CLI flag wins over ``config.yaml``, which wins over the
    built-in default. ``config.yaml`` is read from the project root the layout walks.
    An output directory equal to or inside the walked root raises
    :class:`~auto_reel_ng.config.ConfigError` before anything is walked.
    """
    project_root = resolve_project_root(args)

    config = load_project_config(project_root)
    walk_root = (project_root / config.input_dir) if config.input_dir else project_root

    if args.output:
        output_dir = Path(args.output)
    elif config.output_dir:
        output_dir = project_root / config.output_dir
    else:
        output_dir = default_output_dir(project_root)
    require_output_outside_walk_root(output_dir, walk_root, project_root)

    layout_name = args.layout or config.layout or DEFAULT_LAYOUT
    layout = get_layout(layout_name)
    years = args.years  # a tuple parsed by the CLI, or None
    events = list(layout(walk_root, years))

    return ProjectContext(
        project_root=project_root,
        walk_root=walk_root,
        output_dir=output_dir,
        layout_name=layout_name,
        config=config,
        events=events,
    )


__all__ = ["ProjectContext", "project_context", "resolve_project_root"]
