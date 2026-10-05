# Existing-data metrics v1

F8 defines twelve raw, citywide metrics for the accepted
`spb-square-200m-v1` analysis grid. The implementation uses the universal F7
publication tables; it adds no migration, metric-specific table, or metric-specific
column. Production publication and backend rollout remain a separate, explicitly
authorized step.

## Metric definitions

| Metric key | Meaning at the cell center | Unit | Source category |
|---|---|---:|---|
| `education.school.distance_m` | Nearest school geometry | m | `education.school` |
| `education.school.count_1000m` | Schools within 1,000 m | count | `education.school` |
| `education.kindergarten.distance_m` | Nearest kindergarten geometry | m | `education.kindergarten` |
| `education.kindergarten.count_1000m` | Kindergartens within 1,000 m | count | `education.kindergarten` |
| `healthcare.hospital.distance_m` | Nearest hospital geometry | m | `healthcare.hospital` |
| `healthcare.clinic.distance_m` | Nearest clinic geometry | m | `healthcare.clinic` |
| `healthcare.pharmacy.distance_m` | Nearest pharmacy geometry | m | `healthcare.pharmacy` |
| `healthcare.pharmacy.count_1000m` | Pharmacies within 1,000 m | count | `healthcare.pharmacy` |
| `nature.park.distance_m` | Nearest park geometry | m | `nature.park` |
| `nature.water.distance_m` | Nearest water geometry | m | `nature.water` |
| `transport.stop.distance_m` | Nearest public-transport stop | m | `transport.stop` |
| `transport.stop.count_500m` | Public-transport stops within 500 m | count | `transport.stop` |

All definitions use definition version `1` and calculation version
`catalog-spatial-v1`. The registry contains only these enabled definitions.

## Spatial semantics

Both providers work in EPSG:32636 from each analysis cell's `center_metric`:

- `catalog.nearest_distance` uses indexed KNN candidate selection followed by exact
  `ST_Distance` from the cell center to the complete target geometry;
- `catalog.count_within_radius` uses indexed `ST_DWithin` and counts each logical
  target once.

Point, line, polygon, and multipolygon targets retain their real geometry. Distance is
not measured to a target centroid. A cell center inside a polygon therefore has distance
zero.

Active categorized objects that belong to an active logical facility collapse into one
target. Its stable facility UUID is the logical identity and its
`analysis_object_id` supplies geometry. Categorized objects outside an active facility
remain individual targets. Inactive objects, assignments, members, and facilities are
excluded. Missing, empty, invalid, or wrong-SRID analysis geometry fails the calculation
closed rather than silently reducing coverage.

## Reproducibility

Each provider calculates its own SHA-256 input fingerprint inside the same PostgreSQL
`REPEATABLE READ` snapshot as the values. The fingerprint covers:

- grid version and deterministic ordered grid checksum;
- source category;
- ordered logical target kind and UUID;
- analysis object UUID;
- ordered contributing canonical object UUIDs;
- metric-CRS EWKB of the effective target geometry.

Provider configuration is included in the immutable definition checksum. Together the
definition checksum and input fingerprint determine the F7 run signature. Identical
source state returns the existing immutable run; a source or definition change creates a
new run and moves only the current pointer.

## Isolated real-data rehearsal

The twelve definitions were calculated against an isolated restore of the accepted
production-shaped catalog and all 36,292 cells. Production was not mutated. Target
resolution returned: school 1,074; kindergarten 1,641; hospital 173; clinic 692;
pharmacy 2,546; park 1,582; water 4,332; and transport stop 18,600.

The first pass created twelve immutable runs and 435,504 raw values. A complete second
pass returned `unchanged` for all twelve definitions with the same UUIDs, fingerprints,
and value checksums, leaving twelve historical runs and twelve current pointers. No
calculation exceeded 3.7 seconds; the twelve provider calculations totaled about 19.9
seconds on the rehearsal environment.

`EXPLAIN ANALYZE` on the largest 18,600-target category confirmed the temporary GiST
index is used: nearest-distance performed one KNN index lookup per cell and completed in
1.403 s; the 500 m count used a bitmap GiST index scan with `ST_DWithin` filtering and
completed in 0.698 s. No provider forms a full cell-by-target Cartesian product.

A controlled rehearsal-only pharmacy assignment change reduced its logical target set
from 2,546 to 2,545. The pharmacy-distance fingerprint changed from
`31aa6a089c7ec0c9a57ade9b9643f3f9bda59a7545c0747f1c2468078f7a45cf` to
`b0e2a96d40c2073650438f4ff5069658b6d9683cfc6cb48901b2bb54fdde1e79`, created a
new immutable run, retained the original run, and advanced the current pointer. This
change occurred only in the disposable rehearsal database.

## Limitations

- Distance is geometric metric distance, not walking distance or travel time.
- School proximity measures accessibility, not school quality.
- Stop proximity/count measures physical stops, not route availability or service
  frequency.
- Park proximity does not measure park quality, access entrances, or usable area.
- Water proximity is contextual and is not automatically positive suitability.
- No road, traffic, air-quality, or noise penalty exists yet.
- Raw values are not normalized or scored. F9 owns normalization and scoring.
- F8 adds no heatmap, scenario logic, metric picker, or public bulk raw-values API.
