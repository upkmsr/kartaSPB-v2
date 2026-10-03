import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from app.upi.arcgis import (
    ArcGisClient,
    ArcGisServiceError,
    CompletenessError,
    HttpResponse,
    SourceHttpError,
    SourceResponseError,
    SourceUnavailableError,
    fixture_transport,
)
from app.upi.config import load_source_config

FIXTURE = Path("tests/fixtures/upi/toris_construction.json")


def response(payload: Any, status: int = 200) -> HttpResponse:
    body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    return HttpResponse(status, {"Content-Type": "application/json"}, body, 1)


def test_arcgis_id_chunk_pagination_is_complete_ordered_and_multi_page() -> None:
    config = replace(
        load_source_config(), page_size=2, expected_count_min=4, expected_count_max=4
    )
    base_transport = fixture_transport(FIXTURE)
    calls: list[dict[str, str]] = []

    def recording_transport(url: str, params: dict[str, str], timeout: int) -> HttpResponse:
        calls.append(dict(params))
        return base_transport(url, params, timeout)

    evidence = ArcGisClient(config, recording_transport).fetch_all()

    assert evidence.count == 4
    assert evidence.object_ids == (10, 20, 30, 40)
    assert [feature["attributes"]["OBJECTID"] for feature in evidence.features] == [
        10,
        20,
        30,
        40,
    ]
    page_calls = [call for call in calls if "objectIds" in call]
    assert [call["objectIds"] for call in page_calls] == ["10,20", "30,40"]
    assert all(call["outSR"] == "4326" for call in page_calls)
    assert all(call["orderByFields"] == "OBJECTID ASC" for call in page_calls)


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        (b"not-json", SourceResponseError),
        ({"error": {"code": 400, "message": "bad query"}}, ArcGisServiceError),
    ],
)
def test_arcgis_rejects_invalid_or_error_payload(payload: Any, expected: type[Exception]) -> None:
    config = replace(load_source_config(), max_retries=0)

    def transport(url: str, params: dict[str, str], timeout: int) -> HttpResponse:
        return response(payload)

    with pytest.raises(expected):
        ArcGisClient(config, transport).metadata()


def test_arcgis_timeout_and_http_500_are_structured_failures() -> None:
    config = replace(load_source_config(), max_retries=0)

    def timeout_transport(url: str, params: dict[str, str], timeout: int) -> HttpResponse:
        raise SourceUnavailableError("timeout")

    def http_transport(url: str, params: dict[str, str], timeout: int) -> HttpResponse:
        return response({"message": "failure"}, status=500)

    with pytest.raises(SourceUnavailableError):
        ArcGisClient(config, timeout_transport).metadata()
    with pytest.raises(SourceHttpError) as captured:
        ArcGisClient(config, http_transport).metadata()
    assert captured.value.http_status == 500


def test_arcgis_count_mismatch_and_duplicate_ids_fail_closed() -> None:
    config = replace(load_source_config(), expected_count_min=0, expected_count_max=10)
    base_transport = fixture_transport(FIXTURE)

    def mismatch_transport(url: str, params: dict[str, str], timeout: int) -> HttpResponse:
        if params.get("returnCountOnly") == "true":
            return response({"count": 5})
        return base_transport(url, params, timeout)

    def duplicate_transport(url: str, params: dict[str, str], timeout: int) -> HttpResponse:
        if params.get("returnIdsOnly") == "true":
            return response({"objectIdFieldName": "OBJECTID", "objectIds": [10, 10, 20, 30]})
        return base_transport(url, params, timeout)

    with pytest.raises(CompletenessError, match="count mismatch"):
        ArcGisClient(config, mismatch_transport).fetch_all()
    with pytest.raises(CompletenessError, match="duplicates"):
        ArcGisClient(config, duplicate_transport).fetch_all()


def test_arcgis_second_page_failure_never_returns_partial_evidence() -> None:
    config = replace(
        load_source_config(),
        page_size=2,
        max_retries=0,
        expected_count_min=4,
        expected_count_max=4,
    )
    base_transport = fixture_transport(FIXTURE)

    def transport(url: str, params: dict[str, str], timeout: int) -> HttpResponse:
        if params.get("objectIds") == "30,40":
            return response({"message": "page failed"}, status=500)
        return base_transport(url, params, timeout)

    with pytest.raises(SourceHttpError):
        ArcGisClient(config, transport).fetch_all()
