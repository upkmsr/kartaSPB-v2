# Search UX contract

This contract is the backend boundary for the F5B search UI. It does not prescribe a
specific React component structure.

## Request

- Endpoint: `GET /api/search`.
- `q`: required, 3–100 characters after trimming, whitespace collapse, lowercasing, and
  Russian `ё` to `е` normalization.
- `categories`: optional comma-separated enabled category keys.
- `districts`: optional comma-separated enabled domain district UUIDs; matching uses
  exact geometry intersection.
- `limit`: 20 by default, 50 maximum.
- Recommended input debounce: 250 ms.
- The client must cancel the previous fetch with `AbortController` and must also ignore a
  response whose monotonically increasing request token is no longer current.
- Empty and shorter-than-three-character input must not issue a request.

## Result

Every item contains a canonical UUID `id`, `name`, active `categories`, `object_kind`,
`geometry_type`, a GeoJSON Point `representative_point`, and a four-number `bbox`.
Duplicate names remain distinct objects; `id`, not name, is the identity.

Representative-point semantics are:

- Point: the original point.
- LineString: `ST_LineInterpolatePoint(geom, 0.5)`.
- Polygon and MultiPolygon: `ST_PointOnSurface(geom)`.
- MultiLineString: unsupported and not currently present in the active searchable catalog.

On selection, fetch full details from `GET /api/objects/{id}`. Point results navigate with
`flyTo`. LineString results may use the representative point and/or `fitBounds(bbox)`.
Polygon and MultiPolygon results use `fitBounds(bbox)`.

## Empty and error states

- Empty input and input below the minimum are client-prevented. If sent anyway, the API
  responds with structured `422 invalid_request`.
- Unknown category responds with structured `422 unknown_category`.
- Unknown or disabled district responds with structured `422 unknown_district`.
- A valid query with no matches responds `200` with `{"type":"SearchResults","results":[]}`.
- Server failures are `5xx` and must show a retryable error state, not an empty result state.
