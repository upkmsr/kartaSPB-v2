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

Without configuration, the map uses a local dark style with no tile dependency
or commercial token. Set `VITE_MAP_STYLE_URL` at build time to use a compatible
external style. If its initial style load fails, the map installs the local dark
style so catalog overlays can still start.

Clicking an interactive render layer uses the GeoJSON feature's canonical UUID,
loads the public object-details endpoint with abort/stale protection, highlights
the selected geometry, and shows only canonical properties and compact source
summaries. Search, attribute filters, routing, drawing, district scope, and user
data remain outside FOUNDATION 4B.
