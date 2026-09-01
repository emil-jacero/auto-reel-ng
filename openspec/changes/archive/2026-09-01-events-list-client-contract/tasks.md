## 1. staleness/ — the reason vocabulary becomes a closed type

- [x] 1.1 Add `StalenessReason(StrEnum)` to `staleness/gate.py` with the six members, replacing the
      `NO_MANIFEST` / `MISSING_OUTPUT` constants, and retype `Verdict.reasons` as
      `tuple[StalenessReason, ...]`; the gate maps a component name through `StalenessReason(name)` so an
      unknown component raises rather than emitting an untyped reason.
- [x] 1.2 Test in `tests/test_staleness_gate.py` that the enum's component members are exactly
      `fingerprint.COMPONENTS`, in order, and that every reason a verdict cites is both an enum member and
      equal to the string it was before (the existing gate tests must pass unmodified).

## 2. api/ — publish the closed set

- [x] 2.1 Retype `StalenessOut.reasons` as `List[StalenessReason]` in `api/schemas.py`.
- [x] 2.2 Test in `tests/test_api_openapi.py` that the generated schema describes the reasons as an
      enumeration of exactly the gate's reasons, not an unconstrained string array.

## 3. api/ — events reads fail loud in the shared problem shape

- [x] 3.1 Add the shared database-failure mapping in `api/routes/events.py`: `SQLAlchemyError` →
      `service_unavailable(..., check="database")` on both `GET /api/v1/events` and
      `GET /api/v1/events/{event_id}`, plus `ReelError` → `bad_gateway(...)` on the list, matching the
      detail route's existing mapping. Nothing broader is caught.
- [x] 3.2 Test (`requires_db`-marked where a live container is needed) that a pointed-at-nothing database
      yields the 503 problem body with `check="database"` on both reads, that an unparseable `reel.yaml`
      yields the list's 502 problem body, that no partial list and no absent-looking `latest_job` is ever
      returned for a failed read, and that the detail route's existing 404/502 behaviour is unchanged.

## 4. Regenerate the committed client artifacts

- [x] 4.1 `.venv/bin/python -m auto_reel_ng.api.openapi > web/openapi.json` — the drift test fails until
      this is done, which is the pipeline working as designed.
- [x] 4.2 Regenerate `web/src/api/schema.d.ts` in the Node container and confirm the reasons field is a
      string union rather than `string[]`.

## 5. Documentation

- [x] 5.1 Extend `docs/high-level-design.md` §4.10's pipeline text: a closed vocabulary must be typed as
      an enumeration for the schema→types checks to cover it; a bare `list[str]` is a hole neither check
      can see.

## 6. Validation gates

- [x] 6.1 `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`
- [x] 6.2 `.venv/bin/python -m mypy auto_reel_ng`
- [x] 6.3 `.venv/bin/python -m pylint auto_reel_ng`
- [x] 6.4 `.venv/bin/python -m pytest` (podman required for `requires_db`; if unavailable, run
      `-m "not requires_db"` and say so rather than skipping silently)
- [x] 6.5 `tsc --noEmit` in the container — the frontend gate, against the regenerated types
