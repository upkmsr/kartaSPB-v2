# Map API

FOUNDATION 4A exposes canonical catalog data through two read-only generic endpoints.
It does not expose raw OSM tags, source candidate payloads, import-run internals, search,
or category-specific routes.

## Map features

`GET /api/map/features` accepts:

- `bbox=minLon,minLat,maxLon,maxLat`;
- `categories=category.one,category.two` (1–10 enabled catalog categories);
- `limit` (default 1000, maximum 5000).

The response is a GeoJSON FeatureCollection. Every feature uses the canonical UUID as
its GeoJSON ID and exposes only `name`, all active `categories`, and `object_kind`.
Selection uses both the PostGIS bounding-box operator and `ST_Intersects`.

The API fetches `limit + 1`. If the complete result would exceed the requested limit it
returns HTTP 422 with `feature_limit_exceeded`; it never presents a truncated collection
as complete. Bboxes are limited to 0.5° longitude span, 0.3° latitude span, and 0.1 square
degrees. Antimeridian-crossing boxes are not supported in FOUNDATION 4A.

## Object details

`GET /api/objects/{uuid}` returns an active canonical object's name, active categories,
kind, geometry type, canonical properties, and compact source summaries. Inactive and
unknown objects return 404; malformed UUIDs return 422.

Interactive schemas and request details are available from FastAPI at `/docs`.
