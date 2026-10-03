## Context

See proposal.md, "Why". Code facts, from `main` at `b7b25c8` (both gates landed):

- **The manifest** (`staleness/manifest.py`): `RenderManifest(fingerprint, components, output, engine_identity,
  written_at, superseded)`. `fingerprint` is the combined sha256 hex of the four components
  (`staleness/fingerprint.py`, `_hash_json`). `written_at` is `datetime.now(timezone.utc).isoformat()`, written
  by `write_manifest` only after the atomic finalize (orchestrator) or by `adopt-renders` for a movie that
  already existed (`cli/commands.py`, `cmd_adopt_renders`). `read_manifest` returns `None` for an absent,
  unreadable or wrong-version manifest and never raises.
- **The movie lookup** is `staleness.rendered_output(event_dir, expected)`: none without a readable manifest,
  the expected file when it is a file, else the file under the recorded old name (`output_renamed`). The movie
  route (`api/media.py`, `movie_media`) wraps it: it loads the document with the resolving loader, applies
  `require_processable`, builds `expected = settings.output_dir / output_relpath(metadata)`, and refuses a path
  that is not lexically inside the output directory (`_inside`).
- **The detail** (`api/events_read.py`, `get_event`) computes the staleness verdict through `staleness_for`,
  which resolves the document (`with_resolved_metadata(document or seed_document(...))`) and builds the same
  `expected` path internally, then discards it. Today nothing in the detail says whether a movie exists or which
  render it is; a client infers "has a movie" from the verdict (`no_manifest` and `output` absent), which
  `Rendered movie endpoint` documents.
- **Gate changes this builds on** (both merged to `main` before this change is applied):
  - `render-chapter-times` (landed) adds `RenderManifest.chapters: Optional[Tuple[ChapterTime, ...]]`, where
    `ChapterTime(name, start_ms, end_ms, title_card)` holds **integer milliseconds** (the numbers the movie's
    `[CHAPTER]` markers carry). An older manifest, an adopted one and a malformed list all read as `None`
    (all-or-nothing, in `staleness/manifest.py`). The API therefore reports `start = start_ms / 1000` seconds
    and drops `end_ms` and `title_card` (non-goals). The earlier draft of this design assumed `(name, start)`
    pairs in seconds; the landed shape is the one used here.
  - `proxy-state-read` adds `proxy` to each clip of the same `EventDetailOut`. It touches `ClipOut`, this
    change touches the detail's top level; the OpenAPI regeneration is the one place both show, so this change
    regenerates on top of theirs rather than merging two hand-edited artifacts.
- **Evidence for the shape.** `docs/research/browser-playback.md` §4 (Chrome and Firefox expose 0 text tracks
  for the movie's MP4 chapters; the manifest has no chapter times); D-15 (the `v` entity-tag, "Chrome fails to
  play a replaced file at an address that served the old one"); the `Events read model` requirement (probe-free,
  no cache write).

## Goals / Non-Goals

**Goals:**
- One read of the detail tells a client: is there a rendered movie, which render is it, and where do its
  chapters start.
- The answer to "is there a movie" can never disagree with the movie route.
- The read stays probe-free and write-free.

**Non-Goals:** as in proposal.md. In addition: this design does not decide how the player shows the list
(`movie-chapter-list`) and does not define what a chapter is named (the render does).

## Decisions

### The movie facts are one nested nullable object on the detail only

**Context**: The client needs three related facts that are all about the same file; flat siblings on the detail
(`movie_chapters`, `movie_version`) would each need their own "no movie" rule.
**Explored**: flat fields; a separate `GET …/movie/facts` endpoint; nesting under `staleness`.
**Decision**: `EventDetailOut.movie: Optional[MovieOut] = None`, always present on the wire (as
`StalenessOut.renamed_from` is). Not on the list rows.
**Rationale**: One null means "no movie to show"; a separate endpoint would add a request to every page open for
data that is already read with the verdict (the same manifest read) and would double the "movie exists" rule.
The list stays cheap and its rows have no player.

```python
class MovieChapterOut(BaseModel):
    name: str          # as the render recorded it; "" for the default chapter if it so recorded
    start: float       # seconds into the rendered movie, finite, >= 0

class MovieOut(BaseModel):
    recorded_at: datetime              # manifest written_at; timezone-aware UTC
    fingerprint: str                   # first 12 hex characters of the manifest's combined fingerprint
    chapters: Optional[List[MovieChapterOut]] = None   # null: this render recorded no chapter times
```

`recorded_at` and `fingerprint` are required inside `MovieOut`; `chapters` is optional and nullable, so a
generated client types it `chapters?: … | null` and treats absent and null alike, as the `duration` field does.

### `movie` is non-null exactly when the movie route would find a file

**Context**: `Rendered movie endpoint` already says a client SHALL be able to decide from the detail alone
whether to offer a player; today it does that through the verdict. Two implementations of the same rule drift
(this is why `movie_media` calls `rendered_output` rather than copying the gate).
**Decision**: Extract the lookup's tail from `movie_media` into one function in `events_read.py`:

```python
def rendered_movie_path(settings: ApiSettings, event_dir: Path, metadata: EventMetadata) -> Optional[Path]:
    expected = settings.output_dir / output_relpath(metadata)
    movie = rendered_output(event_dir, expected)
    return movie if movie is not None and _inside(movie, settings.output_dir) else None
```

`_inside` moves with it. `movie_media` calls it (and raises `MovieNotFoundError` on `None`, then `open_media`);
`get_event` calls it with the resolved metadata `staleness_for` already derives. `staleness_for` is split so the
resolved document is built once (`_resolved_document(settings, event_dir, document)`), not twice, and the
verdict, the lookup and the route use one `expected`. Existing movie-route tests pass unchanged; a new test
asserts agreement for every event of the dev library (movie non-null iff `GET …/movie` answers 200).
**Rationale**: Principle V (no logic in `api/` the CLI cannot reach) holds because `rendered_output` is the
gate's own function; the extraction only keeps the two API callers equal. `_inside` guards a title that climbs
out of the output directory: the detail must not report a movie the route refuses.

### Version and chapters come from one manifest read

**Context**: A render can finish between two reads of the manifest.
**Decision**: `get_event` reads the manifest once for the facts (`read_manifest(event_dir)`), and fills
`recorded_at`, `fingerprint` and `chapters` from that one object. The movie path comes from
`rendered_movie_path`, which reads the manifest itself; if a render lands between the two, the facts describe
the newer render while the path check described the older. That is harmless: the file at the address is the
newer render's (finalize renames atomically after verify, then writes the manifest) and the facts are
self-consistent. A manifest that disappears between the two reads yields `movie: null` (no fabricated facts).
**Rationale**: Self-consistency of version and chapters is the invariant a client relies on; passing the
manifest into `rendered_output` would change a gate signature this change does not own.

### `recorded_at`, not `rendered_at`

**Context**: The plan calls it the "render finished time". `adopt-renders` also writes a manifest for a movie
rendered long before, with `written_at` = the adoption time.
**Decision**: The field is `recorded_at` and its description says when the record was written. For a render
that is when it finished; for an adopted movie it is when `adopt-renders` ran. An adopted movie has no chapter
times (nothing rendered them), so `chapters` is `null` for it. No `adopted` flag is added.
**Rationale**: Principle I. A field named `rendered_at` would show a render time for a render nobody timed.
The two cases are distinguishable enough by `chapters: null`, and a flag nobody reads is speculation (VII).

### The short fingerprint is 12 hex characters of the manifest's combined hash

**Decision**: `manifest.fingerprint[:12]`. Computed in `api/`, nowhere stored. The manifest's `fingerprint` is
already hex (`hexdigest`), so no re-hash; the manifest's own validation guarantees a string. 12 hex characters
(48 bits) distinguish renders of one event for any realistic number of edits, and match what developers read in
git. The full value is not exposed: nothing in the client compares it with another, and the verdict is the
freshness answer.
**Consequence to state**: the fingerprint is a hash of the *inputs*. Two renders of identical inputs (a
`--force` re-render) have the same fingerprint and different `recorded_at`; the version is the pair, and it is
not a hash of the movie's bytes. A client that needs the bytes uses `v` (D-15).

### Chapter list: verbatim, null when unknown, never partial

**Decision**: The API copies the recorded chapters in recorded order, converting each `start_ms` to seconds
(`start_ms / 1000`, the one arithmetic step): no sorting, no clamping, no renaming, no title-card entry, no
synthesized "Untitled". `chapters` is `null` when the manifest has no chapter list, and
when the list is present but malformed the manifest reader (`render-chapter-times`) already reports it as
absent (the manifest module's fail-open convention), so the API sees `None`. An empty recorded list stays
`[]`: it is a statement of the render, not unknown.
**Rationale**: The API knows no more than the render did (Principle I); an editor who renames a chapter after
the render must see the old name in the list because that is what the movie contains. The stale verdict, already
in the same response, is how a client says "outdated".

### A `written_at` that is not a date-time is an unreadable record

**Context**: `read_manifest` accepts any string as `written_at`; the engine always writes
`datetime.now(timezone.utc).isoformat()`.
**Decision**: `get_event` parses it with `datetime.fromisoformat`; a value that does not parse, or parses without
a UTC offset, gives `movie: null` (logged at debug). The API does not fall back to the file's modification time
or the current time.
**Rationale**: Principle I (never fabricate a version) and the detail's "never an error for the movie facts".
This is the one case where `movie` is null although the route would find the file, and the spec says so.

### Failure behavior and idempotency

- **Reads only.** `get_event` never creates or modifies `reel.yaml`, the manifest or any cache. A manifest or a
  movie that cannot be read gives `movie: null`, never an error: the detail's own failures (unparseable
  `reel.yaml`, unusable metadata, unreadable disk) are unchanged and still win with their problem body.
- A movie file removed since the render: `rendered_output` finds none, `movie` is `null`, and the verdict
  already cites `output`.
- A symbolic-linked year folder is followed, as the route follows it.
- Repeating the read, with no disk change, returns identical `movie`. A render finishing between two reads
  changes `recorded_at`, `fingerprint` and `chapters` together. A worker restart changes nothing: no state is
  held.
- **No ffmpeg arguments**, so there is no profile or CPU-fallback path (Principle III is not touched).

### OpenAPI and the generated client

`MovieOut`, `MovieChapterOut` join `EXPECTED_MODELS`' set of published models in `tests/test_api_openapi.py`;
`EventDetailOut.required` is unchanged (`movie` is optional in the schema, present on the wire). The artifacts
are regenerated with the commands in `web/README.md`. The client is not edited: the field is unused until
`movie-chapter-list`; if a typed test fixture in `web/` constructs a full `EventDetail`, adding `movie` there is
the only web edit.

### HLD: one sentence in D-15 and §4.10, no D-n

The change makes true what D-15 says is deferred ("Chapter times in the render manifest and a movie version in
the event detail are v2 items"). D-15 gets a pointer sentence and §4.10's v2 bullet is marked read-half-landed.
D-20 (timeline) and D-21 (proxy contract) are untouched: the timeline's chapter band is the editorial chapter
list, not this one. §6 gets a one-line note under item 9.

## Risks / Trade-offs

- **Gate names differ from this design's.** Mitigated by task 1.1, which reads them before any code.
- **Two manifest reads per detail** (one inside `rendered_output`, one for the facts). A small JSON file in a
  directory the same request already reads; accepted rather than changing the gate's signature. If measurement
  shows it matters, `rendered_output` can take a manifest (a follow-up, not this change).
- **Chapter times are only as good as the render's.** If `render-chapter-times` has a defect, this change
  shows it faithfully. Its own tests on a real render cover the numbers; this change's real-render test checks
  the plumbing, not the arithmetic.
- **The list may be outdated.** By design (above); the verdict says so.
- **`recorded_at` of an adopted movie is not a render time.** Named and documented, not hidden.
