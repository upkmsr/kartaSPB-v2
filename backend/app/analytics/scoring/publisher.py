import hashlib
import json
import math
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import Engine, bindparam, text

from app.analytics.scoring.contracts import NormalizationDefinition


class NormalizationPublishError(RuntimeError):
    """Raised before commit when normalized publication violates an invariant."""


class NormalizationPublishStatus(StrEnum):
    CREATED = "created"
    UNCHANGED = "unchanged"


@dataclass(frozen=True)
class NormalizationPublishResult:
    status: NormalizationPublishStatus
    score_run_id: UUID
    metric_run_id: UUID
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
        payload["score_run_id"] = str(self.score_run_id)
        payload["metric_run_id"] = str(self.metric_run_id)
        return payload


def normalized_values_checksum(values: Iterable[tuple[str, float]]) -> str:
    digest = hashlib.sha256()
    for cell_id, score in sorted(values):
        digest.update(f"{cell_id}\t{float(score).hex()}\n".encode())
    return digest.hexdigest()


def score_run_signature(
    metric_key: str,
    grid_version: str,
    metric_run_id: UUID,
    normalization_version: str,
    normalization_checksum: str,
) -> str:
    canonical = json.dumps(
        {
            "grid_version": grid_version,
            "metric_key": metric_key,
            "metric_run_id": str(metric_run_id),
            "normalization_checksum": normalization_checksum,
            "normalization_version": normalization_version,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def publish_normalized_metric(
    engine: Engine,
    definition: NormalizationDefinition,
    grid_version: str,
    *,
    normalization_checksum: str | None = None,
) -> NormalizationPublishResult:
    if not grid_version.strip():
        raise NormalizationPublishError("grid_version must not be blank")
    expected_checksum = definition.checksum()
    if normalization_checksum is not None and normalization_checksum != expected_checksum:
        raise NormalizationPublishError(
            "normalization checksum does not match the definition snapshot"
        )

    with engine.begin() as connection:
        connection.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
            {"lock_key": f"normalized:{definition.metric_key}:{grid_version}"},
        )
        raw_run = connection.execute(
            text(
                "SELECT r.run_id, r.cell_count FROM analytics.metric_current_runs AS c "
                "JOIN analytics.metric_runs AS r ON r.run_id = c.run_id "
                "WHERE c.metric_key = :metric_key AND c.grid_version = :grid_version"
            ),
            {"metric_key": definition.metric_key, "grid_version": grid_version},
        ).mappings().one_or_none()
        if raw_run is None:
            raise NormalizationPublishError("current raw metric run not found")
        grid_count = connection.scalar(
            text(
                "SELECT count(*) FROM analytics.analysis_cells "
                "WHERE grid_version = :grid_version"
            ),
            {"grid_version": grid_version},
        )
        if not grid_count or raw_run["cell_count"] != grid_count:
            raise NormalizationPublishError("current raw metric run is incomplete for the grid")
        raw_values = [
            (str(row.cell_id), float(row.raw_value))
            for row in connection.execute(
                text(
                    "SELECT v.cell_id, v.raw_value FROM analytics.cell_metric_values AS v "
                    "WHERE v.run_id = :run_id ORDER BY v.cell_id"
                ),
                {"run_id": raw_run["run_id"]},
            )
        ]
        if len(raw_values) != grid_count:
            raise NormalizationPublishError("raw metric values are incomplete for the grid")

        normalized: list[tuple[str, float]] = []
        for cell_id, raw_value in raw_values:
            score = float(definition.normalize(float(raw_value)))
            if not math.isfinite(score) or not 0 <= score <= 100:
                raise NormalizationPublishError(
                    f"normalization produced an invalid score for cell: {cell_id}"
                )
            normalized.append((cell_id, score))
        values_checksum = normalized_values_checksum(normalized)
        signature = score_run_signature(
            definition.metric_key,
            grid_version,
            raw_run["run_id"],
            definition.normalization_version,
            expected_checksum,
        )
        existing = connection.execute(
            text(
                "SELECT score_run_id, metric_run_id, cell_count, score_min, score_max, "
                "score_mean, values_checksum FROM analytics.metric_score_runs "
                "WHERE run_signature = :run_signature"
            ),
            {"run_signature": signature},
        ).mappings().one_or_none()
        if existing is not None:
            if existing["values_checksum"] != values_checksum:
                raise NormalizationPublishError(
                    "an immutable score run signature already exists with different values"
                )
            connection.execute(
                text(
                    "INSERT INTO analytics.metric_score_current_runs "
                    "(metric_key, grid_version, score_run_id) "
                    "VALUES (:metric_key, :grid_version, :score_run_id) "
                    "ON CONFLICT (metric_key, grid_version) DO UPDATE "
                    "SET score_run_id = EXCLUDED.score_run_id, updated_at = now()"
                ),
                {
                    "metric_key": definition.metric_key,
                    "grid_version": grid_version,
                    "score_run_id": existing["score_run_id"],
                },
            )
            return NormalizationPublishResult(
                status=NormalizationPublishStatus.UNCHANGED,
                score_run_id=existing["score_run_id"],
                metric_run_id=existing["metric_run_id"],
                metric_key=definition.metric_key,
                grid_version=grid_version,
                cell_count=existing["cell_count"],
                minimum=existing["score_min"],
                maximum=existing["score_max"],
                mean=existing["score_mean"],
                values_checksum=existing["values_checksum"],
            )

        scores = [score for _, score in normalized]
        score_run_id = uuid4()
        minimum = min(scores)
        maximum = max(scores)
        mean = math.fsum(scores) / len(scores)
        connection.execute(
            text(
                "INSERT INTO analytics.metric_score_runs "
                "(score_run_id, metric_key, grid_version, metric_run_id, "
                "normalization_version, normalization_checksum, normalization_snapshot, "
                "run_signature, cell_count, score_min, score_max, score_mean, values_checksum) "
                "VALUES (:score_run_id, :metric_key, :grid_version, :metric_run_id, "
                ":normalization_version, :normalization_checksum, "
                "CAST(:normalization_snapshot AS jsonb), :run_signature, :cell_count, "
                ":score_min, :score_max, :score_mean, :values_checksum)"
            ),
            {
                "score_run_id": score_run_id,
                "metric_key": definition.metric_key,
                "grid_version": grid_version,
                "metric_run_id": raw_run["run_id"],
                "normalization_version": definition.normalization_version,
                "normalization_checksum": expected_checksum,
                "normalization_snapshot": definition.canonical_json(),
                "run_signature": signature,
                "cell_count": len(normalized),
                "score_min": minimum,
                "score_max": maximum,
                "score_mean": mean,
                "values_checksum": values_checksum,
            },
        )
        insert_scores = text(
            "INSERT INTO analytics.cell_metric_scores (score_run_id, cell_id, score) "
            "VALUES (:score_run_id, :cell_id, :score)"
        ).bindparams(bindparam("score_run_id"), bindparam("cell_id"), bindparam("score"))
        for offset in range(0, len(normalized), 5000):
            connection.execute(
                insert_scores,
                [
                    {"score_run_id": score_run_id, "cell_id": cell_id, "score": score}
                    for cell_id, score in normalized[offset : offset + 5000]
                ],
            )
        connection.execute(
            text(
                "INSERT INTO analytics.metric_score_current_runs "
                "(metric_key, grid_version, score_run_id) "
                "VALUES (:metric_key, :grid_version, :score_run_id) "
                "ON CONFLICT (metric_key, grid_version) DO UPDATE "
                "SET score_run_id = EXCLUDED.score_run_id, updated_at = now()"
            ),
            {
                "metric_key": definition.metric_key,
                "grid_version": grid_version,
                "score_run_id": score_run_id,
            },
        )
        return NormalizationPublishResult(
            status=NormalizationPublishStatus.CREATED,
            score_run_id=score_run_id,
            metric_run_id=raw_run["run_id"],
            metric_key=definition.metric_key,
            grid_version=grid_version,
            cell_count=len(normalized),
            minimum=minimum,
            maximum=maximum,
            mean=mean,
            values_checksum=values_checksum,
        )
