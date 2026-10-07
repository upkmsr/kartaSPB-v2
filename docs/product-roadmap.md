# Product roadmap

The accepted platform sequence is deliberately data-first:

1. Foundation Closeout — **DONE**
2. F6 Analysis Grid — **DONE**
3. F7 Metric Engine — **DONE**
4. F8 Existing Data Metrics — **DONE**
5. F9 Scoring Engine — **DONE**
6. F10 Heatmap — **IMPLEMENTED / PRODUCTION ROLLOUT PENDING**
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
analysis cells. F10 now has an accepted stateless prepare/MVT implementation and dynamic
frontend overlay, with no schema change or persisted composite. Its production
backend/frontend rollout remains separately authorized; F11 has not started.
