## Why

The staleness gate (HLD §4.13, change-detection) tells an operator that an event's movie was renamed, but not
which file is meant. After a retitle, `auto-reel scan` prints `stale: editorial, output_renamed` and nothing else:
neither the movie still on disk (the old name) nor the file the next render will write (the new name). The
operator who sees this has to work both names out by hand from the title, date, location and **D-9** (HLD §7 and
§4.3, `<output>/<YYYY>/<YYYY-MM-DD> - <title>[ - <location>].mp4`), which is exactly the lookup the gate has just
done. A status line that withholds the one fact it computed is a weaker form of the legacy problem that HLD §2
row 5 warns about: the tool knew and did not say.

Verified on `main` at `bbd5494` (triage ran at `6a7fe16`), in triage item `output-renamed-names-neither-old-nor-new-file`:

- `staleness/gate.py`: `Verdict` is `(stale, reasons)` and nothing else. `_renamed_output(manifest, expected)`
  finds the old movie's `Path`, and `evaluate()` uses it only to choose between `OUTPUT_RENAMED` and `OUTPUT`;
  the path is dropped. `rendered_output()` exposes the same path to the movie route, but not to the verdict.
- `cli/commands.py` `_print_inventory`: `print(f"  stale: {', '.join(verdict.reasons)}")`.
- `api/schemas.py` and `api/events_read.py` carry the reasons only. This change does **not** touch them; see
  Non-goals.

HLD §6 **phase 8** (GUI v1): a follow-up to `output-renamed-reason` (archived 2026-10-01). It depends on no open
§8 research item.

## What Changes

- **`Verdict` gains two optional fields, `renamed_from` and `output_name`.** Both are `None` unless the verdict
  cites `output_renamed`; when it does, both are set. `renamed_from` is the file name of the movie the last render
  left on disk, as found by the gate. `output_name` is the file name of the event's expected output, which the next
  render writes. Existing consumers that read only `stale` and `reasons` are unaffected, and the vocabulary of
  reasons does not change.
- **`auto-reel scan` names both files.** The `output_renamed` entry of the `stale:` line is followed by
  ``(was '<old>', now '<new>')``, so `stale: editorial, output_renamed (was '2024-06-27 - Grillning med
  Grannar.mp4', now '2024-06-27 - Grillkväll med grannarna.mp4')`. A verdict without `output_renamed` prints as
  before.
- **Tests.** Gate tests pin the detail for each rename shape (retitle, location, date moved across years) and its
  absence in every other verdict; CLI tests pin the new `scan` line.
- No decision changes: the rename reason still never changes whether an event is stale.

Rendered output for identical inputs: unchanged, so **no `RENDER_GRAPH_VERSION` bump**. The staleness fingerprint
inputs, the manifest schema, `reel.yaml` and `config.yaml`: unchanged. No Alembic migration, no rescan.

## Capabilities

### New Capabilities
<!-- None. -->

### Modified Capabilities
- `change-detection`: the staleness gate's verdict carries the old and new movie file names whenever it cites
  `output_renamed`.
- `headless-cli`: `scan` prints those two names beside the `output_renamed` reason.

## Non-goals

- **API and GUI.** `StalenessOut` and the event screens keep publishing the reasons only. Exposing
  `renamed_from`/`output_name` there is a purely additive follow-up, change `api-job-summary-and-renamed-fields`,
  which consumes the two `Verdict` field names fixed here.
- A new reason, a change of which events are stale, or any change to what a render writes, keeps or deletes
  (decided in `output-renamed-reason`; deleting or pruning superseded renamed movies is held for the operator).
- The `render`, `enqueue` and `adopt-renders` output: those paths do not print reasons today and keep not doing so.
- A manifest change. How the gate finds the old movie is owned by `staleness-output-lookup`.

## Impact

- Packages: `auto_reel_ng/staleness` (`gate.py`), `auto_reel_ng/cli` (`commands.py`). CLI only; the API is not
  touched (Principle V: the engine and CLI surface lands first, the API follows).
- Tests: `tests/test_staleness_gate.py`, `tests/test_cli_render_staleness.py`, `tests/test_cli_scan.py`.
- Docs: the `README.md` paragraph on `output_renamed` and its `scan` example.
- Ordering: both gates, `staleness-output-lookup` (same `gate.py`) and `cli-serve-forced-stop-and-lifespan` (same
  `commands.py`), are already on `main`; the change builds on them.
