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
    candidate_category_filter = ""
    if categories:
        candidate_category_filter = """
              AND EXISTS (
                  SELECT 1
                  FROM catalog.object_categories AS selected_category
                  WHERE selected_category.object_id = object.id
                    AND selected_category.lifecycle_status = 'active'
                    AND selected_category.category_key = ANY(:categories)
              )
        """
    ctes.append(
        f"""
        candidate_ids AS MATERIALIZED (
            SELECT object.id
            FROM catalog.objects AS object
            CROSS JOIN query_input AS input
            WHERE object.lifecycle_status = 'active'
              AND object.search_name IS NOT NULL
              AND object.search_name LIKE '%' || input.value || '%'
              {candidate_category_filter}
        )
        """
    )
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
                   CASE
                     WHEN object.search_name = input.value THEN 0
                     WHEN object.search_name LIKE input.value || '%' THEN 1
                     WHEN object.search_name LIKE '% ' || input.value || '%' THEN 2
                     WHEN object.search_name LIKE '%' || input.value || '%' THEN 3
                     ELSE 3
                   END AS match_rank,
                   similarity(object.search_name, input.value) AS trigram_score,
                   row_number() OVER (
                       PARTITION BY object.search_name ORDER BY object.id
                   ) AS duplicate_ordinal
            FROM candidate_ids AS candidate
            CROSS JOIN LATERAL (
                SELECT matched.id,
                       matched.name,
                       matched.search_name,
                       matched.object_kind,
                       matched.geom
                FROM catalog.objects AS matched
                WHERE matched.id = candidate.id
                  AND matched.lifecycle_status = 'active'
                  AND matched.name IS NOT NULL
                  AND matched.search_name IS NOT NULL
                OFFSET 0
            ) AS object
            CROSS JOIN query_input AS input
            {district_join}
            WHERE true
              {district_filter}
        )
        """
    )
    ctes.append(
        """
        top_results AS MATERIALIZED (
            SELECT *
            FROM ranked
            ORDER BY duplicate_ordinal,
                     match_rank,
                     trigram_score DESC,
                     char_length(search_name),
                     search_name,
                     id
            LIMIT :limit
        )
        """
    )
    return text(
        f"""
        WITH {','.join(ctes)}
        SELECT result.id,
               result.name,
               result.object_kind,
               replace(ST_GeometryType(object.geom), 'ST_', '') AS geometry_type,
               ST_AsGeoJSON(
                   CASE
                     WHEN ST_GeometryType(object.geom) = 'ST_LineString'
                       THEN ST_LineInterpolatePoint(object.geom, 0.5)
                     ELSE ST_PointOnSurface(object.geom)
                   END,
                   6
               )::jsonb
                   AS representative_point,
               ARRAY[
                   ST_XMin(Box3D(object.geom)),
                   ST_YMin(Box3D(object.geom)),
                   ST_XMax(Box3D(object.geom)),
                   ST_YMax(Box3D(object.geom))
               ]::double precision[] AS bbox,
               ARRAY(
                   SELECT category.category_key
                   FROM catalog.object_categories AS category
                   WHERE category.object_id = result.id
                     AND category.lifecycle_status = 'active'
                   ORDER BY category.category_key
               ) AS categories
        FROM top_results AS result
        JOIN catalog.objects AS object ON object.id = result.id
        ORDER BY result.duplicate_ordinal,
                 result.match_rank,
                 result.trigram_score DESC,
                 char_length(result.search_name),
                 result.search_name,
                 result.id
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
