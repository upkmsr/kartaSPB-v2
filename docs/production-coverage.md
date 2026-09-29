# Saint Petersburg production coverage

Status: production import and physical visual QA accepted on 2026-09-29. The
authoritative `spb_city` snapshot is active in the main database.

## Locked source and scope

The `spb_city` profile is the production-capable ordinary-object scope. It is locked to:

- `data/sources/osm/northwestern-fed-district-20260921T231045Z.osm.pbf`;
- source version `20260921T231045Z`;
- SHA-256 `ebd1ac7b344c091a9190089422c75b8b704eaaacdc5f93ab5046bab16732925f`;
- Saint Petersburg parent administrative relation `337422`;
- no geographic buffer.

The scope polygon is generated deterministically from relation `337422` in the locked
source. It does not depend on the canonical catalog and does not use the historical
`spb_lo` bounding box. The pipeline first runs an exact polygon `simple` selection, then
uses osmium to retain selected ways, supported area/route relations, route-master
parents, and all references available in the locked regional source. This targeted
closure avoided the memory failure of an unrestricted `smart` extraction on the local
2 CPU / 4 GiB Docker allocation.

The final extract deliberately has a broad metadata bbox because reference-complete
route/relation members can lie outside the city. The geographic selection itself is the
exact relation polygon. No arbitrary Leningrad Oblast buffer is added.

Measured deterministic extract:

| Measure | Result |
|---|---:|
| Size | 61,385,155 bytes (58.5 MiB) |
| SHA-256 | `edd61cf412abc1fe6cb3d18591393d6d9b6f33391df9d4fd4c856b87f9ba4ad6` |
| Nodes in PBF | 4,883,373 |
| Ways in PBF | 850,481 |
| Relations in PBF | 52,166 |
| Missing nodes referenced by ways | 0 |
| Wall time | 93.01 seconds |
| Peak osmium memory | 2,030 MiB |

The parent relation, all 18 `admin_level=5` district subareas, ten S3 remote acceptance
ways, representative central objects, and the references needed by current geometry
assembly are present. Some relation references point outside the Northwestern source
PBF; osmium returns status 1 for those unavailable external members, and the pipeline
retains every reference available in the locked source rather than silently changing
source snapshots.

## Import provenance and lifecycle

Global OSM identity remains `(source_id, OSM type, OSM ID)`. Profiles never duplicate
the raw staging or canonical identity. `meta.osm_profile_memberships` records which
profile snapshot observed an identity, with first/last import run and present/missing
state. `meta.import_runs` records source version/checksum, profile, authoritative flag,
status, timestamps, counts, details, and lifecycle-finalization time.

An authoritative refresh progresses through `running -> staged -> success`. Raw
staging, derived geometry, canonicalization, and classification must finish before the
single final lifecycle transaction. Only that transaction may:

1. mark identities absent from the new successful same-profile snapshot as missing;
2. mark a source binding missing when no other authoritative profile still observes it;
3. reconcile affected categories and canonical object activity;
4. publish the run as successful with `lifecycle_finalized_at`.

A failed or interrupted run never performs absence reconciliation. Existing objects and
UUID bindings therefore remain valid. Canonical refresh is driven by explicit 10,000-ID
batches with bigint staging joins; it does not repeat a source-wide winner update for
every batch. Category refresh is also candidate-scoped and deactivates only assignments
no longer produced by the current rules.

## Commands

Verify the registered source checksum before every extraction. The normal commands are:

```bash
docker compose run --rm ingest extract --region spb_city
docker compose run --rm ingest refresh --region spb_city
```

`import --region spb_city` is intentionally rejected: authoritative profiles must use
the complete `refresh` path. Production execution additionally requires the explicit
approval gate, a verified custom-format backup, a pre-import snapshot, current code/CI,
and sufficient disk.

## Isolated rehearsal

The production database was restored into `kartaspb_s3r_rehearsal`; migration
`20260928_0008` was applied only there. The main database remained at `20260925_0007`
with 257,047 active objects throughout rehearsal.

Accepted identical snapshots:

| Measure | First accepted run | Second accepted run |
|---|---:|---:|
| Import run | 332 | 333 |
| Wall time | 28:46 | 19:10 |
| Staging identities | 1,372,973 | 1,372,973 |
| Staging inserted / updated | 0 / 0 | 0 / 0 |
| Category candidates | 407,544 | 407,544 |
| Canonical objects created | 0 | 0 |
| Rule matches | 411,346 | 411,346 |
| Active assignments | 417,332 | 417,332 |
| Missing memberships / bindings / affected objects | 0 / 0 / 0 | 0 / 0 / 0 |
| Canonical/category phase | 758.2 s | 499.6 s |

The realistic baseline transition created the new city objects before these two final
accepted passes. Afterward there were 417,331 active canonical objects, 416,538 active
non-boundary objects, and no duplicate source identities, category assignments, or
category provenance rows. All six established UUID controls and all ten newly introduced
remote UUIDs stayed unchanged on the second successful run. All 18 district UUIDs stayed
unchanged.

A controlled candidate-discovery cancellation and a later rejected category pass both
left `lifecycle_finalized_at` empty and preserved old active objects. The latter exposed
a PostgreSQL backend `SIGPIPE` recovery (not an OOM or container restart) while an
external diagnostic session was active. Category write churn was removed, diagnostic
concurrency was eliminated, and both accepted end-to-end runs then completed without a
database crash, restart, or OOM. Observed database memory was about 1.63 GiB under the
3.81 GiB container limit; global PostgreSQL memory settings were not changed.

## Accepted production execution

The main database was upgraded from `20260925_0007` to `20260928_0008` only after the
rehearsal, implementation push, green CI, verified backup, and explicit production
approval. Production refresh run `327` used the locked source and cached extract
checksums above. It completed with status `success`, `authoritative_snapshot=true`, and
`lifecycle_finalized_at=2026-09-29T09:48:22.320812Z`. PostgreSQL remained healthy with
zero container restarts and no OOM.

| Measure | Production result |
|---|---:|
| Started | `2026-09-29T09:24:54.161435Z` |
| Completed | `2026-09-29T09:48:22.320812Z` |
| Total wall time | 1,408.16 s (23:28.16) |
| Raw osm2pgsql phase | 143 s |
| Staging + derived phase | 676.57 s |
| Canonical + category phase | 731.42 s |
| Peak observed production DB memory | about 1.36 GiB of 3.81 GiB available |
| Run identities | 1,372,973 |
| Inserted / updated / unchanged | 575,572 / 1,129 / 796,272 |
| Run nodes / ways / relations / members | 471,068 / 849,739 / 52,166 / 600,689 |
| Relation geometries | 41,317 |
| Category candidates | 407,544 |
| Canonical objects created | 160,284 |
| Bindings processed | 407,546 |
| Rule matches / active assignments | 411,346 / 417,332 |
| Missing memberships / bindings / affected objects | 0 / 0 / 0 |

The current instrumentation records the raw osm2pgsql timing, the complete
staging/derived phase, and the combined canonical/category phase. It does not fabricate
separate derived, canonical, category, or finalization sub-timings; lifecycle
finalization is the final atomic transaction at the recorded completion timestamp.
Post-import `ANALYZE` was run on the affected staging, derived, provenance, canonical,
and category tables.

Final main-database counts are:

| Measure | Before S3R | After S3R |
|---|---:|---:|
| Staging nodes | 322,884 | 481,740 |
| Staging ways | 478,268 | 870,762 |
| Staging relations | 29,264 | 53,486 |
| Relation members | 307,268 | 611,123 |
| Derived relation geometries | 22,693 | 42,472 |
| Active canonical objects | 257,047 | 417,331 |
| Source bindings | 257,047 | 417,331 |
| Category assignment rows | 257,051 | 417,336 (417,332 active) |
| Inactive canonical objects | 0 | 0 |
| Database size | 1,120 MB | 1,858 MB |

There are zero duplicate source identities, category assignments, or category
provenance keys. Four historical category rows are inactive after deterministic rule
reconciliation; their canonical objects remain active and this is not object lifecycle
loss. All six established canonical UUID controls and all 18 district public/canonical
bindings are unchanged. All ten remote acceptance ways have active bindings and the
expected `education.school` or `transport.road` category.

## Coverage and runtime acceptance

Exact `ST_Intersects` counts populate all 18 districts. Each district's total is within
1% of the S3 `spb_lo` rule-equivalent reference. Small larger percentage differences in
individual low-count water/park cells come from exact no-buffer boundary selection versus
the coarse reference bbox; known non-exhaustive water semantics remain unchanged.

Final production matrix (active non-boundary objects and active category assignments):

| District | Total | School | Kindergarten | Pharmacy | Hospital | Clinic | Park | Water | Stop | Road |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Адмиралтейский | 18,349 | 60 | 73 | 111 | 13 | 29 | 127 | 50 | 404 | 17,482 |
| Василеостровский | 17,425 | 57 | 59 | 109 | 9 | 28 | 142 | 32 | 488 | 16,501 |
| Выборгский | 30,199 | 92 | 140 | 258 | 25 | 90 | 93 | 218 | 1,220 | 28,064 |
| Калининский | 24,188 | 71 | 117 | 169 | 11 | 43 | 70 | 59 | 910 | 22,738 |
| Кировский | 17,959 | 51 | 81 | 129 | 4 | 26 | 85 | 133 | 640 | 16,810 |
| Колпинский | 12,051 | 36 | 59 | 62 | 7 | 6 | 48 | 308 | 548 | 10,977 |
| Красногвардейский | 22,689 | 66 | 101 | 167 | 5 | 42 | 66 | 132 | 872 | 21,238 |
| Красносельский | 24,301 | 68 | 110 | 144 | 6 | 45 | 49 | 434 | 934 | 22,512 |
| Кронштадтский | 4,727 | 11 | 11 | 15 | 5 | 3 | 42 | 82 | 140 | 4,418 |
| Курортный | 14,478 | 18 | 30 | 39 | 12 | 6 | 73 | 311 | 671 | 13,318 |
| Московский | 32,099 | 70 | 116 | 183 | 6 | 54 | 120 | 152 | 820 | 30,578 |
| Невский | 30,469 | 90 | 164 | 220 | 14 | 43 | 84 | 98 | 903 | 28,854 |
| Петроградский | 15,679 | 46 | 61 | 69 | 11 | 56 | 109 | 110 | 343 | 14,874 |
| Петродворцовый | 17,645 | 29 | 36 | 57 | 7 | 13 | 73 | 448 | 704 | 16,278 |
| Приморский | 34,873 | 110 | 155 | 288 | 10 | 73 | 92 | 361 | 1,179 | 32,606 |
| Пушкинский | 25,657 | 58 | 72 | 81 | 8 | 21 | 97 | 544 | 788 | 23,988 |
| Фрунзенский | 28,416 | 59 | 104 | 170 | 5 | 25 | 78 | 49 | 692 | 27,234 |
| Центральный | 23,180 | 70 | 85 | 133 | 12 | 74 | 129 | 44 | 500 | 22,133 |

The five previously empty remote API controls now return 40, 51, 63, 39, and 19 features
for Kolpinsky, Kronshtadtsky, Kurortny, Petrodvortsovy, and Pushkinsky respectively.
All ten traced S3 ways have active canonical bindings and the expected school or road
category. Remote district search reaches all five named schools. Two OSM names contain a
non-breaking space after `№`; generic district-scoped `Гимназия` finds them, while a
query containing an ordinary space retains the pre-existing exact-substring limitation.
Search normalization/ranking was intentionally not changed in S3R.

Warm central search controls measured 24-107 ms. A city-scale road regression caused by
materializing all road category IDs was fixed by joining the bounded spatial candidate
set through the `(object_id, category_key)` key. The representative zoom-16 road request
improved from 4-7 seconds to 0.14-0.18 seconds while returning the same 319 features.

Production API acceptance returned HTTP 200 for every remote and central control. The
remote counts changed from `0 / 0 / 0 / 0 / 2` to `40 / 51 / 63 / 39 / 19`; the three
central controls remained `149 / 100 / 162`. Observed map latency was 0.14-0.82 seconds.
All five district-scoped remote search controls returned their expected named schools;
the standard `школа`, `аптека`, `парк`, `невский`, and `энергетиков` controls returned
results in 0.08-0.33 seconds.

Physical visual QA passed at 1280x800, 1440x900, and 1920x1080. Remote districts now
contain ordinary objects and roads, the old smoke cutoff is no longer apparent, central
districts still render normally, and district overlay, Layers, search, ObjectCard, and
map click remain functional.

Post-production regression passed: 90 backend/ingest tests, 64 frontend tests, Ruff,
strict mypy, Alembic model/migration parity, ESLint, TypeScript, ingest-tooling build and
version checks, production frontend build, and the MapLibre worker asset check.

## Production backup and rollback

The verified pre-production custom-format backup remains outside the repository at
`/private/tmp/kartaspb_s3r_preprod_20260929T091258Z.dump`. It is 150,227,266 bytes,
was created at `2026-09-29T09:13:48Z`, and has SHA-256
`87236cbd41f60a219cd910a822e0a315751b2bc101420cdb1a9126fe0cd2c1c9`.
`pg_restore --list` produced a valid 168-entry manifest. A full restore into a temporary
database succeeded, and representative staging, derived, canonical, binding, and
category counts exactly matched the pre-import main database. The temporary restore
database was removed; the backup itself was retained.

If extraction or refresh fails before finalization, stop and diagnose; do not run manual
absence updates. Consider a full restore only for identity corruption, unexplained data
loss, district corruption, uncontrolled duplicates, failed lifecycle semantics, or
persistent database instability. Minor style/UX issues are not rollback conditions.

Large PBFs, extracts, dumps, logs, and benchmark payloads remain outside Git.
