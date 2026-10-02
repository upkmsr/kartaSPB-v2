# Map loading and visibility settings

F5.5-S6 separates four states that used to be represented by one layer checkbox:

- **enabled** — persistent user intent; the logical layer checkbox is on;
- **loadable now** — enabled and the current zoom meets the registry `minZoom`;
- **loaded** — the latest successful catalog response covered that logical layer;
- **visible** — its MapLibre render layers are enabled and the zoom is within their display range.

An enabled layer below `minZoom` remains checked and is labelled `с zN`. The fixed
minimum zoom remains part of the Layer Registry and is not a user preference.

## Loading lifecycle

Automatic loading is on by default. In this mode viewport, enabled-layer, and district
changes are debounced and reduced to one request for the latest bbox, loadable category
set, and district set. An identical successful or in-flight request is not repeated.

With automatic loading off, those changes make the catalog state
`pending-manual-load`; they do not call `/api/map/features`. The user action
`Загрузить объекты` makes one request from the latest map and filter state. Search and
the selected-district geometry overlay have independent request lifecycles.

The request states intentionally distinguish:

- `no-enabled-layers`: no ordinary layer is enabled; catalog GeoJSON is cleared;
- `waiting-for-zoom`: layers are enabled but none is currently loadable; catalog is cleared;
- `empty`: a valid request completed successfully with no features;
- `bbox-too-large` and `feature-limit`: stale catalog GeoJSON is cleared;
- `stale-error`: a network/server refresh failed and the previous successful data remains,
  with an explicit stale warning;
- `error`: no previous data can safely be shown.

Map-origin selection closes when a successful/clearing state removes its object.
Search-origin ObjectCard selection is independent of the current catalog source and is
not closed merely because viewport data is unloaded. Style reloads reinstall the source,
layers, selection filters, and district overlay from local state without turning automatic
loading back on or forcing a duplicate request.

## Persistence and reset

`frontend/src/map/mapLoadingSettings.ts` owns a versioned localStorage record containing
only `autoLoad`, visible logical-layer IDs, and the registry IDs known when the record was
written. Reads and writes tolerate unavailable storage, invalid JSON, and incompatible
versions by using current defaults.

On load, removed/unknown historical IDs are ignored. Saved choices for known IDs are
preserved, while registry IDs introduced by a future release receive their own current
`defaultVisible` value. This merge rule prevents an old settings snapshot from silently
disabling future layers.

`Сбросить настройки` resets only automatic loading and logical-layer visibility to their
current defaults. It does not reset map position, zoom, district selection, search, or the
ObjectCard.
