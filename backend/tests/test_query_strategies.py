from uuid import UUID

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
    assert "category_ids AS MATERIALIZED" in stop_sql
    assert "JOIN category_ids AS selected_category" in stop_sql


def test_search_query_builds_indexable_candidate_branches_before_geometry() -> None:
    sql = str(SEARCH_SQL[(False, "none")])

    assert "candidate_ids AS MATERIALIZED" in sql
    assert "object.search_name LIKE" in sql
    assert "object.search_name % input.value" not in sql
    assert " OR " not in sql
    assert "CROSS JOIN LATERAL" in sql
    assert "WHERE matched.id = candidate.id" in sql
    assert "top_results AS MATERIALIZED" in sql
    assert "JOIN catalog.objects AS object ON object.id = result.id" in sql
    assert sql.index("candidate_ids AS MATERIALIZED") < sql.index("ranked AS MATERIALIZED")
    assert sql.index("ranked AS MATERIALIZED") < sql.index("top_results AS MATERIALIZED")
