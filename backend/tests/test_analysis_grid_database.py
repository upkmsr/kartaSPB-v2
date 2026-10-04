import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

from app.analytics.grid import GridBootstrapError, bootstrap_grid


def database_url() -> str:
    value = os.getenv("TEST_DATABASE_URL")
    if value is None:
        pytest.skip("Set TEST_DATABASE_URL to run analysis-grid integration tests")
    return value


@pytest.mark.integration
def test_analysis_grid_bootstrap_is_deterministic_and_fail_closed() -> None:
    engine = create_engine(database_url())
    district_ids = [uuid4() for _ in range(18)]
    object_ids = [uuid4() for _ in range(18)]
    with engine.connect() as connection:
        if connection.scalar(text("SELECT count(*) FROM domain.districts")):
            pytest.skip("analysis-grid fixture requires an empty district registry")
        if connection.scalar(text("SELECT count(*) FROM analytics.analysis_cells")):
            pytest.skip("analysis-grid fixture requires an empty grid table")

    try:
        with engine.begin() as connection:
            for index, (district_id, object_id) in enumerate(
                zip(district_ids, object_ids, strict=True)
            ):
                min_lon = 29.8 + index * 0.02
                connection.execute(
                    text(
                        """
                        INSERT INTO catalog.objects (
                            id, object_kind, lifecycle_status, name, geom,
                            properties, property_sources, revision
                        ) VALUES (
                            :object_id, 'boundary', 'active', :name,
                            ST_MakeEnvelope(:min_lon, 59.9, :max_lon, 59.91, 4326),
                            '{}', '{}', 1
                        )
                        """
                    ),
                    {
                        "object_id": object_id,
                        "name": f"F6 fixture district {index + 1}",
                        "min_lon": min_lon,
                        "max_lon": min_lon + 0.02,
                    },
                )
                connection.execute(
                    text(
                        """
                        INSERT INTO domain.districts (
                            id, canonical_object_id, name, slug, display_order, enabled
                        ) VALUES (:district_id, :object_id, :name, :slug, :display_order, true)
                        """
                    ),
                    {
                        "district_id": district_id,
                        "object_id": object_id,
                        "name": f"F6 fixture district {index + 1}",
                        "slug": f"f6-fixture-{index + 1}",
                        "display_order": index + 1,
                    },
                )

        first = bootstrap_grid(engine)
        second = bootstrap_grid(engine)

        assert first.cell_count > 0
        assert first.district_count == 18
        assert all(count > 0 for count in first.district_cell_counts.values())
        assert first.invalid_geometry_count == 0
        assert first.missing_district_count == 0
        assert first.duplicate_coordinate_count == 0
        assert first.created_count == first.cell_count
        assert first.unchanged_count == 0
        assert second.created_count == 0
        assert second.unchanged_count == first.cell_count
        assert second.checksum_sha256 == first.checksum_sha256

        with engine.connect() as connection:
            assert connection.scalar(
                text(
                    """
                    SELECT count(*) FROM analytics.analysis_cells
                    WHERE ST_GeometryType(geom) <> 'ST_Polygon'
                       OR ST_SRID(geom) <> 4326
                       OR ST_SRID(geom_metric) <> 32636
                       OR abs(ST_Area(geom_metric) - 40000) > 0.01
                       OR NOT ST_Covers(geom_metric, center_metric)
                    """
                )
            ) == 0

        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    UPDATE analytics.analysis_cells
                    SET grid_i = grid_i + 1000000
                    WHERE cell_id = (
                        SELECT cell_id FROM analytics.analysis_cells ORDER BY cell_id LIMIT 1
                    )
                    """
                )
            )
        with pytest.raises(GridBootstrapError, match="refusing automatic repair"):
            bootstrap_grid(engine)
    finally:
        with engine.begin() as connection:
            connection.execute(text("DELETE FROM analytics.analysis_cells"))
            connection.execute(
                text("DELETE FROM domain.districts WHERE id = ANY(:district_ids)"),
                {"district_ids": district_ids},
            )
            connection.execute(
                text("DELETE FROM catalog.objects WHERE id = ANY(:object_ids)"),
                {"object_ids": object_ids},
            )
        engine.dispose()
