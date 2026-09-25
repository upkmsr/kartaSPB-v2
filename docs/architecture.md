# Architecture

## Product boundary

KARTASPB v2 is a desktop-first / desktop-only GIS application.

- Minimum supported viewport width: **1280 px**.
- Primary input: mouse and keyboard.
- Target resolutions include 1440×900 and 1920×1080.
- Phone and tablet-specific layouts, navigation, controls, breakpoints, touch QA, and PWA mobile UX are outside project scope.

At narrower desktop window sizes, the application may show a minimum-width notice instead of attempting a mobile layout.

## Data flow

The foundation boundary is explicit:

```text
FOUNDATION 1 — OSM raw data
nodes / ways / relations
        ↓
FOUNDATION 2 — correct GIS interpretation
multipolygons / holes / boundaries / routes / ordered members
        ↓
FOUNDATION 3A — provider-independent canonical GIS identity
objects / source bindings / relationships / provenance
        ↓
FOUNDATION 3B — application meaning
school / pharmacy / park / road / transport / ...
```

FOUNDATION 2 and 3A do not assign application categories. FOUNDATION 2 turns
the OSM relation model into validated GIS structures; FOUNDATION 3A gives
eligible features stable provider-independent identity and provenance.

```text
External open data
        ↓
Provider PBF / source adapter
        ↓
Immutable local source (`data/sources`)
        ↓
Derived extract (`data/cache`)
        ↓
Source-shaped PostGIS staging
        ↓
Derived OSM geometry and ordered relations
        ↓
Canonical GIS model
        ↓
FOUNDATION 3B categories
        ↓
PostGIS
        ↓
Domain logic
        ↓
API
        ↓
Desktop frontend / map / analytics
```

The source-to-canonical boundary is the central architectural rule. The
frontend and domain logic consume canonical objects; they must not need to know
whether a future school, park, road, or medical category came from
OpenStreetMap or an official registry.

## Components

- **Frontend:** React, TypeScript, Vite, and MapLibre GL JS. The desktop map consumes bounded canonical GeoJSON from the generic map API; source-specific data never reaches UI components.
- **Backend:** FastAPI exposes transport concerns. Domain code owns application meaning. The data package will own adapters, imports, and normalisation.
- **Database:** PostgreSQL/PostGIS holds the canonical spatial system of record. Alembic exclusively manages schema changes.
- **OSM data engine:** a dedicated Docker service combines pinned Osmium and osm2pgsql versions with Python orchestration. Osmium validates and extracts; osm2pgsql Flex translates OSM primitives without category filtering and assembles mature multipolygon/boundary geometry.
- **Infrastructure:** Docker Compose makes database initialisation, migrations, API startup, frontend, and data tooling deterministic.

## Real map

FOUNDATION 4B keeps one `catalog-features` GeoJSON source for the current viewport.
A central layer registry maps the ten public category keys to ordered MapLibre
render layers, visibility defaults, interaction rules, and minimum zooms. A
logical category can render points, polygons, and outlines without additional
HTTP requests.

Viewport loading runs after `moveend` with a 200 ms debounce. The client checks
the API bbox limits before sending a request, aborts superseded work, and uses a
monotonic sequence guard against late responses. Feature-limit and network
errors retain the last complete source; a successful empty result deliberately
clears it. Object selection loads compact canonical details by UUID and never
reads raw OSM payloads.

The normal development style is the token-free OpenFreeMap dark basemap selected
through `VITE_MAP_STYLE_URL`, with explicit OpenFreeMap/OpenMapTiles/OpenStreetMap
attribution. A local background-only style remains the emergency fallback. A
style failure reinstalls that fallback and then restores the single catalog
source, render layers, and most recent FeatureCollection.

The production pipeline explicitly emits the MapLibre worker as a JavaScript
asset and configures MapLibre with that URL before map construction. The map
delivery path is therefore:

```text
PostGIS catalog
  -> generic bounded GeoJSON API
  -> MapLibre worker
  -> one catalog GeoJSON source
  -> Layer Registry
  -> production render layers
  -> canonical UUID click and details card
```

This explicit worker path prevents the previously observed production failure:
the worker asset was not emitted at the URL MapLibre requested, nginx returned
the SPA `index.html` fallback with `text/html`, and GeoJSON/vector source
processing never started even though the DOM and WebGL canvas were healthy.

## Known map data quality

The water layer represents the baseline OSM mappings implemented in FOUNDATION
3B, including the supported polygon water semantics and `waterway=river` line
ways. Coverage is not exhaustive for every OSM water semantic; detailed river
and water enrichment is deferred to a dedicated data-enrichment stage.

`boundary.administrative` remains a generic technical baseline layer. It is not
an authoritative representation of the exact 18 Saint Petersburg districts.
Exact district semantics and an authoritative/derived district registry are
deferred to FOUNDATION 5.

## Dependency direction

Source-specific concepts stop at the data layer. Domain logic may depend on
canonical models, and API handlers may depend on domain services. The reverse
dependencies are not allowed. Canonicalization reads `staging` and `derived`
and writes `catalog`; it does not create school, pharmacy, park, road, or
transport categories.

## Deferred work

Exact administrative clipping, routing, scoring, exhaustive water semantics,
and the authoritative district registry remain deferred. Transport routes
retain their ordered semantics in `derived` and are deliberately excluded from
generic `catalog.objects`.
# Category boundary

FOUNDATION 3B classifies canonical objects through declarative taxonomy and
source-specific rules. Taxonomy, matching, and provenance are centralized; adding a
category does not add an importer. API, map, UI, GTFS, and cross-provider merge policy
remain outside this foundation.
