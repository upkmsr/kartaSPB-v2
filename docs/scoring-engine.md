# Normalization and scoring engine

F9 converts immutable F8 raw measurements into transparent 0–100 utility scores and
combines only the scores explicitly selected by a caller. It does not define an official
or implicit "KARTASPB score", persist user composites, or render a heatmap.

## Raw values and normalized scores

An F8 value describes a measurable fact such as distance to a school or the number of
stops within 500 metres. An F9 metric score describes the utility assigned to that value
by a versioned product curve. Raw values remain unchanged in `analytics.cell_metric_values`;
normalized values are separate immutable rows in `analytics.cell_metric_scores`.

Citywide min/max and percentile ranks are intentionally not used as product scores. Both
would change meaning when coverage or source data changes. F9 uses explicit
piecewise-linear curves whose anchors remain stable until a new `normalization_version`
is introduced. Values outside the anchors clamp to the nearest endpoint.

The v1 registry is `config/analytics/scoring/normalizations.json`. Its document and every
profile have deterministic SHA-256 checksums. Raw x coordinates are strictly increasing,
scores remain within 0–100, and score monotonicity must match the F8 metric direction.

## Product-default curves v1

| Metric | `(raw value → score)` anchors |
| --- | --- |
| `education.school.distance_m` | `0→100, 500→100, 1000→75, 1500→50, 2500→20, 4000→0` |
| `education.school.count_1000m` | `0→0, 1→50, 2→65, 3→75, 5→90, 8→100` |
| `education.kindergarten.distance_m` | `0→100, 300→100, 700→80, 1200→50, 2000→20, 3000→0` |
| `education.kindergarten.count_1000m` | `0→0, 1→40, 2→55, 4→75, 6→90, 10→100` |
| `healthcare.hospital.distance_m` | `0→100, 1000→100, 2500→80, 5000→50, 8000→20, 12000→0` |
| `healthcare.clinic.distance_m` | `0→100, 500→100, 1000→80, 2000→50, 4000→20, 8000→0` |
| `healthcare.pharmacy.distance_m` | `0→100, 300→100, 600→80, 1000→55, 2000→20, 3000→0` |
| `healthcare.pharmacy.count_1000m` | `0→0, 1→45, 2→60, 4→80, 8→95, 12→100` |
| `nature.park.distance_m` | `0→100, 300→100, 600→85, 1000→65, 1500→40, 2500→15, 4000→0` |
| `nature.water.distance_m` | `0→100, 300→100, 800→80, 1500→50, 3000→20, 5000→0` |
| `transport.stop.distance_m` | `0→100, 200→100, 400→85, 600→65, 1000→30, 1500→0` |
| `transport.stop.count_500m` | `0→0, 1→30, 3→50, 5→65, 10→85, 20→100` |

These are transparent product defaults, not scientific claims. Water proximity is an
optional utility and contributes only if a caller supplies it a positive weight.

## Immutable normalized publication

Migration `20261005_0014` adds exactly:

- `analytics.metric_score_runs` — immutable raw-run/profile publication metadata;
- `analytics.cell_metric_scores` — immutable normalized values per cell;
- `analytics.metric_score_current_runs` — mutable current pointers.

A score-run signature binds the metric, grid, immutable raw run, normalization version,
and profile checksum. Repeating the same publication is `UNCHANGED`; a changed raw run
or profile version creates a new run and retains history. Publication validates complete
grid coverage and commits the run, all values, and the current pointer atomically. DB
triggers reject updates or deletes to historical run/value rows.

## Explicit weighted scoring

Weights are independent from normalization. Every supplied weight must be finite and in
`0..100`; zero excludes a metric and at least one positive weight is required. Negative
weights, hidden weights, implicit metrics, and automatic correlation balancing are not
supported.

For the caller's selected metrics:

```text
combined score = sum(metric score × weight) / sum(weight)
```

The result remains in `0..100`. School distance and school count may be correlated, but
choosing both is an explicit product/scenario decision. F9 returns the exact weights,
current normalized runs, deterministic scoring signature, summary statistics, and a
bounded top-cell preview. Combined scores are not persisted.

The scoring signature hashes the grid plus ordered metric keys, current normalized-run
signatures, and exact weights. Equivalent maps in different input order produce the same
signature; changes to a weight or normalized run change it. F10 can use this identity for
tile caching, while F11 will own named scenarios and saved weight sets.

## Interfaces

```bash
python -m app.analytics.scoring validate
python -m app.analytics.scoring normalize-all
python -m app.analytics.scoring evaluate \
  --weight education.school.distance_m=100 \
  --weight nature.park.distance_m=50
```

The HTTP API exposes profile metadata at
`GET /api/analysis/scoring/normalizations`, individual profiles at the matching
`/{metric_key}` path, and bounded previews at `POST /api/analysis/scoring/evaluate`.
It never returns every city cell as JSON; F10 owns map delivery.

## F9 acceptance

The production-shaped rehearsal published 12 current normalized runs and 435,504 values.
An identical second run produced 12 `UNCHANGED` results. A profile-version change created
one new immutable run, retained the previous run, advanced only the pointer, and left F8
raw history unchanged. The three rehearsal composites covered all 36,292 cells; the
12-metric case completed in 0.234 seconds. Rehearsal normalized storage was 84 MiB.

The accepted v1 curves were not adjusted to make distributions visually uniform. In
particular, raw count sparsity produces many zero scores, while the water curve places a
large share of currently covered cells at 100. These are reported data/curve properties,
not hidden percentile normalization.

Production rollout completed on 2026-10-07 at Alembic `20261005_0014`. One authorized
`normalize-all` publication created exactly 12 immutable score runs, 435,504 cell scores,
and 12 current pointers. Every normalized-value checksum matched rehearsal; there were no
missing cells, invalid values, duplicate current pointers, or changes to F8 raw runs.
Normalized production storage was 86 MiB.

The accepted backend artifact was built from commit
`81fabf8173dd4526eebf50ccfffd8a490282da00`. All twelve normalization endpoints, raw
metric endpoints, grid and catalog regressions passed. The all-metric production scoring
request covered 36,292 cells in 1.111 seconds cold and 0.313 seconds warm, with the same
deterministic signature as rehearsal:
`d21049dc6d51bee82b94551dcc9cd9b94f98d84c3bacff888611eb577e6ed588`.

The pre-rollout recovery point is
`/private/tmp/kartaspb-f9-pre-20261007T102500Z.dump` (329,101,291 bytes; SHA-256
`a267006bc065b2b52936b6ea1d3c5a408de457ca4abb609ce93136f88273afce`), validated with
`pg_restore --list`. The previous backend image and stopped container remain available as
rollback checkpoints. F9 is complete. F10 now consumes these immutable runs without
changing them; its delivery contract is documented in [heatmap.md](heatmap.md).
