# Real catalog map

The FOUNDATION 4B desktop map starts at Saint Petersburg (`30.3158, 59.9398`,
zoom 12) and reads only the generic FOUNDATION 4A endpoints:

- `GET /api/map/features` for the current bounded viewport;
- `GET /api/objects/{uuid}` for a selected canonical object.

## Layer and request lifecycle

`frontend/src/map/layerRegistry.ts` is the single registry for schools,
kindergartens, pharmacies, hospitals, clinics, parks, water, stops, roads, and
administrative boundaries. It owns labels, defaults, minimum zooms, interaction,
render definitions, and deterministic order. MapLibre uses one
`catalog-features` source; render layers filter its `properties.categories` and
geometry type.

Only visible logical layers whose minimum zoom is satisfied contribute an API
category. A viewport produces one request after a 200 ms debounce. The client
aborts the previous request and also rejects late responses by sequence number.
Roads are requested from zoom 16, while stops and pharmacies start at zoom 14.

The client enforces the same bbox spans and area as the API. Oversized viewports,
`feature_limit_exceeded`, network failures, empty results, and loading are shown
as compact map states. Limit and network failures do not replace the last
complete collection; a successful empty collection does.

## Base style and selection

Normal development uses the token-free OpenFreeMap dark style configured by
`VITE_MAP_STYLE_URL`, with OpenFreeMap/OpenMapTiles/OpenStreetMap attribution.
Set the value to `local` for the background-only emergency style. If the
external style cannot load, the map installs that local style and then restores
the catalog source, render layers, and most recent FeatureCollection.

Clicking an interactive render layer uses the GeoJSON feature's canonical UUID,
loads the public object-details endpoint with abort/stale protection, highlights
the selected geometry, and shows only canonical properties and compact source
summaries. Search, attribute filters, routing, drawing, district scope, and user
data remain outside FOUNDATION 4B.

The production build imports and emits the MapLibre worker as a dedicated
JavaScript asset, then configures its URL before constructing the map. The build
fails if the worker is absent, looks like the SPA HTML fallback, is not valid
JavaScript, or is not referenced by the application bundle. The MapLibre source
lifecycle regression also verifies that a GeoJSON source is installed once,
updated on viewport changes, and restored with the latest collection after a
style reload.

## Performance validation snapshot

The bounded GeoJSON architecture remains appropriate for the accepted smoke
catalog. On the local `spb_smoke` validation database, five sequential warm
viewport requests returned 98–325 features (119–315 KB) in 90–417 ms total. A
representative zoom-16 road viewport returned 2,084 LineStrings (713 KB) in 444
ms warm. These measurements are a closeout snapshot, not a production SLA; MVT,
PMTiles, and a tile server are intentionally not introduced in FOUNDATION 4.

## Known data-quality limitations

- Water coverage reflects the current baseline OSM mappings and is not
  exhaustive for all OSM water semantics. Detailed river/water semantic
  enrichment is deferred to a dedicated data-enrichment stage; no geometry is
  hand-drawn and there is no Neva-specific exception.
- The generic `boundary.administrative` layer is a technical baseline, not an
  authoritative representation of the exact 18 Saint Petersburg districts.
  Exact district semantics and the authoritative/derived district registry are
  deferred to FOUNDATION 5.
