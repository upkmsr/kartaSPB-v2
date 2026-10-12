# UX & Map Engine 2.0 — R1

R1 separates analytical exploration from composite suitability without changing any
published F8/F9 value. It was implemented on `feature/ux-map-engine-2-r1` from baseline
`51c42d1`. Production schema, analytics pointers, backend, and frontends were read-only
during implementation and acceptance.

## Analysis modes

`Слои влияния` renders up to eight immutable normalized score channels from one vector
source. Every channel keeps its own enabled state, minimum visible score (0–99), fixed
color, source-object toggle, and score-run identity. Changing a threshold is a MapLibre
filter/paint update; it does not call prepare and cannot alter another channel. Draw order
is the factor registry order. Per-layer opacity is bounded as more channels are enabled,
and an explicit accent can mute the other channels. The inspector reports every enabled
score, threshold, visibility result, and immutable run ID; it does not synthesize a
combined score.

`Общий анализ` keeps the accepted weighted F11A-R3 formula and immutable heatmap spec.
The former contrast choices are replaced by one minimum displayed score (0–99), with 100
as the fixed upper bound. Scores below the minimum are transparent. The overlay opacity is
0.36, so OpenFreeMap roads and labels remain visible. A zero-weight scenario has no
residual overlay.

The two modes persist independent state in the versioned analysis preference document.
Only the active mode is installed on the map. The sidebar tabs only change layout and do
not own object, district, viewport, inspector, or analytical state.

## Read-only API

R1 adds:

- `POST /api/analysis/influence/prepare`, accepting 1–8 unique scenario metric keys and a
  supported grid version;
- `GET /api/analysis/influence/tiles/{signature}/{z}/{x}/{y}.mvt`, returning one
  deterministic `analysis_influence` layer with `score_0` … `score_7` channels.

The canonical spec contains historical score-run UUIDs and can be reproduced without
following a later current pointer. Unknown metrics, duplicate keys, more than eight
channels, non-canonical weights, signature mismatch, and out-of-range tiles are rejected.
The existing heatmap endpoints remain compatible.

## City overview and resolution

Both analytical sources start at z8. For z8–10 the backend groups existing 200 m cells by
stable grid buckets and district, collecting their geometries and averaging scores:

| Zoom | Bucket | Effective overview size |
| ---: | ---: | ---: |
| 8 | 8 × 8 | 1,600 m |
| 9 | 4 × 4 | 800 m |
| 10 | 2 × 2 | 400 m |

Independent mode averages each channel independently. Composite mode averages the final
weighted score, which is mathematically equivalent to averaging complete component scores
under fixed weights. z11–12 returns genuine 200 m cells; z13+ may use genuine 50 m cells.
No grid borders are rendered. Overview IDs are synthetic and therefore score explain is
enabled only at z11+, where real cell IDs are present.

The initial camera is z9.2 and, once the authoritative 18-district list loads, performs a
one-time fit to their combined API bboxes. A user navigation made before that response is
never overwritten. `Авто` uses 200 m below z13 and 50 m from z13. A manually selected
50 m mode safely falls back to 200 m below z13 rather than requesting a citywide 50 m
overview. Zooming beyond the available 50 m data smooths rendering only and is not
presented as 25/10 m analytical precision.

## Measured overview performance

Measurements used the production-shaped database through a connection forced to
`default_transaction_read_only=on`. All eight R3 dimensions were selected. Repeated tile
bytes were identical, and F8/F9 table counts before and after were unchanged.

| Mode | Zoom | Bytes | Cold | Warm |
| --- | ---: | ---: | ---: | ---: |
| independent, 8 channels | 8 | 222,198 | 1,167 ms | 930 ms |
| independent, 8 channels | 9 | 154,303 | 281 ms | 196 ms |
| independent, 8 channels | 10 | 440,006 | 187 ms | 210 ms |
| independent, 8 channels | 12 | 112,852 | 18 ms | 14 ms |
| composite, 8 weights | 8 | 144,596 | 1,164 ms | 1,012 ms |
| composite, 8 weights | 9 | 90,162 | 268 ms | 257 ms |
| composite, 8 weights | 10 | 246,950 | 224 ms | 221 ms |
| composite, 8 weights | 12 | 49,366 | 18 ms | 17 ms |

Mode A uses one MVT request per visible tile rather than eight factor-specific requests.
The exact visible-tile count and compressed transfer volume depend on viewport size,
device pixel ratio, and MapLibre cache state; they require preview browser network
measurement and are intentionally not claimed from the server benchmark alone. z8 is the
known latency edge; z9–10 is the preferred initial overview range.

## Loading preferences

Map-loading storage is schema v3. The presets are:

- `Экономичный`: manual catalog loading, 200 m analytics, catalog min-zooms +1;
- `Сбалансированный`: automatic loading, Auto analytics, accepted catalog min-zooms;
- `Подробный`: automatic loading, 50 m analytics where supported, catalog min-zooms −1.

Offsets are bounded and apply only to catalog sources. Auto/manual loading and analytical
detail remain independently adjustable after applying a preset. The catalog road overlay
is off by default while OpenFreeMap roads remain unchanged. The technical analysis-grid
layer remains available to backend/debug code but is omitted from normal controls.

## Park and water diagnosis

Read-only checks found representative small, medium, and large parks in the catalog and
their v2 accessibility scores. A nearby small square retains a non-zero local effect; the
v2 provider intentionally applies a diminishing area-quality factor, so it is not equal to
a major park. The main observed visibility loss was the previous shared display threshold,
not missing geometry. Independent per-factor thresholds expose this local influence
without changing the provider or republishing metrics.

The water catalog contains polygon park ponds, and hundreds of water/park intersections
were found. Representative named ponds also have non-zero water scores. Park and water
are separate channels and may overlap; neither excludes the other. The previous shared
threshold could hide small-water influence. No snapshot correction or metric publication
was justified by the examined cases.

## Sub-50 m feasibility

The existing bounded study in [multi-resolution-analysis.md](multi-resolution-analysis.md)
remains authoritative: full-city 25 m is about 2.32 million cells and is technically
plausible only after a dedicated capacity/value decision; full-city 10 m is about 14.5
million cells and should remain local/on-demand. The current production relations occupy
about 415 MiB for both existing grids, 3,595 MiB for raw values, and 5,212 MiB for scores.
Linear full-city persistence with 20 current raw and normalized metrics would put 25 m in
the rough tens-of-GiB class and 10 m well above 100 GiB before WAL, build workspace, and
backup capacity. R1 creates neither grid and publishes no values.

## Preview acceptance boundary

Static, unit, integration-contract, lint, type, production-build, and worker checks can be
completed on this branch. Full visual acceptance still requires a separately authorized
preview rollout on port 15174 and browser checks at 1280×720, 1366×768, 1920×1080, and a
narrow mobile viewport. That gate must verify OpenFreeMap readability, overlap blending,
sidebar stacking/scrolling, selection persistence, city overview, network request count,
search, and ObjectDetail. HTTP or bundle inspection alone is not a visual PASS.
