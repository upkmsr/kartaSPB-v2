# Logical facility representations

Status: F5.5-S4R implementation rehearsal accepted on 2026-09-29. Production
backfill is intentionally pending the manual visual gate.

## Problem and boundary

OSM may describe one facility with a POI node, a facility/site area, and a building
footprint. `catalog.objects` correctly preserves each OSM identity as a separate
canonical object. The product needs one displayable facility without destroying that
identity, provenance, or geometry.

S4R adds a representation layer only for:

- `education.kindergarten`;
- `education.school`;
- `healthcare.hospital`;
- `healthcare.clinic`.

Pharmacies, parks, water, stops, roads, and administrative boundaries are excluded.
Street entities and search-result collapsing remain S5 work.

## Schema

Migration `20260929_0009` adds two tables and does not alter catalog rows:

- `domain.facility_entities` stores the stable facility UUID, category, explicit
  representative/display/analysis canonical object references, lifecycle, aggregate
  link method, evidence, and timestamps;
- `domain.facility_entity_members` stores canonical members, geometry role, lifecycle,
  link method, evidence, and timestamps.

One partial unique index permits a canonical object in only one active facility. All
role and member references are foreign keys to `catalog.objects`; geometry is not
copied. Downgrade removes only these two S4R tables and their indexes.

## Conservative matcher

Candidate discovery is category-scoped and compares Point to Polygon/MultiPolygon
objects only. It uses a GiST bbox prefilter and a maximum 100 m geography predicate.
Spatial relationship is candidate generation, never identity evidence.

An automatic link requires the same eligible category plus at least one deterministic
strong signal:

- shared explicit `type=site` relation;
- exact non-empty `ref`;
- exact `wikidata` or `brand:wikidata`;
- containment plus exact normalized phone or official website;
- containment plus exact normalized name and operator;
- containment plus exact normalized name and a direct facility-site area;
- containment plus a complete street/house-number address and either matching
  name/operator or a nameless compatible direct-facility area.

Contradictory non-empty refs or Wikidata IDs reject a pair. Different non-empty names
are not linked merely because two direct-facility objects share an address. Proximity,
containment, fuzzy names, same street/district/category, or containment in a generic
building are never sufficient. There is no fuzzy auto-linking.

Components with multiple Points, duplicate competing area roles, category collision,
or overlap with multiple existing facility entities are conflicts and are not written.
The schema can represent a Point + facility site + building when every member has
strong evidence, while ambiguous alternatives remain unlinked.

The current OSM snapshot contains 52 `type=site` relations, but none supplies a usable
Point/area facility link in the eligible categories. The implementation supports that
evidence for future snapshots; initial accepted links use exact ref, contact, or address
identity.

## Representation roles

Area classification is explicit:

- `FACILITY_SITE`: direct facility semantics without a building/building-part tag;
- `BUILDING`: a building or building part, even when it also has facility tags;
- `OTHER_AREA`: another polygonal object;
- `POINT`: point geometry;
- `UNKNOWN`: defensive fallback.

Representative selection is deterministic: richest stable facility metadata first,
then facility-site, Point, building, other area, and UUID tie-break. Display precedence
is confirmed facility site, confirmed building, then representative. Analysis
precedence is confirmed facility site, Point, then representative. Consequently a
building-only match may improve display geometry while analysis remains the POI Point;
a building is not silently treated as facility territory.

## Identity, refresh, and lifecycle

New facility IDs are UUIDv5 values derived from category plus sorted initial canonical
member UUIDs. A later refresh reuses any existing entity that contains an accepted
member, so added evidence does not churn identity. Refresh is a single transaction and
updates only changed rows.

If a strong group disappears and exactly one member remains active with the category,
the entity stays active and all three roles fall back to that canonical object. If zero
or multiple formerly linked objects remain usable without a current unambiguous strong
group, the entity and memberships become inactive. Canonical lifecycle is never
changed. A failed refresh rolls back and leaves the previous valid representation
usable.

Operational order is:

```text
OSM ingest -> canonical refresh -> category refresh -> facility refresh
```

Facility refresh is deliberately an explicit retry-safe command so a failure cannot
corrupt or roll back successful canonical/category processing:

```bash
python -m app.data.facility_cli dry-run
python -m app.data.facility_cli refresh
```

## API and search behavior

`GET /api/map/features` collapses active group members into one feature whose ID is the
facility UUID and whose geometry is the display object's geometry. Compact properties
retain the representative canonical ID, display canonical ID, and member canonical
IDs. Category, district, spatial, and feature-limit selection operate on the logical
display representation. Ungrouped objects keep their prior behavior.

`GET /api/objects/{canonical_uuid}` remains canonical. For a member it additionally
returns facility roles and every member's canonical and OSM identity. The frontend
clicks through to the representative canonical object, highlights by any member UUID,
and therefore highlights the visible display geometry.

Search ranking, result identity, duplicate-name behavior, and street semantics are
unchanged. A member result keeps its canonical UUID and rank, but navigation geometry,
bbox, representative point, and district filtering use the facility display geometry.
S5 may collapse facility-member search suggestions; it must use a separate entity model
for streets.

Analysis geometry is stored for future scoring only. S4R adds no scores, heatmaps, or
ranking changes.

## Isolated rehearsal

The current production database was dumped and restored to
`kartaspb_s4r_rehearsal`. The verified custom-format dump was 302 MiB with SHA-256
`e2ebe8dd602888860ea50069fba3b9e0fbdb24c44accd8c003bff71afd2e0e41`.
Migration `20260929_0009` and both refreshes ran only there; production remained at
`20260928_0008` with no facility tables.

Dry-run and refresh measurements:

| Measure | Result |
|---|---:|
| bounded candidate pairs | 165 |
| strong pairs | 19 |
| rejected/insufficient pairs | 146 |
| conflict components | 2 |
| active facility entities | 15 |
| active members | 30 |
| multi-member entities | 15 |
| second-run creates / changes / unchanged | 0 / 0 / 15 |
| refresh wall time including one-off container startup | about 10 s |

Accepted entities by category: 9 kindergarten, 3 school, 3 clinic, and 0 hospital.
Display roles are 12 facility sites and 3 buildings. Analysis roles are 12 facility
sites and 3 Points. Members are 15 Points, 12 facility sites, and 3 buildings. There
are zero duplicate active memberships and zero invalid active role references.

Before and after rehearsal remained identical at 417,331 active canonical objects,
417,332 active assignments (417,336 total rows), zero duplicate source identities, and
18 district bindings. The district UUID/binding checksum remained
`f4689bd0dc0f6a13462acd05a31c55da`.

## Reviewed initial links

Every proposed initial entity was inspected. Each row lists its OSM members and role
outcome (`display / analysis`).

| Category | Facility UUID | Members | Evidence | Roles |
|---|---|---|---|---|
| clinic | `3367de30-1bf2-5177-84cc-3a5ba9de4156` | `node/1868505732`, `way/23375678` | complete address + compatible nameless facility building | building / Point |
| clinic | `ef19b411-9bb0-54d0-9f44-c1cd6897b82f` | `node/10807428892`, `way/751143097` | exact phone + containment | building / Point |
| clinic | `e1d40eee-ecdc-59b4-86fa-396af7c07f53` | `node/8193687529`, `relation/1835712` | exact website + containment | site / site |
| kindergarten | `a6be6d1a-8329-52b0-9773-07313d0e65ff` | `node/1066206884`, `relation/1702678` | exact ref 91 | site / site |
| kindergarten | `0415db3e-97fe-5579-9ffd-fad1feb9c327` | `node/5265188406`, `way/91757471` | exact ref 250 | site / site |
| kindergarten | `38af0a75-e95e-56e5-b3c3-1856b0818b9d` | `node/9838721233`, `way/84488097` | exact ref 43 | site / site |
| kindergarten | `45bd3b45-4210-569f-a0dd-2b190983ef5d` | `node/3732087286`, `relation/2885167` | exact ref 21 | site / site |
| kindergarten | `ef6fb15a-8f1a-5495-942f-d43206e3ab04` | `node/7596024032`, `way/542394860` | exact ref 1 | site / site |
| kindergarten | `abf1d852-4844-5a0f-9be7-f667f961e89e` | `node/1586994504`, `way/1393997314` | exact ref 41 | site / site |
| kindergarten | `70c2f338-d86c-53d3-9e79-293b111eb1db` | `node/3583782889`, `way/628426559` | exact ref 115 | site / site |
| kindergarten | `1ea54d84-0ccf-5313-8eab-fc55b4443a09` | `node/11070392225`, `way/870285446` | exact ref 28 | site / site |
| kindergarten | `c3dd4587-7eae-5c57-9e34-05cf1da918e9` | `node/10968955824`, `relation/19993140` | exact ref 355 | site / site |
| school | `cf074c39-8f4d-5e35-ac9c-769d07460a49` | `node/11800067314`, `way/28932878` | exact ref 47 | building / Point |
| school | `da4e37e3-e5f0-5a04-b49a-c3879c7900ac` | `node/965318389`, `way/817936106` | exact ref 27 | site / site |
| school | `6a587d87-55e8-5672-9c60-e600572eca30` | `node/805518409`, `way/526506065` | exact ref 642 | site / site |

The matcher intentionally rejected two ambiguous school components: school 171's Point
matched two different area roles, and school 35's Point matched the school and a
preschool department. A differently named diagnostic center at the same address as
`node/1868505732` remains a separate ungrouped clinic. The other 146 candidate pairs,
including most kindergarten Points, remain canonical Points/areas because their
evidence is insufficient.

## Known limitations and future work

- Initial linking requires a Point/area pair; area-only relation structures are not
  broadly inferred.
- No current accepted group comes from explicit `type=site` membership.
- Exact refs can represent an institution with departments; conflicts are rejected,
  but future manual review may need allow/deny decisions stored separately.
- Search suggestions are not collapsed in S4R.
- Production counts remain pending the manual S4R visual gate and approved production
  migration/refresh.
