# Smooth accessibility metrics

F11A adds eight generic accessibility inputs without changing canonical objects or
persisting a composite scenario. Each input is an immutable F8 metric run calculated for
every cell of a selected analysis grid, then published through the existing F9
normalization pipeline.

## Provider contract

The reusable provider key is `catalog.smooth_influence`. It resolves the same logical
catalog targets as the established distance/count providers, including facility collapse,
and calculates the compact quartic kernel for each target inside radius `R`:

```text
u = distance / R
influence = (1 - u²)², when u < 1
influence = 0, otherwise
cell value = sum(influence)
```

The kernel reaches zero continuously at the configured support boundary. PostGIS performs
the bounded `ST_DWithin` candidate lookup and distance calculation; there are no Python
cell loops and no nearest-only shortcut. The run fingerprint includes the grid identity,
catalog/category evidence, provider version, category, and radius, so a changed analytical
input produces a new immutable run while an identical rerun remains idempotent.

The v1 dimensions are explicit configuration:

| Scenario dimension | Metric key | Category | Radius |
| --- | --- | --- | ---: |
| Детские сады | `education.kindergarten.accessibility_index` | `education.kindergarten` | 1,000 m |
| Школы | `education.school.accessibility_index` | `education.school` | 1,400 m |
| Общественный транспорт | `transport.stop.accessibility_index` | `transport.stop` | 700 m |
| Поликлиники | `healthcare.clinic.accessibility_index` | `healthcare.clinic` | 2,000 m |
| Больницы | `healthcare.hospital.accessibility_index` | `healthcare.hospital` | 4,000 m |
| Аптеки | `healthcare.pharmacy.accessibility_index` | `healthcare.pharmacy` | 1,000 m |
| Парки | `nature.park.accessibility_index` | `nature.park` | 1,800 m |
| Вода / набережные | `nature.water.accessibility_index` | `nature.water` | 2,000 m |

These radii are product v1 parameters, not claims about travel time. All distance is
straight-line metric distance in EPSG:32636. Network travel, entrances, capacity, quality,
opening hours, and official-service evidence are separate future inputs.

## Normalization and interpretation

Each raw influence sum is normalized by a versioned, monotone piecewise-linear profile.
The profiles were calibrated from genuine 50 m and 200 m rehearsal distributions rather
than copied from the older nearest/count metrics. Exact score 100 was 0% for all eight
new metrics on both grids; the share at or above 90 was approximately 2.87–5.00%. This
avoids a broad saturated plateau while retaining deterministic 0–100 scoring.

The resulting value means relative spatial access to one category under this kernel. It
is not a recommendation, district rank, overall quality score, or saved user scenario.

## Isolated rehearsal

The production-shaped rehearsal published 16 raw runs and 16 normalized runs: eight
metrics on 36,292 genuine 200 m cells and 580,597 genuine 50 m cells. That is 4,935,112
new raw values and 4,935,112 new normalized values. Repeated publication preserved the
same run identities and checksums. Five representative residential districts retained
meaningful differentiation for every metric.

The accessibility publications added about 1.25 GiB in the isolated database. They have
not been published to production. F11A production publication remains a separate,
explicitly authorized data rollout after migration `20261008_0015`.

## Boundary

F11A exposes these eight dimensions to an ephemeral Scenario Builder. It does not store
scenario names or weights, choose a default lifestyle, rank homes, add routing, or start
F11B. See [scenario-builder.md](scenario-builder.md) for the request and UI contract.
