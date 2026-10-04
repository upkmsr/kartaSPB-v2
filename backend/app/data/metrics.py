from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import Engine, text


@dataclass(frozen=True)
class CurrentMetricRun:
    run_id: UUID
    metric_key: str
    definition_version: str
    calculation_version: str
    grid_version: str
    cell_count: int
    min_value: float
    max_value: float
    mean_value: float
    values_checksum: str
    created_at: datetime


class MetricQueryService:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def current(self, metric_key: str, grid_version: str) -> CurrentMetricRun | None:
        with self._engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT r.run_id, r.metric_key, r.definition_version, "
                    "r.calculation_version, r.grid_version, r.cell_count, "
                    "r.min_value, r.max_value, r.mean_value, r.values_checksum, r.created_at "
                    "FROM analytics.metric_current_runs AS c "
                    "JOIN analytics.metric_runs AS r ON r.run_id = c.run_id "
                    "WHERE c.metric_key = :metric_key AND c.grid_version = :grid_version"
                ),
                {"metric_key": metric_key, "grid_version": grid_version},
            ).mappings().one_or_none()
        return CurrentMetricRun(**row) if row is not None else None
