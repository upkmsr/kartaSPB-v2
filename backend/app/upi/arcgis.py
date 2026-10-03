import json
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.upi.config import UpiSourceConfig


class SourceError(RuntimeError):
    code = "SOURCE_ERROR"
    health_status = "IMPORT_FAILED"

    def __init__(self, message: str, *, http_status: int | None = None) -> None:
        super().__init__(message)
        self.http_status = http_status


class SourceUnavailableError(SourceError):
    code = "SOURCE_UNAVAILABLE"
    health_status = "SOURCE_UNAVAILABLE"


class SourceHttpError(SourceUnavailableError):
    code = "HTTP_ERROR"


class SourceResponseError(SourceError):
    code = "INVALID_RESPONSE"


class ArcGisServiceError(SourceError):
    code = "ARCGIS_ERROR"


class CompletenessError(SourceError):
    code = "INCOMPLETE_SNAPSHOT"
    health_status = "PARTIALLY_UPDATED"


class SchemaChangedError(SourceError):
    code = "SCHEMA_CHANGED"
    health_status = "SCHEMA_CHANGED"


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes
    elapsed_ms: int


Transport = Callable[[str, Mapping[str, str], int], HttpResponse]


@dataclass(frozen=True)
class ArcGisEvidence:
    metadata: dict[str, Any]
    count: int
    object_ids: tuple[int, ...]
    features: tuple[dict[str, Any], ...]
    http_status: int
    content_type: str | None
    response_headers: dict[str, str]
    latency_ms: int


@dataclass(frozen=True)
class ArcGisProbe:
    metadata: dict[str, Any]
    count: int
    object_id_count: int
    sample_features: tuple[dict[str, Any], ...]
    http_status: int
    latency_ms: int


def urllib_transport(url: str, params: Mapping[str, str], timeout_seconds: int) -> HttpResponse:
    full_url = f"{url}?{urlencode(params)}"
    request = Request(
        full_url,
        headers={"Accept": "application/json", "User-Agent": "kartaSPB-v2/UPI-A"},
    )
    started = time.monotonic()
    try:
        with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
            return HttpResponse(
                status=response.status,
                headers=dict(response.headers.items()),
                body=response.read(),
                elapsed_ms=round((time.monotonic() - started) * 1000),
            )
    except HTTPError as exc:
        return HttpResponse(
            status=exc.code,
            headers=dict(exc.headers.items()) if exc.headers else {},
            body=exc.read(),
            elapsed_ms=round((time.monotonic() - started) * 1000),
        )
    except (TimeoutError, URLError) as exc:
        raise SourceUnavailableError(f"ArcGIS request failed: {exc}") from exc


class ArcGisClient:
    def __init__(self, config: UpiSourceConfig, transport: Transport = urllib_transport) -> None:
        self.config = config
        self.transport = transport

    def _request(self, url: str, params: Mapping[str, str]) -> tuple[dict[str, Any], HttpResponse]:
        last_error: SourceUnavailableError | None = None
        for attempt in range(self.config.max_retries + 1):
            try:
                response = self.transport(url, params, self.config.timeout_seconds)
            except SourceUnavailableError as exc:
                last_error = exc
                if attempt < self.config.max_retries:
                    continue
                raise
            retryable_status = response.status == 429 or response.status >= 500
            if retryable_status and attempt < self.config.max_retries:
                continue
            if response.status != 200:
                raise SourceHttpError(
                    f"ArcGIS HTTP status {response.status}", http_status=response.status
                )
            try:
                payload = json.loads(response.body)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise SourceResponseError("ArcGIS response is not valid JSON") from exc
            if not isinstance(payload, dict):
                raise SourceResponseError("ArcGIS response must be a JSON object")
            service_error = payload.get("error")
            if service_error:
                raise ArcGisServiceError(f"ArcGIS returned an error: {service_error}")
            return payload, response
        assert last_error is not None
        raise last_error

    def metadata(self) -> tuple[dict[str, Any], HttpResponse]:
        return self._request(self.config.layer_url, {"f": "pjson"})

    def count(self) -> tuple[int, HttpResponse]:
        payload, response = self._request(
            self.config.query_url,
            {"where": "1=1", "returnCountOnly": "true", "f": "json"},
        )
        count = payload.get("count")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise SourceResponseError("ArcGIS count response is invalid")
        return count, response

    def object_ids(self) -> tuple[tuple[int, ...], HttpResponse]:
        payload, response = self._request(
            self.config.query_url,
            {"where": "1=1", "returnIdsOnly": "true", "f": "json"},
        )
        object_id_field = payload.get("objectIdFieldName")
        if object_id_field != self.config.object_id_field:
            raise SchemaChangedError(
                f"ArcGIS object ID field changed: {object_id_field!r}"
            )
        raw_ids = payload.get("objectIds")
        if not isinstance(raw_ids, list) or any(
            isinstance(value, bool) or not isinstance(value, int) for value in raw_ids
        ):
            raise SourceResponseError("ArcGIS objectIds response is invalid")
        ids = tuple(sorted(raw_ids))
        if len(ids) != len(set(ids)):
            raise CompletenessError("ArcGIS objectIds response contains duplicates")
        return ids, response

    def feature_page(self, object_ids: Sequence[int]) -> tuple[list[dict[str, Any]], HttpResponse]:
        if not object_ids:
            return [], HttpResponse(200, {}, b"{}", 0)
        payload, response = self._request(
            self.config.query_url,
            {
                "objectIds": ",".join(str(value) for value in object_ids),
                "outFields": ",".join(self.config.out_fields),
                "returnGeometry": "true",
                "outSR": str(self.config.output_srid),
                "orderByFields": f"{self.config.object_id_field} ASC",
                "f": "json",
            },
        )
        if payload.get("geometryType") != self.config.geometry_type:
            raise SchemaChangedError("ArcGIS query geometry type changed")
        spatial_reference = payload.get("spatialReference")
        if not isinstance(spatial_reference, dict) or spatial_reference.get("wkid") != 4326:
            raise SourceResponseError("ArcGIS query did not return EPSG:4326 geometry")
        raw_features = payload.get("features")
        if not isinstance(raw_features, list) or any(
            not isinstance(feature, dict) for feature in raw_features
        ):
            raise SourceResponseError("ArcGIS features response is invalid")
        features = list(raw_features)
        try:
            features.sort(key=lambda feature: feature["attributes"][self.config.object_id_field])
        except (KeyError, TypeError) as exc:
            raise CompletenessError("ArcGIS feature is missing its transport object ID") from exc
        returned_ids = [
            feature["attributes"][self.config.object_id_field] for feature in features
        ]
        if returned_ids != sorted(object_ids):
            raise CompletenessError(
                f"ArcGIS page IDs differ from request: requested={list(object_ids)!r}, "
                f"returned={returned_ids!r}"
            )
        return features, response

    def fetch_all(self) -> ArcGisEvidence:
        metadata, metadata_response = self.metadata()
        count, count_response = self.count()
        if not self.config.expected_count_min <= count <= self.config.expected_count_max:
            raise CompletenessError(
                f"ArcGIS count {count} is outside approved range "
                f"{self.config.expected_count_min}..{self.config.expected_count_max}"
            )
        object_ids, ids_response = self.object_ids()
        if len(object_ids) != count:
            raise CompletenessError(
                f"ArcGIS count mismatch: count={count}, objectIds={len(object_ids)}"
            )
        features: list[dict[str, Any]] = []
        responses = [metadata_response, count_response, ids_response]
        for offset in range(0, len(object_ids), self.config.page_size):
            page_ids = object_ids[offset : offset + self.config.page_size]
            page, response = self.feature_page(page_ids)
            features.extend(page)
            responses.append(response)
        if len(features) != count:
            raise CompletenessError(
                f"ArcGIS feature count mismatch: expected={count}, retrieved={len(features)}"
            )
        return ArcGisEvidence(
            metadata=metadata,
            count=count,
            object_ids=object_ids,
            features=tuple(features),
            http_status=responses[-1].status,
            content_type=responses[-1].headers.get("Content-Type"),
            response_headers=_safe_headers(responses[-1].headers),
            latency_ms=sum(response.elapsed_ms for response in responses),
        )

    def probe(self, sample_size: int = 3) -> ArcGisProbe:
        if sample_size < 1 or sample_size > 10:
            raise ValueError("ArcGIS probe sample size must be between 1 and 10")
        metadata, metadata_response = self.metadata()
        count, count_response = self.count()
        if not self.config.expected_count_min <= count <= self.config.expected_count_max:
            raise CompletenessError(
                f"ArcGIS count {count} is outside approved range "
                f"{self.config.expected_count_min}..{self.config.expected_count_max}"
            )
        object_ids, ids_response = self.object_ids()
        if len(object_ids) != count:
            raise CompletenessError(
                f"ArcGIS count mismatch: count={count}, objectIds={len(object_ids)}"
            )
        features, sample_response = self.feature_page(object_ids[:sample_size])
        return ArcGisProbe(
            metadata=metadata,
            count=count,
            object_id_count=len(object_ids),
            sample_features=tuple(features),
            http_status=sample_response.status,
            latency_ms=sum(
                response.elapsed_ms
                for response in (
                    metadata_response,
                    count_response,
                    ids_response,
                    sample_response,
                )
            ),
        )


def _safe_headers(headers: Mapping[str, str]) -> dict[str, str]:
    allowed = {"content-type", "etag", "last-modified", "date"}
    return {key.lower(): value for key, value in headers.items() if key.lower() in allowed}


def fixture_transport(path: Path) -> Transport:
    with path.open(encoding="utf-8") as file:
        fixture = json.load(file)
    if not isinstance(fixture, dict):
        raise ValueError("ArcGIS fixture must be a JSON object")
    metadata = fixture.get("metadata")
    features = fixture.get("features")
    if not isinstance(metadata, dict) or not isinstance(features, list):
        raise ValueError("ArcGIS fixture must contain metadata and features")
    by_id: dict[int, dict[str, Any]] = {}
    for feature in features:
        try:
            object_id = feature["attributes"]["OBJECTID"]
        except (KeyError, TypeError) as exc:
            raise ValueError("ArcGIS fixture feature has no OBJECTID") from exc
        if isinstance(object_id, bool) or not isinstance(object_id, int) or object_id in by_id:
            raise ValueError("ArcGIS fixture OBJECTIDs must be unique integers")
        by_id[object_id] = feature

    def transport(url: str, params: Mapping[str, str], timeout_seconds: int) -> HttpResponse:
        del timeout_seconds
        if params.get("returnCountOnly") == "true":
            payload: dict[str, Any] = {"count": len(by_id)}
        elif params.get("returnIdsOnly") == "true":
            payload = {"objectIdFieldName": "OBJECTID", "objectIds": sorted(by_id)}
        elif "objectIds" in params:
            requested = [int(value) for value in params["objectIds"].split(",")]
            payload = {
                "geometryType": metadata.get("geometryType"),
                "spatialReference": {"wkid": 4326, "latestWkid": 4326},
                "features": [by_id[value] for value in requested if value in by_id],
            }
        elif params == {"f": "pjson"}:
            payload = metadata
        else:
            raise ValueError(f"Unexpected ArcGIS fixture request: {url} {params}")
        return HttpResponse(
            status=200,
            headers={"Content-Type": "application/json", "ETag": '"fixture-v1"'},
            body=canonical_fixture_json(payload),
            elapsed_ms=1,
        )

    return transport


def canonical_fixture_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
