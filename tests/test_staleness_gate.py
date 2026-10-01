"""Tests for the staleness gate: fresh, each stale arm, reasons, MISSING clip (task 1.3).

Also the rename reason (change ``output-renamed-reason``): an absent expected movie whose
last render's movie is still on disk under its old D-9 name cites ``output_renamed`` in place
of ``output``, and never changes whether the event is stale.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from auto_reel_ng.reel.document import Chapter, ClipRef, Metadata, ReelDocument
from auto_reel_ng.render import output_relpath
from auto_reel_ng.staleness.fingerprint import COMPONENTS, compute_fingerprint, engine_identity
from auto_reel_ng.staleness.gate import StalenessReason, Verdict, evaluate
from auto_reel_ng.staleness.manifest import write_manifest

FFMPEG_VERSION = (7, 1)


def _document(title: str = "Party", clips: tuple[str, ...] = ("clip.mp4",)) -> ReelDocument:
    return ReelDocument(
        metadata=Metadata(title=title),
        chapters=(Chapter(name="", clips=tuple(ClipRef(c) for c in clips)),),
    )


def _fingerprint(event_dir: Path, **overrides: object):
    document = overrides.pop("document", None) or _document()
    look_defaults = overrides.pop("look_defaults", {})
    ffmpeg_version = overrides.pop("ffmpeg_version", FFMPEG_VERSION)
    return compute_fingerprint(
        document, event_dir=event_dir, look_defaults=look_defaults, ffmpeg_version=ffmpeg_version
    )


def _render(event_dir: Path, fingerprint, *, output_name: str = "Party.mp4") -> Path:
    write_manifest(
        event_dir, fingerprint, output=output_name, engine_identity=engine_identity(FFMPEG_VERSION)
    )
    output_path = event_dir / output_name
    output_path.write_bytes(b"rendered")
    return output_path


def _setup(tmp_path: Path, *, content: bytes = b"clip-bytes") -> Path:
    (tmp_path / "clip.mp4").write_bytes(content)
    return tmp_path


def test_fresh_event_has_no_reasons(tmp_path: Path) -> None:
    event_dir = _setup(tmp_path)
    fingerprint = _fingerprint(event_dir)
    output_path = _render(event_dir, fingerprint)

    verdict = evaluate(event_dir, output_path, fingerprint)

    assert verdict.stale is False
    assert verdict.reasons == ()


def test_no_manifest_is_stale(tmp_path: Path) -> None:
    event_dir = _setup(tmp_path)
    fingerprint = _fingerprint(event_dir)

    verdict = evaluate(event_dir, event_dir / "Party.mp4", fingerprint)

    assert verdict.stale is True
    assert verdict.reasons == (StalenessReason.NO_MANIFEST,)


def test_missing_output_is_always_stale(tmp_path: Path) -> None:
    event_dir = _setup(tmp_path)
    fingerprint = _fingerprint(event_dir)
    output_path = _render(event_dir, fingerprint)
    output_path.unlink()

    verdict = evaluate(event_dir, output_path, fingerprint)

    assert verdict.stale is True
    assert StalenessReason.OUTPUT in verdict.reasons


def test_reasons_name_exactly_the_changed_components(tmp_path: Path) -> None:
    event_dir = _setup(tmp_path)
    baseline = _fingerprint(event_dir)
    output_path = _render(event_dir, baseline)

    # A clip changes, and the editorial document changes; defaults/engine do not.
    (event_dir / "clip.mp4").write_bytes(b"replaced content, different size")
    changed_fp = _fingerprint(event_dir, document=_document(title="Renamed Party"))

    verdict = evaluate(event_dir, output_path, changed_fp)

    assert verdict.stale is True
    assert set(verdict.reasons) == {"editorial", "clip_set"}


def test_missing_referenced_clip_is_stale_via_clip_set(tmp_path: Path) -> None:
    event_dir = _setup(tmp_path)
    baseline = _fingerprint(event_dir)
    output_path = _render(event_dir, baseline)

    (event_dir / "clip.mp4").unlink()
    changed_fp = _fingerprint(event_dir)

    verdict = evaluate(event_dir, output_path, changed_fp)

    assert verdict.stale is True
    assert "clip_set" in verdict.reasons


def test_component_members_are_exactly_the_fingerprint_components() -> None:
    """The hand-written component reasons mirror COMPONENTS, in order.

    A fifth fingerprint component added without its reason fails here rather than
    raising out of :func:`evaluate` the first time that component changes.
    """
    non_components = (
        StalenessReason.NO_MANIFEST,
        StalenessReason.OUTPUT,
        StalenessReason.OUTPUT_RENAMED,
    )
    component_members = tuple(reason for reason in StalenessReason if reason not in non_components)

    assert tuple(reason.value for reason in component_members) == COMPONENTS


def test_reasons_are_enum_members_carrying_the_unchanged_wire_values(tmp_path: Path) -> None:
    """Every cited reason is a member *and* equal to the plain string it was before."""
    event_dir = _setup(tmp_path)
    baseline = _fingerprint(event_dir)
    output_path = _render(event_dir, baseline)
    (event_dir / "clip.mp4").write_bytes(b"replaced content, different size")
    changed_fp = _fingerprint(event_dir, document=_document(title="Renamed Party"))
    output_path.unlink()

    verdict = evaluate(event_dir, output_path, changed_fp)

    assert all(isinstance(reason, StalenessReason) for reason in verdict.reasons)
    assert verdict.reasons == ("editorial", "clip_set", "output")

    no_manifest = evaluate(tmp_path / "unrendered", tmp_path / "unrendered" / "x.mp4", changed_fp)
    assert isinstance(no_manifest.reasons[0], StalenessReason)
    assert no_manifest.reasons == ("no_manifest",)


# --- The rename reason --------------------------------------------------------------------------

GRILLNING = Metadata(title="Grillning med Grannar", date=date(2024, 6, 27))
MIDSOMMAR_2024 = Metadata(title="Midsommar", date=date(2024, 6, 21), location="Dalarna")
MIDSOMMAR_2023 = Metadata(title="Midsommar", date=date(2023, 6, 23), location="Dalarna")


def _render_named(tmp_path: Path, metadata: Metadata) -> tuple[Path, Path]:
    """Render ``metadata``'s event as the engine does, into ``tmp_path / "out"``.

    The movie goes at its D-9 path and the manifest records that movie's bare file name.
    Returns the event folder and the movie.
    """
    event_dir = tmp_path / "event"
    event_dir.mkdir()
    _setup(event_dir)
    movie = tmp_path / "out" / output_relpath(metadata)
    movie.parent.mkdir(parents=True, exist_ok=True)
    movie.write_bytes(b"rendered")
    write_manifest(
        event_dir,
        _fingerprint(event_dir, document=_document_named(metadata)),
        output=movie.name,
        engine_identity=engine_identity(FFMPEG_VERSION),
    )
    return event_dir, movie


def _document_named(metadata: Metadata) -> ReelDocument:
    return ReelDocument(
        metadata=metadata, chapters=(Chapter(name="", clips=(ClipRef("clip.mp4"),)),)
    )


def _evaluate_named(tmp_path: Path, event_dir: Path, metadata: Metadata) -> Verdict:
    """The gate's verdict for the event now named by ``metadata``, at its current D-9 path."""
    expected = tmp_path / "out" / output_relpath(metadata)
    return evaluate(
        event_dir, expected, _fingerprint(event_dir, document=_document_named(metadata))
    )


def _as_before(reasons: tuple[StalenessReason, ...]) -> tuple[str, ...]:
    """The reasons today's gate (before ``output_renamed``) cites for the same disk state."""
    return tuple("output" if reason == "output_renamed" else reason for reason in reasons)


def test_retitle_cites_output_renamed(tmp_path: Path) -> None:
    event_dir, old_movie = _render_named(tmp_path, GRILLNING)
    retitled = Metadata(title="Grillkväll med grannarna", date=GRILLNING.date)

    verdict = _evaluate_named(tmp_path, event_dir, retitled)

    assert verdict.stale is True
    assert verdict.reasons == ("editorial", "output_renamed")
    assert _as_before(verdict.reasons) == ("editorial", "output")
    assert old_movie.read_bytes() == b"rendered"


def test_location_change_cites_output_renamed(tmp_path: Path) -> None:
    event_dir, _ = _render_named(tmp_path, MIDSOMMAR_2024)
    moved = Metadata(title="Midsommar", date=MIDSOMMAR_2024.date, location="Leksand")

    verdict = _evaluate_named(tmp_path, event_dir, moved)

    assert verdict.stale is True
    assert verdict.reasons == ("editorial", "output_renamed")
    assert _as_before(verdict.reasons) == ("editorial", "output")


def test_date_moved_to_another_year_cites_output_renamed(tmp_path: Path) -> None:
    """The old movie stays in ``2023/``; the expected path is in ``2022/``."""
    event_dir, old_movie = _render_named(tmp_path, MIDSOMMAR_2023)
    redated = Metadata(title="Midsommar", date=date(2022, 6, 23), location="Dalarna")
    assert old_movie.parent.name == "2023"

    verdict = _evaluate_named(tmp_path, event_dir, redated)

    assert verdict.stale is True
    assert verdict.reasons == ("editorial", "output_renamed")
    assert _as_before(verdict.reasons) == ("editorial", "output")


@pytest.mark.parametrize("recorded", ["", "2024", "absolute", "../Grillning.mp4"])
def test_a_recorded_value_that_is_not_a_bare_movie_file_cites_output(
    tmp_path: Path, recorded: str
) -> None:
    """A hand-edited manifest never claims a rename, even when its value names something on disk."""
    event_dir, old_movie = _render_named(tmp_path, GRILLNING)
    (tmp_path / "Grillning.mp4").write_bytes(b"rendered")  # what ``out/../Grillning.mp4`` names
    value = str(old_movie) if recorded == "absolute" else recorded
    write_manifest(
        event_dir,
        _fingerprint(event_dir, document=_document_named(GRILLNING)),
        output=value,
        engine_identity=engine_identity(FFMPEG_VERSION),
    )
    retitled = Metadata(title="Grillkväll med grannarna", date=GRILLNING.date)

    verdict = _evaluate_named(tmp_path, event_dir, retitled)

    assert verdict.stale is True
    assert verdict.reasons == ("editorial", "output")
    assert _as_before(verdict.reasons) == ("editorial", "output")
    assert old_movie.is_file()


def test_renamed_with_old_movie_deleted_cites_output(tmp_path: Path) -> None:
    event_dir, old_movie = _render_named(tmp_path, GRILLNING)
    old_movie.unlink()
    retitled = Metadata(title="Grillkväll med grannarna", date=GRILLNING.date)

    verdict = _evaluate_named(tmp_path, event_dir, retitled)

    assert verdict.stale is True
    assert verdict.reasons == ("editorial", "output")
    assert _as_before(verdict.reasons) == ("editorial", "output")


def test_expected_movie_present_cites_neither(tmp_path: Path) -> None:
    """A leftover file at the new path: the next render replaces it, so no output reason."""
    event_dir, old_movie = _render_named(tmp_path, GRILLNING)
    retitled = Metadata(title="Grillkväll med grannarna", date=GRILLNING.date)
    (tmp_path / "out" / output_relpath(retitled)).write_bytes(b"leftover")

    verdict = _evaluate_named(tmp_path, event_dir, retitled)

    assert verdict.stale is True
    assert verdict.reasons == ("editorial",)
    assert _as_before(verdict.reasons) == ("editorial",)
    assert old_movie.is_file()
