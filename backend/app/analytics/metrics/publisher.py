import hashlib
import json
import math
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import Engine, bindparam, text

from app.analytics.metrics.contracts import MetricDefinition


class MetricPublishError(RuntimeError):
    """Raised before commit when a metric publication violates an invariant."""


class MetricPublishStatus(StrEnum):
    CREATED = "created"
    UNCHANGED = "unchanged"


@dataclass(frozen=True)
class MetricPublishResult:
    status: MetricPublishStatus
    run_id: UUID
    metric_key: str
    grid_version: str
    cell_count: int
    minimum: float
    maximum: float
    mean: float
    values_checksum: str

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["status"] = self.status.value
        payload["run_id"] = str(self.run_id)
        return payload


def values_checksum(values: Iterable[tuple[str, float]]) -> str:
    digest = hashlib.sha256()
    for cell_id, raw_value in sorted(values):
        digest.update(f"{cell_id}\t{float(raw_value).hex()}\n".encode())
    return digest.hexdigest()


def _run_signature(
    definition: MetricDefinition, grid_version: str, input_fingerprint: str
) -> str:
    payload = {
        "calculation_version": definition.calculation_version,
        "definition_checksum": definition.checksum(),
        "definition_version": definition.definition_version,
        "grid_version": grid_version,
        "input_fingerprint": input_fingerprint,
        "metric_key": definition.key,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _validate_sha256(value: str, label: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise MetricPublishError(f"{label} must be a lowercase SHA-256 digest")


def publish_metric(
    engine: Engine,
    definition: MetricDefinition,
    grid_version: str,
    input_fingerprint: str,
    values: Iterable[tuple[str, float]],
    *,
    definition_checksum: str | None = None,
) -> MetricPublishResult:
    if not grid_version.strip():
        raise MetricPublishError("grid_version must not be blank")
    _validate_sha256(input_fingerprint, "input_fingerprint")
    expected_definition_checksum = definition.checksum()
    if definition_checksum is not None and definition_checksum != expected_definition_checksum:
        raise MetricPublishError("definition checksum does not match the definition snapshot")

    materialized: dict[str, float] = {}
    for cell_id, raw_value in values:
        if cell_id in materialized:
            raise MetricPublishError(f"duplicate cell value: {cell_id}")
        value = float(raw_value)
        if not math.isfinite(value):
            raise MetricPublishError(f"non-finite value for cell: {cell_id}")
        materialized[cell_id] = value

    ordered_values = sorted(materialized.items())
    checksum = values_checksum(ordered_values)
    signature = _run_signature(definition, grid_version, input_fingerprint)

    with engine.begin() as connection:
        connection.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
            {"lock_key": f"metric:{definition.key}:{grid_version}"},
        )
        expected_ids = tuple(
            connection.scalars(
                text(
                    "SELECT cell_id FROM analytics.analysis_cells "
                    "WHERE grid_version = :grid_version ORDER BY cell_id"
                ),
                {"grid_version": grid_version},
            )
        )
        if not expected_ids:
            raise MetricPublishError(f"grid has no cells: {grid_version}")
        actual_ids = tuple(cell_id for cell_id, _ in ordered_values)
        expected_set = set(expected_ids)
        actual_set = set(actual_ids)
        if expected_set != actual_set:
            missing = len(expected_set - actual_set)
            extra = len(actual_set - expected_set)
            raise MetricPublishError(
                f"metric values do not exactly cover the grid: missing={missing}, extra={extra}"
            )

        existing = connection.execute(
            text(
                "SELECT run_id, cell_count, min_value, max_value, mean_value, values_checksum "
                "FROM analytics.metric_runs WHERE run_signature = :run_signature"
            ),
            {"run_signature": signature},
        ).mappings().one_or_none()
        if existing is not None:
            if existing["values_checksum"] != checksum:
                raise MetricPublishError(
                    "an immutable run signature already exists with different values"
                )
            connection.execute(
                text(
                    "INSERT INTO analytics.metric_current_runs "
                    "(metric_key, grid_version, run_id) "
                    "VALUES (:metric_key, :grid_version, :run_id) "
                    "ON CONFLICT (metric_key, grid_version) DO UPDATE "
                    "SET run_id = EXCLUDED.run_id, updated_at = now()"
                ),
                {
                    "metric_key": definition.key,
                    "grid_version": grid_version,
                    "run_id": existing["run_id"],
                },
            )
            return MetricPublishResult(
                status=MetricPublishStatus.UNCHANGED,
                run_id=existing["run_id"],
                metric_key=definition.key,
                grid_version=grid_version,
                cell_count=existing["cell_count"],
                minimum=existing["min_value"],
                maximum=existing["max_value"],
                mean=existing["mean_value"],
                values_checksum=existing["values_checksum"],
            )

        raw_values = [value for _, value in ordered_values]
        run_id = uuid4()
        minimum = min(raw_values)
        maximum = max(raw_values)
        mean = math.fsum(raw_values) / len(raw_values)
        connection.execute(
            text(
                "INSERT INTO analytics.metric_runs "
                "(run_id, metric_key, definition_version, calculation_version, grid_version, "
                "definition_checksum, input_fingerprint, definition_snapshot, run_signature, "
                "cell_count, min_value, max_value, mean_value, values_checksum) "
                "VALUES (:run_id, :metric_key, :definition_version, :calculation_version, "
                ":grid_version, :definition_checksum, :input_fingerprint, "
                "CAST(:definition_snapshot AS jsonb), :run_signature, :cell_count, "
                ":min_value, :max_value, :mean_value, :values_checksum)"
            ),
            {
                "run_id": run_id,
                "metric_key": definition.key,
                "definition_version": definition.definition_version,
                "calculation_version": definition.calculation_version,
                "grid_version": grid_version,
                "definition_checksum": expected_definition_checksum,
                "input_fingerprint": input_fingerprint,
                "definition_snapshot": definition.canonical_json(),
                "run_signature": signature,
                "cell_count": len(ordered_values),
                "min_value": minimum,
                "max_value": maximum,
                "mean_value": mean,
                "values_checksum": checksum,
            },
        )
        insert_values = text(
            "INSERT INTO analytics.cell_metric_values (run_id, cell_id, raw_value) "
            "VALUES (:run_id, :cell_id, :raw_value)"
        ).bindparams(bindparam("run_id"), bindparam("cell_id"), bindparam("raw_value"))
        for offset in range(0, len(ordered_values), 5000):
            connection.execute(
                insert_values,
                [
                    {"run_id": run_id, "cell_id": cell_id, "raw_value": raw_value}
                    for cell_id, raw_value in ordered_values[offset : offset + 5000]
                ],
            )
        connection.execute(
            text(
                "INSERT INTO analytics.metric_current_runs "
                "(metric_key, grid_version, run_id) "
                "VALUES (:metric_key, :grid_version, :run_id) "
                "ON CONFLICT (metric_key, grid_version) DO UPDATE "
                "SET run_id = EXCLUDED.run_id, updated_at = now()"
            ),
            {
                "metric_key": definition.key,
                "grid_version": grid_version,
                "run_id": run_id,
            },
        )
        return MetricPublishResult(
            status=MetricPublishStatus.CREATED,
            run_id=run_id,
            metric_key=definition.key,
            grid_version=grid_version,
            cell_count=len(ordered_values),
            minimum=minimum,
            maximum=maximum,
            mean=mean,
            values_checksum=checksum,
        )
