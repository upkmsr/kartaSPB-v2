# Product roadmap

The accepted platform sequence is deliberately data-first:

1. Foundation Closeout — **DONE**
2. F6 Analysis Grid — **DONE**
3. F7 Metric Engine — **DONE**
4. F8 Existing Data Metrics — **DONE**
5. F9 Scoring Engine
6. F10 Heatmap
7. F11 Scenario Builder
8. F12+ Data Enrichment

F6 creates neutral spatial units only. It does not calculate metrics, suitability,
scores, heatmaps, scenarios, or ingest another evidence source. UPI-B/C/D are not the
next product stages.

F7 provides only the versioned definition, provider, immutable run/value, current-pointer,
CLI, and read-API contracts. F8 adds and publishes the twelve accepted catalog-derived
raw metrics using two reusable spatial providers. F9 is the next stage and owns
normalization and scoring; it has not started.
