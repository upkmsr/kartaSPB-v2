# Real catalog map

The FOUNDATION 4B desktop map starts at Saint Petersburg (`30.3158, 59.9398`,
zoom 12) and reads only the generic FOUNDATION 4A endpoints:

- `GET /api/map/features` for the current bounded viewport;
- `GET /api/objects/{uuid}` for a selected canonical object;
- `GET /api/districts` for the authoritative 18-district control list;
- `GET /api/search` for canonical name search in the active user scope.

## Desktop shell and district scope

The permanent left control panel is 320 px wide when expanded and 56 px when
collapsed. It contains the district multi-select and the unchanged Layer Registry
controls; the existing minimum supported viewport remains 1280 px. Opening an object
adds the existing 360 px ObjectCard as a right column. The center map stays fluid, and
its `ResizeObserver` calls `map.resize()` after either side changes width.

The district section is a keyboard-accessible accordion independent of the whole panel.
Collapsing it only hides its rows: selected UUIDs and map scope remain unchanged and the
checkboxes restore their state when reopened. The panel header stays outside a dedicated
vertical scroll area, so all 18 district rows and every layer control remain reachable at
1280×800 without page or horizontal scrolling.

District rows come exclusively from `GET /api/districts` and use domain UUIDs as
identity. Zero selections means unrestricted district scope and omits the `districts`
query parameter. One or more selections add one comma-separated `districts` value to
the existing bounded map request; bbox, categories, limit, debounce, cancellation, and
stale-response protection are unchanged. No per-district feature requests are made.

Checkboxes change the exact backend scope without moving the map. Each row has a
separate locate action using its public bbox, while “Показать выбранные” computes one
client-side bbox union and calls `fitBounds` once. This union is navigation only; exact
spatial filtering remains a backend geometry intersection. If a successful scoped map
response no longer contains the selected object, its highlight and ObjectCard close.

## Catalog search

The expanded sidebar keeps Search above Districts and Layers. Input stays local until
the normalized query contains at least three characters, then waits 250 ms before one
`GET /api/search` request. Clearing the input cancels the active request, clears only
the result list, and leaves districts, layers, map position, and ObjectCard unchanged.
Every new query or scope aborts the previous request and advances a monotonically
increasing token, so an older response cannot replace current results.

Search reuses the selected district UUIDs as exact backend spatial scope. It also sends
the category keys of enabled Layer Registry entries, independently of their map
`minZoom`: layer switches are the user's category filter, while zoom thresholds are
only map rendering and performance rules. With every layer disabled, search makes no
request and asks the user to enable a layer. Category labels in results come from the
same registry; no second label map or client-side fuzzy/ranking logic exists.

Point results navigate with `flyTo`; LineString, Polygon, and MultiPolygon results use
their API bbox with `fitBounds`, falling back to the representative point for a
degenerate bbox. Activating a result stores its canonical UUID in the same selection
state as a map click and opens the existing `GET /api/objects/{uuid}` ObjectCard flow.
A search-selected object remains valid even when it is not present in the current
viewport GeoJSON; selection highlighting simply appears when that feature is available.
Arrow keys move between result buttons, Enter activates one, and Escape closes the
result list and returns focus to the input. Results are bounded to an internal scroll
area so Districts and Layers remain reachable through the sidebar scroll.

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
summaries. Search result clicks reuse that same flow; routing, drawing, and user data
remain outside the current scope. District scope was added by FOUNDATION 5B1 and
search UI by FOUNDATION 5B2.

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
- The generic `boundary.administrative` layer remains a technical baseline and is not
  used as district identity. The separate `domain.districts` registry supplies the
  authoritative 18 selectable application districts.
