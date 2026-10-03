"""Shared ``Job``/``ReelDocument`` -> pydantic conversions used by more than one route."""

from __future__ import annotations

import logging
from typing import Iterable

from ..persistence.models import JobKind
from ..reel.document import ReelDocument
from .schemas import (
    ChapterBody,
    ClipPropertiesBody,
    EditorialDocumentBody,
    JobOut,
    MetadataBody,
    TrimBody,
)

logger = logging.getLogger(__name__)

_KNOWN_KINDS = frozenset(kind.value for kind in JobKind)


def document_to_body(document: ReelDocument) -> EditorialDocumentBody:
    """Convert a validated :class:`ReelDocument` to its wire shape (editorial-write echo)."""
    return EditorialDocumentBody(
        metadata=MetadataBody(
            title=document.metadata.title,
            date=document.metadata.date,
            location=document.metadata.location,
            description=document.metadata.description,
        ),
        look=dict(document.look),
        chapters=[
            ChapterBody(name=chapter.name, clips=[ref.identity for ref in chapter.clips])
            for chapter in document.chapters
        ],
        clips={
            identity: ClipPropertiesBody(
                trims=[
                    TrimBody(in_=trim.start, out=trim.end, reason=trim.reason)  # type: ignore[call-arg]
                    for trim in props.trims
                ],
                title=props.title,
                rotate=props.rotate,
                exclude=props.exclude,
            )
            for identity, props in document.clips.items()
        },
        ignore=list(document.ignore),
    )


def job_to_out(job: object) -> JobOut:
    """Convert a store ``Job`` row (or a duck-typed stand-in, for hub tests) to :class:`JobOut`."""
    return JobOut(
        id=job.id,  # type: ignore[attr-defined]
        kind=job.kind,  # type: ignore[attr-defined]
        status=job.status.value,  # type: ignore[attr-defined]
        event_dir=job.event_dir,  # type: ignore[attr-defined]
        project_root=job.project_root,  # type: ignore[attr-defined]
        device=job.device,  # type: ignore[attr-defined]
        progress=job.progress,  # type: ignore[attr-defined]
        worker_id=job.worker_id,  # type: ignore[attr-defined]
        cancel_requested=job.cancel_requested,  # type: ignore[attr-defined]
        requeue_count=job.requeue_count,  # type: ignore[attr-defined]
        force=job.force,  # type: ignore[attr-defined]
        fingerprint=job.fingerprint,  # type: ignore[attr-defined]
        error=job.error,  # type: ignore[attr-defined]
        created_at=job.created_at,  # type: ignore[attr-defined]
        started_at=job.started_at,  # type: ignore[attr-defined]
        finished_at=job.finished_at,  # type: ignore[attr-defined]
    )


def jobs_to_out(jobs: Iterable[object]) -> list[JobOut]:
    """Convert the rows a list or the live feed reports, leaving out any of an unknown kind.

    ``jobs.kind`` is free text on purpose (``job-kind``): a row written by another build can
    name a kind this one does not, and the worker fails such a row with a reason. The wire's
    ``kind`` is the closed enumeration, so that row cannot be described. One such row, even
    an old failed one, must not take the whole list or the live feed down: it is left out
    and logged, and every other job is still reported.
    """
    described: list[JobOut] = []
    for job in jobs:
        kind = job.kind  # type: ignore[attr-defined]
        if kind not in _KNOWN_KINDS:
            logger.warning(
                "job %s has the unknown kind %r and is not reported",
                job.id,  # type: ignore[attr-defined]
                kind,
            )
            continue
        described.append(job_to_out(job))
    return described


__all__ = ["document_to_body", "job_to_out", "jobs_to_out"]
