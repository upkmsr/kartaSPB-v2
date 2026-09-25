# Query performance acceptance

These measurements are local acceptance evidence for the current `spb_smoke` catalog,
not a production SLA. The measured catalog contained 257,047 active objects, including
30,937 named objects. Plans were collected with PostgreSQL 17 and PostGIS 3.5.

## Canonical search

The initial F5A2.1 query combined substring and fuzzy trigram predicates with `OR`. For
`аптека`, PostgreSQL chose a sequential scan (268.8 ms for the candidate-only plan),
and the complete ranked request took roughly 371–441 ms warm. Some terms paid a larger
trigram recheck cost.

F5A2.2 uses one deterministic substring candidate branch backed by
`ix_catalog_objects_search_name_trgm`. Trigram similarity ranks those candidates; it is
not a second fuzzy candidate branch. Primary-key lookup is forced after the candidate
set, and representative geometry is computed only for the final top-N objects.

Warm top-20 timings from three consecutive requests were:

| Query | Warm range |
| --- | ---: |
| `школа` | 79–88 ms |
| `аптека` | 26–27 ms |
| `парк` | 31–32 ms |
| `невский` | 43–94 ms |
| `энергетиков` | 25 ms |
| `озерки` | 21–22 ms |

Category-scoped warm requests measured 98–109 ms for `школа` in
`education.school` and 30–32 ms for `аптека` in `healthcare.pharmacy`.
District-scoped `невский` measured 37–45 ms warm. Normal warm searches therefore
pass the local 200 ms sanity target. First access after cold data pages can be slower.

## Map transport stops

Dense line and stop categories use a spatial-first plan; selective school, healthcare,
and nature categories retain the category-first plan. Spatial candidates and category
IDs are materialized separately, then hash-joined. This prevents PostgreSQL from scanning
all canonical objects for `transport.stop` and avoids thousands of per-object category
index probes when the viewport estimate is low.

For viewport `30.30,59.93,30.34,59.95` (representative of the stop layer's zoom range),
both plans returned the same 135 objects:

| Strategy | Execution time | Relevant indexes |
| --- | ---: | --- |
| Previous category-first | 3908 ms | category index, followed by catalog seq scan |
| Spatial-first + category hash | 226 ms | geometry GiST and category index |

The accepted plan is about 17 times faster in this measurement. On the deliberately
larger `30.30,59.90,30.41,59.97` viewport it remained faster (about 0.9 s versus 3.5 s),
while returning the same 1,254 stops.
