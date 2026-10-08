# Multi-resolution analysis

F10-R2 proves a real multi-resolution analytical path without changing the F6–F9 schema
or manufacturing precision. Every cell has its own center and geometry; every raw metric
and normalized score is calculated for that cell. A 50 m view is never a visual split of
a 200 m parent.

## Concepts that must remain separate

- **Score sensitivity** is defined by versioned F9 normalization curves. F10-R2 leaves
  normalization v1 and all stored scores unchanged.
- **Color sensitivity** is a client-side MapLibre display transform. The default 40–100
  range improves contrast without changing a request, signature, spec, tile, or database.
- **Spatial resolution** is the selected `grid_version` and therefore selects different
  cells and distinct F8/F9 publications.

## Grid identity and schema

The existing schema already keys cells, raw runs, normalized runs, and current pointers by
`grid_version`. Stable cell IDs contain the grid version and grid coordinates, so IDs are
never reused across resolutions. The bootstrap is now parameterized but retains the
200 m defaults for backward compatibility. No migration 0015 is required.

| Grid | Cells | Districts | Invalid | Duplicates | Grid checksum |
| --- | ---: | ---: | ---: | ---: | --- |
| `spb-square-200m-v1` | 36,292 | 18 | 0 | 0 | existing production identity |
| `spb-square-100m-v1` | 145,113 | 18 | 0 | 0 | `0a754c567f637ef05175fd58d84828298fd5c63c7cdfa84e3469fc78d436945f` |
| `spb-square-50m-v1` | 580,597 | 18 | 0 | 0 | `41e8dd7827ae1d965f0a6bfa5c5d7f9694959ac7f1d039479c4b2d2ac5f026ea` |

Generation took 17.9 seconds for 100 m and 61.6 seconds for 50 m in the isolated
production-shaped rehearsal. Logical grid-row storage was 14 MiB for 200 m, 56 MiB for
100 m, and 221 MiB for 50 m; the shared analysis-cell relation was 458 MiB after all three
grids. Backup growth should be budgeted from the measured database growth, not only the
logical row payload.

## 50 m publication cost

The rehearsal used the accepted 12 F8 definitions and unchanged F9 normalization v1
curves:

| Stage | Runs | Values | Duration | Logical value payload |
| --- | ---: | ---: | ---: | ---: |
| F8 raw | 12 | 6,967,164 | 673.4 s | 512 MiB |
| F9 normalized | 12 | 6,967,164 | 383.1 s | 512 MiB |

The raw-value relation reached about 1.52 GiB and the normalized-value relation about
1.50 GiB including their 200 m rows and indexes. The rehearsal database grew from about
1.61 GiB before extra grids to 4.93 GiB after 50 m grid, raw values, and normalized
values. A production rollout therefore needs an explicit capacity/backup gate and must
publish the grid, raw metrics, and normalized runs as one controlled sequence.

## Tile acceptance and Auto threshold

The representative 50 m Case A/B/C benchmark is recorded in
[heatmap.md](heatmap.md). z12 meets the hard limits but can contain 9,781 cells and more
than 117,000 score joins for all 12 metrics. z13 contains 2,496 cells and is comfortably
inside the preferred latency envelope. The supported Auto hypothesis is therefore:

- z11–12: 200 m overview;
- z13 and above: 50 m detail.

Manual 200 m and 50 m modes remain available. This threshold must still pass the
production visual gate after the 50 m data publication.

## 25 m and 10 m feasibility

A bounded dense-urban sample around central Saint Petersburg used genuine square cells
and ran all 12 F8 and all 12 F9 calculations:

| Cell size | Area | Cells | Cells/km² | Raw values | Scores | F8 duration | F9 duration |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 25 m | 4.101 km² | 6,561 | 1,600 | 78,732 | 78,732 | 9.1 s | 4.0 s |
| 10 m | 4.040 km² | 40,401 | 10,000 | 484,812 | 484,812 | 35.2 s | 21.4 s |

The 25 m raw and score payloads were about 7 MiB each; 10 m used about 43 MiB each.
For the all-12 case, representative MVT results were:

| Cell size | z14 | z15 | z16 |
| ---: | ---: | ---: | ---: |
| 25 m | 229 KiB / 114 ms | 60 KiB / 23 ms | 15 KiB / 10 ms |
| 10 m | 1.30 MiB / 786–813 ms | 350 KiB / 178–186 ms | 90 KiB / 47–53 ms |

Full-city scaling is approximately 2.32 million cells at 25 m and 14.5 million at 10 m,
or roughly 27.9 million and 174 million values per layer of 12 metrics respectively.
Consequently:

- 25 m is technically viable as a future district/local mode after a dedicated capacity
  and user-value decision;
- 10 m should be viewport-local or explicitly bounded/on-demand, with z15 as the earliest
  plausible display floor;
- full-city persisted 10 m is deferred;
- neither mode may be represented by interpolating 50/200 m scores.

## Normalization saturation

Production v1 distributions show that the green appearance is a combination of display
range, normalization plateaus, and coarse spatial aggregation:

| Metric | =0 | =100 | >=90 | >=75 |
| --- | ---: | ---: | ---: | ---: |
| education.kindergarten.count_1000m | 50.328% | 15.667% | 25.058% | 30.594% |
| education.kindergarten.distance_m | 13.981% | 20.765% | 31.420% | 42.536% |
| education.school.count_1000m | 50.915% | 12.143% | 22.537% | 31.539% |
| education.school.distance_m | 7.313% | 30.574% | 39.190% | 49.085% |
| healthcare.clinic.distance_m | 6.588% | 17.081% | 26.659% | 38.796% |
| healthcare.hospital.distance_m | 0.000% | 21.834% | 40.846% | 62.474% |
| healthcare.pharmacy.count_1000m | 52.871% | 17.701% | 25.672% | 32.690% |
| healthcare.pharmacy.distance_m | 18.660% | 17.971% | 26.573% | 36.540% |
| nature.park.distance_m | 4.216% | 26.325% | 36.253% | 48.052% |
| nature.water.distance_m | 0.066% | 40.510% | 64.827% | 85.041% |
| transport.stop.count_500m | 44.332% | 12.140% | 20.622% | 34.352% |
| transport.stop.distance_m | 10.887% | 25.524% | 42.301% | 55.668% |

Water distance, school distance, park distance, stop distance, and hospital distance show
the strongest high-score saturation. A separately versioned F9 normalization v2 study is
recommended. Version 1 must remain immutable and was not changed by F10-R2.

## Production boundary

F10-R2 implementation and rehearsal do not publish any new production row. Production
continues to use `spb-square-200m-v1` and its immutable F8/F9 runs until a separate 50 m
publication and backend/frontend rollout is explicitly authorized.
