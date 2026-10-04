# Universal metric engine

F7 adds the neutral publication mechanism used by later analytical stages. It does not
define or calculate any real product metric, normalize values, score locations, or render
a heatmap.

## Definition registry

Metric definitions are declarative JSON under `config/analytics/metrics/`. A definition
has a stable lowercase dotted key, explicit definition and calculation versions, user
metadata, raw-value semantics and direction, a provider key, provider configuration,
source dependencies, and an enabled flag. The loader rejects unknown fields, invalid
enums, invalid keys, blank versions, and duplicate keys. Ordering and the registry
SHA-256 are deterministic.

The production registry intentionally contains zero definitions. Tests and the isolated
rehearsal inject a synthetic fixture; it is not a school, park, transport, or other
product metric.

## Persistence and publication

Revision `20261004_0013` adds exactly three `analytics` tables:

- `metric_runs` is immutable run metadata, including a complete definition snapshot,
  input fingerprint, statistics, deterministic signature, and values checksum.
- `cell_metric_values` is the immutable raw finite value for every grid cell in a run.
- `metric_current_runs` is the mutable current pointer for one metric/grid pair.

The publisher requires exact full-grid coverage. Missing, extra, duplicate, NaN, and
infinite values fail before commit. It publishes metadata, all values, and the current
pointer in one bounded transaction. Values are inserted in batches. Identical definition,
calculation version, grid, and input fingerprint return `unchanged` only when the ordered
raw-value checksum is identical. Changed input creates a new immutable run and advances
the pointer while retaining history. Database triggers reject update or delete operations
on both historical tables.

The values checksum is SHA-256 over rows ordered by `cell_id`, using Python hexadecimal
float serialization. It excludes UUIDs, timestamps, physical row order, and mutable
pointers.

## Provider and command contracts

Providers implement the small `MetricProvider` protocol and return `(cell_id, raw_value)`
pairs. Provider-specific behavior stays outside the publisher. The production provider
registry is empty in F7.

```bash
python -m app.analytics.metrics validate
python -m app.analytics.metrics list
python -m app.analytics.metrics run --metric example.metric.key \
  --input-fingerprint <sha256>
```

Commands emit JSON. `run` fails closed when a definition or provider is not registered.

## Read API

- `GET /api/analysis/metrics` lists enabled public definitions; F7 production returns `[]`.
- `GET /api/analysis/metrics/{key}` returns one public definition or 404.
- `GET /api/analysis/metrics/{key}/current` returns current run metadata or 404. An optional
  `grid_version` query parameter defaults to `spb-square-200m-v1`.

Provider configuration, source-dependency internals, and secrets are never exposed.
Raw per-cell values are not an API in F7.

## Isolated full-grid rehearsal

The F7 implementation was exercised against the ordered identity set from the accepted
`spb-square-200m-v1` production grid (36,292 distinct cells) in an isolated PostgreSQL
database. No production DDL or DML was used.

- first synthetic publication: 36,292 values, 1.671 s, checksum
  `864deaa4d6c66b04a9b9a28a366663800608aeca576a850678072e91b1ea49e8`;
- identical rerun: `unchanged`, same run UUID and checksum, 0.074 s;
- changed input and values: new historical run, pointer advanced, 1.649 s, checksum
  `9675f01daed036a262ce8138e8821baf7db5ccaba16a0e37aab95ca65800678f`;
- incomplete input: rejected with one missing cell and current pointer preserved;
- two retained runs increased isolated database size by 14,802,944 bytes.

The fixture used only synthetic signed raw values and did not create a product metric.

## Production acceptance

F7 was accepted in production on 2026-10-04 from repository commit
`cb8968e53208a58dd60cc8a74dc8f9e3f09d7c1c`:

- Alembic revision is `20261004_0013`;
- all three metric-engine tables and both append-only guards are present;
- the production registry contains zero real metric definitions;
- runs, cell values, and current pointers are all empty;
- the accepted 36,292-cell F6 grid and its checksum are unchanged;
- catalog, category, district, facility, street, and UPI invariants are unchanged;
- backend readiness and existing product APIs pass against revision `0013`.

No synthetic metric was published in production. F8 has not started.

## Deferred

F8 owns real existing-data metric definitions/providers. F9 owns normalization and
scoring, F10 heatmaps, and F11 scenarios. F7 does not begin any of them.
