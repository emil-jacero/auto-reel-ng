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
import warnings
from pathlib import Path

import pytest
from fastapi.openapi.utils import get_openapi
from fastapi.testclient import TestClient

from auto_reel_ng.api.app import create_app
from auto_reel_ng.api.openapi import (
    SCHEMA_DUMP_DATABASE_URL,
    build_openapi_schema,
    render_openapi_schema,
    schema_dump_settings,
)
from auto_reel_ng.api.schemas import (
    EnqueueConflict,
    EventFailure,
    ThumbnailFailure,
    WsMessageType,
)
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
    "/api/v1/events/{event_id}/thumbnail",
    "/api/v1/events/{event_id}/media",
    "/api/v1/events/{event_id}/movie",
    "/api/v1/events/{event_id}/proxy",
    "/api/v1/events/{event_id}/filmstrip",
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
    "ProxyState",
    "ProxyOut",
    "ProxyFactsOut",
    "ProxyFilmstripOut",
    "MovieOut",
    "MovieChapterOut",
    "AnalysisOut",
    "EditorialWriteResult",
    "JobOut",
    "JobSummaryOut",
    "CancelResult",
    "CancelOutcome",
    "EnqueueConflict",
    "ThumbnailFailure",
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
    # The rename reason is published, and its description says what it means.
    assert "output_renamed" in published["enum"]
    assert "output_renamed" in published["description"]


def test_clip_status_is_published_as_a_closed_enumeration() -> None:
    """A clip's status references reconcile's own enum, so a renamed status breaks the client."""
    models = build_openapi_schema()["components"]["schemas"]
    assert models["ClipOut"]["properties"]["status"]["$ref"].endswith("/ClipStatus")

    published = models["ClipStatus"]
    assert published["type"] == "string"
    assert published["enum"] == [status.value for status in ClipStatus]
    assert set(published["enum"]) == {"new", "active", "missing", "ignored"}


def test_the_excluded_clip_read_model_is_published() -> None:
    """The flags a client reads to mark an excluded clip and to gate Render are in the schema."""
    models = build_openapi_schema()["components"]["schemas"]

    assert models["ClipOut"]["properties"]["excluded"]["type"] == "boolean"
    blocking = models["EventDetailOut"]["properties"]["blocking_missing"]
    assert blocking["type"] == "array"
    assert blocking["items"]["type"] == "string"
    summary = models["EventSummaryOut"]
    for name in ("ignored_count", "blocking_missing_count"):
        assert summary["properties"][name]["type"] == "integer"
        assert name in summary["required"]


def test_the_clip_duration_is_published_as_a_nullable_optional_number() -> None:
    """A client treats a null and an absent ``duration`` alike as "not known"."""
    clip = build_openapi_schema()["components"]["schemas"]["ClipOut"]

    assert clip["properties"]["duration"]["anyOf"] == [{"type": "number"}, {"type": "null"}]
    assert "duration" not in clip["required"]


def test_the_clip_proxy_is_published_as_a_nullable_optional_object() -> None:
    """A client treats a null and an absent ``proxy`` alike as "not known" (never ``absent``)."""
    clip = build_openapi_schema()["components"]["schemas"]["ClipOut"]

    assert clip["properties"]["proxy"]["anyOf"] == [
        {"$ref": "#/components/schemas/ProxyOut"},
        {"type": "null"},
    ]
    assert "proxy" not in clip["required"]


def test_the_proxy_state_is_published_as_a_closed_enumeration() -> None:
    """Four values, so the generated client's union is exhaustive (D-8, §4.10)."""
    models = build_openapi_schema()["components"]["schemas"]

    assert models["ProxyOut"]["properties"]["state"]["$ref"].endswith("/ProxyState")
    assert "state" in models["ProxyOut"]["required"]
    assert models["ProxyState"]["type"] == "string"
    assert models["ProxyState"]["enum"] == ["absent", "ready", "stale", "failed"]


def test_the_proxy_members_other_than_state_are_optional_and_nullable() -> None:
    proxy = build_openapi_schema()["components"]["schemas"]["ProxyOut"]

    assert set(proxy["required"]) == {"state"}
    for name in ("facts", "version", "reason"):
        assert {"type": "null"} in proxy["properties"][name]["anyOf"], name
    assert proxy["properties"]["version"]["anyOf"][0] == {"type": "string"}
    assert proxy["properties"]["reason"]["anyOf"][0] == {"type": "string"}
    assert proxy["properties"]["facts"]["anyOf"][0] == {
        "$ref": "#/components/schemas/ProxyFactsOut"
    }


def test_the_proxy_facts_require_every_fact_and_the_frame_rate_is_a_fraction_of_integers() -> None:
    models = build_openapi_schema()["components"]["schemas"]
    facts = models["ProxyFactsOut"]

    assert set(facts["required"]) == set(facts["properties"])
    assert facts["properties"]["duration"]["type"] == "number"
    for name in ("fps_num", "fps_den", "width", "height"):
        assert facts["properties"][name]["type"] == "integer", name
    # Facts the probe could not give are null, never defaulted: required but nullable.
    for name, kind in (("vfr", "boolean"), ("rotation", "integer"), ("audio_codec", "string")):
        assert facts["properties"][name]["anyOf"] == [{"type": kind}, {"type": "null"}], name
    film = models["ProxyFilmstripOut"]
    assert set(film["required"]) == {"tile_width", "tile_height", "columns", "tiles", "interval"}
    assert {film["properties"][name]["type"] for name in film["required"]} == {"integer"}


def test_the_events_list_does_not_reference_the_proxy_models() -> None:
    """The list keeps its clip counts: no per-clip proxy fact on it."""
    content = build_openapi_schema()["paths"]["/api/v1/events"]["get"]["responses"]["200"][
        "content"
    ]
    assert "Proxy" not in json.dumps(content)


def test_the_detail_publishes_the_movie_object() -> None:
    """``movie`` is optional and nullable; its chapters are nullable ("unknown"), never required."""
    models = build_openapi_schema()["components"]["schemas"]
    detail, movie, chapter = models["EventDetailOut"], models["MovieOut"], models["MovieChapterOut"]

    assert detail["properties"]["movie"]["anyOf"] == [
        {"$ref": "#/components/schemas/MovieOut"},
        {"type": "null"},
    ]
    assert "movie" not in detail["required"]
    assert set(movie["required"]) == {"recorded_at", "fingerprint"}
    assert movie["properties"]["recorded_at"] == {
        "type": "string",
        "format": "date-time",
        "title": "Recorded At",
    }
    assert movie["properties"]["fingerprint"]["type"] == "string"
    assert movie["properties"]["chapters"]["anyOf"] == [
        {"items": {"$ref": "#/components/schemas/MovieChapterOut"}, "type": "array"},
        {"type": "null"},
    ]
    assert "chapters" not in movie["required"]
    assert set(chapter["required"]) == {"name", "start"}
    assert chapter["properties"]["name"]["type"] == "string"
    assert chapter["properties"]["start"]["type"] == "number"


def test_the_events_list_does_not_reference_the_movie_models() -> None:
    schema = build_openapi_schema()
    content = schema["paths"]["/api/v1/events"]["get"]["responses"]["200"]["content"]
    assert "Movie" not in json.dumps(content)
    rows = schema["components"]["schemas"]
    assert "movie" not in rows["EventSummaryOut"]["properties"]
    assert "movie" not in rows["EventErrorOut"]["properties"]


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
    identically, so a generated client types each one the same in both places. The two times
    stay optional; the id, status, progress, creation time, cancel flag and requeue count are
    required."""
    models = build_openapi_schema()["components"]["schemas"]
    summary, detail = models["JobSummaryOut"], models["JobOut"]
    assert list(summary["properties"]) == [
        "id",
        "status",
        "progress",
        "created_at",
        "cancel_requested",
        "requeue_count",
        "started_at",
        "finished_at",
    ]
    for name, field in summary["properties"].items():
        assert field == detail["properties"][name], name
    assert summary["required"] == [
        "id",
        "status",
        "progress",
        "created_at",
        "cancel_requested",
        "requeue_count",
    ]


def test_the_verdict_publishes_the_two_movie_names_as_optional_nullable_strings() -> None:
    verdict = build_openapi_schema()["components"]["schemas"]["StalenessOut"]
    for name in ("renamed_from", "output_name"):
        field = verdict["properties"][name]
        assert {"type": "string"} in field["anyOf"] and {"type": "null"} in field["anyOf"], name
        assert name not in verdict.get("required", []), name
    assert list(verdict["properties"]) == ["stale", "reasons", "renamed_from", "output_name"]
    assert verdict["required"] == ["stale"]


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


def test_the_analysis_route_publishes_its_problem_responses() -> None:
    """A 404 and a 502 in the shared problem shape; no 503, the route never needs the database."""
    operation = build_openapi_schema()["paths"]["/api/v1/events/{event_id}/analysis"]["get"]
    responses = operation["responses"]
    assert set(responses) - {"422"} == {"200", "404", "502"}
    for code in ("404", "502"):
        ref = responses[code]["content"]["application/json"]["schema"]["$ref"]
        assert ref.endswith("/ProblemOut"), code


def test_the_thumbnail_route_publishes_its_parameters_and_responses() -> None:
    """``clip`` required, ``v`` and ``If-None-Match`` optional; a JPEG 200, a 304; problems."""
    operation = build_openapi_schema()["paths"]["/api/v1/events/{event_id}/thumbnail"]["get"]
    query = {param["name"]: param for param in operation["parameters"] if param["in"] == "query"}
    assert set(query) == {"clip", "v"}
    assert query["clip"]["required"] is True
    assert query["clip"]["schema"]["type"] == "string"
    assert query["v"]["required"] is False
    assert _non_null(query["v"]["schema"]) == {"type": "string"}
    header = {param["name"]: param for param in operation["parameters"] if param["in"] == "header"}
    assert set(header) == {"If-None-Match"}
    assert header["If-None-Match"]["required"] is False

    responses = operation["responses"]
    assert set(responses) - {"422"} == {"200", "304", "404", "502"}
    assert "503" not in responses
    assert list(responses["200"]["content"]) == ["image/jpeg"]
    assert responses["200"]["content"]["image/jpeg"]["schema"] == {
        "type": "string",
        "format": "binary",
    }
    for code in ("200", "304"):
        assert {"ETag", "Cache-Control"} <= set(responses[code]["headers"]), code
    assert "content" not in responses["304"]
    for code in ("404", "502"):
        ref = responses[code]["content"]["application/json"]["schema"]["$ref"]
        assert ref.endswith("/ProblemOut"), code


@pytest.mark.parametrize(
    ("path", "required_query"),
    [("/api/v1/events/{event_id}/media", {"clip"}), ("/api/v1/events/{event_id}/movie", set())],
)
def test_the_media_routes_publish_their_parameters_and_responses(
    path: str, required_query: set[str]
) -> None:
    """``get`` and ``head`` alike: ``v`` and the four request headers optional; video 200/206,
    304, 400, 416; problems; a distinct ``operationId`` each."""
    paths = build_openapi_schema()["paths"][path]
    assert {"get", "head"} <= set(paths)
    assert paths["get"]["operationId"] != paths["head"]["operationId"]
    for method in ("get", "head"):
        operation = paths[method]
        query = {
            param["name"]: param for param in operation["parameters"] if param["in"] == "query"
        }
        assert set(query) == required_query | {"v"}, method
        assert {name for name, param in query.items() if param["required"]} == required_query
        assert _non_null(query["v"]["schema"]) == {"type": "string"}
        header = {
            param["name"]: param for param in operation["parameters"] if param["in"] == "header"
        }
        assert set(header) == {"If-None-Match", "If-Modified-Since", "Range", "If-Range"}, method
        assert not any(param["required"] for param in header.values())

        responses = operation["responses"]
        assert set(responses) == {"200", "206", "304", "400", "404", "416", "502", "422"}, method
        for code in ("200", "206"):
            assert responses[code]["content"] == {
                "video/*": {"schema": {"type": "string", "format": "binary"}}
            }, code
        for code in ("206", "416"):
            assert "Content-Range" in responses[code]["headers"], code
        assert set(responses["200"]["headers"]) == {
            "ETag",
            "Last-Modified",
            "Cache-Control",
            "Accept-Ranges",
            "Content-Disposition",
        }
        assert set(responses["304"]["headers"]) == {"ETag", "Cache-Control"}
        for code in ("304", "400", "416"):
            assert "content" not in responses[code], code
        for code in ("404", "502"):
            ref = responses[code]["content"]["application/json"]["schema"]["$ref"]
            assert ref.endswith("/ProblemOut"), code


@pytest.mark.parametrize(
    ("path", "media_type"),
    [
        ("/api/v1/events/{event_id}/proxy", "video/mp4"),
        ("/api/v1/events/{event_id}/filmstrip", "image/jpeg"),
    ],
)
def test_the_proxy_routes_publish_their_exact_types_and_the_media_behaviour(
    path: str, media_type: str
) -> None:
    """Proxy and filmstrip: the media routes' codes and headers, one exact binary type."""
    paths = build_openapi_schema()["paths"][path]
    assert {"get", "head"} <= set(paths)
    assert paths["get"]["operationId"] != paths["head"]["operationId"]
    for method in ("get", "head"):
        operation = paths[method]
        query = {
            param["name"]: param for param in operation["parameters"] if param["in"] == "query"
        }
        assert set(query) == {"clip", "v"}, method
        assert {name for name, param in query.items() if param["required"]} == {"clip"}
        header = {
            param["name"]: param for param in operation["parameters"] if param["in"] == "header"
        }
        assert set(header) == {"If-None-Match", "If-Modified-Since", "Range", "If-Range"}, method
        assert not any(param["required"] for param in header.values())

        responses = operation["responses"]
        assert set(responses) == {"200", "206", "304", "400", "404", "416", "502", "422"}, method
        assert "503" not in responses
        for code in ("200", "206"):
            assert responses[code]["content"] == {
                media_type: {"schema": {"type": "string", "format": "binary"}}
            }, code
        for code in ("206", "416"):
            assert "Content-Range" in responses[code]["headers"], code
        assert set(responses["200"]["headers"]) == {
            "ETag",
            "Last-Modified",
            "Cache-Control",
            "Accept-Ranges",
            "Content-Disposition",
        }
        for code in ("404", "502"):
            ref = responses[code]["content"]["application/json"]["schema"]["$ref"]
            assert ref.endswith("/ProblemOut"), code


def test_the_clip_and_movie_responses_keep_their_video_wildcard() -> None:
    """The proxy routes copy the shared responses; the originals stay untouched."""
    paths = build_openapi_schema()["paths"]
    for path in ("/api/v1/events/{event_id}/media", "/api/v1/events/{event_id}/movie"):
        assert list(paths[path]["get"]["responses"]["200"]["content"]) == ["video/*"]


def test_building_the_schema_raises_no_duplicate_operation_id_warning() -> None:
    """Two decorators, not one ``api_route`` with two methods (which repeats the id)."""
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        build_openapi_schema()


#: The responses each jobs route declares besides its success and FastAPI's 422, by
#: published model (jobs-client-contract; the enqueue's 502 from jobs-project-guards).
EXPECTED_JOBS_RESPONSES = {
    ("post", "/api/v1/jobs"): {
        "200": "FreshResult",
        "404": "ProblemOut",
        "409": "ProblemOut",
        "502": "ProblemOut",
        "503": "ProblemOut",
    },
    ("get", "/api/v1/jobs"): {"503": "ProblemOut"},
    ("get", "/api/v1/jobs/{job_id}"): {"404": "ProblemOut", "503": "ProblemOut"},
    ("post", "/api/v1/jobs/{job_id}/cancel"): {"404": "ProblemOut", "503": "ProblemOut"},
}


def test_jobs_routes_declare_their_responses() -> None:
    """Exactly the documented codes, each described by its own published model."""
    schema = build_openapi_schema()
    for (method, path), expected in EXPECTED_JOBS_RESPONSES.items():
        responses = schema["paths"][path][method]["responses"]
        success = "201" if (method, path) == ("post", "/api/v1/jobs") else "200"
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
    assert published["enum"] == ["active_job", "output_collision", "missing_clips"]
    assert _non_null(problem["claimed_by"]) == {"type": "array", "items": {"type": "string"}}
    assert _non_null(problem["missing"]) == {"type": "array", "items": {"type": "string"}}


def test_the_thumbnail_failure_is_published_as_a_closed_enumeration() -> None:
    """A field of its own on the problem body; the events failure set keeps its three values."""
    models = build_openapi_schema()["components"]["schemas"]
    problem = models["ProblemOut"]["properties"]
    assert _non_null(problem["thumbnail_failure"])["$ref"].endswith("/ThumbnailFailure")
    published = models["ThumbnailFailure"]
    assert published["type"] == "string"
    assert published["enum"] == [failure.value for failure in ThumbnailFailure]
    assert published["enum"] == ["thumbnail_failed"]
    assert _non_null(problem["failure"])["$ref"].endswith("/EventFailure")
    assert models["EventFailure"]["enum"] == [
        "unparseable_reel_yaml",
        "unusable_metadata",
        "unreadable_disk",
    ]


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
    assert published["enum"] == ["snapshot", "delta", "heartbeat"]
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
