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
one user-selected metric at weight 100. F11A reuses the same immutable delivery protocol
for an explicit eight-dimension Scenario Builder; it does not introduce hidden/default
weights or scenario persistence. See [scenario-builder.md](scenario-builder.md).

The overlay is default off and starts at zoom 11. Both its vector source and fill layer
declare `minzoom: 11`, so normal product rendering does not request heatmap tiles below
the supported floor. The backend remains capable of serving z10 for diagnostics. This
floor does not automatically change the user's zoom.

F10-R2 separates the analytical score from its display transform. The score, F9 run,
scoring signature, heatmap spec, tile request, and MVT bytes remain unchanged when the
user changes contrast. Only the MapLibre `fill-color` paint expression changes. Three
presets are available:

| Contrast | Display range |
| --- | ---: |
| Low | 0–100 |
| Medium | 25–100 |
| High (default) | 40–100 |

Values at or below the display minimum use the minimum color and values at or above the
maximum use the maximum color. The legend shows the active values; for the default they
are 40, 55, 70, 85, and 100. This changes color sensitivity only and never rewrites an
analytical score. The palette remains:

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

The resolution prototype offers Auto, 200 m, and 50 m. A selection changes the real
`grid_version`, metric score runs, and tile source; it never subdivides or interpolates a
coarser score. The rehearsed Auto hypothesis is 200 m below z13 and 50 m at z13 and above.
The optional technical grid outline remains a separate control and continues to show the
production 200 m grid until a resolution-aware outline API is explicitly added.

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
cells. The isolated rehearsal met the original z10 and z11 limits.

The first production rollout on 2026-10-07 was intentionally rolled back after cold z10
requests exceeded the original 1.5-second gate: school took 2.544 seconds and the
all-metric case took 1.609 seconds. This was an operational product-floor decision, not a
correctness or architectural failure. Production z11 cold results remained comfortably
inside the accepted 1-second limit (school 0.157 seconds, family 0.554 seconds, all-metric
0.608 seconds), so F10-R1 adopts the architecture's documented fallback and makes zoom 11
the supported frontend minimum. z10 is diagnostic only and is no longer a production
acceptance gate; z11 cold below 1 second and warm below 300 ms are authoritative.

The F10-R1 production-shaped rehearsal then measured z11 cold/warm results of
177/75 ms for school, 269/244 ms for the family profile, and 286/286 ms for all twelve
metrics. The first all-metric warm observation was a 305 ms boundary outlier; four of the
next five identical warmed requests were below 300 ms and the five-sample median was
286 ms. z12 cold/warm results were 22/22 ms, 114/118 ms, and 148/181 ms respectively.
All responses remained byte-identical and retained the accepted signatures and sizes.

HTTP rehearsal confirmed correct MVT media type and identity/cache headers, empty-tile
behavior, rejection of a mismatched signature, and zero changes to grid, F8, and F9 table
counts. Interactive browser visual QA remains a production-rollout gate; automated UI,
overlay lifecycle, API, TypeScript, lint, and production-build checks cover the current
implementation checkpoint.

## F10-R2 50 m rehearsal

The isolated production-shaped rehearsal generated 580,597 genuine 50 m cells covering
18/18 districts, then calculated 12 F8 raw runs and 12 F9 v1 normalized runs. Each layer
contains 6,967,164 values. No 200 m value was interpolated. The grid checksum is
`41e8dd7827ae1d965f0a6bfa5c5d7f9694959ac7f1d039479c4b2d2ac5f026ea`.

The tile path was hardened so immutable run metadata is resolved without recounting every
score row for every tile. Atomic publication, append-only guards, stored cell counts, and
the full scoring evaluation completeness check remain in force. With that fix, all three
50 m cases met the cold <1 second, warm <300 ms, and <1.5 MiB hard gates:

| z | Cells | School cold/warm | Family cold/warm | All 12 cold/warm | Largest tile |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 12 | 9,781 | 265/176 ms | 644/404 ms | 542/592 ms | 703 KiB |
| 13 | 2,496 | 50/49 ms | 109/109 ms | 152/110 ms | 185 KiB |
| 14 | 650 | 13/12 ms | 22/19 ms | 26/22 ms | 48 KiB |
| 15 | 174 | 6/6 ms | 10/9 ms | 11/10 ms | 13 KiB |

Representative z13 `EXPLAIN ANALYZE` completed in 151 ms, selected 2,496 cells spatially,
and joined 29,952 score rows for the 12-metric case. See
[multi-resolution-analysis.md](multi-resolution-analysis.md) for generation, storage,
25/10 m feasibility, and normalization-saturation evidence.

## Stage boundary

F10 does not define a recommended composite or persist scenarios. F11A adds only an
ephemeral, explicit-weight personal scenario over eight smooth-accessibility inputs. Saved
scenario names, durable preferences, comparisons, and product policy for recommended
presets remain outside F11A. The F10-R2 50 m grid/runtime rollout is complete; F11A's new
metric publications, migration 0015, and Scenario Builder rollout each remain explicit
production actions.
