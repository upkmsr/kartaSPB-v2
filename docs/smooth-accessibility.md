# Smooth accessibility metrics

F11A adds eight generic accessibility inputs without changing canonical objects or
persisting a composite scenario. Each input is an immutable F8 metric run calculated for
every cell of a selected analysis grid, then published through the existing F9
normalization pipeline.

## Versioned provider contract

The historical v1 provider `catalog.smooth_influence` remains reproducible from every
stored definition snapshot. It summed all compact-quartic target influences. That made
local object density the dominant signal: in the production-shaped 50 m data, a cell at
an isolated school scored 37.9, an isolated kindergarten 35.7, and an isolated pharmacy
33.7 despite being directly beside the object.

Definition v2 keeps the eight metric keys but introduces three explicit providers. All
three resolve the same logical targets as the established providers, including facility
collapse, and measure distance to the actual PostGIS geometry in EPSG:32636.

### Point and service amenities

Schools, kindergartens, pharmacies, clinics, hospitals, and public-transport stops use:

```text
primary = max(exp(-ln(2) * (distance / half_distance)²))
extra = max(sum(influence) - primary, 0)
bonus = bonus_cap * (1 - exp(-extra / bonus_saturation))
accessibility = primary + (1 - primary) * bonus
```

The nearest suitable logical object therefore supplies the main value. Extra availability
has diminishing returns and is capped at 18% of the remaining headroom. The Gaussian-like
curve is continuous; `ST_DWithin` only applies a technical cutoff at four half-distances,
where residual influence is about 0.0015%.

| Dimension | Half-distance | Technical cutoff |
| --- | ---: | ---: |
| Детские сады | 600 m | 2,400 m |
| Школы | 700 m | 2,800 m |
| Общественный транспорт | 350 m | 1,400 m |
| Поликлиники | 1,000 m | 4,000 m |
| Больницы | 2,000 m | 8,000 m |
| Аптеки | 500 m | 2,000 m |

These are straight-line proximity parameters, not claims about walking time, capacity,
quality, opening hours, entrances, or official-service availability.

### Parks

`catalog.park_accessibility` multiplies boundary distance influence by a bounded area
quality:

```text
size_quality = 0.2 + 0.8 * (1 - exp(-area_m² / 50,000))
target_influence = size_quality * proximity(distance, half_distance=900 m)
```

The strongest park is primary; additional independent parks contribute at most 15% of
remaining headroom. Area has diminishing returns, so a very large park cannot influence
the whole city by size alone. Distances use polygon boundaries, not centroids. The source
does not prove public entrances or access rights, so this remains geometry-based park
proximity.

### Water

`catalog.water_accessibility` uses only the strongest nearby water geometry. Polygon area
quality uses the same diminishing-return form with a 100,000 m² reference and 0.25 floor;
LineStrings use quality 0.85. Proximity has a 1,000 m half-distance. Influences are never
summed, so splitting a river into additional segments cannot create a density bonus.
This measures proximity to mapped water, not guaranteed pedestrian access to its bank.

## Normalization and interpretation

The bounded v2 raw index has direct meaning on 0–1, so normalization v2 preserves it as
0–100 through a versioned monotone piecewise-linear identity curve. Exact score 100
covered only 0–1.28% of the 50 m cells by metric; no citywide saturation plateau was
introduced. Historical v1 raw and normalized runs remain immutable and queryable.

The resulting value means relative spatial access to one category under this kernel. It
is not a recommendation, district rank, overall quality score, or saved user scenario.

## Isolated rehearsal

The R3 production-shaped rehearsal added 16 raw v2 runs and 16 normalized v2 runs: eight
metrics on 36,292 genuine 200 m cells and 580,597 genuine 50 m cells, or 4,935,112 values
per publication layer. All 16 v1 raw and normalized runs remained present. Representative
50 m results were:

| Case / canonical object | Geometry, area | Distance | v1 raw / score | v2 raw / score |
| --- | --- | ---: | ---: | ---: |
| School 354 `859c6ca2-8d97-4452-a26f-db0d900c49f2` | MultiPolygon, 60,728 m² | 0 m | 1.000 / 37.9 | 1.000 / 100.0 |
| Kindergarten 12 `f642f6ec-246b-4fa4-ac57-7d28bb0e7092` | Polygon, 11,355 m² | 0 m | 1.000 / 35.7 | 1.000 / 100.0 |
| Pharmacy Vital `ef7b365d-1722-4ccb-aa4e-c8298bd90e3e` | Point | 21.4 m | 0.999 / 33.7 | 0.999 / 99.9 |
| Pavlovsky Park `5c5a7d1a-6bc3-470b-9825-658d8d6590de` | Polygon, 5,412,691 m² | 0 m | 5.072 / 54.2 | 1.000 / 100.0 |
| Kharitonov square `f715b5b1-a6e1-4800-9144-d0d3c666bfa8` | Polygon, 239 m² | 9.6 m | 41.960 / 97.6 | 0.524 / 52.4 |
| Sestroretsk Razliv `7e969d0c-eac7-4857-9c59-b75d496e20ab` | Polygon, 10,945,956 m² | 0 m | 11.826 / 60.7 | 1.000 / 100.0 |
| Bolshaya Neva `fd20cf60-ef8b-49d5-bdcd-d945ee8e6593` | Polygon, 2,772,506 m² | 0 m | 14.668 / 66.6 | 1.000 / 100.0 |
| Neva `6044e956-e461-4d71-adce-bd0914688b41` | LineString | 37.0 m | 3.127 / 23.1 | 0.850 / 85.0 |

At half-distance the sparse school, kindergarten, and pharmacy cases scored approximately
50; at twice half-distance they scored approximately 6.25. Frunzensky's eight-factor
family profile retained spatial differentiation (p10/p50/p90 34.8/78.6/87.4; standard
deviation 20.5).

The same 14,993 Frunzensky 50 m cells gave the following before/after distributions:

| Scenario | v1 p10 / p50 / p90 / stddev | v2 p10 / p50 / p90 / stddev |
| --- | --- | --- |
| Schools only | 22.6 / 60.9 / 88.9 / 26.3 | 21.8 / 88.0 / 99.4 / 29.4 |
| Kindergartens only | 0.0 / 62.8 / 91.5 / 31.6 | 18.6 / 89.0 / 99.5 / 30.1 |
| Parks only | 35.7 / 59.6 / 77.7 / 16.7 | 29.8 / 66.0 / 96.3 / 24.5 |
| Water only | 12.8 / 30.2 / 56.8 / 18.6 | 20.7 / 49.7 / 83.7 / 23.6 |
| Transport only | 30.8 / 60.8 / 84.6 / 22.0 | 42.4 / 83.4 / 98.0 / 22.8 |
| Eight-factor family | 26.5 / 58.5 / 75.5 / 18.5 | 34.8 / 78.6 / 87.4 / 20.5 |

R3 runs exist only in the isolated rehearsal. Production remains on the accepted v1
pointers. Publishing v2 definitions/runs and switching production runtime requires a
separate explicit authorization.

## Boundary

F11A exposes these eight dimensions to an ephemeral Scenario Builder. It does not store
scenario names or weights, choose a default lifestyle, rank homes, add routing, or start
F11B. See [scenario-builder.md](scenario-builder.md) for the request and UI contract.
