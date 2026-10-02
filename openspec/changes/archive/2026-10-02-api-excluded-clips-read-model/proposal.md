## Why

GUI v1 (HLD **§6 phase 8**, §4.10) reads everything about an event from `GET /api/v1/events[/{id}]`, and that
read model does not carry `exclude`. `reel.yaml` can exclude a clip it lists (`clips.<identity>.exclude: true`);
the engine honours it (`event/resolution.py:_resolve_chapter` drops it from the plan, `cli/build.py`
`_probe_clips` never probes it), but the service and the screens know nothing of it. Three defects follow, all
confirmed on `6a7fe16` by the bug triage and re-read against the code for this change (design, "Findings
re-checked"):

- **A clip's `exclude: true` is not shown anywhere in the GUI.** `ClipOut` carries only
  `identity/status/size/mtime`. The event page and Edit mode list an excluded clip as "Included", count it
  among the clips the event plays, and offer Cuts on it, though a render drops it. Edit mode round-trips the
  flag on Save (`draft.ts` `withCuts`), so it is preserved but never displayed.
- **An excluded MISSING clip holds Render back.** Reconcile reports a listed, absent clip MISSING whether or
  not it is excluded, so `missing` names it and the page's `missingClipsReason(event.missing)` and the list's
  `missing_count > 0` both refuse Render. A render would succeed, since an excluded clip is never probed. The
  client cannot tell which missing clips matter, because the read model does not say.
  `web-app` even specifies the wrong behaviour ("An excluded missing clip still holds Render back",
  "since the page's read does not say which missing clips are excluded").
- **The event list's "N clips" counts ignored clips, and the event page's does not.**
  `events_read._event_summary` sets `clip_count=len(result.classification)`, which includes IGNORED clips;
  `EventDetail.tsx` counts `clips.filter(status !== 'ignored')`. One event reads "3 clips" in the list and
  "2 clips · 1 ignored" on its page.

This is a read-model and screens fix (a bug round on `main` at `6a7fe16`, not a new phase). It resolves no §8
research item and adds no decision to the HLD's D-n list: it applies D-8 (types generated from the service's
own schema) to two new fields.

## What Changes

- **`auto_reel_ng/api`** (read model, `GET` only):
  - `ClipOut.excluded: bool`, true when the document's `clips` map marks the identity `exclude: true`. A flag
    beside `status`, not a new `ClipStatus` member: the closed status vocabulary is unchanged.
  - `EventDetailOut.blocking_missing: list[str]`: the missing clips the document does not exclude, the ones a
    render needs. `missing` keeps listing every missing clip.
  - `EventSummaryOut.clip_count` becomes the clips the event lists that are not ignored (the page's number);
    new `ignored_count` and `blocking_missing_count`. `missing_count` is unchanged.
  - `web/openapi.json` and `web/src/api/schema.d.ts` regenerate (the drift test is the gate).
- **`web`**:
  - An **Excluded** status label (words and an icon) on the event page and in Edit mode, in place of the quiet
    "Included" word; an "n excluded" count in the facts line. Excluded clips keep their place and number.
  - The page's Render guard and the list row's Render guard use only the missing clips that block
    (`blocking_missing`, `blocking_missing_count`). The page's warning still names every missing clip, and
    marks an excluded one.
  - No Cuts control, cut count or read-only cut list for an excluded clip. Its stored cuts stay in `reel.yaml`
    and Save writes them back unchanged.
  - The list row shows its ignored clips ("2 clips · 1 ignored") the way the page does.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `api-service`: a new requirement "The event reads report excluded clips and the missing clips that block a
  render" (an addition: no existing requirement defines `clip_count` or the detail's `missing`, so no existing
  text changes).
- `web-app`: a new requirement "A clip that reel.yaml excludes is marked as excluded"; the MODIFIED
  "The event list shows every event with its render state", "The event page shows the event's chapters and
  clips", "The event list shows live job state and offers a render", "Edit mode lists, adds and removes a
  clip's cuts" and "The event page shows each clip's cuts"; and "An event's page schedules its render", which
  is REMOVED and re-stated as "An event's page schedules its render, held back only by clips a render needs".
  Its scenario "An excluded missing clip still holds Render back" is the bug, stated as required behaviour,
  and `openspec validate` will not let a MODIFIED block drop or rename a scenario, so the requirement is
  replaced rather than modified; every other paragraph and scenario is carried over unchanged.

## Impact

- **Packages (two):** `auto_reel_ng/api` (`schemas.py`, `events_read.py`) and `web` (`src/events/`,
  `src/edit/ClipOrderList.tsx`, `src/cuts/ReadCuts.tsx`, `src/ui/Icon.tsx` if an icon is added,
  `openapi.json`, `src/api/schema.d.ts`).
- **Rendered output / fingerprint:** unchanged for identical inputs. This change is read-only, so
  `RENDER_GRAPH_VERSION` is **not** bumped, and no staleness fingerprint input changes (`exclude` is already
  in the editorial hash; a missing clip is not in the clip-set component, which hashes the clips on disk).
- **`reel.yaml` / `config.yaml` schema, Alembic:** none. No migration, no rescan.
- **CLI vs API (Principle V):** the API shapes an engine fact (the document's `exclude`, reconcile's MISSING)
  that the CLI already acts on. Nothing here is behaviour the CLI cannot reach.
- **Gates:** `api-jobs-create-validation` (`events_read.py`) and `api-ws-heartbeat` (`schemas.py`,
  `openapi.json`, `schema.d.ts`) merge first; this change is implemented on top of them (design, "Gates").
  `api-jobs-missing-clips-refusal` is implemented after this one and reuses `blocking_missing`.
- **Tests:** `tests/test_api_events.py`, `tests/test_api_openapi.py`, and a real-browser Playwright run for
  the two screens and Edit mode (the web package has no unit-test runner; `tsc --noEmit` and `vite build`
  are its gates).

## Non-goals

- **No server refusal on `POST /api/v1/jobs`.** That is `api-jobs-missing-clips-refusal`, which uses the
  `blocking_missing` definition fixed here. This change enqueues exactly as before.
- **No change to the engine.** Exclusion, MISSING, the plan and the probe are untouched; no CLI change.
- **No exclude toggle in the GUI.** The flag is shown, not edited; `reel.yaml` is the place to set it.
- **No change to staleness.** An excluded clip on disk still counts in the clip-set component (its file is
  on disk), as before; narrowing that is not needed for these bugs.
- **No refresh-until-restored** for a missing clip: screens still do not poll for a file coming back.
- **No reordering of excluded clips out of the play order** in Edit mode (design, "Excluded clips stay in
  place").
