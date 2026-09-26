"""Tests for the committed OpenAPI artifact (tasks 1.2-1.3).

Two things are asserted: the schema can be produced with nothing running — no
service, no reachable database — and the committed ``web/openapi.json`` still
equals what the application produces today. The second is the check that makes a
backend response-model change fail ``pytest`` rather than drift silently into the
generated TypeScript (D-8, §4.10).
"""

from __future__ import annotations

import json
from pathlib import Path

from auto_reel_ng.api.openapi import (
    SCHEMA_DUMP_DATABASE_URL,
    build_openapi_schema,
    render_openapi_schema,
)
from auto_reel_ng.persistence.models import JobStatus
from auto_reel_ng.staleness.gate import StalenessReason

#: The committed artifact `openapi-typescript` reads (repo root / web/openapi.json).
COMMITTED_SCHEMA = Path(__file__).resolve().parent.parent / "web" / "openapi.json"

#: Endpoints the client is generated against; a rename here is a client-visible break.
EXPECTED_PATHS = {
    "/healthz",
    "/api/v1/events",
    "/api/v1/events/{event_id}",
    "/api/v1/events/{event_id}/analysis",
    "/api/v1/events/{event_id}/reel",
    "/api/v1/jobs",
    "/api/v1/jobs/{job_id}",
    "/api/v1/jobs/{job_id}/cancel",
}

#: Response models the generated types are derived from.
EXPECTED_MODELS = {
    "EventSummaryOut",
    "EventDetailOut",
    "AnalysisOut",
    "EditorialWriteResult",
    "JobOut",
    "JobSummaryOut",
    "CancelResult",
    "StalenessOut",
    "StalenessReason",
    "JobStatus",
    "ProblemOut",
}

#: The problem responses each events read declares (events-list-job-status-contract).
EXPECTED_PROBLEM_RESPONSES = {
    "/api/v1/events": {"502", "503"},
    "/api/v1/events/{event_id}": {"404", "502", "503"},
}


def test_schema_builds_with_no_database_reachable() -> None:
    """The dump URL points at a closed port: building the schema must not connect."""
    assert "127.0.0.1:1" in SCHEMA_DUMP_DATABASE_URL
    schema = build_openapi_schema()
    assert schema["openapi"].startswith("3.")
    assert schema["info"]["title"] == "auto-reel-ng API"


def test_schema_describes_the_current_endpoints() -> None:
    schema = build_openapi_schema()
    assert EXPECTED_PATHS <= set(schema["paths"])


def test_schema_describes_the_response_models() -> None:
    schema = build_openapi_schema()
    assert EXPECTED_MODELS <= set(schema["components"]["schemas"])


def test_events_list_response_is_the_event_summary_model() -> None:
    """The wiring-check page reads this shape through the generated types."""
    schema = build_openapi_schema()
    content = schema["paths"]["/api/v1/events"]["get"]["responses"]["200"]["content"]
    items = content["application/json"]["schema"]["items"]
    assert items["$ref"].endswith("/EventSummaryOut")


def test_staleness_reasons_are_published_as_a_closed_enumeration() -> None:
    """The reasons field is an enumeration of the gate's reasons, not ``string[]``.

    This is what makes a renamed reason a client build error: ``openapi-typescript``
    turns the referenced enum into a string union (D-8, §4.10). A bare
    ``{"type": "string"}`` array item here would be the hole this asserts against.
    """
    schema = build_openapi_schema()
    reasons = schema["components"]["schemas"]["StalenessOut"]["properties"]["reasons"]
    assert reasons["type"] == "array"
    assert reasons["items"]["$ref"].endswith("/StalenessReason")

    published = schema["components"]["schemas"]["StalenessReason"]
    assert published["type"] == "string"
    assert published["enum"] == [reason.value for reason in StalenessReason]


def test_job_status_fields_are_published_as_the_job_status_enumeration() -> None:
    """Every job-status response field references the store's own enum, not ``string``."""
    schema = build_openapi_schema()
    models = schema["components"]["schemas"]
    for model in ("JobSummaryOut", "JobOut", "CancelResult"):
        status = models[model]["properties"]["status"]
        assert status.get("$ref", "").endswith("/JobStatus"), f"{model}.status: {status}"

    published = models["JobStatus"]
    assert published["type"] == "string"
    assert published["enum"] == [status.value for status in JobStatus]


def test_events_reads_declare_their_problem_responses() -> None:
    """Exactly the documented error codes, each described by ``ProblemOut``."""
    schema = build_openapi_schema()
    for path, expected in EXPECTED_PROBLEM_RESPONSES.items():
        responses = schema["paths"][path]["get"]["responses"]
        declared = {code for code in responses if code not in {"200", "422"}}
        assert declared == expected, f"{path}: {sorted(declared)}"
        for code in expected:
            ref = responses[code]["content"]["application/json"]["schema"]["$ref"]
            assert ref.endswith("/ProblemOut"), f"{path} {code}: {ref}"


def test_committed_schema_is_not_stale() -> None:
    """`web/openapi.json` must equal the schema the application produces today."""
    committed_text = COMMITTED_SCHEMA.read_text(encoding="utf-8")
    current_text = render_openapi_schema()
    if committed_text == current_text:
        return

    committed = json.loads(committed_text)
    current = json.loads(current_text)
    differences: list[str] = []
    for label, left, right in (
        ("paths", set(committed["paths"]), set(current["paths"])),
        (
            "components.schemas",
            set(committed.get("components", {}).get("schemas", {})),
            set(current.get("components", {}).get("schemas", {})),
        ),
    ):
        if removed := sorted(left - right):
            differences.append(f"{label} no longer produced: {', '.join(removed)}")
        if added := sorted(right - left):
            differences.append(f"{label} newly produced: {', '.join(added)}")
    for name in sorted(set(committed["paths"]) & set(current["paths"])):
        if committed["paths"][name] != current["paths"][name]:
            differences.append(f"paths[{name}] changed")
    shared_models = set(committed.get("components", {}).get("schemas", {})) & set(
        current.get("components", {}).get("schemas", {})
    )
    for name in sorted(shared_models):
        if committed["components"]["schemas"][name] != current["components"]["schemas"][name]:
            differences.append(f"components.schemas[{name}] changed")

    detail = "\n  ".join(differences or ["the serialized documents differ byte-for-byte"])
    raise AssertionError(
        "web/openapi.json is out of date — regenerate it and the generated types:\n"
        "  .venv/bin/python -m auto_reel_ng.api.openapi > web/openapi.json\n"
        f"Disagreement:\n  {detail}"
    )
