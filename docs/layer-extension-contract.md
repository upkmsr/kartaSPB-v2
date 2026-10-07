# Layer extension contract

F5.5-S7 separates a layer's meaning from its transport, loading lifecycle, rendering,
and selection behavior. F6 retains the ten catalog layers and adds one static derived
analysis layer. F10 adds a parameterized dynamic derived-analysis overlay whose immutable
tile source is installed only after an explicit prepare action; the other examples below
remain declarative, test-only extension proofs.

## Contract dimensions

`LayerDefinition` in `frontend/src/map/layerContract.ts` describes these independent
dimensions:

- `layerClass`: `canonical-object`, `reference-vector`, `temporal-vector`, `raster`,
  or `derived-analysis`;
- `source`: catalog, GeoJSON, vector tiles, raster tiles, or a derived delivery;
- `loadingStrategy`: `viewport`, `static`, `tiles`, or `manual`;
- source `loadParticipation`: `s6-viewport`, `independent`, `maplibre-native`, or
  `external`;
- source `districtHandling`: catalog filtering, ignored, or source-managed;
- `selection`: none, canonical ObjectDetail selection, or a generic layer feature;
- `legend`, `opacity`, `time`, and optional `provenance` metadata;
- ordered MapLibre render definitions.

This separation is intentional. A reference and a temporal layer can both use GeoJSON;
a derived analysis can use GeoJSON or tiles; and raster tiles do not enter the catalog
viewport request lifecycle.

## Semantic classes

- `canonical-object` is the application catalog: canonical identity, facility
  representation, shared catalog GeoJSON, and ObjectCard selection.
- `reference-vector` represents relatively stable reference facts such as a future
  official polygon, line, or point dataset.
- `temporal-vector` requires snapshot, range, or event metadata.
- `raster` represents image/tile surfaces and is nonselectable by default.
- `derived-analysis` is explicitly distinct from official fact and uses a derived source.

The contract prepares for future urban-planning layers but S7 publishes no General Plan,
PZZ, height, parcel, development, raster, viewshed, or climate dataset.

## Source drivers and loading

`frontend/src/map/layerRuntime.ts` is the source-driver boundary. It installs configured
catalog, GeoJSON, vector-tile, raster-tile, and derived sources and their declarative
render layers. `MapView` invokes this runtime and does not branch on logical layer IDs.

The catalog driver in `frontend/src/map/catalogLayerDriver.ts` additionally owns:

- the shared `catalog-features` source;
- extraction and aggregation of loadable catalog categories;
- the S6 viewport participation plan;
- canonical/facility selection filters and highlight layers.

Multiple enabled catalog layers still produce one `/api/map/features` request containing
the combined category set. GeoJSON/static drivers load independently; tile drivers use
MapLibre-native loading; externally controlled sources do not implicitly enter S6.

All ten production declarations use the same canonical catalog mapping:

| Logical layer | Catalog category | Minimum zoom | Default |
|---|---|---:|---|
| water | `nature.water` | 9 | on |
| park | `nature.park` | 10 | on |
| school | `education.school` | 13 | on |
| kindergarten | `education.kindergarten` | 13 | on |
| pharmacy | `healthcare.pharmacy` | 14 | on |
| hospital | `healthcare.hospital` | 12 | on |
| clinic | `healthcare.clinic` | 13 | on |
| road | `transport.road` | 16 | on |
| boundary | `boundary.administrative` | 10 | off |
| stop | `transport.stop` | 14 | on |

Their labels, paint declarations, render order, interaction behavior, and current
default visibility are preserved by the migration.

The eleventh production declaration is `analysis-grid` in the separate `analytics`
group (`Аналитика`). It uses derived vector tiles from
`/api/analysis/grid/tiles/{z}/{x}/{y}.mvt`, source layer `analysis_grid`, minimum zoom 11,
and default off. It is non-selectable, district-scope agnostic, and MapLibre-native, so
it never enters catalog aggregation or the S6 auto/manual loading state.

The F10 heatmap is not a twelfth static registry declaration. It is a runtime
`derived-analysis` overlay because its source URL is parameterized by a deterministic F9
scoring signature and an immutable historical-run spec. It is default off, non-selectable,
MapLibre-native, independent of district/catalog loading, and visible from zoom 10. Its
fill is installed below both the optional grid outline and catalog layers. Style reload
reinstalls the active source and layer without preparing a different score plan.

District UUIDs are sent only to the catalog request. Other sources explicitly declare
whether district scope is ignored or managed by that source. The selected-district
overlay remains independent of all ordinary layers.

## Enabled, loadable, loaded, and visible

S6 remains authoritative:

- enabled is persistent checkbox intent;
- loadable is enabled and inside the declared zoom range;
- loaded means the participating driver successfully covered the current state;
- visible means its render layer is enabled and within MapLibre's zoom range.

Only sources with `loadParticipation: "s6-viewport"` affect the current auto/manual
catalog button and status. Catalog auto-load, manual pending/load, latest-state dedupe,
cancellation, waiting-for-zoom, and stale/error policies are unchanged. Persistence still
stores logical IDs and applies a newly introduced registry entry's current
`defaultVisible` value.

## Selection

The interaction index deterministically maps each MapLibre render-layer ID to its logical
layer and selection strategy. Duplicate render IDs are invalid.

- `canonical-object` resolves the representative/canonical UUID and may open ObjectCard.
- `layer-feature` resolves a typed `{ layerId, featureId }` result and is never sent to
  `/api/objects/{uuid}`.
- `none` is absent from the interactive render index.

Facility representative/member highlighting is part of the catalog driver. Search v2 is
independent: a Street result remains bbox navigation with `detail_object_id=null`, so its
logical Street UUID is never treated as either a canonical object or a map layer feature.

## Legend, opacity, time, and provenance

Legend metadata supports point, line, fill, and raster-gradient indicators. LayerControl
renders it generically, so adding an ID no longer requires an ID-specific CSS class.

Opacity declares a default, whether future UI may adjust it, and the render-layer/paint
properties to update. The runtime applies declared defaults without per-layer code. S7
does not add an opacity slider.

Time metadata is `none`, `snapshot`, `range`, or `event`. Temporal-vector definitions
must declare a non-`none` model. S7 adds no time controls or historical data.

Provenance distinguishes `official`, `community`, `derived`, and `internal`, with an
optional attribution and source reference. Current OSM-derived catalog layers are marked
community; this makes no claim of official legal authority.

## Declarative examples

The examples omit paint detail for brevity and use configuration symbols rather than
invented production endpoints.

```ts
const canonicalCatalog = {
  layerClass: "canonical-object",
  source: {
    type: "catalog",
    categoryKey: "nature.park",
    loadParticipation: "s6-viewport",
    districtHandling: "catalog-filter",
  },
  loadingStrategy: "viewport",
  selection: { kind: "canonical-object" },
  time: { kind: "none" },
};
```

```ts
const referenceVector = {
  layerClass: "reference-vector",
  source: {
    type: "geojson",
    dataUrl: configuredReferenceUrl,
    loadParticipation: "independent",
    districtHandling: "source-managed",
  },
  loadingStrategy: "static",
  selection: { kind: "layer-feature", idProperty: "feature_id" },
  legend: { kind: "fill", color: "#7865cc", outlineColor: "#d8d0ff" },
};
```

```ts
const temporalVector = {
  layerClass: "temporal-vector",
  source: { type: "geojson", dataUrl: configuredTemporalUrl },
  loadingStrategy: "static",
  selection: { kind: "layer-feature", idProperty: "event_id" },
  time: { kind: "range", startProperty: "valid_from", endProperty: "valid_to" },
};
```

```ts
const raster = {
  layerClass: "raster",
  source: {
    type: "raster-tile",
    tiles: configuredRasterTemplates,
    loadParticipation: "maplibre-native",
    districtHandling: "ignored",
  },
  loadingStrategy: "tiles",
  selection: { kind: "none" },
  opacity: { default: 0.7, adjustable: true, applyTo: [rasterOpacityMapping] },
};
```

```ts
const derivedAnalysis = {
  layerClass: "derived-analysis",
  source: {
    type: "derived",
    delivery: { type: "geojson", dataUrl: configuredAnalysisUrl },
    loadParticipation: "independent",
    districtHandling: "source-managed",
  },
  loadingStrategy: "static",
  selection: { kind: "none" },
  provenance: { kind: "derived", sourceLabel: configuredAnalysisLabel },
};
```

Executable extension proofs for all five classes and transport types live in
`layerContract.test.ts` and `layerRuntime.test.ts`; the F6 analysis grid is the first
production static `derived-analysis` vector-tile declaration. F10's parameterized overlay
lifecycle is covered separately by `heatmapOverlay.test.ts`.

## Registry validation

Development startup and tests fail loudly for duplicate logical or render IDs, unknown
groups, invalid zoom/opacity, missing source configuration, incompatible source/loading
combinations, invalid catalog/raster selection, incompatible time metadata, invalid
opacity mappings, and tile/render mismatches.

Pure helpers derive enabled/loadable/waiting layers, catalog category aggregation,
driver partitions, ordered render declarations, default IDs, group ordering, and the
interaction index. React components do not reimplement these rules.

## Extension recipe

For another layer using an existing source type:

1. Add its declarative `LayerDefinition` to the registry (and a group declaration only
   when introducing a real, non-empty UI group).
2. Supply its source configuration through the appropriate application configuration.
3. Add focused validation/runtime tests for the declaration.

No MapView special case is required. A genuinely new transport requires one source
driver in `layerRuntime.ts`; it still must not introduce branches for individual layer
IDs.
