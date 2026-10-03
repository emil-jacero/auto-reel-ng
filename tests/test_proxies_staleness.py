"""Proxies never change a render or a staleness verdict (clip-proxies, D-21).

A proxy lives outside the library, so making, deleting or replacing one leaves the staleness
fingerprint, the gate's verdict and the render manifest alone; an editorial cut edit changes
the verdict and leaves the proxy current. No ffmpeg is needed: the fake runtime of the
``ensure_proxy`` tests builds the entry.
"""

from __future__ import annotations

import shutil
from dataclasses import replace
from pathlib import Path

import pytest
from test_proxies_ensure import Env, enabled_loggers  # noqa: F401  (autouse fixture re-exported)

from auto_reel_ng.reel.document import (
    Chapter,
    ClipProperties,
    ClipRef,
    Metadata,
    ReelDocument,
    Trim,
)
from auto_reel_ng.staleness.fingerprint import compute_fingerprint, engine_identity
from auto_reel_ng.staleness.gate import evaluate
from auto_reel_ng.staleness.manifest import manifest_path, write_manifest

FFMPEG_VERSION = (7, 1)


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Env:
    return Env(tmp_path, monkeypatch)


def _document(env: Env, *, cut: bool = False) -> ReelDocument:
    document = ReelDocument(
        metadata=Metadata(title="Party"),
        chapters=(Chapter(name="", clips=(ClipRef(env.clip.name),)),),
    )
    if cut:
        document = replace(
            document, clips={env.clip.name: ClipProperties(trims=(Trim(1.0, 2.0, "manual"),))}
        )
    return document


def _fingerprint(env: Env, *, cut: bool = False):  # type: ignore[no-untyped-def]
    return compute_fingerprint(
        _document(env, cut=cut),
        event_dir=env.clip.parent,
        look_defaults={},
        ffmpeg_version=FFMPEG_VERSION,
    )


def _rendered_event(env: Env):  # type: ignore[no-untyped-def]
    """The event is rendered: a manifest of the current fingerprint and its movie."""
    fingerprint = _fingerprint(env)
    write_manifest(
        env.clip.parent,
        fingerprint,
        output="Party.mp4",
        engine_identity=engine_identity(FFMPEG_VERSION),
    )
    movie = env.clip.parent.parent / "out" / "Party.mp4"  # outputs are outside the event folder
    movie.parent.mkdir(exist_ok=True)
    movie.write_bytes(b"rendered")
    return fingerprint, movie


def test_making_and_deleting_proxies_leaves_the_event_fresh(env: Env) -> None:
    fingerprint, movie = _rendered_event(env)
    manifest_before = manifest_path(env.clip.parent).read_bytes()
    assert evaluate(env.clip.parent, movie, fingerprint).stale is False

    env.ensure()

    assert _fingerprint(env) == fingerprint  # identical before and after the proxy run
    assert evaluate(env.clip.parent, movie, _fingerprint(env)).stale is False
    assert manifest_path(env.clip.parent).read_bytes() == manifest_before

    shutil.rmtree(env.cache)  # delete the whole cache

    assert evaluate(env.clip.parent, movie, _fingerprint(env)).stale is False


def test_a_cut_edit_makes_the_event_stale_and_leaves_the_proxy_current(env: Env) -> None:
    fingerprint, movie = _rendered_event(env)
    entry = env.ensure()

    edited = _fingerprint(env, cut=True)

    assert evaluate(env.clip.parent, movie, edited).stale is True  # the render must be redone
    again = env.ensure()  # but the proxy is the same complete entry
    assert again.generated is False and again.directory == entry.directory
    assert len(env.runtime.runs) == 1
