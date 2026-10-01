from inspect import getsource
from uuid import UUID

from app.data.catalog import _load_candidates
from app.data.map_catalog import (
    MAP_FEATURE_IDS_CATEGORY_FIRST_SQL,
    MAP_FEATURE_IDS_MULTI_DISTRICT_SPATIAL_FIRST_SQL,
    MAP_FEATURE_IDS_ONE_DISTRICT_SPATIAL_FIRST_SQL,
    MAP_FEATURE_IDS_SPATIAL_FIRST_SQL,
    SPATIAL_FIRST_CATEGORIES,
    feature_ids_query,
)
from app.data.search_catalog import SEARCH_SQL


def test_dense_transport_categories_use_spatial_first_map_query() -> None:
    assert {"transport.road", "transport.stop"} == SPATIAL_FIRST_CATEGORIES
    assert not SPATIAL_FIRST_CATEGORIES.isdisjoint(("transport.stop",))
    assert not SPATIAL_FIRST_CATEGORIES.isdisjoint(
        ("nature.park", "transport.road")
    )
    assert SPATIAL_FIRST_CATEGORIES.isdisjoint(("nature.park", "education.school"))

    first = UUID("161ba369-c548-5569-9cc2-679522090220")
    second = UUID("01992d00-0fe0-54cd-99db-b35bbb7f34e2")
    assert feature_ids_query(("transport.stop",), ()) is MAP_FEATURE_IDS_SPATIAL_FIRST_SQL
    assert (
        feature_ids_query(("transport.stop",), (first,))
        is MAP_FEATURE_IDS_ONE_DISTRICT_SPATIAL_FIRST_SQL
    )
    assert (
        feature_ids_query(("transport.stop",), (first, second))
        is MAP_FEATURE_IDS_MULTI_DISTRICT_SPATIAL_FIRST_SQL
    )
    assert feature_ids_query(("nature.park",), ()) is MAP_FEATURE_IDS_CATEGORY_FIRST_SQL
    stop_sql = str(feature_ids_query(("transport.stop",), ()))
    assert "spatial_objects AS MATERIALIZED" in stop_sql
    assert "category_ids AS MATERIALIZED" not in stop_sql
    assert "JOIN catalog.object_categories AS selected_category" in stop_sql
    assert "selected_category.object_id = candidate.id" in stop_sql


def test_search_v2_builds_indexable_entity_branches_before_final_limit() -> None:
    sql = str(SEARCH_SQL[(False, "none")])

    assert "ordinary_results AS MATERIALIZED" in sql
    assert "facility_results AS MATERIALIZED" in sql
    assert "street_results AS MATERIALIZED" in sql
    assert "logical_results AS MATERIALIZED" in sql
    assert "object.search_name_v2 LIKE" in sql
    assert "street.search_name LIKE" in sql
    assert "object.search_name_v2 % input.value" not in sql
    assert "CROSS JOIN LATERAL" in sql
    assert "domain.facility_entity_members" in sql
    assert "domain.street_entity_members" in sql
    assert "UNION ALL SELECT * FROM facility_results" in sql
    assert "UNION ALL SELECT * FROM street_results" in sql
    assert "top_results AS MATERIALIZED" in sql
    assert sql.index("logical_results AS MATERIALIZED") < sql.index("ranked AS MATERIALIZED")
    assert sql.index("ranked AS MATERIALIZED") < sql.index("top_results AS MATERIALIZED")


def test_canonical_candidate_join_keeps_staging_identity_indexes_usable() -> None:
    source = getsource(_load_candidates)

    assert "source_object_id bigint" in source
    assert "requested.source_object_id = node.osm_id" in source
    assert "requested.source_object_id = way.osm_id" in source
    assert "requested.source_object_id = relation.osm_id" in source
    assert "requested.source_object_id = node.osm_id::text" not in source
    assert "requested.source_object_id = way.osm_id::text" not in source
    assert "requested.source_object_id = relation.osm_id::text" not in source
