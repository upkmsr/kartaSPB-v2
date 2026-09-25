# Map API

The backend exposes canonical catalog data through read-only generic endpoints.
It does not expose raw OSM tags, source candidate payloads, import-run internals, or
category-specific routes.

## Districts

`GET /api/districts` returns the 18 enabled application districts in deterministic
`display_order`. Each entry contains its stable domain UUID, display name, ASCII slug,
display order, and bbox. Exact district polygons are deliberately omitted: the bbox is
sufficient for the planned selector and `fitBounds`, while exact canonical geometry
remains internal for spatial filtering. A district detail endpoint is therefore not
needed.

## Map features

`GET /api/map/features` accepts:

- `bbox=minLon,minLat,maxLon,maxLat`;
- `categories=category.one,category.two` (1–10 enabled catalog categories);
- optional `districts=uuid.one,uuid.two` (up to 18 unique domain district UUIDs);
- `limit` (default 1000, maximum 5000).

Duplicate district IDs are normalized while preserving first-seen order. Invalid UUIDs,
unknown districts, and disabled districts return structured HTTP 422 errors. Omitting
`districts` uses the original map query with no district join. One district uses its exact
canonical geometry directly; multiple districts build one materialized unary-union scope.
All cases still require the viewport, and category, bbox-size, `limit + 1`, and
`feature_limit_exceeded` behavior is unchanged.

The response is a GeoJSON FeatureCollection. Every feature uses the canonical UUID as
its GeoJSON ID and exposes only `name`, all active `categories`, and `object_kind`.
Selection uses both the PostGIS bounding-box operator and `ST_Intersects`.
District filtering also uses `&&` plus `ST_Intersects`, so points, lines, polygons, and
multipolygons use true spatial intersection rather than centroid membership. An object
crossing district boundaries is visible when either intersected district is selected.

The API fetches `limit + 1`. If the complete result would exceed the requested limit it
returns HTTP 422 with `feature_limit_exceeded`; it never presents a truncated collection
as complete. Bboxes are limited to 0.5° longitude span, 0.3° latitude span, and 0.1 square
degrees. Antimeridian-crossing boxes are not supported in FOUNDATION 4A.

## Object details

`GET /api/objects/{uuid}` returns an active canonical object's name, active categories,
kind, geometry type, canonical properties, and compact source summaries. Inactive and
unknown objects return 404; malformed UUIDs return 422.

Interactive schemas and request details are available from FastAPI at `/docs`.

## Search

`GET /api/search` searches active canonical objects by normalized `name`. The required
`q` parameter is 2–100 characters after trimming and whitespace normalization. Search is
case-insensitive and treats Russian `ё` as `е`. Optional `categories` and `districts`
parameters use the same enabled-category and exact district-intersection contracts as the
map API. `limit` defaults to 20 and is capped at 50.

Ranking is deterministic: exact, prefix, word-prefix, substring, and trigram matches are
ordered by match quality, while repeated normalized names are interleaved so a single
duplicate name cannot hide all other relevant names. Duplicate-name objects are never
collapsed; canonical UUID remains result identity.

Each result contains the canonical ID and name, all active categories, object kind,
geometry type, a representative point, and bbox. Points remain unchanged; other geometry
types use `ST_PointOnSurface`, which avoids the outside-polygon behavior possible with a
centroid. Full geometry and source details continue to come from the existing map and
object-detail endpoints.

Search uses the generated `catalog.objects.search_name` column and a partial `pg_trgm`
GIN index for active named objects. It does not search raw provider tags or introduce an
external search service.
