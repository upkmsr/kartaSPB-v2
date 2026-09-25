import json
from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import Engine, text
from sqlalchemy.sql.elements import TextClause

from app.data.districts import validate_district_selection
from app.data.map_catalog import UnknownCategoriesError


@dataclass(frozen=True)
class SearchResultData:
    id: UUID
    name: str
    categories: list[str]
    object_kind: str
    geometry_type: str
    representative_point: dict[str, Any]
    bbox: tuple[float, float, float, float]


DistrictMode = Literal["none", "one", "many"]


def _district_scope_cte(mode: DistrictMode) -> str:
    if mode == "one":
        return """
        selected_scope AS MATERIALIZED (
            SELECT object.geom
            FROM domain.districts AS district
            JOIN catalog.objects AS object ON object.id = district.canonical_object_id
            WHERE district.id = :district_id
              AND district.enabled
              AND object.lifecycle_status = 'active'
        )
        """
    if mode == "many":
        return """
        selected_scope AS MATERIALIZED (
            SELECT ST_UnaryUnion(ST_Collect(object.geom)) AS geom
            FROM domain.districts AS district
            JOIN catalog.objects AS object ON object.id = district.canonical_object_id
            WHERE district.id = ANY(:district_ids)
              AND district.enabled
              AND object.lifecycle_status = 'active'
        )
        """
    return ""


def _search_sql(*, categories: bool, district_mode: DistrictMode) -> TextClause:
    ctes = ["query_input AS (SELECT CAST(:query AS text) AS value)"]
    scope = _district_scope_cte(district_mode)
    if scope:
        ctes.append(scope)
    category_filter = ""
    if categories:
        category_filter = """
          AND EXISTS (
              SELECT 1
              FROM catalog.object_categories AS selected_category
              WHERE selected_category.object_id = object.id
                AND selected_category.lifecycle_status = 'active'
                AND selected_category.category_key = ANY(:categories)
          )
        """
    district_join = ""
    district_filter = ""
    if district_mode != "none":
        district_join = "CROSS JOIN selected_scope AS scope"
        district_filter = """
          AND object.geom && scope.geom
          AND ST_Intersects(object.geom, scope.geom)
        """
    ctes.append(
        f"""
        ranked AS MATERIALIZED (
            SELECT object.id,
                   object.name,
                   object.search_name,
                   object.object_kind,
                   object.geom,
                   CASE
                     WHEN object.search_name = input.value THEN 0
                     WHEN object.search_name LIKE input.value || '%' THEN 1
                     WHEN object.search_name LIKE '% ' || input.value || '%' THEN 2
                     WHEN object.search_name LIKE '%' || input.value || '%' THEN 3
                     ELSE 4
                   END AS match_rank,
                   similarity(object.search_name, input.value) AS trigram_score,
                   row_number() OVER (
                       PARTITION BY object.search_name ORDER BY object.id
                   ) AS duplicate_ordinal
            FROM catalog.objects AS object
            CROSS JOIN query_input AS input
            {district_join}
            WHERE object.lifecycle_status = 'active'
              AND object.name IS NOT NULL
              AND object.search_name IS NOT NULL
              AND (
                  object.search_name LIKE '%' || input.value || '%'
                  OR object.search_name % input.value
              )
              {category_filter}
              {district_filter}
        )
        """
    )
    return text(
        f"""
        WITH {','.join(ctes)}
        SELECT ranked.id,
               ranked.name,
               ranked.object_kind,
               replace(ST_GeometryType(ranked.geom), 'ST_', '') AS geometry_type,
               ST_AsGeoJSON(ST_PointOnSurface(ranked.geom), 6)::jsonb
                   AS representative_point,
               ARRAY[
                   ST_XMin(Box3D(ranked.geom)),
                   ST_YMin(Box3D(ranked.geom)),
                   ST_XMax(Box3D(ranked.geom)),
                   ST_YMax(Box3D(ranked.geom))
               ]::double precision[] AS bbox,
               ARRAY(
                   SELECT category.category_key
                   FROM catalog.object_categories AS category
                   WHERE category.object_id = ranked.id
                     AND category.lifecycle_status = 'active'
                   ORDER BY category.category_key
               ) AS categories
        FROM ranked
        ORDER BY ranked.duplicate_ordinal,
                 ranked.match_rank,
                 ranked.trigram_score DESC,
                 char_length(ranked.search_name),
                 ranked.search_name,
                 ranked.id
        LIMIT :limit
        """
    )


DISTRICT_MODES: tuple[DistrictMode, ...] = ("none", "one", "many")

SEARCH_SQL: dict[tuple[bool, DistrictMode], TextClause] = {
    (has_categories, district_mode): _search_sql(
        categories=has_categories, district_mode=district_mode
    )
    for has_categories in (False, True)
    for district_mode in DISTRICT_MODES
}


def _geometry(value: Any) -> dict[str, Any]:
    parsed = json.loads(value) if isinstance(value, str) else value
    if not isinstance(parsed, dict):
        raise ValueError("PostGIS returned invalid GeoJSON geometry")
    return {str(key): item for key, item in parsed.items()}


class SearchCatalogService:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def search(
        self,
        query: str,
        categories: tuple[str, ...],
        district_ids: tuple[UUID, ...],
        limit: int,
    ) -> list[SearchResultData]:
        with self.engine.connect() as connection:
            if categories:
                enabled: set[str] = set(
                    connection.execute(
                        text(
                            "SELECT key FROM catalog.categories "
                            "WHERE enabled AND key = ANY(:categories)"
                        ),
                        {"categories": list(categories)},
                    ).scalars()
                )
                unknown = sorted(set(categories) - enabled)
                if unknown:
                    raise UnknownCategoriesError(unknown)
            validate_district_selection(connection, district_ids)
            district_mode: DistrictMode = (
                "none" if not district_ids else "one" if len(district_ids) == 1 else "many"
            )
            parameters: dict[str, Any] = {"query": query, "limit": limit}
            if categories:
                parameters["categories"] = list(categories)
            if district_mode == "one":
                parameters["district_id"] = district_ids[0]
            elif district_mode == "many":
                parameters["district_ids"] = list(district_ids)
            rows = connection.execute(
                SEARCH_SQL[(bool(categories), district_mode)], parameters
            ).all()
        return [
            SearchResultData(
                id=row.id,
                name=str(row.name),
                categories=[str(category) for category in row.categories],
                object_kind=str(row.object_kind),
                geometry_type=str(row.geometry_type),
                representative_point=_geometry(row.representative_point),
                bbox=tuple(float(value) for value in row.bbox),  # type: ignore[arg-type]
            )
            for row in rows
        ]
