# Personal priority scenario v1

F11A composes the eight smooth accessibility scores into a user-controlled heatmap. The
scenario is deliberately ephemeral: the browser holds the weights and the backend resolves
them to immutable F9 score runs. No scenario, composite score, or preference is written to
the database.

## Explicit scenario contract

`config/analytics/scenarios/dimensions.json` is the presentation registry. Every enabled
dimension must reference an enabled index metric and normalization. The v1 registry
contains exactly eight dimensions grouped as education, transport, healthcare, and nature.
Each visible slider accepts an integer weight from 0 to 100 and starts at zero. Zero-weight
dimensions are omitted; at least one positive weight is required.

The weighted cell score uses the existing F9 formula and identity rules. Metric order does
not affect the result. The response carries the exact current normalized run IDs in the
opaque heatmap spec, and the scoring signature changes when any selected run or weight
changes. A later current-pointer update cannot alter an already prepared map.

The API additions are:

- `GET /api/analysis/scenarios/dimensions` for the validated presentation registry;
- `POST /api/analysis/scoring/distribution` for district-relative p10/p25/p50/p75/p90;
- the existing `POST /api/analysis/heatmap/prepare` and immutable MVT endpoint for map data.

Prepare uses stored immutable-run summaries for bounded metadata work; it does not scan
millions of score rows merely to return the plan. The representative all-eight 50 m
prepare completed in 85 ms in the final isolated rehearsal.

## Frontend behavior

The Scenario Builder is separate from the single-metric heatmap control. It provides all
eight weights, equal/reset shortcuts, Auto/200 m/50 m resolution, and Low/Medium/High
display contrast. Active changes are debounced for 320 ms, stale requests are aborted,
and canonical request identities prevent duplicate prepare calls. Auto uses 200 m below
z13 and genuine 50 m at z13 or above; manual 50 m is disabled below z13.

`По району` is enabled only when at least one district is selected. It keeps the analytical
cell scores unchanged and sets the color range to the selected districts' p10–p90. Removing
the district selection restores the standard high-contrast range. Distribution responses
must match the active scoring signature before they may update the legend, preventing a
stale request from recoloring a newer scenario.

Scenario and single-metric heatmaps share the accepted MapLibre overlay lifecycle. Catalog
layers, district selection overlay, object click/card behavior, and the optional grid layer
remain independent and render above or alongside the heatmap as already defined.

## District distribution remediation

The 50 m city grid contains 580,597 cells. Separate indexes on `grid_version` and
`district_id` could not efficiently return a district's cell IDs, and the first F11A
rehearsal observed approximately 7.98 seconds for one dimension and 2.01 seconds for the
optimized all-eight request.

Migration `20261008_0015` adds exactly one production-safe concurrent index:

```sql
CREATE INDEX CONCURRENTLY ix_analytics_analysis_cells_grid_district_cell
ON analytics.analysis_cells (grid_version, district_id, cell_id);
```

The bounded query first materializes district cell IDs through an index-only scan, then
performs exact `(score_run_id, cell_id)` lookups for each selected metric and computes the
unchanged numeric weighted formula before `percentile_cont`. It never computes a full-city
distribution and never loops through cells in Python.

Final production-shaped rehearsal used Frunzensky district (14,993 50 m cells):

| Weights | Cold | Warm | Score rows | Result |
| --- | ---: | ---: | ---: | --- |
| 1 dimension | 145 ms | 114 ms | 14,993 | PASS |
| 4 dimensions | 515 ms | 492 ms | 59,972 | PASS |
| 8 dimensions | 809 ms | 837 ms | 119,944 | PASS hard gate |

All cold observations passed the required one-second gate. The preferred 500 ms warm goal
passed for one and four dimensions but not for all eight; this preference is recorded, not
hidden. The all-eight plan used
`ix_analytics_analysis_cells_grid_district_cell` with zero heap fetches, avoided a
580,597-cell scan, and reproduced the pre-index signature, cell count, and all five
quantiles exactly.

The concurrent build took about 5 seconds in rehearsal. The index occupied 51 MiB
(53,714,944 bytes), increased the `analysis_cells` total relation from about 358 MiB to
409 MiB, and generated about 46.5 MiB of WAL. A production attempt must require at least
1 GiB of verified free Docker/VM space plus a fresh validated backup; 2 GiB is the
conservative operational gate.

## Rehearsal and stage boundary

The all-eight representative z13 tile was 191,781 bytes, returned in 727 ms cold and
266 ms warm, and was byte-identical across repeated requests. Distribution, prepare, and
tile calls left all immutable run/value and current-pointer counts unchanged.

F11A implementation/rehearsal does not apply migration 0015 to production, publish the 16
accessibility runs, or deploy the Scenario Builder. Production remains at Alembic
`20261005_0014` until separate authorization. F11 is not complete: persistence, named
presets, comparison workflows, and any recommendation policy remain future scope.
