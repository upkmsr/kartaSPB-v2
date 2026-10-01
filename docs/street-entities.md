# Logical street entities

Status: F5.5-S5 implementation and isolated rehearsal passed on 2026-10-01.
Production migration/backfill is intentionally pending the manual visual gate.

## Problem and identity boundary

OSM splits a named street into many ways at intersections, surface changes, bridges,
and divided carriageways. Those ways remain separate source-backed canonical objects.
Search and navigation need a logical representation without merging or rewriting that
canonical identity.

Migration `20261001_0010` therefore adds:

- `domain.street_entities`: stable UUID, display/search names, lifecycle, grouping
  method/evidence, aggregate MultiLineString, representative Point, and timestamps;
- `domain.street_entity_members`: logical street/canonical road membership with
  lifecycle and evidence;
- `catalog.objects.search_name_v2`: stored Search v2 comparison text plus a partial
  trigram index.

The migration is additive. It does not modify canonical IDs, source bindings,
geometries, category assignments, districts, or facility entities. Its downgrade
removes only S5-owned tables, indexes, and the Search v2 column.

## Production-data audit

Read-only discovery on the production snapshot found:

| Measure | Result |
|---|---:|
| active `transport.road` objects | 385,886 |
| named eligible road objects | 36,416 |
| geometry | all eligible rows are LineString |
| distinct exact names | 4,211 |
| distinct normalized names | 4,204 |
| normalized names represented by multiple ways | 2,852 |
| member-count percentiles | p50 3, p75 7, p90 18, p95 32, p99 about 95 |
| largest same-name population | 678 source ways |

The inspected source tags included `name`, `name:ru`, `official_name`, `short_name`,
`alt_name`, `old_name`, `ref`, and `highway`. Name equality alone was demonstrably
unsafe: for example, `Центральная улица` occurs in many spatially separate places.

Relevant explicit OSM relation evidence was also measured: 297 `type=street`
relations (5,705 road memberships), nine `associatedStreet` relations (201
memberships), and two `dual_carriageway` relations (12 memberships). Relation
`4760879` supplies the evidence needed to join the two otherwise separate 30 m
components of Невский проспект.

## Conservative grouping

Eligibility requires an active canonical object, an active `transport.road`
assignment, a usable LineString/MultiLineString geometry, and a non-empty name.
Unnamed roads are excluded.

The deterministic comparison name uses NFKC, NBSP replacement, lowercase, Russian
`ё` to `е`, whitespace collapse, and trim. The original human name remains the display
name.

Grouping proceeds in two bounded stages:

1. `ST_ClusterDBSCAN` in EPSG:32636 groups only roads with the exact normalized name,
   using a 30 m maximum gap and `minpoints=1`.
2. Separate components may be joined only by an explicit matching-name `type=street`
   or `associatedStreet` relation, or by explicit `dual_carriageway` evidence.

Different normalized names never merge. District is never part of identity, so one
street can cross district boundaries. A broad citywide same-name merge and fuzzy name
similarity are deliberately absent. Evidence on every entity records the normalized
name, member count, distance threshold, and any supporting OSM relations.

New entity IDs are UUIDv5 values derived from the deterministic initial membership.
On later refresh, an unambiguous active membership anchor reuses the existing entity
UUID, so member ordering and ordinary source evolution do not churn identity.

## Refresh and lifecycle

The explicit operational interface is:

```bash
python -m app.data.street_cli dry-run
python -m app.data.street_cli refresh
```

Dry-run performs no writes. Refresh builds a plan, then applies entities, memberships,
aggregate geometries, and lifecycle transitions in one transaction. A failed write
rolls back. Rows absent from a later valid plan become inactive; canonical objects,
category assignments, facilities, and districts are never changed.

Operational order after any future source refresh is:

```text
OSM -> canonical -> categories -> facilities -> streets
```

## Search v2 semantics

`GET /api/search` returns explicit `object`, `facility`, and `street` result types.
Facility members collapse to their facility UUID and retain an explicit canonical
ObjectCard target. Street members collapse to the street UUID, a stored aggregate bbox
and representative point, and `detail_object_id=null`. Selecting a street fits its bbox
and never sends that logical UUID to the canonical ObjectDetail endpoint.

Object/facility category filters retain their existing semantics. Streets remain
searchable when every ordinary layer is off, through `include_objects=false`. District
scope uses the logical street geometry, so a cross-district entity is found from either
district without splitting its identity.

## Isolated rehearsal

A verified custom-format production snapshot was restored into
`kartaspb_s5_rehearsal`. The 302 MiB dump has SHA-256
`9833d4888e38aecd7e3ec678402d37166d387f051d9ce330a0e228b496dac21b`;
`pg_restore --list` passed. The restored baseline was revision `20260929_0009` with
417,331 active canonical objects, 417,332 active assignments, 18 enabled districts,
15 active facilities, and 30 active facility members.

Migration upgrade, downgrade/re-upgrade, and Alembic model-parity checks passed in the
isolated database. Rehearsal results were:

| Measure | Result |
|---|---:|
| active street entities | 6,843 |
| active street members | 36,416 |
| multi-member entities | 3,688 |
| largest entity | 519 members, КАД |
| normalized names intentionally kept as multiple entities | 925 |
| entities with explicit relation support | 43 |
| first refresh | 6,843 created, 0 changed; 67.42 s |
| second refresh | 0 created, 0 changed, 6,843 unchanged; 63.28 s |

There were zero duplicate active memberships, invalid member references, or invalid
active street geometries. Canonical/category counts, facility counts, district count,
and canonical/category checksums remained unchanged.

Warm production-like API timings were 43 ms for an ordinary query, 18 ms for a
facility query, 15 ms for an exact street query, 14 ms for a partial street query, and
50 ms for a district-scoped street query.

## Reviewed real controls

- Невский проспект: entity `8266b2e8-cbbd-575a-997d-db2065db03ff`, 121
  members, supported by `type=street/4760879`.
- набережная Обводного канала: entity
  `32aed7f1-0fab-55ba-a173-14dfadeda2e1`, 205 members, and searchable with the same
  UUID from five intersecting districts.
- проспект Энергетиков: entity `a28ad1d7-b7fd-5a5a-98b5-7e8cb528cd56`, 23
  members, with explicit `dual_carriageway/151280` and `/151282` evidence.
- `Центральная улица`: 54 distinct entities after conservative spatial
  grouping, proving that exact normalized name does not imply one citywide identity.
- Поликлиника №104: facility `3367de30-1bf2-5177-84cc-3a5ba9de4156` is one
  result, with canonical detail target `c5a591bc-b1cf-474b-a85c-beebbc587031` and
  Polygon navigation geometry.
- Юникея remains an intentionally unlinked ordinary Point; ordinary pharmacy,
  park, and stop search behavior remains canonical.
- `Гимназия № 642` matches its NBSP source name; `проспект
  королева` matches display name `проспект Королёва`.

## Known limitations

- The model represents conservative spatial components, not official municipal street
  registries. Missing or incorrect OSM names/relations remain source limitations.
- Aliases were audited but are not yet a general independent identity/search document;
  primary-name grouping remains authoritative for S5.
- A same-name road separated by more than 30 m without explicit supported relation
  evidence remains separate, even when a human might consider it one corridor.
- Search returns bbox and representative point only; a StreetCard, address search,
  routing, and map-layer redesign are outside S5.
