# Dynamic heatmap

F10 renders explicit F9 weighted scores as vector tiles. It introduces no database
migration, stored composite, implicit city score, or saved user scenario. The database
remains the F8/F9 publication model at Alembic `20261005_0014`; F10 is a stateless read
and delivery layer over immutable normalized score runs.

## Request and immutable identity

`POST /api/analysis/heatmap/prepare` accepts the same explicit metric-weight mapping as
the F9 scoring API. The backend validates it, resolves every metric to its current
immutable normalized run, and returns:

- the deterministic F9 scoring signature and summary statistics;
- an opaque, versioned heatmap spec;
- a vector-tile URL template containing both identities;
- the exact metric keys, weights, normalized run IDs, and run signatures used.

The spec is canonical JSON encoded as unpadded base64url. It is bounded to 4 KiB after
decoding and at most 12 metrics, and contains no SQL or arbitrary expression. Metric
order in the request does not affect either the canonical spec or signature.

Tile requests decode the spec and resolve the exact historical normalized run IDs
recorded at prepare time. A later change to a current-run pointer therefore does not
silently change an already prepared map. An unknown run, metric/run mismatch, grid
mismatch, malformed spec, or path/signature mismatch is rejected rather than substituted.

## Tile delivery

`GET /api/analysis/heatmap/tiles/{signature}/{z}/{x}/{y}.mvt?spec=...` returns Mapbox
Vector Tiles with source layer `analysis_heatmap`. Each feature exposes only stable cell
identity, district identity, and the weighted `score` in `0..100`.

The query is spatial-first: it selects cells intersecting the tile through the analysis
cell GiST index before joining the selected score runs. The weighted result is calculated
with order-independent numeric accumulation, and encoded rows are ordered by cell ID so
repeated requests are byte-identical. Empty tiles are valid zero-byte MVT responses.

Responses include immutable public caching, a content ETag, the scoring signature, and
delivery version `heatmap-mvt-v1`. The prepare endpoint itself does not persist state;
all identity needed to reproduce a tile is carried by the validated immutable spec.

## Frontend contract

The sidebar exposes a separate `HeatmapControl`. In F10 it intentionally prepares only
one user-selected metric at weight 100. The backend supports arbitrary valid explicit
multi-metric weights so F11 can build scenarios without changing the delivery protocol,
but F10 does not expose hidden/default weights or scenario persistence.

The overlay is default off and starts at zoom 10. It uses fixed absolute score colors:

| Score | Color | Meaning |
| ---: | --- | --- |
| 0 | `#d73027` | worse |
| 25 | `#fc8d59` | |
| 50 | `#fee08b` | |
| 75 | `#91cf60` | |
| 100 | `#1a9850` | better |

The fill opacity is 0.72. The heatmap is installed below the analysis grid and catalog
objects, is non-selectable, and never participates in catalog viewport loading. It is
restored after a MapLibre style reload. Hiding it removes its source/layer; a failed new
prepare leaves an already active overlay intact. State is deliberately not persisted.

## Rehearsal acceptance

The production-shaped rehearsal used a read-only production dump with 36,292 grid cells,
12 current F8 raw runs, and 12 current F9 normalized runs. Three representative requests
were tested: school distance only, a multi-metric family profile, and all 12 metrics.
Every prepared result covered the complete grid and every repeated tile was byte-identical.

Warm MVT results at the representative city-centre tile were:

| Selection | z10 | z11 | z12 |
| --- | ---: | ---: | ---: |
| School distance | 112 ms / 452 KiB | 30 ms / 166 KiB | 10 ms / 42 KiB |
| Family profile | 278 ms / 500 KiB | 190 ms / 181 KiB | 70 ms / 47 KiB |
| All 12 metrics | 332 ms / 506 KiB | 158 ms / 184 KiB | 86 ms / 48 KiB |

At z11, `EXPLAIN ANALYZE` completed the all-metric SQL in 89 ms, selected 2,475 tile
cells via the geometry index, and joined 29,700 score rows rather than scanning all city
cells. All accepted limits were met, including the z11 preferred target below 300 ms and
the z10 hard limits below 1.5 seconds and 1.5 MiB.

HTTP rehearsal confirmed correct MVT media type and identity/cache headers, empty-tile
behavior, rejection of a mismatched signature, and zero changes to grid, F8, and F9 table
counts. Interactive browser visual QA remains a production-rollout gate; automated UI,
overlay lifecycle, API, TypeScript, lint, and production-build checks cover the current
implementation checkpoint.

## Stage boundary

F10 does not define a recommended composite or persist scenarios. F11 owns scenario
names, saved weight sets, comparison, and any product policy for multi-metric presets.
Production backend/frontend rollout of F10 requires separate explicit authorization.
