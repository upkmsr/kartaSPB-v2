import json
from dataclasses import dataclass
from typing import Any, Literal, cast
from uuid import UUID

from sqlalchemy import Engine, text
from sqlalchemy.sql.elements import TextClause

from app.data.districts import validate_district_selection
from app.data.map_catalog import UnknownCategoriesError

SearchResultType = Literal["object", "facility", "street"]
DistrictMode = Literal["none", "one", "many"]


@dataclass(frozen=True)
class SearchResultData:
    id: UUID
    result_type: SearchResultType
    detail_object_id: UUID | None
    name: str
    categories: list[str]
    object_kind: str
    geometry_type: str
    representative_point: dict[str, Any]
    bbox: tuple[float, float, float, float]


def _district_scope_cte(mode: DistrictMode) -> str:
    if mode == "one":
        return """
        selected_scope AS MATERIALIZED (
            SELECT object.geom
            FROM domain.districts AS district
            JOIN catalog.objects AS object ON object.id=district.canonical_object_id
            WHERE district.id=:district_id
              AND district.enabled
              AND object.lifecycle_status='active'
        )
        """
    if mode == "many":
        return """
        selected_scope AS MATERIALIZED (
            SELECT ST_UnaryUnion(ST_Collect(object.geom)) AS geom
            FROM domain.districts AS district
            JOIN catalog.objects AS object ON object.id=district.canonical_object_id
            WHERE district.id=ANY(:district_ids)
              AND district.enabled
              AND object.lifecycle_status='active'
        )
        """
    return ""


def _search_sql(*, categories: bool, district_mode: DistrictMode) -> TextClause:
    ctes = ["query_input AS (SELECT CAST(:query AS text) AS value)"]
    scope = _district_scope_cte(district_mode)
    if scope:
        ctes.append(scope)

    scope_join = "CROSS JOIN selected_scope AS scope" if district_mode != "none" else ""
    object_spatial = (
        "AND object.geom && scope.geom AND ST_Intersects(object.geom,scope.geom)"
        if district_mode != "none"
        else ""
    )
    facility_spatial = (
        "AND display.geom && scope.geom AND ST_Intersects(display.geom,scope.geom)"
        if district_mode != "none"
        else ""
    )
    street_spatial = (
        "AND street.geom && scope.geom AND ST_Intersects(street.geom,scope.geom)"
        if district_mode != "none"
        else ""
    )
    object_category = ""
    facility_category = ""
    if categories:
        object_category = """
          AND EXISTS (
              SELECT 1 FROM catalog.object_categories AS selected_category
              WHERE selected_category.object_id=object.id
                AND selected_category.lifecycle_status='active'
                AND selected_category.category_key=ANY(:categories)
          )
        """
        facility_category = "AND facility.category_key=ANY(:categories)"

    ctes.append(
        f"""
        ordinary_results AS MATERIALIZED (
            SELECT object.id,
                   'object'::text AS result_type,
                   object.id AS detail_object_id,
                   object.name,
                   object.search_name_v2 AS search_name,
                   object.object_kind,
                   object.geom AS representation_geom,
                   NULL::geometry AS stored_representative_point,
                   ARRAY(
                       SELECT category.category_key
                       FROM catalog.object_categories AS category
                       WHERE category.object_id=object.id
                         AND category.lifecycle_status='active'
                       ORDER BY category.category_key
                   ) AS categories
            FROM catalog.objects AS object
            CROSS JOIN query_input AS input
            {scope_join}
            WHERE :include_objects
              AND object.lifecycle_status='active'
              AND object.name IS NOT NULL
              AND object.search_name_v2 LIKE '%' || input.value || '%'
              {object_category}
              {object_spatial}
              AND NOT EXISTS (
                  SELECT 1 FROM domain.facility_entity_members AS member
                  JOIN domain.facility_entities AS facility
                    ON facility.id=member.facility_entity_id
                   AND facility.lifecycle_status='active'
                  WHERE member.canonical_object_id=object.id
                    AND member.lifecycle_status='active'
              )
              AND NOT EXISTS (
                  SELECT 1 FROM domain.street_entity_members AS member
                  JOIN domain.street_entities AS street
                    ON street.id=member.street_entity_id
                   AND street.lifecycle_status='active'
                  WHERE member.canonical_object_id=object.id
                    AND member.lifecycle_status='active'
              )
        )
        """
    )
    ctes.append(
        f"""
        facility_results AS MATERIALIZED (
            SELECT facility.id,
                   'facility'::text AS result_type,
                   representative.id AS detail_object_id,
                   coalesce(representative.name,matched.name) AS name,
                   matched.search_name,
                   representative.object_kind,
                   display.geom AS representation_geom,
                   NULL::geometry AS stored_representative_point,
                   ARRAY[facility.category_key]::varchar[] AS categories
            FROM domain.facility_entities AS facility
            JOIN catalog.objects AS representative
              ON representative.id=facility.representative_object_id
             AND representative.lifecycle_status='active'
            JOIN catalog.objects AS display
              ON display.id=facility.display_object_id
             AND display.lifecycle_status='active'
            CROSS JOIN query_input AS input
            CROSS JOIN LATERAL (
                SELECT member_object.name,member_object.search_name_v2 AS search_name
                FROM domain.facility_entity_members AS member
                JOIN catalog.objects AS member_object
                  ON member_object.id=member.canonical_object_id
                 AND member_object.lifecycle_status='active'
                WHERE member.facility_entity_id=facility.id
                  AND member.lifecycle_status='active'
                  AND member_object.search_name_v2 LIKE '%' || input.value || '%'
                ORDER BY
                  CASE
                    WHEN member_object.search_name_v2=input.value THEN 0
                    WHEN member_object.search_name_v2 LIKE input.value || '%' THEN 1
                    WHEN member_object.search_name_v2 LIKE '% ' || input.value || '%' THEN 2
                    ELSE 3
                  END,
                  similarity(member_object.search_name_v2,input.value) DESC,
                  member_object.id
                LIMIT 1
            ) AS matched
            {scope_join}
            WHERE :include_objects
              AND facility.lifecycle_status='active'
              {facility_category}
              {facility_spatial}
        )
        """
    )
    ctes.append(
        f"""
        street_results AS MATERIALIZED (
            SELECT street.id,
                   'street'::text AS result_type,
                   NULL::uuid AS detail_object_id,
                   street.display_name AS name,
                   street.search_name,
                   'street'::text AS object_kind,
                   street.geom AS representation_geom,
                   street.representative_point AS stored_representative_point,
                   ARRAY['transport.road']::varchar[] AS categories
            FROM domain.street_entities AS street
            CROSS JOIN query_input AS input
            {scope_join}
            WHERE street.lifecycle_status='active'
              AND street.search_name LIKE '%' || input.value || '%'
              {street_spatial}
        )
        """
    )
    ctes.append(
        """
        logical_results AS MATERIALIZED (
            SELECT * FROM ordinary_results
            UNION ALL SELECT * FROM facility_results
            UNION ALL SELECT * FROM street_results
        )
        """
    )
    ctes.append(
        """
        ranked AS MATERIALIZED (
            SELECT result.*,
                   CASE
                     WHEN result.search_name=input.value THEN 0
                     WHEN result.search_name LIKE input.value || '%' THEN 1
                     WHEN result.search_name LIKE '% ' || input.value || '%' THEN 2
                     ELSE 3
                   END AS match_rank,
                   similarity(result.search_name,input.value) AS trigram_score,
                   row_number() OVER (
                     PARTITION BY result.search_name
                     ORDER BY CASE result.result_type
                       WHEN 'facility' THEN 0 WHEN 'street' THEN 1 ELSE 2 END,
                       result.id
                   ) AS duplicate_ordinal
            FROM logical_results AS result
            CROSS JOIN query_input AS input
        )
        """
    )
    ctes.append(
        """
        top_results AS MATERIALIZED (
            SELECT * FROM ranked
            ORDER BY duplicate_ordinal,match_rank,trigram_score DESC,
                     char_length(search_name),search_name,result_type,id
            LIMIT :limit
        )
        """
    )
    return text(
        f"""
        WITH {','.join(ctes)}
        SELECT result.id,result.result_type,result.detail_object_id,result.name,
               result.categories,result.object_kind,
               replace(ST_GeometryType(result.representation_geom),'ST_','') AS geometry_type,
               ST_AsGeoJSON(
                 coalesce(
                   result.stored_representative_point,
                   CASE
                     WHEN ST_GeometryType(result.representation_geom)='ST_LineString'
                       THEN ST_LineInterpolatePoint(result.representation_geom,0.5)
                     ELSE ST_PointOnSurface(result.representation_geom)
                   END
                 ),6
               )::jsonb AS representative_point,
               ARRAY[
                 ST_XMin(Box3D(result.representation_geom)),
                 ST_YMin(Box3D(result.representation_geom)),
                 ST_XMax(Box3D(result.representation_geom)),
                 ST_YMax(Box3D(result.representation_geom))
               ]::double precision[] AS bbox
        FROM top_results AS result
        ORDER BY result.duplicate_ordinal,result.match_rank,result.trigram_score DESC,
                 char_length(result.search_name),result.search_name,result.result_type,result.id
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
        include_objects: bool = True,
    ) -> list[SearchResultData]:
        with self.engine.connect() as connection:
            if categories:
                enabled: set[str] = set(
                    connection.execute(
                        text(
                            "SELECT key FROM catalog.categories "
                            "WHERE enabled AND key=ANY(:categories)"
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
            parameters: dict[str, Any] = {
                "query": query,
                "limit": limit,
                "include_objects": include_objects,
            }
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
                result_type=cast(SearchResultType, str(row.result_type)),
                detail_object_id=row.detail_object_id,
                name=str(row.name),
                categories=[str(category) for category in row.categories],
                object_kind=str(row.object_kind),
                geometry_type=str(row.geometry_type),
                representative_point=_geometry(row.representative_point),
                bbox=tuple(float(value) for value in row.bbox),  # type: ignore[arg-type]
            )
            for row in rows
        ]
