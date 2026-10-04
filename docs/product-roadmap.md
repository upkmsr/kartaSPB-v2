# Product roadmap

The accepted platform sequence is deliberately data-first:

1. Foundation Closeout — **DONE**
2. F6 Analysis Grid — **DONE**
3. F7 Metric Engine — **IMPLEMENTED, production rollout pending explicit authorization**
4. F8 Existing Data Metrics
5. F9 Scoring Engine
6. F10 Heatmap
7. F11 Scenario Builder
8. F12+ Data Enrichment

F6 creates neutral spatial units only. It does not calculate metrics, suitability,
scores, heatmaps, scenarios, or ingest another evidence source. UPI-B/C/D are not the
next product stages.

F7 provides only the versioned definition, provider, immutable run/value, current-pointer,
CLI, and read-API contracts. The production definition registry is empty, so real metrics
still begin in F8 only after F7 production acceptance.
