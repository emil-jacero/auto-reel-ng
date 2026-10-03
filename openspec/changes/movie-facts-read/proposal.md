## Why

HLD §4.10 lists two v2 items "beside the proxy work": chapter times for the movie player and a movie
version in the event detail. GUI v1 shipped the movie player without either (**D-15**): "There are no
custom controls or shortcuts, no captions and no chapter list: the manifest records no chapter times and
browsers expose none." That measurement is in `docs/research/browser-playback.md` §4: the rendered MP4 has
real container chapters, but Chrome and Firefox expose **0** `textTracks` for them, and the manifest holds
only `output`, the fingerprint, the engine identity and `written_at`. A chapter jump list therefore needs
the times from somewhere the browser is not, and a probe of the movie is ruled out by the probe-free read
model (Principle IV, `api-service` "Events read model").

The gate change `render-chapter-times` (HLD §6 phase 9, GUI v2) makes the render record each chapter's start
in the rendered movie, computed from the segments it actually concatenated, in `render-manifest.json`. This
change is the read half: it puts that list, and a version that names which render it belongs to, in the
event detail, so the next change (`movie-chapter-list`) can build the player's jump list from a read alone.

The version matters as much as the list. The detail already reports freshness, but only as a verdict about
the *current* editorial state. A client that holds chapter times and a loaded `<video>` needs to know that
the two describe the same render (a re-render replaces the file at the same address, and Chrome fails to
play a replaced file at an address that served the old one, D-15). Nothing in the detail identifies the
render today.

Research evidence relied on (all under `research/v2/`, and the repo's own notes):
- `docs/research/browser-playback.md` §4: no browser chapter tracks; manifest has no chapter times; both
  ways to get a list (probe, or record at render time) are named v2 items.
- `research/v2/synthesis.md` §5 ("HLD v2 items outside these three reports ... chapter times in the render
  manifest, movie version in the event detail are not sequenced here"): this change is that unsequenced
  item. It has no proxy dependency; it is applied after `render-chapter-times` (its data) and
  `proxy-state-read` (which edits the same response model), so that one regeneration of the artifacts
  carries both.

## What Changes

- **`GET /api/v1/events/{event_id}` gains `movie`**, a nullable object, read from the render manifest and the
  filesystem by stat and JSON only:
  - `movie` is `null` when the event has no rendered movie, by the rule `GET …/movie` already uses (the gate's
    `rendered_output`, inside the output directory). `movie` is non-null exactly when the movie route would
    answer 200 for a file that stays in place.
  - `movie.recorded_at`: the manifest's `written_at`, a timezone-aware date-time. The manifest is written only
    after the atomic finalize verified the movie, so for a render it is when the render finished. For a movie
    `adopt-renders` recorded it is when it was adopted; the field is named for what the manifest knows.
  - `movie.fingerprint`: the first 12 hex characters of the manifest's combined fingerprint, the identity of
    the inputs that render was made from. Together `recorded_at` and `fingerprint` are the "movie version".
  - `movie.chapters`: `[{name, start}]`, `start` in seconds into the rendered movie, in the order the render
    recorded them; **`null`** when the manifest predates `render-chapter-times` (or its list is unreadable).
    Never an empty list as a stand-in for unknown, never computed here.
- **The chapter list describes the movie that is on disk, not the current editorial state.** After a rename or
  an edit the event is stale and the list still names the chapters of the last render.
- **`web/openapi.json` and `web/src/api/schema.d.ts` are regenerated** (the drift test fails until they are).
  No client code reads the field yet.
- **Docs:** README events bullet, HLD §4.10 and D-15 sentence, §6 phase 9 note (task 5.1). No new D-n.

## Non-goals

- **No player UI, jump list or version display.** That is `movie-chapter-list`.
- **No probe, no ffmpeg, no decoding, no write, no cache entry, no database read.** A test forbids
  subprocess launches during the read.
- **No title-card span in the API.** The manifest records it (render-chapter-times); this change exposes
  chapter names and starts only, as the summary says. A later reader can add it additively.
- **No synthesized chapters.** An old manifest yields `chapters: null`; this change does not rebuild times
  from the reel, the clips' durations or the movie.
- **No change to the list endpoint** (`GET /api/v1/events`): the movie facts belong to the page that plays
  the movie, and the list stays cheap.
- **No change to the `v` entity-tag mechanism of D-15.** The version names a render; `v` names the bytes a
  browser holds. They answer different questions.
- **No change to the movie route, staleness, the fingerprint or the manifest schema.**

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `api-service`: ADDED `Requirement: The event detail reports the rendered movie's version and chapter
  times`. No requirement is MODIFIED, so the text of "Events read model", "Rendered movie endpoint" and a
  parallel change's requirements is not rewritten.

## Impact

- **Packages (two, Principle VIII):**
  - `api/`: `schemas.py` (`MovieOut`, `MovieChapterOut`, `EventDetailOut.movie`), `events_read.py` (the one
    movie lookup shared with `media.py`, and `get_event`), `media.py` (calls the shared lookup);
    regenerated `web/openapi.json`
  - `web/`: regenerated `src/api/schema.d.ts` only (plus any fixture the generated type forces)
- **Reads:** `staleness.read_manifest` and the existing `rendered_output`. `staleness/` and `render/` are
  not edited here; their part is `render-chapter-times`.
- **CLI vs API (Principle V):** API only. The facts are read-model shaping of a manifest field the engine
  already writes (`render-chapter-times`) and that `auto-reel` can read through the same `read_manifest`;
  no behavior is added that the CLI cannot reach.
- **Rendered output:** unchanged. **No `RENDER_GRAPH_VERSION` bump.** Fingerprint inputs unchanged.
- **Schemas:** no `reel.yaml`/`config.yaml` change, **no Alembic migration**, no rescan.
- **Wire:** additive. `EventDetailOut` gains one optional key, always present (an object or `null`).
- **Dependencies (gates):** `render-chapter-times` (the manifest field) and `proxy-state-read` (the detail
  response is edited by both; this change is applied on top so that regenerated artifacts are not
  conflicted) must be on `main`. Task 1.1 checks both and the landed names.
- **Runtime dependencies:** none new (Principle VII).
- **Size (Principle VIII):** three small models/fields, one extracted lookup, one regeneration, one docs
  task. Eight tasks, one of them the gate and one the browser check.
