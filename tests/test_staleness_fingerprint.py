"""Golden tests for the render fingerprint: stability, sensitivity, device/host
independence, and no-ffprobe (task 1.1)."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import date
from pathlib import Path

import pytest

from auto_reel_ng.reel.card import ChapterCard
from auto_reel_ng.reel.document import (
    Chapter,
    ClipProperties,
    ClipRef,
    Metadata,
    ReelDocument,
    Trim,
)
from auto_reel_ng.staleness import fingerprint as fingerprint_module
from auto_reel_ng.staleness.fingerprint import COMPONENTS, compute_fingerprint, editorial_hash
from auto_reel_ng.staleness.gate import StalenessReason, evaluate
from auto_reel_ng.staleness.manifest import write_manifest

FFMPEG_VERSION = (7, 1)

#: Golden hashes for ``_pinned_document()`` + ``_pinned_event_dir()`` (task 1.1).
#: ENGINE/COMBINED re-pinned for RENDER_GRAPH_VERSION 7 (title-card-model; 6 was clip-rotate-engine, 5 title-card-fonts); EDITORIAL, DEFAULTS and CLIP_SET are as before.
PINNED_EDITORIAL = "cfb295abf2c9f44e4ec05e5634beaf1b9b21235c21d65d0109a944509d848de4"
PINNED_DEFAULTS = "9d1a9bf4432fae2ec90ade0e7eb1552455abd6da0fac7974d78a16d63113f555"
PINNED_CLIP_SET = "b1c642b3cd29b949070b357534bae6e2077121b032f93fa34c7aa0df957b6663"
PINNED_ENGINE = "eff99b0f11f902eeae8a74752f74249d453490ff6a35761780a39b457f117de1"
PINNED_COMBINED = "97dd20729ebb5d6b57c5ee87a5b645d09a2bce6f06044bc03d2ac7158203f230"
#: ``_hash_json({1: "a", "b": "c"})``: the fallback path, which tags every key with its type.
PINNED_FALLBACK = "43ef72b9709103ca8e6941bcc4ae7e089a867d856cf5f73300d83181f52e17e1"


def _document(title: str = "Party") -> ReelDocument:
    return ReelDocument(
        metadata=Metadata(title=title),
        chapters=(Chapter(name="", clips=(ClipRef("clip.mp4"),)),),
    )


def _event_dir(tmp_path: Path, *, content: bytes = b"clip-bytes") -> Path:
    (tmp_path / "clip.mp4").write_bytes(content)
    return tmp_path


def _fingerprint(
    event_dir: Path, *, document=None, look_defaults=None, ffmpeg_version=FFMPEG_VERSION
):
    return compute_fingerprint(
        document if document is not None else _document(),
        event_dir=event_dir,
        look_defaults=look_defaults if look_defaults is not None else {},
        ffmpeg_version=ffmpeg_version,
    )


def test_unchanged_event_is_fingerprint_stable(tmp_path: Path) -> None:
    event_dir = _event_dir(tmp_path)
    first = _fingerprint(event_dir)
    second = _fingerprint(event_dir)
    assert first == second
    assert first.combined == second.combined


def test_editorial_change_moves_only_editorial(tmp_path: Path) -> None:
    event_dir = _event_dir(tmp_path)
    baseline = _fingerprint(event_dir)
    changed = _fingerprint(event_dir, document=_document(title="Different Party"))

    assert changed.editorial != baseline.editorial
    assert changed.combined != baseline.combined
    for name in ("defaults", "clip_set", "engine"):
        assert changed.component(name) == baseline.component(name)


def test_defaults_change_moves_only_defaults(tmp_path: Path) -> None:
    event_dir = _event_dir(tmp_path)
    baseline = _fingerprint(event_dir)
    changed = _fingerprint(event_dir, look_defaults={"transitions": "fade"})

    assert changed.defaults != baseline.defaults
    assert changed.combined != baseline.combined
    for name in ("editorial", "clip_set", "engine"):
        assert changed.component(name) == baseline.component(name)


def test_clip_signal_change_moves_only_clip_set(tmp_path: Path) -> None:
    event_dir = _event_dir(tmp_path, content=b"short")
    baseline = _fingerprint(event_dir)

    (event_dir / "clip.mp4").write_bytes(b"a much longer replacement clip")
    changed = _fingerprint(event_dir)

    assert changed.clip_set != baseline.clip_set
    assert changed.combined != baseline.combined
    for name in ("editorial", "defaults", "engine"):
        assert changed.component(name) == baseline.component(name)


def test_engine_version_bump_moves_only_engine(tmp_path: Path) -> None:
    event_dir = _event_dir(tmp_path)
    baseline = _fingerprint(event_dir)
    changed = _fingerprint(event_dir, ffmpeg_version=(8, 0))

    assert changed.engine != baseline.engine
    assert changed.combined != baseline.combined
    for name in ("editorial", "defaults", "clip_set"):
        assert changed.component(name) == baseline.component(name)


def test_version_2_manifest_is_engine_stale(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # vaapi-pad-fill bumped RENDER_GRAPH_VERSION to 3: an output rendered under
    # version 2 must re-render, for the engine reason alone.
    event_dir = _event_dir(tmp_path)
    output = event_dir / "Party.mp4"
    output.write_bytes(b"rendered")
    with monkeypatch.context() as patch:
        patch.setattr(fingerprint_module, "RENDER_GRAPH_VERSION", 2)
        old = _fingerprint(event_dir)
        identity = fingerprint_module.engine_identity(FFMPEG_VERSION)
    assert identity.startswith("render_graph_version=2 ")
    write_manifest(event_dir, old, output=output.name, engine_identity=identity)

    verdict = evaluate(event_dir, output, _fingerprint(event_dir))

    assert verdict.stale is True
    assert verdict.reasons == (StalenessReason.ENGINE,)


def test_version_3_manifest_is_engine_stale(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # An output rendered under version 3 must re-render, for the engine reason alone.
    event_dir = _event_dir(tmp_path)
    output = event_dir / "Party.mp4"
    output.write_bytes(b"rendered")
    with monkeypatch.context() as patch:
        patch.setattr(fingerprint_module, "RENDER_GRAPH_VERSION", 3)
        old = _fingerprint(event_dir)
        identity = fingerprint_module.engine_identity(FFMPEG_VERSION)
    assert identity.startswith("render_graph_version=3 ")
    assert fingerprint_module.RENDER_GRAPH_VERSION > 3
    write_manifest(event_dir, old, output=output.name, engine_identity=identity)

    verdict = evaluate(event_dir, output, _fingerprint(event_dir))

    assert verdict.stale is True
    assert verdict.reasons == (StalenessReason.ENGINE,)


def test_version_5_manifest_is_engine_stale(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # clip-rotate-engine bumped RENDER_GRAPH_VERSION to 6 (a display rotation is applied by the
    # engine on every profile): an output rendered under version 5 must re-render, for the
    # engine reason alone.
    event_dir = _event_dir(tmp_path)
    output = event_dir / "Party.mp4"
    output.write_bytes(b"rendered")
    with monkeypatch.context() as patch:
        patch.setattr(fingerprint_module, "RENDER_GRAPH_VERSION", 5)
        old = _fingerprint(event_dir)
        identity = fingerprint_module.engine_identity(FFMPEG_VERSION)
    assert identity.startswith("render_graph_version=5 ")
    assert fingerprint_module.RENDER_GRAPH_VERSION >= 6
    write_manifest(event_dir, old, output=output.name, engine_identity=identity)

    verdict = evaluate(event_dir, output, _fingerprint(event_dir))

    assert verdict.stale is True
    assert verdict.reasons == (StalenessReason.ENGINE,)


def test_version_4_manifest_is_engine_stale(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # title-card-fonts bumped RENDER_GRAPH_VERSION to 5: the title card is now drawn from the
    # bundled fonts under the engine's fontconfig, so an output rendered under version 4
    # must re-render, for the engine reason alone.
    event_dir = _event_dir(tmp_path)
    output = event_dir / "Party.mp4"
    output.write_bytes(b"rendered")
    with monkeypatch.context() as patch:
        patch.setattr(fingerprint_module, "RENDER_GRAPH_VERSION", 4)
        old = _fingerprint(event_dir)
        identity = fingerprint_module.engine_identity(FFMPEG_VERSION)
    assert identity.startswith("render_graph_version=4 ")
    assert fingerprint_module.RENDER_GRAPH_VERSION >= 5
    write_manifest(event_dir, old, output=output.name, engine_identity=identity)

    verdict = evaluate(event_dir, output, _fingerprint(event_dir))

    assert verdict.stale is True
    assert verdict.reasons == (StalenessReason.ENGINE,)


def test_version_6_manifest_is_engine_stale_and_the_new_version_gates_fresh(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # title-card-model bumped RENDER_GRAPH_VERSION to 7 (the opening card's text and each card's
    # length and style changed for identical inputs): an output rendered under version 6 must
    # re-render, for the engine reason alone, while the same event under 7 is fresh.
    event_dir = _event_dir(tmp_path)
    output = event_dir / "Party.mp4"
    output.write_bytes(b"rendered")
    with monkeypatch.context() as patch:
        patch.setattr(fingerprint_module, "RENDER_GRAPH_VERSION", 6)
        old = _fingerprint(event_dir)
        old_identity = fingerprint_module.engine_identity(FFMPEG_VERSION)
    assert old_identity.startswith("render_graph_version=6 ")
    assert fingerprint_module.RENDER_GRAPH_VERSION == 7
    new = _fingerprint(event_dir)
    # Only the engine component moved: a card-less document hashes exactly as before.
    assert new.engine != old.engine
    for name in ("editorial", "defaults", "clip_set"):
        assert new.component(name) == old.component(name)

    write_manifest(event_dir, old, output=output.name, engine_identity=old_identity)
    verdict = evaluate(event_dir, output, new)
    assert verdict.stale is True
    assert verdict.reasons == (StalenessReason.ENGINE,)

    write_manifest(
        event_dir,
        new,
        output=output.name,
        engine_identity=fingerprint_module.engine_identity(FFMPEG_VERSION),
    )
    assert evaluate(event_dir, output, new).stale is False


def test_adding_a_card_moves_only_the_editorial_component(tmp_path: Path) -> None:
    event_dir = _event_dir(tmp_path)
    plain = _document()
    carded = ReelDocument(
        metadata=plain.metadata,
        chapters=(
            Chapter(
                name=plain.chapters[0].name,
                clips=plain.chapters[0].clips,
                card=ChapterCard(subtitle="Hos mormor"),
            ),
        ),
    )
    baseline = _fingerprint(event_dir)
    changed = compute_fingerprint(
        carded, event_dir=event_dir, look_defaults={}, ffmpeg_version=FFMPEG_VERSION
    )
    assert changed.editorial != baseline.editorial
    for name in ("defaults", "clip_set", "engine"):
        assert changed.component(name) == baseline.component(name)


def test_device_selection_does_not_move_the_fingerprint(tmp_path: Path) -> None:
    # The fingerprint never takes a profile/device argument at all, so a caller
    # rendering under CPU vs GPU necessarily computes the same value (D-C1).
    event_dir = _event_dir(tmp_path)
    cpu_run = _fingerprint(event_dir)
    gpu_run = _fingerprint(event_dir)
    assert cpu_run.combined == gpu_run.combined


def test_all_components_are_covered() -> None:
    assert set(COMPONENTS) == {"editorial", "defaults", "clip_set", "engine"}


def test_no_probing_occurs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    event_dir = _event_dir(tmp_path)

    def _forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("compute_fingerprint must not shell out to ffmpeg/ffprobe")

    monkeypatch.setattr(subprocess, "run", _forbidden)
    monkeypatch.setattr(subprocess, "Popen", _forbidden)

    _fingerprint(event_dir)  # must not raise


# --- editorial_hash extraction regression (task 1.1, D-R1) -------------------


def _pinned_document() -> ReelDocument:
    """A document exercising every editorial section the hash covers."""
    return ReelDocument(
        metadata=Metadata(
            title="Pinned Party",
            date=date(2026, 8, 31),
            location="Gothenburg",
            description="a fixed document",
        ),
        look={"resolution": "1080p", "fps": 30},
        chapters=(
            Chapter(name="", clips=(ClipRef("clip.mp4"),)),
            Chapter(name="beach", clips=(ClipRef("beach/two.mp4"),)),
        ),
        clips={
            "clip.mp4": ClipProperties(
                trims=(Trim(0.5, 2.25, "black"),), title=True, rotate=90, exclude=False
            )
        },
        ignore=("beach/skip.mp4",),
    )


def _pinned_event_dir(tmp_path: Path) -> Path:
    """An event dir with a fixed size *and* mtime, so ``clip_set`` is pinnable too."""
    (tmp_path / "clip.mp4").write_bytes(b"clip-bytes")
    (tmp_path / "beach").mkdir()
    (tmp_path / "beach" / "two.mp4").write_bytes(b"more-clip-bytes")
    for clip in ("clip.mp4", "beach/two.mp4"):
        os.utime(tmp_path / clip, ns=(1_756_000_000_000_000_000, 1_756_000_000_000_000_000))
    return tmp_path


def test_pinned_fingerprint_is_bit_identical(tmp_path: Path) -> None:
    """Golden hashes for a fixed document + disk state (task 1.1).

    Extracting ``editorial_hash`` out of ``compute_fingerprint`` must leave every
    component — and the combined hash — byte-identical, so no rendered event goes
    stale. A diff here means either an intentional fingerprint-input change (which
    needs its own decision) or an accidental one (which does not).
    """
    fingerprint = compute_fingerprint(
        _pinned_document(),
        event_dir=_pinned_event_dir(tmp_path),
        look_defaults={"resolution": "1080p", "fps": 30},
        ffmpeg_version=FFMPEG_VERSION,
    )

    assert fingerprint.editorial == PINNED_EDITORIAL
    assert fingerprint.defaults == PINNED_DEFAULTS
    assert fingerprint.clip_set == PINNED_CLIP_SET
    assert fingerprint.engine == PINNED_ENGINE
    assert fingerprint.combined == PINNED_COMBINED


def test_editorial_hash_is_the_editorial_component(tmp_path: Path) -> None:
    """The extracted function IS the component, not a parallel implementation."""
    document = _pinned_document()
    fingerprint = compute_fingerprint(
        document,
        event_dir=_pinned_event_dir(tmp_path),
        look_defaults={},
        ffmpeg_version=FFMPEG_VERSION,
    )
    assert editorial_hash(document) == fingerprint.editorial


def test_editorial_hash_moves_only_on_editorial_change() -> None:
    """Canonical over typed fields: metadata moves it, an equal document does not."""
    baseline = editorial_hash(_pinned_document())
    assert editorial_hash(_pinned_document()) == baseline

    changed = _pinned_document()
    changed = ReelDocument(
        version=changed.version,
        metadata=Metadata(
            title="Renamed Party",
            date=changed.metadata.date,
            location=changed.metadata.location,
            description=changed.metadata.description,
        ),
        look=changed.look,
        chapters=changed.chapters,
        clips=changed.clips,
        ignore=changed.ignore,
    )
    assert editorial_hash(changed) != baseline


def test_file_added_under_originals_leaves_fingerprint_unchanged(tmp_path: Path) -> None:
    event_dir = _event_dir(tmp_path)
    baseline = _fingerprint(event_dir)

    (event_dir / "original").mkdir()
    (event_dir / "original" / "clip.MTS").write_bytes(b"camera-original")

    assert _fingerprint(event_dir) == baseline


# --------------------------------------------------------------------------- #
# _hash_json: total over key types, unchanged for native keys (config-yaml-hardening)
# --------------------------------------------------------------------------- #


def _old_hash(value: object) -> str:
    """The pre-change formula, recomputed here so a drift in the native path is caught."""
    canonical = json.dumps(value, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@pytest.mark.parametrize(
    "value",
    [
        {"b": 1, "a": {"y": [1, 2], "x": None}},
        {1: "a", 2: "b"},
        {True: "a", False: "b"},
        [{"k": 1}, "text", 3.5],
    ],
    ids=["str-keys", "int-keys", "bool-keys", "list"],
)
def test_native_key_content_hashes_exactly_as_before(value: object) -> None:
    assert fingerprint_module._hash_json(value) == _old_hash(value)


def test_a_date_key_in_the_defaults_does_not_crash_the_fingerprint(tmp_path: Path) -> None:
    event_dir = _event_dir(tmp_path)
    defaults = {date(2024, 1, 1): "x"}
    first = _fingerprint(event_dir, look_defaults=defaults)
    assert _fingerprint(event_dir, look_defaults=defaults) == first
    moved = _fingerprint(event_dir, look_defaults={date(2024, 1, 1): "y"})
    assert moved.defaults != first.defaults
    assert moved.editorial == first.editorial


def test_mixed_int_and_str_look_keys_do_not_crash_the_editorial_hash() -> None:
    def hashed(one: str, b: str) -> str:
        return editorial_hash(
            ReelDocument(metadata=Metadata(title="Party"), look={1: one, "b": b})  # type: ignore[dict-item]
        )

    baseline = hashed("a", "b")
    assert hashed("a", "b") == baseline
    assert hashed("changed", "b") != baseline
    assert hashed("a", "changed") != baseline


def test_keys_that_differ_only_in_type_are_not_conflated() -> None:
    one = fingerprint_module._hash_json({1: "a", "1": "b"})
    other = fingerprint_module._hash_json({1: "b", "1": "a"})
    assert one != other


def test_the_fallback_hash_is_pinned() -> None:
    """The tag format (``<type>:<key>``) is hashed content; it must not drift silently."""
    assert fingerprint_module._hash_json({1: "a", "b": "c"}) == PINNED_FALLBACK
