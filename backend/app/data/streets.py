from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from typing import Any
from uuid import UUID, uuid5

from sqlalchemy import Connection, Engine, text

from app.db.session import get_engine

STREET_NAMESPACE = UUID("1a627e46-1e82-4d86-a3cf-836a52d66772")
MAX_COMPONENT_GAP_METERS = 30
LINK_METHOD = "exact_name_spatial_30m"


@dataclass(frozen=True)
class StreetCandidate:
    id: UUID
    name: str
    search_name: str
    spatial_component: int
    source_type: str
    source_object_id: str
    tags: dict[str, Any]
    relation_keys: tuple[str, ...]


@dataclass(frozen=True)
class PlannedStreet:
    search_name: str
    display_name: str
    members: tuple[StreetCandidate, ...]
    relation_keys: tuple[str, ...]
    link_method: str


@dataclass(frozen=True)
class StreetDryRunReport:
    eligible_members: int
    street_entities: int
    multi_member_entities: int
    largest_entity_members: int
    separated_same_name_cases: int
    relation_supported_entities: int
    groups: tuple[PlannedStreet, ...]


@dataclass(frozen=True)
class StreetRefreshResult:
    eligible_members: int
    active_entities: int
    multi_member_entities: int
    active_members: int
    largest_entity_members: int
    separated_same_name_cases: int
    relation_supported_entities: int
    created_entities: int
    changed_entities: int
    unchanged_entities: int


RELATION_NAME_SQL = (
    "btrim(regexp_replace(replace(lower(translate(normalize(relation.tags->>'name', NFKC), "
    "'Ёё', 'Ее')), chr(160), ' '), '[[:space:]]+', ' ', 'g'))"
)

CANDIDATE_SQL = text(
    f"""
    WITH eligible AS MATERIALIZED (
        SELECT object.id,
               object.name,
               object.search_name_v2 AS search_name,
               object.geom,
               binding.source_id,
               binding.source_object_type,
               binding.source_object_id,
               coalesce(way.tags,'{{}}'::jsonb) AS tags
        FROM catalog.objects AS object
        JOIN catalog.object_categories AS category
          ON category.object_id=object.id
         AND category.category_key='transport.road'
         AND category.lifecycle_status='active'
        JOIN catalog.object_sources AS binding
          ON binding.object_id=object.id
         AND binding.source_status='present'
        LEFT JOIN staging.osm_ways AS way
          ON binding.source_object_type='way'
         AND way.source_id=binding.source_id
         AND way.osm_id=binding.source_object_id::bigint
        WHERE object.lifecycle_status='active'
          AND GeometryType(object.geom) IN ('LINESTRING','MULTILINESTRING')
          AND nullif(object.search_name_v2,'') IS NOT NULL
    ), clustered AS MATERIALIZED (
        SELECT eligible.*,
               ST_ClusterDBSCAN(
                   ST_Transform(eligible.geom,32636),
                   eps => :distance_meters,
                   minpoints => 1
               ) OVER (
                   PARTITION BY eligible.search_name
                   ORDER BY eligible.id
               ) AS spatial_component
        FROM eligible
    )
    SELECT candidate.id,
           candidate.name,
           candidate.search_name,
           candidate.spatial_component,
           candidate.source_object_type,
           candidate.source_object_id,
           candidate.tags,
           coalesce(relations.relation_keys,ARRAY[]::text[]) AS relation_keys
    FROM clustered AS candidate
    LEFT JOIN LATERAL (
        SELECT array_agg(
                   DISTINCT concat(
                       member.source_id,':',relation.tags->>'type',':',member.relation_id
                   )
                   ORDER BY concat(
                       member.source_id,':',relation.tags->>'type',':',member.relation_id
                   )
               ) AS relation_keys
        FROM staging.osm_relation_members AS member
        JOIN staging.osm_relations AS relation
          ON relation.source_id=member.source_id
         AND relation.osm_id=member.relation_id
        WHERE candidate.source_object_type='way'
          AND member.source_id=candidate.source_id
          AND member.member_type='way'
          AND member.member_id=candidate.source_object_id::bigint
          AND (
              (
                  relation.tags->>'type' IN ('street','associatedStreet')
                  AND {RELATION_NAME_SQL}=candidate.search_name
              )
              OR relation.tags->>'type'='dual_carriageway'
          )
    ) AS relations ON true
    ORDER BY candidate.search_name,candidate.spatial_component,candidate.id
    """
)


def _display_text(value: str) -> str:
    return value.strip()


def _load_candidates(connection: Connection) -> list[StreetCandidate]:
    rows = connection.execute(
        CANDIDATE_SQL, {"distance_meters": MAX_COMPONENT_GAP_METERS}
    ).all()
    return [
        StreetCandidate(
            id=row.id,
            name=_display_text(str(row.name)),
            search_name=str(row.search_name),
            spatial_component=int(row.spatial_component),
            source_type=str(row.source_object_type),
            source_object_id=str(row.source_object_id),
            tags=dict(row.tags or {}),
            relation_keys=tuple(str(value) for value in row.relation_keys),
        )
        for row in rows
    ]


class _DisjointSet:
    def __init__(self, keys: set[tuple[str, int]]) -> None:
        self.parent = {key: key for key in keys}

    def find(self, key: tuple[str, int]) -> tuple[str, int]:
        parent = self.parent[key]
        if parent != key:
            self.parent[key] = self.find(parent)
        return self.parent[key]

    def union(self, left: tuple[str, int], right: tuple[str, int]) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root == right_root:
            return
        first, second = sorted((left_root, right_root))
        self.parent[second] = first


def _build_groups(candidates: list[StreetCandidate]) -> list[PlannedStreet]:
    component_keys = {
        (candidate.search_name, candidate.spatial_component) for candidate in candidates
    }
    disjoint = _DisjointSet(component_keys)
    relation_components: dict[tuple[str, str], set[tuple[str, int]]] = defaultdict(set)
    for candidate in candidates:
        component_key = (candidate.search_name, candidate.spatial_component)
        for relation_key in candidate.relation_keys:
            relation_components[(candidate.search_name, relation_key)].add(component_key)
    for keys in relation_components.values():
        ordered = sorted(keys)
        for key in ordered[1:]:
            disjoint.union(ordered[0], key)

    members_by_root: dict[tuple[str, int], list[StreetCandidate]] = defaultdict(list)
    for candidate in candidates:
        key = (candidate.search_name, candidate.spatial_component)
        members_by_root[disjoint.find(key)].append(candidate)

    groups: list[PlannedStreet] = []
    for members in members_by_root.values():
        ordered_members = tuple(sorted(members, key=lambda member: str(member.id)))
        name_counts = Counter(member.name for member in ordered_members)
        display_name = min(
            name_counts,
            key=lambda name: (-name_counts[name], len(name), name.casefold(), name),
        )
        relation_keys = tuple(
            sorted({key for member in ordered_members for key in member.relation_keys})
        )
        initial_components = {
            (member.search_name, member.spatial_component) for member in ordered_members
        }
        relation_supported = bool(relation_keys and len(initial_components) > 1)
        groups.append(
            PlannedStreet(
                search_name=ordered_members[0].search_name,
                display_name=display_name,
                members=ordered_members,
                relation_keys=relation_keys,
                link_method=(
                    f"{LINK_METHOD}+explicit_osm_relation"
                    if relation_supported
                    else LINK_METHOD
                ),
            )
        )
    return sorted(
        groups,
        key=lambda group: (
            group.search_name,
            str(group.members[0].id),
        ),
    )


def _report(groups: list[PlannedStreet], eligible_members: int) -> StreetDryRunReport:
    name_counts = Counter(group.search_name for group in groups)
    return StreetDryRunReport(
        eligible_members=eligible_members,
        street_entities=len(groups),
        multi_member_entities=sum(len(group.members) > 1 for group in groups),
        largest_entity_members=max((len(group.members) for group in groups), default=0),
        separated_same_name_cases=sum(count > 1 for count in name_counts.values()),
        relation_supported_entities=sum(
            group.link_method.endswith("+explicit_osm_relation") for group in groups
        ),
        groups=tuple(groups),
    )


def dry_run_streets(*, engine: Engine | None = None) -> StreetDryRunReport:
    database = engine or get_engine()
    with database.connect() as connection:
        candidates = _load_candidates(connection)
    return _report(_build_groups(candidates), len(candidates))


def _new_entity_id(group: PlannedStreet) -> UUID:
    member_ids = ",".join(str(member.id) for member in group.members)
    return uuid5(STREET_NAMESPACE, f"{group.search_name}|{member_ids}")


def _resolve_entity_ids(
    connection: Connection, groups: list[PlannedStreet]
) -> list[tuple[UUID, PlannedStreet]]:
    existing_by_member: dict[UUID, UUID] = {
        row.canonical_object_id: row.street_entity_id
        for row in connection.execute(
            text(
                "SELECT canonical_object_id,street_entity_id "
                "FROM domain.street_entity_members WHERE lifecycle_status='active'"
            )
        )
    }
    tentative: list[tuple[UUID, PlannedStreet, int]] = []
    for group in groups:
        anchors = Counter(
            existing_by_member[member.id]
            for member in group.members
            if member.id in existing_by_member
        )
        if anchors:
            anchor, overlap = min(
                anchors.items(), key=lambda item: (-item[1], str(item[0]))
            )
            tentative.append((anchor, group, overlap))
        else:
            tentative.append((_new_entity_id(group), group, 0))

    by_id: dict[UUID, list[tuple[PlannedStreet, int]]] = defaultdict(list)
    for entity_id, group, overlap in tentative:
        by_id[entity_id].append((group, overlap))
    resolved: list[tuple[UUID, PlannedStreet]] = []
    used: set[UUID] = set()
    for entity_id in sorted(by_id, key=str):
        choices = sorted(
            by_id[entity_id],
            key=lambda item: (-item[1], item[0].search_name, str(item[0].members[0].id)),
        )
        for index, (group, _) in enumerate(choices):
            selected = entity_id if index == 0 else _new_entity_id(group)
            while selected in used:
                selected = uuid5(STREET_NAMESPACE, f"{selected}|split")
            used.add(selected)
            resolved.append((selected, group))
    return sorted(resolved, key=lambda item: str(item[0]))


def _entity_evidence(group: PlannedStreet) -> dict[str, Any]:
    return {
        "normalized_name": group.search_name,
        "max_component_gap_meters": MAX_COMPONENT_GAP_METERS,
        "member_count": len(group.members),
        "osm_relations": list(group.relation_keys),
    }


def _member_evidence(member: StreetCandidate) -> dict[str, Any]:
    return {
        "source": f"{member.source_type}/{member.source_object_id}",
        "normalized_name": member.search_name,
        "spatial_component": member.spatial_component,
        "osm_relations": list(member.relation_keys),
    }


def _existing_snapshot(connection: Connection) -> dict[UUID, tuple[Any, ...]]:
    rows = connection.execute(
        text(
            """
            SELECT entity.id,entity.display_name,entity.search_name,
                   entity.lifecycle_status,entity.link_method,entity.evidence,
                   coalesce(array_agg(
                     member.canonical_object_id ORDER BY member.canonical_object_id
                   )
                     FILTER (WHERE member.lifecycle_status='active'),ARRAY[]::uuid[]) AS members
            FROM domain.street_entities AS entity
            LEFT JOIN domain.street_entity_members AS member
              ON member.street_entity_id=entity.id
            GROUP BY entity.id
            """
        )
    ).all()
    return {
        row.id: (
            str(row.display_name),
            str(row.search_name),
            str(row.lifecycle_status),
            str(row.link_method),
            dict(row.evidence or {}),
            tuple(row.members),
        )
        for row in rows
    }


def _write_plan(
    connection: Connection, resolved: list[tuple[UUID, PlannedStreet]]
) -> None:
    connection.execute(
        text(
            """
            CREATE TEMP TABLE planned_street_entities (
              id uuid PRIMARY KEY,display_name text NOT NULL,search_name text NOT NULL,
              link_method text NOT NULL,evidence jsonb NOT NULL
            ) ON COMMIT DROP;
            CREATE TEMP TABLE planned_street_members (
              street_entity_id uuid NOT NULL,canonical_object_id uuid NOT NULL,
              link_method text NOT NULL,evidence jsonb NOT NULL,
              PRIMARY KEY (street_entity_id,canonical_object_id)
            ) ON COMMIT DROP
            """
        )
    )
    entity_rows = [
        {
            "id": entity_id,
            "display_name": group.display_name,
            "search_name": group.search_name,
            "link_method": group.link_method,
            "evidence": json.dumps(_entity_evidence(group), ensure_ascii=False),
        }
        for entity_id, group in resolved
    ]
    member_rows = [
        {
            "entity_id": entity_id,
            "object_id": member.id,
            "link_method": group.link_method,
            "evidence": json.dumps(_member_evidence(member), ensure_ascii=False),
        }
        for entity_id, group in resolved
        for member in group.members
    ]
    if entity_rows:
        connection.execute(
            text(
                "INSERT INTO planned_street_entities "
                "(id,display_name,search_name,link_method,evidence) VALUES "
                "(:id,:display_name,:search_name,:link_method,CAST(:evidence AS jsonb))"
            ),
            entity_rows,
        )
        connection.execute(
            text(
                "INSERT INTO planned_street_members "
                "(street_entity_id,canonical_object_id,link_method,evidence) VALUES "
                "(:entity_id,:object_id,:link_method,CAST(:evidence AS jsonb))"
            ),
            member_rows,
        )

    connection.execute(
        text(
            """
            UPDATE domain.street_entity_members AS member
            SET lifecycle_status='inactive',updated_at=now()
            WHERE member.lifecycle_status='active'
              AND NOT EXISTS (
                SELECT 1 FROM planned_street_members AS planned
                WHERE planned.street_entity_id=member.street_entity_id
                  AND planned.canonical_object_id=member.canonical_object_id
              )
            """
        )
    )
    connection.execute(
        text(
            """
            WITH assembled AS MATERIALIZED (
                SELECT planned.id,planned.display_name,planned.search_name,
                       planned.link_method,planned.evidence,
                       ST_Multi(ST_CollectionExtract(ST_Collect(object.geom),2)) AS geom
                FROM planned_street_entities AS planned
                JOIN planned_street_members AS member ON member.street_entity_id=planned.id
                JOIN catalog.objects AS object ON object.id=member.canonical_object_id
                GROUP BY planned.id,planned.display_name,planned.search_name,
                         planned.link_method,planned.evidence
            )
            INSERT INTO domain.street_entities
              (id,display_name,search_name,geom,representative_point,lifecycle_status,
               link_method,evidence)
            SELECT id,display_name,search_name,geom,ST_PointOnSurface(geom),'active',
                   link_method,evidence
            FROM assembled
            ON CONFLICT (id) DO UPDATE SET
              display_name=excluded.display_name,
              search_name=excluded.search_name,
              geom=excluded.geom,
              representative_point=excluded.representative_point,
              lifecycle_status='active',
              link_method=excluded.link_method,
              evidence=excluded.evidence,
              updated_at=now()
            WHERE street_entities.display_name IS DISTINCT FROM excluded.display_name
               OR street_entities.search_name IS DISTINCT FROM excluded.search_name
               OR NOT ST_Equals(street_entities.geom,excluded.geom)
               OR NOT ST_Equals(
                    street_entities.representative_point,excluded.representative_point
                  )
               OR street_entities.lifecycle_status<>'active'
               OR street_entities.link_method IS DISTINCT FROM excluded.link_method
               OR street_entities.evidence IS DISTINCT FROM excluded.evidence
            """
        )
    )
    connection.execute(
        text(
            """
            INSERT INTO domain.street_entity_members
              (street_entity_id,canonical_object_id,lifecycle_status,link_method,evidence)
            SELECT street_entity_id,canonical_object_id,'active',link_method,evidence
            FROM planned_street_members
            ON CONFLICT (street_entity_id,canonical_object_id) DO UPDATE SET
              lifecycle_status='active',link_method=excluded.link_method,
              evidence=excluded.evidence,updated_at=now()
            WHERE street_entity_members.lifecycle_status<>'active'
               OR street_entity_members.link_method IS DISTINCT FROM excluded.link_method
               OR street_entity_members.evidence IS DISTINCT FROM excluded.evidence
            """
        )
    )
    connection.execute(
        text(
            """
            UPDATE domain.street_entities AS entity
            SET lifecycle_status='inactive',updated_at=now()
            WHERE entity.lifecycle_status='active'
              AND NOT EXISTS (
                SELECT 1 FROM planned_street_entities AS planned WHERE planned.id=entity.id
              )
            """
        )
    )


def refresh_streets(*, engine: Engine | None = None) -> StreetRefreshResult:
    database = engine or get_engine()
    with database.begin() as connection:
        candidates = _load_candidates(connection)
        groups = _build_groups(candidates)
        report = _report(groups, len(candidates))
        resolved = _resolve_entity_ids(connection, groups)
        before = _existing_snapshot(connection)
        _write_plan(connection, resolved)
        created = 0
        changed = 0
        unchanged = 0
        for entity_id, group in resolved:
            expected = (
                group.display_name,
                group.search_name,
                "active",
                group.link_method,
                _entity_evidence(group),
                tuple(member.id for member in group.members),
            )
            if entity_id not in before:
                created += 1
            elif before[entity_id] == expected:
                unchanged += 1
            else:
                changed += 1
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
                  ),0) AS members,
                  coalesce(max(active_members.count) FILTER (
                    WHERE entity.lifecycle_status='active'
                  ),0) AS largest
                FROM domain.street_entities AS entity
                CROSS JOIN LATERAL (
                  SELECT count(*)
                  FROM domain.street_entity_members AS member
                  WHERE member.street_entity_id=entity.id
                    AND member.lifecycle_status='active'
                ) AS active_members
                """
            )
        ).one()
    return StreetRefreshResult(
        eligible_members=report.eligible_members,
        active_entities=int(counts.entities),
        multi_member_entities=int(counts.multi_member),
        active_members=int(counts.members),
        largest_entity_members=int(counts.largest),
        separated_same_name_cases=report.separated_same_name_cases,
        relation_supported_entities=report.relation_supported_entities,
        created_entities=created,
        changed_entities=changed,
        unchanged_entities=unchanged,
    )


def report_json(report: StreetDryRunReport | StreetRefreshResult) -> str:
    payload = asdict(report)
    payload.pop("groups", None)
    return json.dumps(payload, ensure_ascii=False, indent=2)
