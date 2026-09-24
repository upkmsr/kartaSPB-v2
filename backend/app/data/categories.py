# ruff: noqa: E501
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, text

from app.data.osm.config import project_root
from app.db.session import get_engine

OPERATORS = frozenset({"equals", "in", "exists", "not_equals", "not_in"})


@dataclass(frozen=True)
class Condition:
    tag: str
    operator: str
    value: str | tuple[str, ...] | None = None


@dataclass(frozen=True)
class Rule:
    id: str
    version: str
    category: str
    conditions: tuple[Condition, ...]
    source_object_types: frozenset[str] = frozenset()
    geometry_families: frozenset[str] = frozenset()
    object_kinds: frozenset[str] = frozenset()


@dataclass(frozen=True)
class CategoryRunResult:
    candidates: int
    canonical_created: int
    bindings_processed: int
    matches: int
    assignments: int
    duration_seconds: float


def _json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return value


def load_category_config(root: Path | None = None) -> tuple[list[dict[str, Any]], list[Rule]]:
    base = (root or project_root()) / "config/categories"
    taxonomy = _json(base / "taxonomy.json")
    source = _json(base / "sources/osm.json")
    raw_categories = taxonomy.get("categories")
    raw_rules = source.get("rules")
    if not isinstance(raw_categories, list) or not isinstance(raw_rules, list):
        raise ValueError("Category config must contain category and rule lists")
    categories = [item for item in raw_categories if isinstance(item, dict)]
    keys = {str(item.get("key")) for item in categories}
    if len(keys) != len(categories) or "None" in keys:
        raise ValueError("Category keys must be present and unique")
    rules: list[Rule] = []
    ids: set[str] = set()
    for raw in raw_rules:
        if not isinstance(raw, dict):
            raise ValueError("Each rule must be an object")
        rule_id = str(raw.get("id"))
        category = str(raw.get("category"))
        if rule_id in ids:
            raise ValueError(f"Duplicate rule id: {rule_id}")
        if category not in keys:
            raise ValueError(f"Unknown category in rule {rule_id}: {category}")
        ids.add(rule_id)
        conditions: list[Condition] = []
        for item in raw.get("conditions", []):
            operator = str(item.get("operator"))
            if operator not in OPERATORS:
                raise ValueError(f"Unsupported operator in {rule_id}: {operator}")
            raw_value = item.get("value")
            if operator in {"in", "not_in"}:
                if not isinstance(raw_value, list) or not raw_value:
                    raise ValueError(f"Operator {operator} requires a non-empty list")
                value: str | tuple[str, ...] | None = tuple(str(v) for v in raw_value)
            elif operator == "exists":
                value = None
            else:
                if raw_value is None:
                    raise ValueError(f"Operator {operator} requires a value")
                value = str(raw_value)
            conditions.append(Condition(str(item.get("tag")), operator, value))
        if not conditions:
            raise ValueError(f"Rule {rule_id} has no conditions")
        rules.append(
            Rule(
                id=rule_id,
                version=str(raw.get("version")),
                category=category,
                conditions=tuple(conditions),
                source_object_types=frozenset(map(str, raw.get("source_object_types", []))),
                geometry_families=frozenset(map(str, raw.get("geometry_families", []))),
                object_kinds=frozenset(map(str, raw.get("object_kinds", []))),
            )
        )
    return categories, sorted(rules, key=lambda rule: rule.id)


def match_rule(
    rule: Rule,
    tags: dict[str, Any],
    source_object_type: str,
    geometry_family: str,
    object_kind: str,
) -> dict[str, str] | None:
    if rule.source_object_types and source_object_type not in rule.source_object_types:
        return None
    if rule.geometry_families and geometry_family not in rule.geometry_families:
        return None
    if rule.object_kinds and object_kind not in rule.object_kinds:
        return None
    evidence: dict[str, str] = {}
    for condition in rule.conditions:
        present = condition.tag in tags and tags[condition.tag] is not None
        actual = str(tags[condition.tag]) if present else None
        expected = condition.value
        matched = (
            present
            if condition.operator == "exists"
            else actual == expected
            if condition.operator == "equals"
            else actual in expected
            if condition.operator == "in" and isinstance(expected, tuple)
            else actual != expected
            if condition.operator == "not_equals"
            else actual not in expected
            if condition.operator == "not_in" and isinstance(expected, tuple)
            else False
        )
        if not matched:
            return None
        if present and actual is not None:
            evidence[condition.tag] = actual
    return evidence


def _sync_taxonomy(connection: Any, categories: list[dict[str, Any]]) -> None:
    connection.execute(
        text(
            """
            INSERT INTO catalog.categories (key, parent_key, label, enabled, metadata)
            VALUES (:key, :parent_key, :label, :enabled, CAST(:metadata AS jsonb))
            ON CONFLICT (key) DO UPDATE SET parent_key=excluded.parent_key,
                label=excluded.label, enabled=excluded.enabled,
                metadata=excluded.metadata, updated_at=now()
            """
        ),
        [
            {
                "key": str(item["key"]),
                "parent_key": item.get("parent_key"),
                "label": str(item["label"]),
                "enabled": bool(item.get("enabled", True)),
                "metadata": json.dumps(item.get("metadata", {})),
            }
            for item in categories
        ],
    )


def discover_osm_category_candidates(
    source_id: int, *, engine: Engine | None = None
) -> list[tuple[str, int]]:
    _, rules = load_category_config()
    tag_keys = sorted({condition.tag for rule in rules for condition in rule.conditions})
    database = engine or get_engine()
    with database.connect() as connection:
        rows = connection.execute(
            text(
                """
                SELECT 'node' AS source_object_type, n.osm_id, n.tags,
                       'point' AS geometry_family, 'feature' AS object_kind
                FROM staging.osm_nodes n WHERE n.source_id=:source_id AND n.tags ?| :keys
                UNION ALL
                SELECT 'way', w.osm_id, w.tags,
                       CASE WHEN GeometryType(w.geom)='LINESTRING' THEN 'line' ELSE 'polygon' END,
                       'feature'
                FROM staging.osm_ways w WHERE w.source_id=:source_id AND w.tags ?| :keys
                  AND w.geom IS NOT NULL
                UNION ALL
                SELECT 'relation', r.osm_id, r.tags, 'polygon',
                       CASE WHEN g.relation_type='boundary' THEN 'boundary' ELSE 'feature' END
                FROM staging.osm_relations r
                JOIN derived.osm_relation_geometries g ON g.source_id=r.source_id
                  AND g.relation_id=r.osm_id AND g.assembly_status='assembled'
                WHERE r.source_id=:source_id AND r.tags ?| :keys
                  AND g.relation_type IN ('multipolygon','boundary')
                """
            ),
            {"source_id": source_id, "keys": tag_keys},
        )
        result: list[tuple[str, int]] = []
        for row in rows:
            tags = dict(row.tags)
            if any(
                match_rule(rule, tags, row.source_object_type, row.geometry_family, row.object_kind)
                is not None
                for rule in rules
            ):
                result.append((str(row.source_object_type), int(row.osm_id)))
    return sorted(set(result))


def bulk_create_osm_objects(
    source_id: int,
    import_run_id: int,
    identities: list[tuple[str, int]],
    *,
    engine: Engine,
    chunk_size: int = 50000,
) -> int:
    """Create missing canonical bindings set-wise; never reconcile by absence."""
    created = 0
    sql = text("""
        WITH requested AS (
          SELECT * FROM jsonb_to_recordset(CAST(:payload AS jsonb))
            AS x(source_object_type text,source_object_id bigint)
        ), candidates AS (
          SELECT 'node'::text source_object_type,n.osm_id::text source_object_id,
            'feature'::text object_kind,n.tags->>'name' name,n.geom,'raw'::text quality
          FROM requested x JOIN staging.osm_nodes n ON x.source_object_type='node'
            AND x.source_object_id=n.osm_id AND n.source_id=:source_id
          WHERE n.geom IS NOT NULL AND ST_IsValid(n.geom) AND NOT ST_IsEmpty(n.geom)
          UNION ALL
          SELECT 'way',w.osm_id::text,'feature',w.tags->>'name',w.geom,'raw'
          FROM requested x JOIN staging.osm_ways w ON x.source_object_type='way'
            AND x.source_object_id=w.osm_id AND w.source_id=:source_id
          WHERE w.geom IS NOT NULL AND GeometryType(w.geom) IN ('LINESTRING','POLYGON')
            AND ST_IsValid(w.geom) AND NOT ST_IsEmpty(w.geom)
          UNION ALL
          SELECT 'relation',r.osm_id::text,
            CASE WHEN g.relation_type='boundary' THEN 'boundary' ELSE 'feature' END,
            r.tags->>'name',g.geom,'assembled'
          FROM requested x JOIN staging.osm_relations r ON x.source_object_type='relation'
            AND x.source_object_id=r.osm_id AND r.source_id=:source_id
          JOIN derived.osm_relation_geometries g ON g.source_id=r.source_id
            AND g.relation_id=r.osm_id AND g.assembly_status='assembled'
            AND g.relation_type IN ('multipolygon','boundary')
        ), prepared AS MATERIALIZED (
          SELECT gen_random_uuid() id,c.*,
            md5(coalesce(c.name,'')||encode(ST_AsEWKB(c.geom),'hex')) ||
            md5('2'||coalesce(c.name,'')||encode(ST_AsEWKB(c.geom),'hex')) payload_hash
          FROM candidates c WHERE NOT EXISTS (SELECT 1 FROM catalog.object_sources b
            WHERE b.source_id=:source_id AND b.source_object_type=c.source_object_type
              AND b.source_object_id=c.source_object_id)
        ), inserted AS (
          INSERT INTO catalog.objects
            (id,object_kind,lifecycle_status,name,geom,properties,property_sources,revision)
          SELECT id,object_kind,'active',name,geom,'{}'::jsonb,'{}'::jsonb,1 FROM prepared
          RETURNING id
        ), bindings AS (
          INSERT INTO catalog.object_sources
            (object_id,source_id,source_object_type,source_object_id,source_native_version,
             source_status,candidate_name,candidate_geom,candidate_properties,payload_hash,
             geometry_quality,source_priority,match_method,match_confidence,
             first_seen_import_run_id,last_seen_import_run_id,last_changed_import_run_id)
          SELECT p.id,:source_id,p.source_object_type,p.source_object_id,:source_version,
            'present',p.name,p.geom,'{}'::jsonb,p.payload_hash,p.quality,0,
            'source_identity',1.000,:run_id,:run_id,:run_id
          FROM prepared p JOIN inserted i ON i.id=p.id RETURNING id,object_id
        )
        SELECT count(*) AS created FROM bindings
    """)
    for offset in range(0, len(identities), chunk_size):
        payload = json.dumps([
            {"source_object_type": kind, "source_object_id": str(object_id)}
            for kind, object_id in identities[offset : offset + chunk_size]
        ])
        with engine.begin() as connection:
            source_version = connection.scalar(text("""
                SELECT source.version FROM meta.import_runs run
                JOIN meta.dataset_sources source ON source.id=run.source_id
                WHERE run.id=:run_id AND run.source_id=:source_id AND run.status='success'
            """), {"run_id": import_run_id, "source_id": source_id})
            created += int(connection.scalar(sql, {
                "payload": payload, "source_id": source_id, "run_id": import_run_id,
                "source_version": source_version,
            }) or 0)
            connection.execute(text("""
                UPDATE catalog.objects o
                SET name_source_id=b.id,geometry_source_id=b.id,updated_at=now()
                FROM catalog.object_sources b
                WHERE b.source_id=:source_id AND b.object_id=o.id
                  AND (o.name_source_id IS NULL OR o.geometry_source_id IS NULL)
            """), {"source_id": source_id})
    return created


def apply_categories(
    source_id: int,
    import_run_id: int,
    *,
    engine: Engine | None = None,
    binding_ids: list[int] | None = None,
    chunk_size: int = 5000,
) -> tuple[int, int]:
    categories, rules = load_category_config()
    database = engine or get_engine()
    processed = matches = 0
    last_id = 0
    while True:
        with database.begin() as connection:
            _sync_taxonomy(connection, categories)
            rows = connection.execute(
                text(
                    """
                    SELECT b.id, b.object_id, b.source_object_type, b.source_object_id,
                           o.object_kind,
                           CASE WHEN GeometryType(b.candidate_geom)='POINT' THEN 'point'
                                WHEN GeometryType(b.candidate_geom)='LINESTRING' THEN 'line'
                                ELSE 'polygon' END AS geometry_family,
                           CASE b.source_object_type
                             WHEN 'node' THEN n.tags WHEN 'way' THEN w.tags ELSE r.tags END AS tags
                    FROM catalog.object_sources b
                    JOIN catalog.objects o ON o.id=b.object_id
                    LEFT JOIN staging.osm_nodes n ON b.source_object_type='node'
                      AND n.source_id=b.source_id AND n.osm_id=b.source_object_id::bigint
                    LEFT JOIN staging.osm_ways w ON b.source_object_type='way'
                      AND w.source_id=b.source_id AND w.osm_id=b.source_object_id::bigint
                    LEFT JOIN staging.osm_relations r ON b.source_object_type='relation'
                      AND r.source_id=b.source_id AND r.osm_id=b.source_object_id::bigint
                    WHERE b.source_id=:source_id AND b.source_status='present' AND b.id>:last_id
                      AND (:all_bindings OR b.id = ANY(:binding_ids))
                    ORDER BY b.id LIMIT :chunk_size
                    """
                ),
                {
                    "source_id": source_id,
                    "last_id": last_id,
                    "chunk_size": chunk_size,
                    "all_bindings": binding_ids is None,
                    "binding_ids": binding_ids or [],
                },
            ).all()
            if not rows:
                break
            last_id = int(rows[-1].id)
            processed += len(rows)
            active_keys: list[dict[str, Any]] = []
            affected: set[tuple[str, str]] = set()
            row_ids = [int(row.id) for row in rows]
            for row in rows:
                tags = dict(row.tags or {})
                for rule in rules:
                    evidence = match_rule(
                        rule,
                        tags,
                        str(row.source_object_type),
                        str(row.geometry_family),
                        str(row.object_kind),
                    )
                    if evidence is None:
                        continue
                    matches += 1
                    affected.add((str(row.object_id), rule.category))
                    active_keys.append(
                        {
                            "object_id": row.object_id,
                            "category_key": rule.category,
                            "object_source_id": row.id,
                            "rule_id": rule.id,
                            "rule_version": rule.version,
                            "evidence": evidence,
                            "run_id": import_run_id,
                        }
                    )
            connection.execute(
                text(
                    "UPDATE catalog.object_category_sources SET status='inactive', updated_at=now() WHERE object_source_id=ANY(:ids)"
                ),
                {"ids": row_ids},
            )
            if active_keys:
                evidence_payload = json.dumps(active_keys, default=str)
                connection.execute(
                    text("""
                    INSERT INTO catalog.object_category_sources
                      (object_id,category_key,object_source_id,rule_id,rule_version,status,evidence,
                       first_seen_import_run_id,last_seen_import_run_id)
                    SELECT x.object_id::uuid,x.category_key,x.object_source_id,x.rule_id,
                           x.rule_version,'active',x.evidence,x.run_id,x.run_id
                    FROM jsonb_to_recordset(CAST(:payload AS jsonb)) x(
                      object_id text,category_key text,object_source_id bigint,rule_id text,
                      rule_version text,evidence jsonb,run_id integer)
                    ON CONFLICT (object_source_id,category_key,rule_id) DO UPDATE SET
                      object_id=excluded.object_id, rule_version=excluded.rule_version,status='active',
                      evidence=excluded.evidence,last_seen_import_run_id=excluded.last_seen_import_run_id,
                      updated_at=now()
                """),
                    {"payload": evidence_payload},
                )
            existing_affected = connection.execute(
                text(
                    "SELECT DISTINCT object_id::text, category_key FROM catalog.object_category_sources WHERE object_source_id=ANY(:ids)"
                ),
                {"ids": row_ids},
            ).all()
            affected.update(
                (str(row.object_id), str(row.category_key)) for row in existing_affected
            )
            if affected:
                payload = json.dumps(
                    [{"object_id": oid, "category_key": key} for oid, key in affected]
                )
                connection.execute(
                    text("""
                    INSERT INTO catalog.object_categories (object_id,category_key,lifecycle_status)
                    SELECT x.object_id::uuid,x.category_key,
                      CASE WHEN EXISTS (SELECT 1 FROM catalog.object_category_sources s
                        WHERE s.object_id=x.object_id::uuid AND s.category_key=x.category_key AND s.status='active')
                      THEN 'active' ELSE 'inactive' END
                    FROM jsonb_to_recordset(CAST(:payload AS jsonb)) x(object_id text,category_key text)
                    ON CONFLICT (object_id,category_key) DO UPDATE SET
                      lifecycle_status=excluded.lifecycle_status,updated_at=now()
                """),
                    {"payload": payload},
                )
    return processed, matches


def run_osm_category_pipeline(
    source_id: int, import_run_id: int, *, engine: Engine | None = None, chunk_size: int = 10000
) -> CategoryRunResult:
    started = time.monotonic()
    database = engine or get_engine()
    identities = discover_osm_category_candidates(source_id, engine=database)
    created = bulk_create_osm_objects(
        source_id, import_run_id, identities, engine=database,
        chunk_size=max(chunk_size, 50000),
    )
    processed, matches = apply_categories(source_id, import_run_id, engine=database)
    with database.connect() as connection:
        assignments = int(
            connection.scalar(
                text(
                    "SELECT count(*) FROM catalog.object_categories WHERE lifecycle_status='active'"
                )
            )
            or 0
        )
    return CategoryRunResult(
        len(identities), created, processed, matches, assignments, time.monotonic() - started
    )
