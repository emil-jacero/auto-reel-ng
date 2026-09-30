"""Tests for the committed OpenAPI artifact (tasks 1.2-1.3).

Two things are asserted: the schema can be produced with nothing running — no
service, no reachable database — and the committed ``web/openapi.json`` still
equals what the application produces today. The second is the check that makes a
backend response-model change fail ``pytest`` rather than drift silently into the
generated TypeScript (D-8, §4.10).
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from fastapi.openapi.utils import get_openapi
from fastapi.testclient import TestClient

from auto_reel_ng.api.app import create_app
from auto_reel_ng.api.openapi import (
    SCHEMA_DUMP_DATABASE_URL,
    build_openapi_schema,
    render_openapi_schema,
    schema_dump_settings,
)
from auto_reel_ng.api.schemas import EnqueueConflict, EventFailure, WsMessageType
from auto_reel_ng.event.reconcile import ClipStatus
from auto_reel_ng.persistence.job_store import CancelOutcome
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
    "EventErrorOut",
    "EventFailure",
    "EventDetailOut",
    "ClipStatus",
    "AnalysisOut",
    "EditorialWriteResult",
    "JobOut",
    "JobSummaryOut",
    "CancelResult",
    "CancelOutcome",
    "EnqueueConflict",
    "FreshResult",
    "StalenessOut",
    "StalenessReason",
    "JobStatus",
    "ProblemOut",
    "WsMessage",
    "WsMessageType",
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


def test_events_list_item_is_a_union_discriminated_by_kind() -> None:
    """A summary or an error row, told apart by ``kind`` — never a summary with nulls."""
    schema = build_openapi_schema()
    content = schema["paths"]["/api/v1/events"]["get"]["responses"]["200"]["content"]
    items = content["application/json"]["schema"]["items"]
    members = {ref["$ref"].rsplit("/", 1)[-1] for ref in items["oneOf"]}
    assert members == {"EventSummaryOut", "EventErrorOut"}
    assert items["discriminator"]["propertyName"] == "kind"
    assert set(items["discriminator"]["mapping"]) == {"event", "error"}


def test_kind_is_required_on_both_row_types() -> None:
    """Required, so the generated TypeScript discriminator is non-optional."""
    models = build_openapi_schema()["components"]["schemas"]
    for model, value in (("EventSummaryOut", "event"), ("EventErrorOut", "error")):
        assert "kind" in models[model]["required"], model
        assert models[model]["properties"]["kind"]["const"] == value


def test_event_failure_is_published_as_a_closed_enumeration() -> None:
    models = build_openapi_schema()["components"]["schemas"]
    assert models["EventErrorOut"]["properties"]["failure"]["$ref"].endswith("/EventFailure")
    published = models["EventFailure"]
    assert published["type"] == "string"
    assert published["enum"] == [failure.value for failure in EventFailure]
    assert len(published["enum"]) == 3


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


def test_clip_status_is_published_as_a_closed_enumeration() -> None:
    """A clip's status references reconcile's own enum, so a renamed status breaks the client."""
    models = build_openapi_schema()["components"]["schemas"]
    assert models["ClipOut"]["properties"]["status"]["$ref"].endswith("/ClipStatus")

    published = models["ClipStatus"]
    assert published["type"] == "string"
    assert published["enum"] == [status.value for status in ClipStatus]
    assert set(published["enum"]) == {"new", "active", "missing", "ignored"}


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


def test_the_latest_job_publishes_its_fields_as_the_job_detail_does() -> None:
    """``JobSummaryOut`` is a projection of ``JobOut``: every field it has is defined there
    identically, so a generated client types each one the same in both places, and the four
    fields a summary always had stay the only required ones."""
    models = build_openapi_schema()["components"]["schemas"]
    summary, detail = models["JobSummaryOut"], models["JobOut"]
    assert list(summary["properties"]) == [
        "id",
        "status",
        "progress",
        "created_at",
        "started_at",
        "finished_at",
    ]
    for name, field in summary["properties"].items():
        assert field == detail["properties"][name], name
    assert summary["required"] == ["id", "status", "progress", "created_at"]


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


#: The problem responses each editorial route declares (editorial-client-contract).
EXPECTED_EDITORIAL_RESPONSES = {
    "get": {"404", "502"},
    "put": {"400", "404", "412", "502"},
}


def test_editorial_routes_declare_their_responses_and_etag() -> None:
    """Exactly the documented error codes as ``ProblemOut``, and the 200's ``ETag`` header."""
    schema = build_openapi_schema()
    for method, expected in EXPECTED_EDITORIAL_RESPONSES.items():
        responses = schema["paths"]["/api/v1/events/{event_id}/reel"][method]["responses"]
        declared = {code for code in responses if code not in {"200", "422"}}
        assert declared == expected, f"{method}: {sorted(declared)}"
        for code in expected:
            ref = responses[code]["content"]["application/json"]["schema"]["$ref"]
            assert ref.endswith("/ProblemOut"), f"{method} {code}: {ref}"
        assert "ETag" in responses["200"]["headers"], method


#: The responses each jobs route declares besides its success and FastAPI's 422, by
#: published model (jobs-client-contract; the enqueue's 502 from jobs-project-guards).
EXPECTED_JOBS_RESPONSES = {
    ("post", "/api/v1/jobs"): {
        "200": "FreshResult",
        "404": "ProblemOut",
        "409": "ProblemOut",
        "502": "ProblemOut",
    },
    ("get", "/api/v1/jobs/{job_id}"): {"404": "ProblemOut"},
    ("post", "/api/v1/jobs/{job_id}/cancel"): {"404": "ProblemOut"},
}


def test_jobs_routes_declare_their_responses() -> None:
    """Exactly the documented codes, each described by its own published model."""
    schema = build_openapi_schema()
    for (method, path), expected in EXPECTED_JOBS_RESPONSES.items():
        responses = schema["paths"][path][method]["responses"]
        success = "201" if path == "/api/v1/jobs" else "200"
        declared = {code for code in responses if code not in {success, "422"}}
        assert declared == set(expected), f"{method} {path}: {sorted(declared)}"
        for code, model in expected.items():
            ref = responses[code]["content"]["application/json"]["schema"]["$ref"]
            assert ref.endswith(f"/{model}"), f"{method} {path} {code}: {ref}"
    created = schema["paths"]["/api/v1/jobs"]["post"]["responses"]["201"]
    assert created["content"]["application/json"]["schema"]["$ref"].endswith("/JobOut")


def test_fresh_result_status_is_a_required_constant() -> None:
    """Required, so the generated type is a non-optional ``status: "fresh"``."""
    fresh = build_openapi_schema()["components"]["schemas"]["FreshResult"]
    assert fresh["properties"]["status"]["const"] == "fresh"
    assert "status" in fresh["required"]


def test_cancel_outcome_is_published_as_a_closed_enumeration() -> None:
    models = build_openapi_schema()["components"]["schemas"]
    assert models["CancelResult"]["properties"]["outcome"]["$ref"].endswith("/CancelOutcome")
    published = models["CancelOutcome"]
    assert published["type"] == "string"
    assert published["enum"] == [outcome.value for outcome in CancelOutcome]


def test_the_problem_body_declares_job_id_and_jobs_document_their_event() -> None:
    models = build_openapi_schema()["components"]["schemas"]
    assert "job_id" in models["ProblemOut"]["properties"]
    description = models["JobOut"]["properties"]["event_dir"]["description"]
    assert "the event's id" in description.lower()
    assert "event_id" in description


def _non_null(field: dict) -> dict:
    """The one non-null member of an optional field's ``anyOf``."""
    (member,) = [member for member in field["anyOf"] if member != {"type": "null"}]
    return member


def test_the_enqueue_conflict_is_published_as_a_closed_enumeration() -> None:
    """``conflict`` tells a client which 409 it got; ``claimed_by`` names the other events."""
    models = build_openapi_schema()["components"]["schemas"]
    problem = models["ProblemOut"]["properties"]
    assert _non_null(problem["conflict"])["$ref"].endswith("/EnqueueConflict")
    published = models["EnqueueConflict"]
    assert published["type"] == "string"
    assert published["enum"] == [conflict.value for conflict in EnqueueConflict]
    assert published["enum"] == ["active_job", "output_collision"]
    assert _non_null(problem["claimed_by"]) == {"type": "array", "items": {"type": "string"}}


def test_the_websocket_frame_is_published_without_a_path() -> None:
    """Named components for the frame and its type set; no HTTP operation invented."""
    schema = build_openapi_schema()
    models = schema["components"]["schemas"]
    frame = models["WsMessage"]
    assert frame["properties"]["type"]["$ref"].endswith("/WsMessageType")
    assert frame["properties"]["jobs"]["items"]["$ref"].endswith("/JobOut")
    assert set(frame["required"]) == {"type", "jobs"}
    published = models["WsMessageType"]
    assert published["type"] == "string"
    assert published["enum"] == [message_type.value for message_type in WsMessageType]
    assert published["enum"] == ["snapshot", "delta"]
    assert "/api/v1/ws/jobs" not in schema["paths"]
    assert not [path for path in schema["paths"] if "/ws/" in path]


def test_the_frame_merge_keeps_the_components_the_routes_publish() -> None:
    """Merge-if-absent: the frame's ``$ref``s resolve to the routes' own ``JobOut``."""
    app = create_app(schema_dump_settings())
    routes_only = get_openapi(title=app.title, version=app.version, routes=app.routes)
    merged = app.openapi()["components"]["schemas"]
    for name, definition in routes_only["components"]["schemas"].items():
        assert merged[name] == definition, name
    assert set(merged) - set(routes_only["components"]["schemas"]) == {
        "WsMessage",
        "WsMessageType",
    }


def test_the_schema_hook_is_idempotent() -> None:
    app = create_app(schema_dump_settings())
    first = copy.deepcopy(app.openapi())
    second = app.openapi()
    assert second == first
    assert list(second["components"]["schemas"]) == list(first["components"]["schemas"])


def test_the_served_schema_is_the_committed_one() -> None:
    """``/openapi.json`` goes through the same hook, so it publishes the frame too."""
    served = TestClient(create_app(schema_dump_settings())).get("/openapi.json")
    assert served.status_code == 200
    assert served.json() == json.loads(render_openapi_schema())


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
