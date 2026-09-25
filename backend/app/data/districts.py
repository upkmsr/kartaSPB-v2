import argparse
import json
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import Connection, Engine, text

from app.db.session import get_engine

DISTRICT_SOURCE_NAME = "osm_geofabrik_northwestern_federal_district"
DISTRICT_SOURCE_VERSION = "20260921T231045Z"
DISTRICT_PARENT_RELATION_ID = 337422


@dataclass(frozen=True)
class DistrictDefinition:
    id: UUID
    relation_id: int
    name: str
    slug: str
    display_order: int


DISTRICT_DEFINITIONS = (
    DistrictDefinition(
        UUID("01992d00-0fe0-54cd-99db-b35bbb7f34e2"),
        1114193,
        "Адмиралтейский",
        "admiralteysky",
        1,
    ),
    DistrictDefinition(
        UUID("5d5648bf-d176-55ba-a665-fe4b2677396c"),
        1114252,
        "Василеостровский",
        "vasileostrovsky",
        2,
    ),
    DistrictDefinition(
        UUID("a04abf32-d853-54fc-b8e1-389d5e4483b9"), 1114354, "Выборгский", "vyborgsky", 3
    ),
    DistrictDefinition(
        UUID("07e4bea3-c750-5619-9f2d-58f46a2fa829"), 1114806, "Калининский", "kalininsky", 4
    ),
    DistrictDefinition(
        UUID("a5b24b7e-49df-5cbc-9e5b-f5bc6396ee04"), 1114809, "Кировский", "kirovsky", 5
    ),
    DistrictDefinition(
        UUID("3cd0f3bc-ef1a-5de3-bfa4-2c8c50e253ce"), 337424, "Колпинский", "kolpinsky", 6
    ),
    DistrictDefinition(
        UUID("eb31713a-e792-5f5d-a963-7799467d8769"),
        1114895,
        "Красногвардейский",
        "krasnogvardeysky",
        7,
    ),
    DistrictDefinition(
        UUID("b7faed37-7335-545b-a03c-dfebedd2f92c"),
        363103,
        "Красносельский",
        "krasnoselsky",
        8,
    ),
    DistrictDefinition(
        UUID("b0d2b52a-0f4a-519a-ae6c-138d4d4b2af1"),
        1115082,
        "Кронштадтский",
        "kronshtadtsky",
        9,
    ),
    DistrictDefinition(
        UUID("8bcd2545-b82a-58ba-b9c9-a1a91590dae0"), 1115366, "Курортный", "kurortny", 10
    ),
    DistrictDefinition(
        UUID("d185d384-8169-58fd-b259-11ebb0a17ef1"), 338636, "Московский", "moskovsky", 11
    ),
    DistrictDefinition(
        UUID("de099430-1d6d-5168-a1c6-89d90fe31e28"), 368287, "Невский", "nevsky", 12
    ),
    DistrictDefinition(
        UUID("564bf87c-ee21-537d-a50b-7e4887a0728b"),
        1114905,
        "Петроградский",
        "petrogradsky",
        13,
    ),
    DistrictDefinition(
        UUID("8d97794e-0b99-5c7c-8a13-6a719513df03"),
        367375,
        "Петродворцовый",
        "petrodvortsovy",
        14,
    ),
    DistrictDefinition(
        UUID("230bcc6e-fb6a-5172-afe6-81f0736fb77b"), 1115367, "Приморский", "primorsky", 15
    ),
    DistrictDefinition(
        UUID("2190fde8-fb1d-5d58-81f8-143e0b897efc"), 338635, "Пушкинский", "pushkinsky", 16
    ),
    DistrictDefinition(
        UUID("294eacf9-9cdd-5eaa-af19-120b9403660f"), 369514, "Фрунзенский", "frunzensky", 17
    ),
    DistrictDefinition(
        UUID("161ba369-c548-5569-9cc2-679522090220"), 1114902, "Центральный", "centralny", 18
    ),
)


class DistrictRegistryError(RuntimeError):
    pass


class UnknownDistrictsError(ValueError):
    def __init__(self, unknown: list[UUID], disabled: list[UUID]) -> None:
        self.unknown = unknown
        self.disabled = disabled
        super().__init__("One or more districts are unknown or disabled")


@dataclass(frozen=True)
class DistrictData:
    id: UUID
    name: str
    slug: str
    bbox: tuple[float, float, float, float]
    display_order: int


@dataclass(frozen=True)
class DistrictBootstrapResult:
    source_id: int
    rows: int
    changed: int


def _resolve_source_id(connection: Connection, source_id: int | None) -> int:
    if source_id is not None:
        exists = connection.scalar(
            text("SELECT count(*) FROM meta.dataset_sources WHERE id=:source_id"),
            {"source_id": source_id},
        )
        if exists != 1:
            raise DistrictRegistryError(f"OSM source {source_id} does not exist")
        return source_id
    rows: list[int] = list(
        connection.execute(
            text(
                "SELECT id FROM meta.dataset_sources "
                "WHERE name=:name AND version=:version"
            ),
            {"name": DISTRICT_SOURCE_NAME, "version": DISTRICT_SOURCE_VERSION},
        )
        .scalars()
        .all()
    )
    if len(rows) != 1:
        raise DistrictRegistryError(
            "Expected exactly one registered district source "
            f"{DISTRICT_SOURCE_NAME}@{DISTRICT_SOURCE_VERSION}, found {len(rows)}"
        )
    return int(rows[0])


def _accepted_bindings(connection: Connection, source_id: int) -> dict[int, UUID]:
    parent = connection.execute(
        text(
            "SELECT tags->>'boundary' AS boundary, tags->>'admin_level' AS admin_level, "
            "tags->>'wikidata' AS wikidata FROM staging.osm_relations "
            "WHERE source_id=:source_id AND osm_id=:parent_id"
        ),
        {"source_id": source_id, "parent_id": DISTRICT_PARENT_RELATION_ID},
    ).one_or_none()
    if parent is None or tuple(parent) != ("administrative", "4", "Q656"):
        raise DistrictRegistryError("Parent relation r337422 is missing or has unexpected tags")

    rows = connection.execute(
        text(
            """
            SELECT member.member_id AS relation_id,
                   child.tags->>'boundary' AS boundary,
                   child.tags->>'admin_level' AS admin_level,
                   binding.object_id,
                   binding.source_status,
                   object.lifecycle_status,
                   object.geom IS NOT NULL AS has_geometry,
                   coalesce(ST_IsEmpty(object.geom), true) AS is_empty,
                   coalesce(ST_IsValid(object.geom), false) AS is_valid,
                   ST_SRID(object.geom) AS srid
            FROM staging.osm_relation_members AS member
            LEFT JOIN staging.osm_relations AS child
              ON child.source_id=member.source_id AND child.osm_id=member.member_id
            LEFT JOIN catalog.object_sources AS binding
              ON binding.source_id=member.source_id
             AND binding.source_object_type='relation'
             AND binding.source_object_id=member.member_id::text
            LEFT JOIN catalog.objects AS object ON object.id=binding.object_id
            WHERE member.source_id=:source_id
              AND member.relation_id=:parent_id
              AND member.member_type='relation'
              AND member.role='subarea'
            ORDER BY member.sequence
            """
        ),
        {"source_id": source_id, "parent_id": DISTRICT_PARENT_RELATION_ID},
    ).all()
    expected_ids = {item.relation_id for item in DISTRICT_DEFINITIONS}
    actual_ids = {int(row.relation_id) for row in rows}
    if len(rows) != 18 or actual_ids != expected_ids:
        raise DistrictRegistryError(
            "Parent r337422 must contain the accepted 18 district subareas; "
            f"found {sorted(actual_ids)}"
        )
    bindings: dict[int, UUID] = {}
    for row in rows:
        relation_id = int(row.relation_id)
        checks = (
            row.boundary == "administrative",
            row.admin_level == "5",
            row.object_id is not None,
            row.source_status == "present",
            row.lifecycle_status == "active",
            bool(row.has_geometry),
            not bool(row.is_empty),
            bool(row.is_valid),
            row.srid == 4326,
        )
        if not all(checks):
            raise DistrictRegistryError(
                f"District relation r{relation_id} has an invalid source/canonical binding"
            )
        bindings[relation_id] = row.object_id
    if len(set(bindings.values())) != 18:
        raise DistrictRegistryError("District canonical bindings must be unique")
    return bindings


def bootstrap_districts(
    *, engine: Engine | None = None, source_id: int | None = None
) -> DistrictBootstrapResult:
    database = engine or get_engine()
    with database.begin() as connection:
        resolved_source_id = _resolve_source_id(connection, source_id)
        bindings = _accepted_bindings(connection, resolved_source_id)
        expected_domain_ids = {item.id for item in DISTRICT_DEFINITIONS}
        existing_ids: set[UUID] = set(
            connection.execute(text("SELECT id FROM domain.districts")).scalars()
        )
        unexpected_ids = existing_ids - expected_domain_ids
        if unexpected_ids:
            raise DistrictRegistryError(
                "District registry contains unexpected domain IDs: "
                f"{sorted(map(str, unexpected_ids))}"
            )
        payload = [
            {
                "id": str(item.id),
                "canonical_object_id": str(bindings[item.relation_id]),
                "name": item.name,
                "slug": item.slug,
                "display_order": item.display_order,
            }
            for item in DISTRICT_DEFINITIONS
        ]
        result = connection.execute(
            text(
                """
                INSERT INTO domain.districts
                  (id,canonical_object_id,name,slug,display_order,enabled)
                SELECT item.id,item.canonical_object_id,item.name,item.slug,
                       item.display_order,true
                FROM jsonb_to_recordset(CAST(:payload AS jsonb)) AS item(
                  id uuid,canonical_object_id uuid,name text,slug text,display_order smallint)
                ON CONFLICT (id) DO UPDATE SET
                  canonical_object_id=excluded.canonical_object_id,
                  name=excluded.name,
                  slug=excluded.slug,
                  display_order=excluded.display_order,
                  enabled=true,
                  updated_at=now()
                WHERE (districts.canonical_object_id,districts.name,districts.slug,
                       districts.display_order,districts.enabled)
                  IS DISTINCT FROM
                      (excluded.canonical_object_id,excluded.name,excluded.slug,
                       excluded.display_order,excluded.enabled)
                """
            ),
            {"payload": json.dumps(payload)},
        )
        rows = int(connection.scalar(text("SELECT count(*) FROM domain.districts")) or 0)
        enabled = int(
            connection.scalar(text("SELECT count(*) FROM domain.districts WHERE enabled")) or 0
        )
        if rows != 18 or enabled != 18:
            raise DistrictRegistryError(
                f"District registry must contain exactly 18 enabled rows; found {rows}/{enabled}"
            )
        return DistrictBootstrapResult(resolved_source_id, rows, result.rowcount)


def validate_district_selection(connection: Connection, district_ids: tuple[UUID, ...]) -> None:
    if not district_ids:
        return
    rows = connection.execute(
        text("SELECT id,enabled FROM domain.districts WHERE id=ANY(:district_ids)"),
        {"district_ids": list(district_ids)},
    ).all()
    found = {row.id: bool(row.enabled) for row in rows}
    unknown = sorted((item for item in district_ids if item not in found), key=str)
    disabled = sorted((item for item in district_ids if item in found and not found[item]), key=str)
    if unknown or disabled:
        raise UnknownDistrictsError(unknown, disabled)


class DistrictCatalogService:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def districts(self) -> list[DistrictData]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                text(
                    """
                    SELECT district.id,district.name,district.slug,district.display_order,
                           object.lifecycle_status,
                           object.geom IS NOT NULL AS has_geometry,
                           coalesce(ST_IsEmpty(object.geom),true) AS is_empty,
                           coalesce(ST_IsValid(object.geom),false) AS is_valid,
                           ST_SRID(object.geom) AS srid,
                           ST_XMin(Box3D(object.geom)) AS min_lon,
                           ST_YMin(Box3D(object.geom)) AS min_lat,
                           ST_XMax(Box3D(object.geom)) AS max_lon,
                           ST_YMax(Box3D(object.geom)) AS max_lat
                    FROM domain.districts AS district
                    JOIN catalog.objects AS object ON object.id=district.canonical_object_id
                    WHERE district.enabled
                    ORDER BY district.display_order
                    """
                )
            ).all()
        if len(rows) != 18:
            raise DistrictRegistryError(f"Expected 18 enabled districts, found {len(rows)}")
        result: list[DistrictData] = []
        for row in rows:
            if not (
                row.lifecycle_status == "active"
                and bool(row.has_geometry)
                and not bool(row.is_empty)
                and bool(row.is_valid)
                and row.srid == 4326
            ):
                raise DistrictRegistryError(f"District {row.id} has invalid canonical geometry")
            result.append(
                DistrictData(
                    id=row.id,
                    name=str(row.name),
                    slug=str(row.slug),
                    bbox=(
                        float(row.min_lon),
                        float(row.min_lat),
                        float(row.max_lon),
                        float(row.max_lat),
                    ),
                    display_order=int(row.display_order),
                )
            )
        return result


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Bootstrap the SPb district domain registry")
    parser.add_argument("command", choices=["bootstrap"])
    parser.add_argument("--source-id", type=int)
    args = parser.parse_args(argv)
    result = bootstrap_districts(source_id=args.source_id)
    print(
        json.dumps(
            {"source_id": result.source_id, "rows": result.rows, "changed": result.changed},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
