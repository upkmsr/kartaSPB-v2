import json
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic
from typing import Any

from sqlalchemy import Engine, text

from app.upi.adapters import SourceAdapter, TorisConstructionAdapter
from app.upi.arcgis import ArcGisClient, SourceError, fixture_transport
from app.upi.config import RawRetentionMode, UpiSourceConfig
from app.upi.normalization import (
    NormalizedSnapshot,
    normalize_features,
    sha256_json,
    validate_schema,
)


@dataclass(frozen=True)
class ProbeReport:
    source: str
    adapter_version: str
    normalization_version: str
    status: str
    expected_count: int
    retrieved_count: int
    sampled_count: int
    schema_fingerprint: str
    payload_checksum: str
    geometries: dict[str, int]
    duration_ms: int
    import_run_id: None = None
    database_mutated: bool = False


@dataclass(frozen=True)
class SnapshotReport:
    source: str
    adapter_version: str
    normalization_version: str
    status: str
    expected_count: int
    retrieved_count: int
    schema_fingerprint: str
    payload_checksum: str
    geometries: dict[str, int]
    duration_ms: int
    import_run_id: int
    snapshot_id: int
    unchanged: bool


def probe_source(adapter: SourceAdapter) -> ProbeReport:
    started = monotonic()
    config = adapter.config
    probe = adapter.probe()
    normalized = normalize_features(probe.sample_features, probe.metadata, config)
    return ProbeReport(
        source=config.source_key,
        adapter_version=config.adapter_version,
        normalization_version=config.normalization_version,
        status="CURRENT",
        expected_count=probe.count,
        retrieved_count=probe.object_id_count,
        sampled_count=len(probe.sample_features),
        schema_fingerprint=validate_schema(probe.metadata, config),
        payload_checksum=normalized.payload_checksum,
        geometries=normalized.geometry_counts,
        duration_ms=round((monotonic() - started) * 1000),
    )


def bootstrap_source(engine: Engine, config: UpiSourceConfig) -> int:
    with engine.begin() as connection:
        source_id = int(
            connection.scalar(
                text(
                    """
                    INSERT INTO meta.dataset_sources
                        (name, provider, source_type, source_url, license, attribution)
                    VALUES
                        (:name, :provider, :source_type, :source_url, :license, :attribution)
                    ON CONFLICT (name) DO UPDATE SET
                        provider = EXCLUDED.provider,
                        source_type = EXCLUDED.source_type,
                        source_url = EXCLUDED.source_url,
                        license = EXCLUDED.license,
                        attribution = EXCLUDED.attribution,
                        updated_at = now()
                    RETURNING id
                    """
                ),
                {
                    "name": config.dataset_source_name,
                    "provider": config.provider,
                    "source_type": config.source_type,
                    "source_url": config.primary_url,
                    "license": config.license,
                    "attribution": config.attribution,
                },
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO upi.source_profiles
                    (source_id, source_key, adapter_key, adapter_version,
                     normalization_version, config_version, official_status,
                     provenance_kind, automation_level, service_type, primary_url,
                     service_url, access_mode, terms_status, raw_retention_mode,
                     retention_policy, refresh_mode, enabled)
                VALUES
                    (:source_id, :source_key, :adapter_key, :adapter_version,
                     :normalization_version, :config_version, :official_status,
                     :provenance_kind, :automation_level, :service_type, :primary_url,
                     :service_url, :access_mode, :terms_status, :raw_retention_mode,
                     CAST(:retention_policy AS jsonb), :refresh_mode, :enabled)
                ON CONFLICT (source_key) DO UPDATE SET
                    source_id = EXCLUDED.source_id,
                    adapter_key = EXCLUDED.adapter_key,
                    adapter_version = EXCLUDED.adapter_version,
                    normalization_version = EXCLUDED.normalization_version,
                    config_version = EXCLUDED.config_version,
                    official_status = EXCLUDED.official_status,
                    provenance_kind = EXCLUDED.provenance_kind,
                    automation_level = EXCLUDED.automation_level,
                    service_type = EXCLUDED.service_type,
                    primary_url = EXCLUDED.primary_url,
                    service_url = EXCLUDED.service_url,
                    access_mode = EXCLUDED.access_mode,
                    terms_status = EXCLUDED.terms_status,
                    raw_retention_mode = EXCLUDED.raw_retention_mode,
                    retention_policy = EXCLUDED.retention_policy,
                    refresh_mode = EXCLUDED.refresh_mode,
                    enabled = EXCLUDED.enabled,
                    updated_at = now()
                """
            ),
            {
                "source_id": source_id,
                "source_key": config.source_key,
                "adapter_key": config.adapter_key,
                "adapter_version": config.adapter_version,
                "normalization_version": config.normalization_version,
                "config_version": config.config_version,
                "official_status": config.official_status,
                "provenance_kind": config.provenance_kind,
                "automation_level": config.automation_level,
                "service_type": config.service_type,
                "primary_url": config.primary_url,
                "service_url": config.service_url,
                "access_mode": config.access_mode,
                "terms_status": config.terms_status.value,
                "raw_retention_mode": config.raw_retention_mode.value,
                "retention_policy": json.dumps(config.retention_policy),
                "refresh_mode": config.refresh_mode,
                "enabled": config.enabled,
            },
        )
    return source_id


def _start_run(engine: Engine, source_id: int, config: UpiSourceConfig) -> int:
    with engine.begin() as connection:
        run_id = int(
            connection.scalar(
                text(
                    """
                    INSERT INTO meta.import_runs
                        (source_id, status, profile, authoritative_snapshot, details)
                    VALUES
                        (:source_id, 'pending', :profile, false, CAST(:details AS jsonb))
                    RETURNING id
                    """
                ),
                {
                    "source_id": source_id,
                    "profile": config.source_key,
                    "details": json.dumps(
                        {
                            "adapter_version": config.adapter_version,
                            "normalization_version": config.normalization_version,
                            "scope": "upi_source_snapshot",
                        }
                    ),
                },
            )
        )
    with engine.begin() as connection:
        result = connection.execute(
            text(
                """
                UPDATE meta.import_runs
                SET status = 'running', started_at = now(), updated_at = now()
                WHERE id = :run_id AND status = 'pending'
                """
            ),
            {"run_id": run_id},
        )
        if result.rowcount != 1:
            raise RuntimeError(f"Could not start UPI import run {run_id}")
    return run_id


def snapshot_fixture(
    engine: Engine, config: UpiSourceConfig, fixture_path: Path
) -> SnapshotReport:
    with fixture_path.open(encoding="utf-8") as file:
        fixture_payload = json.load(file)
    fixture_features = fixture_payload.get("features")
    if not isinstance(fixture_features, list):
        raise ValueError("ArcGIS fixture has no features list")
    fixture_config = replace(
        config,
        expected_count_min=len(fixture_features),
        expected_count_max=len(fixture_features),
    )
    adapter = TorisConstructionAdapter(
        config,
        ArcGisClient(fixture_config, fixture_transport(fixture_path)),
    )
    return snapshot_source(
        engine,
        adapter,
        raw_payload=fixture_payload,
        raw_evidence_locator=f"fixture://{fixture_path.name}",
    )


def snapshot_source(
    engine: Engine,
    adapter: SourceAdapter,
    *,
    raw_payload: dict[str, Any] | None = None,
    raw_evidence_locator: str | None = None,
) -> SnapshotReport:
    config = adapter.config
    if raw_payload is not None and raw_evidence_locator is None:
        raise ValueError("Raw payload requires an evidence locator")
    if (
        raw_payload is not None
        and raw_evidence_locator is not None
        and not raw_evidence_locator.startswith("fixture://")
        and config.raw_retention_mode is not RawRetentionMode.FULL_RAW_ALLOWED
    ):
        raise PermissionError("Live raw payload retention is not authorized")
    started = monotonic()
    source_id = bootstrap_source(engine, config)
    run_id = _start_run(engine, source_id, config)
    try:
        evidence = adapter.fetch_snapshot()
        observed_at = datetime.now(UTC)
        normalized = adapter.normalize(evidence, observed_at=observed_at)
        evidence_checksum = sha256_json(
            raw_payload
            if raw_payload is not None
            else {"metadata": evidence.metadata, "features": evidence.features}
        )
        snapshot_id, unchanged = _persist_success(
            engine,
            source_id,
            run_id,
            config,
            normalized,
            evidence_checksum,
            _source_crs(evidence.metadata),
            evidence.http_status,
            evidence.content_type,
            evidence.response_headers,
            evidence.latency_ms,
            observed_at,
            raw_payload,
            raw_evidence_locator,
        )
    except Exception as exc:
        _persist_failure(engine, source_id, run_id, exc)
        raise
    return SnapshotReport(
        source=config.source_key,
        adapter_version=config.adapter_version,
        normalization_version=config.normalization_version,
        status="CURRENT",
        expected_count=evidence.count,
        retrieved_count=len(normalized.features),
        schema_fingerprint=normalized.schema_fingerprint,
        payload_checksum=evidence_checksum,
        geometries=normalized.geometry_counts,
        duration_ms=round((monotonic() - started) * 1000),
        import_run_id=run_id,
        snapshot_id=snapshot_id,
        unchanged=unchanged,
    )


def _persist_success(
    engine: Engine,
    source_id: int,
    run_id: int,
    config: UpiSourceConfig,
    normalized: NormalizedSnapshot,
    evidence_checksum: str,
    source_crs: dict[str, Any],
    http_status: int,
    content_type: str | None,
    response_headers: dict[str, str],
    latency_ms: int,
    observed_at: datetime,
    raw_payload: dict[str, Any] | None,
    raw_evidence_locator: str | None,
) -> tuple[int, bool]:
    with engine.begin() as connection:
        previous = connection.execute(
            text(
                """
                SELECT id, payload_checksum
                FROM upi.source_snapshots
                WHERE source_id = :source_id
                ORDER BY id DESC
                LIMIT 1
                """
            ),
            {"source_id": source_id},
        ).mappings().first()
        unchanged = bool(
            previous is not None and previous["payload_checksum"] == evidence_checksum
        )
        snapshot_id = int(
            connection.scalar(
                text(
                    """
                    INSERT INTO upi.source_snapshots
                        (source_id, import_run_id, previous_snapshot_id, retrieved_at,
                         adapter_version, normalization_version, request_url,
                         config_version,
                         request_parameters, http_status, content_type, response_headers,
                         source_crs,
                         record_count, schema_fingerprint, payload_checksum, snapshot_status,
                         raw_payload, raw_evidence_locator)
                    VALUES
                        (:source_id, :run_id, :previous_snapshot_id, :retrieved_at,
                         :adapter_version, :normalization_version, :request_url,
                         :config_version,
                         CAST(:request_parameters AS jsonb), :http_status, :content_type,
                         CAST(:response_headers AS jsonb), CAST(:source_crs AS jsonb),
                         :record_count, :schema_fingerprint,
                         :payload_checksum, :snapshot_status, CAST(:raw_payload AS jsonb),
                         :raw_evidence_locator)
                    RETURNING id
                    """
                ),
                {
                    "source_id": source_id,
                    "run_id": run_id,
                    "previous_snapshot_id": previous["id"] if previous else None,
                    "retrieved_at": observed_at,
                    "adapter_version": config.adapter_version,
                    "normalization_version": config.normalization_version,
                    "config_version": config.config_version,
                    "request_url": config.query_url,
                    "request_parameters": json.dumps(
                        {
                            "where": "1=1",
                            "outFields": list(config.out_fields),
                            "outSR": 4326,
                            "pagination": "returnIdsOnly+objectIds",
                            "pageSize": config.page_size,
                        }
                    ),
                    "http_status": http_status,
                    "content_type": content_type,
                    "response_headers": json.dumps(response_headers),
                    "source_crs": json.dumps(source_crs),
                    "record_count": len(normalized.features),
                    "schema_fingerprint": normalized.schema_fingerprint,
                    "payload_checksum": evidence_checksum,
                    "snapshot_status": "UNCHANGED" if unchanged else "COMPLETE",
                    "raw_payload": json.dumps(raw_payload) if raw_payload is not None else None,
                    "raw_evidence_locator": raw_evidence_locator,
                },
            )
        )
        for feature in normalized.features:
            connection.execute(
                text(
                    """
                    INSERT INTO upi.normalized_features
                        (source_id, snapshot_id, source_object_id, source_version, observed_at,
                         effective_from, effective_to, status, normalization_version,
                         properties, raw_locator, payload_hash, geom)
                    VALUES
                        (:source_id, :snapshot_id, :source_object_id, :source_version,
                         :observed_at, :effective_from, :effective_to, :status,
                         :normalization_version, CAST(:properties AS jsonb), :raw_locator,
                         :payload_hash,
                         ST_SetSRID(ST_GeomFromGeoJSON(:geometry), 4326))
                    """
                ),
                {
                    "source_id": source_id,
                    "snapshot_id": snapshot_id,
                    "source_object_id": feature.source_object_id,
                    "source_version": feature.source_version,
                    "observed_at": feature.observed_at,
                    "effective_from": feature.effective_from,
                    "effective_to": feature.effective_to,
                    "status": feature.status,
                    "normalization_version": config.normalization_version,
                    "properties": json.dumps(feature.properties, ensure_ascii=False),
                    "raw_locator": feature.raw_locator,
                    "payload_hash": feature.payload_hash,
                    "geometry": json.dumps(feature.geometry),
                },
            )
        connection.execute(
            text(
                """
                UPDATE meta.import_runs
                SET status = 'success', finished_at = now(),
                    processed_count = :count, inserted_count = :count,
                    updated_count = 0, skipped_count = 0, error_count = 0,
                    checksum = :checksum,
                    details = details || CAST(:details AS jsonb), updated_at = now()
                WHERE id = :run_id AND status = 'running'
                """
            ),
            {
                "run_id": run_id,
                "count": len(normalized.features),
                "checksum": evidence_checksum,
                "details": json.dumps(
                    {
                        "snapshot_id": snapshot_id,
                        "schema_fingerprint": normalized.schema_fingerprint,
                        "normalized_checksum": normalized.payload_checksum,
                        "unchanged": unchanged,
                    }
                ),
            },
        )
        connection.execute(
            text(
                """
                INSERT INTO upi.source_health
                    (source_id, import_run_id, checked_at, status, http_status, latency_ms,
                     schema_fingerprint, record_count, details)
                VALUES
                    (:source_id, :run_id, :checked_at, 'CURRENT', :http_status, :latency_ms,
                     :schema_fingerprint, :record_count, CAST(:details AS jsonb))
                """
            ),
            {
                "source_id": source_id,
                "run_id": run_id,
                "checked_at": observed_at,
                "http_status": http_status,
                "latency_ms": latency_ms,
                "schema_fingerprint": normalized.schema_fingerprint,
                "record_count": len(normalized.features),
                "details": json.dumps({"snapshot_id": snapshot_id, "unchanged": unchanged}),
            },
        )
    return snapshot_id, unchanged


def _persist_failure(engine: Engine, source_id: int, run_id: int, exc: Exception) -> None:
    status = exc.health_status if isinstance(exc, SourceError) else "IMPORT_FAILED"
    error_code = exc.code if isinstance(exc, SourceError) else type(exc).__name__
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                UPDATE meta.import_runs
                SET status = 'failed', finished_at = now(), error_count = 1,
                    details = details || CAST(:details AS jsonb), updated_at = now()
                WHERE id = :run_id
                """
            ),
            {"run_id": run_id, "details": json.dumps({"error_code": error_code})},
        )
        connection.execute(
            text(
                """
                INSERT INTO upi.source_health
                    (source_id, import_run_id, checked_at, status, http_status,
                     error_code, error_message)
                VALUES (:source_id, :run_id, now(), :status, :http_status,
                        :error_code, :error_message)
                """
            ),
            {
                "source_id": source_id,
                "run_id": run_id,
                "status": status,
                "http_status": getattr(exc, "http_status", None),
                "error_code": error_code,
                "error_message": str(exc)[:4000],
            },
        )


def _source_crs(metadata: dict[str, Any]) -> dict[str, Any]:
    extent = metadata.get("extent")
    if not isinstance(extent, dict):
        return {}
    spatial_reference = extent.get("spatialReference")
    return dict(spatial_reference) if isinstance(spatial_reference, dict) else {}


def report_json(report: ProbeReport | SnapshotReport) -> str:
    return json.dumps(asdict(report), ensure_ascii=False, sort_keys=True)
