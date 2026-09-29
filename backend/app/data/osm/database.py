import json
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from sqlalchemy import Connection, Engine, text

from app.data.osm.config import SourceConfig


def ensure_source(connection: Connection, source: SourceConfig) -> Mapping[str, Any]:
    row = (
        connection.execute(
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
            RETURNING *
            """
            ),
            {
                "name": source.name,
                "provider": source.provider,
                "source_type": source.source_type,
                "source_url": source.source_url,
                "license": source.license,
                "attribution": source.attribution,
            },
        )
        .mappings()
        .one()
    )
    return dict(row)


def record_download(
    connection: Connection,
    source_id: int,
    *,
    version: str,
    checksum: str,
    local_filename: str,
    source_updated_at: datetime | None,
) -> None:
    connection.execute(
        text(
            """
            UPDATE meta.dataset_sources
            SET version = :version,
                checksum = :checksum,
                local_filename = :local_filename,
                downloaded_at = now(),
                source_updated_at = :source_updated_at,
                updated_at = now()
            WHERE id = :source_id
            """
        ),
        {
            "source_id": source_id,
            "version": version,
            "checksum": checksum,
            "local_filename": local_filename,
            "source_updated_at": source_updated_at,
        },
    )


def start_import_run(
    engine: Engine,
    *,
    source_id: int,
    source_version: str | None,
    checksum: str | None,
    profile: str | None = None,
    authoritative_snapshot: bool = False,
    details: dict[str, Any],
) -> int:
    with engine.begin() as connection:
        return int(
            connection.scalar(
                text(
                    """
                    INSERT INTO meta.import_runs
                        (source_id, status, started_at, source_version, checksum, profile,
                         authoritative_snapshot, details)
                    VALUES
                        (:source_id, 'running', now(), :source_version, :checksum, :profile,
                         :authoritative_snapshot,
                         CAST(:details AS jsonb))
                    RETURNING id
                    """
                ),
                {
                    "source_id": source_id,
                    "source_version": source_version,
                    "checksum": checksum,
                    "profile": profile,
                    "authoritative_snapshot": authoritative_snapshot,
                    "details": json.dumps(details),
                },
            )
        )


def stage_import_run(
    engine: Engine,
    run_id: int,
    *,
    processed_count: int,
    inserted_count: int,
    updated_count: int,
    skipped_count: int,
    details: dict[str, Any],
) -> None:
    """Publish raw staging completion without authorizing lifecycle finalization."""
    with engine.begin() as connection:
        result = connection.execute(
            text(
                """
                UPDATE meta.import_runs
                SET status = 'staged',
                    processed_count = :processed_count,
                    inserted_count = :inserted_count,
                    updated_count = :updated_count,
                    skipped_count = :skipped_count,
                    details = details || CAST(:details AS jsonb),
                    updated_at = now()
                WHERE id = :run_id AND status = 'running'
                """
            ),
            {
                "run_id": run_id,
                "processed_count": processed_count,
                "inserted_count": inserted_count,
                "updated_count": updated_count,
                "skipped_count": skipped_count,
                "details": json.dumps(details),
            },
        )
        if result.rowcount != 1:
            raise RuntimeError(f"Import run {run_id} is not in running state")


def finish_import_run(
    engine: Engine,
    run_id: int,
    *,
    status: str,
    processed_count: int | None = None,
    inserted_count: int | None = None,
    updated_count: int | None = None,
    skipped_count: int = 0,
    error_count: int = 0,
    details: dict[str, Any] | None = None,
) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                UPDATE meta.import_runs
                SET status = :status,
                    finished_at = now(),
                    processed_count = COALESCE(:processed_count, processed_count),
                    inserted_count = COALESCE(:inserted_count, inserted_count),
                    updated_count = COALESCE(:updated_count, updated_count),
                    skipped_count = :skipped_count,
                    error_count = :error_count,
                    details = details || CAST(:details AS jsonb),
                    updated_at = now()
                WHERE id = :run_id
                """
            ),
            {
                "run_id": run_id,
                "status": status,
                "processed_count": processed_count,
                "inserted_count": inserted_count,
                "updated_count": updated_count,
                "skipped_count": skipped_count,
                "error_count": error_count,
                "details": json.dumps(details or {}),
            },
        )
