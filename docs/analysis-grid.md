# Analysis grid v1

F6 introduces a versioned, deterministic square grid for future analytical work. The
grid is infrastructure, not a metric or a score.

## Contract

- Version: `spb-square-200m-v1`
- Cell size: 200 metres
- Construction CRS: EPSG:32636
- API/display CRS: EPSG:4326
- Persistence: `analytics.analysis_cells`
- Coverage: the union of the 18 enabled Saint Petersburg district geometries
- Inclusion: the full square is retained when its metric-CRS centre is covered by the
  district union; boundary cells are not clipped
- District assignment: `ST_Covers` at the cell centre, with `display_order` and UUID as
  deterministic overlap tie-breakers
- Stable identity: `spb-square-200m-v1:<grid_i>:<grid_j>`

Each cell keeps both display and metric polygons and centres. The metric polygon is the
authoritative analytical geometry and must remain a valid 40,000 m² polygon. District
geometry continues to live in the canonical catalog; the grid stores only the stable
domain district UUID.

## Bootstrap

After applying Alembic revision `20261004_0012`, run:

```bash
python -m app.analytics.grid bootstrap
```

The command validates all 18 source geometries, generates the complete expected dataset
in a transaction, and prints a JSON report with counts, per-district distribution, bbox,
SHA-256 checksum, creation/idempotency counts, and duration. A second run verifies every
stored row and reports all cells unchanged. If an existing version is partial or differs
in identity, district assignment, or geometry, the command fails without repairing,
deleting, or rewriting it.

The checksum covers ordered `cell_id`, `district_id`, and metric EWKB. Timestamps and
physical row order are deliberately excluded.

## API and map

- `GET /api/analysis/grid/meta` reports the active grid contract and distribution.
- `GET /api/analysis/grid/tiles/{z}/{x}/{y}.mvt` returns native Mapbox Vector Tiles with
  source layer `analysis_grid` and only `cell_id`, `district_id`, and `grid_version`.

Tile generation uses `ST_TileEnvelope`, indexed EPSG:4326 bbox filtering,
`ST_AsMVTGeom`, and `ST_AsMVT` in PostgreSQL. It never loads the whole grid into Python.

The frontend declares `analysis-grid` as a non-selectable, derived-analysis vector-tile
layer in the `Аналитика` group. It is off by default, starts at zoom 11, ignores district
request scope, and does not participate in S6 catalog loading. Its light fill and thin
outline intentionally do not imply a heatmap or value.

## Explicitly deferred

F7 owns metric definitions and computation. F8 owns existing-data metrics, F9 scoring,
F10 heatmaps, and F11 scenarios. No part of those stages is encoded in this table, API,
or layer.
