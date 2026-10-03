## Context

See proposal.md, "Why". The code on `origin/main` at `8fb4d16`:

- **`render/orchestrator.py`, `_run_pipeline` (the render body).** After normalize and the equivalence
  pre-flight it computes `measured = [probe_media(p).duration for p in intermediates]` (probed from the files
  that will be concatenated, copy-eligible source segments included), then
  `chapter_pairs = aggregate_chapter_durations(segments, measured)` and writes
  `build_ffmetadata(chapter_pairs)`. After `verify_output` and `os.replace`, and only when
  `options.fingerprint is not None`, it calls `write_manifest(event_dir, fingerprint, output=..., engine_identity=...)`.
  `measured` and `chapter_pairs` are local to the `with tempfile` block that also holds the manifest write, so
  the numbers are in scope at the one place the manifest is written.
- **`render/chapters.py`.** `aggregate_chapter_durations(segments, durations)` sums per chapter name in
  first-seen order, and `build_ffmetadata(pairs)` emits `START`/`END` as cumulative `round(duration * 1000)`
  per chapter. The boundary rule lives only in `build_ffmetadata`'s loop.
- **`staleness/manifest.py`.** `RenderManifest` is a frozen dataclass; `write_manifest(event_dir, fingerprint,
  *, output, engine_identity)` writes `version: 1`; `read_manifest` returns `None` for a wrong version or a
  structurally incomplete required field. The optional `superseded` field is read tolerantly by
  `_superseded_names` (absent or malformed reads as empty), the precedent this change follows.
- **Title cards.** `render/title/decorator.py` inserts at most one synthetic segment with `producer ==
  TITLE_PRODUCER` per chapter, immediately before that chapter's title clip, with the segment's `chapter` set
  to the chapter name. It is not necessarily the chapter's first segment. `Segment.chapter` is the chapter name
  for source and synthetic segments alike, which is what `aggregate_chapter_durations` groups by.
- **Callers of `write_manifest`:** the orchestrator, `adopt-renders` (`cli/`, no render) and many tests.
  `Segment`, `RenderPlan` and the fingerprint are not touched.
- **Evidence.** The research round (`scratchpad/research/v2/synthesis.md` §5, last paragraph) lists "chapter
  times in the render manifest" among the HLD v2 items outside the three research reports and does not size or
  sequence it, so this design rests on the code above, not on a measurement. HLD §4.10 and D-15 are the only
  statements of intent.

## Goals / Non-Goals

**Goals:**
- Record, per chapter, the start/end the movie really has, from measured durations only, in the same numbers as
  the muxed `[CHAPTER]` markers.
- Keep the field out of every staleness decision, and old manifests valid.

**Non-Goals:** exposing the field (API/web), backfill, per-clip times, a new fingerprint component. See
proposal.md, "Non-goals".

## Research & Decisions

### One boundary rule for the markers and the manifest

**Context**: The markers are cumulative per-chapter `round(duration * 1000)`. A second implementation of the
arithmetic for the manifest could disagree by a millisecond, and the field's whole point is to be the same as
what the movie carries.
**Explored**: `render/chapters.py`; rounding per segment (rejected: it would change the existing marker values
and so the movie bytes, which Principle IV forbids without a `RENDER_GRAPH_VERSION` bump); rounding the
cumulative total (same objection).
**Decision**: Extract the existing loop into one pure helper in `render/chapters.py` that both
`build_ffmetadata` and the new `chapter_times(segments, durations)` call. `build_ffmetadata`'s signature and
output stay byte-identical. `chapter_times` returns `tuple[ChapterTime, ...]`, one per aggregated chapter, in
the same order as `aggregate_chapter_durations`.
**Rationale**: One rule, tested once; the unit test asserts `START`/`END` of `build_ffmetadata(pairs)` equal
the helper's numbers for the same input, so the two cannot drift.
**Alternatives**: parse the `ffmetadata` text back (string coupling); probe the finished movie with
`ffprobe -show_chapters` (extra subprocess, and it would make the manifest depend on the container rather than
on the measurement).

### Where the record's type lives

**Context**: `render/` already imports `staleness/manifest` (the orchestrator does); `staleness/` must not need
`render/` to read a manifest.
**Decision**: `ChapterTime` and `TitleCardSpan` are frozen dataclasses defined in `staleness/manifest.py`
(the record's owner) and exported from `staleness/__init__.py`; `render/chapters.py` imports them to build
the values.
**Rationale**: The reader (`read_manifest`) and the writer share one definition and the import direction is the
one that exists today. `render/` stays free of persistence and `api/`.
**Alternatives**: a plain dict across the boundary (Code Style: prefer dataclasses); the dataclass in `render/`
(would make `staleness/` import `render/`).

```python
@dataclass(frozen=True)
class TitleCardSpan:
    start_ms: int
    end_ms: int

@dataclass(frozen=True)
class ChapterTime:
    name: str
    start_ms: int
    end_ms: int
    title_card: Optional[TitleCardSpan] = None

# staleness/manifest.py
RenderManifest.chapters: Optional[Tuple[ChapterTime, ...]] = None
def write_manifest(..., chapters: Optional[Sequence[ChapterTime]] = None) -> Path: ...

# render/chapters.py
def chapter_times(segments: Sequence[Segment], durations: Sequence[float]) -> tuple[ChapterTime, ...]: ...
```

JSON written as `"chapters": [{"name": "...", "start_ms": 0, "end_ms": 1500, "title_card": {"start_ms": 0,
"end_ms": 3000}}]`, or `"chapters": null`.

### Title-card span

**Context**: The card is one synthetic segment, placed before the chapter's title clip, possibly after other
clips of the chapter.
**Decision**: For chapter `c` with start `S` (from the shared rule), the card's span is `[S + round(1000 * pre),
S + round(1000 * (pre + card))]`, where `pre` is the sum of the measured durations of the chapter's segments
before the card and `card` its own measured duration. A segment is the card iff `segment.producer ==
TITLE_PRODUCER` (the constant from `render/title`); a chapter has at most one, and a second one in a chapter
raises `RenderError` rather than keeping the first (Principle I).
**Rationale**: Rounding each end once from the exact sum keeps `S <= start <= end <= chapter end` because
rounding is monotone, so the span can never poke out of its chapter, and it is within 1 ms of the card's
measured duration. Rounding per segment would not give that guarantee.
**Alternatives**: no title-card span (the player would not be able to offset the card; HLD asks for it);
record every synthetic segment (YAGNI: the title card is the only producer).

### The manifest field is additive, at version 1 (no bump)

**Context**: The plan for this change said "schema bump handled backward-compatibly".
**Explored**: (a) bump `_MANIFEST_VERSION` to 2, accept 1 and 2 on read; (b) keep 1 and add an optional field,
as `superseded` did and the change-detection spec records ("The manifest schema version stays 1").
**Decision**: (b).
**Rationale**: `read_manifest` returns `None` for any version it does not know. With (a), any older engine
(a rollback, or another checkout of the repo against the same library) would read every new manifest as absent:
every event stale and `records_output` returning false, so the output-collision claim (`render/claims.py`)
silently stops protecting every movie rendered since the upgrade. With (b), an older reader ignores the unknown
key and everything it relied on still holds. A "no chapter times" state is representable without a version:
absent and `null` both read as `None`.
**Alternatives**: (a). If a later change makes chapters mandatory, a version bump belongs there.

### Writing: from the render only, never carried over

**Decision**: `write_manifest` takes `chapters` as an optional keyword defaulting to `None`. The orchestrator
passes the freshly computed times. `adopt-renders` and every existing caller pass nothing and so write
`null`. The previous manifest's chapters are not carried over (unlike `superseded`): they describe a movie that
the new render replaced, or, for an adoption, a movie nobody measured.
**Rationale**: Carrying them forward after an adoption would present an old render's times as the adopted
movie's. An absent value is honest; a stale one is the fabricated metadata Principle I forbids.

### Reading: whole list or nothing

**Decision**: `read_manifest` parses `chapters` with a tolerant function like `_superseded_names`: absent,
`null`, or malformed (not a list; an entry that is not an object; `name` not a string; `start_ms`/`end_ms`
not plain integers (`bool` excluded) or negative or `start > end`; a `title_card` that is neither `null` nor a
well-formed span inside its chapter) gives `None` for the whole field, with a `logger.debug` line, and never
makes the manifest unreadable. It does not require chapters to be contiguous or sorted: those are properties of
what the renderer writes, tested at the writer, not conditions a reader should refuse a manifest for.
**Rationale**: The field decides no verdict, so ignoring a malformed one cannot turn a stale event fresh; and a
partly kept list would be a list the engine never wrote.

## Risks / Trade-offs

- **Concat offsets can differ from the sum of probed durations** (stream-copy joins can shift timestamps by a
  fraction of a frame) → this is the same assumption the existing markers make ("Chapter markers from measured
  durations"); the real-render test compares the last recorded end with the probed movie duration to within
  one frame period, which would fail loudly if it stopped holding.
- **Chapters that share a name merge** (`aggregate_chapter_durations` groups by name, and so do the markers) →
  the manifest records exactly the merged list, equal to the markers; making chapter names unique is held for
  the user and out of scope.
- **A manifest without the field after upgrade** is the normal state of every event until it is next rendered →
  consumers treat `None` as "unknown" (documented in the spec); nothing is rendered because of it.
- **Rollback**: an older engine ignores the field and rewrites manifests without it. Nothing to undo.

## Migration Plan

None. No migration, no rescan; old manifests read as `None` and the field appears on each event's next
successful render. Rollback is a revert; manifests written by this change stay valid for the older reader.

## Idempotency and failure

- **Re-run of a fresh event**: the gate skips it; the manifest is not written. A render of an event that is
  stale, or `--force`, writes a new manifest with newly measured chapters. The same inputs give the same
  numbers, so a forced re-render of unchanged inputs rewrites an equal list.
- **Worker restart mid-render**: unchanged. The manifest is written only after the rename, so a killed render
  leaves the previous manifest and its chapters (describing the previous movie) in place.
- **Failure behaviour**: a probe or concat failure raises as before; a malformed segment/duration pairing
  raises `ValueError` from the helper today and `RenderError` for a second title card in a chapter, before the
  concat runs; no `.part` and no manifest are left. The manifest write itself is after `os.replace` as today.
