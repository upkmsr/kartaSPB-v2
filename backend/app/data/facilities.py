from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter, defaultdict, deque
from dataclasses import asdict, dataclass
from typing import Any
from uuid import UUID, uuid5

from sqlalchemy import Connection, Engine, text

from app.db.session import get_engine

ELIGIBLE_CATEGORIES = (
    "education.kindergarten",
    "education.school",
    "healthcare.hospital",
    "healthcare.clinic",
)
FACILITY_NAMESPACE = UUID("6e172d0f-bf3f-4e03-b61e-15010228bc60")
MAX_CANDIDATE_DISTANCE_METERS = 100


@dataclass(frozen=True)
class CandidateObject:
    id: UUID
    source_id: int
    source_type: str
    source_object_id: str
    name: str | None
    geometry_type: str
    geometry_role: str
    tags: dict[str, Any]


@dataclass(frozen=True)
class CandidatePair:
    category_key: str
    point: CandidateObject
    area: CandidateObject
    contained: bool
    distance_meters: float
    shared_site_relations: tuple[int, ...]
    strong: bool
    methods: tuple[str, ...]
    rejected_reason: str | None


@dataclass(frozen=True)
class PlannedMember:
    object: CandidateObject
    methods: tuple[str, ...]


@dataclass(frozen=True)
class PlannedGroup:
    category_key: str
    members: tuple[PlannedMember, ...]
    representative_object_id: UUID
    display_object_id: UUID
    analysis_object_id: UUID
    methods: tuple[str, ...]


@dataclass(frozen=True)
class FacilityDryRunReport:
    candidate_pairs: int
    strong_pairs: int
    ambiguous_pairs: int
    conflicts: int
    multi_member_groups: int
    groups: tuple[PlannedGroup, ...]
    strong_by_method: dict[str, int]
    explicit_site_links: int


@dataclass(frozen=True)
class FacilityRefreshResult:
    candidate_pairs: int
    strong_pairs: int
    ambiguous_pairs: int
    conflicts: int
    active_entities: int
    multi_member_entities: int
    active_members: int
    created_entities: int
    changed_entities: int
    unchanged_entities: int


CANDIDATE_SQL = text(
    """
    WITH eligible_ids AS MATERIALIZED (
        SELECT DISTINCT object.id, category.category_key, object.name, object.geom
        FROM catalog.objects AS object
        JOIN catalog.object_categories AS category
          ON category.object_id=object.id
         AND category.lifecycle_status='active'
         AND category.category_key=ANY(:categories)
        WHERE object.lifecycle_status='active'
    ), eligible AS MATERIALIZED (
        SELECT candidate.id,
               candidate.category_key,
               candidate.name,
               candidate.geom,
               GeometryType(candidate.geom) AS geometry_type,
               binding.source_id,
               binding.source_object_type,
               binding.source_object_id,
               coalesce(node.tags,way.tags,relation.tags,'{}'::jsonb) AS tags
        FROM eligible_ids AS candidate
        JOIN catalog.object_sources AS binding
          ON binding.object_id=candidate.id AND binding.source_status='present'
        LEFT JOIN staging.osm_nodes AS node
          ON binding.source_object_type='node'
         AND node.source_id=binding.source_id
         AND node.osm_id=binding.source_object_id::bigint
        LEFT JOIN staging.osm_ways AS way
          ON binding.source_object_type='way'
         AND way.source_id=binding.source_id
         AND way.osm_id=binding.source_object_id::bigint
        LEFT JOIN staging.osm_relations AS relation
          ON binding.source_object_type='relation'
         AND relation.source_id=binding.source_id
         AND relation.osm_id=binding.source_object_id::bigint
    ), points AS MATERIALIZED (
        SELECT * FROM eligible WHERE geometry_type='POINT'
    ), areas AS MATERIALIZED (
        SELECT * FROM eligible WHERE geometry_type IN ('POLYGON','MULTIPOLYGON')
    )
    SELECT point.category_key,
           point.id AS point_id,
           point.source_id AS point_source_id,
           point.source_object_type AS point_source_type,
           point.source_object_id AS point_source_object_id,
           point.name AS point_name,
           point.geometry_type AS point_geometry_type,
           point.tags AS point_tags,
           area.id AS area_id,
           area.source_id AS area_source_id,
           area.source_object_type AS area_source_type,
           area.source_object_id AS area_source_object_id,
           area.name AS area_name,
           area.geometry_type AS area_geometry_type,
           area.tags AS area_tags,
           ST_Covers(area.geom,point.geom) AS contained,
           ST_Distance(area.geom::geography,point.geom::geography) AS distance_meters,
           coalesce(site.shared_relations,ARRAY[]::bigint[]) AS shared_site_relations
    FROM points AS point
    JOIN areas AS area
      ON area.category_key=point.category_key
     AND point.geom && ST_Expand(area.geom,0.002)
     AND ST_DWithin(point.geom::geography,area.geom::geography,:distance_meters)
    LEFT JOIN LATERAL (
        SELECT array_agg(DISTINCT point_member.relation_id ORDER BY point_member.relation_id)
                   AS shared_relations
        FROM staging.osm_relation_members AS point_member
        JOIN staging.osm_relation_members AS area_member
          ON area_member.source_id=point_member.source_id
         AND area_member.relation_id=point_member.relation_id
        JOIN staging.osm_relations AS site_relation
          ON site_relation.source_id=point_member.source_id
         AND site_relation.osm_id=point_member.relation_id
         AND site_relation.tags->>'type'='site'
        WHERE point.source_id=area.source_id
          AND point_member.source_id=point.source_id
          AND point_member.member_type=point.source_object_type
          AND point_member.member_id=point.source_object_id::bigint
          AND area_member.member_type=area.source_object_type
          AND area_member.member_id=area.source_object_id::bigint
    ) AS site ON true
    ORDER BY point.category_key,point.id,area.id
    """
)


def _normalized(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = unicodedata.normalize("NFKC", value).replace("\u00a0", " ").casefold()
    normalized = " ".join(normalized.split())
    return normalized or None


def _normalized_url(value: Any) -> str | None:
    normalized = _normalized(value)
    if normalized is None:
        return None
    return re.sub(r"^https?://(?:www\.)?", "", normalized).rstrip("/") or None


def _normalized_phone(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    numbers = sorted(
        number for part in re.split(r"[;,]", value) if len(number := re.sub(r"\D", "", part)) >= 7
    )
    return ";".join(numbers) or None


def _tag(tags: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = _normalized(tags.get(key))
        if value is not None:
            return value
    return None


def _direct_facility_semantics(category: str, tags: dict[str, Any]) -> bool:
    amenity = _tag(tags, "amenity")
    healthcare = _tag(tags, "healthcare")
    return {
        "education.kindergarten": amenity == "kindergarten",
        "education.school": amenity == "school",
        "healthcare.hospital": amenity == "hospital" or healthcare == "hospital",
        "healthcare.clinic": amenity == "clinic" or healthcare in {"clinic", "centre"},
    }[category]


def _geometry_role(category: str, geometry_type: str, tags: dict[str, Any]) -> str:
    if geometry_type == "POINT":
        return "POINT"
    if _tag(tags, "building", "building:part") is not None:
        return "BUILDING"
    if _direct_facility_semantics(category, tags):
        return "FACILITY_SITE"
    if geometry_type in {"POLYGON", "MULTIPOLYGON"}:
        return "OTHER_AREA"
    return "UNKNOWN"


def _same_nonempty(left: str | None, right: str | None) -> bool:
    return left is not None and left == right


def _evidence(
    category: str,
    point_tags: dict[str, Any],
    area_tags: dict[str, Any],
    area_role: str,
    *,
    contained: bool,
    shared_site_relations: tuple[int, ...],
) -> tuple[bool, tuple[str, ...], str | None]:
    point_ref = _tag(point_tags, "ref")
    area_ref = _tag(area_tags, "ref")
    point_wikidata = _tag(point_tags, "wikidata", "brand:wikidata")
    area_wikidata = _tag(area_tags, "wikidata", "brand:wikidata")
    for left, right, label in (
        (point_ref, area_ref, "contradictory_ref"),
        (point_wikidata, area_wikidata, "contradictory_wikidata"),
    ):
        if left is not None and right is not None and left != right:
            return False, (), label

    methods: list[str] = []
    if shared_site_relations:
        methods.append("explicit_site_relation")
    if _same_nonempty(point_ref, area_ref):
        methods.append("exact_ref")
    if _same_nonempty(point_wikidata, area_wikidata):
        methods.append("exact_wikidata")

    point_phone = _normalized_phone(
        point_tags.get("contact:phone") or point_tags.get("phone")
    )
    area_phone = _normalized_phone(area_tags.get("contact:phone") or area_tags.get("phone"))
    if contained and _same_nonempty(point_phone, area_phone):
        methods.append("exact_phone_contained")

    point_url = _normalized_url(
        point_tags.get("contact:website") or point_tags.get("website")
    )
    area_url = _normalized_url(area_tags.get("contact:website") or area_tags.get("website"))
    if contained and _same_nonempty(point_url, area_url):
        methods.append("exact_website_contained")

    point_name = _tag(point_tags, "name", "official_name")
    area_name = _tag(area_tags, "name", "official_name")
    point_operator = _tag(point_tags, "operator")
    area_operator = _tag(area_tags, "operator")
    same_name = _same_nonempty(point_name, area_name)
    same_operator = _same_nonempty(point_operator, area_operator)
    if contained and same_name and same_operator:
        methods.append("exact_name_operator_contained")
    if contained and same_name and area_role == "FACILITY_SITE":
        methods.append("exact_name_site_contained")

    point_street = _tag(point_tags, "addr:street")
    area_street = _tag(area_tags, "addr:street")
    point_house = _tag(point_tags, "addr:housenumber")
    area_house = _tag(area_tags, "addr:housenumber")
    same_complete_address = _same_nonempty(point_street, area_street) and _same_nonempty(
        point_house, area_house
    )
    compatible_facility_semantics = (
        _direct_facility_semantics(category, point_tags)
        and _direct_facility_semantics(category, area_tags)
        and (point_name is None or area_name is None)
    )
    if (
        contained
        and same_complete_address
        and (same_name or same_operator or compatible_facility_semantics)
    ):
        methods.append("exact_address_contained_facility")

    return bool(methods), tuple(sorted(set(methods))), None


def _candidate_object(row: Any, prefix: str, category: str) -> CandidateObject:
    tags = dict(getattr(row, f"{prefix}_tags") or {})
    geometry_type = str(getattr(row, f"{prefix}_geometry_type"))
    return CandidateObject(
        id=getattr(row, f"{prefix}_id"),
        source_id=int(getattr(row, f"{prefix}_source_id")),
        source_type=str(getattr(row, f"{prefix}_source_type")),
        source_object_id=str(getattr(row, f"{prefix}_source_object_id")),
        name=(
            str(getattr(row, f"{prefix}_name"))
            if getattr(row, f"{prefix}_name") is not None
            else None
        ),
        geometry_type=geometry_type,
        geometry_role=_geometry_role(category, geometry_type, tags),
        tags=tags,
    )


def _load_candidate_pairs(connection: Connection) -> list[CandidatePair]:
    rows = connection.execute(
        CANDIDATE_SQL,
        {
            "categories": list(ELIGIBLE_CATEGORIES),
            "distance_meters": MAX_CANDIDATE_DISTANCE_METERS,
        },
    ).all()
    pairs: list[CandidatePair] = []
    for row in rows:
        category = str(row.category_key)
        point = _candidate_object(row, "point", category)
        area = _candidate_object(row, "area", category)
        site_relations = tuple(int(value) for value in row.shared_site_relations)
        strong, methods, rejected = _evidence(
            category,
            point.tags,
            area.tags,
            area.geometry_role,
            contained=bool(row.contained),
            shared_site_relations=site_relations,
        )
        pairs.append(
            CandidatePair(
                category_key=category,
                point=point,
                area=area,
                contained=bool(row.contained),
                distance_meters=float(row.distance_meters),
                shared_site_relations=site_relations,
                strong=strong,
                methods=methods,
                rejected_reason=rejected,
            )
        )
    return pairs


def _metadata_score(member: CandidateObject) -> int:
    keys = ("name", "official_name", "operator", "ref", "wikidata", "addr:street")
    return sum(_tag(member.tags, key) is not None for key in keys)


def _role_members(members: list[CandidateObject]) -> tuple[UUID, UUID, UUID]:
    role_rank = {"FACILITY_SITE": 0, "POINT": 1, "BUILDING": 2, "OTHER_AREA": 3, "UNKNOWN": 4}
    representative = min(
        members,
        key=lambda member: (
            -_metadata_score(member),
            role_rank[member.geometry_role],
            str(member.id),
        ),
    )
    sites = sorted(
        (member for member in members if member.geometry_role == "FACILITY_SITE"),
        key=lambda member: (-_metadata_score(member), str(member.id)),
    )
    buildings = sorted(
        (member for member in members if member.geometry_role == "BUILDING"),
        key=lambda member: (-_metadata_score(member), str(member.id)),
    )
    points = sorted(
        (member for member in members if member.geometry_role == "POINT"),
        key=lambda member: (-_metadata_score(member), str(member.id)),
    )
    display = (sites or buildings or [representative])[0]
    analysis = (sites or points or [representative])[0]
    return representative.id, display.id, analysis.id


def _build_groups(pairs: list[CandidatePair]) -> tuple[list[PlannedGroup], int]:
    strong = [pair for pair in pairs if pair.strong]
    adjacency: dict[UUID, set[UUID]] = defaultdict(set)
    objects: dict[UUID, CandidateObject] = {}
    edge_pairs: dict[frozenset[UUID], CandidatePair] = {}
    for pair in strong:
        adjacency[pair.point.id].add(pair.area.id)
        adjacency[pair.area.id].add(pair.point.id)
        objects[pair.point.id] = pair.point
        objects[pair.area.id] = pair.area
        edge_pairs[frozenset((pair.point.id, pair.area.id))] = pair

    groups: list[PlannedGroup] = []
    conflicts = 0
    visited: set[UUID] = set()
    for start in sorted(adjacency, key=str):
        if start in visited:
            continue
        queue = deque([start])
        component: set[UUID] = set()
        while queue:
            current = queue.popleft()
            if current in visited:
                continue
            visited.add(current)
            component.add(current)
            queue.extend(adjacency[current] - visited)
        members = [objects[object_id] for object_id in component]
        component_edges = {
            frozenset((left, right))
            for left in component
            for right in adjacency[left]
        }
        categories = {edge_pairs[edge].category_key for edge in component_edges}
        point_count = sum(member.geometry_role == "POINT" for member in members)
        area_role_counts = Counter(
            member.geometry_role for member in members if member.geometry_role != "POINT"
        )
        if (
            len(categories) != 1
            or point_count > 1
            or any(count > 1 for count in area_role_counts.values())
        ):
            conflicts += 1
            continue
        member_methods: dict[UUID, set[str]] = defaultdict(set)
        all_methods: set[str] = set()
        for edge in component_edges:
            left, right = tuple(edge)
            methods = edge_pairs[edge].methods
            member_methods[left].update(methods)
            member_methods[right].update(methods)
            all_methods.update(methods)
        representative, display, analysis = _role_members(members)
        groups.append(
            PlannedGroup(
                category_key=next(iter(categories)),
                members=tuple(
                    PlannedMember(objects[object_id], tuple(sorted(member_methods[object_id])))
                    for object_id in sorted(component, key=str)
                ),
                representative_object_id=representative,
                display_object_id=display,
                analysis_object_id=analysis,
                methods=tuple(sorted(all_methods)),
            )
        )

    ownership: dict[UUID, list[int]] = defaultdict(list)
    for index, group in enumerate(groups):
        for member in group.members:
            ownership[member.object.id].append(index)
    conflicted_indexes = {
        index for indexes in ownership.values() if len(indexes) > 1 for index in indexes
    }
    if conflicted_indexes:
        conflicts += len(conflicted_indexes)
        groups = [group for index, group in enumerate(groups) if index not in conflicted_indexes]
    return groups, conflicts


def dry_run_facilities(*, engine: Engine | None = None) -> FacilityDryRunReport:
    database = engine or get_engine()
    with database.connect() as connection:
        pairs = _load_candidate_pairs(connection)
    groups, conflicts = _build_groups(pairs)
    methods = Counter(method for pair in pairs if pair.strong for method in pair.methods)
    return FacilityDryRunReport(
        candidate_pairs=len(pairs),
        strong_pairs=sum(pair.strong for pair in pairs),
        ambiguous_pairs=sum(not pair.strong for pair in pairs),
        conflicts=conflicts,
        multi_member_groups=sum(len(group.members) > 1 for group in groups),
        groups=tuple(groups),
        strong_by_method=dict(sorted(methods.items())),
        explicit_site_links=methods["explicit_site_relation"],
    )


def _entity_id(group: PlannedGroup) -> UUID:
    member_ids = ",".join(sorted(str(member.object.id) for member in group.members))
    return uuid5(FACILITY_NAMESPACE, f"{group.category_key}|{member_ids}")


def _entity_payload(group: PlannedGroup) -> dict[str, Any]:
    return {
        "methods": list(group.methods),
        "members": [
            {
                "canonical_object_id": str(member.object.id),
                "source": f"{member.object.source_type}/{member.object.source_object_id}",
                "geometry_role": member.object.geometry_role,
                "methods": list(member.methods),
            }
            for member in group.members
        ],
    }


def _existing_entity_ids(connection: Connection, group: PlannedGroup) -> set[UUID]:
    return set(
        connection.execute(
            text(
                """
                SELECT DISTINCT facility_entity_id
                FROM domain.facility_entity_members
                WHERE canonical_object_id=ANY(:member_ids)
                """
            ),
            {"member_ids": [member.object.id for member in group.members]},
        ).scalars()
    )


def _upsert_group(
    connection: Connection, entity_id: UUID, group: PlannedGroup
) -> tuple[bool, bool]:
    existed = bool(
        connection.scalar(
            text("SELECT count(*) FROM domain.facility_entities WHERE id=:id"),
            {"id": entity_id},
        )
    )
    evidence = json.dumps(_entity_payload(group), ensure_ascii=False, sort_keys=True)
    method = "+".join(group.methods)
    result = connection.execute(
        text(
            """
            INSERT INTO domain.facility_entities
              (id,category_key,representative_object_id,display_object_id,
               analysis_object_id,lifecycle_status,link_method,evidence)
            VALUES
              (:id,:category_key,:representative,:display,:analysis,'active',
               :link_method,CAST(:evidence AS jsonb))
            ON CONFLICT (id) DO UPDATE SET
              category_key=EXCLUDED.category_key,
              representative_object_id=EXCLUDED.representative_object_id,
              display_object_id=EXCLUDED.display_object_id,
              analysis_object_id=EXCLUDED.analysis_object_id,
              lifecycle_status='active',
              link_method=EXCLUDED.link_method,
              evidence=EXCLUDED.evidence,
              updated_at=now()
            WHERE (facility_entities.category_key,
                   facility_entities.representative_object_id,
                   facility_entities.display_object_id,
                   facility_entities.analysis_object_id,
                   facility_entities.lifecycle_status,
                   facility_entities.link_method,
                   facility_entities.evidence)
              IS DISTINCT FROM
                  (EXCLUDED.category_key,
                   EXCLUDED.representative_object_id,
                   EXCLUDED.display_object_id,
                   EXCLUDED.analysis_object_id,
                   'active',EXCLUDED.link_method,EXCLUDED.evidence)
            """
        ),
        {
            "id": entity_id,
            "category_key": group.category_key,
            "representative": group.representative_object_id,
            "display": group.display_object_id,
            "analysis": group.analysis_object_id,
            "link_method": method,
            "evidence": evidence,
        },
    )
    changed = bool(result.rowcount)
    member_ids = [member.object.id for member in group.members]
    connection.execute(
        text(
            """
            UPDATE domain.facility_entity_members
            SET lifecycle_status='inactive',updated_at=now()
            WHERE facility_entity_id=:entity_id
              AND lifecycle_status='active'
              AND NOT (canonical_object_id=ANY(:member_ids))
            """
        ),
        {"entity_id": entity_id, "member_ids": member_ids},
    )
    for member in group.members:
        member_evidence = json.dumps(
            {"methods": list(member.methods)}, ensure_ascii=False, sort_keys=True
        )
        connection.execute(
            text(
                """
                INSERT INTO domain.facility_entity_members
                  (facility_entity_id,canonical_object_id,geometry_role,lifecycle_status,
                   link_method,evidence)
                VALUES
                  (:entity_id,:object_id,:geometry_role,'active',:link_method,
                   CAST(:evidence AS jsonb))
                ON CONFLICT (facility_entity_id,canonical_object_id) DO UPDATE SET
                  geometry_role=EXCLUDED.geometry_role,
                  lifecycle_status='active',
                  link_method=EXCLUDED.link_method,
                  evidence=EXCLUDED.evidence,
                  updated_at=now()
                WHERE (facility_entity_members.geometry_role,
                       facility_entity_members.lifecycle_status,
                       facility_entity_members.link_method,
                       facility_entity_members.evidence)
                  IS DISTINCT FROM
                      (EXCLUDED.geometry_role,'active',EXCLUDED.link_method,EXCLUDED.evidence)
                """
            ),
            {
                "entity_id": entity_id,
                "object_id": member.object.id,
                "geometry_role": member.object.geometry_role,
                "link_method": "+".join(member.methods),
                "evidence": member_evidence,
            },
        )
    return not existed, changed


def _reconcile_unplanned_entity(connection: Connection, entity_id: UUID) -> bool:
    rows = connection.execute(
        text(
            """
            SELECT member.canonical_object_id,
                   member.geometry_role,
                   object.lifecycle_status='active'
                     AND category.lifecycle_status='active' AS usable
            FROM domain.facility_entity_members AS member
            JOIN domain.facility_entities AS entity ON entity.id=member.facility_entity_id
            JOIN catalog.objects AS object ON object.id=member.canonical_object_id
            LEFT JOIN catalog.object_categories AS category
              ON category.object_id=member.canonical_object_id
             AND category.category_key=entity.category_key
            WHERE member.facility_entity_id=:entity_id
            ORDER BY member.canonical_object_id
            """
        ),
        {"entity_id": entity_id},
    ).all()
    usable = [row for row in rows if bool(row.usable)]
    if len(usable) == 1:
        fallback = usable[0].canonical_object_id
        connection.execute(
            text(
                """
                UPDATE domain.facility_entity_members
                SET lifecycle_status=CASE WHEN canonical_object_id=:fallback
                                          THEN 'active' ELSE 'inactive' END,
                    updated_at=CASE
                      WHEN lifecycle_status<>CASE WHEN canonical_object_id=:fallback
                                                 THEN 'active' ELSE 'inactive' END
                      THEN now() ELSE updated_at END
                WHERE facility_entity_id=:entity_id
                """
            ),
            {"entity_id": entity_id, "fallback": fallback},
        )
        result = connection.execute(
            text(
                """
                UPDATE domain.facility_entities
                SET representative_object_id=:fallback,
                    display_object_id=:fallback,
                    analysis_object_id=:fallback,
                    lifecycle_status='active',
                    link_method='inactive_member_fallback',
                    updated_at=now()
                WHERE id=:entity_id
                  AND (representative_object_id,display_object_id,analysis_object_id,
                       lifecycle_status,link_method)
                    IS DISTINCT FROM (:fallback,:fallback,:fallback,'active',
                                      'inactive_member_fallback')
                """
            ),
            {"entity_id": entity_id, "fallback": fallback},
        )
        return bool(result.rowcount)
    connection.execute(
        text(
            """
            UPDATE domain.facility_entity_members
            SET lifecycle_status='inactive',updated_at=now()
            WHERE facility_entity_id=:entity_id AND lifecycle_status='active'
            """
        ),
        {"entity_id": entity_id},
    )
    result = connection.execute(
        text(
            """
            UPDATE domain.facility_entities
            SET representative_object_id=NULL,display_object_id=NULL,analysis_object_id=NULL,
                lifecycle_status='inactive',link_method='no_current_strong_group',updated_at=now()
            WHERE id=:entity_id
              AND (lifecycle_status<>'inactive' OR representative_object_id IS NOT NULL
                   OR display_object_id IS NOT NULL OR analysis_object_id IS NOT NULL
                   OR link_method<>'no_current_strong_group')
            """
        ),
        {"entity_id": entity_id},
    )
    return bool(result.rowcount)


def refresh_facilities(*, engine: Engine | None = None) -> FacilityRefreshResult:
    database = engine or get_engine()
    with database.begin() as connection:
        pairs = _load_candidate_pairs(connection)
        groups, conflicts = _build_groups(pairs)
        resolved: list[tuple[UUID, PlannedGroup]] = []
        for group in groups:
            existing = _existing_entity_ids(connection, group)
            if len(existing) > 1:
                conflicts += 1
                continue
            resolved.append((next(iter(existing)) if existing else _entity_id(group), group))

        planned_ids = {entity_id for entity_id, _ in resolved}
        all_existing: set[UUID] = set(
            connection.execute(text("SELECT id FROM domain.facility_entities")).scalars()
        )
        created = 0
        changed = 0
        unchanged = 0
        for entity_id, group in resolved:
            was_created, was_changed = _upsert_group(connection, entity_id, group)
            created += was_created
            changed += was_changed and not was_created
            unchanged += not was_changed
        for entity_id in sorted(all_existing - planned_ids, key=str):
            changed += _reconcile_unplanned_entity(connection, entity_id)

        counts = connection.execute(
            text(
                """
                SELECT
                  count(*) FILTER (WHERE entity.lifecycle_status='active') AS entities,
                  count(*) FILTER (
                    WHERE entity.lifecycle_status='active' AND active_members.count>1
                  ) AS multi_member,
                  coalesce(sum(active_members.count) FILTER (
                    WHERE entity.lifecycle_status='active'
                  ),0) AS members
                FROM domain.facility_entities AS entity
                CROSS JOIN LATERAL (
                  SELECT count(*)
                  FROM domain.facility_entity_members AS member
                  WHERE member.facility_entity_id=entity.id
                    AND member.lifecycle_status='active'
                ) AS active_members
                """
            )
        ).one()
    return FacilityRefreshResult(
        candidate_pairs=len(pairs),
        strong_pairs=sum(pair.strong for pair in pairs),
        ambiguous_pairs=sum(not pair.strong for pair in pairs),
        conflicts=conflicts,
        active_entities=int(counts.entities),
        multi_member_entities=int(counts.multi_member),
        active_members=int(counts.members),
        created_entities=created,
        changed_entities=changed,
        unchanged_entities=unchanged,
    )


def report_json(report: FacilityDryRunReport | FacilityRefreshResult) -> str:
    return json.dumps(asdict(report), ensure_ascii=False, indent=2, default=str)
