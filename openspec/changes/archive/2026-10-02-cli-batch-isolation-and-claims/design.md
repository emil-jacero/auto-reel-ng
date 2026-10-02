## Context

See proposal.md, "Why", for the four findings. Current state on `origin/main` at `d683264`, after the three gates merged
(`auto_reel_ng/cli/commands.py`, 927 lines; pylint's `max-module-lines` is 1000):

- `cmd_import` (line 493) loops `_import_event` bare. `_legacy_source` calls `exists()` on `metadata.yaml`
  and `reel.yaml`, `_import_event` calls `reel_path.exists()`, and `_read_yaml` / `_has_version` read with
  `path.read_text(encoding="utf-8")` and a ruamel safe `YAML().load`. `_has_version` catches only `OSError`.
- `cmd_enqueue` (line 626) calls `store.active_job(...)`, then `store.enqueue(...)` (which is `submit(...)
  .job_id`), and reports from the pre-read. `JobStore.submit` returns `Submission(job_id, created)`.
- `_checked_document(ref, today, order)` (line 128) is `load_or_seed` + `require_processable` with
  `except EventMetadataError` / `except ReelError`. It is called by `cmd_scan`, `_staleness_filter` (render)
  and, through `_checked_documents`, by `cmd_enqueue` and `cmd_adopt_renders`.
- Everything after the claim check in those four commands lists the folder again: `cmd_scan` calls
  `scan_event`, `compute_fingerprint` calls it (`staleness/fingerprint.py:112`), `prepare_and_persist` calls
  `prepare_event`, which calls it. An `OSError` from any of those today ends the command.
- `ReelParseError` is how the loaders already report "this file cannot be read, is not UTF-8, or is
  malformed", with the path in the message (`reel/parser.py` `load_document`, `loads_document`).

**Interfaces consumed from the gate changes (all merged; checked against `d683264` when this change was
re-based, names and import paths below are the real ones):**

| From | Interface | Behaviour relied on |
|---|---|---|
| `engine-output-claims` | `event.claims.checked_claim(event_dir, *, order, today) -> (ReelDocument \| None, str \| None)` | `ReelError`, `EventMetadataError` and `OSError` become a reason; a failure returns `(None, reason)`; never raises those |
| `event-permission-errors` | `event.metadata.reel_exists(path) -> bool` | `False` only for "no such file" / "not a directory"; a `PermissionError` propagates |
| `event-permission-errors` | `scan_event` raises `PermissionError` for an unsearchable folder instead of returning an empty listing | |
| `cli-project-context-module` | `cli.context.project_context(args)` replaces `commands._project_context` | already adopted by `commands.py`; this change does not touch it |

## Goals / Non-Goals

**Goals:**

- No per-event failure in `import` ends the batch, and none is reported as success.
- `enqueue`'s report and count come from the insert, so they cannot disagree with the table.
- `scan`, `render`, `enqueue` and `adopt-renders` agree with the service on what an unreadable event is, and
  never answer "no file" for a lookup the disk refused.

**Non-Goals:**

- Re-implementing claim selection or `reel_exists` in the CLI (both come from the gates).
- Changing which events `_output_collisions` compares or its message. It keeps checking the selected events
  only (so `--years` still narrows it); the engine's layout-aware `output_collision` is for the API and the
  worker, and adopting its message formatter here would couple this change to a signature that did not
  exist yet, for identical wording.
- Changing any exit code beyond adding `import`'s failure exit.

## Decisions

**1. `import` gets one safe reader and one per-event guard.** A private
`_read_legacy_mapping(path: Path) -> Mapping[str, object]` replaces `_read_yaml` and is also what
`_has_version` uses:

```python
def _read_legacy_mapping(path: Path) -> Mapping[str, object]:
    """Read ``path`` as a YAML mapping; raise ReelParseError (path in the message) otherwise."""
    # OSError -> "cannot read"; UnicodeDecodeError -> "not UTF-8 text"; any ruamel failure
    # (YAMLError and the odd non-YAMLError, as reel/parser.loads_document) -> "malformed YAML";
    # a non-mapping root -> "legacy metadata must be a mapping, got <type>".

def _has_version(path: Path) -> bool:
    return "version" in _read_legacy_mapping(path)
```

`cmd_import` wraps each event:

```python
failed = 0
for ref in ctx.events:
    try:
        result = _import_event(ref.event_dir, overwrite=args.overwrite)
    except (OSError, ReelError) as exc:
        print(f"ERROR  {ref.event_dir.name}: {exc}")
        failed += 1
        continue
    ...
print(f"\nimported {imported} event(s)" + (f", {failed} failed" if failed else ""))
return 1 if failed else 0
```

The reader maps everything the *content* can do to `ReelParseError`, so the guard's set stays two types
(`OSError` for the disk, `ReelError` for content and for `import_legacy`'s `ReelImportError`). Anything else
(a real bug) still propagates: Principle I tolerates per-event isolation, not hiding programming errors. The
three `exists()` calls in `_legacy_source` and `_import_event` become `reel_exists` (and, for
`metadata.yaml`, the same helper: it takes any file path), so a `PermissionError` is that event's `ERROR`.
`_has_version` no longer swallows `OSError` and no longer returns `False` for an unreadable file: that
turned "I cannot tell" into "legacy", which then re-read the same file and crashed anyway. A malformed
`reel.yaml` with no `metadata.yaml` is therefore an `ERROR`, not a silent skip.
Alternative: the triage's guard tuple `(OSError, UnicodeDecodeError, YAMLError, ValueError, ReelError)` with
the reader unchanged. Rejected: five types to keep in step with the reader, and a bare `ValueError` catch
would also swallow bugs; mapping inside the reader keeps the set closed.
Alternative: reuse `reel.parser.load_document` as the reader. Rejected: it validates a v0 document and
routes a versionless file to the legacy importer, which is the very thing `import` is calling.

**2. `enqueue` calls `submit` and branches on `created`.**

```python
submission = store.submit(project_root_str, event_dir, device=device, force=force,
                          fingerprint=fingerprint.combined)
if submission.created:
    created += 1
    print(f"+  {name}: queued ({submission.job_id})")
else:
    print(f"=  {name}: already queued/running ({submission.job_id})")
```

Output text is unchanged. `JobStore.enqueue` stays (other callers, tests); only its CLI use ends. The
`JobStore.active_job` docstring drops "the `enqueue` CLI command classifies its report" and keeps "the API
refuses a duplicate before running the staleness gate". Docstring only; `persistence/` behaviour is
unchanged. The test stubs `submit` to return `Submission(job_id, created=False)` while `active_job` returns
`None`: with the old code the line would say `+ queued`.

**3. `_checked_document` delegates to `checked_claim`, and also lists the folder once.**

```python
def _checked_document(ref, today, order):
    document, reason = checked_claim(ref.event_dir, order=order, today=today)
    if document is None:
        return None, reason
    try:
        scan_event(ref.event_dir)  # fail here, per event, not in fingerprinting or adoption
    except OSError as exc:
        return None, f"cannot read {ref.event_dir}: {exc}"
    return document, None
```

`checked_claim` is the engine's claim rule and says what *claims a path*. A folder that holds a readable
`reel.yaml` but cannot be listed (mode `0300`) loads and is processable, so it passes that rule, and then
`scan_event` raises inside `compute_fingerprint` or `prepare_event`, which none of the four commands guard.
Listing once in the one place all four commands already share closes that without a `try` in each loop
(`commands.py` is near its line cap). The cost is one more directory listing and a `stat` per entry per
event; no media is decoded and nothing is written. The same-folder `0600` case (cannot search) is already
`checked_claim`'s `PermissionError`, via `reel_exists`. `cmd_scan`'s own presence test becomes
`reel_exists(...)`, for consistency: after the claim step it cannot differ.
Alternative: ask `engine-output-claims` for the listing inside `checked_claim`. Rejected here: its scope is
fixed by its proposal and it has not merged; if it already lists the folder when this is applied, the probe
is dropped in the same task and the test stays.
Alternative: a `try/except OSError` around the body of each command's loop. Rejected: four copies, and
`_staleness_filter`, `cmd_scan`, `cmd_enqueue` and `cmd_adopt_renders` would each need their own report path.

**4. Failure behaviour, idempotency, and files.** Per event, the failure reports are `ERROR  <event>:
<reason>` and set a non-zero exit; nothing is rendered, enqueued, adopted or written for that event.
`import` re-run: events already imported are `SKIP`ped (v2 `reel.yaml`, no `--overwrite`), failed events
fail again with the same reason, and a failed `write_document` leaves the old file (it writes a temp file
and renames). `enqueue` re-run: reports `=` for each active job and creates none. `--force` and a worker
restart do not interact with any of this. No `RENDER_GRAPH_VERSION` bump: rendered bytes for identical
inputs are unchanged. No decision here outlives the change, so there is no HLD D-n entry.

**5. Module size.** `commands.py` must stay under pylint's 1000-line cap. `cli-project-context-module` has already
freed about 70 lines (927 now); this change is roughly neutral (the reader replaces two helpers, `submit`
removes lines, the guard and probe add about 15). If the file would exceed 990 lines after the change, the
import helpers (`_import_event`, `_legacy_source`, `_report_import`, `_read_legacy_mapping`, `_has_version`)
move unchanged to `cli/legacy_import.py` in the same task, a pure move with `cmd_import` left in
`commands.py`.

## Risks / Trade-offs

- [The gate interfaces differ from the proposals read] -> tasks 1.1 checks `checked_claim`, `reel_exists`,
  `project_context` against the merged code first; only names and import paths may change. A behavioural
  mismatch (for example `checked_claim` raising) is a blocker to report, not to paper over.
- [A gate's archive changes the current text of a requirement modified here] -> `engine-output-claims`
  modifies two other `headless-cli` requirements (collision, per-event isolation) and
  `cli-project-context-module` one more; none of the three requirements here (`scan`, `import`, `enqueue`).
  The apply step still re-copies the current text from `openspec/specs/headless-cli/spec.md` before
  archiving.
- [Listing the folder twice] -> one directory listing per event, no decode; `scan` and `enqueue` already
  list it again during fingerprinting.
- [`_has_version` no longer swallows an unreadable `reel.yaml`] -> intended: it is now that event's `ERROR`.
  A legacy-only tree (`metadata.yaml`, no `reel.yaml`) never reaches it.
