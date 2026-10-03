import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from shapely.geometry import MultiPolygon, Polygon, mapping

from app.upi.arcgis import CompletenessError, SchemaChangedError, SourceResponseError
from app.upi.config import UpiSourceConfig


@dataclass(frozen=True)
class NormalizedFeature:
    source_object_id: str
    source_version: str | None
    observed_at: datetime
    effective_from: datetime | None
    effective_to: datetime | None
    status: str | None
    properties: dict[str, Any]
    raw_locator: str
    payload_hash: str
    geometry: dict[str, Any]


@dataclass(frozen=True)
class NormalizedSnapshot:
    features: tuple[NormalizedFeature, ...]
    schema_fingerprint: str
    payload_checksum: str
    geometry_counts: dict[str, int]


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def validate_schema(metadata: dict[str, Any], config: UpiSourceConfig) -> str:
    if metadata.get("geometryType") != config.geometry_type:
        raise SchemaChangedError(
            f"Expected geometry type {config.geometry_type}, got {metadata.get('geometryType')!r}"
        )
    extent = metadata.get("extent")
    spatial_reference = extent.get("spatialReference") if isinstance(extent, dict) else None
    if not isinstance(spatial_reference, dict) or (
        spatial_reference.get("wkid") != config.source_wkid
        or spatial_reference.get("latestWkid") != config.source_latest_wkid
    ):
        raise SchemaChangedError(
            f"ArcGIS source CRS changed: expected {config.source_wkid}/"
            f"{config.source_latest_wkid}, got {spatial_reference!r}"
        )
    raw_fields = metadata.get("fields")
    if not isinstance(raw_fields, list):
        raise SchemaChangedError("ArcGIS metadata has no fields list")
    actual: dict[str, dict[str, Any]] = {}
    for field in raw_fields:
        if isinstance(field, dict) and isinstance(field.get("name"), str):
            actual[field["name"]] = field
    fingerprint_fields: list[dict[str, Any]] = []
    for contract in config.fields:
        field = actual.get(contract.source)
        if field is None:
            if contract.required:
                raise SchemaChangedError(f"Required ArcGIS field disappeared: {contract.source}")
            continue
        if field.get("type") != contract.type:
            raise SchemaChangedError(
                f"ArcGIS field {contract.source} type changed from {contract.type} "
                f"to {field.get('type')!r}"
            )
        fingerprint_fields.append(
            {
                "name": contract.source,
                "type": field.get("type"),
                "nullable": field.get("nullable"),
                "required": contract.required,
            }
        )
    return sha256_json(
        {
            "geometry_type": metadata.get("geometryType"),
            "identity_field": config.identity_field,
            "object_id_field": config.object_id_field,
            "output_srid": config.output_srid,
            "source_wkid": config.source_wkid,
            "source_latest_wkid": config.source_latest_wkid,
            "fields": fingerprint_fields,
        }
    )


def normalize_features(
    raw_features: tuple[dict[str, Any], ...],
    metadata: dict[str, Any],
    config: UpiSourceConfig,
    *,
    observed_at: datetime | None = None,
) -> NormalizedSnapshot:
    observed = observed_at or datetime.now(UTC)
    schema_fingerprint = validate_schema(metadata, config)
    normalized: list[NormalizedFeature] = []
    identities: set[str] = set()
    geometry_counts: dict[str, int] = {}
    field_map = {field.source: field.target for field in config.fields}
    for raw_feature in raw_features:
        attributes = raw_feature.get("attributes")
        geometry = raw_feature.get("geometry")
        if not isinstance(attributes, dict):
            raise SourceResponseError("ArcGIS feature attributes are missing")
        for field in config.fields:
            if field.required and field.source not in attributes:
                raise SchemaChangedError(f"Required normalized field is missing: {field.source}")
        raw_identity = attributes.get(config.identity_field)
        if not isinstance(raw_identity, str) or not raw_identity.strip():
            raise CompletenessError("ArcGIS feature has no stable GUID")
        try:
            identity = str(UUID(raw_identity.strip())).upper()
        except ValueError as exc:
            raise CompletenessError(f"ArcGIS feature GUID is invalid: {raw_identity!r}") from exc
        if identity in identities:
            raise CompletenessError(f"Duplicate stable source identity: {identity}")
        identities.add(identity)
        object_id = attributes.get(config.object_id_field)
        if isinstance(object_id, bool) or not isinstance(object_id, int):
            raise CompletenessError("ArcGIS feature has an invalid transport object ID")
        geojson_geometry = esri_polygon_to_geojson(geometry)
        geometry_type = str(geojson_geometry["type"])
        geometry_counts[geometry_type] = geometry_counts.get(geometry_type, 0) + 1
        properties = {
            target: attributes.get(source)
            for source, target in field_map.items()
            if source != config.identity_field
        }
        properties["guid"] = identity
        stable_payload = {
            "source_object_id": identity,
            "properties": properties,
            "geometry": geojson_geometry,
            "normalization_version": config.normalization_version,
        }
        normalized.append(
            NormalizedFeature(
                source_object_id=identity,
                source_version=None,
                observed_at=observed,
                effective_from=None,
                effective_to=None,
                status=(
                    str(attributes["STATUSOBJECT"])
                    if attributes.get("STATUSOBJECT") is not None
                    else None
                ),
                properties=properties,
                raw_locator=f"{config.layer_url}/{object_id}",
                payload_hash=sha256_json(stable_payload),
                geometry=geojson_geometry,
            )
        )
    normalized.sort(key=lambda feature: feature.source_object_id)
    payload_checksum = sha256_json(
        [
            {
                "source_object_id": feature.source_object_id,
                "payload_hash": feature.payload_hash,
            }
            for feature in normalized
        ]
    )
    return NormalizedSnapshot(
        features=tuple(normalized),
        schema_fingerprint=schema_fingerprint,
        payload_checksum=payload_checksum,
        geometry_counts=geometry_counts,
    )


def esri_polygon_to_geojson(raw_geometry: Any) -> dict[str, Any]:
    if not isinstance(raw_geometry, dict) or not isinstance(raw_geometry.get("rings"), list):
        raise SourceResponseError("ArcGIS polygon geometry is missing rings")
    ring_polygons: list[tuple[list[list[float]], Polygon]] = []
    for raw_ring in raw_geometry["rings"]:
        if not isinstance(raw_ring, list) or len(raw_ring) < 4:
            raise SourceResponseError("ArcGIS polygon ring is invalid")
        coordinates: list[list[float]] = []
        for point in raw_ring:
            if (
                not isinstance(point, list)
                or len(point) < 2
                or isinstance(point[0], bool)
                or isinstance(point[1], bool)
                or not isinstance(point[0], (int, float))
                or not isinstance(point[1], (int, float))
            ):
                raise SourceResponseError("ArcGIS polygon coordinate is invalid")
            lon, lat = float(point[0]), float(point[1])
            if not (-180 <= lon <= 180 and -90 <= lat <= 90):
                raise SourceResponseError("ArcGIS polygon is not in EPSG:4326")
            coordinates.append([lon, lat])
        if coordinates[0] != coordinates[-1]:
            coordinates.append(coordinates[0])
        polygon = Polygon(coordinates)
        if polygon.is_empty or not polygon.is_valid or polygon.area == 0:
            raise SourceResponseError("ArcGIS polygon ring is empty or invalid")
        ring_polygons.append((coordinates, polygon))
    if not ring_polygons:
        raise SourceResponseError("ArcGIS polygon has no rings")

    depths: list[int] = []
    for index, (_, polygon) in enumerate(ring_polygons):
        representative = polygon.representative_point()
        depths.append(
            sum(
                1
                for other_index, (_, other) in enumerate(ring_polygons)
                if other_index != index
                and other.area > polygon.area
                and other.contains(representative)
            )
        )
    polygons: list[Polygon] = []
    for index, (shell, shell_polygon) in enumerate(ring_polygons):
        if depths[index] % 2 != 0:
            continue
        holes = [
            ring
            for hole_index, (ring, hole_polygon) in enumerate(ring_polygons)
            if depths[hole_index] == depths[index] + 1
            and shell_polygon.contains(hole_polygon.representative_point())
        ]
        polygon = Polygon(shell, holes)
        if polygon.is_empty or not polygon.is_valid:
            raise SourceResponseError("ArcGIS polygon topology is invalid")
        polygons.append(polygon)
    if not polygons:
        raise SourceResponseError("ArcGIS polygon has no outer ring")
    result: Polygon | MultiPolygon = polygons[0] if len(polygons) == 1 else MultiPolygon(polygons)
    if not result.is_valid:
        raise SourceResponseError("Normalized ArcGIS geometry is invalid")
    return dict(mapping(result))
