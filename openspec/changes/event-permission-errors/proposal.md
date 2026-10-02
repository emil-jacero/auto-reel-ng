## Why

A readable but unsearchable event folder (mode `0600`: the owner can list the names in it, but not look
anything up) is read as a brand-new event with no clips, and its `reel.yaml` is ignored. Reproduced on
`main` (`6a7fe16`, Python 3.14.7) with `2024-06-21 - Fest/` at `0600` holding a `reel.yaml` titled `Real`
and `a.mp4`:

- `Path.exists()` swallows `EACCES` on Python 3.14, so `(dir / "reel.yaml").exists()` is `False`.
  `load_authored_document` (`event/metadata.py:55`) therefore returns `seeded=True` with the title `Fest`
  taken from the folder name, and `Real` is never read.
- `Path.is_dir()` / `is_file()` swallow it the same way, so `scan_event` (`event/discovery.py:134`, `:145`,
  `:333`) lists the names, finds every entry "not a file", and returns an empty listing. `seed_document` is
  empty and `scan_event(d).identities == ()`.

The events list then shows a healthy, empty event instead of an error row. Constitution I: fail loud,
never fabricate. The overwrite risk is small, because creating a file in a folder without search permission
fails too, so the cost is a silently wrong read, not data loss. That is why it is low severity.

## What Changes

- A new helper `reel_exists(path)` answers "is there a `reel.yaml` here" from `stat()`: `False` only for
  "no such file" and "not a directory"; a permission error propagates.
- `load_authored_document` uses it, so an event whose `reel.yaml` it was not allowed to look for is an error,
  never a seed from the folder name.
- `scan_event` stops reading `EACCES` as "not a file / not a directory": an event root, a chapter subfolder
  or a `.reelignore` marker lookup it cannot stat raises the permission error instead of yielding an empty
  listing. A dangling symlink and a non-clip entry are skipped exactly as before.
- Callers need no change to be loud: the events list and detail already map an `OSError` to the
  `unreadable_disk` failure kind. The remaining `exists()` call sites (`event/editorial.py`,
  `api/events_read.py`, `cli/commands.py`, `cli/adoption.py`) are swapped to the helper by the changes that
  own those files (`editorial-chapter-comments`, `api-jobs-create-validation`,
  `cli-batch-isolation-and-claims`); this change supplies the helper they use.
- No `RENDER_GRAPH_VERSION` bump: every input that rendered before renders to the same bytes. Only inputs
  that were silently misread now fail.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `reel-document`: "Fail-loud parse and validation" gains the rule that a document's existence is answered
  by the disk; a lookup the disk refuses is a permission error, neither "no document" nor a parse error.
- `event-reconcile`: a new requirement, "An event folder that cannot be searched is not an empty event".

## Impact

- Code: `auto_reel_ng/event/metadata.py` (helper, `load_authored_document`), `auto_reel_ng/event/discovery.py`
  (`scan_event` and its private helpers), `auto_reel_ng/event/__init__.py` export if the helper is public.
- Tests: `tests/test_event_metadata.py`, `tests/test_event_reconcile.py`, `tests/test_api_events_failures.py`.
- Behaviour: an unsearchable event now reads as a per-event failure. The events list reports an
  `unreadable_disk` error row where it showed an empty summary; the detail answers 502 with the same kind.
- No new dependency, no config key, no API schema change.
