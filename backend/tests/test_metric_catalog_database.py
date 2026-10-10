import os
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Connection, create_engine, text

from app.analytics.metrics.catalog import (
    CatalogCountWithinRadiusProvider,
    CatalogNearestDistanceProvider,
    CatalogParkAccessibilityProvider,
    CatalogSmoothInfluenceProvider,
    CatalogWaterAccessibilityProvider,
    MetricProviderError,
    bounded_accessibility,
    proximity_influence,
    size_quality,
    smooth_influence,
)
from app.analytics.metrics.contracts import MetricDefinition
from app.analytics.metrics.providers import MetricProviderContext


def database_url() -> str:
    value = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    if value is None:
        pytest.skip("Set TEST_DATABASE_URL to run catalog metric integration tests")
    return value


def metric_definition(
    key: str, provider_key: str, category_key: str, *, radius_m: float | None = None
) -> MetricDefinition:
    provider_config: dict[str, object] = {"category_key": category_key}
    if radius_m is not None:
        provider_config["radius_m"] = radius_m
    return MetricDefinition.model_validate(
        {
            "key": key,
            "definition_version": "1",
            "label": "F8 fixture",
            "description": "Catalog spatial provider integration fixture",
            "group": "test",
            "unit": "count" if radius_m is not None else "m",
            "value_semantics": "count" if radius_m is not None else "distance_m",
            "preferred_direction": "higher_better" if radius_m is not None else "lower_better",
            "provider_key": provider_key,
            "calculation_version": "catalog-spatial-v1",
            "provider_config": provider_config,
        }
    )


def insert_object(connection: Connection, object_id: UUID, name: str, metric_wkt: str) -> None:
    connection.execute(
        text(
            "INSERT INTO catalog.objects "
            "(id, object_kind, lifecycle_status, name, geom, properties, "
            "property_sources, revision) VALUES "
            "(:id, 'feature', 'active', :name, "
            "ST_Transform(ST_GeomFromText(:wkt, 32636), 4326), '{}', '{}', 1)"
        ),
        {"id": object_id, "name": name, "wkt": metric_wkt},
    )


def smooth_definition(key: str, category_key: str, radius_m: float) -> MetricDefinition:
    return MetricDefinition.model_validate(
        {
            "key": key,
            "definition_version": "1",
            "label": "Smooth fixture",
            "description": "Compact quartic provider fixture",
            "group": "test",
            "unit": "index",
            "value_semantics": "index",
            "preferred_direction": "higher_better",
            "provider_key": "catalog.smooth_influence",
            "calculation_version": "compact-quartic-v1",
            "provider_config": {"category_key": category_key, "radius_m": radius_m},
        }
    )


def quality_definition(
    key: str,
    provider_key: str,
    category_key: str,
) -> MetricDefinition:
    provider_config: dict[str, object] = {
        "category_key": category_key,
        "half_distance_m": 900,
        "cutoff_multiplier": 4,
        "extra_bonus_cap": 0.15,
        "extra_saturation": 0.75,
        "area_reference_m2": 50_000,
        "minimum_size_quality": 0.2,
    }
    if provider_key == "catalog.water_accessibility":
        provider_config["line_quality"] = 0.85
        provider_config["extra_bonus_cap"] = 0
    return MetricDefinition.model_validate(
        {
            "key": key,
            "definition_version": "2",
            "label": "Quality-aware accessibility fixture",
            "description": "F11A-R3 geometry quality integration fixture",
            "group": "test",
            "unit": "index",
            "value_semantics": "index",
            "preferred_direction": "higher_better",
            "provider_key": provider_key,
            "calculation_version": "quality-aware-v2",
            "provider_config": provider_config,
        }
    )


def test_smooth_influence_is_monotonic_continuous_and_accumulates() -> None:
    radius = 1000.0
    samples = [smooth_influence(distance, radius) for distance in range(0, 1001, 50)]
    assert samples[0] == 1.0
    assert samples[-1] == 0.0
    assert all(left > right for left, right in zip(samples, samples[1:], strict=False))
    assert smooth_influence(999.0, radius) > 0
    assert smooth_influence(1000.0, radius) == 0
    assert smooth_influence(1001.0, radius) == 0
    assert 3 * smooth_influence(700.0, radius) > smooth_influence(600.0, radius)


def test_primary_accessibility_is_monotonic_and_bounds_density_bonus() -> None:
    near = proximity_influence(100, 700)
    far = proximity_influence(1400, 700)
    assert near > 0.98
    assert far == pytest.approx(0.0625)
    assert proximity_influence(700, 700) == pytest.approx(0.5)
    assert bounded_accessibility(near, near, 0.18, 1) == pytest.approx(near)
    assert near < bounded_accessibility(near, near + 10, 0.18, 1) <= 1
    assert bounded_accessibility(0.5, 100, 0.18, 1) <= 0.59


def test_park_size_quality_has_practically_meaningful_diminishing_returns() -> None:
    small = size_quality(500, 50_000, 0.2)
    medium = size_quality(50_000, 50_000, 0.2)
    large = size_quality(500_000, 50_000, 0.2)
    assert large > medium > small
    assert large - small > 0.5
    assert large < 1
    assert size_quality(5_000_000, 50_000, 0.2) - large < medium - small


@pytest.mark.integration
def test_geometry_quality_models_handle_park_area_and_water_segments() -> None:
    engine = create_engine(database_url())
    suffix = uuid4().hex
    grid_version = f"f11-r3-grid-{suffix}"
    small_category = f"test.small_park_{suffix}"
    large_category = f"test.large_park_{suffix}"
    water_category = f"test.water_{suffix}"
    boundary_id = uuid4()
    district_id = uuid4()
    small_id = uuid4()
    large_id = uuid4()
    water_ids = [uuid4(), uuid4()]
    cell_id = f"{grid_version}:0"
    object_ids = [boundary_id, small_id, large_id, *water_ids]
    try:
        with engine.begin() as connection:
            for category in (small_category, large_category, water_category):
                connection.execute(
                    text(
                        "INSERT INTO catalog.categories (key,label,enabled) "
                        "VALUES (:key,'F11A-R3 fixture',true)"
                    ),
                    {"key": category},
                )
            insert_object(
                connection,
                boundary_id,
                "F11A-R3 district",
                "POLYGON((499900 6649000,501000 6649000,501000 6651000,"
                "499900 6651000,499900 6649000))",
            )
            connection.execute(
                text("UPDATE catalog.objects SET object_kind='boundary' WHERE id=:id"),
                {"id": boundary_id},
            )
            connection.execute(
                text(
                    "INSERT INTO domain.districts "
                    "(id,canonical_object_id,name,slug,display_order,enabled) VALUES "
                    "(:id,:object_id,'F11A-R3 district',:slug,"
                    "(SELECT min(candidate) FROM generate_series(10000,32767) "
                    "candidates(candidate) "
                    "LEFT JOIN domain.districts existing ON existing.display_order=candidate "
                    "WHERE existing.id IS NULL),false)"
                ),
                {"id": district_id, "object_id": boundary_id, "slug": f"f11-r3-{suffix}"},
            )
            connection.execute(
                text(
                    "INSERT INTO analytics.analysis_cells "
                    "(cell_id,grid_version,grid_i,grid_j,cell_size_m,district_id,center,"
                    "center_metric,geom,geom_metric) VALUES "
                    "(:cell,:grid,0,0,50,:district,"
                    "ST_Transform(ST_SetSRID(ST_MakePoint(500000,6650000),32636),4326),"
                    "ST_SetSRID(ST_MakePoint(500000,6650000),32636),"
                    "ST_Transform(ST_MakeEnvelope(499975,6649975,500025,6650025,32636),4326),"
                    "ST_MakeEnvelope(499975,6649975,500025,6650025,32636))"
                ),
                {"cell": cell_id, "grid": grid_version, "district": district_id},
            )
            insert_object(
                connection,
                small_id,
                "Small park",
                "POLYGON((500200 6649950,500300 6649950,500300 6650050,"
                "500200 6650050,500200 6649950))",
            )
            insert_object(
                connection,
                large_id,
                "Large park",
                "POLYGON((500200 6649750,500700 6649750,500700 6650250,"
                "500200 6650250,500200 6649750))",
            )
            for object_id, category in (
                (small_id, small_category),
                (large_id, large_category),
            ):
                connection.execute(
                    text(
                        "INSERT INTO catalog.object_categories "
                        "(object_id,category_key,lifecycle_status) VALUES (:id,:category,'active')"
                    ),
                    {"id": object_id, "category": category},
                )
            for water_id in water_ids:
                insert_object(
                    connection,
                    water_id,
                    "Water segment",
                    "LINESTRING(500200 6649500,500200 6650500)",
                )
            connection.execute(
                text(
                    "INSERT INTO catalog.object_categories "
                    "(object_id,category_key,lifecycle_status) VALUES (:id,:category,'active')"
                ),
                {"id": water_ids[0], "category": water_category},
            )

        small = CatalogParkAccessibilityProvider().calculate(
            MetricProviderContext(
                engine,
                quality_definition("test.park.small", "catalog.park_accessibility", small_category),
                grid_version,
            )
        )
        large = CatalogParkAccessibilityProvider().calculate(
            MetricProviderContext(
                engine,
                quality_definition("test.park.large", "catalog.park_accessibility", large_category),
                grid_version,
            )
        )
        assert large.values[0][1] - small.values[0][1] > 0.5

        water_definition = quality_definition(
            "test.water.segment", "catalog.water_accessibility", water_category
        )
        one_segment = CatalogWaterAccessibilityProvider().calculate(
            MetricProviderContext(engine, water_definition, grid_version)
        )
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO catalog.object_categories "
                    "(object_id,category_key,lifecycle_status) VALUES (:id,:category,'active')"
                ),
                {"id": water_ids[1], "category": water_category},
            )
        two_segments = CatalogWaterAccessibilityProvider().calculate(
            MetricProviderContext(engine, water_definition, grid_version)
        )
        assert two_segments.values[0][1] == pytest.approx(one_segment.values[0][1])
        assert one_segment.diagnostics["spatial_match_count"] == 1
        assert two_segments.diagnostics["spatial_match_count"] == 2
    finally:
        with engine.begin() as connection:
            connection.execute(
                text("DELETE FROM analytics.analysis_cells WHERE grid_version=:grid"),
                {"grid": grid_version},
            )
            connection.execute(
                text("DELETE FROM domain.districts WHERE id=:id"), {"id": district_id}
            )
            connection.execute(
                text("DELETE FROM catalog.object_categories WHERE object_id=ANY(:ids)"),
                {"ids": object_ids},
            )
            connection.execute(
                text("DELETE FROM catalog.objects WHERE id=ANY(:ids)"),
                {"ids": object_ids},
            )
            connection.execute(
                text("DELETE FROM catalog.categories WHERE key=ANY(:keys)"),
                {"keys": [small_category, large_category, water_category]},
            )
        engine.dispose()


@pytest.mark.integration
def test_catalog_providers_collapse_facilities_and_fingerprint_inputs() -> None:
    engine = create_engine(database_url())
    suffix = uuid4().hex
    grid_version = f"f8-grid-{suffix}"
    category_key = f"test.f8_{suffix}"
    boundary_object_id = uuid4()
    district_id = uuid4()
    ordinary_id = uuid4()
    facility_analysis_id = uuid4()
    facility_point_id = uuid4()
    line_id = uuid4()
    facility_id = uuid4()
    object_ids = [
        boundary_object_id,
        ordinary_id,
        facility_analysis_id,
        facility_point_id,
        line_id,
    ]
    cell_ids = [f"{grid_version}:{index}" for index in range(3)]

    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO catalog.categories (key, label, enabled) "
                    "VALUES (:key, 'F8', true)"
                ),
                {"key": category_key},
            )
            insert_object(
                connection,
                boundary_object_id,
                "F8 district",
                "POLYGON((499900 6649900,502100 6649900,502100 6650300,"
                "499900 6650300,499900 6649900))",
            )
            connection.execute(
                text(
                    "UPDATE catalog.objects SET object_kind='boundary' WHERE id=:id"
                ),
                {"id": boundary_object_id},
            )
            connection.execute(
                text(
                    "INSERT INTO domain.districts "
                    "(id, canonical_object_id, name, slug, display_order, enabled) "
                    "VALUES (:id, :object_id, 'F8 district', :slug, "
                    "(SELECT min(candidate) FROM generate_series(10000,32767) "
                    "candidates(candidate) "
                    "LEFT JOIN domain.districts existing ON existing.display_order=candidate "
                    "WHERE existing.id IS NULL), false)"
                ),
                {"id": district_id, "object_id": boundary_object_id, "slug": f"f8-{suffix}"},
            )
            for index, center_x in enumerate((500000, 500400, 502000)):
                connection.execute(
                    text(
                        "INSERT INTO analytics.analysis_cells "
                        "(cell_id, grid_version, grid_i, grid_j, cell_size_m, district_id, "
                        "center, center_metric, geom, geom_metric) VALUES "
                        "(:cell_id,:grid_version,:grid_i,0,200,:district_id,"
                        "ST_Transform(ST_SetSRID(ST_MakePoint(:x,6650100),32636),4326),"
                        "ST_SetSRID(ST_MakePoint(:x,6650100),32636),"
                        "ST_Transform(ST_MakeEnvelope(:x-100,6650000,:x+100,6650200,32636),4326),"
                        "ST_MakeEnvelope(:x-100,6650000,:x+100,6650200,32636))"
                    ),
                    {
                        "cell_id": cell_ids[index],
                        "grid_version": grid_version,
                        "grid_i": index,
                        "district_id": district_id,
                        "x": center_x,
                    },
                )
            insert_object(connection, ordinary_id, "Ordinary", "POINT(500000 6650100)")
            insert_object(
                connection,
                facility_analysis_id,
                "Facility polygon",
                "POLYGON((500300 6650000,500500 6650000,500500 6650200,"
                "500300 6650200,500300 6650000))",
            )
            insert_object(
                connection, facility_point_id, "Facility point", "POINT(502000 6650100)"
            )
            insert_object(
                connection,
                line_id,
                "Ordinary line",
                "LINESTRING(501900 6650500,502100 6650500)",
            )
            for object_id in (
                ordinary_id,
                facility_analysis_id,
                facility_point_id,
                line_id,
            ):
                connection.execute(
                    text(
                        "INSERT INTO catalog.object_categories "
                        "(object_id,category_key,lifecycle_status) VALUES (:id,:category,'active')"
                    ),
                    {"id": object_id, "category": category_key},
                )
            connection.execute(
                text(
                    "INSERT INTO domain.facility_entities "
                    "(id,category_key,representative_object_id,display_object_id,analysis_object_id,"
                    "lifecycle_status,link_method,evidence) VALUES "
                    "(:id,:category,:analysis,:analysis,:analysis,'active','test','{}')"
                ),
                {"id": facility_id, "category": category_key, "analysis": facility_analysis_id},
            )
            for object_id, role in (
                (facility_analysis_id, "FACILITY_SITE"),
                (facility_point_id, "POINT"),
            ):
                connection.execute(
                    text(
                        "INSERT INTO domain.facility_entity_members "
                        "(facility_entity_id,canonical_object_id,geometry_role,lifecycle_status,"
                        "link_method,evidence) VALUES "
                        "(:facility,:object,:role,'active','test','{}')"
                    ),
                    {"facility": facility_id, "object": object_id, "role": role},
                )

        distance_definition = metric_definition(
            f"test.f8_{suffix}.distance",
            "catalog.nearest_distance",
            category_key,
        )
        distance_context = MetricProviderContext(engine, distance_definition, grid_version)
        distance = CatalogNearestDistanceProvider().calculate(distance_context)
        assert distance.diagnostics["target_count"] == 3
        assert distance.diagnostics["grid_cell_count"] == 3
        assert [value for _, value in distance.values] == pytest.approx(
            [0.0, 0.0, 400.0]
        )

        repeated = CatalogNearestDistanceProvider().calculate(distance_context)
        assert repeated.input_fingerprint == distance.input_fingerprint
        assert repeated.values == distance.values

        count_definition = metric_definition(
            f"test.f8_{suffix}.count",
            "catalog.count_within_radius",
            category_key,
            radius_m=250,
        )
        counted = CatalogCountWithinRadiusProvider().calculate(
            MetricProviderContext(engine, count_definition, grid_version)
        )
        assert counted.diagnostics["target_count"] == 3
        assert [value for _, value in counted.values] == [1.0, 1.0, 0.0]

        boundary_count_definition = metric_definition(
            f"test.f8_{suffix}.boundary_count",
            "catalog.count_within_radius",
            category_key,
            radius_m=400,
        )
        boundary_counted = CatalogCountWithinRadiusProvider().calculate(
            MetricProviderContext(engine, boundary_count_definition, grid_version)
        )
        assert [value for _, value in boundary_counted.values] == [2.0, 2.0, 1.0]

        smooth = CatalogSmoothInfluenceProvider().calculate(
            MetricProviderContext(
                engine,
                smooth_definition(
                    f"test.f8_{suffix}.smooth", category_key, radius_m=500
                ),
                grid_version,
            )
        )
        assert smooth.diagnostics["target_count"] == 3
        assert smooth.diagnostics["kernel"] == "compact_quartic_v1"
        assert smooth.diagnostics["spatial_match_count"] == 5
        assert [value for _, value in smooth.values] == pytest.approx(
            [1.4096, 1.1296, 0.1296]
        )
        changed_radius = CatalogSmoothInfluenceProvider().calculate(
            MetricProviderContext(
                engine,
                smooth_definition(
                    f"test.f8_{suffix}.smooth_wide", category_key, radius_m=600
                ),
                grid_version,
            )
        )
        assert changed_radius.input_fingerprint != smooth.input_fingerprint

        with engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE catalog.objects SET "
                    "geom=ST_Transform(ST_SetSRID(ST_MakePoint(500010,6650100),32636),4326) "
                    "WHERE id=:id"
                ),
                {"id": ordinary_id},
            )
        geometry_changed = CatalogNearestDistanceProvider().calculate(distance_context)
        assert geometry_changed.input_fingerprint != distance.input_fingerprint
        assert [value for _, value in geometry_changed.values] == pytest.approx(
            [10.0, 0.0, 400.0]
        )

        with engine.begin() as connection:
            connection.execute(
                text("UPDATE catalog.objects SET lifecycle_status='inactive' WHERE id=:id"),
                {"id": line_id},
            )
        inactive_object = CatalogNearestDistanceProvider().calculate(distance_context)
        assert inactive_object.diagnostics["target_count"] == 2
        with engine.begin() as connection:
            connection.execute(
                text("UPDATE catalog.objects SET lifecycle_status='active' WHERE id=:id"),
                {"id": line_id},
            )

        with engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE domain.facility_entities "
                    "SET lifecycle_status='inactive' WHERE id=:id"
                ),
                {"id": facility_id},
            )
        inactive_facility = CatalogNearestDistanceProvider().calculate(distance_context)
        assert inactive_facility.diagnostics["target_count"] == 4
        assert inactive_facility.values[-1][1] == pytest.approx(0.0)
        with engine.begin() as connection:
            connection.execute(
                text("UPDATE domain.facility_entities SET lifecycle_status='active' WHERE id=:id"),
                {"id": facility_id},
            )

        with engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE catalog.object_categories SET lifecycle_status='inactive' "
                    "WHERE object_id=:id AND category_key=:category"
                ),
                {"id": facility_point_id, "category": category_key},
            )
        changed = CatalogNearestDistanceProvider().calculate(distance_context)
        assert changed.input_fingerprint != geometry_changed.input_fingerprint
        assert changed.diagnostics["target_count"] == 3

        with engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE catalog.object_categories SET lifecycle_status='active' "
                    "WHERE object_id=:id AND category_key=:category"
                ),
                {"id": facility_point_id, "category": category_key},
            )
            connection.execute(
                text("UPDATE catalog.objects SET lifecycle_status='inactive' WHERE id=:id"),
                {"id": facility_analysis_id},
            )
        with pytest.raises(MetricProviderError, match="invalid analytical target geometries"):
            CatalogNearestDistanceProvider().calculate(distance_context)
    finally:
        with engine.begin() as connection:
            connection.execute(
                text("DELETE FROM domain.facility_entity_members WHERE facility_entity_id=:id"),
                {"id": facility_id},
            )
            connection.execute(
                text("DELETE FROM domain.facility_entities WHERE id=:id"), {"id": facility_id}
            )
            connection.execute(
                text("DELETE FROM catalog.object_categories WHERE category_key=:key"),
                {"key": category_key},
            )
            connection.execute(
                text("DELETE FROM analytics.analysis_cells WHERE grid_version=:version"),
                {"version": grid_version},
            )
            connection.execute(
                text("DELETE FROM domain.districts WHERE id=:id"), {"id": district_id}
            )
            connection.execute(
                text("DELETE FROM catalog.objects WHERE id=ANY(:ids)"), {"ids": object_ids}
            )
            connection.execute(
                text("DELETE FROM catalog.categories WHERE key=:key"), {"key": category_key}
            )
        engine.dispose()
