# Product roadmap

The accepted platform sequence is deliberately data-first:

1. Foundation Closeout — **DONE**
2. F6 Analysis Grid — **DONE**
3. F7 Metric Engine — **DONE**
4. F8 Existing Data Metrics — **DONE**
5. F9 Scoring Engine — **DONE**
6. F10 Heatmap — **RUNTIME ACCEPTED / R2 VISUAL + 50 M ROLLOUT PENDING**
7. F11 Scenario Builder
8. F12+ Data Enrichment

F6 creates neutral spatial units only. It does not calculate metrics, suitability,
scores, heatmaps, scenarios, or ingest another evidence source. UPI-B/C/D are not the
next product stages.

F7 provides only the versioned definition, provider, immutable run/value, current-pointer,
CLI, and read-API contracts. F8 adds and publishes the twelve accepted catalog-derived
raw metrics using two reusable spatial providers. F9 adds versioned piecewise-linear
normalization, immutable normalized runs, and explicit-weight on-demand scoring. Its
production rollout is complete with twelve current normalized runs covering all 36,292
analysis cells. F10-R1's stateless prepare/MVT implementation and overlay behavior are
accepted, but its visual QA exposed low color sensitivity and insufficient 200 m detail.
F10-R2 adds a pure display-range transform, proves a genuine 580,597-cell 50 m target in
isolation, and prototypes Auto/200 m/50 m selection without a schema change or persisted
composite. F10 remains open until separately authorized 50 m data publication, artifact
rollout, and visual acceptance. F11 has not started.
