import json
import os
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

from app.upi.adapters import TorisConstructionAdapter
from app.upi.arcgis import (
    ArcGisClient,
    CompletenessError,
    HttpResponse,
    SchemaChangedError,
    SourceResponseError,
    SourceUnavailableError,
)
from app.upi.config import load_source_config
from app.upi.normalization import sha256_json
from app.upi.service import bootstrap_source, snapshot_fixture, snapshot_source

FIXTURE = Path("tests/fixtures/upi/toris_construction.json")


def database_url() -> str:
    value = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    if value is None:
        pytest.skip("Set TEST_DATABASE_URL to run UPI database integration tests")
    return value


def isolated_config() -> object:
    suffix = uuid4().hex
    return replace(
        load_source_config(),
        source_key=f"toris-construction-test-{suffix}",
        dataset_source_name=f"upi-toris-construction-test-{suffix}",
    )


@pytest.mark.integration
def test_fixture_snapshot_is_atomic_append_only_and_detects_unchanged_rerun() -> None:
    engine = create_engine(database_url())
    config = isolated_config()
    first = snapshot_fixture(engine, config, FIXTURE)  # type: ignore[arg-type]
    second = snapshot_fixture(engine, config, FIXTURE)  # type: ignore[arg-type]

    assert first.unchanged is False
    assert second.unchanged is True
    assert first.snapshot_id != second.snapshot_id
    assert first.payload_checksum == second.payload_checksum
    with engine.connect() as connection:
        row = connection.execute(
            text(
                """
                SELECT count(DISTINCT s.id) snapshot_count,
                       count(f.id) feature_count,
                       count(DISTINCT r.id) FILTER (WHERE r.status = 'success') success_runs,
                       count(DISTINCT h.id) FILTER (WHERE h.status = 'CURRENT') current_health,
                       min(ST_SRID(f.geom)) min_srid,
                       bool_and(ST_IsValid(f.geom)) all_valid,
                       count(*) FILTER (
                           WHERE f.properties ? 'UNAPPROVED_RAW_FIELD'
                       ) leaked_raw_fields,
                       min(s.source_crs->>'wkid') source_wkid,
                       min(s.raw_payload::text) raw_payload_text,
                       min(s.payload_checksum) first_checksum
                FROM upi.source_snapshots s
                JOIN meta.import_runs r ON r.id = s.import_run_id
                JOIN upi.normalized_features f ON f.snapshot_id = s.id
                JOIN upi.source_health h ON h.import_run_id = r.id
                WHERE s.id IN (:first_id, :second_id)
                """
            ),
            {"first_id": first.snapshot_id, "second_id": second.snapshot_id},
        ).one()
    assert row.snapshot_count == 2
    assert row.feature_count == 8
    assert row.success_runs == 2
    assert row.current_health == 2
    assert row.min_srid == 4326
    assert row.all_valid is True
    assert row.leaked_raw_fields == 0
    assert row.source_wkid == "102100"
    assert row.raw_payload_text is not None
    assert row.first_checksum == sha256_json(json.loads(row.raw_payload_text))

    with pytest.raises(DBAPIError, match="append-only"), engine.begin() as connection:
        connection.execute(
            text("UPDATE upi.source_snapshots SET record_count = 0 WHERE id = :id"),
            {"id": first.snapshot_id},
        )


@pytest.mark.integration
def test_bootstrap_is_idempotent_and_reuses_global_dataset_source() -> None:
    engine = create_engine(database_url())
    config = isolated_config()

    first_id = bootstrap_source(engine, config)  # type: ignore[arg-type]
    second_id = bootstrap_source(engine, config)  # type: ignore[arg-type]

    assert first_id == second_id
    with engine.connect() as connection:
        row = connection.execute(
            text(
                """
                SELECT count(*) profile_count,
                       count(DISTINCT p.source_id) source_count
                FROM upi.source_profiles p
                WHERE p.source_key = :source_key
                """
            ),
            {"source_key": config.source_key},  # type: ignore[attr-defined]
        ).one()
    assert row.profile_count == 1
    assert row.source_count == 1


@pytest.mark.integration
@pytest.mark.parametrize(
    ("failure", "expected_health"),
    [
        (SourceUnavailableError("deterministic timeout"), "SOURCE_UNAVAILABLE"),
        (SourceResponseError("deterministic invalid JSON"), "IMPORT_FAILED"),
        (SchemaChangedError("deterministic schema drift"), "SCHEMA_CHANGED"),
        (CompletenessError("deterministic second page failure"), "PARTIALLY_UPDATED"),
    ],
)
def test_failed_snapshot_persists_failure_state_but_no_partial_snapshot(
    failure: Exception, expected_health: str
) -> None:
    engine = create_engine(database_url())
    config = replace(isolated_config(), max_retries=0)  # type: ignore[arg-type]

    def unavailable(url: str, params: dict[str, str], timeout: int) -> HttpResponse:
        raise failure

    with pytest.raises(type(failure)):
        snapshot_source(
            engine,
            TorisConstructionAdapter(config, ArcGisClient(config, unavailable)),
        )

    with engine.connect() as connection:
        row = connection.execute(
            text(
                """
                SELECT
                    count(s.id) snapshot_count,
                    count(r.id) FILTER (WHERE r.status = 'failed') failed_runs,
                    count(h.id) FILTER (WHERE h.status = :expected_health) expected_health
                FROM meta.dataset_sources ds
                LEFT JOIN meta.import_runs r ON r.source_id = ds.id
                LEFT JOIN upi.source_snapshots s ON s.import_run_id = r.id
                LEFT JOIN upi.source_health h ON h.import_run_id = r.id
                WHERE ds.name = :name
                """
            ),
            {"name": config.dataset_source_name, "expected_health": expected_health},
        ).one()
    assert row.snapshot_count == 0
    assert row.failed_runs == 1
    assert row.expected_health == 1


def test_live_raw_payload_retention_is_blocked_before_source_access() -> None:
    engine = create_engine(database_url())
    config = isolated_config()

    def unused(url: str, params: dict[str, str], timeout: int) -> HttpResponse:
        raise AssertionError("source must not be accessed")

    with pytest.raises(PermissionError, match="not authorized"):
        snapshot_source(
            engine,
            TorisConstructionAdapter(
                config,  # type: ignore[arg-type]
                ArcGisClient(config, unused),  # type: ignore[arg-type]
            ),
            raw_payload={"live": True},
            raw_evidence_locator="https://example.test/live.json",
        )
