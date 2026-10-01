# Search v2 UX contract

This document is the API/frontend boundary for entity-aware search. Search is a
lightweight suggestion and navigation service, not a geocoder, address search, or
routing API.

## Request

- Endpoint: `GET /api/search`.
- `q`: required, 3–100 characters after Search v2 normalization.
- `categories`: optional comma-separated enabled category keys. It scopes ordinary
  objects and logical facilities; streets remain searchable independently.
- `districts`: optional comma-separated enabled domain district UUIDs. Matching uses
  exact geometry intersection with the object geometry, facility display geometry, or
  stored logical street geometry.
- `limit`: 20 by default, 50 maximum. The limit is applied after logical facility and
  street collapsing.
- `include_objects`: true by default. When false, ordinary objects and facilities are
  omitted but street search remains active. The frontend uses this mode when no object
  layer is enabled.
- Recommended input debounce: 250 ms.

The client cancels the previous fetch with `AbortController` and also ignores any
response whose monotonically increasing request token is no longer current. Empty and
shorter-than-three-character input does not issue a request.

## Normalization and ranking

Client, request validation, persisted object search text, and street refresh use the
same deterministic comparison form:

1. Unicode NFKC compatibility normalization;
2. NBSP replacement with an ordinary space;
3. lowercase;
4. Russian `ё/Ё` to `е/Е` folding;
5. whitespace collapse and trim.

Display names are never rewritten. There is no transliteration or broad typo
correction. Ranking is deterministic: exact normalized match, prefix, word-boundary
substring, weaker substring/trigram order, then stable name/type/UUID tie-breaks.

## Result identity

Each item has this explicit shape:

```json
{
  "id": "logical-or-canonical-uuid",
  "result_type": "object|facility|street",
  "detail_object_id": "canonical-uuid-or-null",
  "name": "display name",
  "categories": ["category.key"],
  "object_kind": "semantic kind",
  "geometry_type": "Point|LineString|Polygon|MultiPolygon|MultiLineString",
  "representative_point": {"type": "Point", "coordinates": [30.3, 59.9]},
  "bbox": [30.2, 59.8, 30.4, 60.0]
}
```

The semantics are:

| `result_type` | `id` | `detail_object_id` | Navigation geometry |
|---|---|---|---|
| `object` | canonical object UUID | same canonical UUID | canonical geometry |
| `facility` | logical facility UUID | representative canonical UUID | facility display geometry |
| `street` | logical street UUID | `null` | stored aggregate street geometry |

An active facility's Point/site/building members are excluded from ordinary results;
matching any member emits the facility once. Unlinked facilities remain ordinary
objects. Street member ways are likewise excluded from ordinary results and emit one
result per conservative logical street component.

## Selection and navigation

- Point objects use `flyTo`; line and polygonal results use `fitBounds(bbox)`.
- Object selection requests `GET /api/objects/{detail_object_id}`.
- Facility selection navigates with logical display geometry and opens the existing
  canonical ObjectCard through its explicit `detail_object_id`.
- Street selection fits the logical street bbox, clears canonical ObjectCard state,
  and never requests `/api/objects/{street_entity_uuid}`.
- Search selection is keyed by logical result `id`; map clicks clear that search
  selection without changing district or layer state.
- ArrowUp, ArrowDown, Enter, Escape, clear, retry, empty, debounce, and stale-response
  behavior remain part of the accessible desktop contract.

## Empty and error states

- Empty input and input below the minimum are client-prevented. If sent anyway, the API
  responds with structured `422 invalid_request`.
- Unknown category responds with structured `422 unknown_category`.
- Unknown or disabled district responds with structured `422 unknown_district`.
- A valid query with no matches responds `200` with
  `{"type":"SearchResults","results":[]}`.
- Server failures are `5xx` and show a retryable error state, not an empty state.
