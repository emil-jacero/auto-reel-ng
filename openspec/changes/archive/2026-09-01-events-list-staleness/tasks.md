## 1. api/ — resolve the look defaults once per request

- [x] 1.1 Change `staleness_for` to take the resolved look defaults as a required parameter instead of
      calling `resolve_look_defaults(load_project_config(...))` itself; update `get_event` and the
      editorial write route to resolve them once per request and pass them down. Existing detail and
      editorial-write tests must pass unchanged — this task moves a call, it changes no behavior.
- [x] 1.2 Test in `tests/test_api_events.py` that editing `config.yaml`'s look defaults between two
      requests changes the reported verdict, proving the value is resolved per request and never cached
      across them (D-A3: responses reflect disk changes).

## 2. api/ — staleness on the events list

- [x] 2.1 Add `staleness: StalenessOut` to `EventSummaryOut` in `api/schemas.py`.
- [x] 2.2 Take the `FfmpegRuntime` in `list_events`, resolve the look defaults once before the loop, and
      compute each event's verdict through the same `staleness_for` helper the detail path uses; pass
      `app.state.runtime` from the list route.
- [x] 2.3 Test the three-event case: one rendered and unchanged, one whose clips changed since its
      render, one never rendered — a single `GET /api/v1/events` reports fresh, stale citing the
      clip-set component, and stale citing the absent manifest. Marked `requires_db` (the list embeds
      `latest_job`).
- [x] 2.4 Test that list and detail return the identical verdict and reasons for the same event with no
      disk change between the two requests.
- [x] 2.5 Test that an event whose most recent job completed successfully is still reported stale after a
      clip is added — a completed job is not freshness.
- [x] 2.6 Test that serving the list over a project of events with no `reel.yaml` and no manifest creates
      no `reel.yaml`, no manifest and no output file, and that a malformed manifest yields a stale
      verdict rather than an error.
- [x] 2.7 Test, by counting calls during one list request over several events, that the project config is
      loaded exactly once and that the fingerprint is computed with the content-hash opt-in off.

## 3. Measurement and the design record

- [x] 3.1 Measure `GET /api/v1/events` before and after on a scratch copy with symlinked clips (never
      against `auto-reel-media/` itself) using the route's existing duration log; record both numbers in
      design.md's Open Questions and state whether the duplicate directory walk needs a follow-up.
- [x] 3.2 Extend the probe-free read-model paragraph in `docs/high-level-design.md` §4.9 to forbid
      content hashing on a whole-library read, in the same voice as the existing probe rule.

## 4. Validation gates

- [x] 4.1 `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`
- [x] 4.2 `.venv/bin/python -m mypy auto_reel_ng`
- [x] 4.3 `.venv/bin/python -m pylint auto_reel_ng`
- [x] 4.4 `.venv/bin/python -m pytest` (podman required for `requires_db`; if unavailable, run
      `-m "not requires_db"` and say so rather than skipping silently)
