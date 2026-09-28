# F5.5-S3 spatial coverage audit

Audit date: 2026-09-28

Start revision: `c5e215882c4216b254be33d752919cd24307bd62`

Scope: diagnostic only; the main `kartaspb` database was not intentionally mutated.

## Verdict

The remote-data problem is **B — extraction profile too small**. The current ordinary
catalog is effectively the historical `spb_smoke` catalog. The later
`spb_districts` import added authoritative district boundaries and a small number of
tagged member ways/nodes, but it did not add general remote POIs or roads.

The `spb_smoke` hypothesis is **CONFIRMED**:

- 256,581 of 256,916 active non-boundary objects were first canonicalized from
  `spb_smoke`;
- the remaining 335 were first canonicalized from `spb_districts`;
- 256,585 objects intersect the smoke box and only 331 (0.129%) are wholly outside it;
- all 331 outside objects came from `spb_districts` member data (72 water, 213 roads,
  46 stops);
- `spb_lo` has never completed an import in the main database;
- source-side and isolated full-area evidence contains thousands of classifiable
  objects in remote districts that are absent from current staging.

The five remote API controls returned HTTP 200 with zero features. Equivalent central
controls returned 97 to 171 features. The failure is therefore upstream of API and
frontend visibility; it is not a feature-limit, request-validation, district-filter,
or min-zoom failure.

## Environment and source

| Item | Audited value |
|---|---|
| PostgreSQL | 17.5 |
| PostGIS | 3.5.2 |
| Alembic | `20260925_0007` |
| Osmium | 1.15.0 (libosmium 2.18.0) |
| osm2pgsql | 1.8.0 |
| Source | `data/sources/osm/northwestern-fed-district-20260921T231045Z.osm.pbf` |
| Registered version | `20260921T231045Z` |
| PBF replication timestamp | `2026-09-21T20:21:51Z` |
| Size | 653,745,939 bytes (623 MiB) |
| SHA-256 | `ebd1ac7b344c091a9190089422c75b8b704eaaacdc5f93ab5046bab16732925f` |
| Source objects | 88,807,310 nodes; 7,288,746 ways; 438,369 relations |

The registered provider is Geofabrik's Northwestern Federal District extract. The
filename, version, checksum, and timestamps above come from `meta.dataset_sources`,
the repository configuration, and `osmium fileinfo -e`; they were not inferred from
historical filenames.

## Extraction profiles and production provenance

| Profile | Selection and strategy | Purpose | Main DB evidence |
|---|---|---|---|
| `spb_smoke` | bbox `[30.20, 59.85, 30.50, 60.08]`; `osmium extract --strategy simple` | Fast real-data development/acceptance box; not production-wide coverage | Eight successful runs. Import run 45 supplied 256,581 current ordinary objects and 51 boundaries. |
| `spb_lo` | bbox `[27.50, 58.35, 35.00, 61.80]`; `simple` | Coarse Saint Petersburg + Leningrad Oblast source, not an official boundary | No successful main import. Run 11 failed before import because the extract did not exist. |
| `spb_districts` | relation root `337422`; `osmium getid --add-referenced --verbose-ids` | Reference-complete administrative hierarchy for the 18 district registry | Runs 184/185 succeeded. It supplied 80 new boundaries and 335 tagged ordinary member objects, not general object coverage. |

The one-off `route_master_acceptance` runs are F2 acceptance data, not a supported
geographic coverage profile.

`spb_smoke.osm.pbf` is 33,579,936 bytes and its measured data extent is
`(30.2000005,59.8500001,30.4999996,60.0799988)`, matching the configured bbox.
It contains 2,395,865 nodes, 477,389 ways, and 29,208 relations.

## Current catalog footprint

| Measure | Result |
|---|---:|
| Active canonical objects | 257,047 |
| Active administrative boundaries | 131 |
| Active non-boundary objects | 256,916 |
| Active category assignments | 257,047 |
| Intersecting smoke bbox | 256,585 |
| Wholly outside smoke bbox | 331 |
| Outside percentage | 0.129% |
| Overall ordinary extent | `BOX(29.4822006 59.6523981,30.735294 60.2344325)` |
| `spb_smoke`-origin ordinary extent | `BOX(30.2000027 59.8500003,30.4999996 60.0799984)` |
| 1 km point-on-surface grid cells | 1,918 total; 1,765 inside smoke; 157 outside |

The overall extent is misleading if read alone: the sparse remote tail consists of
district-extract members. The extent of the 256,581 smoke-origin objects has a sharp
cutoff at the configured smoke coordinates.

Current active category assignments inside/outside the smoke bbox:

| Category | Inside | Outside |
|---|---:|---:|
| `education.school` | 740 | 0 |
| `education.kindergarten` | 1,165 | 0 |
| `healthcare.pharmacy` | 1,870 | 0 |
| `healthcare.hospital` | 115 | 0 |
| `healthcare.clinic` | 555 | 0 |
| `nature.park` | 1,092 | 0 |
| `nature.water` | 736 | 72 |
| `transport.stop` | 7,708 | 46 |
| `transport.road` | 242,604 | 213 |

## Full-area comparison method

An isolated database named `kartaspb_coverage_audit_s3` was migrated to the current
Alembic head. No import was run against `kartaspb`.

The diagnostic `spb_lo` extract was produced from the registered source version with
the profile's current `simple` strategy:

```text
source PBF
  -> osmium extract --bbox 27.5,58.35,35.0,61.8 --strategy simple
  -> isolated migrations
  -> existing import_region("spb_lo")
  -> exact current category rules evaluated against isolated staging/derived data
  -> ST_Intersects against the 18 assembled district geometries
```

Extract facts:

- size: 214,177,553 bytes (204 MiB);
- SHA-256: `4210edc4453aa8c0e61a62335de694e2d2cc5a977ceb431f4b8fd6296086cf95`;
- 24,536,844 nodes, 2,997,568 ways, 165,652 relations;
- measured extent: `(27.5000084,58.35,34.9999998,61.8)`;
- all 18 district relations were present and all 18 derived geometries had
  `assembly_status='assembled'`;
- isolated import: 3,893,600 staging objects, 1,383,544 relation members,
  142,622 area candidates, and 146,930 derived relation geometries;
- import wall time: 3,543 seconds (59 minutes 3 seconds); osm2pgsql itself took
  589 seconds.

The ordinary full-area catalog was not materialized completely. The current bulk
canonical path found 825,172 candidates across the coarse profile, but its repeated
source-wide winner update made completion impractical on the 2 CPU / 4 GiB Docker
allocation. A partial 50,000-object audit batch was not used for any result below.
Instead, exact current JSON rule semantics were evaluated in low-memory,
district-scoped queries over the successfully imported isolated staging/derived
layers. This is the permitted expensive-import fallback and yields deterministic
source identity/category counts, but it is not a claim that a complete audit
`catalog.objects` table was built.

## All-district coverage matrix

Every count uses exact `ST_Intersects`; centroid assignment was not used. An object
crossing a district boundary can appear in both district rows. Cells in the category
columns are `current -> full-area rule-equivalent`.

| District | km² | Current | Full | Coverage | Current/full objects per km² |
|---|---:|---:|---:|---:|---:|
| Адмиралтейский | 13.80 | 18,349 | 18,349 | 100.00% | 1,329.64 / 1,329.64 |
| Василеостровский | 21.63 | 16,786 | 17,426 | 96.33% | 776.05 / 805.64 |
| Выборгский | 114.66 | 26,488 | 30,227 | 87.63% | 231.01 / 263.62 |
| Калининский | 40.17 | 24,189 | 24,189 | 100.00% | 602.17 / 602.17 |
| Кировский | 46.03 | 11,910 | 17,959 | 66.32% | 258.74 / 390.16 |
| Колпинский | 102.87 | 74 | 12,085 | 0.61% | 0.72 / 117.48 |
| Красногвардейский | 56.24 | 20,923 | 22,726 | 92.07% | 372.03 / 404.09 |
| Красносельский | 90.79 | 1,704 | 24,412 | 6.98% | 18.77 / 268.88 |
| Кронштадтский | 20.02 | 0 | 4,727 | 0.00% | 0.00 / 236.11 |
| Курортный | 274.25 | 69 | 14,590 | 0.47% | 0.25 / 53.20 |
| Московский | 73.91 | 15,821 | 32,103 | 49.28% | 214.06 / 434.35 |
| Невский | 61.79 | 26,401 | 30,494 | 86.58% | 427.27 / 493.51 |
| Петроградский | 19.64 | 15,679 | 15,680 | 99.99% | 798.32 / 798.37 |
| Петродворцовый | 110.74 | 33 | 17,692 | 0.19% | 0.30 / 159.76 |
| Приморский | 110.50 | 28,854 | 34,873 | 82.74% | 261.12 / 315.59 |
| Пушкинский | 239.59 | 51 | 25,683 | 0.20% | 0.21 / 107.20 |
| Фрунзенский | 37.47 | 17,453 | 28,416 | 61.42% | 465.79 / 758.37 |
| Центральный | 17.70 | 23,180 | 23,181 | 100.00% | 1,309.60 / 1,309.66 |

| District | School | Kindergarten | Pharmacy | Hospital | Clinic | Park | Water | Stop | Road |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Адмиралтейский | 60→60 | 73→73 | 111→111 | 13→13 | 29→29 | 127→127 | 50→50 | 404→404 | 17,482→17,482 |
| Василеостровский | 54→57 | 58→59 | 105→109 | 9→9 | 28→28 | 141→142 | 30→33 | 433→488 | 15,927→16,501 |
| Выборгский | 85→92 | 130→140 | 241→258 | 24→25 | 85→90 | 90→93 | 113→220 | 1,079→1,220 | 24,641→28,090 |
| Калининский | 71→71 | 117→117 | 169→169 | 11→11 | 43→43 | 70→70 | 59→60 | 910→910 | 22,738→22,738 |
| Кировский | 23→51 | 42→81 | 80→129 | 3→4 | 18→26 | 62→85 | 80→133 | 406→640 | 11,196→16,810 |
| Колпинский | 0→36 | 0→60 | 0→62 | 0→7 | 0→6 | 0→48 | 21→314 | 16→548 | 37→11,004 |
| Красногвардейский | 64→66 | 98→101 | 165→167 | 5→5 | 40→42 | 66→67 | 107→137 | 771→872 | 19,607→21,269 |
| Красносельский | 7→68 | 12→111 | 19→144 | 0→6 | 3→45 | 2→49 | 9→439 | 67→934 | 1,585→22,617 |
| Кронштадтский | 0→11 | 0→11 | 0→15 | 0→5 | 0→3 | 0→42 | 0→82 | 0→140 | 0→4,418 |
| Курортный | 0→18 | 0→30 | 0→39 | 0→12 | 0→6 | 0→73 | 11→325 | 11→671 | 47→13,416 |
| Московский | 36→70 | 68→116 | 98→183 | 2→6 | 36→54 | 75→120 | 41→152 | 421→820 | 15,044→30,582 |
| Невский | 77→90 | 145→164 | 180→220 | 14→14 | 39→43 | 78→84 | 38→103 | 785→903 | 25,045→28,874 |
| Петроградский | 46→46 | 61→61 | 69→69 | 11→11 | 56→56 | 109→109 | 110→111 | 343→343 | 14,874→14,874 |
| Петродворцовый | 0→29 | 0→36 | 0→57 | 0→7 | 0→13 | 0→73 | 3→453 | 4→704 | 26→16,320 |
| Приморский | 97→110 | 141→155 | 268→288 | 7→10 | 71→73 | 79→92 | 98→361 | 1,015→1,179 | 27,078→32,606 |
| Пушкинский | 0→58 | 0→72 | 0→81 | 0→8 | 0→21 | 0→95 | 32→545 | 2→788 | 17→24,015 |
| Фрунзенский | 34→59 | 59→104 | 91→170 | 1→5 | 15→25 | 58→78 | 20→49 | 444→692 | 16,731→27,234 |
| Центральный | 70→70 | 85→85 | 133→133 | 12→12 | 74→74 | 129→129 | 44→45 | 500→500 | 22,133→22,133 |

The near-empty/boundary-only group is Кронштадтский, Курортный, Петродворцовый,
Пушкинский, and Колпинский. Красносельский is strongly truncated. Московский,
Кировский, and Фрунзенский show partial cutoff. Districts mostly or wholly inside the
smoke box form the control group and approach 100%.

## Category-level comparison

These totals use the union of the 18 official district geometries, so cross-district
objects are counted once.

| Category | Current | Full-area | Current/full | Classification |
|---|---:|---:|---:|---|
| All non-boundary | 246,792 | 393,103 | 62.78% | `SMOKE-LIMITED` |
| `education.school` | 724 | 1,061 | 68.24% | `SMOKE-LIMITED` |
| `education.kindergarten` | 1,089 | 1,576 | 69.10% | `SMOKE-LIMITED` |
| `healthcare.pharmacy` | 1,729 | 2,404 | 71.92% | `SMOKE-LIMITED` |
| `healthcare.hospital` | 112 | 170 | 65.88% | `SMOKE-LIMITED` |
| `healthcare.clinic` | 537 | 677 | 79.32% | `SMOKE-LIMITED` |
| `nature.park` | 1,084 | 1,572 | 68.96% | `SMOKE-LIMITED` |
| `nature.water` | 732 | 3,437 | 21.30% | `SMOKE-LIMITED` and separately rule/semantic-limited |
| `transport.stop` | 7,596 | 12,741 | 59.62% | `SMOKE-LIMITED` |
| `transport.road` | 233,192 | 369,469 | 63.12% | `SMOKE-LIMITED` |

The full-area values are not completeness scores for OSM or the category ontology.
They answer the narrower question: what the current rules would classify if geographic
coverage were present. The known non-exhaustive water semantics remain a separate data
quality issue.

## Remote API and search reality

Map API requests used five non-road categories, exact district UUIDs, a 0.02° × 0.014°
viewport around a verified remote source school, and `limit=5000`.

| District/control | Bbox | HTTP | Features |
|---|---|---:|---:|
| Колпинский | `30.555461,59.728042,30.575461,59.742042` | 200 | 0 |
| Кронштадтский | `29.744836,59.986827,29.764836,60.000827` | 200 | 0 |
| Курортный | `29.960998,60.088546,29.980998,60.102546` | 200 | 0 |
| Петродворцовый | `29.865884,59.883111,29.885884,59.897111` | 200 | 0 |
| Пушкинский | `30.341638,59.729371,30.361638,59.743371` | 200 | 0 |
| Адмиралтейский control | `30.292795,59.911443,30.312795,59.925443` | 200 | 161 |
| Петроградский control | `30.275820,59.957234,30.295820,59.971234` | 200 | 97 |
| Центральный control | `30.344600,59.928826,30.364600,59.942826` | 200 | 171 |

No request returned 422 or `feature_limit_exceeded`.

District-scoped searches for `Гимназия № 446`, `Морской кадетский корпус`,
`Гимназия № 433`, `Академическая гимназия СПбГУ`, and `Воскресная школа` each
returned HTTP 200 with zero results. The central control query
`Вторая Санкт-Петербургская гимназия` returned two results. Search mirrors catalog
coverage; ranking or UI behavior is not hiding remote canonical objects.

## Traced missing source objects

Direct `osmium getid` against the registered source PBF confirmed every identity and
its relevant tags. The same identities were present in isolated `spb_lo` staging and
matched current category rules. All ten were absent from current `staging.osm_ways` by
exact `(source system, OSM type, OSM ID)`, so downstream derived processing is `N/A`,
there is no current source binding/category, and no canonical ID can be returned by
the API.

| District | OSM identity | Name / relevant tags | Geometry | Source | Audit staging | Current staging | Derived | Binding/category/API |
|---|---|---|---|---|---|---|---|---|
| Колпинский | `way/315576917` | 10-й проезд; `highway=service` | LineString | YES | YES | NO | N/A | NO / NO / NO |
| Колпинский | `way/746814512` | Гимназия № 446; `amenity=school` | Polygon | YES | YES | NO | N/A | NO / NO / NO |
| Кронштадтский | `way/1484281867` | 2; `highway=footway` | LineString | YES | YES | NO | N/A | NO / NO / NO |
| Кронштадтский | `way/78199509` | Морской кадетский корпус; `amenity=school` | Polygon | YES | YES | NO | N/A | NO / NO / NO |
| Курортный | `way/206259111` | 10-я дорожка; `highway=residential` | LineString | YES | YES | NO | N/A | NO / NO / NO |
| Курортный | `way/1243420903` | Гимназия № 433; `amenity=school` | Polygon | YES | YES | NO | N/A | NO / NO / NO |
| Петродворцовый | `way/113106874` | 10 линия; `highway=residential` | LineString | YES | YES | NO | N/A | NO / NO / NO |
| Петродворцовый | `way/132911076` | Академическая гимназия СПбГУ; `amenity=school` | Polygon | YES | YES | NO | N/A | NO / NO / NO |
| Пушкинский | `way/107996505` | 10-я линия; `highway=residential` | LineString | YES | YES | NO | N/A | NO / NO / NO |
| Пушкинский | `way/82141716` | Воскресная школа; `amenity=school` | Polygon | YES | YES | NO | N/A | NO / NO / NO |

Equivalent road + school pairs were also verified in Приморский, Выборгский, and
Красносельский. Relation processing is not implicated in these ten losses. Separately,
the isolated import proved all 18 administrative relation geometries assemble.

## Pipeline diagnosis

| Stage | Finding |
|---|---|
| Source PBF | Remote roads and amenities exist. Source absence is rejected. |
| Extraction | The only successfully imported general-object profile is smoke-sized. This is the loss boundary. |
| Current staging | Exact remote identities are absent. |
| Derived | N/A for the traced ways; all 18 district relations assemble in the full extract. |
| Canonical | No binding can exist for identities missing from staging. No additional canonical loss was observed. |
| Categories | Current rules classify the same remote objects in isolated data. Category loss is rejected as the primary cause. |
| Map API | Valid requests return HTTP 200/empty remotely and populated controls centrally. API filtering is rejected. |
| Frontend | Data is absent before the frontend. Layer minZoom still controls normal visibility, but is not this defect. |

Root-cause classification: **B only for the primary remote-coverage defect**. Water
semantic incompleteness and full-import performance/lifecycle risks are separate
follow-up concerns, not evidence for A, D, E, F, or G.

## `spb_lo` suitability

`spb_lo` geometrically contains all 18 district geometries: **YES**. The district union
extent is `BOX(29.4257576 59.6337832,30.7594934 60.2448369)`, well inside the profile.

Immediate production suitability: **WITH CHANGES**.

- the bbox is about 160,185 km² versus 1,451.8 km² for the official 18-district union;
- it includes a large amount of unrelated Leningrad Oblast territory;
- its 204 MiB extract produced 3.89 million staging objects and a 59-minute import on
  the current local allocation;
- bbox profiles use `simple`; boundary-crossing ways can be incomplete at the profile
  edge, although all 18 district relations assembled in this audit;
- a complete coarse-profile canonical/category run is not currently operationally
  acceptable.

The existing profile is suitable as an audit/source baseline, not as the default
production coverage decision.

## Identity, idempotency, and lifecycle

Duplicate risk for a larger import of the same OSM source is **LOW**:

- staging keys are `(source_id, osm_id)` in type-specific node/way/relation tables and
  merge with `ON CONFLICT`;
- canonical bindings have a unique
  `(source_id, source_object_type, source_object_id)` constraint;
- canonical reconciliation uses exact source identity, not name or fuzzy geometry;
- integration tests prove repeated canonicalization reuses stable canonical IDs and
  updates `last_seen_import_run_id` without increasing revision when payload is
  unchanged.

Lifecycle/freshness risk before remediation is **HIGH**:

- profile absence intentionally never deletes or retires staging/canonical data; this
  is correct for partial extracts but means profile replacement cannot infer deletion;
- `_merge_work_tables` upserts objects present in the new extract and does not remove
  old rows outside its scope;
- `run_osm_category_pipeline` uses `bulk_create_osm_objects`, which only creates missing
  bindings. It does not run the changed/unchanged refresh behavior of
  `canonicalize_osm_objects` for existing bindings;
- category application re-evaluates existing bindings, but stale candidate
  name/geometry/property payloads can remain unless an explicit canonical refresh path
  is used;
- the bulk creator's source-wide winner update repeats for every chunk and becomes a
  major full-area performance cost.

Therefore a same-version larger import should reuse identities without duplicates, but
S3R must explicitly define refresh scope, freshness markers, disappearance semantics,
and rollback before production execution.

## Recommended remediation

Next task: **F5.5-S3R — Production Saint Petersburg Coverage Import**.

Recommended geographic target: all 18 official Saint Petersburg districts, with an
explicitly chosen small operational buffer only if product requirements justify it.
Do not silently adopt the existing coarse `spb_lo` box.

S3R should:

1. add a dedicated full-city profile derived from the official district/city geometry,
   while keeping `spb_smoke`, `spb_lo`, and `spb_districts` semantics unchanged;
2. choose and validate relation/way closure for the new profile under the 4 GiB
   allocation, retaining explicit incomplete-geometry diagnostics;
3. harden canonical bulk refresh so work is scoped to the current identity chunk and
   existing identities refresh without duplication;
4. define explicit import scope/provenance and disappearance handling instead of using
   absence from a partial extract as deletion;
5. rehearse extract, import, canonicalization, classification, rollback, and timing in
   an isolated DB;
6. perform production import only after district-by-district count, API, search,
   idempotency, and performance acceptance;
7. retain the existing API/frontend contracts; no category-specific importer rewrite
   is required.

The current architecture can support a new profile through generic staging,
canonical identity, classification, API, and frontend layers. The blockers are
coverage-scope selection, bulk performance, and explicit refresh/lifecycle semantics,
not application-category coupling.

## Safety and limitations

Initial resources were 225 GiB free disk, 2 Docker CPUs, and 4 GiB Docker memory. The
main DB was 1,120 MiB. The isolated DB peaked at several GiB and was never used by the
application.

One over-broad temporary candidate-materialization query in the isolated database
exhausted the shared PostgreSQL allocation and caused PostgreSQL crash recovery. It did
not commit production DML. Recovery was immediately verified with:

- `pg_isready` accepting connections;
- Alembic still at `20260925_0007`;
- 257,047 active canonical objects;
- 18 enabled districts;
- backend readiness reporting database/PostGIS/migrations ready;
- backend, database, and frontend containers healthy.

All subsequent comparison queries were district-scoped, limited to 8 MiB `work_mem`,
and completed without another incident. The incident is additional evidence against a
coarse one-shot `spb_lo` production workflow on this allocation.

The audit did not change product code, API behavior, frontend behavior, category rules,
minZoom, feature limits, or main database content. It did not start F5.5-S4, S5, S6,
S7, or F6.

Regression completed after the audit:

- 19 relevant backend OSM/catalog/map/search tests passed against the disposable DB;
- the frontend baseline passed (1 file, 2 tests);
- `git diff --check` passed.

After the measurements and regression run, the exact disposable database
`kartaspb_coverage_audit_s3` was dropped to remove the partial 50,000-object catalog
and recover its 2.3 GiB. It can be rebuilt from the retained source and diagnostic
`spb_lo` cache; the main database and Docker volume were not deleted.
