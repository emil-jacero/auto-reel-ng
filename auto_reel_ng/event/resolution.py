"""Resolve a :class:`ReelDocument` into a fully-explicit :class:`RenderPlan`.

Resolution is the document -> plan half of decision **D-H**: it materializes every
chapter and clip in document order, applies per-clip properties (cut spans,
rotate, exclude), marks each chapter's title clip, and fills ``look`` from the
server-config defaults. It is **deterministic** — order follows the document's
explicit lists and never depends on dict iteration order — and is derived from
the document alone (plus optional clip content facts), never by re-reading folder
structure for membership or order.
"""

from __future__ import annotations

from typing import Iterable, Mapping, Optional

from ..errors import ReelError
from ..probe.metadata import ClipMetadata
from ..reel.card import ChapterCard
from ..reel.document import ClipProperties, ReelDocument, is_excluded
from .plan import RenderPlan, ResolvedChapter, ResolvedClip


def resolve(
    document: ReelDocument,
    *,
    look_defaults: Optional[Mapping[str, object]] = None,
    clip_facts: Optional[Mapping[str, ClipMetadata]] = None,
) -> RenderPlan:
    """Resolve ``document`` into a render plan.

    ``look_defaults`` is the server-level ``config.yaml`` default ``look`` map
    (absent/partial tolerated, D-J). ``clip_facts`` optionally supplies probed
    :class:`ClipMetadata` keyed by identity; when given, every included clip must
    have facts or resolution fails loud (the plan never references an unprobeable
    clip). Both ``look`` maps are treated opaquely (D-I).
    """
    chapters = tuple(
        _resolve_chapter(chapter.name, chapter.clips, document.clips, clip_facts, chapter.card)
        for chapter in document.chapters
    )
    look = _merge_look(look_defaults, document.look)
    return RenderPlan(metadata=document.metadata, look=look, chapters=chapters)


def _resolve_chapter(
    name: str,
    refs: Iterable,
    clip_props: Mapping[str, ClipProperties],
    clip_facts: Optional[Mapping[str, ClipMetadata]],
    card: Optional[ChapterCard] = None,
) -> ResolvedChapter:
    """Materialize one chapter: drop excluded clips, then mark the title clip."""
    included: list[tuple[str, ClipProperties]] = []
    for ref in refs:
        if is_excluded(clip_props, ref.identity):
            continue
        props = clip_props.get(ref.identity, ClipProperties())
        if clip_facts is not None and ref.identity not in clip_facts:
            raise ReelError(
                f"resolve: clip {ref.identity!r} in chapter {name!r} has no probed "
                f"metadata; cannot include an unprobeable clip in the plan"
            )
        included.append((ref.identity, props))

    title_identity = _resolve_title(included)
    clips = tuple(
        ResolvedClip(
            identity=identity,
            cut_spans=props.trims,
            rotate=props.rotate,
            is_title=(identity == title_identity),
        )
        for identity, props in included
    )
    return ResolvedChapter(name=name, clips=clips, card=card)


def _resolve_title(included: list[tuple[str, ClipProperties]]) -> Optional[str]:
    """Pick the chapter's title clip: first included clip unless overridden (4.4).

    An explicit ``title: true`` wins (first such clip in order). Otherwise the
    first included clip not marked ``title: false`` is the baseline title. If
    every included clip is ``title: false`` (or the chapter is empty), there is no
    title clip.
    """
    for identity, props in included:
        if props.title is True:
            return identity
    for identity, props in included:
        if props.title is not False:  # title is None (no override)
            return identity
    return None


def _merge_look(
    defaults: Optional[Mapping[str, object]],
    doc_look: Mapping[str, object],
) -> dict[str, object]:
    """Top-level shallow-merge of the document ``look`` over the defaults (4.5).

    A document top-level key wins over the same key in the defaults; default-only
    keys are carried through; an absent/partial defaults map is tolerated.
    """
    merged: dict[str, object] = dict(defaults or {})
    merged.update(doc_look or {})
    return merged
