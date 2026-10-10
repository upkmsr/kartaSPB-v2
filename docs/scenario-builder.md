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

The API surface is:

- `GET /api/analysis/scenarios/dimensions` for the validated presentation registry;
- `POST /api/analysis/scoring/distribution` for district-relative p10/p25/p50/p75/p90;
- `POST /api/analysis/scenarios/explain` for an immutable-run explanation of one cell;
- the existing `POST /api/analysis/heatmap/prepare` and immutable MVT endpoint for map data.

Prepare uses stored immutable-run summaries for bounded metadata work; it does not scan
millions of score rows merely to return the plan. The representative all-eight 50 m
prepare completed in 85 ms in the final isolated rehearsal.

## Frontend behavior

The Scenario Builder is separate from the single-metric heatmap control. It provides all
eight weights, equal/reset shortcuts, Auto/200 m/50 m resolution, and
Low/Medium/High/Ultra/manual display contrast. Manual contrast enforces
`0 <= min < max <= 100`, updates only the MapLibre paint expression and legend, and never
issues a prepare request or changes a score/signature. Active changes are debounced for
320 ms, stale requests are aborted,
and canonical request identities prevent duplicate prepare calls. Auto uses 200 m below
z13 and genuine 50 m at z13 or above; manual 50 m is disabled below z13.

`По району` is enabled only when at least one district is selected. It keeps the analytical
cell scores unchanged and sets the color range to the selected districts' p10–p90. Removing
the district selection restores the standard high-contrast range. Distribution responses
must match the active scoring signature before they may update the legend, preventing a
stale request from recoloring a newer scenario.

All eight zero weights mean that no personal heatmap exists. Reset aborts in-flight
prepare/distribution requests, invalidates late responses, removes the source/layer and
legend, and shows the neutral prompt to choose a priority. This does not affect the
separate single-metric mode.

The opt-in score inspector intercepts a heatmap-cell click before catalog selection and
shows the total, every selected factor, weight, individual immutable-run score, weighted
contribution, and the nearest or model-significant logical target. Park explanations also
show the target area. Provider parameters come from the exact metric run's immutable
definition snapshot, so an old heatmap spec cannot be explained with a newer formula.
Target attribution is shown only while both raw and normalized runs remain the current
pointers; historical specs retain exact scores/contributions but do not guess a target
from a newer catalog state. Outside inspector mode, catalog click and `ObjectCard`
behavior are unchanged.

Scenario and single-metric heatmaps share the accepted MapLibre overlay lifecycle. Catalog
layers, district selection overlay, object click/card behavior, and the optional grid layer
remain independent and render above or alongside the heatmap as already defined.

## District distribution remediation

The 50 m city grid contains 580,597 cells. Separate indexes on `grid_version` and
`district_id` could not efficiently return a district's cell IDs, and the first F11A
rehearsal observed approximately 7.98 seconds for one dimension and 2.01 seconds for the
optimized all-eight request.

The original F11A migration `20261008_0015` adds the district-cell lookup index. R3 adds
migration `20261010_0016`, which builds the score index concurrently before removing the
superseded single-column index:

```sql
CREATE INDEX CONCURRENTLY ix_analytics_cell_metric_scores_cell_run_cover
ON analytics.cell_metric_scores (cell_id, score_run_id) INCLUDE (score);
```

The bounded query materializes district cell IDs, reads their selected immutable runs
cell-first from the covering index, groups them once, and applies the unchanged weighted
formula before `percentile_cont`. It never computes a full-city distribution and never
loops through cells in Python.

Final production-shaped rehearsal used Frunzensky district (14,993 50 m cells):

The final all-eight Frunzensky request returned its 14,993 cells' distribution in 386 ms
after candidate restart and 422–500 ms on repeated calls. It reproduced the same scoring
signature and five quantiles. The covering index occupies 1,274 MiB in the
production-shaped rehearsal; its concurrent host-backed build took several minutes. A
production attempt must require a fresh validated backup and at least 6 GiB verified free
Docker/VM capacity for the new index, build workspace, and WAL before the old 216 MiB
single-column index is removed.

## Rehearsal and stage boundary

Prepare returned in 8.7 ms. The all-eight representative z13 tile was 191,781 bytes,
returned in 393 ms cold and 223 ms warm, and was byte-identical across repeated requests.
Diagnostic z12 was 730,985 bytes / 1.69 s; z14 was 49,860 bytes / 42 ms. Distribution,
prepare, explain, and tile calls left all immutable run/value and current-pointer counts
unchanged.

F11A-R3 implementation/rehearsal does not publish v2 accessibility runs or switch any
production runtime. Production remains on Alembic `20261008_0015`, its accepted v1
metric/score pointers, backend `c830cdf`, live frontend `0bb05fa`, and preview frontend
`c830cdf`. F11 is not complete: persistence, named presets, comparison workflows, and
any recommendation policy remain future scope.
